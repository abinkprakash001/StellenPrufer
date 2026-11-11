# Extract text from PDF/TXT resumes and employment contracts

import io
import os
import re

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

_ocr_engine = None


def get_ocr_engine():
    """Lazy-load RapidOCR engine so server startup stays fast."""
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr_engine = RapidOCR()
        except Exception:
            _ocr_engine = False
    return _ocr_engine if _ocr_engine is not False else None


def extract_text_from_file(file_bytes, filename):
    """Extract text from a PDF, image screenshot (PNG/JPG/WEBP/BMP), or text file."""
    if not file_bytes:
        return {"text": "", "method": "none", "error": "Empty file uploaded."}

    ext = os.path.splitext(filename or "")[1].lower()

    # 1. PDF Document
    if ext == ".pdf" or file_bytes[:4] == b"%PDF":
        if PdfReader is None:
            return {"text": "", "method": "pdf", "error": "PDF library (pypdf) is not installed."}
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            pages_text = []
            for page in reader.pages:
                page_txt = page.extract_text() or ""
                if page_txt.strip():
                    pages_text.append(page_txt.strip())

            combined_text = "\n\n".join(pages_text).strip()

            # Fallback: if PDF is a scanned image with almost no selectable text, run OCR on embedded images
            if len(combined_text) < 30:
                ocr = get_ocr_engine()
                ocr_lines = []
                if ocr:
                    for page in reader.pages:
                        for image_file_object in getattr(page, "images", []):
                            try:
                                result, _ = ocr(image_file_object.data)
                                if result:
                                    ocr_lines.extend([line[1] for line in result if len(line) > 1])
                            except Exception:
                                continue
                if ocr_lines:
                    combined_text = "\n".join(ocr_lines).strip()
                    return {
                        "text": combined_text,
                        "method": "Scanned PDF (OCR)",
                        "pages": len(reader.pages),
                        "error": None
                    }

            return {
                "text": combined_text,
                "method": f"PDF Text Extraction ({len(reader.pages)} page(s))",
                "pages": len(reader.pages),
                "error": None if combined_text else "No readable text found in PDF."
            }
        except Exception as e:
            return {"text": "", "method": "PDF", "error": f"Failed to read PDF: {e}"}

    # 2. Image Screenshot (WhatsApp / Email / Offer Screenshot)
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        ocr = get_ocr_engine()
        if not ocr:
            return {"text": "", "method": "OCR", "error": "OCR engine (rapidocr-onnxruntime) is not available."}
        try:
            result, _ = ocr(file_bytes)
            if not result:
                return {"text": "", "method": "Image OCR", "error": "No readable text detected in the image."}
            extracted_lines = [item[1] for item in result if len(item) > 1]
            text = "\n".join(extracted_lines).strip()
            return {
                "text": text,
                "method": "Image Screenshot OCR (RapidOCR)",
                "error": None
            }
        except Exception as e:
            return {"text": "", "method": "Image OCR", "error": f"OCR processing error: {e}"}

    # 3. Plain Text File
    if ext in (".txt", ".csv", ".md"):
        try:
            text = file_bytes.decode("utf-8", errors="replace").strip()
            return {"text": text, "method": "Text File", "error": None}
        except Exception as e:
            return {"text": "", "method": "Text File", "error": str(e)}

    return {
        "text": "",
        "method": "Unsupported",
        "error": f"Unsupported file format '{ext}'. Please upload a PDF or image screenshot (PNG, JPG, WEBP)."
    }


def extract_entities_from_text(text, filename=None):
    """Automatically detect company name, address/location, email addresses, and URLs inside extracted document text."""
    if not text and not filename:
        return {"company_name": None, "company_address": None, "emails": [], "urls": [], "truncated_urls": []}

    text = text or ""

    # 1. Extract emails
    emails = list(dict.fromkeys(
        re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    ))

    # 2. Extract URLs (separate complete URLs from browser print-to-PDF truncated footer URLs ending in '…' or '...')
    raw_urls = list(dict.fromkeys(
        re.findall(r"https?://[^\s<>\"')]+", text)
    ))
    valid_urls = []
    truncated_urls = []
    for u in raw_urls:
        u_clean = u.rstrip(".,;:!?)")
        if "\u2026" in u_clean or u_clean.endswith("..."):
            u_stripped = u_clean.split("\u2026")[0].rstrip(".")
            if u_stripped.startswith("http"):
                truncated_urls.append(u_stripped)
        else:
            valid_urls.append(u_clean)

    # 3. Extract Company Name & Address from filename if browser-printed PDF (e.g., "Title _ Job in City _ Company.pdf")
    company_name = None
    company_address = None

    if filename:
        base_name = os.path.splitext(os.path.basename(filename))[0]
        parts = [p.strip() for p in re.split(r"\s+(?:_|\||—|–)\s+", base_name) if p.strip()]
        if len(parts) >= 2:
            last_part = parts[-1]
            if not re.search(r"\b(job|jobs|linkedin|stepstone|indeed|xing|karriere|careers)\b", last_part, re.I):
                company_name = last_part
            for part in parts:
                loc_m = re.search(r"\b(?:Job\s+in|in|Standort)\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-\s]{2,35})$", part)
                if loc_m:
                    company_address = loc_m.group(1).strip()

    # 4. Extract Company Name from text
    if not company_name:
        company_patterns = [
            # German Sparkassen, Volksbanken, Landesbanken, Universities, Public Institutions
            r"\b((?:Kreissparkasse|Stadtsparkasse|Sparkasse|Volksbank|Raiffeisenbank|Landesbank|Commerzbank|Deutsche\s+Bahn|Universität|Hochschule|Klinikum)\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+){0,2})\b",
            # Explicit prefix + Legal suffix
            r"(?:zwischen(?:\s+der)?|between|from|von|bei|at|Employer|Arbeitgeber|Company|Firma)\s*[:\-]?\s*([A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9&\-\. ]{1,40}?\s+(?:GmbH\s*&\s*Co\.\s*KG|GmbH|AG|SE|UG\s*\(haftungsbeschränkt\)|UG|KG|OHG|e\.V\.|eG|AöR|KdöR|Ltd\.?|Inc\.?|Corp\.?|S\.A\.|B\.V\.))\b",
            # Standard legal entity suffix
            r"\b([A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9&\-\.]{1,30}(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9&\-\.]{1,30}){0,3}\s+(?:GmbH\s*&\s*Co\.\s*KG|GmbH|AG|SE|UG\s*\(haftungsbeschränkt\)|UG|KG|OHG|e\.V\.|eG|AöR|KdöR|Ltd\.?|Inc\.?|Corp\.?|S\.A\.|B\.V\.))\b",
        ]
        for pattern in company_patterns:
            match = re.search(pattern, text)
            if match:
                candidate = re.sub(r"\s+", " ", match.group(1)).strip(" ,.-:\n\r")
                candidate = re.sub(
                    r"^(?:Arbeitsvertrag|Job\s+Offer|Offer\s+Letter|Stellenangebot|WhatsApp|Services)\s+(?:zwischen|from|von|bei|at)?\s*",
                    "",
                    candidate,
                    flags=re.I
                ).strip()
                # Trim trailing words that belong to the next sentence/heading
                candidate = re.split(r"\s+(?:Product|Full-time|Part-time|Vollzeit|Teilzeit|We\s+are|Wir\s+sind|m/f/d|m/w/d)\b", candidate)[0].strip()
                if 3 <= len(candidate) <= 65:
                    company_name = candidate
                    break

    # 5. Extract Address / Location from text if not yet found
    if not company_address:
        addr_patterns = [
            # Street + German 5-digit postcode + City
            r"\b([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-\. ]+(?:straße|str\.|platz|weg|allee)\s*\d+[a-zA-Z]?\s*,\s*\d{5}\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\- ]+)\b",
            # German 5-digit postcode + City
            r"\b(\d{5}\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]{2,30}(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]{2,25})?)\b",
            # "at our <City> location" or "Standort <City>"
            r"(?:at\s+our\s+|Standort\s+|location\s+in\s+)([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]{2,30}(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]{2,30})?)(?:\s+location|\b)",
        ]
        for pat in addr_patterns:
            m = re.search(pat, text)
            if m:
                company_address = re.sub(r"\s+", " ", m.group(1)).strip(" ,.-")
                break

    return {
        "company_name": company_name,
        "company_address": company_address,
        "emails": emails,
        "urls": valid_urls,
        "truncated_urls": truncated_urls
    }


# Mandatory clauses for an employment contract (German Nachweisgesetz - NachwG & standard practice)
CONTRACT_MANDATORY_CLAUSES = [
    (
        "Parties & Employer Address (Vertragsparteien & Anschrift)",
        r"\b(zwischen|between|arbeitgeber|employer|anschrift|adresse|address|straße|str\.|platz|weg|gmbh|ag)\b"
    ),
    (
        "Start Date / Term of Employment (Beginn & Dauer)",
        r"\b(beginn|start date|commencement|eintrittsdatum|ab dem|tritt am|arbeitsverhältnis beginnt|effective from)\b"
    ),
    (
        "Job Title & Duties (Tätigkeit & Aufgaben)",
        r"\b(tätigkeit|position|job title|als|aufgaben|duties|role|beschäftigt als|employed as|stellenbeschreibung)\b"
    ),
    (
        "Salary & Remuneration (Vergütung / Arbeitsentgelt)",
        r"\b(vergütung|gehalt|salary|remuneration|lohn|brutto|gross|euro|eur|€|\$|monatlich|monthly|stunde|hourly)\b"
    ),
    (
        "Working Hours (Arbeitszeit)",
        r"\b(arbeitszeit|working hours|wochenstunden|hours per week|stundenzahl|vollzeit|teilzeit|full-time|part-time)\b"
    ),
    (
        "Vacation Entitlement (Urlaubsanspruch)",
        r"\b(urlaub|urlaubsanspruch|vacation|annual leave|arbeitstage|urlaubstage|paid leave|holiday entitlement)\b"
    ),
    (
        "Notice Periods & Termination (Kündigungsfristen)",
        r"\b(kündigung|kuendigung|kündigungsfrist|kuendigungsfrist|termination|notice period|probezeit|probation|beendigung|schriftform)\b"
    ),
]

# Red flags specific to fake or unlawful employment contracts
CONTRACT_SCAM_RED_FLAGS = [
    (
        r"\b(security deposit|kaution für arbeitsmittel|training fee|schulungsgebühr|visa fee|bearbeitungsgebühr|application fee|background check fee|equipment fee)\b",
        "CRITICAL CONTRACT RED FLAG: The contract demands an upfront fee, deposit, or payment from the employee. Legitimate employers never charge fees to sign a contract."
    ),
    (
        r"\b(private bank account|privates bankkonto|forward funds|weiterleiten von geldern|payment processing agent|finanzagent|cryptocurrency|bitcoin|usdt|western union)\b",
        "CRITICAL CONTRACT RED FLAG: Contract mentions using personal bank accounts or cryptocurrency for transferring money (classic 'Money Mule' / Finanzagent crime)."
    ),
    (
        r"\b(probezeit|probation(?:ary)? period)\b[^.\n]{0,50}\b([7-9]|1[0-2])\s*(monate|months)\b",
        "LEGAL WARNING (§ 622 Abs. 3 BGB): The contract specifies a probation period (Probezeit) longer than 6 months, which exceeds the statutory maximum under German labor law."
    ),
    (
        r"\b(whatsapp|telegram)\b",
        "CONTRACT WARNING: Official employment contracts do not conduct onboarding or contract administration exclusively over WhatsApp or Telegram."
    ),
    (
        r"\b(online banking|pin|tan|passwort|password|credit card details)\b",
        "CRITICAL CONTRACT RED FLAG: The document asks for banking credentials, PINs, TANs, or credit card details."
    ),
]


def analyze_job_contract(text):
    """Analyze text as an Employment Contract (Arbeitsvertrag).
    Checks mandatory clauses under German Nachweisgesetz (NachwG) and detects contract scam red flags.
    """
    if not text or len(text.strip()) < 20:
        return {
            "is_contract": True,
            "clauses_present": [],
            "clauses_missing": [name for name, _ in CONTRACT_MANDATORY_CLAUSES],
            "clause_score": f"0/{len(CONTRACT_MANDATORY_CLAUSES)} mandatory clauses found",
            "red_flags": ["Document text is too short or empty to be a valid employment contract."],
            "contract_verdict": "INVALID / UNREADABLE CONTRACT"
        }

    text_lower = text.lower()
    clauses_present = []
    clauses_missing = []

    for clause_name, pattern in CONTRACT_MANDATORY_CLAUSES:
        if re.search(pattern, text_lower):
            clauses_present.append(clause_name)
        else:
            clauses_missing.append(clause_name)

    red_flags = []
    for pattern, warning_msg in CONTRACT_SCAM_RED_FLAGS:
        if re.search(pattern, text_lower):
            red_flags.append(warning_msg)

    # Check if critical clauses are missing
    total = len(CONTRACT_MANDATORY_CLAUSES)
    found_count = len(clauses_present)
    clause_score = f"{found_count}/{total} mandatory clauses found (German NachwG standard)"

    if clauses_missing:
        missing_str = ", ".join(clauses_missing)
        red_flags.append(
            f"Missing standard employment contract clauses: {missing_str}."
        )

    if any("CRITICAL" in rf for rf in red_flags):
        verdict = "HIGH RISK / FRAUDULENT CONTRACT"
    elif found_count >= 6 and not any("LEGAL WARNING" in rf or "CONTRACT WARNING" in rf for rf in red_flags):
        verdict = "COMPLETE CONTRACT STRUCTURE"
    elif found_count >= 4:
        verdict = "INCOMPLETE / REVIEW CAREFULLY"
    else:
        verdict = "MISSING ESSENTIAL CONTRACT CLAUSES"

    return {
        "is_contract": True,
        "clauses_present": clauses_present,
        "clauses_missing": clauses_missing,
        "clause_score": clause_score,
        "red_flags": red_flags,
        "contract_verdict": verdict
    }
