# StellenPrüfer — Job Advertisement Verification Tool

A web application and Chrome extension that helps job seekers in Germany check if a job posting is real, safe, and still active before applying.

## What It Checks
* **Company Registration:** Checks if the company exists in the German Commercial Register (*Handelsregister*) and has a real website.
* **Website & Email Safety:** Checks the job link for security threats (VirusTotal) and verifies the recruiter's email domain.
* **Ghost Job Check:** Checks if the job is older than 45 days or already closed (*"No longer accepting applications"*).
* **Salary & Minimum Wage:** Checks if the pay meets Germany's legal minimum wage (**13,90 €/h**).
* **Scam Wording & Contract Check:** Flags upfront payment requests, WhatsApp/Telegram-only interviews, and missing contract details.
* **Resume Match:** Compares the job requirements with your uploaded CV.

## Trust Score (0–100)
* **70 – 100 (High Trust):** Likely valid — safe to apply.
* **45 – 69 (Medium Trust):** Verify details before applying (or job is closed / older than 45 days).
* **0 – 44 (Low Trust):** High scam risk — apply at your own risk.

## Tech Stack
* **Backend:** Python, Flask, SQLite
* **Frontend:** HTML, CSS, JavaScript
* **Browser Extension:** Chrome / Edge (Manifest V3)
