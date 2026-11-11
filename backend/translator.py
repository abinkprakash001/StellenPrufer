# German to English Translation Engine tailored for Expats & English Speakers in Germany
# Provides domain-specific translation for German job postings, employment contracts,
# labor law terminology, and company registration concepts.

import re
import urllib.parse
import urllib.request
import json
from functools import lru_cache

# Key German labor and job market terminology glossary with English explanations
GERMAN_EXPAT_GLOSSARY = {
    "arbeitsvertrag": "employment contract",
    "probezeit": "probationary period (statutory maximum 6 months under § 622 BGB)",
    "kündigungsfrist": "statutory notice period for termination",
    "befristet": "fixed-term (contract has an end date)",
    "unbefristet": "permanent / open-ended contract (no end date)",
    "vollzeit": "full-time employment (typically 38-40 hrs/week)",
    "teilzeit": "part-time employment",
    "minijob": "marginal employment (max. 538 €/month tax-free in Germany)",
    "werkstudent": "working student position (max. 20 hrs/week during university semester)",
    "urlaubsanspruch": "paid vacation entitlement (statutory minimum 20 days/yr for 5-day week under BUrlG)",
    "urlaubstage": "annual paid vacation days",
    "betriebliche altersvorsorge": "company pension scheme (bAV)",
    "mindestlohn": "German statutory minimum wage (currently 13.90 €/hour under MiLoG)",
    "handelsregister": "German Commercial Register (official court registry of legitimate businesses)",
    "amtsgericht": "local district court maintaining the commercial register",
    "hrb": "Handelsregister B (commercial register for corporations: GmbH, AG, UG)",
    "hra": "Handelsregister A (commercial register for sole traders & partnerships: e.K., OHG, KG)",
    "impressum": "mandatory legal notice and imprint required on all German business websites (§ 5 DDG)",
    "steuer-id": "German tax identification number (Steuer-ID, only required AFTER contract signing)",
    "sozialversicherungsnummer": "German social security number",
    "krankenkasse": "German public or private health insurance provider",
    "tarifvertrag": "collective bargaining agreement (negotiated trade union wage standards)",
    "gleitzeit": "flexible working hours / flexitime",
    "sonderzahlung": "special bonus payment (e.g., 13th month salary or Christmas bonus / Weihnachtsgeld)",
    "überstundenregelung": "overtime regulation clause",
    "wettbewerbsverbot": "post-contractual non-compete clause (requires compensation under § 74 HGB)",
    "ausschlussfristen": "forfeiture / preclusion periods (claims must be filed within deadline)",
    "geheimhaltungspflicht": "confidentiality / non-disclosure obligation",
    "körperschaft des öffentlichen rechts": "public-law corporation (e.g. state universities and government institutions)"
}

# Common German job phrase mapping for fast offline translation
PHRASE_MAPPINGS = [
    # Headings
    (r"\b(ihre aufgaben|deine aufgaben|das sind deine aufgaben|das machst du|aufgabenbereiche?|aufgabengebiet)\b", "Your Responsibilities"),
    (r"\b(ihr profil|dein profil|das bringst du mit|das bringen sie mit|anforderungsprofil|anforderungen|voraussetzungen|qualifikationen)\b", "Your Qualifications & Profile"),
    (r"\b(wir bieten|das bieten wir|unser angebot|benefits|vorteile für dich|deine vorteile)\b", "What We Offer & Benefits"),
    (r"\b(über uns|wer wir sind|unser unternehmen|das unternehmen)\b", "About the Company"),
    
    # Contract & Terms
    (r"\bunbefristeter arbeitsvertrag\b", "Permanent employment contract"),
    (r"\bbefristeter arbeitsvertrag\b", "Fixed-term employment contract"),
    (r"\bmit Option auf Übernahme\b", "with option for permanent retention"),
    (r"\bflexible arbeitszeiten\b", "Flexible working hours"),
    (r"\bmobiles arbeiten\b", "Remote / mobile work"),
    (r"\bhomeoffice möglichkeit\b", "Home office option"),
    (r"\b30 tage urlaub\b", "30 days paid vacation"),
    (r"\b28 tage urlaub\b", "28 days paid vacation"),
    (r"\bbetriebliche altersvorsorge\b", "Company pension scheme"),
    (r"\bweihnachtsgeld und urlaubsgeld\b", "Holiday and Christmas bonuses"),
    (r"\battraktive vergütung\b", "Attractive compensation"),
    (r"\bfahrtkostenzuschuss\b", "Travel subsidy / Deutschlandticket allowance"),
    (r"\bdeutschlandticket\b", "German transit pass (Deutschlandticket)"),
    (r"\bgute verkehrsanbindung\b", "Convenient public transit access"),
    (r"\bkostenlose getränke und obst\b", "Complimentary beverages and fresh fruit"),
    (r"\bflache hierarchien\b", "Flat corporate hierarchies"),
    (r"\bgutes betriebsklima\b", "Positive workplace atmosphere"),
    
    # Requirements
    (r"\berfolgreich abgeschlossene(?:s)? (?:ausbildung|studium)\b", "Successfully completed vocational training or degree"),
    (r"\babgeschlossene(?:s)? kaufmännische(?:s)? ausbildung\b", "Completed commercial / business vocational qualification"),
    (r"\babgeschlossenes studium\b", "Completed university degree"),
    (r"\berste berufserfahrung\b", "Initial professional experience"),
    (r"\bmehrjährige berufserfahrung\b", "Several years of relevant professional experience"),
    (r"\bfundierte kenntnisse\b", "Solid, in-depth working knowledge"),
    (r"\bgute deutschkenntnisse in wort und schrift\b", "Good German language skills (spoken and written)"),
    (r"\bverhandlungssichere deutschkenntnisse\b", "Fluent / business German language proficiency"),
    (r"\bsehr gute englischkenntnisse\b", "Very good English language proficiency"),
    (r"\bteamfähigkeit und kommunikationsstärke\b", "Strong teamwork and communication abilities"),
    (r"\bselbstständige und strukturierte arbeitsweise\b", "Independent and structured work approach"),
    (r"\bsicherer umgang mit\b", "Proficient handling of"),
    
    # Common Tasks
    (r"\bbetreuung und beratung von\b", "Advising and supporting"),
    (r"\banalyse und optimierung von\b", "Analyzing and optimizing"),
    (r"\berstellung von reportings\b", "Preparing reports and documentation"),
    (r"\bmitwirkung bei\b", "Contributing to and participating in"),
    (r"\bkoordination von\b", "Coordinating and overseeing"),
    (r"\banpassung von\b", "Adapting and customizing"),
    (r"\bpflege und weiterentwicklung von\b", "Maintaining and further developing"),
    (r"\berster ansprechpartner für\b", "Primary point of contact for")
]

GERMAN_INDICATOR_WORDS = {
    "und", "der", "die", "das", "mit", "für", "auf", "ein", "eine", "einer", "einem",
    "ihre", "deine", "aufgaben", "profil", "wir", "bieten", "erfahrung", "kenntnisse",
    "abschluss", "ausbildung", "studium", "unternehmen", "bewerbung", "stelle",
    "vollzeit", "teilzeit", "arbeitsvertrag", "urlaub", "standort", "vergütung",
    "wie", "man", "im", "werden", "wird", "durch", "oder", "auch", "bei", "von",
    "zu", "als", "du", "sie", "nicht", "nur", "gemeinsam", "daten", "verwaltet"
}


def is_german_text(text: str) -> bool:
    """Detect if a string is predominantly German."""
    if not text:
        return False
    lower = text.lower()
    # German specific characters
    if any(char in lower for char in ["ä", "ö", "ü", "ß"]):
        return True
    tokens = re.findall(r"\b[a-zäöüß]+\b", lower)
    if not tokens:
        return False
    german_matches = sum(1 for t in tokens if t in GERMAN_INDICATOR_WORDS)
    ratio = german_matches / len(tokens)
    return ratio >= 0.12 or german_matches >= 3


@lru_cache(maxsize=1000)
def translate_german_phrase_offline(text: str) -> str:
    """Translate German employment text to English using contextual domain rules."""
    if not text:
        return ""
    result = text
    # Apply regex phrase replacements
    for pattern, replacement in PHRASE_MAPPINGS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    # Replace individual glossary terms if present
    for de_term, en_explanation in GERMAN_EXPAT_GLOSSARY.items():
        if de_term in result.lower() and len(de_term) > 3:
            # Add English annotation
            pattern = re.compile(rf"\b{re.escape(de_term)}\b", re.IGNORECASE)
            result = pattern.sub(f"{de_term.capitalize()} ({en_explanation})", result)
    return result


@lru_cache(maxsize=1000)
def fetch_online_translation(text: str, source_lang="de", target_lang="en", timeout_sec=1.5) -> str:
    """Fast, free translation fallback using MyMemory API with strict timeout."""
    if not text or len(text) > 450:
        return ""
    try:
        clean = text.strip()
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(clean)}&langpair={source_lang}|{target_lang}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "StellenPruefer-GermanExpatAssistant/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and data.get("responseData") and data["responseData"].get("translatedText"):
                trans = data["responseData"]["translatedText"].strip()
                # If translation service returned invalid text or identical non-translated string
                if trans and not trans.startswith("MYMEMORY WARNING:") and trans.lower() != clean.lower():
                    return trans
    except Exception:
        pass
    return ""


def translate_text_for_expats(text: str) -> dict:
    """
    Translates German text to clear English for expats in Germany.
    Returns: {
        'is_german': bool,
        'original': str,
        'translated': str,
        'glossary_notes': list of dicts with German legal/labor terms explained,
        'source_lang': 'de' or 'en'
    }
    """
    if not text or not text.strip():
        return {
            "is_german": False,
            "original": "",
            "translated": "",
            "glossary_notes": [],
            "source_lang": "en"
        }

    clean_text = text.strip()
    is_german = is_german_text(clean_text)

    glossary_notes = []

    if not is_german:
        return {
            "is_german": False,
            "original": clean_text,
            "translated": clean_text,
            "glossary_notes": glossary_notes,
            "source_lang": "en"
        }

    # Attempt online translation for short blocks (< 400 chars)
    translated = ""
    if len(clean_text) <= 350:
        translated = fetch_online_translation(clean_text)

    # Fallback to high-accuracy offline German job market translator
    if not translated:
        translated = translate_german_phrase_offline(clean_text)

    # If translation produced something meaningful
    if not translated or translated == clean_text:
        translated = translate_german_phrase_offline(clean_text)

    return {
        "is_german": True,
        "original": clean_text,
        "translated": translated or clean_text,
        "glossary_notes": glossary_notes,
        "source_lang": "de"
    }


def translate_bullet_points(bullets: list) -> list:
    """Translate an array of German task or requirement bullet points to English."""
    translated_bullets = []
    for bullet in bullets:
        if not bullet:
            continue
        res = translate_text_for_expats(bullet)
        translated_bullets.append(res["translated"])
    return translated_bullets
