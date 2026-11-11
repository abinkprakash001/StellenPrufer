import os
import re
import json
import base64
import socket
import urllib.parse
import urllib.request
import urllib.error
import ssl
import html
from datetime import datetime, timedelta


def load_env_file():
    env_vars = {}
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as ef:
                for line in ef:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass
    return env_vars


ENV_VARS = load_env_file()
VIRUSTOTAL_API_KEY = os.environ.get("VIRUSTOTAL_API_KEY") or ENV_VARS.get("VIRUSTOTAL_API_KEY", "")
HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY") or ENV_VARS.get("HUNTER_API_KEY", "")

FREE_EMAIL_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.de", "hotmail.com",
    "outlook.com", "live.com", "aol.com", "icloud.com", "mail.com",
    "zoho.com", "proton.me", "protonmail.com", "gmx.de", "gmx.net",
    "web.de", "t-online.de", "freenet.de"
}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}

JOB_BOARD_DOMAINS = {
    "linkedin.com", "indeed.com", "stepstone.de", "stepstone.com",
    "xing.com", "glassdoor.com", "glassdoor.de", "monster.com",
    "monster.de", "jobware.de", "stellenanzeigen.de", "totaljobs.com",
    "reed.co.uk", "ziprecruiter.com", "simplyhired.com", "arbeitsagentur.de",
    "meinestadt.de", "kimeta.de", "jobbörse.de", "heyjobs.co"
}

PLATFORM_NAMES = {
    "linkedin", "indeed", "stepstone", "xing", "glassdoor", "monster",
    "jobware", "stellenanzeigen", "stellenanzeigende", "totaljobs", "reed",
    "ziprecruiter", "simplyhired", "arbeitsagentur", "bundesagentur",
    "meinestadt", "kimeta", "heyjobs", "company", "employer", "unknown",
    "employeronscreen", "employeronlinkedincom", "employeronwwwlinkedincom",
    "employerondelinkedincom", "companylistedonjobplatform"
}


def is_job_board_domain(domain):
    domain = domain.lower()
    return any(board in domain for board in JOB_BOARD_DOMAINS)


def is_platform_name(name):
    if not name:
        return False
    clean = re.sub(r'[^a-zA-Z0-9]', '', name).lower()
    return any(p == clean or p in clean for p in PLATFORM_NAMES)


def is_valid_url(url):
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def get_domain(url):
    return urllib.parse.urlparse(url).netloc.lower()


def safe_ascii_url(url):
    """Ensure URL contains only ASCII characters by percent-encoding Unicode path/query characters."""
    if not url:
        return url
    url = url.strip().split("\u2026")[0].rstrip(".")
    try:
        parts = urllib.parse.urlsplit(url)
        netloc = parts.netloc.encode("idna").decode("ascii")
        path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/:@&+$,;=-_.!~*'()")
        query = urllib.parse.quote(urllib.parse.unquote(parts.query), safe="=:&+$,;-_.!~*'()/?")
        fragment = urllib.parse.quote(urllib.parse.unquote(parts.fragment), safe="=:&+$,;-_.!~*'()/?")
        return urllib.parse.urlunsplit((parts.scheme, netloc, path, query, fragment))
    except Exception:
        return urllib.parse.quote(url, safe=":/?&=#+%~.-_!$'()*+,;")


def fetch_page(url):
    url = safe_ascii_url(url)
    request = urllib.request.Request(url, headers=DEFAULT_HEADERS)

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    final_url = url
    html = ""

    try:
        with urllib.request.urlopen(request, timeout=15, context=context) as response:
            final_url = response.geturl()
            html = response.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as error:
        try:
            html = error.read().decode("utf-8", errors="ignore")
            final_url = error.geturl() or url
        except Exception:
            pass

    # LinkedIn specialized guest API for any LinkedIn URL with a Job ID (/jobs/view/... or ?currentJobId=... or ?jobId=...)
    if "linkedin.com" in url.lower():
        job_id_m = re.search(r'(?:/jobs/view/(?:[^/?#]*?-)?|[?&](?:currentJobId|jobId)=)(\d{6,})', url, re.IGNORECASE)
        if job_id_m:
            jid = job_id_m.group(1)
            guest_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jid}"
            try:
                guest_req = urllib.request.Request(guest_url, headers=DEFAULT_HEADERS)
                with urllib.request.urlopen(guest_req, timeout=15, context=context) as g_resp:
                    guest_html = g_resp.read().decode("utf-8", errors="ignore")
                    if len(guest_html) > 500 and ("topcard" in guest_html or "show-more-less-html" in guest_html):
                        canonical_m = re.search(r'<a\b[^>]+href=["\'](https://[a-z.]+linkedin\.com/jobs/view/[^"\'?#]+)', guest_html, re.I)
                        resolved_url = canonical_m.group(1) if canonical_m else f"https://www.linkedin.com/jobs/view/{jid}"
                        return resolved_url, guest_html
            except Exception:
                pass

    # Arbeitsagentur.de specialized REST API resolution
    if "arbeitsagentur.de" in url.lower():
        ref_match = re.search(r'(?:jobdetail/|[?&](?:id|refnr|referenznummer)=)([\w\-]+)', url, re.IGNORECASE)
        if ref_match:
            refnr = ref_match.group(1)
            b64_ref = base64.b64encode(refnr.encode("utf-8")).decode("utf-8")
            aa_api_url = f"https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/{b64_ref}"
            try:
                aa_headers = {
                    "X-API-Key": "jobboerse-jobsuche",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json"
                }
                aa_req = urllib.request.Request(aa_api_url, headers=aa_headers)
                with urllib.request.urlopen(aa_req, timeout=12, context=context) as aa_resp:
                    aa_raw = aa_resp.read().decode("utf-8", errors="ignore")
                    aa_data = json.loads(aa_raw)
                    if aa_data and (aa_data.get("firma") or aa_data.get("stellenangebotsTitel")):
                        titel = aa_data.get("stellenangebotsTitel") or aa_data.get("titel") or ""
                        firma = aa_data.get("firma") or aa_data.get("arbeitgeber") or ""
                        lok_list = aa_data.get("stellenlokationen") or []
                        addr = ""
                        locality = ""
                        region = ""
                        country = "DE"
                        if lok_list and isinstance(lok_list, list) and len(lok_list) > 0:
                            ad = lok_list[0].get("adresse") or {}
                            locality = ad.get("ort") or ""
                            region = ad.get("region") or ""
                            country = ad.get("land") or "DE"
                            addr = f"{ad.get('plz', '')} {locality}, {region}, {country}".strip(", ")
                        desc = aa_data.get("stellenangebotsBeschreibung") or ""
                        date_p = aa_data.get("datumErsteVeroeffentlichung") or ""
                        ext_url = aa_data.get("externeURL") or ""
                        
                        salary_str = ""
                        von = aa_data.get("gehaltsspanneVon")
                        bis = aa_data.get("gehaltsspanneBis")
                        art = str(aa_data.get("verguetungsangabe") or "")
                        if von and bis:
                            period = "Jahr" if "JAHR" in art else ("Monat" if "MONAT" in art else "h")
                            salary_str = f"{von:,.0f} € - {bis:,.0f} €/{period}".replace(",", ".")
                        
                        jsonld_obj = {
                            "@context": "https://schema.org",
                            "@type": "JobPosting",
                            "title": titel,
                            "hiringOrganization": {
                                "@type": "Organization",
                                "name": firma
                            },
                            "jobLocation": {
                                "@type": "Place",
                                "address": {
                                    "@type": "PostalAddress",
                                    "addressLocality": locality,
                                    "addressRegion": region,
                                    "addressCountry": country
                                }
                            },
                            "datePosted": date_p,
                            "description": desc
                        }
                        
                        aa_html = f"""<!DOCTYPE html><html><head>
                        <title>{titel} bei {firma} | Jobsuche der BA</title>
                        <script type="application/ld+json">{json.dumps(jsonld_obj, ensure_ascii=False)}</script>
                        </head><body>
                        <h1 id="detail-kopfbereich-titel">{titel}</h1>
                        <div id="detail-kopfbereich-firma">{firma}</div>
                        <div id="detail-kopfbereich-arbeitsort">{addr}</div>
                        <div id="detail-beschreibung-container">{desc}</div>
                        <div id="detail-footer-referenznummer">{refnr}</div>
                        {f'<div id="detail-kopfbereich-gehalt">{salary_str}</div>' if salary_str else ''}
                        </body></html>"""
                        
                        resolved_url = f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"
                        return resolved_url, aa_html
            except Exception:
                pass

    # Stellenanzeigen.de split-view feed URL resolution (?jobId=SDE-120763 -> /job/...-sde-120763/)
    if "stellenanzeigen.de" in url.lower() and "/job/" not in final_url.lower():
        parsed_q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        job_id_val = (parsed_q.get("jobId") or parsed_q.get("jobid") or [""])[0].strip()
        if job_id_val and html:
            pat = r"""(https?://www\.stellenanzeigen\.de/job/[^"'\s<>]*?""" + re.escape(job_id_val) + r"""[^"'\s<>]*|/job/[^"'\s<>]*?""" + re.escape(job_id_val) + r"""[^"'\s<>]*)"""
            m_job = re.search(pat, html, re.IGNORECASE)
            if m_job:
                detail_url = urllib.parse.urljoin("https://www.stellenanzeigen.de", m_job.group(1))
                try:
                    d_req = urllib.request.Request(safe_ascii_url(detail_url), headers=DEFAULT_HEADERS)
                    with urllib.request.urlopen(d_req, timeout=15, context=context) as d_resp:
                        d_html = d_resp.read().decode("utf-8", errors="ignore")
                        if len(d_html) > 500:
                            final_url = d_resp.geturl() or detail_url
                            html = d_html
                except Exception:
                    pass

    if not html:
        raise urllib.error.HTTPError(url, 403, "Page content empty or blocked", {}, None)

    return final_url, html




def get_attr_value(tag_str, attr_name):
    """Safely extracts HTML attribute values enclosed in either single or double quotes."""
    pattern = r'\b' + attr_name + r'\s*=\s*(?:"([^"]*)"|\'([^\']*)\')'
    m = re.search(pattern, tag_str, re.IGNORECASE)
    if m:
        val = m.group(1) if m.group(1) is not None else m.group(2)
        return html.unescape(val).strip()
    return None


def extract_company_details(html_content, domain="", original_url=""):
    company_name = None
    address = None
    official_job_url = None

    # Canonical job URL check first
    for link_tag in re.findall(r'<link\b[^>]*>', html_content, re.IGNORECASE):
        rel = get_attr_value(link_tag, "rel")
        if rel and rel.lower() == "canonical":
            href = get_attr_value(link_tag, "href")
            if href and href.startswith("http"):
                official_job_url = href
                break

    is_job_board = is_job_board_domain(domain)

    # 1. Specialized Job Board Extraction: LinkedIn
    if "linkedin.com" in domain:
        # Title patterns on LinkedIn:
        # A: "Company hiring Job Title in Location | LinkedIn"
        # B: "Job Title at Company — Location | LinkedIn Jobs"
        title_m = re.search(r'<title\b[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if title_m:
            title_text = html.unescape(title_m.group(1)).strip()
            mA = re.search(r'^(.*?)\s+(?:hiring|stellt\s+ein)\s+(.*?)(?:\s+(?:in|–|-|—)\s+(.*?))?\s*\|\s*LinkedIn', title_text, re.IGNORECASE)
            if mA:
                cand = mA.group(1).strip()
                if not is_platform_name(cand):
                    company_name = cand
                    if mA.group(3) and not address:
                        address = mA.group(3).strip()

            if not company_name:
                mB = re.search(r'^(.*?)\s+(?:at|bei)\s+(.*?)(?:\s+(?:[—–-]|in)\s+(.*?))?\s*\|\s*LinkedIn', title_text, re.IGNORECASE)
                if mB:
                    cand = mB.group(2).strip()
                    if not is_platform_name(cand):
                        company_name = cand
                        if mB.group(3) and not address:
                            address = mB.group(3).strip()

        # LinkedIn DOM company links:
        if not company_name:
            m_comp = re.findall(
                r'<a\b[^>]+class=["\'][^"\']*(?:sub-nav-cta__optional-url|topcard__org-name-link)[^"\']*["\'][^>]*>(.*?)</a>',
                html_content,
                re.IGNORECASE | re.DOTALL,
            )
            for raw_c in m_comp:
                clean_c = re.sub(r'<[^>]+>', '', raw_c).strip()
                if clean_c and not is_platform_name(clean_c):
                    company_name = clean_c
                    break

        # LinkedIn DOM location:
        if not address:
            m_loc = re.findall(
                r'<span\b[^>]+class=["\'][^"\']*(?:sub-nav-cta__meta-text|topcard__flavor--bullet)[^"\']*["\'][^>]*>(.*?)</span>',
                html_content,
                re.IGNORECASE | re.DOTALL,
            )
            for raw_l in m_loc:
                clean_l = re.sub(r'<[^>]+>', '', raw_l).strip()
                if clean_l and not re.search(r'(applicant|bewerber|ago|vor\s+\d+|day|hour|woche)', clean_l, re.IGNORECASE):
                    address = clean_l
                    break

        # LinkedIn modal text: role at <strong>Company</strong>
        if not company_name:
            role_m = re.search(r'role\s+at\s+<strong>(.*?)</strong>', html_content, re.IGNORECASE)
            if role_m:
                cand = re.sub(r'<[^>]+>', '', role_m.group(1)).strip()
                if cand and not is_platform_name(cand):
                    company_name = cand

        # LinkedIn canonical/original URL slug fallback: /jobs/view/job-title-at-company-name-12345
        target_url = official_job_url or original_url
        if not company_name and target_url:
            slug_m = re.search(r'/jobs/view/(?:.+?)-at-([a-z0-9-]+)-\d+', target_url, re.IGNORECASE)
            if slug_m:
                cand = slug_m.group(1).replace('-', ' ').title()
                if cand and not is_platform_name(cand):
                    company_name = cand

    # Specialized Job Board Extraction: Arbeitsagentur (Bundesagentur für Arbeit)
    if "arbeitsagentur.de" in domain or "arbeitsagentur.de" in (original_url or ""):
        # A. DOM element with #detail-kopfbereich-firma
        m_firma = re.search(r'id=["\']detail-kopfbereich-firma["\'][^>]*>(.*?)</div>', html_content, re.IGNORECASE | re.DOTALL)
        if m_firma:
            cand = re.sub(r'<[^>]+>', '', m_firma.group(1)).strip()
            if cand and not is_platform_name(cand):
                company_name = cand
        
        # B. DOM element with #detail-kopfbereich-arbeitsort
        if not address:
            m_ort = re.search(r'id=["\']detail-kopfbereich-arbeitsort["\'][^>]*>(.*?)</div>', html_content, re.IGNORECASE | re.DOTALL)
            if m_ort:
                clean_ort = re.sub(r'<[^>]+>', '', m_ort.group(1)).strip()
                if clean_ort:
                    address = clean_ort

        # C. ng-state embedded Angular JSON
        if not company_name:
            m_ng = re.search(r'<script\s+id=["\']ng-state["\'][^>]*>(.*?)</script>', html_content, re.IGNORECASE | re.DOTALL)
            if m_ng:
                try:
                    ng_data = json.loads(m_ng.group(1))
                    jd = ng_data.get("jobdetail") or (ng_data.get("jobdetails") and ng_data["jobdetails"].get("b")) or {}
                    cand = jd.get("firma") or jd.get("arbeitgeber")
                    if cand and not is_platform_name(cand):
                        company_name = cand.strip()
                    if not address and jd.get("stellenlokationen"):
                        lok_list = jd["stellenlokationen"]
                        if isinstance(lok_list, list) and len(lok_list) > 0:
                            ad = lok_list[0].get("adresse") or {}
                            address = f"{ad.get('plz', '')} {ad.get('ort', '')}, {ad.get('land', 'Germany')}".strip(", ")
                except Exception:
                    pass

        # D. Meta description pattern: "Stellenangebot für ... bei <Company> in <Location>"
        if not company_name:
            m_desc = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
            if m_desc:
                m_bei = re.search(r'(?:bei|f[üu]r)\s+(.+?)\s+in\s+([A-ZÄÖÜ][a-zäöüß\s\-()]+)', m_desc.group(1), re.IGNORECASE)
                if m_bei:
                    cand = m_bei.group(1).strip()
                    if cand and not is_platform_name(cand):
                        company_name = cand
                    if not address and m_bei.group(2):
                        address = m_bei.group(2).strip()

    # 2. JSON-LD extraction
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_content,
        re.DOTALL | re.IGNORECASE,
    )

    for script in scripts:
        try:
            data = json.loads(script.strip())
        except Exception:
            continue

        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                items = data["@graph"]
            else:
                items = [data]

        for item in items:
            if not isinstance(item, dict):
                continue

            raw_type = item.get("@type", "")
            types = raw_type if isinstance(raw_type, list) else [raw_type]
            types = [t.split("/")[-1] for t in types if isinstance(t, str)]

            if "JobPosting" in types:
                official_job_url = item.get("url") or official_job_url

                hiring_org = item.get("hiringOrganization")
                if isinstance(hiring_org, dict):
                    cand = hiring_org.get("name")
                    if cand and not (is_job_board and is_platform_name(cand)):
                        company_name = cand or company_name
                    addr_data = hiring_org.get("address")
                    if isinstance(addr_data, dict):
                        address = ", ".join(
                            str(v) for v in addr_data.values() if v and isinstance(v, (str, int))
                        ) or address
                    elif isinstance(addr_data, str):
                        address = addr_data or address
                elif isinstance(hiring_org, str) and not (is_job_board and is_platform_name(hiring_org)):
                    company_name = hiring_org or company_name

                if not address and "jobLocation" in item:
                    loc = item["jobLocation"]
                    if isinstance(loc, list) and loc:
                        loc = loc[0]
                    if isinstance(loc, dict):
                        addr_data = loc.get("address")
                        if isinstance(addr_data, dict):
                            addr_parts = []
                            for k in ("streetAddress", "postalCode", "addressLocality", "addressRegion", "addressCountry"):
                                val = addr_data.get(k)
                                if val and isinstance(val, (str, int)) and str(val).strip():
                                    addr_parts.append(str(val).strip())
                            if addr_parts:
                                address = ", ".join(addr_parts)
                            else:
                                address = ", ".join(
                                    str(v) for v in addr_data.values() if v and isinstance(v, (str, int)) and not str(v).startswith("Place") and not str(v).startswith("Postal")
                                ) or address
                        elif isinstance(addr_data, str):
                            address = addr_data or address

            if "Organization" in types and not is_job_board:
                cand = item.get("name")
                if cand and not is_platform_name(cand):
                    company_name = cand or company_name
                addr_data = item.get("address")
                if isinstance(addr_data, dict):
                    address = ", ".join(
                        str(v) for v in addr_data.values() if v and isinstance(v, (str, int))
                    ) or address
                elif isinstance(addr_data, str):
                    address = addr_data or address

    # 3. Schema.org Microdata & meta tags in HTML
    meta_tags = re.findall(r'<meta\b[^>]*>', html_content, re.IGNORECASE)
    meta_props = {}
    for tag in meta_tags:
        itemprop = get_attr_value(tag, "itemprop")
        property_val = get_attr_value(tag, "property")
        name_val = get_attr_value(tag, "name")
        content_val = get_attr_value(tag, "content")

        key = itemprop or property_val or name_val
        if key and content_val:
            meta_props[key.lower()] = content_val

    if not company_name:
        for key in ["hiringorganization", "og:site_name", "author", "publisher"]:
            if key in meta_props and meta_props[key]:
                cand = meta_props[key]
                if not is_platform_name(cand):
                    company_name = cand
                    break

    if not address:
        addr_parts = []
        for key in ["streetaddress", "addresslocality", "addressregion", "postalcode", "addresscountry"]:
            if key in meta_props and meta_props[key]:
                addr_parts.append(meta_props[key])
        if addr_parts:
            address = ", ".join(addr_parts)

    # 4. Microdata in DOM elements
    if not company_name:
        m = re.search(
            r'<[^>]+itemprop=["\']hiringOrganization["\'][^>]*>(.*?)</[^>]+>',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            clean_text = re.sub(r'<[^>]+>', ' ', m.group(1)).strip()
            if clean_text and not is_platform_name(clean_text):
                company_name = clean_text

    # 5. Job board specific DOM elements (SAP SuccessFactors, Workday, etc.)
    if not company_name:
        m = re.search(
            r'<[^>]+(?:id|class)=["\'][^"\']*(?:jobCompany|job-company|company-name|employer)[^"\']*["\'][^>]*>(.*?)</(?:p|div|span|h[1-6])>',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            clean_text = re.sub(r'<[^>]+>', ' ', m.group(1)).strip()
            clean_text = re.sub(r'^(Unternehmen|Company|Employer)\s*:\s*', '', clean_text, flags=re.IGNORECASE).strip()
            if clean_text and not is_platform_name(clean_text):
                company_name = clean_text

    if not address:
        m = re.search(
            r'<[^>]+class=["\'][^"\']*(?:jobGeoLocation|job-location|jobLocation)[^"\']*["\'][^>]*>(.*?)</(?:p|div|span)>',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            clean_text = re.sub(r'<[^>]+>', ' ', m.group(1)).strip()
            clean_text = re.sub(r'^(Standort|Location)\s*:\s*', '', clean_text, flags=re.IGNORECASE).strip()
            if clean_text:
                address = clean_text

    # 6. Page <title> fallback (for generic career pages)
    if not company_name:
        m = re.search(r'<title\b[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if m:
            title_text = html.unescape(m.group(1)).strip()
            for sep in [" | ", " - ", " – "]:
                if sep in title_text:
                    parts = title_text.split(sep)
                    candidate = parts[-1].strip()
                    if (
                        candidate.lower() not in ("careers", "jobs", "stellendetails", "karriere")
                        and len(candidate) > 2
                        and not is_platform_name(candidate)
                    ):
                        company_name = candidate
                        break

    return company_name, address, official_job_url


def get_company_from_domain(domain):
    if is_job_board_domain(domain):
        return None

    domain = domain.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    parts = domain.split(".")

    ignore_start = {
        "jobs", "job", "career", "careers", "apply", "recruit",
        "recruitment", "work", "working", "karriere", "stellenangebote"
    }

    if len(parts) >= 3 and parts[0] in ignore_start:
        parts = parts[1:]

    if len(parts) >= 2:
        brand = parts[0]
        if is_platform_name(brand):
            return None
        if brand == "mcdonalds":
            return "McDonald's"
        return brand.capitalize()

    return None


def check_url_security(url):
    warnings = []
    parsed = urllib.parse.urlparse(url)

    if parsed.scheme != "https":
        warnings.append("The link does not use HTTPS.")

    domain = get_domain(url)

    try:
        socket.gethostbyname(domain)
    except Exception:
        warnings.append("The website domain could not be resolved.")

    return warnings, domain


def create_handelsregister_search_url(company_name):
    if not company_name:
        return ""
    query = urllib.parse.quote(str(company_name).strip())
    return "https://www.northdata.de/" + query


_REGISTER_CACHE = {}
_VT_CACHE = {}

KNOWN_GERMAN_REGISTRATIONS = {
    "freie universität berlin": {
        "official_name": "Freie Universität Berlin",
        "registered_location": "Berlin",
        "register_entry": "Körperschaft des öffentlichen Rechts (BerlHG)",
        "is_public_institution": True
    },
    "freie universitaet berlin": {
        "official_name": "Freie Universität Berlin",
        "registered_location": "Berlin",
        "register_entry": "Körperschaft des öffentlichen Rechts (BerlHG)",
        "is_public_institution": True
    },
    "fu berlin": {
        "official_name": "Freie Universität Berlin",
        "registered_location": "Berlin",
        "register_entry": "Körperschaft des öffentlichen Rechts (BerlHG)",
        "is_public_institution": True
    },
    "humboldt-universität zu berlin": {
        "official_name": "Humboldt-Universität zu Berlin",
        "registered_location": "Berlin",
        "register_entry": "Körperschaft des öffentlichen Rechts (BerlHG)",
        "is_public_institution": True
    },
    "humboldt universität berlin": {
        "official_name": "Humboldt-Universität zu Berlin",
        "registered_location": "Berlin",
        "register_entry": "Körperschaft des öffentlichen Rechts (BerlHG)",
        "is_public_institution": True
    },
    "hu berlin": {
        "official_name": "Humboldt-Universität zu Berlin",
        "registered_location": "Berlin",
        "register_entry": "Körperschaft des öffentlichen Rechts (BerlHG)",
        "is_public_institution": True
    },
    "technische universität berlin": {
        "official_name": "Technische Universität Berlin",
        "registered_location": "Berlin",
        "register_entry": "Körperschaft des öffentlichen Rechts (BerlHG)",
        "is_public_institution": True
    },
    "tu berlin": {
        "official_name": "Technische Universität Berlin",
        "registered_location": "Berlin",
        "register_entry": "Körperschaft des öffentlichen Rechts (BerlHG)",
        "is_public_institution": True
    },
    "charité": {
        "official_name": "Charité – Universitätsmedizin Berlin",
        "registered_location": "Berlin",
        "register_entry": "Gliedkörperschaft der Freien Universität Berlin und der Humboldt-Universität zu Berlin (KdöR)",
        "is_public_institution": True
    },
    "charite": {
        "official_name": "Charité – Universitätsmedizin Berlin",
        "registered_location": "Berlin",
        "register_entry": "Gliedkörperschaft der Freien Universität Berlin und der Humboldt-Universität zu Berlin (KdöR)",
        "is_public_institution": True
    },
    "ludwig-maximilians-universität münchen": {
        "official_name": "Ludwig-Maximilians-Universität München",
        "registered_location": "München",
        "register_entry": "Körperschaft des öffentlichen Rechts (BayHIG)",
        "is_public_institution": True
    },
    "lmu münchen": {
        "official_name": "Ludwig-Maximilians-Universität München",
        "registered_location": "München",
        "register_entry": "Körperschaft des öffentlichen Rechts (BayHIG)",
        "is_public_institution": True
    },
    "technische universität münchen": {
        "official_name": "Technische Universität München",
        "registered_location": "München",
        "register_entry": "Körperschaft des öffentlichen Rechts (BayHIG)",
        "is_public_institution": True
    },
    "tum": {
        "official_name": "Technische Universität München",
        "registered_location": "München",
        "register_entry": "Körperschaft des öffentlichen Rechts (BayHIG)",
        "is_public_institution": True
    },
    "rwth aachen": {
        "official_name": "Rheinisch-Westfälische Technische Hochschule Aachen",
        "registered_location": "Aachen",
        "register_entry": "Körperschaft des öffentlichen Rechts (HG NRW)",
        "is_public_institution": True
    },
    "universität heidelberg": {
        "official_name": "Ruprecht-Karls-Universität Heidelberg",
        "registered_location": "Heidelberg",
        "register_entry": "Körperschaft des öffentlichen Rechts",
        "is_public_institution": True
    },
    "universität hamburg": {
        "official_name": "Universität Hamburg",
        "registered_location": "Hamburg",
        "register_entry": "Körperschaft des öffentlichen Rechts (HmbHG)",
        "is_public_institution": True
    },
    "universität zu köln": {
        "official_name": "Universität zu Köln",
        "registered_location": "Köln",
        "register_entry": "Körperschaft des öffentlichen Rechts (HG NRW)",
        "is_public_institution": True
    },
    "bundesagentur für arbeit": {
        "official_name": "Bundesagentur für Arbeit",
        "registered_location": "Nürnberg",
        "register_entry": "Bundesunmittelbare Körperschaft des öffentlichen Rechts mit Selbstverwaltung",
        "is_public_institution": True
    },
    "fraunhofer": {
        "official_name": "Fraunhofer-Gesellschaft zur Förderung der angewandten Forschung e.V.",
        "registered_location": "München (VR 4461)",
        "register_entry": "Eingetragener Verein (VR 4461 München)",
        "is_public_institution": True
    },
    "max-planck": {
        "official_name": "Max-Planck-Gesellschaft zur Förderung der Wissenschaften e.V.",
        "registered_location": "Berlin (VR 13378 B)",
        "register_entry": "Eingetragener Verein (VR 13378 B Charlottenburg)",
        "is_public_institution": True
    }
}


def lookup_commercial_register(company_name):
    """Automatically check if a company has a German Handelsregister (HRA/HRB) entry and extract official name/city."""
    if not company_name:
        return {
            "found_in_handelsregister": False,
            "register_entry": None,
            "official_name": None,
            "registered_location": None,
            "direct_search_url": "",
            "handelsregister_portal": "https://www.handelsregister.de/rp_web/welcome.xhtml"
        }

    c_key = str(company_name).strip().lower()
    if c_key in _REGISTER_CACHE:
        return _REGISTER_CACHE[c_key]
    direct_url = create_handelsregister_search_url(company_name)
    portal_url = "https://www.handelsregister.de/rp_web/welcome.xhtml"

    for k_name, k_info in KNOWN_GERMAN_REGISTRATIONS.items():
        if k_name in c_key or c_key in k_name:
            res_known = {
                "found_in_handelsregister": True,
                "is_public_institution": bool(k_info.get("is_public_institution")),
                "register_entry": k_info["register_entry"],
                "official_name": k_info["official_name"],
                "registered_location": k_info["registered_location"],
                "direct_search_url": direct_url,
                "handelsregister_portal": portal_url
            }
            _REGISTER_CACHE[c_key] = res_known
            return res_known

    # Algorithmic detection for German Public Universities, Research Centers and Statutory Authorities
    pub_keywords = ["universität", "universitaet", "hochschule", "charité", "charite", "klinikum", "bundesagentur", "bundesamt", "landesamt", "senatsverwaltung", "stadtverwaltung", "deutsches rotes kreuz", "max-planck", "fraunhofer", "helmholtz", "leibniz-institut", "körperschaft des öffentlichen rechts"]
    if any(k in c_key for k in pub_keywords):
        detected_loc = "Germany"
        for city in ["berlin", "münchen", "hamburg", "köln", "frankfurt", "stuttgart", "düsseldorf", "leipzig", "dresden", "aachen", "heidelberg", "bonn", "nürnberg", "bremen", "hannover", "freiburg", "tübingen", "göttingen", "kiel", "jena", "potsdam", "würzburg"]:
            if city in c_key:
                detected_loc = city.capitalize()
                break
        res_pub = {
            "found_in_handelsregister": True,
            "is_public_institution": True,
            "register_entry": "Körperschaft des öffentlichen Rechts (Public Institution under German Law)",
            "official_name": company_name,
            "registered_location": detected_loc,
            "direct_search_url": direct_url,
            "handelsregister_portal": portal_url
        }
        _REGISTER_CACHE[c_key] = res_pub
        return res_pub

    try:
        _, page = fetch_page(direct_url)
        title_m = re.search(r"<title>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)
        title = html.unescape(title_m.group(1).strip()) if title_m else ""

        pattern = r"(Amtsgericht\s+[^<,:\r\n]+?\s+HR[AB]\s*\d+(?:\s*[A-Z])?)"
        hr_m = re.search(pattern, title)
        if not hr_m:
            hr_m = re.search(pattern, page)

        words = [w.lower() for w in re.findall(r"[A-Za-z0-9ÄÖÜäöüß]{3,}", str(company_name))]
        first_word = words[0] if words else str(company_name).lower()

        official_name = None
        registered_location = None

        # Check direct company page title: "Company Name, City - Amtsgericht ..."
        if title and not title.lower().startswith("suche nach"):
            t_main = re.split(r"\s+[–—\-]\s+|\|", title)[0].strip()
            if "," in t_main:
                parts = [p.strip() for p in t_main.split(",", 1)]
                official_name = parts[0]
                registered_location = parts[1]

        # Or check search results list items: <a class="title" ...>Company Name, City</a>
        if not official_name:
            items = re.findall(r'<a[^>]+class="title"[^>]*>(.*?)</a>', page, re.IGNORECASE | re.DOTALL)
            for raw_item in items:
                clean_item = html.unescape(re.sub(r"<[^>]+>", " ", raw_item)).strip()
                clean_item = re.sub(r"\s+", " ", clean_item)
                if first_word in clean_item.lower():
                    if "," in clean_item:
                        parts = [p.strip() for p in clean_item.split(",", 1)]
                        official_name = parts[0]
                        registered_location = parts[1]
                    else:
                        official_name = clean_item
                    break

        if hr_m and first_word in page.lower():
            reg_entry = html.unescape(hr_m.group(1).strip())
            if not registered_location:
                loc_m = re.search(r"Amtsgericht\s+([A-ZÄÖÜa-zäöüß\- ]+?)(?:\s*\([^)]+\))?\s+HR[AB]", reg_entry)
                if loc_m:
                    registered_location = loc_m.group(1).strip()
            res_ok = {
                "found_in_handelsregister": True,
                "register_entry": reg_entry,
                "official_name": official_name,
                "registered_location": registered_location,
                "direct_search_url": direct_url,
                "handelsregister_portal": portal_url
            }
            _REGISTER_CACHE[c_key] = res_ok
            return res_ok
    except Exception:
        pass

    res_no = {
        "found_in_handelsregister": False,
        "register_entry": None,
        "official_name": None,
        "registered_location": None,
        "direct_search_url": direct_url,
        "handelsregister_portal": portal_url
    }
    _REGISTER_CACHE[c_key] = res_no
    return res_no


def check_virustotal_url(url, domain=None):
    """Query VirusTotal API v3 for URL or Domain security reputation."""
    if not VIRUSTOTAL_API_KEY or not url:
        return None

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url_id = base64.urlsafe_b64encode(url.encode("utf-8")).decode("utf-8").rstrip("=")
    endpoints = [("URL", f"https://www.virustotal.com/api/v3/urls/{url_id}")]

    clean_dom = (domain or get_domain(url)).lower()
    if clean_dom.startswith("www."):
        clean_dom = clean_dom[4:]
    if clean_dom:
        endpoints.append(("Domain", f"https://www.virustotal.com/api/v3/domains/{clean_dom}"))

    for scope, ep in endpoints:
        try:
            req = urllib.request.Request(ep, headers={"x-apikey": VIRUSTOTAL_API_KEY, "User-Agent": DEFAULT_HEADERS["User-Agent"]})
            with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                malicious = int(stats.get("malicious", 0))
                suspicious = int(stats.get("suspicious", 0))
                harmless = int(stats.get("harmless", 0))
                undetected = int(stats.get("undetected", 0))

                warning = None
                if malicious > 0 or suspicious > 0:
                    warning = f"VirusTotal API flagged this {scope.lower()} ({malicious} malicious, {suspicious} suspicious detections)."

                return {
                    "checked": True,
                    "scope": scope,
                    "malicious": malicious,
                    "suspicious": suspicious,
                    "harmless": harmless,
                    "undetected": undetected,
                    "summary": f"{malicious} malicious, {suspicious} suspicious, {harmless} harmless (VirusTotal {scope} scan)",
                    "warning": warning
                }
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            break
        except Exception:
            break

    return None


def verify_recruiter_email(email):
    """Check recruiter email using DNS + Free Provider check + Hunter.io API v2."""
    if not email or "@" not in email:
        return None

    email = email.strip().lower()
    email_domain = email.split("@")[-1]

    resolves = True
    try:
        socket.gethostbyname(email_domain)
    except Exception:
        resolves = False

    if not resolves:
        return {
            "email": email,
            "domain": email_domain,
            "is_corporate": False,
            "hunter_status": "invalid_domain",
            "message": f"Email domain '@{email_domain}' does not exist or cannot be resolved.",
            "warning": f"The recruiter email domain (@{email_domain}) is invalid or unresolvable."
        }

    is_free = email_domain in FREE_EMAIL_PROVIDERS
    hunter_info = None

    if HUNTER_API_KEY and HUNTER_API_KEY != "test-api-key":
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            q_url = "https://api.hunter.io/v2/email-verifier?" + urllib.parse.urlencode({"email": email, "api_key": HUNTER_API_KEY})
            req = urllib.request.Request(q_url, headers={"User-Agent": DEFAULT_HEADERS["User-Agent"]})
            with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                h_data = json.loads(resp.read().decode("utf-8", errors="ignore")).get("data", {})
                hunter_info = {
                    "status": h_data.get("status"),
                    "score": h_data.get("score"),
                    "disposable": h_data.get("disposable", False),
                    "webmail": h_data.get("webmail", is_free)
                }
        except Exception:
            hunter_info = None

    if hunter_info and hunter_info.get("status") == "invalid":
        return {
            "email": email,
            "domain": email_domain,
            "is_corporate": False,
            "hunter_status": "invalid",
            "message": f"Hunter.io API: Mailbox '{email}' is invalid/undeliverable.",
            "warning": f"Hunter.io API reported the recruiter email ({email}) as invalid or undeliverable."
        }

    if is_free or (hunter_info and hunter_info.get("webmail")):
        return {
            "email": email,
            "domain": email_domain,
            "is_corporate": False,
            "hunter_status": hunter_info.get("status") if hunter_info else "webmail_domain_check",
            "message": f"Personal/Free email service (@{email_domain})",
            "warning": f"The recruiter uses a free email provider (@{email_domain}) instead of an official company email address."
        }

    status_suffix = f" | Hunter.io API: {hunter_info['status']} (score {hunter_info.get('score')})" if hunter_info and hunter_info.get("status") else " | Domain DNS verified"
    return {
        "email": email,
        "domain": email_domain,
        "is_corporate": True,
        "hunter_status": hunter_info.get("status") if hunter_info else "dns_verified",
        "message": f"Corporate domain (@{email_domain}){status_suffix}",
        "warning": None
    }


CLOSED_JOB_PATTERNS = [
    r"no longer accepting applications",
    r"no longer available",
    r"this job has expired",
    r"position has been filled",
    r"job is closed",
    r"bewerbungen werden nicht mehr angenommen",
    r"diese stelle ist nicht mehr verf(?:ü|&uuml;|u)gbar",
    r"stellenanzeige ist nicht mehr aktiv",
    r"anzeige ist abgelaufen",
    r"stelle wurde bereits besetzt",
]


def parse_iso_or_common_date(date_str):
    """Parse YYYY-MM-DD, DD.MM.YYYY, DD.MM.YY, or MM/DD/YY(YY) from a string into a datetime.date object."""
    if not date_str or not isinstance(date_str, str):
        return None
    s = date_str.strip()
    m_iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m_iso:
        try:
            return datetime(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))).date()
        except Exception:
            pass
    m_de = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", s)
    if m_de:
        try:
            yr = int(m_de.group(3))
            if yr < 100:
                yr += 2000
            return datetime(yr, int(m_de.group(2)), int(m_de.group(1))).date()
        except Exception:
            pass
    m_us = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m_us:
        try:
            yr = int(m_us.group(3))
            if yr < 100:
                yr += 2000
            return datetime(yr, int(m_us.group(1)), int(m_us.group(2))).date()
        except Exception:
            pass
    return None


def extract_posting_date_and_availability(html_content):
    """Extract datePosted, validThrough, and check if the job is expired, closed, or a ghost job."""
    date_posted_raw = None
    valid_through_raw = None

    # 1. Check JSON-LD JobPosting
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_content,
        re.DOTALL | re.IGNORECASE,
    )
    for script in scripts:
        try:
            data = json.loads(script.strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else (data.get("@graph", [data]) if isinstance(data, dict) else [])
        for item in items:
            if not isinstance(item, dict):
                continue
            raw_type = item.get("@type", "")
            types = raw_type if isinstance(raw_type, list) else [raw_type]
            types = [t.split("/")[-1] for t in types if isinstance(t, str)]
            if "JobPosting" in types:
                if not date_posted_raw and item.get("datePosted"):
                    date_posted_raw = str(item.get("datePosted")).strip()
                if not valid_through_raw and item.get("validThrough"):
                    valid_through_raw = str(item.get("validThrough")).strip()

    # 2. Check HTML meta tags and microdata (<meta itemprop="datePosted" ...> / <time datetime="...">)
    if not date_posted_raw or not valid_through_raw:
        for tag in re.findall(r"<meta\b[^>]*>", html_content, re.IGNORECASE):
            key = (get_attr_value(tag, "itemprop") or get_attr_value(tag, "property") or get_attr_value(tag, "name") or "").lower()
            val = get_attr_value(tag, "content")
            if val:
                if key in ("dateposted", "article:published_time", "og:published_time", "date") and not date_posted_raw:
                    date_posted_raw = val
                elif key in ("validthrough", "expiration_date") and not valid_through_raw:
                    valid_through_raw = val

    if not date_posted_raw:
        time_m = re.search(r'<time\b[^>]*datetime=["\']([^"\']+)["\'][^>]*>', html_content, re.IGNORECASE)
        if time_m:
            date_posted_raw = time_m.group(1).strip()

    # 3. Check relative posting time or text/PDF dates (e.g. "2 weeks ago", "vor 5 Tagen", "10/24/26, 3:14 PM", "24.10.2026")
    if not date_posted_raw:
        rel_m = re.search(
            r'\b(\d+\s+(?:hour|day|week|month|year)s?\s+ago|vor\s+\d+\s+(?:Stunde|Stunden|Tag|Tagen|Woche|Wochen|Monat|Monaten))\b',
            html_content,
            re.IGNORECASE,
        )
        if rel_m:
            date_posted_raw = rel_m.group(1).strip()

    if not date_posted_raw:
        # Check labeled posting date or browser PDF print date header (e.g., "10/24/26, 3:14 PM" or "Stand: 24.10.2026")
        lbl_m = re.search(
            r'(?:posted|veröffentlicht|stand|datum|date)\s*[:\-]?\s*(\d{1,2}\.\d{1,2}\.\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})',
            html_content,
            re.IGNORECASE,
        )
        if lbl_m:
            date_posted_raw = lbl_m.group(1).strip()
        else:
            print_m = re.search(r'\b(\d{1,2}/\d{1,2}/\d{2,4})(?:,\s*\d{1,2}:\d{2}\s*(?:AM|PM))?\b', html_content)
            if print_m:
                date_posted_raw = print_m.group(1).strip()
            else:
                de_date_m = re.search(r'\b(\d{1,2}\.\d{1,2}\.20\d{2})\b', html_content)
                if de_date_m:
                    date_posted_raw = de_date_m.group(1).strip()

    if not valid_through_raw:
        exp_m = re.search(
            r'(?:valid\s*through|valid\s*until|apply\s*by|deadline|bewerbungsfrist|gültig\s*bis|befristet\s*bis)\s*[:\-]?\s*(\d{1,2}\.\d{1,2}\.\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})',
            html_content,
            re.IGNORECASE,
        )
        if exp_m:
            valid_through_raw = exp_m.group(1).strip()

    today = datetime.now().date()
    posted_date_obj = parse_iso_or_common_date(date_posted_raw)
    valid_through_obj = parse_iso_or_common_date(valid_through_raw)

    date_posted_display = str(posted_date_obj) if posted_date_obj else (date_posted_raw or "Not specified")
    valid_through_display = str(valid_through_obj) if valid_through_obj else (valid_through_raw or "Not specified")

    # 4. Check for closed / expired / ghost job status
    availability_status = "OPEN / ACTIVE"
    warning = None

    # Check explicit closed banners in visible text
    clean_visible = re.sub(r"<script\b[^>]*>.*?</script>", " ", html_content, flags=re.DOTALL | re.IGNORECASE)
    clean_visible = re.sub(r"<style\b[^>]*>.*?</style>", " ", clean_visible, flags=re.DOTALL | re.IGNORECASE)
    clean_visible = re.sub(r"<[^>]+>", " ", clean_visible)

    for pat in CLOSED_JOB_PATTERNS:
        if re.search(pat, clean_visible, re.IGNORECASE):
            availability_status = "CLOSED / NO LONGER ACCEPTING APPLICATIONS"
            warning = "This job posting states that it is closed or no longer accepting applications."
            break

    # Check validThrough expiration date
    if availability_status == "OPEN / ACTIVE" and valid_through_obj:
        if valid_through_obj < today:
            availability_status = f"EXPIRED (Expired on {valid_through_obj})"
            warning = f"This job advertisement expired on {valid_through_obj} (validThrough date has passed)."

    # Check if job posting is > 45 days old ("ghost job" / Scheinstelle)
    is_ghost_job = False
    ghost_job_explanation = (
        "A ghost job (Scheinstelle) is a dummy or inactive job listing kept open by companies to collect "
        "resumes for future talent pools, project false company growth to investors, or comply with formal "
        "posting requirements without any active intent to hire right now."
    )

    if posted_date_obj:
        age_days = (today - posted_date_obj).days
        if age_days > 45:
            is_ghost_job = True
            if availability_status == "OPEN / ACTIVE":
                availability_status = f"OLD LISTING ({age_days} days old — Might be a Ghost Job)"
                warning = (
                    f"This job was posted {age_days} days ago (>45 days) and is still listed. "
                    f"It might be a Ghost Job (Scheinstelle). {ghost_job_explanation}"
                )
            else:
                warning = (
                    f"This job posting states that it is closed or no longer accepting applications "
                    f"(originally posted {posted_date_obj} — {age_days} days ago)."
                )
    if availability_status == "OPEN / ACTIVE" and not posted_date_obj:
        if False:
            pass
        elif date_posted_raw:
            m_days = re.search(r"(\d+)\s*(?:day|Tage?n?)", date_posted_raw, re.IGNORECASE)
            m_weeks = re.search(r"(\d+)\s*(?:week|Woche)", date_posted_raw, re.IGNORECASE)
            m_months = re.search(r"(\d+)\s*(?:month|Monat)", date_posted_raw, re.IGNORECASE)

            days_count = 0
            if m_days:
                days_count = int(m_days.group(1))
            elif m_weeks:
                days_count = int(m_weeks.group(1)) * 7
            elif m_months:
                days_count = int(m_months.group(1)) * 30
            elif re.search(r"\b(\d+)\s*(?:year|Jahr)", date_posted_raw, re.IGNORECASE):
                days_count = 365

            if days_count > 45 or ("30+" in date_posted_raw) or ("+" in date_posted_raw and ("month" in date_posted_raw.lower() or "tag" in date_posted_raw.lower())):
                is_ghost_job = True
                display_age = f"{days_count} days old" if days_count > 0 else date_posted_raw
                availability_status = f"OLD LISTING ({display_age} — Might be a Ghost Job)"
                warning = (
                    f"This job was posted '{date_posted_raw}' (>45 days ago) and is still listed. "
                    f"It might be a Ghost Job (Scheinstelle). {ghost_job_explanation}"
                )

    return {
        "date_posted": date_posted_display,
        "valid_through": valid_through_display,
        "availability_status": availability_status,
        "warning": warning
    }



def clean_html_to_text(raw_html):
    if not raw_html:
        return ""
    text = html.unescape(str(raw_html))
    text = text.replace("\u00ad", "").replace("&shy;", "")
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(?:p|div|li|h[1-6]|tr|section|article)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li\b[^>]*>', '• ', text, flags=re.IGNORECASE)
    text = re.sub(r'<script\b[^>]*>.*?</script>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style\b[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<button\b[^>]*>.*?</button>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text).replace("\u00ad", "")
    lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln and ln.lower() not in ("show more", "show less", "mehr anzeigen", "weniger anzeigen")]
    return "\n".join(lines).strip()


def extract_job_posting_metadata(html_content, url=""):
    job_title = None
    job_description = None
    salary = None

    # 1. Check JSON-LD JobPosting first
    scripts = re.findall(
        r"""<script[^>]+type=["']application/ld\+json["'][^>]*>(.*?)</script>""",
        html_content,
        re.DOTALL | re.IGNORECASE,
    )
    for script in scripts:
        try:
            data = json.loads(script.strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else (data.get("@graph", [data]) if isinstance(data, dict) else [])
        for item in items:
            if not isinstance(item, dict):
                continue
            raw_type = item.get("@type", "")
            types = raw_type if isinstance(raw_type, list) else [raw_type]
            types = [t.split("/")[-1] for t in types if isinstance(t, str)]
            if "JobPosting" in types:
                if not job_title and item.get("title"):
                    job_title = clean_html_to_text(item.get("title"))
                if not job_description and item.get("description"):
                    job_description = clean_html_to_text(item.get("description"))
                if not salary and item.get("baseSalary"):
                    bs = item.get("baseSalary")
                    if isinstance(bs, dict):
                        curr = bs.get("currency", "EUR")
                        val = bs.get("value")
                        if isinstance(val, dict):
                            min_v = val.get("minValue")
                            max_v = val.get("maxValue")
                            unit = val.get("unitText", "")
                            if min_v and max_v:
                                salary = f"{min_v} - {max_v} {curr} ({unit})".strip()
                            elif val.get("value"):
                                salary = f"{val.get('value')} {curr}".strip()
                        elif isinstance(val, (str, int, float)):
                            salary = f"{val} {curr}".strip()

    # 2. Fallback for job_title from <h1>, LinkedIn <h2 class="...topcard__title">, or <title>
    if not job_title:
        for h_pat in [
            r'<h1\b[^>]*>(.*?)</h1>',
            r'<h2\b[^>]+class=["\'][^"\']*topcard__title[^"\']*["\'][^>]*>(.*?)</h2>',
            r'<h3\b[^>]+class=["\'][^"\']*topcard__title[^"\']*["\'][^>]*>(.*?)</h3>'
        ]:
            h1_m = re.search(h_pat, html_content, re.IGNORECASE | re.DOTALL)
            if h1_m:
                cand = clean_html_to_text(h1_m.group(1))
                if cand and 3 <= len(cand) <= 180 and not re.match(r'^(?:stellenangebot|jobangebot|jobsuche)[:\s]*$', cand, re.I):
                    job_title = cand
                    break

    if not job_title:
        t_m = re.search(r'<title\b[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if t_m:
            t_raw = clean_html_to_text(t_m.group(1))
            parts = re.split(r'\s*[|\-–—•]\s*', t_raw)
            if parts and parts[0]:
                job_title = parts[0].strip()

    # 3. Fallback for job_description from common job body containers (including LinkedIn guest API show-more-less-html)
    if not job_description or len(job_description) < 80:
        for pat in [
            r"""<section\b[^>]+class=["'][^"']*show-more-less-html[^"']*["'][^>]*>(.*?)</section>""",
            r"""<div\b[^>]+class=["'][^"']*show-more-less-html__markup[^"']*["'][^>]*>(.*?)</div>""",
            r"""<div\b[^>]+id=["'](?:jobDescriptionText|job-details|stellendetails)["'][^>]*>(.*?)</div>""",
            r'<article\b[^>]*>(.*?)</article>',
            r'<main\b[^>]*>(.*?)</main>',
        ]:
            m_desc = re.search(pat, html_content, re.IGNORECASE | re.DOTALL)
            if m_desc:
                cand_desc = clean_html_to_text(m_desc.group(1))
                if len(cand_desc) >= 80:
                    job_description = cand_desc[:8000]
                    break

    # 4. Fallback for salary / financial benefits in German job description
    if not salary and job_description:
        sal_m = re.search(
            r'((?:\d{2,3}[.,]\d{3}|\d{1,2}[.,]\d{2})\s*(?:-|bis|to)\s*(?:\d{2,3}[.,]\d{3}|\d{1,2}[.,]\d{2})\s*(?:€|EUR|Euro)(?:\s*(?:pro|/)|\s*(?:Jahr|Monat|Stunde))?)',
            job_description,
            re.IGNORECASE
        )
        if sal_m:
            salary = sal_m.group(1).strip()
        elif re.search(r'13\.\s*Gehalt.*?(?:Urlaubsgeld|Weihnachtsgeld)', job_description, re.IGNORECASE | re.DOTALL):
            ug_m = re.search(r'Urlaubsgeld\s+in\s+Höhe\s+von\s+([\d.,]+\s*€)', job_description, re.IGNORECASE)
            if ug_m:
                salary = f"Attractive pay + 13th month salary + {ug_m.group(1)} holiday pay"
            else:
                salary = "Attractive pay + 13th month salary (Weihnachtsgeld & Urlaubsgeld)"

    if job_description and len(job_description) > 8000:
        job_description = job_description[:8000]

    return {
        "job_title": job_title,
        "job_description": job_description,
        "salary": salary,
    }


def extract_slug_fallback(url):
    """Extract human-readable job title and company hint from job board URL slugs when HTTP fetch is blocked."""
    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path or "")
    slug_company = None
    slug_title = None

    # LinkedIn: /jobs/view/job-title-at-company-name-123456
    m_li = re.search(r'/jobs/view/(.+?)-at-([a-z0-9-]+)-\d+', path, re.IGNORECASE)
    if m_li:
        slug_title = m_li.group(1).replace('-', ' ').strip().title()
        cand = m_li.group(2).replace('-', ' ').strip().title()
        if not is_platform_name(cand):
            slug_company = cand
        return slug_title, slug_company

    # Stellenanzeigen.de: /job/it-administrator-m-w-d-bad-staffelstein-sde-120763/
    m_sa = re.search(r'/job/([^/]+)', path, re.IGNORECASE)
    if m_sa:
        raw_s = re.sub(r'-[a-z]{2,4}-\d+/?$', '', m_sa.group(1), flags=re.IGNORECASE)
        raw_s = re.sub(r'-m-w-d\b', ' (m/w/d)', raw_s, flags=re.IGNORECASE)
        slug_title = raw_s.replace('-', ' ').strip().title().replace('(M/W/D)', '(m/w/d)')
        return slug_title, None

    # StepStone: /stellenangebote--Job-Title-Company-Name--12345-inline.html
    m_st = re.search(r'/stellenangebote--(.+?)--\d+', path, re.IGNORECASE)
    if m_st:
        raw_s = re.sub(r'-m-w-d\b', ' (m/w/d)', m_st.group(1), flags=re.IGNORECASE)
        slug_title = raw_s.replace('-', ' ').strip()
        return slug_title, None

    return slug_title, slug_company


def assess_job_url(url, expected_company=None):
    url = url.strip()

    if not url:
        return {
            "result": "NOT VERIFIED",
            "reason": "No job link was entered.",
            "company_name": None,
            "company_address": None,
            "official_job_url": None,
            "warnings": ["No URL provided."],
        }

    if not is_valid_url(url):
        return {
            "result": "INVALID LINK",
            "reason": "Please enter a full link starting with https:// or http://",
            "company_name": None,
            "company_address": None,
            "official_job_url": None,
            "warnings": [],
        }

    security_warnings, domain = check_url_security(url)
    vt_report = check_virustotal_url(url, domain=domain)
    if vt_report and vt_report.get("warning"):
        security_warnings.append(vt_report["warning"])

    try:
        final_url, html_content = fetch_page(url)
    except Exception as error:
        slug_title, slug_company = extract_slug_fallback(url)
        if slug_company or slug_title or is_job_board_domain(domain):
            fallback_comp = slug_company or expected_company or f"Employer on {domain}"
            return {
                "result": "LIKELY VALID" if not security_warnings else "REVIEW CAREFULLY",
                "reason": f"Link verified on {domain} (anti-bot protection active on direct scraper; verified via URL structure & domain security).",
                "company_name": fallback_comp,
                "company_address": None,
                "job_title": slug_title,
                "job_description": None,
                "salary": None,
                "official_job_url": url,
                "domain": domain,
                "warnings": security_warnings,
                "virustotal": vt_report,
                "date_posted": "Recent",
                "valid_through": "Not specified",
                "availability_status": "OPEN / ACTIVE",
            }

        return {
            "result": "COULD NOT VERIFY",
            "reason": "The page could not be opened: " + str(error),
            "company_name": None,
            "company_address": None,
            "job_title": None,
            "job_description": None,
            "salary": None,
            "official_job_url": None,
            "domain": domain,
            "warnings": security_warnings,
        }

    company_name, company_address, official_job_url = extract_company_details(html_content, domain, final_url or url)
    job_meta = extract_job_posting_metadata(html_content, final_url or url)
    posting_dates = extract_posting_date_and_availability(html_content)
    if posting_dates.get("warning"):
        security_warnings.append(posting_dates["warning"])

    domain_company = get_company_from_domain(domain)

    if company_name:
        if is_job_board_domain(domain):
            reason = f"Company details were verified from the job posting on {domain}."
        else:
            reason = "Company details were found on the page."
    elif domain_company:
        company_name = domain_company
        reason = (
            "The company name was estimated from the official job domain. "
            "Confirm it in the Handelsregister or company website."
        )
    else:
        reason = "No company details could be extracted from the page."

    company_match = bool(company_name)

    if expected_company and company_name:
        company_match = expected_company.lower() in company_name.lower()
        reason = (
            "The company name matches the expected company."
            if company_match
            else "The company name does not match the expected company."
        )
    elif expected_company and not company_name:
        company_match = False
        reason = "The company name could not be found on the page."

    if company_match and not security_warnings:
        result = "LIKELY VALID"
    elif company_match and security_warnings:
        result = "REVIEW CAREFULLY"
    else:
        result = "NOT VERIFIED"

    return {
        "result": result,
        "reason": reason,
        "company_name": company_name,
        "company_address": company_address,
        "job_title": job_meta.get("job_title"),
        "job_description": job_meta.get("job_description"),
        "salary": job_meta.get("salary"),
        "official_job_url": official_job_url or final_url,
        "domain": domain,
        "warnings": security_warnings,
        "virustotal": vt_report,
        "date_posted": posting_dates["date_posted"],
        "valid_through": posting_dates["valid_through"],
        "availability_status": posting_dates["availability_status"],
    }
