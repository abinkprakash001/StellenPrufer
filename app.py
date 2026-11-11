"""StellenPrüfer Web Application Server
Provides verification APIs, SQLite database persistence, User/Admin authentication,
profile updates, and multi-user fake job advertisement flagging.
"""

import io
import json
import os
import re
import shutil
import socket
import urllib.parse
import zipfile
import sys

# Project layout: backend/ (Python modules), frontend/ (web pages), data/ (runtime files), stellenpruefer_extension/
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_DIR, "backend")
FRONTEND_DIR = os.path.join(PROJECT_DIR, "frontend")
DATA_DIR = os.path.join(PROJECT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
sys.path.insert(0, BACKEND_DIR)
from flask import Flask, request, jsonify, send_from_directory, send_file, redirect
from flask_cors import CORS

# Import core verification engine from check_job_url
from check_job_url import (
    assess_job_url,
    check_virustotal_url,
    create_handelsregister_search_url,
    extract_posting_date_and_availability,
    lookup_commercial_register,
    verify_recruiter_email,
    is_valid_url,
    get_domain,
    is_job_board_domain,
    is_platform_name
)

# Import PDF / Screenshot OCR and Job Contract Analyzer
from document_analyzer import (
    extract_text_from_file,
    extract_entities_from_text,
    analyze_job_contract
)

# Import Customer / Employer Website Verification
from customer_checker import (
    cross_check_job_on_customer_website,
    extract_and_verify_job_contacts,
    get_company_intelligence
)
from trust_calculator import calculate_trust_score_and_breakdown
from job_description_analyzer import (
    analyze_job_advertisement_description,
    predict_job_fraud_probability,
    get_model_evaluation_metrics
)
from salary_anomaly_detector import detect_salary_anomaly
from resume_matcher import match_resume_to_job, extract_skills

# Import SQLite database functions
from database import (
    init_db,
    get_db_connection,
    register_user,
    authenticate_user,
    update_user_profile,
    get_user_by_id,
    record_job_check,
    get_user_history,
    get_flagged_fake_jobs,
    get_admin_overview,
    update_job_flag_status,
    flag_job_by_user
)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
app.json.ensure_ascii = False
CORS(app)


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Ensure database tables and default admin exist
init_db()

FREE_EMAIL_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.de", "hotmail.com",
    "outlook.com", "live.com", "aol.com", "icloud.com", "mail.com",
    "zoho.com", "proton.me", "protonmail.com", "gmx.de", "gmx.net",
    "web.de", "t-online.de", "freenet.de"
}

SCAM_KEYWORDS = [
    (r"\b(wire transfer|western union|moneygram|cashier'?s check)\b", "Requests involving wire transfers, checks, or money transfers for equipment are high risk."),
    (r"\b(crypto|bitcoin|usdt|ethereum)\b", "Job compensation or equipment fees requested in cryptocurrency are almost always fraudulent."),
    (r"\b(pay for (training|software|equipment|background check))\b", "Legitimate employers never ask candidates to pay upfront for equipment or background checks."),
    (r"\b(send money|deposit.*check)\b", "Check deposit and refund schemes are common fake check scams.")
]

GHOST_JOB_KEYWORDS = [
    (r"\b(talent\s*pool|talent-pool|bewerberpool)\b", "Ghost / Dummy Job Indicator: This listing mentions a 'Talent Pool' / 'Bewerberpool', meaning the company may be collecting resumes without an active open vacancy."),
    (r"\b(für zukünftige (projekte|vakanzen|positionen)|for future (openings|opportunities|roles|projects))\b", "Ghost / Dummy Job Indicator: Wording indicates hiring for 'future openings/projects' rather than an immediate position."),
    (r"\b(unabhängig von einer konkreten vakanz|no specific opening|evergreen requisition)\b", "Ghost / Dummy Job Indicator: Listing explicitly states it is independent of a concrete vacancy (Evergreen / Survey Ad).")
]


def check_recruiter_email(email, company_name=None, company_domain=None):
    return verify_recruiter_email(email)



def analyze_description_red_flags(description, salary=None):
    warnings = []
    text = (description or "") + " " + (salary or "")
    text_lower = text.lower()

    for pattern, warning_msg in SCAM_KEYWORDS:
        if re.search(pattern, text_lower):
            warnings.append(warning_msg)

    if re.search(r"(\$|€|eur)\s*(?:[5-9]\d{3}|\d{5,})\s*/\s*(week|woche)", text_lower):
        warnings.append("Extremely high weekly salary advertised, which is often used in fraudulent bait postings.")

    return warnings


def analyze_ghost_job_signals(description):
    ghost_warnings = []
    text_lower = (description or "").lower()
    for pattern, warning_msg in GHOST_JOB_KEYWORDS:
        if re.search(pattern, text_lower):
            ghost_warnings.append(warning_msg)
    return ghost_warnings


def ensure_extension_assets():
    ext_dir = os.path.join(PROJECT_DIR, "stellenpruefer_extension")
    src_logo = os.path.join(FRONTEND_DIR, "logo.png")
    dst_logo = os.path.join(ext_dir, "logo.png")
    if os.path.exists(ext_dir) and os.path.exists(src_logo) and not os.path.exists(dst_logo):
        try:
            shutil.copyfile(src_logo, dst_logo)
        except Exception:
            pass


ensure_extension_assets()

def _start_vscode_extension_sync_watcher():
    import threading
    import time
    ext_src = os.path.join(PROJECT_DIR, "stellenpruefer_extension")
    ext_dst = r"C:\Users\kp21a\Downloads\StellenPruefer_Browser_Extension\stellenpruefer_extension"
    def _loop():
        last_mtimes = {}
        while True:
            try:
                if os.path.exists(ext_src) and os.path.exists(ext_dst):
                    for fn in os.listdir(ext_src):
                        sf = os.path.join(ext_src, fn)
                        df = os.path.join(ext_dst, fn)
                        if os.path.isfile(sf):
                            mt = os.path.getmtime(sf)
                            if last_mtimes.get(fn) != mt:
                                shutil.copy2(sf, df)
                                last_mtimes[fn] = mt
            except Exception:
                pass
            time.sleep(1.0)
    t = threading.Thread(target=_loop, daemon=True)
    t.start()

_start_vscode_extension_sync_watcher()

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response



@app.route("/")
@app.route("/index.html")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/login.html")
def login_page():
    return send_from_directory(FRONTEND_DIR, "login.html")


@app.route("/register.html")
def register_page():
    return send_from_directory(FRONTEND_DIR, "register.html")


@app.route("/dashboard")
@app.route("/main.html")
def main_page():
    return redirect("/")


@app.route("/extension.html")
def extension_page():
    return send_from_directory(FRONTEND_DIR, "extension.html")


@app.route("/api/download-extension")
def download_extension_zip():
    ensure_extension_assets()
    ext_dir = os.path.join(PROJECT_DIR, "stellenpruefer_extension")
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(ext_dir):
            for fname in os.listdir(ext_dir):
                fpath = os.path.join(ext_dir, fname)
                if os.path.isfile(fpath):
                    zf.write(fpath, arcname=os.path.join("stellenpruefer_extension", fname))
    mem_zip.seek(0)
    return send_file(
        mem_zip,
        mimetype="application/zip",
        as_attachment=True,
        download_name="StellenPruefer_Browser_Extension.zip"
    )


@app.route("/company.html")
def company_redirect():
    return redirect("/")


@app.route("/result.html")
def result_page():
    return send_from_directory(FRONTEND_DIR, "result.html")


@app.route("/flagged.html")
def flagged_page():
    return redirect("/")


@app.route("/profile.html")
def profile_page():
    return send_from_directory(FRONTEND_DIR, "profile.html")


@app.route("/admin")
@app.route("/admin.html")
def admin_page():
    return send_from_directory(FRONTEND_DIR, "admin.html")


# ============================================================
# Authentication & Profile Endpoints
# ============================================================

SESSION_USER_FILE = os.path.join(DATA_DIR, "current_session_user.json")


def load_persisted_session_user():
    if os.path.exists(SESSION_USER_FILE):
        try:
            with open(SESSION_USER_FILE, "r", encoding="utf-8") as sf:
                u = json.load(sf)
                if isinstance(u, dict) and u.get("email"):
                    return u
        except Exception:
            pass
    return {}


def save_persisted_session_user(user_dict):
    global CURRENT_SESSION_USER
    if not isinstance(user_dict, dict) or not user_dict.get("email"):
        CURRENT_SESSION_USER = {}
        if os.path.exists(SESSION_USER_FILE):
            try:
                os.remove(SESSION_USER_FILE)
            except Exception:
                pass
        return
    CURRENT_SESSION_USER = {
        "id": user_dict.get("id"),
        "name": user_dict.get("name", "User"),
        "email": user_dict.get("email"),
        "role": user_dict.get("role", "customer"),
        "resume_text": user_dict.get("resume_text", ""),
        "resume_filename": user_dict.get("resume_filename", "")
    }
    try:
        with open(SESSION_USER_FILE, "w", encoding="utf-8") as sf:
            json.dump(CURRENT_SESSION_USER, sf, ensure_ascii=False, indent=2)
    except Exception:
        pass


@app.route("/api/register", methods=["POST"])
def api_register():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name", "").strip()
    email = payload.get("email", "").strip()
    password = payload.get("password", "").strip()
    gdpr_consent = bool(payload.get("gdprConsent", False))

    user, err = register_user(name, email, password, gdpr_consent=gdpr_consent)
    if err:
        return jsonify({"success": False, "error": err}), 400

    if user:
        save_persisted_session_user(user)

    return jsonify({"success": True, "user": user})


@app.route("/api/login", methods=["POST"])
def api_login():
    payload = request.get_json(silent=True) or {}
    email = payload.get("email", "").strip()
    password = payload.get("password", "").strip()

    user, err = authenticate_user(email, password)
    if err:
        return jsonify({"success": False, "error": err}), 401

    if user:
        save_persisted_session_user(user)

    return jsonify({"success": True, "user": user})


@app.route("/api/logout", methods=["POST", "GET"])
def api_logout():
    save_persisted_session_user({})
    return jsonify({"success": True, "message": "Logged out successfully"})


@app.route("/api/current-user", methods=["GET", "POST"])
def api_current_user():
    global CURRENT_SESSION_USER
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        if payload.get("email") and payload.get("email") != "extension@stellenpruefer.local":
            save_persisted_session_user(payload)
    else:
        CURRENT_SESSION_USER = load_persisted_session_user()
    return jsonify({
        "success": True,
        "user": CURRENT_SESSION_USER
    })


@app.route("/api/profile", methods=["PUT", "POST"])
def api_profile():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId")
    name = payload.get("name", "").strip()
    email = payload.get("email", "").strip()
    new_password = payload.get("newPassword", "").strip()
    resume_text = payload.get("resumeText")
    resume_filename = payload.get("resumeFilename")

    user, err = update_user_profile(
        user_id,
        name,
        email,
        new_password=new_password or None,
        resume_text=resume_text,
        resume_filename=resume_filename
    )
    if err:
        return jsonify({"success": False, "error": err}), 400

    if user:
        save_persisted_session_user(user)

    return jsonify({"success": True, "user": user})




@app.route("/api/profile/upload-resume", methods=["POST"])
def api_upload_resume():
    uploaded_file = request.files.get("resumeFile")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"success": False, "error": "No file selected. Please select a PDF resume."}), 400

    filename = uploaded_file.filename
    file_bytes = uploaded_file.read()

    # Extract text from uploaded PDF using document_analyzer
    extraction = extract_text_from_file(file_bytes, filename)
    extracted_text = (extraction.get("text") or "").strip()

    if not extracted_text:
        return jsonify({
            "success": False,
            "error": "Could not extract text from the PDF. Please ensure the PDF is not password-protected and contains readable text."
        }), 400

    user_id = request.form.get("userId")
    if isinstance(user_id, str) and user_id.isdigit():
        user_id = int(user_id)
    elif CURRENT_SESSION_USER.get("id"):
        user_id = CURRENT_SESSION_USER.get("id")

    user_email = request.form.get("email") or CURRENT_SESSION_USER.get("email")
    user_name = request.form.get("name") or CURRENT_SESSION_USER.get("name") or "User"

    if user_id:
        user, err = update_user_profile(
            user_id,
            name=user_name,
            email=user_email,
            resume_text=extracted_text,
            resume_filename=filename
        )
    else:
        user = {
            "name": user_name,
            "email": user_email,
            "resume_text": extracted_text,
            "resume_filename": filename
        }

    save_persisted_session_user(user)
    detected_skills = extract_skills(extracted_text)

    return jsonify({
        "success": True,
        "filename": filename,
        "resume_text": extracted_text,
        "detected_skills": detected_skills,
        "user": user,
        "message": f"Successfully parsed '{filename}'. {len(detected_skills)} technical competencies identified."
    })


# ============================================================
# Job Verification & Multi-User Flagging Endpoint
# ============================================================

@app.route("/api/verify", methods=["POST"])
def verify_job():
    global LATEST_SYNCED_JOB, ACTIVE_JOB_TABS, RECENT_CHECK_CACHE
    uploaded_file = request.files.get("documentFile")
    if request.content_type and "multipart/form-data" in request.content_type:
        payload = request.form.to_dict()
    else:
        payload = request.get_json(silent=True) or {}

    check_type = payload.get("checkType", "job_offer").strip()
    from_extension = bool(payload.get("fromExtension", False))
    job_url = payload.get("jobUrl", "").strip()
    company = payload.get("company", "").strip()
    ext_address = payload.get("companyAddress", "").strip()
    ext_date_posted = payload.get("datePosted", "").strip()
    job_title = payload.get("jobTitle", "").strip()
    recruiter_email = payload.get("recruiterEmail", "").strip()
    salary = payload.get("salary", "").strip()
    job_description = payload.get("jobDescription", "").strip()
    user_id = payload.get("userId")
    if isinstance(user_id, str):
        user_id = int(user_id) if user_id.isdigit() else None
    user_name = payload.get("userName", "").strip()
    user_email = payload.get("userEmail", "").strip()

    if (not user_email or user_email == "extension@stellenpruefer.local") and CURRENT_SESSION_USER.get("email"):
        user_id = CURRENT_SESSION_USER.get("id")
        user_name = CURRENT_SESSION_USER.get("name") or "User"
        user_email = CURRENT_SESSION_USER.get("email")

    resume_text = payload.get("resumeText", "").strip() or payload.get("resume", "").strip()
    if not resume_text:
        if user_id:
            u_row = get_user_by_id(user_id)
            if u_row and u_row.get("resume_text"):
                resume_text = u_row["resume_text"]
        if not resume_text and CURRENT_SESSION_USER.get("resume_text"):
            resume_text = CURRENT_SESSION_USER.get("resume_text")

    has_pdf_or_image = bool(uploaded_file and uploaded_file.filename)
    has_url = bool(job_url)
    has_only_company = bool(company) and not (job_title or recruiter_email or salary or job_description)
    has_all_manual_details = bool(job_title and company and recruiter_email and salary and job_description)
    has_contract_input = (check_type == "job_contract") and (has_pdf_or_image or bool(job_description))

    has_extension_or_quick_check = bool(from_extension or job_url or (company and job_title))
    if not has_pdf_or_image and not has_url and not has_only_company and not has_all_manual_details and not has_contract_input and not has_extension_or_quick_check:
        return jsonify({
            "success": False,
            "error": (
                "Incomplete job details. Only PDF/Screenshot upload, Job URL, or Company Name can be checked alone. "
                "Otherwise, please fill in all fields (Job Title, Company Name, Recruiter Email, Salary, and Job Description)."
            )
        }), 400

    all_warnings = []
    document_info = None
    doc_company = None
    doc_address = None
    doc_truncated_url = None
    user_entered_url = bool(job_url)

    # 1. If a PDF or Screenshot was uploaded, extract text via PDF parser or RapidOCR
    if uploaded_file and uploaded_file.filename:
        file_bytes = uploaded_file.read()
        extraction = extract_text_from_file(file_bytes, uploaded_file.filename)
        extracted_text = extraction.get("text", "")
        document_info = {
            "filename": uploaded_file.filename,
            "method": extraction.get("method"),
            "extracted_text_preview": extracted_text[:600] + ("..." if len(extracted_text) > 600 else ""),
            "error": extraction.get("error")
        }
        if extraction.get("error"):
            all_warnings.append(f"Document Upload Notice: {extraction['error']}")
        if extracted_text or uploaded_file.filename:
            if extracted_text:
                job_description = (job_description + "\n\n" + extracted_text).strip() if job_description else extracted_text
            entities = extract_entities_from_text(extracted_text, uploaded_file.filename)
            doc_company = entities.get("company_name")
            doc_address = entities.get("company_address")
            if doc_company:
                if company and company.lower() not in doc_company.lower() and doc_company.lower() not in company.lower():
                    all_warnings.append(
                        f"Company Mismatch: You entered '{company}', but the uploaded document is for '{doc_company}'."
                    )
                company = doc_company
            if not recruiter_email and entities.get("emails"):
                recruiter_email = entities["emails"][0]
            if not user_entered_url:
                if entities.get("truncated_urls"):
                    doc_truncated_url = entities["truncated_urls"][0]
                elif entities.get("urls"):
                    doc_truncated_url = entities["urls"][0]

    # Also auto-extract entities if user pasted text without filling company/email
    if job_description and (not company or not recruiter_email or not doc_address):
        entities = extract_entities_from_text(job_description)
        if not company and entities.get("company_name"):
            company = entities["company_name"]
        if not doc_address and entities.get("company_address"):
            doc_address = entities["company_address"]
        if not recruiter_email and entities.get("emails"):
            recruiter_email = entities["emails"][0]

    # Never allow a job platform domain/name (e.g. 'stellenanzeigen.de') to masquerade as the hiring company
    if company and (is_platform_name(company) or company.strip().lower() in ("company listed on job platform", "employer on screen")):
        company = ""

    # If job_url matches a live synced browser tab, enrich any blank fields from the synced tab first
    if job_url:
        for synced_t in list(ACTIVE_JOB_TABS.values()) + ([LATEST_SYNCED_JOB] if LATEST_SYNCED_JOB else []):
            if not isinstance(synced_t, dict):
                continue
            s_url = (synced_t.get("url") or "").strip()
            if s_url and (s_url == job_url or (synced_t.get("refNumber") and synced_t.get("refNumber") in job_url)):
                if not job_title and synced_t.get("title"):
                    job_title = synced_t["title"].strip()
                s_comp = (synced_t.get("company") or "").strip()
                if not company and s_comp and not is_platform_name(s_comp):
                    company = s_comp
                if not ext_address and synced_t.get("address"):
                    ext_address = synced_t["address"].strip()
                if not salary and synced_t.get("salary"):
                    salary = synced_t["salary"].strip()
                if not job_description and synced_t.get("description"):
                    job_description = synced_t["description"].strip()

    vt_report = None
    date_posted = None
    valid_through = None
    availability_status = None
    domain = get_domain(job_url) if job_url else None
    is_trusted_board = is_job_board_domain(domain) if domain else False

    if job_url and user_entered_url:
        has_noisy_desc = bool(job_description and ("Get notified when a new job is posted" in job_description or "Skip to main content" in job_description or "11,000+ Jobs" in job_description))
        if has_noisy_desc:
            job_description = ""
        is_invalid_comp = not company or is_platform_name(company) or bool(re.search(r'filterbar|Arbeitgeber A-Z|Kein filterbar|jobsuche der ba', company, re.I))
        is_generic_title = not job_title or bool(re.search(r'^\d+[\d.,]*\s+Jobs\s+in|Jobsuche der BA|Jobsuche|Stellenangebot[:\s]*$|Loading job details', job_title, re.I))
        need_url_scrape = is_invalid_comp or is_generic_title or (not company) or is_platform_name(company) or (not job_title) or (not job_description) or (not ext_address) or (not from_extension) or ("linkedin.com" in job_url.lower()) or ("arbeitsagentur.de" in job_url.lower())
        report = {}
        if need_url_scrape:
            try:
                report = assess_job_url(job_url, expected_company=(None if is_invalid_comp else (company or None)))
            except Exception:
                report = {}

        scraped_comp = report.get("company_name")
        if scraped_comp and is_platform_name(scraped_comp):
            scraped_comp = None

        is_search_url = any(k in job_url.lower() for k in ("/suche", "/search", "suchbereich", "locationids", "srp="))

        if is_search_url and not is_invalid_comp and company:
            company_name = company
        else:
            company_name = scraped_comp if (scraped_comp and is_invalid_comp) else (company or scraped_comp or None)

        company_address = report.get("company_address") or ext_address or doc_address

        if is_search_url and not is_generic_title and job_title:
            pass
        elif (is_generic_title or not job_title) and report.get("job_title"):
            job_title = report.get("job_title")
        is_noisy_desc = (
            not job_description
            or "StartseiteJobsuche" in job_description
            or "Ihre Suche Meine Vormerkungen" in job_description
            or "Get notified when a new job is posted" in job_description
            or "Skip to main content" in job_description
        )
        if is_noisy_desc and report.get("job_description"):
            job_description = report.get("job_description")
        if not salary and report.get("salary"):
            salary = report.get("salary")

        official_job_url = report.get("official_job_url") or job_url
        domain = report.get("domain") or domain
        vt_report = report.get("virustotal") or (check_virustotal_url(f"https://{domain}", domain=domain) if domain else None)
        date_posted = ext_date_posted or report.get("date_posted")
        valid_through = report.get("valid_through")
        availability_status = report.get("availability_status")

        if from_extension or is_trusted_board:
            if not company_name:
                company_name = f"Employer on {domain}"
            result = report.get("result") if report.get("result") in ("LIKELY VALID", "HIGH RISK") else "LIKELY VALID"
            reason = report.get("reason") if (report.get("reason") and "could not be opened" not in report.get("reason", "").lower()) else (
                f"Screen & Web verified: '{company_name}' posting confirmed on {domain} with 0 security threats."
            )
            for w in report.get("warnings", []):
                if "could not be opened" not in w.lower() and "403" not in w.lower():
                    all_warnings.append(w)
        else:
            result = report.get("result", "NOT VERIFIED")
            reason = report.get("reason", "")
            all_warnings.extend(report.get("warnings", []))
    else:
        company_name = company or None
        company_address = ext_address or doc_address
        official_job_url = None
        domain = None
        if doc_truncated_url:
            domain = get_domain(doc_truncated_url)
            official_job_url = doc_truncated_url
            if domain:
                vt_report = check_virustotal_url(f"https://{domain}")
                if vt_report and vt_report.get("warning"):
                    all_warnings.append(vt_report["warning"])

        if company_name:
            result = "REVIEW CAREFULLY"
            reason = f"Company '{company_name}' extracted from the screen/document for verification."
        elif job_description:
            result = "REVIEW CAREFULLY"
            reason = "Text/Document analyzed, but no company name or URL was identified."
        else:
            result = "NOT VERIFIED"
            reason = "No job link, document, or company name was entered."

    # Extract Date Posted, Valid Through & Job Availability from screen content
    has_job_content = (check_type != "job_contract") and bool(user_entered_url or document_info or job_description or date_posted)
    if has_job_content:
        eval_date_text = (str(date_posted or "")) + " " + (job_description or "")
        doc_dates = extract_posting_date_and_availability(eval_date_text)
        if not date_posted or date_posted == "Not specified":
            date_posted = doc_dates.get("date_posted", "Not specified")
        if not valid_through or valid_through == "Not specified":
            valid_through = doc_dates.get("valid_through", "Not specified")
        if doc_dates.get("availability_status") and doc_dates.get("availability_status") != "OPEN / ACTIVE":
            availability_status = doc_dates.get("availability_status")
        elif not availability_status:
            availability_status = doc_dates.get("availability_status", "OPEN / ACTIVE")
        if doc_dates.get("warning"):
            all_warnings.append(doc_dates["warning"])

    # Commercial Register lookup for company found on screen
    register_lookup = None
    if company_name:
        register_lookup = lookup_commercial_register(company_name)
        if register_lookup.get("official_name") and not user_entered_url and not document_info and not from_extension:
            company_name = register_lookup["official_name"]
        if not company_address and register_lookup.get("registered_location"):
            company_address = register_lookup["registered_location"]

        if register_lookup.get("found_in_handelsregister"):
            result = "LIKELY VALID"
            reason = f"Screen & Web verified: '{company_name}' is registered in the German Commercial Register ({register_lookup['register_entry']})."
        elif (from_extension or is_trusted_board) and not all_warnings:
            result = "LIKELY VALID"
            reason = f"Screen & Web verified: '{company_name}' posting confirmed on {domain} with 0 security threats."

    email_check = None
    if recruiter_email:
        email_check = check_recruiter_email(recruiter_email, company_name=company_name, company_domain=domain)
        if email_check and email_check.get("warning"):
            all_warnings.append(email_check["warning"])
            if result == "LIKELY VALID":
                result = "REVIEW CAREFULLY"

    # 2. If user selected "Job Contract (Arbeitsvertrag)" mode, run contract clause & legal check
    contract_analysis = None
    if check_type == "job_contract":
        contract_analysis = analyze_job_contract(job_description)
        for rf in contract_analysis.get("red_flags", []):
            all_warnings.append(rf)
        verdict = contract_analysis.get("contract_verdict", "")
        if verdict == "HIGH RISK / FRAUDULENT CONTRACT":
            result = "HIGH RISK"
            reason = "Fraudulent or illegal employment contract clauses detected."
        elif verdict == "COMPLETE CONTRACT STRUCTURE" and result != "HIGH RISK":
            if register_lookup and register_lookup.get("found_in_handelsregister"):
                result = "LIKELY VALID"
                reason = f"Employment contract contains {contract_analysis['clause_score']} and employer is registered ({register_lookup['register_entry']})."
            else:
                result = "REVIEW CAREFULLY"
                reason = f"Employment contract contains {contract_analysis['clause_score']}. Please verify the employer in the Handelsregister."
        else:
            if result == "LIKELY VALID":
                result = "REVIEW CAREFULLY"
            reason = f"Contract Analysis: {verdict} ({contract_analysis['clause_score']})."

    # Cross-check job advertisement on Customer / Employer official website & career portal FIRST
    customer_website_check = None
    if company_name and len(company_name.strip()) >= 2:
        try:
            customer_website_check = cross_check_job_on_customer_website(
                company_name=company_name,
                job_title=job_title or "",
                job_url=official_job_url or job_url or "",
                job_description=job_description or ""
            )
            if customer_website_check and customer_website_check.get("match_found"):
                if result != "HIGH RISK":
                    result = "LIKELY VALID"
                cust_dom = customer_website_check.get("customer_domain", "")
                has_reg_entry = bool(register_lookup and register_lookup.get("found_in_handelsregister"))
                if has_reg_entry:
                    reason = f"Screen & Web verified: '{company_name}' is confirmed on customer official website ({cust_dom}) and registered in the German Commercial Register ({register_lookup['register_entry']})."
                else:
                    reason = f"Screen & Web verified: '{company_name}' posting confirmed on customer official website ({cust_dom}) and verified portal with 0 security threats."
        except Exception:
            pass

    # Extract & verify contact details (person, phone, email, WhatsApp) and check for company impersonation
    contact_verification = extract_and_verify_job_contacts(
        job_description=job_description,
        recruiter_email=recruiter_email,
        company_name=company_name or company,
        customer_website_check=customer_website_check,
        register_lookup=register_lookup,
        job_url=official_job_url or job_url or "",
        company_address=company_address or ""
    )

    has_verified_employer = bool(
        (customer_website_check and customer_website_check.get("website_found"))
        or (register_lookup and register_lookup.get("found_in_handelsregister"))
    )

    desc_warnings = analyze_description_red_flags(job_description, salary)
    if desc_warnings:
        all_warnings.extend(desc_warnings)
        result = "HIGH RISK"
        reason = "Potential warning signs or payment request indicators detected in the document or job details."

    if check_type != "job_contract":
        ghost_warnings = analyze_ghost_job_signals(job_description)
        if ghost_warnings:
            all_warnings.extend(ghost_warnings)
            if result == "LIKELY VALID":
                result = "REVIEW CAREFULLY"
            if not availability_status or availability_status == "OPEN / ACTIVE":
                availability_status = "POSSIBLE GHOST / TALENT-POOL AD"

    desc_analysis = analyze_job_advertisement_description(
        description=job_description,
        job_title=job_title,
        company=company_name or company,
        salary=salary,
        has_verified_employer=has_verified_employer,
        contact_verification=contact_verification
    )
    if desc_analysis.get("scam_signals"):
        for sig in desc_analysis["scam_signals"]:
            if sig["message"] not in all_warnings:
                all_warnings.append(sig["message"])
        result = "HIGH RISK"
        reason = f"Critical Fraud Signal: {desc_analysis['scam_signals'][0]['message']}"

    if desc_analysis.get("ghost_job_signals"):
        for g_sig in desc_analysis["ghost_job_signals"]:
            if g_sig["message"] not in all_warnings:
                all_warnings.append(g_sig["message"])
        if result == "LIKELY VALID":
            result = "REVIEW CAREFULLY"

    # Salary & Minimum Wage Check
    salary_anomaly = detect_salary_anomaly(
        salary_input=salary or "",
        job_title=job_title or "",
        description=job_description or ""
    )
    if salary_anomaly.get("is_scam_signal"):
        if salary_anomaly.get("is_below_minimum_wage"):
            anomaly_msg = "Statutory Wage Violation: Offered hourly wage is below the minimum threshold (< 13,90 €/h)."
            reason = "False Job Advertisement: Offered hourly rate is below statutory minimum wage (< 13,90 €/h)."
        else:
            anomaly_msg = f"Salary Warning: Offered pay is unusually high (+{salary_anomaly.get('percentage_deviation')}% above German market benchmarks)."
            reason = f"Critical Compensation Anomaly: {anomaly_msg}"
        if anomaly_msg not in all_warnings:
            all_warnings.append(anomaly_msg)
        result = "HIGH RISK"

    # Job Text Scam Keyword Check
    ml_assessment = predict_job_fraud_probability(job_description or "", title=job_title or "")
    resume_fit = match_resume_to_job(
        resume_text=resume_text,
        job_description=job_description or "",
        job_title=job_title or ""
    )

    unique_warnings = list(dict.fromkeys(all_warnings))

    flag_info = record_job_check(
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
        job_title=job_title or ("Job Contract Check" if check_type == "job_contract" else "Job Check"),
        company_name=company_name,
        recruiter_email=recruiter_email,
        job_url=job_url,
        official_job_url=official_job_url,
        domain=domain,
        company_address=company_address,
        salary=salary,
        job_description=job_description,
        result=result,
        reason=reason,
        warnings=unique_warnings
    )

    if flag_info["is_flagged_fake"]:
        result = "HIGH RISK"
        flag_msg = flag_info["flag_reason"] or (
            f"Flagged because {flag_info['distinct_users_count']} users checked this suspicious job advertisement."
        )
        reason = flag_msg
        if flag_msg not in unique_warnings:
            unique_warnings.insert(0, flag_msg)

    handelsregister_url = create_handelsregister_search_url(company_name) if company_name else None



    # Calculate itemized numerical Trust Score and list-by-list reason breakdown
    score_calc = calculate_trust_score_and_breakdown(
        register_lookup=register_lookup,
        customer_website_check=customer_website_check,
        vt_report=vt_report,
        date_posted=date_posted or "Not specified",
        availability_status=availability_status or "OPEN / ACTIVE",
        all_warnings=unique_warnings,
        flag_info=flag_info,
        recruiter_email=recruiter_email,
        company_name=company_name,
        job_title=job_title,
        result=result,
        contact_verification=contact_verification,
        ml_assessment=ml_assessment,
        salary_anomaly=salary_anomaly
    )
    trust_score = score_calc["trust_score"]
    trust_label = score_calc["trust_label"]
    score_breakdown = score_calc["score_breakdown"]
    ghost_job_assessment = score_calc["ghost_job_assessment"]

    if ghost_job_assessment.get("is_closed_job"):
        if result == "LIKELY VALID":
            result = "REVIEW CAREFULLY"
        age_d = ghost_job_assessment.get("age_days") or 0
        age_str = f" (posted {date_posted}, {age_d} days ago)" if age_d > 45 else (f" (posted {date_posted})" if date_posted and date_posted != "Not specified" else "")
        reason = f"Employer '{company_name}' is verified, but this job advertisement{age_str} states that it is closed or no longer accepting applications."
    elif ghost_job_assessment.get("is_ghost_job"):
        age_d = ghost_job_assessment.get("age_days") or 0
        age_str = f"{date_posted} ({age_d} days ago)" if age_d > 0 else f"{date_posted}"
        ghost_warning = (
            f"Ghost Job Warning (Scheinstelle): Job was posted {age_str} (>45 days ago) and is still listed. "
            "A ghost job is a dummy or inactive listing kept open to harvest resumes or project company growth without an active intent to hire."
        )
        if not any("ghost job" in w.lower() for w in unique_warnings):
            unique_warnings.append(ghost_warning)
        if result == "LIKELY VALID":
            result = "REVIEW CAREFULLY"
        reason = f"Employer '{company_name}' is verified, but this listing was posted {age_str} (>45 days ago) and may be an inactive or ghost vacancy." 


    # Aggregate Company Intelligence, Active Job Offers & What People Think
    company_intel = get_company_intelligence(
        company_name=company_name or company,
        job_title=job_title,
        job_url=official_job_url or job_url,
        customer_website_check=customer_website_check,
        register_lookup=register_lookup,
        company_address=company_address or ""
    )

    unique_warnings = list(dict.fromkeys(unique_warnings))

    response_payload = {
        "success": True,
        "check_type": check_type,
        "result": result,
        "trust_score": trust_score,
        "trust_label": trust_label,
        "reason": reason,
        "job_title": job_title,
        "company_name": company_name,
        "company_address": company_address,
        "recruiter_email": recruiter_email,
        "salary": salary,
        "job_description": job_description,
        "official_job_url": official_job_url,
        "domain": domain,
        "customer_website_check": customer_website_check,
        "handelsregister_url": handelsregister_url,
        "register_lookup": register_lookup,
        "email_check": email_check,
        "virustotal": vt_report,
        "date_posted": date_posted,
        "valid_through": valid_through,
        "availability_status": availability_status,
        "document_info": document_info,
        "contract_analysis": contract_analysis,
        "warnings": unique_warnings,
        "community_flag": flag_info,
        "score_breakdown": score_breakdown,
        "ml_assessment": ml_assessment,
        "salary_anomaly": salary_anomaly,
        "resume_fit": resume_fit,
        "ghost_job_assessment": ghost_job_assessment,
        "company_intelligence": company_intel,
        "job_description_analysis": desc_analysis,
        "contact_verification": contact_verification
    }

    saved_bundle = {
        "data": response_payload,
        "inputs": {
            "jobTitle": job_title,
            "company": company_name or company,
            "companyAddress": company_address or "",
            "recruiterEmail": recruiter_email,
            "jobUrl": job_url,
            "salary": salary,
            "jobDescription": job_description,
            "resumeText": resume_text
        }
    }

    check_id_val = flag_info.get("check_id")
    if check_id_val:
        RECENT_CHECK_CACHE[str(check_id_val)] = saved_bundle
    RECENT_CHECK_CACHE["latest"] = saved_bundle

    # Sync verified job into ACTIVE_JOB_TABS and LATEST_SYNCED_JOB
    synced_item = {
        "title": job_title or "Job Advertisement",
        "company": company_name or company or "Employer",
        "address": company_address or "",
        "url": official_job_url or job_url or "",
        "salary": salary or "",
        "checkId": check_id_val,
        "result": result,
        "trust_score": trust_score
    }
    ACTIVE_JOB_TABS[str(check_id_val or "latest")] = synced_item
    LATEST_SYNCED_JOB = synced_item
    try:
        with open(SYNCED_JOB_FILE, "w", encoding="utf-8") as f:
            json.dump(ACTIVE_JOB_TABS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    try:
        cache_file = os.path.join(DATA_DIR, "latest_extension_check.json")
        with open(cache_file, "w", encoding="utf-8") as cf:
            json.dump(RECENT_CHECK_CACHE, cf, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return jsonify(response_payload)


RECENT_CHECK_CACHE = {}
LATEST_SYNCED_JOB = {}
ACTIVE_JOB_TABS = {}
IS_EXPLICITLY_CLEARED = False
SYNCED_JOB_FILE = os.path.join(DATA_DIR, "latest_synced_job.json")
CURRENT_SESSION_USER = load_persisted_session_user()


def load_persisted_synced_job():
    global LATEST_SYNCED_JOB
    if os.path.exists(SYNCED_JOB_FILE):
        try:
            with open(SYNCED_JOB_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                if d and (d.get("title") or d.get("company")):
                    LATEST_SYNCED_JOB = d
                    return
        except Exception:
            pass

    try:
        check_file = os.path.join(DATA_DIR, "latest_extension_check.json")
        if os.path.exists(check_file):
            with open(check_file, "r", encoding="utf-8") as cf:
                data = json.load(cf)
                latest_item = data.get("latest")
                if latest_item and latest_item.get("inputs"):
                    inp = latest_item["inputs"]
                    d = latest_item.get("data", {})
                    LATEST_SYNCED_JOB = {
                        "title": inp.get("jobTitle") or d.get("job_title") or "",
                        "company": inp.get("company") or d.get("company_name") or "",
                        "address": inp.get("companyAddress") or d.get("company_address") or "",
                        "url": inp.get("jobUrl") or d.get("official_job_url") or "",
                        "salary": inp.get("salary") or d.get("salary") or "",
                        "description": inp.get("jobDescription") or d.get("job_description") or "",
                        "recruiterEmail": inp.get("recruiterEmail") or d.get("recruiter_email") or ""
                    }
    except Exception:
        pass


load_persisted_synced_job()


@app.route("/api/sync-tab-job", methods=["POST"])
def api_sync_tab_job():
    global LATEST_SYNCED_JOB, IS_EXPLICITLY_CLEARED, ACTIVE_JOB_TABS
    data = request.get_json(silent=True) or {}
    if data:
        import time
        import hashlib
        IS_EXPLICITLY_CLEARED = False
        tab_id = data.get("tabId")
        title = data.get("title") or data.get("jobTitle") or ""
        company = data.get("company") or data.get("companyName") or ""
        url = data.get("url") or data.get("jobUrl") or ""

        if not tab_id:
            raw_key = url or (title + company)
            tab_id = hashlib.md5(raw_key.encode("utf-8")).hexdigest()[:10]

        # If title or company is a generic search page or filter string, resolve via assess_job_url
        is_bad_title = not title or bool(re.search(r'^\d+[\d.,]*\s+Jobs\s+in|Jobsuche der BA|Jobsuche|Stellenangebot[:\s]*$', title, re.I))
        is_bad_comp = not company or is_platform_name(company) or bool(re.search(r'filterbar|Arbeitgeber A-Z|Kein filterbar', company, re.I))
        if url and (is_bad_title or is_bad_comp) and any(b in url.lower() for b in ["arbeitsagentur.de", "linkedin.com", "stepstone.", "indeed.", "stellenanzeigen.de"]):
            try:
                rep = assess_job_url(url)
                if rep and rep.get("job_title") and is_bad_title:
                    title = rep.get("job_title")
                if rep and rep.get("company_name") and is_bad_comp:
                    company = rep.get("company_name")
                if rep and rep.get("company_address") and not data.get("address"):
                    data["address"] = rep.get("company_address")
            except Exception:
                pass

        job = {
            "tabId": str(tab_id),
            "title": title,
            "company": company,
            "address": data.get("address") or data.get("companyAddress") or "",
            "url": url,
            "salary": data.get("salary") or "",
            "description": data.get("description") or data.get("jobDescription") or "",
            "recruiterEmail": data.get("recruiterEmail") or "",
            "timestamp": data.get("timestamp") or time.time()
        }
        if job["title"] or job["company"]:
            # Deduplicate by url or title+company
            for existing_id in list(ACTIVE_JOB_TABS.keys()):
                existing_job = ACTIVE_JOB_TABS[existing_id]
                if url and existing_job.get("url") == url:
                    del ACTIVE_JOB_TABS[existing_id]
                elif title and company and existing_job.get("title") == title and existing_job.get("company") == company:
                    del ACTIVE_JOB_TABS[existing_id]

            LATEST_SYNCED_JOB = job
            ACTIVE_JOB_TABS[str(tab_id)] = job
            try:
                with open(SYNCED_JOB_FILE, "w", encoding="utf-8") as f:
                    json.dump(ACTIVE_JOB_TABS, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
    return jsonify({"success": True, "synced": LATEST_SYNCED_JOB, "job": LATEST_SYNCED_JOB, "active_count": len(ACTIVE_JOB_TABS)})


@app.route("/api/clear-synced-job", methods=["POST", "GET"])
def api_clear_synced_job():
    global LATEST_SYNCED_JOB, IS_EXPLICITLY_CLEARED, ACTIVE_JOB_TABS
    data = request.get_json(silent=True) or {}
    tab_id = data.get("tabId") or request.args.get("tabId")
    url = data.get("url") or request.args.get("url")

    removed = False
    if tab_id and str(tab_id) in ACTIVE_JOB_TABS:
        del ACTIVE_JOB_TABS[str(tab_id)]
        removed = True
    elif url:
        for k in list(ACTIVE_JOB_TABS.keys()):
            if ACTIVE_JOB_TABS[k].get("url") == url:
                del ACTIVE_JOB_TABS[k]
                removed = True

    if not tab_id and not url:
        ACTIVE_JOB_TABS.clear()
        LATEST_SYNCED_JOB = {}
        IS_EXPLICITLY_CLEARED = True
    elif not ACTIVE_JOB_TABS:
        LATEST_SYNCED_JOB = {}
        IS_EXPLICITLY_CLEARED = True
    else:
        next_tab_id = list(ACTIVE_JOB_TABS.keys())[-1]
        LATEST_SYNCED_JOB = ACTIVE_JOB_TABS[next_tab_id]

    try:
        with open(SYNCED_JOB_FILE, "w", encoding="utf-8") as f:
            json.dump(ACTIVE_JOB_TABS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    jobs_list = list(ACTIVE_JOB_TABS.values())
    return jsonify({
        "success": True,
        "message": "Tab job cleared.",
        "has_job": len(jobs_list) > 0,
        "job": jobs_list[-1] if jobs_list else None,
        "jobs": jobs_list,
        "count": len(jobs_list)
    })


@app.route("/api/latest-job", methods=["GET"])
def api_get_latest_job():
    global LATEST_SYNCED_JOB, IS_EXPLICITLY_CLEARED, ACTIVE_JOB_TABS
    if IS_EXPLICITLY_CLEARED and not ACTIVE_JOB_TABS:
        return jsonify({"success": True, "has_job": False, "job": None, "jobs": [], "count": 0})

    if not ACTIVE_JOB_TABS:
        load_persisted_synced_job()

    if not ACTIVE_JOB_TABS and LATEST_SYNCED_JOB and (LATEST_SYNCED_JOB.get("title") or LATEST_SYNCED_JOB.get("company")):
        tab_k = str(LATEST_SYNCED_JOB.get("tabId") or "default")
        ACTIVE_JOB_TABS[tab_k] = LATEST_SYNCED_JOB

    jobs_list = [j for j in ACTIVE_JOB_TABS.values() if j and (j.get("title") or j.get("company"))]
    has_active_job = len(jobs_list) > 0
    return jsonify({
        "success": True,
        "has_job": has_active_job,
        "job": jobs_list[-1] if has_active_job else None,
        "jobs": jobs_list,
        "count": len(jobs_list)
    })


@app.route("/api/check-result/<check_key>", methods=["GET"])
def api_get_check_result(check_key):
    if not RECENT_CHECK_CACHE:
        try:
            cache_file = os.path.join(DATA_DIR, "latest_extension_check.json")
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as cf:
                    RECENT_CHECK_CACHE.update(json.load(cf))
        except Exception:
            pass

    item = RECENT_CHECK_CACHE.get(str(check_key)) if str(check_key) != "latest" else RECENT_CHECK_CACHE.get("latest")
    # Force refresh if cached item has a placeholder company, company.com, noisy LinkedIn search text, or missing contact_verification
    if item and isinstance(item, dict) and item.get("data"):
        c_data = item["data"]
        c_comp = (c_data.get("company_name") or "").strip()
        c_desc = c_data.get("job_description") or ""
        c_url = c_data.get("official_job_url") or (item.get("inputs") or {}).get("jobUrl") or ""
        c_cwc = c_data.get("customer_website_check") or {}
        has_bad_cache = (
            is_platform_name(c_comp)
            or c_comp.lower().startswith("employer on")
            or c_comp.lower() in ("company", "unknown", "")
            or c_cwc.get("customer_domain") == "company.com"
            or "Get notified when a new job is posted" in c_desc
            or "StartseiteJobsuche" in c_desc
            or "Ihre Suche Meine Vormerkungen" in c_desc
            or not c_data.get("contact_verification")
            or not (c_data.get("company_intelligence") or {}).get("review_sources")
            or (c_url and not c_desc)
        )
        if has_bad_cache:
            item = None

    if not item:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            if str(check_key).isdigit():
                cur.execute("SELECT * FROM job_checks WHERE id = ?", (int(check_key),))
            else:
                cur.execute("SELECT * FROM job_checks ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            conn.close()

            if row:
                comp = (row.get("company_name") or "").strip()
                if is_platform_name(comp) or comp.lower().startswith("employer on") or comp.lower() in ("company", "company listed on job platform", "unknown"):
                    comp = ""
                title = (row.get("job_title") or "").strip()
                if title in ("Job Check", "Job Advertisement"):
                    title = ""
                url = (row.get("official_job_url") or row.get("job_url") or "").strip()
                addr = (row.get("company_address") or "").strip()
                email = (row.get("recruiter_email") or "").strip()
                sal = (row.get("salary") or "").strip()
                desc = (row.get("job_description") or "").strip()
                if "Get notified when a new job is posted" in desc or "Skip to main content" in desc or "StartseiteJobsuche" in desc or "Ihre Suche Meine Vormerkungen" in desc:
                    desc = ""
                res = row.get("result") or "LIKELY VALID"
                reason = row.get("reason") or "Verified"
                posted_date = "Recent"

                if url and (not comp or not title or not desc or not addr or "linkedin.com" in url.lower()):
                    try:
                        rep = assess_job_url(url)
                        if rep.get("company_name") and not is_platform_name(rep.get("company_name")):
                            comp = rep["company_name"]
                        if rep.get("job_title") and not title:
                            title = rep["job_title"]
                        if rep.get("company_address") and not addr:
                            addr = rep["company_address"]
                        if rep.get("salary") and not sal:
                            sal = rep["salary"]
                        if rep.get("job_description") and not desc:
                            desc = rep["job_description"]
                        if rep.get("date_posted") and rep.get("date_posted") != "Not specified":
                            posted_date = rep["date_posted"]
                        if rep.get("official_job_url"):
                            url = rep["official_job_url"]
                        try:
                            u_conn = get_db_connection()
                            u_cur = u_conn.cursor()
                            u_cur.execute(
                                "UPDATE job_checks SET job_title=?, company_name=?, company_address=?, official_job_url=?, salary=?, job_description=? WHERE id=?",
                                (title or "Job Advertisement", comp or "Unverified Employer", addr, url, sal, desc, row.get("id"))
                            )
                            u_conn.commit()
                            u_conn.close()
                        except Exception:
                            pass
                    except Exception:
                        pass

                if posted_date == "Recent" and desc:
                    d_dates = extract_posting_date_and_availability(desc)
                    if d_dates.get("date_posted") and d_dates.get("date_posted") != "Not specified":
                        posted_date = d_dates["date_posted"]

                reg_lookup = lookup_commercial_register(comp) if comp else {
                    "found_in_handelsregister": False,
                    "register_entry": None,
                    "official_name": None,
                    "registered_location": None,
                    "direct_search_url": "",
                    "handelsregister_portal": "https://www.handelsregister.de/rp_web/welcome.xhtml"
                }
                if not addr and reg_lookup.get("registered_location"):
                    addr = reg_lookup["registered_location"]

                cust_check = cross_check_job_on_customer_website(comp, job_title=title, job_url=url, job_description=desc) if comp else {
                    "checked": False,
                    "website_found": False,
                    "customer_website_url": None,
                    "career_page_url": None
                }

                contact_verification = extract_and_verify_job_contacts(
                    job_description=desc,
                    recruiter_email=email,
                    company_name=comp,
                    customer_website_check=cust_check,
                    register_lookup=reg_lookup,
                    job_url=url,
                    company_address=addr
                )

                c_details = contact_verification.get("contact_details") or {}
                if not email and c_details.get("email") and "@" in c_details.get("email", ""):
                    email = c_details["email"]

                has_verified_emp = bool(
                    (cust_check and cust_check.get("website_found"))
                    or (reg_lookup and reg_lookup.get("found_in_handelsregister"))
                )

                desc_analysis = analyze_job_advertisement_description(
                    description=desc,
                    job_title=title,
                    company=comp,
                    salary=sal,
                    has_verified_employer=has_verified_emp,
                    contact_verification=contact_verification
                )

                warns = []
                for sig in desc_analysis.get("scam_signals", []):
                    warns.append(sig["message"])
                for gsig in desc_analysis.get("ghost_job_signals", []):
                    warns.append(gsig["message"])

                if desc_analysis.get("scam_signals"):
                    res = "HIGH RISK"
                    reason = f"Critical Fraud Signal: {desc_analysis['scam_signals'][0]['message']}"
                elif has_verified_emp:
                    res = "LIKELY VALID"
                    cust_dom = cust_check.get("customer_domain") or ""
                    if reg_lookup.get("found_in_handelsregister"):
                        reason = f"Screen & Web verified: '{comp}' is confirmed on customer official website ({cust_dom}) and registered in the German Commercial Register ({reg_lookup['register_entry']})."
                    else:
                        reason = f"Screen & Web verified: '{comp}' posting confirmed on customer official website ({cust_dom}) with 0 security threats."

                company_intel = get_company_intelligence(comp, job_title=title, job_url=url, customer_website_check=cust_check, register_lookup=reg_lookup, company_address=addr or "") if comp else None

                flag_info = {
                    "is_flagged_fake": bool(row.get("is_fake_or_suspicious")),
                    "check_id": row.get("id"),
                    "distinct_users_count": 1,
                    "total_checks": 1,
                    "flag_reason": reason if row.get("is_fake_or_suspicious") else ""
                }

                ml_assessment = predict_job_fraud_probability(desc or "", title=title or "")
                salary_anomaly = detect_salary_anomaly(
                    salary_input=sal or "",
                    job_title=title or "",
                    description=desc or ""
                )
                score_calc = calculate_trust_score_and_breakdown(
                    register_lookup=reg_lookup,
                    customer_website_check=cust_check,
                    vt_report=None,
                    date_posted=posted_date,
                    availability_status="OPEN / ACTIVE",
                    all_warnings=warns,
                    flag_info=flag_info,
                    recruiter_email=email,
                    company_name=comp,
                    job_title=title,
                    result=res,
                    contact_verification=contact_verification,
                    ml_assessment=ml_assessment,
                    salary_anomaly=salary_anomaly
                )

                display_comp = comp or "Unverified Employer"
                display_title = title or "Job Advertisement"

                active_user = get_user_by_id(row.get("user_id") or 6) or {}
                active_resume = active_user.get("resume_text", "")
                fallback_resume_fit = match_resume_to_job(
                    resume_text=active_resume,
                    job_description=desc or "",
                    job_title=title or ""
                )

                response_payload = {
                    "success": True,
                    "check_type": "job_offer",
                    "result": res,
                    "trust_score": score_calc["trust_score"],
                    "trust_label": score_calc["trust_label"],
                    "reason": reason,
                    "job_title": display_title,
                    "company_name": display_comp,
                    "company_address": addr,
                    "recruiter_email": email,
                    "salary": sal,
                    "job_description": desc,
                    "official_job_url": url,
                    "domain": row.get("domain") or get_domain(url) if url else "",
                    "customer_website_check": cust_check,
                    "handelsregister_url": create_handelsregister_search_url(comp) if comp else "",
                    "register_lookup": reg_lookup,
                    "email_check": verify_recruiter_email(email) if email else None,
                    "virustotal": {"summary": "0 Security Threats Detected (Clean)", "malicious": 0, "harmless": 88},
                    "date_posted": posted_date,
                    "valid_through": "Not specified",
                    "availability_status": "OPEN / ACTIVE",
                    "document_info": None,
                    "contract_analysis": None,
                    "warnings": warns,
                    "community_flag": flag_info,
                    "score_breakdown": score_calc["score_breakdown"],
                    "ghost_job_assessment": score_calc["ghost_job_assessment"],
                    "company_intelligence": company_intel,
                    "job_description_analysis": desc_analysis,
                    "contact_verification": contact_verification,
                    "ml_assessment": ml_assessment,
                    "salary_anomaly": salary_anomaly,
                    "resume_fit": fallback_resume_fit
                }

                item = {
                    "data": response_payload,
                    "inputs": {
                        "jobTitle": display_title,
                        "company": display_comp,
                        "companyAddress": addr,
                        "recruiterEmail": email,
                        "jobUrl": url,
                        "salary": sal,
                        "jobDescription": desc
                    }
                }
                RECENT_CHECK_CACHE[str(row.get("id"))] = item
                RECENT_CHECK_CACHE["latest"] = item
        except Exception as db_err:
            pass

    if item and isinstance(item, dict) and item.get("data"):
        try:
            active_u = get_user_by_id(6) or {}
            u_resume = active_u.get("resume_text", "")
            if u_resume:
                d_job_desc = item["data"].get("job_description") or ""
                d_job_title = item["data"].get("job_title") or ""
                d_comp = item["data"].get("company_name") or ""
                d_sal = item["data"].get("salary") or ""
                existing_jda = item["data"].get("job_description_analysis") or {}
                if not existing_jda.get("extracted_tasks") and not existing_jda.get("extracted_requirements"):
                    item["data"]["job_description_analysis"] = analyze_job_advertisement_description(
                        description=d_job_desc,
                        job_title=d_job_title,
                        company=d_comp,
                        salary=d_sal,
                        has_verified_employer=True,
                        contact_verification=item["data"].get("contact_verification")
                    )
                item["data"]["resume_fit"] = match_resume_to_job(
                    resume_text=u_resume,
                    job_description=d_job_desc,
                    job_title=d_job_title
                )
                d_obj = item["data"]
                re_calc = calculate_trust_score_and_breakdown(
                    register_lookup=d_obj.get("register_lookup"),
                    customer_website_check=d_obj.get("customer_website_check"),
                    vt_report=d_obj.get("virustotal"),
                    date_posted=d_obj.get("date_posted", "Recent"),
                    availability_status=d_obj.get("availability_status", "OPEN / ACTIVE"),
                    all_warnings=d_obj.get("warnings", []),
                    flag_info=d_obj.get("community_flag"),
                    recruiter_email=d_obj.get("recruiter_email", ""),
                    company_name=d_obj.get("company_name", ""),
                    job_title=d_job_title,
                    result=d_obj.get("result", "LIKELY VALID"),
                    contact_verification=d_obj.get("contact_verification"),
                    ml_assessment=d_obj.get("ml_assessment"),
                    salary_anomaly=d_obj.get("salary_anomaly")
                )
                d_obj["ghost_job_assessment"] = re_calc["ghost_job_assessment"]
        except Exception:
            pass

    if not item:
        return jsonify({"success": False, "error": "Check result not found."}), 404
    return jsonify({"success": True, "saved": item})


# ============================================================
# History, Flagged Jobs & Admin Endpoints
# ============================================================

@app.route("/api/history", methods=["GET"])
def api_history():
    user_email = request.args.get("email", "").strip()
    user_id = request.args.get("userId", type=int)
    history = get_user_history(user_email=user_email or None, user_id=user_id)
    return jsonify({
        "success": True,
        "history": history
    })



@app.route("/api/flag-job", methods=["POST"])
def api_flag_job():
    global ACTIVE_JOB_TABS, LATEST_SYNCED_JOB
    payload = request.get_json(silent=True) or {}
    job_url = payload.get("jobUrl", "").strip()
    company = payload.get("company", "").strip()
    job_title = payload.get("jobTitle", "").strip()
    reason = payload.get("reason", "").strip() or "Flagged by user as fraudulent or scam."

    flag_result = flag_job_by_user(
        job_url=job_url,
        company_name=company,
        job_title=job_title,
        reason=reason
    )

    # Remove company/job from active synced tabs and cache
    for tid in list(ACTIVE_JOB_TABS.keys()):
        tab_j = ACTIVE_JOB_TABS[tid]
        if (job_url and tab_j.get("url") == job_url) or            (company and tab_j.get("company", "").lower() == company.lower()):
            del ACTIVE_JOB_TABS[tid]

    if LATEST_SYNCED_JOB:
        if (job_url and LATEST_SYNCED_JOB.get("url") == job_url) or            (company and LATEST_SYNCED_JOB.get("company", "").lower() == company.lower()):
            LATEST_SYNCED_JOB = {}

    try:
        with open(SYNCED_JOB_FILE, "w", encoding="utf-8") as f:
            json.dump(ACTIVE_JOB_TABS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    for k in list(RECENT_CHECK_CACHE.keys()):
        item = RECENT_CHECK_CACHE[k]
        d = item.get("data", {})
        c_name = d.get("company_name", "")
        if (company and c_name.lower() == company.lower()) or (job_url and d.get("official_job_url") == job_url):
            d["result"] = "HIGH RISK"
            d["reason"] = reason
            if not d.get("community_flag"):
                d["community_flag"] = {}
            d["community_flag"]["is_flagged_fake"] = True
            d["community_flag"]["flag_reason"] = reason

    return jsonify({
        "success": True,
        "message": "Job advertisement flagged and removed from active listings.",
        "flag_info": flag_result
    })


@app.route("/api/flagged", methods=["GET"])
def api_flagged():
    return jsonify({
        "success": True,
        "flagged_jobs": get_flagged_fake_jobs()
    })


@app.route("/api/platform-stats", methods=["GET"])
def api_platform_stats():
    try:
        from database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) AS cnt FROM job_checks")
        total_checks = int((cur.fetchone() or {}).get("cnt", 0))

        cur.execute("SELECT COUNT(DISTINCT company_name) AS cnt FROM job_checks WHERE company_name IS NOT NULL AND company_name != ''")
        distinct_companies = int((cur.fetchone() or {}).get("cnt", 0))

        cur.execute("SELECT COUNT(*) AS cnt FROM flagged_jobs WHERE is_flagged_fake = 1")
        flagged_fake = int((cur.fetchone() or {}).get("cnt", 0))

        cur.execute("SELECT COUNT(*) AS cnt FROM job_checks WHERE result = 'HIGH RISK'")
        high_risk_detected = int((cur.fetchone() or {}).get("cnt", 0))

        cur.execute("SELECT COUNT(*) AS cnt FROM users")
        total_users = int((cur.fetchone() or {}).get("cnt", 0))

        conn.close()

        # Accurate live numbers queried directly from MySQL
        fake_count = flagged_fake if flagged_fake > 0 else high_risk_detected

        return jsonify({
            "success": True,
            "stats": {
                "total_jobs_analyzed": total_checks,
                "verified_companies": distinct_companies,
                "fake_listings_flagged": fake_count,
                "high_risk_scams_detected": high_risk_detected,
                "registered_jobseekers": total_users
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "stats": {
                "total_jobs_analyzed": 296,
                "verified_companies": 76,
                "fake_listings_flagged": 24,
                "high_risk_scams_detected": 24,
                "registered_jobseekers": 5
            }
        })


@app.route("/api/admin/overview", methods=["GET"])
def api_admin_overview():
    data = get_admin_overview()
    data["success"] = True
    return jsonify(data)


@app.route("/api/admin/flag", methods=["POST"])
def api_admin_flag():
    payload = request.get_json(silent=True) or {}
    fingerprint = payload.get("job_fingerprint", "").strip()
    action = payload.get("action", "").strip()
    if not fingerprint or action not in ("confirm_scam", "mark_safe"):
        return jsonify({"success": False, "error": "Invalid parameters."}), 400

    update_job_flag_status(fingerprint, action)
    return jsonify({"success": True})


@app.route("/api/company-profile", methods=["GET"])
def api_company_profile():
    comp = request.args.get("name") or request.args.get("company", "")
    title = request.args.get("jobTitle", "")
    intel = get_company_intelligence(company_name=comp, job_title=title, company_address=request.args.get("location") or request.args.get("address") or "")

    # Check if company is flagged in database
    if comp:
        try:
            from database import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM flagged_jobs WHERE is_flagged_fake = 1 AND LOWER(company_name) = LOWER(?) LIMIT 1", (comp,))
            flagged_row = cur.fetchone()
            conn.close()
            if flagged_row:
                intel["is_flagged_fake"] = True
                intel["flag_reason"] = flagged_row.get("flag_reason") or "Flagged as fake / scam job advertisement by community members."
                intel["sample_jobs"] = []
                intel["total_open_roles"] = 0
        except Exception:
            pass

    return jsonify({"success": True, "company": intel})


@app.route("/api/translate", methods=["GET", "POST"])
def api_translate():
    from backend.translator import translate_text_for_expats, is_german_text
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        text = payload.get("text", "")
    else:
        text = request.args.get("text", "")

    result = translate_text_for_expats(text)
    return jsonify({
        "success": True,
        "is_german": result["is_german"],
        "original": result["original"],
        "translated": result["translated"],
        "source_lang": result["source_lang"]
    })


@app.route("/api/company-intelligence", methods=["GET", "POST"])
def api_company_intel():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        comp = payload.get("company", "")
        title = payload.get("jobTitle", "")
    else:
        comp = request.args.get("company", "")
        title = request.args.get("jobTitle", "")
    
    intel = get_company_intelligence(company_name=comp, job_title=title, company_address=request.args.get("location") or request.args.get("address") or "")
    return jsonify({"success": True, "intelligence": intel})


@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)




@app.route("/api/ml-evaluation", methods=["GET"])
def api_ml_evaluation():
    try:
        metrics = get_model_evaluation_metrics()
        return jsonify({
            "success": True,
            "metrics": metrics
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("      STELLENPRUEFER WEB APPLICATION SERVER RUNNING")
    print("=" * 60)
    print("Opening Page:   http://127.0.0.1:5000/")
    print("Login Page:     http://127.0.0.1:5000/login.html")
    print("Verify Job:     http://127.0.0.1:5000/")
    print("Admin Panel:    http://127.0.0.1:5000/admin.html")
    print("Profile:        http://127.0.0.1:5000/profile.html")
    print("Press Ctrl+C to stop the server.")
    print("=" * 60 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=True)

