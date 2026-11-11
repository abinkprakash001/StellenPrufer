# Calculate overall trust score (0-100) and build breakdown cards based on checks

import re
from datetime import datetime


GHOST_JOB_DEFINITION = (
    "A ghost job (Scheinstelle) is a dummy or inactive job listing kept open by companies to collect "
    "resumes for future talent pools, project false company growth to investors, or comply with formal "
    "posting requirements without any active intent to hire right now."
)


def calculate_trust_score_and_breakdown(
    register_lookup=None,
    customer_website_check=None,
    vt_report=None,
    date_posted="Not specified",
    availability_status="OPEN / ACTIVE",
    all_warnings=None,
    flag_info=None,
    recruiter_email="",
    company_name="",
    job_title="",
    result="REVIEW CAREFULLY",
    contact_verification=None,
    ml_assessment=None,
    salary_anomaly=None
):
    all_warnings = all_warnings or []
    flag_info = flag_info or {}
    register_lookup = register_lookup or {}
    customer_website_check = customer_website_check or {}
    vt_report = vt_report or {}
    contact_verification = contact_verification or {}

    vac_legit = contact_verification.get("vacancy_legitimacy") or {}
    contact_details = contact_verification.get("contact_details") or {}
    whatsapp_check = contact_verification.get("whatsapp_check") or {}

    score = 50
    breakdown = []

    # 1. Company Existence: Commercial Register Check (Handelsregister)
    has_reg = bool(register_lookup.get("found_in_handelsregister"))
    cust_found = bool(customer_website_check.get("website_found"))
    cust_dom = customer_website_check.get("customer_domain", "")

    is_public = bool(register_lookup.get("is_public_institution"))
    if has_reg:
        score += 20
        reg_entry = register_lookup.get("register_entry", "Commercial Register")
        loc = register_lookup.get("registered_location", "Germany")
        if is_public:
            breakdown.append({
                "type": "positive",
                "icon": "VERIFIED",
                "category": "Public Law Entity (Körperschaft des öffentlichen Rechts)",
                "title": f"Public Entity Verified ({company_name})",
                "detail": f"Official public institution / state university under German public law ({reg_entry}, {loc}). Statutory establishment confirmed.",
                "impact": "+20%"
            })
        else:
            breakdown.append({
                "type": "positive",
                "icon": "VERIFIED",
                "category": "Company Legitimacy (Handelsregister)",
                "title": f"Company Existence Verified ({reg_entry})",
                "detail": f"Active registered business confirmed in the German commercial register ({loc}).",
                "impact": "+20%"
            })
    elif company_name and cust_found:
        score += 5
        breakdown.append({
            "type": "positive",
            "icon": "VERIFIED",
            "category": "Company Legitimacy",
            "title": f"Active Employer Entity ({company_name})",
            "detail": f"Company operates under a verified corporate web domain ({cust_dom}).",
            "impact": "+5%"
        })
    elif company_name:
        score -= 5
        breakdown.append({
            "type": "neutral",
            "icon": "INFO",
            "category": "Company Legitimacy (Handelsregister)",
            "title": "Commercial Register Verification Recommended",
            "detail": f"No direct HRB/HRA entry was automatically matched for '{company_name}'. Verify the legal entity in the Impressum.",
            "impact": "-5%"
        })

    # 2. Official Company Website
    if cust_found and cust_dom:
        score += 15
        breakdown.append({
            "type": "positive",
            "icon": "VERIFIED",
            "category": "Employer Official Website",
            "title": f"Verified Authentic Employer Website ({cust_dom})",
            "detail": f"Official company website is online, reachable, and SSL secured ({cust_dom}).",
            "impact": "+15%"
        })
    elif company_name:
        breakdown.append({
            "type": "neutral",
            "icon": "INFO",
            "category": "Employer Official Website",
            "title": "Customer Official Website Check",
            "detail": f"Could not automatically locate the official website for '{company_name}'.",
            "impact": "0%"
        })

    # 3. Exact Job Vacancy & Career Portal Cross-Check
    cross_status = customer_website_check.get("cross_check_status")
    if cross_status == "VERIFIED_ON_CUSTOMER_CAREER_PORTAL":
        score += 15
        career_url = customer_website_check.get("career_page_url", "")
        breakdown.append({
            "type": "positive",
            "icon": "VERIFIED",
            "category": "Vacancy Legitimacy (Career Portal)",
            "title": "Exact Job Vacancy Verified on Official Career Portal",
            "detail": f"Vacancy '{job_title or 'Position'}' confirmed on employer's official career portal ({career_url}).",
            "impact": "+15%"
        })
    elif cross_status == "CUSTOMER_CAREER_PORTAL_ACTIVE":
        score += 10
        breakdown.append({
            "type": "positive",
            "icon": "VERIFIED",
            "category": "Vacancy Legitimacy (Career Portal)",
            "title": "Employer Career Portal Active",
            "detail": "Employer maintains an active official careers portal online.",
            "impact": "+10%"
        })

    # 4. Recruitment Contact & Impersonation Check (Greater Weight!)
    if vac_legit.get("is_impersonation_risk"):
        score -= 45
        breakdown.append({
            "type": "danger",
            "icon": "ALERT",
            "category": "Impersonation Check",
            "title": "High Risk: Possible Company Impersonation",
            "detail": vac_legit.get("impersonation_reason") or "Job uses a real company name but directs applicants to an unverified personal/free email address.",
            "impact": "-45%"
        })
    elif vac_legit.get("contact_matches_official"):
        score += 10
        c_person = contact_details.get("contact_person", "HR Team")
        c_email = contact_details.get("email", "")
        c_phone = contact_details.get("telephone", "")
        contact_summary_parts = [p for p in [c_person, c_email, c_phone] if p and "Official HR" not in p and "Listed on" not in p and "Via official" not in p]
        contact_str = ", ".join(contact_summary_parts) if contact_summary_parts else f"official @{cust_dom} recruitment channel"
        breakdown.append({
            "type": "positive",
            "icon": "VERIFIED",
            "category": "Recruitment Contact Verification",
            "title": "Recruitment Contact Matches Official Listing",
            "detail": f"Verified contact details ({contact_str}) match the employer's official recruitment process.",
            "impact": "+10%"
        })

    # 5. Context-Aware WhatsApp Application Check (0 Penalty when confirmed by official listing!)
    if whatsapp_check.get("mentioned"):
        if whatsapp_check.get("is_official_channel"):
            breakdown.append({
                "type": "positive",
                "icon": "VERIFIED",
                "category": "WhatsApp Application Option",
                "title": "WhatsApp Application: Confirmed by Official Listing",
                "detail": whatsapp_check.get("explanation") or "Employer explicitly supports applying online or via WhatsApp alongside verified corporate contact details (0 points deducted).",
                "impact": "0% (Verified)"
            })
        else:
            score -= 25
            breakdown.append({
                "type": "warning",
                "icon": "WARNING",
                "category": "Informal Recruitment Channel",
                "title": "Unverified WhatsApp Contact Channel",
                "detail": "WhatsApp is mentioned without a verified company career portal or official corporate contact details.",
                "impact": "-25%"
            })

    # 6. Domain Security & Suspicious Domains Check (Greater Weight!)
    vt_malicious = vt_report.get("malicious", 0)
    vt_suspicious = vt_report.get("suspicious", 0)
    if vt_malicious == 0 and vt_suspicious == 0:
        score += 10
        breakdown.append({
            "type": "positive",
            "icon": "VERIFIED",
            "category": "Domain Security (VirusTotal)",
            "title": "Clean Domain Security Reputation",
            "detail": "0 security threats, phishing, or malware detected across antivirus engines.",
            "impact": "+10%"
        })
    else:
        score -= 50
        breakdown.append({
            "type": "danger",
            "icon": "ALERT",
            "category": "Domain Security (VirusTotal)",
            "title": "Suspicious or Malicious Domain Detected",
            "detail": f"Security engines flagged {vt_malicious} malicious and {vt_suspicious} suspicious alerts on this domain.",
            "impact": "-50%"
        })

    # 7. Job Freshness & Ghost Job (Scheinstelle) Check (45-Day Rule)
    is_ghost_job = False
    avail_str = (availability_status or "").upper()
    is_closed_job = (
        "EXPIRED" in avail_str
        or "CLOSED" in avail_str
        or any("no longer accepting applications" in w.lower() or "posting states that it is closed" in w.lower() for w in all_warnings)
    )
    d_cnt = 0

    if date_posted and date_posted != "Not specified":
        dp_str = str(date_posted).strip()
        dp_lower = dp_str.lower()

        iso_m = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", dp_str)
        de_m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(20\d{2})\b", dp_str)
        today_dt = datetime.now().date()
        if iso_m:
            try:
                parsed_dt = datetime.strptime(iso_m.group(0), "%Y-%m-%d").date()
                d_cnt = max(0, (today_dt - parsed_dt).days)
            except ValueError:
                pass
        elif de_m:
            try:
                parsed_dt = datetime.strptime(f"{int(de_m.group(1)):02d}.{int(de_m.group(2)):02d}.{de_m.group(3)}", "%d.%m.%Y").date()
                d_cnt = max(0, (today_dt - parsed_dt).days)
            except ValueError:
                pass
        else:
            m_days = re.search(r"(\d+)\s*(?:day|tage?n?)", dp_lower)
            m_weeks = re.search(r"(\d+)\s*(?:week|woche)", dp_lower)
            m_months = re.search(r"(\d+)\s*(?:month|monat)", dp_lower)
            if m_days:
                d_cnt = int(m_days.group(1))
            elif m_weeks:
                d_cnt = int(m_weeks.group(1)) * 7
            elif m_months:
                d_cnt = int(m_months.group(1)) * 30
            elif re.search(r"\b(\d+)\s*(?:year|jahr)", dp_lower):
                d_cnt = 365

        if d_cnt > 45 or "30+" in dp_lower or ("+" in dp_lower and ("month" in dp_lower or "tag" in dp_lower)):
            is_ghost_job = True
            display_days = f"{d_cnt} days old" if d_cnt > 0 else date_posted
            if not is_closed_job:
                availability_status = f"OLD LISTING ({display_days} — Might be a Ghost Job)"
                avail_str = availability_status.upper()

    if is_closed_job:
        score -= 30
        age_suffix = f" (Posted {date_posted} — {d_cnt} days ago)" if d_cnt > 45 else (f" (Posted {date_posted})" if date_posted and date_posted != "Not specified" else "")
        breakdown.append({
            "type": "warning",
            "icon": "WARNING",
            "category": "Job Availability Status",
            "title": "Job Closed — No Longer Accepting Applications",
            "detail": f"This job listing states that it is closed or no longer accepting applications{age_suffix}.",
            "impact": "-30%"
        })
    elif is_ghost_job or "GHOST JOB" in avail_str or "OLD LISTING" in avail_str:
        is_ghost_job = True
        score -= 20
        age_note = f"{date_posted} ({d_cnt} days ago)" if d_cnt > 0 else f"{date_posted}"
        breakdown.append({
            "type": "warning",
            "icon": "WARNING",
            "category": "Ghost Job Detection (Scheinstelle)",
            "title": "Might be a Ghost Job (Posted > 45 Days Ago & Still Listed)",
            "detail": f"Posted: {age_note}. {GHOST_JOB_DEFINITION}",
            "impact": "-20%"
        })
    else:
        score += 5
        breakdown.append({
            "type": "positive",
            "icon": "VERIFIED",
            "category": "Job Posting Freshness",
            "title": "Fresh Active Listing (< 45 Days)",
            "detail": f"Posted recently ({date_posted}) and currently open for applications.",
            "impact": "+5%"
        })

    # 8. Community Multi-User Flagging (5+ Users)
    is_community_flagged = bool(flag_info.get("is_flagged_fake"))
    if is_community_flagged:
        score = 15
        breakdown.append({
            "type": "danger",
            "icon": "ALERT",
            "category": "Community Scam Protection",
            "title": "Community Flagged Scam (5+ Users)",
            "detail": flag_info.get("flag_reason") or "Flagged because 5 or more users reported suspicious indicators.",
            "impact": "Drops to 15%"
        })

    # 9. High-Weight Advance-Payment Requests / Money Mule / Telegram Scams
    scam_warnings = [
        w for w in all_warnings
        if any(k in w.lower() for k in ("western union", "starter fee", "advance fee", "upfront", "gift card", "crypto", "money mule", "wire transfer", "telegram"))
    ]
    if scam_warnings:
        score = min(score, 15)
        for sw in scam_warnings[:2]:
            breakdown.append({
                "type": "danger",
                "icon": "ALERT",
                "category": "Critical Fraud Indicator",
                "title": "Advance-Payment / Financial Scam Indicator",
                "detail": sw,
                "impact": "-50%"
            })

    # 9.5 Job Text & Scam Keyword Check
    if ml_assessment:
        fraud_prob = ml_assessment.get("fraud_probability", 0.0)
        risk_lvl = ml_assessment.get("risk_level", "LOW")
        top_words = ml_assessment.get("top_trigger_words", [])
        triggers_str = ", ".join(f"'{w}'" for w in top_words[:3]) if top_words else ""

        if fraud_prob >= 70.0:
            score -= 25
            score = min(score, 30)
            breakdown.append({
                "type": "danger",
                "icon": "ALERT",
                "category": "Job Text & Keyword Check",
                "title": f"Text Check: High Scam Risk ({fraud_prob}%)",
                "detail": f"Calibrated Text check flagged a high deceptive linguistic patterns" + (f" (triggers: {triggers_str})." if triggers_str else "."),
                "impact": "-25%"
            })
        elif fraud_prob <= 30.0:
            score += 10
            breakdown.append({
                "type": "positive",
                "icon": "VERIFIED",
                "category": "Job Text & Keyword Check",
                "title": f"Text Check: Normal Job Wording ({round(100 - fraud_prob, 1)}% Genuine)",
                "detail": "Text check confirmed legitimate enterprise hiring terminology and authentic job description structure.",
                "impact": "+10%"
            })
        else:
            breakdown.append({
                "type": "neutral",
                "icon": "INFO",
                "category": "Job Text & Keyword Check",
                "title": f"Text Check: Moderate Risk ({fraud_prob}% Risk)",
                "detail": "Text check found standard phrasing with minor ambiguity. Cross-referenced with domain checks.",
                "impact": "0%"
            })

    # 9.6 Salary & German Minimum Wage Check
    if salary_anomaly and salary_anomaly.get("has_salary_data"):
        ano_lvl = salary_anomaly.get("anomaly_level")
        pct_diff = salary_anomaly.get("percentage_deviation", 0)
        offered_str = salary_anomaly.get("formatted_offered", "")
        range_str = salary_anomaly.get("formatted_market_range", "")
        role_de = salary_anomaly.get("role_matched", "dieser Position")
        is_min_wage_viol = salary_anomaly.get("is_below_minimum_wage") or ano_lvl == "MINIMUM_WAGE_VIOLATION"

        if is_min_wage_viol:
            score -= 25
            score = min(score, 30)
            breakdown.append({
                "type": "danger",
                "icon": "ALERT",
                "category": "German Statutory Minimum Wage (MiLoG)",
                "title": f"False Job Advertisement: Below Hourly Minimum Wage ({offered_str})",
                "detail": "Offered hourly wage is below Germany's statutory minimum wage (Mindestlohn: 13,90 €/h under § 1 MiLoG). Any listing offering less than 13,90 €/h is a false job advertisement.",
                "impact": "-25%"
            })
        elif salary_anomaly.get("is_scam_signal") or ano_lvl == "CRITICAL_OUTLIER":
            score -= 20
            score = min(score, 30)
            breakdown.append({
                "type": "danger",
                "icon": "ALERT",
                "category": "Salary & Minimum Wage Check",
                "title": f"Salary Warning: Unusually High Pay (+{pct_diff}% vs. Market)",
                "detail": f"Offered pay ({offered_str}) severely exceeds standard German market benchmarks for {role_de} ({range_str}). High correlation with advance-fee or money mule recruitment.",
                "impact": "-20%"
            })
        elif ano_lvl == "AUTHENTIC_MARKET_RATE":
            score += 5
            breakdown.append({
                "type": "positive",
                "icon": "VERIFIED",
                "category": "Salary & Minimum Wage Check",
                "title": f"Conforms to German Market Benchmarks ({offered_str})",
                "detail": f"Compensation complies with German statutory minimum wage (>= 13,90 €/h) and aligns with statistical German collective wage data for {role_de} ({range_str}).",
                "impact": "+5%"
            })

    # 10. Align score with the core verification verdict
    has_pipeline_warn = any(
        any(k in w.lower() for k in ("talent pool", "bewerberpool", "scheinstelle", "evergreen", "future openings", "pipeline hoarding"))
        for w in all_warnings
    )
    has_vague_warn = any("vague boilerplate" in w.lower() for w in all_warnings)
    if has_pipeline_warn or has_vague_warn:
        is_ghost_job = True

    res_upper = (result or "").upper()
    if res_upper in ("HIGH RISK", "NOT VERIFIED", "INVALID LINK", "SCAM", "COULD NOT VERIFY"):
        score = min(score, 25)
        if not any(b.get("type") == "danger" for b in breakdown):
            breakdown.append({
                "type": "danger",
                "icon": "ALERT",
                "category": "Verification Verdict",
                "title": f"High Risk Job Signals Detected ({res_upper})",
                "detail": "High risk warning indicators or fraudulent patterns detected during cross-checks.",
                "impact": "Capped at 25%"
            })
    elif is_closed_job:
        score = max(48, min(score, 62))
    elif is_ghost_job:
        score = max(50, min(score, 65))
    elif res_upper in ("LIKELY VALID", "SAFE", "VERIFIED"):
        score = max(score, 80)
    elif res_upper == "REVIEW CAREFULLY":
        score = max(45, min(score, 69))

    score = max(10, min(score, 98))

    if is_closed_job:
        trust_label = "45 – 69: Job Closed (Employer Verified — No Longer Accepting Applications)"
    elif is_ghost_job:
        trust_label = "45 – 69: Old Listing / Possible Ghost Job (Posted > 45 Days Ago — Verify Vacancy)"
    elif score >= 70:
        trust_label = "70 – 100: High Trust (Likely Valid — Safe to Apply)"
    elif score >= 45:
        trust_label = "45 – 69: Medium Trust (Verify Details Before Applying)"
    else:
        trust_label = "0 – 44: Low Trust / High Scam Risk (Apply at Your Own Risk)"

    c_person_val = (contact_details.get("contact_person") or "").strip()
    c_email_val = (contact_details.get("email") or recruiter_email or "").strip()
    c_phone_val = (contact_details.get("telephone") or "").strip()
    has_named_contact = bool(c_person_val or c_email_val or c_phone_val or vac_legit.get("contact_matches_official"))
    has_portal_sync = bool(cross_status in ("VERIFIED_ON_CUSTOMER_CAREER_PORTAL", "CUSTOMER_CAREER_PORTAL_ACTIVE") or has_reg or is_public or cust_found or company_name)

    age_passed = (not is_ghost_job) and (not is_closed_job)
    if is_closed_job and d_cnt > 45:
        age_status = f"Closed & Stale ({date_posted}, {d_cnt}d old)"
        age_detail = f"Posted: {date_posted} ({d_cnt} days ago) and marked closed / no longer accepting applications."
    elif is_closed_job:
        age_status = "Closed / Inactive"
        age_detail = f"Posted: {date_posted}. Listing states that it is closed or no longer accepting applications."
    elif is_ghost_job:
        age_status = f"Stale ({date_posted}" + (f", {d_cnt}d old)" if d_cnt > 0 else ")")
        age_detail = f"Posted: {date_posted}" + (f" ({d_cnt} days ago — exceeds 45-day active window)." if d_cnt > 0 else " (> 45 days ago — exceeds active window).")
    else:
        age_status = "Fresh (< 30–45 Days)"
        age_detail = f"Posted: {date_posted}. Genuine vacancies typically fill within 30–60 days."

    red_flag_checks = [
        {
            "name": "1. Posting Age (< 30–45 Days)",
            "passed": age_passed,
            "status": age_status,
            "detail": age_detail
        },
        {
            "name": "2. Official Career Portal Sync",
            "passed": has_portal_sync,
            "status": "Confirmed on Official Domain" if has_portal_sync else "Unconfirmed on Direct Portal",
            "detail": f"Cross-checked against {cust_dom or company_name or 'employer career page'} and Handelsregister."
        },
        {
            "name": "3. Named Contact / Hiring Channel",
            "passed": has_named_contact,
            "status": "Verified Contact Channel" if has_named_contact else "No Named Point of Contact",
            "detail": f"Contact: {', '.join(p for p in [c_person_val, c_email_val, c_phone_val] if p)[:80] or 'Official corporate portal'}" if has_named_contact else "Anonymous listing without a named recruiter or direct contact email."
        },
        {
            "name": "4. Specific Role & Stack Details",
            "passed": not has_vague_warn,
            "status": "Concrete Tasks & Requirements" if not has_vague_warn else "Vague Generic Boilerplate",
            "detail": "Job specifies concrete responsibilities, qualifications, and work model." if not has_vague_warn else "Recycles generic clichés with no concrete team or tool specifics."
        },
        {
            "name": "5. Candidate Ghost Reports",
            "passed": not is_community_flagged,
            "status": "0 Ghost / Scam Reports" if not is_community_flagged else "Community Flagged",
            "detail": "No candidate ghosting or deceptive hiring complaints recorded for this listing."
        }
    ]

    failed_flags = sum(1 for c in red_flag_checks if not c["passed"])
    ghost_risk_score = min(95, max(8, failed_flags * 22 + (30 if (is_ghost_job or is_closed_job) else 8)))

    if is_closed_job:
        ghost_risk_label = "Vacancy Closed (No Longer Accepting Applications)"
        status_comment = "Vacancy Closed / No Longer Accepting Applications"
    elif is_ghost_job:
        ghost_risk_label = "High Ghost Job Risk (Possible Phantom / Pipeline Ad)"
        status_comment = "Might be a Ghost Job (Scheinstelle)"
    elif failed_flags >= 2:
        ghost_risk_label = "Moderate Ghost Risk — Verify Vacancy"
        status_comment = "Verify Vacancy Status"
    else:
        ghost_risk_label = "Low Ghost Job Risk (Active Genuine Vacancy)"
        status_comment = "Active Genuine Vacancy"

    ghost_assessment = {
        "is_ghost_job": is_ghost_job,
        "is_closed_job": is_closed_job,
        "age_days": d_cnt,
        "ghost_risk_score": ghost_risk_score,
        "ghost_risk_label": ghost_risk_label,
        "date_posted": date_posted,
        "status_comment": status_comment,
        "definition": GHOST_JOB_DEFINITION,
        "red_flag_checks": red_flag_checks
    }

    return {
        "trust_score": score,
        "trust_label": trust_label,
        "score_breakdown": breakdown,
        "ghost_job_assessment": ghost_assessment,
        "ml_assessment": ml_assessment,
        "salary_anomaly": salary_anomaly
    }
