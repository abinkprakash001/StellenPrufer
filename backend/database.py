"""SQLite 3 Database Layer for StellenPrüfer.
Self-contained, fast, and 100% standard SQL without requiring external database servers or clutter files.
The complete database lives in `data/stellenpruefer.db`.
"""

import os
import re
import json
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "stellenpruefer.db")

SUSPICIOUS_RESULTS = {
    "HIGH RISK",
    "NOT VERIFIED",
    "REVIEW CAREFULLY",
    "COULD NOT VERIFY",
    "INVALID LINK"
}


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_db_connection():
    """Return a thread-safe sqlite3 connection returning dict rows."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15.0)
    conn.row_factory = dict_factory
    return conn


def compute_job_fingerprint(job_url="", company="", job_title="", recruiter_email=""):
    """Generate a clean, normalized fingerprint string for duplicate detection."""
    from urllib.parse import urlparse
    import hashlib

    parts = []
    if job_url:
        try:
            parsed = urlparse(job_url)
            clean_host = (parsed.netloc or "").lower().replace("www.", "")
            clean_path = (parsed.path or "").rstrip("/")
            parts.append(f"url:{clean_host}{clean_path}")
        except Exception:
            parts.append(f"url:{job_url[:120].lower()}")
    if company:
        c_norm = re.sub(r"[^a-z0-9]", "", company.lower())
        if c_norm:
            parts.append(f"co:{c_norm}")
    if job_title:
        t_norm = re.sub(r"[^a-z0-9]", "", job_title.lower())
        if t_norm:
            parts.append(f"title:{t_norm}")
    if recruiter_email:
        em_norm = recruiter_email.strip().lower()
        if em_norm:
            parts.append(f"em:{em_norm}")

    raw = "|".join(parts) if parts else (job_url or "unknown_job")
    fp_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    prefix = (company or job_title or "job")[:30].strip()
    prefix_clean = re.sub(r"[^a-zA-Z0-9_-]", "_", prefix)
    return f"{prefix_clean}_{fp_hash}"


def init_db():
    """Initialize SQLite tables and seed default Admin account if not existing."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer',
            gdpr_consent INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            resume_text TEXT DEFAULT '',
            resume_filename TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS job_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NULL,
            user_name TEXT,
            user_email TEXT,
            job_fingerprint TEXT NOT NULL,
            job_title TEXT,
            company_name TEXT,
            recruiter_email TEXT,
            job_url TEXT,
            official_job_url TEXT,
            domain TEXT,
            company_address TEXT,
            salary TEXT,
            job_description TEXT,
            result TEXT NOT NULL,
            reason TEXT,
            warnings_json TEXT,
            is_fake_or_suspicious INTEGER DEFAULT 0,
            checked_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS flagged_jobs (
            job_fingerprint TEXT PRIMARY KEY,
            job_url TEXT,
            company_name TEXT,
            job_title TEXT,
            recruiter_email TEXT,
            latest_result TEXT,
            total_checks INTEGER DEFAULT 1,
            distinct_users_count INTEGER DEFAULT 1,
            checked_by_users_json TEXT,
            is_flagged_fake INTEGER DEFAULT 0,
            admin_status TEXT DEFAULT 'auto',
            flag_reason TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_jc_fingerprint ON job_checks (job_fingerprint)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_jc_user_id ON job_checks (user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_jc_user_email ON job_checks (user_email)")

    conn.commit()

    # Seed default Admin user if not exists
    cur.execute("SELECT id FROM users WHERE email = ?", ("admin@jobguard.com",))
    if not cur.fetchone():
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            "INSERT INTO users (name, email, password_hash, role, gdpr_consent, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("Admin", "admin@jobguard.com", generate_password_hash("admin123"), "admin", 1, now_str)
        )
        conn.commit()

    # Seed somanjiji customer user if not exists
    cur.execute("SELECT id FROM users WHERE email = ?", ("som123@gmail.com",))
    if not cur.fetchone():
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            "INSERT INTO users (name, email, password_hash, role, gdpr_consent, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("somanjiji", "som123@gmail.com", generate_password_hash("som123"), "customer", 1, now_str)
        )
        conn.commit()

    conn.close()


def register_user(name, email, password, gdpr_consent=True):
    email = (email or "").strip().lower()
    name = (name or "").strip()
    if not name or not email or not password:
        return None, "Name, email, and password are required."

    if not gdpr_consent:
        return None, "You must consent to data processing (GDPR / DSGVO) to create an account."

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cur.fetchone():
        conn.close()
        return None, "An account with this email already exists."

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pw_hash = generate_password_hash(password)
    cur.execute(
        "INSERT INTO users (name, email, password_hash, role, gdpr_consent, created_at) VALUES (?, ?, ?, 'customer', 1, ?)",
        (name, email, pw_hash, now_str)
    )
    user_id = cur.lastrowid

    conn.commit()
    conn.close()

    return {
        "id": user_id,
        "name": name,
        "email": email,
        "role": "customer",
        "gdpr_consent": True,
        "created_at": now_str
    }, None


def authenticate_user(email, password):
    email = (email or "").strip().lower()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()

    if not row or not check_password_hash(row["password_hash"], password or ""):
        return None, "Invalid email or password."

    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "gdpr_consent": bool(row["gdpr_consent"]),
        "created_at": row["created_at"],
        "resume_text": row.get("resume_text") or "",
        "resume_filename": row.get("resume_filename") or "",
        "resume_filename": row.get("resume_filename") or ""
    }, None


def update_user_profile(user_id, name, email, new_password=None, resume_text=None, resume_filename=None):
    name = (name or "").strip()
    email = (email or "").strip().lower()
    if not user_id or not name or not email:
        return None, "Name and email are required."

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    current = cur.fetchone()
    if not current:
        conn.close()
        return None, "User not found."

    cur.execute("SELECT id FROM users WHERE email = ? AND id != ?", (email, user_id))
    if cur.fetchone():
        conn.close()
        return None, "That email address is already in use by another account."

    if new_password and new_password.strip():
        pw_hash = generate_password_hash(new_password.strip())
        if resume_text is not None and resume_filename is not None:
            cur.execute(
                "UPDATE users SET name = ?, email = ?, password_hash = ?, resume_text = ?, resume_filename = ? WHERE id = ?",
                (name, email, pw_hash, resume_text.strip(), resume_filename.strip(), user_id)
            )
        elif resume_text is not None:
            cur.execute(
                "UPDATE users SET name = ?, email = ?, password_hash = ?, resume_text = ? WHERE id = ?",
                (name, email, pw_hash, resume_text.strip(), user_id)
            )
        else:
            cur.execute(
                "UPDATE users SET name = ?, email = ?, password_hash = ? WHERE id = ?",
                (name, email, pw_hash, user_id)
            )
    else:
        if resume_text is not None and resume_filename is not None:
            cur.execute(
                "UPDATE users SET name = ?, email = ?, resume_text = ?, resume_filename = ? WHERE id = ?",
                (name, email, resume_text.strip(), resume_filename.strip(), user_id)
            )
        elif resume_text is not None:
            cur.execute(
                "UPDATE users SET name = ?, email = ?, resume_text = ? WHERE id = ?",
                (name, email, resume_text.strip(), user_id)
            )
        else:
            cur.execute(
                "UPDATE users SET name = ?, email = ? WHERE id = ?",
                (name, email, user_id)
            )

    cur.execute(
        "UPDATE job_checks SET user_name = ?, user_email = ? WHERE user_id = ?",
        (name, email, user_id)
    )

    conn.commit()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    updated = cur.fetchone()
    conn.close()

    return {
        "id": updated["id"],
        "name": updated["name"],
        "email": updated["email"],
        "role": updated["role"],
        "gdpr_consent": bool(updated["gdpr_consent"]),
        "created_at": updated["created_at"],
        "resume_text": updated.get("resume_text") or "",
        "resume_filename": updated.get("resume_filename") or ""
    }, None


def get_user_by_id(user_id):
    if not user_id:
        return None
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "gdpr_consent": bool(row["gdpr_consent"]),
        "created_at": row["created_at"],
        "resume_text": row.get("resume_text") or ""
    }


def record_job_check(
    user_id,
    user_name,
    user_email,
    job_title,
    company_name,
    recruiter_email,
    job_url,
    official_job_url,
    domain,
    company_address,
    salary,
    job_description,
    result,
    reason,
    warnings
):
    """Store a job check and evaluate community fake job flagging."""
    conn = get_db_connection()
    cur = conn.cursor()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fingerprint = compute_job_fingerprint(
        job_url=official_job_url or job_url,
        company=company_name,
        job_title=job_title,
        recruiter_email=recruiter_email
    )

    is_suspicious = 1 if (result in ("NOT VERIFIED", "HIGH RISK", "INVALID LINK", "COULD NOT VERIFY")) else 0

    cur.execute("""
        INSERT INTO job_checks (
            user_id, user_name, user_email, job_fingerprint,
            job_title, company_name, recruiter_email, job_url,
            official_job_url, domain, company_address, salary,
            job_description, result, reason, warnings_json,
            is_fake_or_suspicious, checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        user_name or "User",
        user_email or "user@local",
        fingerprint,
        job_title or "Job Check",
        company_name or "Unknown Company",
        recruiter_email,
        job_url,
        official_job_url,
        domain,
        company_address,
        salary,
        job_description,
        result,
        reason,
        json.dumps(warnings or []),
        is_suspicious,
        now_str
    ))
    inserted_check_id = cur.lastrowid

    cur.execute("""
        SELECT COUNT(*) AS total_checks,
               COUNT(DISTINCT user_email) AS distinct_users,
               SUM(is_fake_or_suspicious) AS suspicious_checks
        FROM job_checks
        WHERE job_fingerprint = ?
    """, (fingerprint,))
    stats = cur.fetchone()
    total_checks = int(stats["total_checks"] or 1)
    distinct_users = int(stats["distinct_users"] or 1)
    suspicious_checks = int(stats["suspicious_checks"] or 0)

    cur.execute("""
        SELECT DISTINCT user_email, user_name
        FROM job_checks
        WHERE job_fingerprint = ?
    """, (fingerprint,))
    users_list = [{"email": r["user_email"], "name": r["user_name"]} for r in cur.fetchall()]

    cur.execute("SELECT * FROM flagged_jobs WHERE job_fingerprint = ?", (fingerprint,))
    existing_flag = cur.fetchone()
    admin_status = existing_flag["admin_status"] if existing_flag else "auto"

    is_flagged_fake = 0
    flag_reason = None

    if admin_status == "confirmed_scam":
        is_flagged_fake = 1
        flag_reason = "Flagged as a fake job advertisement by administrator."
    elif admin_status == "marked_safe":
        is_flagged_fake = 0
        flag_reason = "Reviewed and marked safe by administrator."
    else:
        if (distinct_users >= 5 or distinct_users > 5) and suspicious_checks > 0:
            is_flagged_fake = 1
            flag_reason = (
                f"Community Flagged Scam: Checked by {distinct_users} users with suspicious warning signs "
                f"({suspicious_checks} suspicious checks out of {total_checks} total checks)."
            )

    if existing_flag:
        cur.execute("""
            UPDATE flagged_jobs
            SET job_url = COALESCE(?, job_url),
                company_name = COALESCE(?, company_name),
                job_title = COALESCE(?, job_title),
                recruiter_email = COALESCE(?, recruiter_email),
                latest_result = ?,
                total_checks = ?,
                distinct_users_count = ?,
                checked_by_users_json = ?,
                is_flagged_fake = ?,
                flag_reason = COALESCE(?, flag_reason),
                last_seen_at = ?
            WHERE job_fingerprint = ?
        """, (
            official_job_url or job_url,
            company_name,
            job_title,
            recruiter_email,
            result,
            total_checks,
            distinct_users,
            json.dumps(users_list),
            is_flagged_fake,
            flag_reason,
            now_str,
            fingerprint
        ))
    else:
        cur.execute("""
            INSERT INTO flagged_jobs (
                job_fingerprint, job_url, company_name, job_title, recruiter_email,
                latest_result, total_checks, distinct_users_count, checked_by_users_json,
                is_flagged_fake, admin_status, flag_reason, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fingerprint,
            official_job_url or job_url,
            company_name or "Unknown Company",
            job_title or "Job Check",
            recruiter_email,
            result,
            total_checks,
            distinct_users,
            json.dumps(users_list),
            is_flagged_fake,
            admin_status,
            flag_reason,
            now_str,
            now_str
        ))

    conn.commit()
    conn.close()

    return {
        "check_id": inserted_check_id,
        "job_fingerprint": fingerprint,
        "total_checks": total_checks,
        "distinct_users_count": distinct_users,
        "is_flagged_fake": bool(is_flagged_fake),
        "admin_status": admin_status,
        "flag_reason": flag_reason,
        "checked_by_users": users_list
    }


def get_user_history(user_email=None, user_id=None, limit=50):
    """Return previous job checks for a specific user."""
    conn = get_db_connection()
    cur = conn.cursor()

    if user_id and user_email:
        cur.execute("""
            SELECT jc.*, fj.is_flagged_fake, fj.distinct_users_count, fj.total_checks, fj.flag_reason
            FROM job_checks jc
            LEFT JOIN flagged_jobs fj ON jc.job_fingerprint = fj.job_fingerprint
            WHERE jc.user_id = ? OR LOWER(jc.user_email) = LOWER(?)
            ORDER BY jc.id DESC
            LIMIT ?
        """, (int(user_id), user_email, int(limit)))
    elif user_id:
        cur.execute("""
            SELECT jc.*, fj.is_flagged_fake, fj.distinct_users_count, fj.total_checks, fj.flag_reason
            FROM job_checks jc
            LEFT JOIN flagged_jobs fj ON jc.job_fingerprint = fj.job_fingerprint
            WHERE jc.user_id = ?
            ORDER BY jc.id DESC
            LIMIT ?
        """, (int(user_id), int(limit)))
    elif user_email:
        cur.execute("""
            SELECT jc.*, fj.is_flagged_fake, fj.distinct_users_count, fj.total_checks, fj.flag_reason
            FROM job_checks jc
            LEFT JOIN flagged_jobs fj ON jc.job_fingerprint = fj.job_fingerprint
            WHERE LOWER(jc.user_email) = LOWER(?)
            ORDER BY jc.id DESC
            LIMIT ?
        """, (user_email, int(limit)))
    else:
        conn.close()
        return []

    rows = cur.fetchall()
    conn.close()

    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "user_name": r["user_name"],
            "user_email": r["user_email"],
            "job_title": r["job_title"] or "Job Check",
            "company_name": r["company_name"] or "Unknown Company",
            "recruiter_email": r["recruiter_email"],
            "job_url": r["official_job_url"] or r["job_url"],
            "company_address": r["company_address"] if "company_address" in r.keys() else None,
            "result": r["result"],
            "reason": r["reason"],
            "warnings": json.loads(r["warnings_json"] or "[]"),
            "checked_at": r["checked_at"],
            "is_flagged_fake": bool(r["is_flagged_fake"]),
            "distinct_users_count": r["distinct_users_count"] or 1,
            "total_checks": r["total_checks"] or 1,
            "flag_reason": r["flag_reason"]
        })
    return items


def get_flagged_fake_jobs(limit=100):
    """Return all job advertisements flagged as fake/suspicious by multiple users or admin."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM flagged_jobs
        WHERE is_flagged_fake = 1
        ORDER BY last_seen_at DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()

    flagged = []
    for r in rows:
        flagged.append({
            "job_fingerprint": r["job_fingerprint"],
            "job_url": r["job_url"],
            "company_name": r["company_name"] or "Unknown Company",
            "job_title": r["job_title"] or "Job Check",
            "recruiter_email": r["recruiter_email"],
            "latest_result": r["latest_result"],
            "total_checks": r["total_checks"],
            "distinct_users_count": r["distinct_users_count"],
            "checked_by_users": json.loads(r["checked_by_users_json"] or "[]"),
            "is_flagged_fake": bool(r["is_flagged_fake"]),
            "admin_status": r["admin_status"],
            "flag_reason": r["flag_reason"],
            "first_seen_at": r["first_seen_at"],
            "last_seen_at": r["last_seen_at"]
        })
    return flagged


def get_admin_overview():
    """Return complete platform data for the Admin page."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, name, email, role, gdpr_consent, created_at FROM users ORDER BY id DESC")
    users = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT jc.*, fj.is_flagged_fake, fj.distinct_users_count, fj.total_checks, fj.flag_reason, fj.admin_status
        FROM job_checks jc
        LEFT JOIN flagged_jobs fj ON jc.job_fingerprint = fj.job_fingerprint
        ORDER BY jc.id DESC
        LIMIT 100
    """)
    all_checks = []
    for r in cur.fetchall():
        all_checks.append({
            "id": r["id"],
            "user_id": r["user_id"],
            "user_name": r["user_name"],
            "user_email": r["user_email"],
            "job_fingerprint": r["job_fingerprint"],
            "job_title": r["job_title"],
            "company_name": r["company_name"],
            "recruiter_email": r["recruiter_email"],
            "job_url": r["official_job_url"] or r["job_url"],
            "result": r["result"],
            "reason": r["reason"],
            "warnings": json.loads(r["warnings_json"] or "[]"),
            "is_fake_or_suspicious": bool(r["is_fake_or_suspicious"]),
            "is_flagged_fake": bool(r["is_flagged_fake"]),
            "distinct_users_count": r["distinct_users_count"] or 1,
            "total_checks": r["total_checks"] or 1,
            "admin_status": r["admin_status"] or "auto",
            "flag_reason": r["flag_reason"],
            "checked_at": r["checked_at"]
        })

    flagged_jobs = get_flagged_fake_jobs()

    cur.execute("SELECT COUNT(*) AS cnt FROM job_checks")
    total_checks_count = int((cur.fetchone() or [0])[0])

    cur.execute("SELECT COUNT(*) AS cnt FROM job_checks WHERE is_fake_or_suspicious = 1")
    suspicious_checks_count = int((cur.fetchone() or [0])[0])

    conn.close()

    return {
        "stats": {
            "total_users": len(users),
            "total_checks": total_checks_count,
            "suspicious_checks": suspicious_checks_count,
            "flagged_fake_jobs_count": len(flagged_jobs)
        },
        "users": users,
        "recent_checks": all_checks,
        "flagged_jobs": flagged_jobs
    }


def update_job_flag_status(job_fingerprint, action):
    """Allow Admin to manually confirm a job as scam or mark it safe."""
    conn = get_db_connection()
    cur = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if action == "confirm_scam":
        cur.execute("""
            UPDATE flagged_jobs
            SET is_flagged_fake = 1,
                admin_status = 'confirmed_scam',
                flag_reason = 'Flagged as a fake job advertisement by administrator.',
                last_seen_at = ?
            WHERE job_fingerprint = ?
        """, (now_str, job_fingerprint))
    elif action == "mark_safe":
        cur.execute("""
            UPDATE flagged_jobs
            SET is_flagged_fake = 0,
                admin_status = 'marked_safe',
                flag_reason = 'Reviewed and cleared by administrator.',
                last_seen_at = ?
            WHERE job_fingerprint = ?
        """, (now_str, job_fingerprint))

    conn.commit()
    conn.close()


def flag_job_by_user(job_url="", company_name="", job_title="", reason="Flagged by user as fraudulent or scam"):
    """Manually flag a job advertisement as fake/scam, updating flagged_jobs and job_checks."""
    conn = get_db_connection()
    cur = conn.cursor()
    fingerprint = compute_job_fingerprint(job_url=job_url, company=company_name, job_title=job_title)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("SELECT * FROM flagged_jobs WHERE job_fingerprint = ?", (fingerprint,))
    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE flagged_jobs
            SET is_flagged_fake = 1,
                admin_status = 'confirmed_scam',
                latest_result = 'HIGH RISK',
                flag_reason = ?,
                last_seen_at = ?
            WHERE job_fingerprint = ?
        """, (reason, now_str, fingerprint))
    else:
        cur.execute("""
            INSERT INTO flagged_jobs (
                job_fingerprint, job_url, company_name, job_title, recruiter_email,
                latest_result, total_checks, distinct_users_count, checked_by_users_json,
                is_flagged_fake, admin_status, flag_reason, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fingerprint,
            job_url or "",
            company_name or "Unknown Company",
            job_title or "Job Check",
            "",
            "HIGH RISK",
            1,
            1,
            json.dumps(["User Report"]),
            1,
            "confirmed_scam",
            reason,
            now_str,
            now_str
        ))

    if fingerprint:
        cur.execute("""
            UPDATE job_checks
            SET is_fake_or_suspicious = 1,
                result = 'HIGH RISK',
                reason = ?
            WHERE job_fingerprint = ? OR (company_name = ? AND ? != '')
        """, (reason, fingerprint, company_name, company_name))

    conn.commit()
    conn.close()

    return {
        "job_fingerprint": fingerprint,
        "is_flagged_fake": True,
        "flag_reason": reason
    }
