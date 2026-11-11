# -*- coding: utf-8 -*-
"""German Market Salary Anomaly & Hourly Minimum Wage Detector (backend/salary_anomaly_detector.py)

Evaluates job offer compensation against German labor market benchmarks in Euros (€ / EUR).

Hourly Minimum Wage Rule:
- Only applied when an HOURLY wage is specified.
- If hourly compensation < 13.90 € / Stunde, it is flagged as a false job advertisement
  (is_scam_signal = True, verdict: ILLEGAL SUB-MINIMUM WAGE (FALSE JOB ADVERTISEMENT)).
- If hourly compensation >= 13.90 € / Stunde, it meets the statutory minimum wage.
- Monthly or yearly figures are evaluated against standard statistical market benchmarks.
"""

import re

# German hourly minimum wage threshold: 13.90 € / hour
# If an hourly rate < 13.90 €/h is mentioned, the job is flagged as a false job advertisement.
GERMAN_MINIMUM_WAGE_HOURLY = 13.90
GERMAN_MINIMUM_WAGE_LEGAL_BASIS = "§ 1 Mindestlohngesetz (MiLoG / 13,90 €/h)"

# Benchmark annual salary distributions in Germany (median in EUR, standard deviation)
# Sourced from Destatis, StepStone, and kununu German salary benchmark indices.
ROLE_BENCHMARKS = {
    "data entry": {"median": 28000, "std": 4500, "min": 21000, "max": 36000, "title_de": "Datenerfasser / Bürohilfe"},
    "typist": {"median": 27000, "std": 4000, "min": 21000, "max": 34000, "title_de": "Schreibkraft"},
    "software engineer": {"median": 65000, "std": 14000, "min": 42000, "max": 110000, "title_de": "Softwareentwickler"},
    "developer": {"median": 62000, "std": 13500, "min": 40000, "max": 105000, "title_de": "Entwickler"},
    "devops": {"median": 70000, "std": 15000, "min": 48000, "max": 120000, "title_de": "DevOps Engineer"},
    "cloud": {"median": 72000, "std": 16000, "min": 50000, "max": 125000, "title_de": "Cloud Architect"},
    "data scientist": {"median": 68000, "std": 15000, "min": 45000, "max": 115000, "title_de": "Data Scientist"},
    "customer support": {"median": 33000, "std": 5500, "min": 24000, "max": 45000, "title_de": "Kundenservice / Support"},
    "sales": {"median": 52000, "std": 16000, "min": 32000, "max": 95000, "title_de": "Vertrieb / Sales"},
    "marketing": {"median": 46000, "std": 11000, "min": 30000, "max": 75000, "title_de": "Marketing Manager"},
    "project manager": {"median": 63000, "std": 14000, "min": 42000, "max": 100000, "title_de": "Projektleiter"},
    "human resources": {"median": 48000, "std": 11000, "min": 32000, "max": 78000, "title_de": "Personalreferent (HR)"},
    "accountant": {"median": 50000, "std": 11000, "min": 35000, "max": 80000, "title_de": "Buchhalter / Controller"},
    "reshipping": {"median": 26000, "std": 4000, "min": 21000, "max": 32000, "title_de": "Paketagent (Hochrisiko-Bereich)"},
    "assistant": {"median": 36000, "std": 6500, "min": 26000, "max": 52000, "title_de": "Assistent / Bürokraft"},
    "default": {"median": 48000, "std": 12000, "min": 28000, "max": 85000, "title_de": "Allgemeine Fachkraft"}
}

ROLE_ALIASES = {
    "data entry": ["data entry", "datenerfasser", "bürohilfe", "typing", "typist", "datenerfassung"],
    "software engineer": ["software engineer", "softwareentwickler", "software developer", "backend", "frontend", "fullstack", "full stack"],
    "developer": ["developer", "entwickler", "programmer", "programmierer", "webentwickler"],
    "devops": ["devops", "site reliability", "sre", "ci/cd", "infrastructure"],
    "cloud": ["cloud", "aws architect", "azure architect", "gcp architect"],
    "data scientist": ["data scientist", "machine learning", "ki-spezialist", "ai engineer", "data analyst", "datenanalyst"],
    "customer support": ["customer support", "kundenservice", "customer service", "call center", "support agent", "kundendienst", "helpdesk"],
    "sales": ["sales", "vertrieb", "account manager", "sales manager", "verkäufer", "sales rep"],
    "marketing": ["marketing", "online marketing", "seo", "content creator", "social media manager"],
    "project manager": ["project manager", "projektleiter", "projektmanager", "scrum master", "product owner"],
    "human resources": ["human resources", "hr", "personalreferent", "recruiter", "talent acquisition", "personalabteilung"],
    "accountant": ["accountant", "buchhalter", "controlling", "finanzbuchhalter", "controller", "bilanzbuchhalter"],
    "reshipping": ["reshipping", "paketagent", "warenprüfer", "paketempfänger", "parcel mule", "package forwarder"],
    "assistant": ["assistant", "assistenz", "sekretär", "sekretärin", "bürokraft", "office manager"]
}

# Standard currency conversion rates to Euros (EUR)
CURRENCY_RATES_TO_EUR = {
    "eur": 1.0,
    "€": 1.0,
    "euro": 1.0,
    "euros": 1.0,
    "usd": 0.92,
    "$": 0.92,
    "gbp": 1.17,
    "£": 1.17,
    "chf": 1.05
}


def format_eur(amount):
    """Format a numeric value into German Euro notation (e.g. 65.000 € or 13,90 €)."""
    if amount is None:
        return "-"
    if isinstance(amount, float) and not amount.is_integer() and amount < 100:
        return f"{amount:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(round(amount)):,} €".replace(",", ".")


def get_german_minimum_wage_info(is_violation=False):
    """Return structured metadata on the German statutory hourly minimum wage."""
    return {
        "hourly_eur": GERMAN_MINIMUM_WAGE_HOURLY,
        "formatted_hourly": f"{format_eur(GERMAN_MINIMUM_WAGE_HOURLY)} / Stunde",
        "legal_basis": GERMAN_MINIMUM_WAGE_LEGAL_BASIS,
        "is_violation": is_violation
    }


def _clean_number_string(num_str):
    """Normalize English and German numeric representations to standard float string."""
    if not num_str:
        return 0.0
    s = num_str.strip()
    if "." in s and "," in s:
        if s.rfind(".") > s.rfind(","):
            return float(s.replace(",", ""))
        return float(s.replace(".", "").replace(",", "."))
    if "." in s:
        parts = s.split(".")
        if len(parts[-1]) == 3:
            return float(s.replace(".", ""))
        return float(s)
    if "," in s:
        parts = s.split(",")
        if len(parts[-1]) == 3:
            return float(s.replace(",", ""))
        return float(s.replace(",", "."))
    return float(s)


def parse_salary_amount(raw_salary_str, full_text=""):
    """Parse salary amount from string or job text and normalize to annual Euros (€ / EUR)."""
    combined = f"{raw_salary_str or ''} {full_text or ''}".strip()
    if not combined:
        return None

    curr_pat = r"(?:€|eur|euro|euros|\$|usd|£|gbp|chf)"

    freq_rules = [
        ("hourly", r"(?:(?:pro|per|\/)\s*(?:stunde|std|hour|hr|h\b))|stündlich"),
        ("daily", r"(?:(?:pro|per|\/)\s*(?:tag|day|daily\b))|täglich"),
        ("weekly", r"(?:(?:pro|per|\/)\s*(?:woche|week|weekly\b))|wöchentlich"),
        ("monthly", r"(?:(?:pro|per|\/)\s*(?:monat|month|monthly|mth\b))|monatlich"),
        ("yearly", r"(?:(?:pro|per|\/)\s*(?:jahr|year|annual|annually|p\.a\.))|jährlich|annually|p\.a\.")
    ]

    # Pattern 1: 'k' multiplier range (e.g. "60k - 80k EUR", "€70k - €90k")
    k_range = re.search(
        rf"(?:({curr_pat})\s*)?(\d{{2,3}})\s*k\s*(?:-|bis|to)\s*(?:({curr_pat})\s*)?(\d{{2,3}})\s*k\s*({curr_pat})?",
        combined, re.IGNORECASE
    )
    if k_range:
        cur_token = (k_range.group(1) or k_range.group(3) or k_range.group(5) or "EUR").lower()
        rate = CURRENCY_RATES_TO_EUR.get(cur_token, 1.0)
        v1 = float(k_range.group(2)) * 1000
        v2 = float(k_range.group(4)) * 1000
        avg_val = (v1 + v2) / 2.0
        annual = avg_val * rate
        return {
            "annual_eur": round(annual, 2),
            "raw_extracted": k_range.group(0).strip(),
            "frequency": "yearly",
            "raw_amount": avg_val,
            "currency": "EUR" if cur_token in ["eur", "€", "euro", "euros"] else cur_token.upper(),
            "currency_symbol": "€",
            "converted_to_eur": rate != 1.0
        }

    # Pattern 2: Single 'k' amount (e.g. "65k EUR", "€75k")
    k_single = re.search(rf"(?:({curr_pat})\s*)?(\d{{2,3}})\s*k\b\s*({curr_pat})?", combined, re.IGNORECASE)
    if k_single:
        cur_token = (k_single.group(1) or k_single.group(3) or "EUR").lower()
        rate = CURRENCY_RATES_TO_EUR.get(cur_token, 1.0)
        val = float(k_single.group(2)) * 1000
        annual = val * rate
        return {
            "annual_eur": round(annual, 2),
            "raw_extracted": k_single.group(0).strip(),
            "frequency": "yearly",
            "raw_amount": val,
            "currency": "EUR" if cur_token in ["eur", "€", "euro", "euros"] else cur_token.upper(),
            "currency_symbol": "€",
            "converted_to_eur": rate != 1.0
        }

    # Pattern 3: Ranges with explicit frequency (e.g. "45.000 - 65.000 € / Jahr", "3.000 - 4.500 EUR / Monat")
    for freq_name, freq_regex in freq_rules:
        pat_range = (
            rf"(?:({curr_pat})\s*)?(\d{{1,3}}(?:[.,]\d{{3}})*(?:[.,]\d{{1,2}})?|\d{{2,6}})\s*({curr_pat})?"
            rf"\s*(?:-|bis|to)\s*"
            rf"(?:({curr_pat})\s*)?(\d{{1,3}}(?:[.,]\d{{3}})*(?:[.,]\d{{1,2}})?|\d{{2,6}})\s*({curr_pat})?"
            rf"\s*(?:{freq_regex})"
        )
        m = re.search(pat_range, combined, re.IGNORECASE)
        if m:
            cur_token = (m.group(1) or m.group(3) or m.group(4) or m.group(6) or "EUR").lower()
            rate = CURRENCY_RATES_TO_EUR.get(cur_token, 1.0)
            try:
                v1 = _clean_number_string(m.group(2))
                v2 = _clean_number_string(m.group(5))
                avg_val = (v1 + v2) / 2.0
                eur_amount = avg_val * rate
                annual = _to_annual(eur_amount, freq_name)
                if 5000 <= annual <= 800000:
                    return {
                        "annual_eur": round(annual, 2),
                        "raw_extracted": m.group(0).strip(),
                        "frequency": freq_name,
                        "raw_amount": avg_val,
                        "currency": "EUR" if cur_token in ["eur", "€", "euro", "euros"] else cur_token.upper(),
                        "currency_symbol": "€",
                        "converted_to_eur": rate != 1.0
                    }
            except Exception:
                pass

    # Pattern 4: Single value with explicit frequency (e.g. "12 € / Stunde", "€ 4.500 / Monat", "85.000 EUR / Jahr", "$5000 per week")
    for freq_name, freq_regex in freq_rules:
        pat_single = (
            rf"(?:({curr_pat})\s*)?(\d{{1,3}}(?:[.,]\d{{3}})*(?:[.,]\d{{1,2}})?|\d{{2,6}})\s*({curr_pat})?"
            rf"\s*(?:{freq_regex})"
        )
        m = re.search(pat_single, combined, re.IGNORECASE)
        if m:
            cur_token = (m.group(1) or m.group(3) or "EUR").lower()
            rate = CURRENCY_RATES_TO_EUR.get(cur_token, 1.0)
            try:
                raw_val = _clean_number_string(m.group(2))
                eur_amount = raw_val * rate
                annual = _to_annual(eur_amount, freq_name)
                if 5000 <= annual <= 800000:
                    return {
                        "annual_eur": round(annual, 2),
                        "raw_extracted": m.group(0).strip(),
                        "frequency": freq_name,
                        "raw_amount": raw_val,
                        "currency": "EUR" if cur_token in ["eur", "€", "euro", "euros"] else cur_token.upper(),
                        "currency_symbol": "€",
                        "converted_to_eur": rate != 1.0
                    }
            except Exception:
                pass

    # Pattern 5: Standalone number with currency marker (e.g. "85.000 EUR", "€ 65.000", "75000 €")
    pat_standalone = rf"(?:({curr_pat})\s*)?(\d{{2,3}}[.,]\d{{3}}|\d{{4,6}})\s*({curr_pat})?"
    for m in re.finditer(pat_standalone, combined, re.IGNORECASE):
        cur_token = (m.group(1) or m.group(3) or "EUR").lower()
        if not m.group(1) and not m.group(3):
            continue
        rate = CURRENCY_RATES_TO_EUR.get(cur_token, 1.0)
        try:
            raw_val = _clean_number_string(m.group(2))
            eur_amount = raw_val * rate
            if 1500 <= eur_amount <= 12000:
                annual = eur_amount * 12
                freq_name = "monthly"
            elif 12000 <= eur_amount <= 800000:
                annual = eur_amount
                freq_name = "yearly"
            else:
                continue
            return {
                "annual_eur": round(annual, 2),
                "raw_extracted": m.group(0).strip(),
                "frequency": freq_name,
                "raw_amount": raw_val,
                "currency": "EUR" if cur_token in ["eur", "€", "euro", "euros"] else cur_token.upper(),
                "currency_symbol": "€",
                "converted_to_eur": rate != 1.0
            }
        except Exception:
            continue

    return None


def _to_annual(eur_amount, freq):
    """Convert amount to annual Euros according to German employment standard hours."""
    if freq == "hourly":
        return eur_amount * 40 * 52
    if freq == "daily":
        return eur_amount * 220
    if freq == "weekly":
        return eur_amount * 52
    if freq == "monthly":
        return eur_amount * 12
    return eur_amount


def detect_salary_anomaly(salary_input="", job_title="", description=""):
    """Evaluate offered compensation vs German labor market benchmarks strictly in Euros (€ / EUR).

    Hourly Minimum Wage Rule:
    - Only applied when an HOURLY wage is mentioned in the job ad or input.
    - If hourly compensation < 13.90 € / Stunde, it is flagged as a false job advertisement
      (is_scam_signal = True, verdict: ILLEGAL SUB-MINIMUM WAGE (FALSE JOB ADVERTISEMENT)).
    - If hourly compensation >= 13.90 € / Stunde, it is completely valid and accepted.
    - Monthly and yearly salaries are evaluated against market benchmarks without false minimum wage flags.
    """
    title_lower = (job_title or "").lower()
    desc_lower = (description or "").lower()

    # Match benchmark role via aliases or benchmark keys
    matched_role = "default"
    for role_key, aliases in ROLE_ALIASES.items():
        if any(a in title_lower or a in desc_lower[:300] for a in aliases):
            matched_role = role_key
            break

    if matched_role == "default":
        for role_key in ROLE_BENCHMARKS:
            if role_key != "default" and (role_key in title_lower or role_key in desc_lower[:300]):
                matched_role = role_key
                break

    bench = ROLE_BENCHMARKS[matched_role]
    parsed = parse_salary_amount(salary_input, description)

    if not parsed:
        return {
            "has_salary_data": False,
            "currency": "EUR",
            "currency_symbol": "€",
            "role_matched": bench["title_de"],
            "market_median_annual": bench["median"],
            "market_min_annual": bench["min"],
            "market_max_annual": bench["max"],
            "formatted_market_range": f"{format_eur(bench['min'])} - {format_eur(bench['max'])} / Jahr",
            "formatted_market_median": f"{format_eur(bench['median'])} / Jahr",
            "german_minimum_wage": get_german_minimum_wage_info(is_violation=False),
            "is_below_minimum_wage": False,
            "verdict": "NOT_SPECIFIED",
            "anomaly_level": "NORMAL",
            "explanation": (
                f"No specific numerical salary was stated. Standard German employer collective agreements and the "
                f"hourly minimum wage threshold ({format_eur(GERMAN_MINIMUM_WAGE_HOURLY)}/h under {GERMAN_MINIMUM_WAGE_LEGAL_BASIS}) apply."
            )
        }

    annual_val = parsed["annual_eur"]
    median = bench["median"]
    std = bench["std"]

    # Statistical Z-score and percentage deviation
    z_score = round((annual_val - median) / std, 2)
    pct_diff = round(((annual_val - median) / median) * 100, 1)

    currency_note = ""
    if parsed.get("converted_to_eur"):
        currency_note = f" (converted from {parsed.get('currency', 'foreign currency')} to Euros)"

    # STRICT HOURLY-ONLY CHECK: Triggered only when an hourly wage is explicitly mentioned
    is_below_min_wage = False
    min_wage_reason = ""
    if parsed.get("frequency") == "hourly":
        hourly_rate = parsed.get("raw_amount") if not parsed.get("converted_to_eur") else (annual_val / (40 * 52))
        if hourly_rate < GERMAN_MINIMUM_WAGE_HOURLY:
            is_below_min_wage = True
            min_wage_reason = (
                f"Offered hourly wage ({format_eur(hourly_rate)}/h) is below Germany's statutory minimum wage "
                f"(minimum threshold: {format_eur(GERMAN_MINIMUM_WAGE_HOURLY)}/h under {GERMAN_MINIMUM_WAGE_LEGAL_BASIS})."
            )

    # Anomaly classification
    if z_score >= 3.5 or (annual_val > bench["max"] * 1.8):
        # Exorbitant bait pay (e.g. 5,000 EUR/week for basic data entry)
        anomaly_level = "CRITICAL_OUTLIER"
        is_scam_signal = True
        verdict = "UNREALISTICALLY HIGH COMPENSATION"
        explanation = (
            f"Offered compensation (~{format_eur(annual_val)}/yr{currency_note}) is statistically anomalous (+{pct_diff}% above German market median). "
            f"Legitimate German employers for {bench['title_de']} pay {format_eur(bench['min'])} - {format_eur(bench['max'])} / Jahr. "
            "Exorbitant pay for entry-level work is a primary indicator of advance-payment, fake check, or money mule recruitment."
        )
    elif is_below_min_wage:
        # Explicit hourly rate below 13.90 €/h is a false job advertisement
        anomaly_level = "MINIMUM_WAGE_VIOLATION"
        is_scam_signal = True
        verdict = "ILLEGAL SUB-MINIMUM WAGE (FALSE JOB ADVERTISEMENT)"
        explanation = (
            f"{min_wage_reason} Legitimate German employers are legally prohibited under {GERMAN_MINIMUM_WAGE_LEGAL_BASIS} "
            f"from paying less than {format_eur(GERMAN_MINIMUM_WAGE_HOURLY)} per hour. An advertisement offering less than 13,90 €/h "
            "is an illegal false job advertisement."
        )
    elif z_score >= 2.0 or (annual_val > bench["max"] * 1.3):
        anomaly_level = "HIGH_VARIANCE"
        is_scam_signal = False
        verdict = "ABOVE MARKET BENCHMARK"
        explanation = (
            f"Offered pay (~{format_eur(annual_val)}/yr{currency_note}) is +{pct_diff}% above market average for {bench['title_de']} "
            f"({format_eur(bench['min'])} - {format_eur(bench['max'])} / Jahr). "
            "Verify whether senior qualifications, bonuses, or commissions are included."
        )
    elif z_score <= -2.0 or (annual_val < bench["min"] * 0.7):
        anomaly_level = "UNDERPAID_SUSPICIOUS"
        is_scam_signal = False
        verdict = "STATISTICALLY UNDERPAID"
        explanation = (
            f"Offered compensation (~{format_eur(annual_val)}/yr{currency_note}) falls below standard German collective benchmarks for {bench['title_de']} "
            f"({format_eur(bench['min'])} - {format_eur(bench['max'])} / Jahr). "
            "May indicate exploitative terms or a dummy ghost-job listing."
        )
    else:
        # Hourly >= 13.90 €/h or standard monthly/yearly compensation
        anomaly_level = "AUTHENTIC_MARKET_RATE"
        is_scam_signal = False
        verdict = "STATISTICALLY NORMAL MARKET WAGE"
        hourly_note = f" (complies with hourly minimum wage >= {format_eur(GERMAN_MINIMUM_WAGE_HOURLY)}/h)" if parsed.get("frequency") == "hourly" else ""
        explanation = (
            f"Offered pay (~{format_eur(annual_val)}/yr{currency_note}){hourly_note} conforms to standard German collective agreement benchmarks for "
            f"{bench['title_de']} (Market range: {format_eur(bench['min'])} - {format_eur(bench['max'])} / Jahr)."
        )

    return {
        "has_salary_data": True,
        "currency": "EUR",
        "currency_symbol": "€",
        "parsed_salary": parsed,
        "role_matched": bench["title_de"],
        "annual_amount_eur": annual_val,
        "market_median_annual": median,
        "market_min_annual": bench["min"],
        "market_max_annual": bench["max"],
        "formatted_offered": f"{format_eur(annual_val)} / Jahr",
        "formatted_market_range": f"{format_eur(bench['min'])} - {format_eur(bench['max'])} / Jahr",
        "formatted_market_median": f"{format_eur(median)} / Jahr",
        "german_minimum_wage": get_german_minimum_wage_info(is_violation=is_below_min_wage),
        "is_below_minimum_wage": is_below_min_wage,
        "z_score": z_score,
        "percentage_deviation": pct_diff,
        "anomaly_level": anomaly_level,
        "is_scam_signal": is_scam_signal,
        "verdict": verdict,
        "explanation": explanation
    }
