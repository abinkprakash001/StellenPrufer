# Resume skills matching, domain intelligence, and candidate eligibility engine
import re
import math
from collections import Counter
import urllib.parse

STOP_WORDS = {
    "the", "and", "a", "an", "in", "on", "for", "with", "at", "by", "from",
    "to", "of", "is", "are", "und", "der", "die", "das", "mit", "für", "von",
    "oder", "eine", "einer", "einem", "einen", "bei", "im", "am", "des", "dem"
}

# Rich, comprehensive skill taxonomy across Tech, HR, Sales, and Corporate domains
TECH_SKILLS = [
    "python", "java", "javascript", "typescript", "c++", "c#", "golang", "rust", "php", "ruby",
    "sql", "postgresql", "mysql", "mongodb", "redis", "oracle", "react", "angular", "vue",
    "next.js", "node.js", "django", "flask", "fastapi", "spring boot", "laravel", "bootstrap",
    "html5", "css3", "docker", "kubernetes", "aws", "azure", "gcp", "terraform", "ci/cd",
    "git", "linux", "bash", "rest apis", "restful apis", "api integration", "json",
    "machine learning", "deep learning", "nlp", "pandas", "numpy", "scikit-learn", "tensorflow",
    "pytorch", "data science", "cybersecurity", "threat detection", "penetration testing",
    "wireshark", "siem", "phishing detection", "network security", "unit testing", "agile", "scrum",
    "anwendungsentwicklung", "softwareentwicklung", "webentwicklung", "fachinformatik"
]

HR_RECRUITING_SKILLS = [
    "recruiting", "personalberatung", "talent acquisition", "active sourcing",
    "applicant tracking", "ats", "interviewing", "candidate screening", "personalauswahl",
    "personalwesen", "human resources", "arbeitnehmerüberlassung", "aüg", "arbeitsrecht",
    "onboarding", "headhunting", "staffing", "bewerbermanagement"
]

COMMERCIAL_SALES_SKILLS = [
    "kaufmännische kenntnisse", "kaufmännische ausbildung", "b2b sales", "account management",
    "kundenberatung", "kundenbetreuung", "vertrieb", "crm", "salesforce", "hubspot",
    "negotiation", "verhandlungsgeschick", "contract management", "sachbearbeitung",
    "accounting", "buchhaltung", "controlling", "sap", "erp", "customer support"
]

TAXONOMY_SKILLS = TECH_SKILLS + HR_RECRUITING_SKILLS + COMMERCIAL_SALES_SKILLS

# Curated Professional Learning & Overview Guide (Authoritative & Actionable)
SKILL_LEARNING_GUIDE = {
    # Tech
    "python": {
        "title": "Python Development",
        "category": "Programming Languages",
        "description": "Object-oriented scripting, data engineering, and backend service development.",
        "resource_name": "Python Software Foundation Docs",
        "url": "https://docs.python.org/3/"
    },
    "php": {
        "title": "PHP Web Development",
        "category": "Backend Engineering",
        "description": "Server-side web application development, API architecture, and relational database integration.",
        "resource_name": "PHP Official Documentation",
        "url": "https://www.php.net/docs.php"
    },
    "javascript": {
        "title": "JavaScript (ES6+) & Web Applications",
        "category": "Frontend & Full-Stack",
        "description": "Interactive client-side scripting, asynchronous DOM manipulation, and modern web application development.",
        "resource_name": "MDN Web Docs - JavaScript",
        "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript"
    },
    "anwendungsentwicklung": {
        "title": "Application Development (Anwendungsentwicklung)",
        "category": "Software Engineering",
        "description": "Designing, implementing, testing, and documenting modern web and enterprise software architectures.",
        "resource_name": "BIBB Fachinformatiker Anwendungsentwicklung",
        "url": "https://www.bibb.de/dienstleistungen/berufesuche/de/index_berufesuche.php"
    },
    "softwareentwicklung": {
        "title": "Software Engineering (Softwareentwicklung)",
        "category": "Core Engineering",
        "description": "Collaborative software planning, clean code implementation, debugging, and automated testing.",
        "resource_name": "IEEE Software Engineering Guide",
        "url": "https://www.computer.org/standards"
    },
    "webentwicklung": {
        "title": "Modern Web Development",
        "category": "Full-Stack Development",
        "description": "Building responsive, database-driven web applications using HTML5, CSS3, JavaScript, and backend frameworks.",
        "resource_name": "MDN Web Development Learning Area",
        "url": "https://developer.mozilla.org/en-US/docs/Learn"
    },
    "django": {
        "title": "Django Web Framework",
        "category": "Backend Architecture",
        "description": "High-level Python web framework encouraging clean design and rapid development.",
        "resource_name": "Django Official Guide",
        "url": "https://docs.djangoproject.com/"
    },
    "docker": {
        "title": "Docker Containerization",
        "category": "DevOps & Deployment",
        "description": "Standardized container packaging for microservices and cloud deployments.",
        "resource_name": "Docker Architecture Guide",
        "url": "https://docs.docker.com/get-started/"
    },
    "kubernetes": {
        "title": "Kubernetes Orchestration",
        "category": "Cloud & DevOps",
        "description": "Automated container deployment, scaling, and operational management.",
        "resource_name": "Kubernetes Documentation",
        "url": "https://kubernetes.io/docs/home/"
    },
    "aws": {
        "title": "AWS Cloud Architecture",
        "category": "Cloud Infrastructure",
        "description": "Enterprise cloud services including EC2, S3, RDS, Lambda, and IAM security.",
        "resource_name": "AWS Architecture Center",
        "url": "https://aws.amazon.com/architecture/"
    },
    "cybersecurity": {
        "title": "Cybersecurity & Threat Detection",
        "category": "Security Engineering",
        "description": "Defensive analysis, vulnerability management, and automated incident response.",
        "resource_name": "NIST Cybersecurity Framework",
        "url": "https://www.nist.gov/cyberframework"
    },
    "sql": {
        "title": "SQL Database Optimization",
        "category": "Data Management",
        "description": "Relational schema design, query indexing, and transactional data integrity.",
        "resource_name": "PostgreSQL Documentation",
        "url": "https://www.postgresql.org/docs/"
    },
    # HR & Recruiting
    "recruiting": {
        "title": "Candidate Sourcing & Recruiting",
        "category": "HR & Talent Acquisition",
        "description": "End-to-end recruitment lifecycle: talent outreach, candidate screening, and hiring pipeline management.",
        "resource_name": "SHRM Talent Acquisition Guide",
        "url": "https://www.shrm.org/topics/talent-acquisition"
    },
    "personalberatung": {
        "title": "Commercial Staffing & Recruitment Consulting",
        "category": "Client Account Management",
        "description": "Consulting corporate clients on personnel requirements, placement contracts, and temporary staffing (AÜG).",
        "resource_name": "BAP Staffing & Recruitment Standards",
        "url": "https://www.personaldienstleister.de/"
    },
    "talent acquisition": {
        "title": "Strategic Talent Acquisition",
        "category": "Human Resources",
        "description": "Employer branding, executive search, and building proactive candidate talent pools.",
        "resource_name": "LinkedIn Talent Solutions Guide",
        "url": "https://business.linkedin.com/talent-solutions"
    },
    "active sourcing": {
        "title": "Active Sourcing on LinkedIn & Xing",
        "category": "Talent Sourcing",
        "description": "Direct Boolean search and targeted outreach to passive professional candidates across business networks.",
        "resource_name": "Active Sourcing Handbook",
        "url": "https://www.haufe.de/personal/hr-management/active-sourcing_80_415418.html"
    },
    "arbeitsrecht": {
        "title": "German Employment Law (Arbeitsrecht)",
        "category": "Legal Compliance",
        "description": "Understanding German employment contracts, probationary periods (§ 622 BGB), and dismissal protections (KSchG).",
        "resource_name": "Federal Ministry of Labor (BMAS)",
        "url": "https://www.bmas.de/DE/Arbeit/Arbeitsrecht/arbeitsrecht.html"
    },
    "kaufmännische kenntnisse": {
        "title": "Commercial Business Administration",
        "category": "Business Operations",
        "description": "Commercial correspondence, client account invoicing, contract filing, and office management.",
        "resource_name": "IHK Commercial Qualifications",
        "url": "https://www.dihk.de/de/themen-und-positionen/wirtschaftspolitik/bildung"
    },
    "kundenberatung": {
        "title": "Client Advisory & Account Management",
        "category": "Client Relations",
        "description": "Managing relationships with corporate accounts, needs analysis, and contractual service agreements.",
        "resource_name": "Corporate Account Management Best Practices",
        "url": "https://hbr.org/topic/sales"
    }
}

# Domain Classification Patterns
DOMAIN_PATTERNS = {
    "TECH": [
        "python", "software", "developer", "engineer", "informatik", "computer science",
        "programming", "sql", "devops", "cloud", "backend", "frontend", "full stack",
        "cybersecurity", "security", "data scientist", "data science", "api", "django",
        "fachinformatiker", "anwendungsentwicklung", "anwendungsentwickler", "fachinformatik",
        "systemintegration", "softwareentwicklung", "softwareentwickler", "webentwicklung",
        "webentwickler", "programmierung", "programmierer", "programmiersprachen",
        "webanwendungen", "php", "javascript", "typescript", "html5", "css3", "laravel"
    ],
    "HR_RECRUITING": [
        "personalberater", "recruiting", "recruiter", "personaldisponent", "talent acquisition",
        "personalwesen", "staffing", "headhunter", "personalreferent", "hr manager",
        "recruiting specialist", "personalauswahl"
    ],
    "SALES_COMMERCIAL": [
        "vertrieb", "sales", "kaufmännisch", "kaufmännische", "account manager", "außendienst",
        "innendienst", "sachbearbeiter", "kundenberater", "vertriebsmitarbeiter"
    ],
    "LOGISTICS_MANUAL": [
        "warehouse", "lager", "lagerarbeiter", "lagerist", "kommissionierer", "logistikhelfer",
        "paketzusteller", "zusteller", "fahrer", "driver", "kurier", "courier", "delivery",
        "staplerfahrer", "forklift", "reinigung", "cleaner", "reinigungskraft", "spülkraft",
        "bauhelfer", "hilfskraft", "kassierer", "regaleinräumer", "packer", "packaging associate",
        "produktionshelfer", "verräumer", "security guard", "wachdienst"
    ]
}


def _clean_text(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(text))
    text = re.sub(r"https?://\S+", " ", text)
    # Replace punctuation (dots, commas, hyphens, colons, slashes) with spaces while preserving c++, c#
    text = re.sub(r"[^\w\s\+\#]", " ", str(text))
    return re.sub(r"\s+", " ", text).strip().lower()


def _pure_cosine_similarity(text1, text2):
    words1 = [w for w in text1.split() if len(w) > 2 and w not in STOP_WORDS]
    words2 = [w for w in text2.split() if len(w) > 2 and w not in STOP_WORDS]
    if not words1 or not words2:
        return 0.0

    tokens1 = words1 + [f"{words1[i]} {words1[i+1]}" for i in range(len(words1) - 1)]
    tokens2 = words2 + [f"{words2[i]} {words2[i+1]}" for i in range(len(words2) - 1)]
    c1 = Counter(tokens1)
    c2 = Counter(tokens2)

    intersection = set(c1.keys()) & set(c2.keys())
    if not intersection:
        return 0.0

    numerator = sum(c1[t] * c2[t] for t in intersection)
    sum1 = sum(v ** 2 for v in c1.values())
    sum2 = sum(v ** 2 for v in c2.values())
    denom = math.sqrt(sum1) * math.sqrt(sum2)
    return (numerator / denom) if denom else 0.0


def extract_skills(text):
    """
    Extract known taxonomy skills from text using strict token boundary matching.
    Eliminates false-positive substring traps (e.g. 'go' inside 'django', 'rust' inside 'robust').
    """
    clean = _clean_text(text)
    if not clean:
        return []

    words = set(clean.split())
    found = []

    for skill in TAXONOMY_SKILLS:
        if " " in skill or "." in skill or "+" in skill or "#" in skill or "/" in skill:
            pattern = rf"\b{re.escape(skill)}\b"
            if re.search(pattern, clean):
                found.append(skill)
        else:
            if skill in words:
                found.append(skill)

    return sorted(list(set(found)))


def detect_domain(text, job_title=""):
    """Classify the primary professional domain of text, giving priority to explicit job title indicators."""
    clean_title = _clean_text(job_title)
    if clean_title:
        title_tech = [
            "fachinformatiker", "anwendungsentwicklung", "anwendungsentwickler", "fachinformatik",
            "systemintegration", "software", "softwareentwicklung", "softwareentwickler", "developer",
            "entwickler", "engineer", "programmierer", "programmierung", "webentwicklung",
            "webentwickler", "frontend", "backend", "full stack", "fullstack", "devops",
            "informatik", "data scientist", "data engineer", "cybersecurity", "it"
        ]
        if any(re.search(rf"\b{re.escape(p)}\b", clean_title) for p in title_tech):
            return "TECH"

        title_hr = [
            "personalberater", "personalberatung", "recruiter", "recruiting",
            "talent acquisition", "personaldisponent", "headhunter", "personalreferent"
        ]
        if any(re.search(rf"\b{re.escape(p)}\b", clean_title) for p in title_hr):
            return "HR_RECRUITING"

        title_manual = [
            "lagerarbeiter", "warehouse", "staplerfahrer", "zusteller", "paketzusteller",
            "reinigungskraft", "packer", "kommissionierer", "logistikhelfer", "fahrer", "driver"
        ]
        if any(re.search(rf"\b{re.escape(p)}\b", clean_title) for p in title_manual):
            return "LOGISTICS_MANUAL"

    clean = _clean_text(f"{job_title} {text}")
    scores = {}
    for domain, patterns in DOMAIN_PATTERNS.items():
        # Give extra weight to patterns appearing in the job title
        title_bonus = sum(3 for p in patterns if clean_title and re.search(rf"\b{re.escape(p)}\b", clean_title))
        body_score = sum(1 for p in patterns if re.search(rf"\b{re.escape(p)}\b", clean))
        scores[domain] = title_bonus + body_score

    top_domain = max(scores, key=scores.get)
    return top_domain if scores[top_domain] > 0 else "GENERAL"


def match_resume_to_job(resume_text="", job_description="", job_title=""):
    """
    Computes semantic similarity, skill alignment, universal trap warnings,
    and intelligent cross-domain career guidance.
    """
    if not resume_text or not resume_text.strip():
        return {
            "has_resume": False,
            "message": "No resume provided for matching."
        }

    job_text = f"{job_title or ''} {job_description or ''}"
    clean_resume = _clean_text(resume_text)
    clean_job = _clean_text(job_text)
    clean_title = _clean_text(job_title or "")

    if len(clean_resume.split()) < 5:
        return {
            "has_resume": True,
            "fit_score": 0,
            "fit_label": "Insufficient Resume Data",
            "acceptance_chance": "Not Available",
            "acceptance_chance_color": "#64748b",
            "acceptance_detail": "Please provide a more detailed list of skills or experience in your CV.",
            "explanation": "Please provide a more detailed list of skills or experience."
        }

    resume_skills = extract_skills(clean_resume)
    job_skills = extract_skills(clean_job)

    # Also infer core tech skills from German software/apprenticeship descriptions if not explicitly tokenized
    if any(k in clean_job for k in ["anwendungsentwicklung", "fachinformatiker", "web anwendungen", "webanwendungen", "programmiersprachen"]):
        for implied_skill in ["javascript", "php", "python", "html5", "css3", "sql"]:
            if implied_skill in resume_skills and implied_skill in clean_job and implied_skill not in job_skills:
                job_skills.append(implied_skill)
        # If the job description was truncated on a search page and only the title was captured for Fachinformatiker Anwendungsentwicklung
        if not job_skills and any(k in clean_title for k in ["anwendungsentwicklung", "fachinformatiker"]):
            for core_s in ["javascript", "php", "python", "html5", "css3"]:
                if core_s in resume_skills:
                    job_skills.append(core_s)

    job_skills = sorted(list(set(job_skills)))

    resume_domain = detect_domain(clean_resume)
    job_domain = detect_domain(clean_job, job_title=job_title or "")

    try:
        raw_sim = _pure_cosine_similarity(clean_resume, clean_job)
    except Exception:
        raw_sim = 0.0

    fit_score = min(95.0, max(5.0, round(raw_sim * 140.0, 1)))

    # Filter out generic German category labels from missing_skills if specific programming languages are already matched
    generic_meta_skills = {"anwendungsentwicklung", "softwareentwicklung", "webentwicklung", "fachinformatik"}
    matched_skills = [s for s in job_skills if s in resume_skills]
    for meta_s in generic_meta_skills:
        if meta_s in job_skills and resume_domain == "TECH" and meta_s not in matched_skills:
            matched_skills.append(meta_s)
    matched_skills = sorted(list(set(matched_skills)))
    missing_skills = [s for s in job_skills if s not in matched_skills and s not in generic_meta_skills]

    # Education & Apprenticeship Check
    has_bachelor = any(b in clean_resume for b in ["bachelor", "b sc", "bca", "b tech"])
    has_master = any(m in clean_resume for m in ["master", "m sc", "mca", "m tech"])
    requires_degree = any(d in clean_job for d in ["degree", "bachelor", "master", "hochschulabschluss", "studium"])
    is_apprenticeship = (
        any(k in clean_title for k in ["ausbildung", "azubi", "fachinformatiker", "lehrstelle", "duales studium"]) or
        any(k in clean_job for k in ["ausbildung zum", "ausbildung als", "ausbildungsplatz", "ausbildungsberuf"])
    )

    # Domain Divergence Logic
    is_domain_mismatch = (
        (resume_domain == "TECH" and job_domain in ["HR_RECRUITING", "SALES_COMMERCIAL", "LOGISTICS_MANUAL"]) or
        (resume_domain != "TECH" and job_domain == "TECH")
    )
    is_manual_job = job_domain == "LOGISTICS_MANUAL"

    is_career_divergence = False
    is_overqualified = False
    is_tech_apprenticeship_match = False
    career_advisory_message = ""

    if is_domain_mismatch:
        is_career_divergence = True
        if is_manual_job:
            is_overqualified = True
            fit_score = 65.0
            career_advisory_message = (
                f"Bridge Role Guidance: You exceed basic educational requirements for this role ('{job_title or 'this position'}'). "
                "Because your background is in Software & Computer Science, recruiters may assume this is a short-term bridge job. "
                "Clarify your motivation and availability in your application if you are seeking student or flexible bridge income."
            )
        elif job_domain == "HR_RECRUITING":
            fit_score = 25.0
            career_advisory_message = (
                f"Career Guidance: This vacancy ('{job_title or 'this position'}') is in HR & Commercial Recruitment (Personalberatung), "
                f"focusing on client staffing, applicant screening, and candidate placement. "
                f"Your profile is specialized in Software Engineering, Python Full-Stack Development, and Cybersecurity ({', '.join(resume_skills[:4]) if resume_skills else 'Tech'}). "
                f"While your academic degree and communication skills are valuable, this position does not utilize your software development or engineering competencies. "
                f"For career progression in your field, focus on Software Engineer, Python Developer, or Data Science roles."
            )
        elif job_domain == "SALES_COMMERCIAL":
            fit_score = 30.0
            career_advisory_message = (
                f"Career Note: This job ('{job_title or 'this position'}') is in Commercial Sales & Account Management. "
                f"Your profile is in Computer Science and Software Engineering. Unless you are targeting Technical Sales / Solutions Engineering, "
                f"we recommend prioritizing software development roles that build on your core programming skills."
            )
    else:
        if resume_domain == "TECH" and job_domain == "TECH" and is_apprenticeship and (has_bachelor or has_master):
            is_tech_apprenticeship_match = True
            skill_boost = min(35.0, len(matched_skills) * 12.0)
            fit_score = min(95.0, round(max(fit_score, 68.0 + skill_boost), 1))
            deg_name = "Master's and Bachelor's degrees" if (has_master and has_bachelor) else ("Master's degree" if has_master else "Bachelor's degree")
            matched_display = ", ".join(s.upper() if s in ("php", "sql", "css3", "html5") else s.title() for s in matched_skills[:5]) or "Software Development"
            career_advisory_message = (
                f"Academic & Technical Alignment: This role ('{job_title or 'Fachinformatiker für Anwendungsentwicklung'}') is a German vocational software development apprenticeship (Ausbildung). "
                f"Your CV already demonstrates a {deg_name} in Computer Science and hands-on proficiency in {matched_display}, which directly cover and exceed the apprenticeship curriculum ((Fach-)Abitur + initial programming knowledge). "
                f"You are well-qualified for this training role and also eligible to apply directly for Junior Software Developer or Full-Stack Engineer positions."
            )
        elif matched_skills:
            skill_boost = min(45.0, len(matched_skills) * 12.0)
            fit_score = min(98.0, round(max(fit_score, 45.0 + skill_boost), 1))

    # Universal Trap Detection
    has_zero_requirements = len(job_skills) == 0 and len(clean_job.split()) >= 15
    has_universal_claims = any(k in clean_job for k in [
        "no experience", "anyone can apply", "no qualification", "keine vorkenntnisse",
        "immediate start without interview", "guaranteed hire"
    ])
    is_suspicious_universal_match = False
    trap_warning = ""

    if has_zero_requirements and has_universal_claims:
        is_suspicious_universal_match = True
        trap_warning = (
            "Caution: This job advert lists zero technical or professional prerequisites and guarantees immediate hiring. "
            "Legitimate enterprise employers require defined role competencies. "
            "Universal acceptance claims are a common pattern in resume-harvesting and phishing scams."
        )

    # Fit Labels
    if is_suspicious_universal_match:
        fit_label = "Deceptive Universal Match Trap"
        acceptance_chance = "Deceptive Trap"
        acceptance_chance_color = "#991b1b"
        acceptance_detail = "Warning: Advert guarantees hiring with zero prerequisites (high fraud / scam risk)."
    elif is_overqualified:
        fit_label = "Eligible (Overqualified / Bridge Role)"
        acceptance_chance = "Eligible (Overqualified)"
        acceptance_chance_color = "#0284c7"
        acceptance_detail = "High eligibility: You exceed baseline requirements. Ideal for flexible, student, or bridge income."
    elif is_tech_apprenticeship_match:
        fit_label = "Strong Candidate Fit (Degree Exceeds Apprenticeship)"
        acceptance_chance = "High (Academic Advantage)"
        acceptance_chance_color = "#166534"
        acceptance_detail = "Strong match: Your programming stack (PHP, JavaScript, Web Dev) and Computer Science degree cover and exceed all training prerequisites."
    elif is_career_divergence:
        fit_label = "Different Field / Domain Divergence"
        acceptance_chance = "Different Field"
        acceptance_chance_color = "#c2410c"
        acceptance_detail = "Specialized role in another industry (HR/Commercial) outside your Software Engineering profile."
    elif fit_score >= 70.0:
        fit_label = "Strong Candidate Fit"
        acceptance_chance = "High"
        acceptance_chance_color = "#166534"
        acceptance_detail = "Strong alignment: Core technical competencies, degree, and frameworks match this position."
    elif fit_score >= 45.0:
        fit_label = "Moderate Alignment"
        acceptance_chance = "Moderate"
        acceptance_chance_color = "#b45309"
        acceptance_detail = "Fair alignment: Strong foundational competencies, with some domain prerequisites to address."
    else:
        fit_label = "Low Alignment / Missing Prerequisites"
        acceptance_chance = "Low"
        acceptance_chance_color = "#475569"
        acceptance_detail = "Missing primary technical prerequisites listed for this posting."

    # Reasons Why This Job Matches
    why_matched_reasons = []

    if matched_skills:
        why_matched_reasons.append({
            "category": "Key Skills",
            "icon": "✓",
            "title": f"Matching Skills ({len(matched_skills)} direct match)",
            "detail": f"Your resume covers {len(matched_skills)} specific skills requested in this posting: {', '.join(matched_skills[:6])}."
        })
    elif not is_career_divergence:
        why_matched_reasons.append({
            "category": "Foundational Skills",
            "icon": "✓",
            "title": "Transferable Technical Foundation",
            "detail": f"Your core competencies in {', '.join(resume_skills[:4]) if resume_skills else 'software development'} provide a transferable foundation."
        })

    if is_tech_apprenticeship_match:
        why_matched_reasons.append({
            "category": "Education",
            "icon": "🎓",
            "title": "Computer Science Degree Exceeds (Fach-)Abitur Requirement",
            "detail": "This apprenticeship requests a secondary school diploma ((Fach-)Abitur) or university background with initial programming experience—both exceeded by your BCA & Master's studies."
        })
    elif has_bachelor and requires_degree:
        why_matched_reasons.append({
            "category": "Education",
            "icon": "🎓",
            "title": "Bachelor's Degree Match",
            "detail": "Your university degree meets the academic prerequisite requested by the employer."
        })
    elif has_master and requires_degree:
        why_matched_reasons.append({
            "category": "Education",
            "icon": "🎓",
            "title": "Master's Degree Match",
            "detail": "Your Master's degree fits the advanced academic credentials required."
        })
    elif (has_bachelor or has_master) and not is_career_divergence:
        why_matched_reasons.append({
            "category": "Education",
            "icon": "🎓",
            "title": "University Degree",
            "detail": "Your higher education degree demonstrates strong problem-solving and structured methodology."
        })

    if is_career_divergence:
        why_matched_reasons.append({
            "category": "Career Alignment",
            "icon": "ℹ️",
            "title": "Industry Comparison",
            "detail": f"This vacancy is in {job_domain.replace('_', ' ').title()}, whereas your CV is focused on {resume_domain.title()} & Software Engineering ({', '.join(resume_skills[:4]) if resume_skills else 'Tech'})."
        })
    else:
        why_matched_reasons.append({
            "category": "Role Fit",
            "icon": "💼",
            "title": "Software & Web Application Development Fit",
            "detail": f"Your hands-on experience building full-stack web applications with PHP (Laravel), JavaScript, HTML5/CSS3, and Python (Django) directly aligns with the responsibilities of {job_title or 'this role'}."
        })

    # Actionable Missing Competency Cards (Domain-Intelligent)
    skills_to_improve = []

    # If job has explicit missing skills
    if missing_skills:
        for skill in missing_skills[:4]:
            guide = SKILL_LEARNING_GUIDE.get(skill)
            if guide:
                skills_to_improve.append({
                    "skill": skill,
                    "title": guide["title"],
                    "category": guide["category"],
                    "description": guide["description"],
                    "resource_name": guide["resource_name"],
                    "url": guide["url"]
                })
            else:
                title = skill.title()
                skills_to_improve.append({
                    "skill": skill,
                    "title": title,
                    "category": "Required Role Prerequisite",
                    "description": f"Domain requirement listed for {job_title or 'this vacancy'}.",
                    "resource_name": f"Learn about {title}",
                    "url": f"https://www.google.com/search?q={urllib.parse.quote_plus(skill + ' skills training course')}"
                })
    elif is_career_divergence and job_domain == "HR_RECRUITING":
        # Provide domain-specific competencies ONLY for actual HR Recruiter positions
        hr_requirements = [
            ("personalberatung", "Commercial Staffing (Personalberatung)", "Client Account Management", "Advising corporate clients on staffing requirements, temporary employment (AÜG), and fee placements.", "BAP Staffing & Recruitment Standards", "https://www.personaldienstleister.de/"),
            ("recruiting", "Candidate Sourcing & Screening", "Talent Acquisition", "Identifying, engaging, and screening candidates across LinkedIn, Xing, and job boards.", "SHRM Talent Acquisition Guide", "https://www.shrm.org/topics/talent-acquisition"),
            ("arbeitsrecht", "German Employment Law (Arbeitsrecht)", "Labor Regulations", "Knowledge of German employment contracts, probationary periods (§ 622 BGB), and legal compliance.", "BMAS Labor Law Standards", "https://www.bmas.de/DE/Arbeit/Arbeitsrecht/arbeitsrecht.html")
        ]
        for skill_key, title, cat, desc, res_name, res_url in hr_requirements:
            skills_to_improve.append({
                "skill": skill_key,
                "title": title,
                "category": cat,
                "description": desc,
                "resource_name": res_name,
                "url": res_url
            })

    # Strategy Advice
    if is_overqualified:
        recommendation = "Application Strategy: Because your technical profile exceeds basic role requirements, clarify in your application that you are seeking student income, part-time flexibility, or a reliable bridge role."
    elif is_tech_apprenticeship_match:
        recommendation = "Application Strategy: Highlight your completed PHP/Laravel and JavaScript web application projects. Note that while this is an Ausbildung, your existing programming skills allow you to contribute productively to the engineering team from day one."
    elif is_career_divergence:
        recommendation = "Career Strategy: This role is in HR & Commercial Staffing. To advance your career in tech, we recommend directing your applications to Software Engineering, Python Development, or Cybersecurity positions."
    elif missing_skills:
        recommendation = f"Highlight any practical experience or self-guided projects you have with {', '.join(missing_skills[:3])} in your cover letter."
    else:
        recommendation = "High alignment: Your CV covers all the primary technical prerequisites identified in this job advertisement."

    return {
        "has_resume": True,
        "fit_score": fit_score,
        "fit_label": fit_label,
        "acceptance_chance": acceptance_chance,
        "acceptance_chance_color": acceptance_chance_color,
        "acceptance_detail": acceptance_detail,
        "cosine_similarity_raw": round(raw_sim, 3),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills[:6] if missing_skills else [s["skill"] for s in skills_to_improve],
        "skills_to_improve": skills_to_improve,
        "resume_skills_found": resume_skills,
        "is_suspicious_universal_match": is_suspicious_universal_match,
        "trap_warning": trap_warning,
        "is_career_divergence": is_career_divergence,
        "is_overqualified": is_overqualified,
        "career_advisory_message": career_advisory_message,
        "why_matched_reasons": why_matched_reasons,
        "recommendation": recommendation,
        "summary": (
            f"Candidate profile analyzed: {len(resume_skills)} core technical skills detected on CV. "
            f"{'Industry divergence identified: HR Recruiting vs. Tech profile.' if is_career_divergence else f'{len(matched_skills)} direct skill overlaps with job requirements.'} "
            f"Overall match: {fit_score}%."
        )
    }
