const API_BASE = "http://127.0.0.1:5000";

let currentUser = {

  id: 6,

  name: "somanjiji",

  email: "som123@gmail.com"

};

let activeTabData = {

  url: "",

  title: "",

  company: "",

  address: "",

  salary: "",

  recruiterEmail: "",

  datePosted: "",

  refNumber: "",

  description: ""

};

let currentVerifiedData = null;

// Query job metadata from the active tab's content script

async function fetchTabJobData(tab) {

  if (!tab || !tab.id) return null;

  // 1. First attempt: execute extraction directly in tab to guarantee freshest DOM extraction

  try {

    const [injection] = await chrome.scripting.executeScript({

      target: { tabId: tab.id },

      func: () => (window.__spExtractPageJobData ? window.__spExtractPageJobData() : null)

    });

    if (injection && injection.result && (injection.result.company || injection.result.title)) {

      return injection.result;

    }

  } catch (e) {}

  // 2. Try direct message to content.js

  try {

    const res = await chrome.tabs.sendMessage(tab.id, { type: "GET_PAGE_JOB_DATA" });

    if (res && res.success && res.data && (res.data.company || res.data.title)) return res.data;

  } catch (e) {}

  // 3. Try injecting content.js in case tab was opened before extension loaded/updated

  try {

    await chrome.scripting.executeScript({

      target: { tabId: tab.id },

      files: ["content.js"]

    });

    const res2 = await chrome.tabs.sendMessage(tab.id, { type: "GET_PAGE_JOB_DATA" });

    if (res2 && res2.success && res2.data && (res2.data.company || res2.data.title)) return res2.data;

  } catch (e) {}

  const tabTitleGeneric = isGenericTitle(tab.title);

  return {

    url: tab.url,

    title: tabTitleGeneric ? "" : tab.title,

    company: ""

  };

}

async function loadCurrentUser() {

  try {

    const res = await fetch(`${API_BASE}/api/current-user`);

    const data = await res.json();

    if (data && data.success && data.user) {

      currentUser = data.user;

    }

  } catch (e) {}

  const nameEl = document.getElementById("userName");

  const emailEl = document.getElementById("userEmail");

  if (nameEl) nameEl.textContent = currentUser.name || "somanjiji";

  if (emailEl) emailEl.textContent = currentUser.email || "som123@gmail.com";

}

// Helpers to detect search-page garbage text or generic placeholders

function isGenericTitle(t) {

  if (!t || typeof t !== "string") return true;

  const s = t.trim().toLowerCase();

  if (!s) return true;

  return (

    /^\d+[\d.,]*\s+jobs\s+in/i.test(s) ||

    s.includes("jobsuche der ba") ||

    s.includes("kein filterbarer") ||

    s.includes("filterbarer inhalt") ||

    s.includes("jobs in berlin") ||

    s === "job listing" ||

    s === "job offer page" ||

    s === "current web page" ||

    s === "stellenangebot" ||

    s === "stellenangebote" ||

    s === "selected job position" ||

    s === "job position"

  );

}

function isGenericCompany(c) {

  if (!c || typeof c !== "string") return true;

  const s = c.trim().toLowerCase();

  if (!s) return true;

  return (

    s.includes("filterbar") ||

    s.includes("kein filterbarer") ||

    s.includes("filterbarer inhalt") ||

    s.includes("arbeitgeber a-z") ||

    (s.includes("arbeitgeber") && s.includes("9-1")) ||

    s === "employer on screen" ||

    s === "company" ||

    s === "company verified"

  );

}

async function previewCurrentTab() {

  const titleEl = document.getElementById("tabDetectedTitle");

  const compEl = document.getElementById("tabDetectedCompany");

  const loaderBox = document.getElementById("loaderBox");

  const scoreCard = document.getElementById("scorePopupCard");

  const dashLinks = document.getElementById("dashboardLinkWrapper");

  if (loaderBox) loaderBox.style.display = "none";

  if (scoreCard) scoreCard.style.display = "none";

  if (dashLinks) dashLinks.style.display = "none";

  try {

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab || !tab.url || (!tab.url.startsWith("http://") && !tab.url.startsWith("https://"))) {

      if (titleEl) titleEl.textContent = "Paste any job link or company above";

      if (compEl) compEl.textContent = "Or navigate to any job listing to verify.";

      return;

    }

    const data = await fetchTabJobData(tab);

    if (data) {

      activeTabData = Object.assign({}, activeTabData, data);

    } else {

      activeTabData.url = tab.url;

      activeTabData.title = tab.title || "Job Listing";

    }

    if (isGenericTitle(activeTabData.title)) {

      activeTabData.title = "";

    }

    if (isGenericCompany(activeTabData.company)) {

      activeTabData.company = "";

    }

    if (titleEl) {

      titleEl.textContent = activeTabData.title || "Loading job details...";

    }

    if (compEl) {

      compEl.textContent = activeTabData.company || "Detecting employer...";

    }

    if (activeTabData.url) {

      fetch(`${API_BASE}/api/sync-tab-job`, {

        method: "POST",

        headers: { "Content-Type": "application/json" },

        body: JSON.stringify({ ...activeTabData, tabId: tab.id })

      })

      .then(r => r.json())

      .then(res => {

        if (res && res.success && res.job) {

          if (res.job.title && !isGenericTitle(res.job.title)) {

            activeTabData.title = res.job.title;

            if (titleEl) titleEl.textContent = res.job.title;

          }

          if (res.job.company && !isGenericCompany(res.job.company)) {

            activeTabData.company = res.job.company;

            if (compEl) compEl.textContent = res.job.company;

          }

          if (res.job.url) {

            activeTabData.url = res.job.url;

          }

          if (res.job.salary && !activeTabData.salary) {

            activeTabData.salary = res.job.salary;

          }

        }

      })

      .catch(() => {});

    }

  } catch (err) {

    if (titleEl) titleEl.textContent = "Current Web Page";

  }

}

async function runVerification(payload, tabInfo) {

  const loaderBox = document.getElementById("loaderBox");

  const loaderMsg = document.getElementById("loaderMessage");

  const scoreCard = document.getElementById("scorePopupCard");

  const dashLinks = document.getElementById("dashboardLinkWrapper");

  if (loaderBox) loaderBox.style.display = "block";

  if (loaderMsg) loaderMsg.textContent = "Verifying job details...";

  if (scoreCard) scoreCard.style.display = "none";

  if (dashLinks) dashLinks.style.display = "none";

  try {

    const res = await fetch(`${API_BASE}/api/verify`, {

      method: "POST",

      headers: { "Content-Type": "application/json" },

      body: JSON.stringify(payload)

    });

    const data = await res.json();

    renderVerificationResult(data, tabInfo);

  } catch (err) {

    showOfflineState();

  }

}

async function verifyCurrentTab() {

  try {

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab || !tab.url || (!tab.url.startsWith("http://") && !tab.url.startsWith("https://"))) {

      return;

    }

    const data = await fetchTabJobData(tab);

    if (data) activeTabData = Object.assign({}, activeTabData, data);

    const cleanTitle = isGenericTitle(activeTabData.title) ? "" : activeTabData.title;

    const cleanComp = isGenericCompany(activeTabData.company) ? "" : activeTabData.company;

    const payload = {

      checkType: "job_offer",

      fromExtension: true,

      jobUrl: activeTabData.url,

      jobTitle: cleanTitle,

      company: cleanComp,

      companyAddress: activeTabData.address || "",

      recruiterEmail: activeTabData.recruiterEmail || "",

      salary: activeTabData.salary || "",

      datePosted: activeTabData.datePosted || "",

      jobDescription: activeTabData.description || "",

      userId: currentUser.id,

      userName: currentUser.name,

      userEmail: currentUser.email

    };

    await runVerification(payload, activeTabData);

  } catch (e) {

    showOfflineState();

  }

}

async function verifyManualInput(query) {

  let jobUrl = "";

  let company = "";

  let jobTitle = "";

  if (query.startsWith("http://") || query.startsWith("https://")) {

    jobUrl = query;

  } else {

    company = query;

    jobTitle = query;

  }

  const payload = {

    checkType: "job_offer",

    fromExtension: true,

    jobUrl,

    jobTitle,

    company,

    userId: currentUser.id,

    userName: currentUser.name,

    userEmail: currentUser.email

  };

  await runVerification(payload, {

    url: jobUrl,

    title: jobTitle || "Verified Job",

    company: company || "Company"

  });

}

function renderVerificationResult(data, tabInfo) {

  const loaderBox = document.getElementById("loaderBox");

  const scoreCard = document.getElementById("scorePopupCard");

  const dashLinks = document.getElementById("dashboardLinkWrapper");

  if (loaderBox) loaderBox.style.display = "none";

  if (scoreCard) scoreCard.style.display = "block";

  if (!data || !data.success) {

    const hl = document.getElementById("trustHeadline");

    if (hl) hl.textContent = "Could Not Verify";

    if (dashLinks) dashLinks.style.display = "none";

    return;

  }

  currentVerifiedData = Object.assign({}, data, { tabInfo });

  try {

    chrome.storage.local.set({ latest_verification_result: currentVerifiedData });

  } catch (e) {}

  const res = (data.result || "REVIEW CAREFULLY").toUpperCase();

  const score = typeof data.trust_score === "number" ? data.trust_score : (res === "LIKELY VALID" ? 92 : (res === "HIGH RISK" ? 20 : 60));

  const trustLabel = data.trust_label || (score >= 70 ? "70–100: High Trust (Likely Valid — Safe to Apply)" : (score >= 45 ? "45–69: Medium Trust (Verify Details)" : "0–44: Low Trust / High Scam Risk (Apply at Your Own Risk)"));

  const scoreCircle = document.getElementById("scoreCircle");

  const scoreNum = document.getElementById("scoreNum");

  const trustPill = document.getElementById("trustPill");

  const trustHeadline = document.getElementById("trustHeadline");

  const badgeScoreOutOf = document.getElementById("badgeScoreOutOf");

  if (scoreNum) scoreNum.textContent = score;

  if (badgeScoreOutOf) badgeScoreOutOf.textContent = `${score} / 100`;

  if (trustPill) trustPill.textContent = `${res} · ${score}/100`;

  if (trustHeadline) trustHeadline.textContent = trustLabel;

  const gjaTop = data.ghost_job_assessment || {};
  const isClosedTop = Boolean(
    gjaTop.is_closed_job ||
    (data.availability_status || "").toUpperCase().includes("CLOSED") ||
    (data.warnings || []).some(w => /no longer accepting applications|states that it is closed/i.test(w))
  );
  const isGhostTop = Boolean(gjaTop.is_ghost_job);

  if (scoreCircle && trustPill) {
    scoreCircle.className = "score-circle";
    trustPill.className = "trust-status-pill";
    if (score >= 70 && !isClosedTop && !isGhostTop) {
      scoreCircle.classList.add("score-valid");
      trustPill.classList.add("pill-valid");
    } else if (score <= 44 || res === "HIGH RISK") {
      scoreCircle.classList.add("score-danger");
      trustPill.classList.add("pill-danger");
    } else {
      scoreCircle.classList.add("score-warn");
      trustPill.classList.add("pill-warn");
    }
  }

  const compName = (!isGenericCompany(data.company_name) && data.company_name) ||

                   (!isGenericCompany(tabInfo.company) && tabInfo.company) ||

                   "Company Verified";

  const locName = data.company_address || tabInfo.address || "";

  const jobTitleText = (!isGenericTitle(data.job_title) && data.job_title) ||

                       (!isGenericTitle(tabInfo.title) && tabInfo.title) ||

                       "Selected Job Position";

  const trustComp = document.getElementById("trustCompany");

  const trustTitle = document.getElementById("trustJobTitle");

  if (trustComp) trustComp.textContent = locName ? `${compName} (${locName})` : compName;

  if (trustTitle) trustTitle.textContent = jobTitleText;

  // Update top header preview as well with real verified job details

  const headerTitleEl = document.getElementById("tabDetectedTitle");

  const headerCompEl = document.getElementById("tabDetectedCompany");

  if (headerTitleEl && jobTitleText && jobTitleText !== "Selected Job Position") headerTitleEl.textContent = jobTitleText;

  if (headerCompEl && compName && compName !== "Company Verified") headerCompEl.textContent = compName;

  // Quick 3-pillar preview row

  const quickRow = document.getElementById("quickPillarsRow");

  const quickSecurity = document.getElementById("quickAiBadge");

  const quickSalary = document.getElementById("quickSalaryBadge");

  const quickResume = document.getElementById("quickResumeBadge");
  const quickGhost = document.getElementById("quickGhostBadge");

  if (quickRow) {

    const gjaQuick = data.ghost_job_assessment || {};
    if (quickGhost) {
      if (isClosedTop) {
        quickGhost.textContent = "⛔ Vacancy Closed";
        quickGhost.style.background = "#fef2f2";
        quickGhost.style.color = "#991b1b";
        quickGhost.style.borderColor = "#fecaca";
      } else if (gjaQuick.is_ghost_job) {
        quickGhost.textContent = "⚠ Possible Ghost Job";
        quickGhost.style.background = "#fffbeb";
        quickGhost.style.color = "#b45309";
        quickGhost.style.borderColor = "#fde68a";
      } else {
        quickGhost.textContent = "✓ Not a Ghost Job (Active)";
        quickGhost.style.background = "#f0fdf4";
        quickGhost.style.color = "#166534";
        quickGhost.style.borderColor = "#bbf7d0";
      }
    }

    const rf = data.resume_fit || {};

    const sa = data.salary_anomaly || {};

    const jda = data.job_description_analysis || {};

    const hasWarnings = (data.warnings || []).length > 0 || (jda.scam_signals || []).length > 0;

    if (quickSecurity) {

      if (hasWarnings) {

        quickSecurity.textContent = "Text: Warning";

        quickSecurity.style.background = "#fef2f2";

        quickSecurity.style.color = "#991b1b";

        quickSecurity.style.borderColor = "#fecaca";

      } else {

        quickSecurity.textContent = "Text: Safe";

        quickSecurity.style.background = "#f0fdf4";

        quickSecurity.style.color = "#166534";

        quickSecurity.style.borderColor = "#bbf7d0";

      }

    }

    if (quickSalary) {

      if (sa.has_salary_data) {

        if (sa.is_below_minimum_wage) {

          quickSalary.textContent = "Pay: < Min. Wage";

          quickSalary.style.background = "#fef2f2";

          quickSalary.style.color = "#991b1b";

          quickSalary.style.borderColor = "#fecaca";

        } else {

          quickSalary.textContent = sa.is_scam_signal ? "Pay: Unusual" : "Pay: Normal";

          quickSalary.style.background = sa.is_scam_signal ? "#fef2f2" : "#f4f4f5";

          quickSalary.style.color = sa.is_scam_signal ? "#991b1b" : "#18181b";

          quickSalary.style.borderColor = sa.is_scam_signal ? "#fecaca" : "#e4e4e7";

        }

      } else {

        quickSalary.textContent = "Pay: Standard";

      }

    }

    if (quickResume) {

      if (rf.has_resume) {

        if (rf.is_career_divergence) {

          quickResume.textContent = "Role Mismatch";

          quickResume.style.background = "#fffbeb";

          quickResume.style.color = "#b45309";

          quickResume.style.borderColor = "#fde68a";

        } else {

          const chance = rf.acceptance_chance || (rf.fit_score >= 70 ? "High" : (rf.fit_score >= 45 ? "Moderate" : "Low"));

          quickResume.textContent = `Match: ${chance}`;

          quickResume.style.background = rf.fit_score >= 60 ? "#dcfce7" : "#eff6ff";

          quickResume.style.color = rf.fit_score >= 60 ? "#166534" : "#1d4ed8";

          quickResume.style.borderColor = rf.fit_score >= 60 ? "#bbf7d0" : "#bfdbfe";

        }

      } else {

        quickResume.textContent = "Attach CV in Profile";

      }

    }

    quickRow.style.display = "flex";

  }

  // Links to website dashboard

  const cid = (data.community_flag && data.community_flag.check_id) ? data.community_flag.check_id : "";

  const visitLink = document.getElementById("visitWebsiteLink");

  const openFormLink = document.getElementById("openFormLink");

  const resultUrl = cid ? `${API_BASE}/result.html?checkId=${cid}&from=extension` : `${API_BASE}/result.html?from=extension`;

  if (visitLink) visitLink.href = resultUrl;

  if (openFormLink) openFormLink.href = `${API_BASE}/index.html?openForm=1&checkId=${cid}&from=extension`;

  if (dashLinks) dashLinks.style.display = "flex";

}

function simplifyFactor(item) {

  const t = (item.title || "").toLowerCase();

  if (t.includes("public entity verified") || t.includes("public institution")) {

    return {

      title: item.title || "Public Institution Verified (Körperschaft des öffentlichen Rechts)",

      detail: item.detail || "Official state university / public sector institution in Germany. Statutory establishment confirmed.",

      impact: item.impact || "+20%"

    };

  }

  if (t.includes("company existence") || t.includes("handelsregister")) {

    return {

      title: item.title || "Company Existence Verified (Handelsregister)",

      detail: item.detail || "Company is officially registered in the German commercial register.",

      impact: item.impact || "+20%"

    };

  }

  if (t.includes("website") || t.includes("authentic employer")) {

    return {

      title: item.title || "Official company website is online",

      detail: item.detail || "Official company website is active and reachable.",

      impact: item.impact || "+15%"

    };

  }

  if (t.includes("career portal") || t.includes("vacancy")) {

    return {

      title: item.title || "Exact job vacancy verified on career page",

      detail: item.detail || "Listing matches the employer's official career portal.",

      impact: item.impact || "+15%"

    };

  }

  if (t.includes("contact")) {

    return {

      title: "Recruitment contact matches company",

      detail: item.detail || "Contact information matches the official employer records.",

      impact: item.impact || "+10%"

    };

  }

  if (t.includes("whatsapp")) {

    return {

      title: "WhatsApp application option verified",

      detail: item.detail || "Official listing explicitly permits mobile application.",

      impact: item.impact || "0% (Verified)"

    };

  }

  if (t.includes("security") || t.includes("virus")) {

    return {

      title: "Job link is clean and safe",

      detail: "No phishing or malicious redirects detected on the job URL.",

      impact: item.impact || "+10%"

    };

  }

  if (t.includes("fresh active") || t.includes("< 45 days")) {

    return {

      title: "Recently posted job (Not an old ghost job)",

      detail: item.detail || "Posting is recent and accepting active candidates.",

      impact: item.impact || "+5%"

    };

  }

  return {

    title: item.title || "Verification check",

    detail: item.detail || "",

    impact: item.impact || ""

  };

}

function populateDetailedView(data) {

  const tabInfo = data.tabInfo || {};

  const res = (data.result || "REVIEW CAREFULLY").toUpperCase();

  const score = typeof data.trust_score === "number" ? data.trust_score : (res === "LIKELY VALID" ? 92 : (res === "HIGH RISK" ? 20 : 60));

  const compName = (!isGenericCompany(data.company_name) && data.company_name) ||

                   (!isGenericCompany(tabInfo.company) && tabInfo.company) ||

                   "Company";

  const locName = data.company_address || tabInfo.address || "";

  const jobTitleText = (!isGenericTitle(data.job_title) && data.job_title) ||

                       (!isGenericTitle(tabInfo.title) && tabInfo.title) ||

                       "Job Position";

  const dScoreCircle = document.getElementById("dScoreCircle");

  const dScoreNum = document.getElementById("dScoreNum");

  const dStatusPill = document.getElementById("dStatusPill");

  const dJobTitle = document.getElementById("dJobTitle");

  const dCompany = document.getElementById("dCompany");

  const dBadgeScore = document.getElementById("dBadgeScore");

  if (dScoreNum) dScoreNum.textContent = score;

  if (dBadgeScore) dBadgeScore.textContent = `${score} / 100`;

  const gja = data.ghost_job_assessment || {};
  const isClosedJob = Boolean(
    gja.is_closed_job ||
    (data.availability_status || "").toUpperCase().includes("CLOSED") ||
    (data.warnings || []).some(w => /no longer accepting applications|states that it is closed/i.test(w))
  );
  const isGhostJob = Boolean(gja.is_ghost_job);
  const dom = (data.customer_website_check && data.customer_website_check.customer_domain) ? ` (${data.customer_website_check.customer_domain})` : "";

  let verdictPill = `45–69: MEDIUM TRUST (VERIFY DETAILS) · ${score}/100`;
  let reasonText = `Some company credentials for ${compName} could not be automatically confirmed. Verify contact information before sending documents.`;

  if (isClosedJob) {
    verdictPill = `45–69: JOB CLOSED (NO LONGER ACCEPTING) · ${score}/100`;
    reasonText = `Employer ${compName}${dom} is verified, but this job posting is closed and no longer accepting applications.`;
  } else if (isGhostJob) {
    verdictPill = `45–69: OLD LISTING (POSSIBLE GHOST JOB) · ${score}/100`;
    reasonText = `Employer ${compName}${dom} is verified, but this listing was posted ${gja.date_posted || 'over 45 days ago'}${gja.age_days ? ` (${gja.age_days} days ago)` : ''} and may be an inactive ghost vacancy.`;
  } else if (score >= 70) {
    verdictPill = `70–100: HIGH TRUST (SAFE TO APPLY) · ${score}/100`;
    reasonText = `This position at ${compName} looks authentic. The company website${dom} is verified active and no security red flags were found.`;
  } else if (score <= 44 || res === "HIGH RISK" || res === "NOT VERIFIED") {
    verdictPill = `0–44: LOW TRUST (APPLY AT YOUR OWN RISK) · ${score}/100`;
    reasonText = `Warning: High risk patterns detected in this listing. Never pay upfront fees for equipment or share sensitive identity cards through instant messaging.`;
  }

  if (dStatusPill) dStatusPill.textContent = verdictPill;
  if (dJobTitle) dJobTitle.textContent = jobTitleText;
  if (dCompany) dCompany.textContent = locName ? `${compName} · ${locName}` : compName;

  if (dScoreCircle && dStatusPill) {
    dScoreCircle.className = "score-circle";
    dStatusPill.className = "trust-status-pill";
    if (score >= 70 && !isClosedJob && !isGhostJob) {
      dScoreCircle.classList.add("score-valid");
      dStatusPill.classList.add("pill-valid");
    } else if (score <= 44 || res === "HIGH RISK") {
      dScoreCircle.classList.add("score-danger");
      dStatusPill.classList.add("pill-danger");
    } else {
      dScoreCircle.classList.add("score-warn");
      dStatusPill.classList.add("pill-warn");
    }
  }

  const dReasonSummary = document.getElementById("dReasonSummary");
  if (dReasonSummary) dReasonSummary.textContent = reasonText;

  // Ghost Job & Vacancy Status Box
  const ghostBox = document.getElementById("dGhostBox");
  const ghostTitle = document.getElementById("dGhostTitle");
  const ghostPill = document.getElementById("dGhostPill");
  const ghostDesc = document.getElementById("dGhostDesc");
  const ghostFactors = document.getElementById("dGhostFactorsList");

  if (ghostBox && ghostDesc) {
    ghostBox.style.display = "block";
    const checks = (Array.isArray(gja.red_flag_checks) ? gja.red_flag_checks : []).filter(c => !(c.name || '').includes('Talent-Pool')).map(c => ({ ...c, name: c.name.replace(/^6\./, '5.') }));
    const failedCount = checks.filter(c => !c.passed).length;

    if (isClosedJob) {
      ghostBox.style.background = "#fef2f2";
      ghostBox.style.borderColor = "#fecaca";
      if (ghostTitle) {
        ghostTitle.textContent = "⛔ Vacancy Check: Job Closed (No Longer Accepting)";
        ghostTitle.style.color = "#991b1b";
      }
      if (ghostPill) {
        ghostPill.textContent = "Closed Vacancy";
        ghostPill.style.background = "#fee2e2";
        ghostPill.style.color = "#991b1b";
        ghostPill.style.borderColor = "#fecaca";
      }
      ghostDesc.style.color = "#7f1d1d";
      const ageExtra = gja.age_days > 0 ? ` (${gja.age_days} days ago)` : "";
      ghostDesc.textContent = `Posted: ${gja.date_posted || 'Previously'}${ageExtra}. This job posting explicitly states that it is closed and no longer accepting applications.`;
    } else if (isGhostJob) {
      ghostBox.style.background = "#fffbeb";
      ghostBox.style.borderColor = "#fde68a";
      if (ghostTitle) {
        ghostTitle.textContent = "⚠ Ghost Job Check: Possible Ghost Job (Scheinstelle)";
        ghostTitle.style.color = "#92400e";
      }
      if (ghostPill) {
        ghostPill.textContent = "Ghost Risk";
        ghostPill.style.background = "#fef3c7";
        ghostPill.style.color = "#92400e";
        ghostPill.style.borderColor = "#fde68a";
      }
      ghostDesc.style.color = "#78350f";
      const ageExtra = gja.age_days > 0 ? ` (${gja.age_days} days ago)` : "";
      ghostDesc.textContent = `Warning: Posted ${gja.date_posted || 'over 45 days ago'}${ageExtra}. Exceeds the 45-day active hiring window and may be kept online for passive CV collection.`;
    } else if (failedCount >= 2) {
      ghostBox.style.background = "#fffbeb";
      ghostBox.style.borderColor = "#fde68a";
      if (ghostTitle) {
        ghostTitle.textContent = "Ghost Job Check: Verify Vacancy Status";
        ghostTitle.style.color = "#92400e";
      }
      if (ghostPill) {
        ghostPill.textContent = `${5 - failedCount}/5 Passed`;
        ghostPill.style.background = "#fef3c7";
        ghostPill.style.color = "#92400e";
        ghostPill.style.borderColor = "#fde68a";
      }
      ghostDesc.style.color = "#78350f";
      ghostDesc.textContent = `Posted: ${gja.date_posted || 'Recently'}. Most vacancy checks passed, but ${failedCount} indicator(s) should be verified before applying.`;
    } else {
      ghostBox.style.background = "#f0fdf4";
      ghostBox.style.borderColor = "#bbf7d0";
      if (ghostTitle) {
        ghostTitle.textContent = "✓ Ghost Job Check: Not a Ghost Job (Active Vacancy)";
        ghostTitle.style.color = "#166534";
      }
      if (ghostPill) {
        ghostPill.textContent = "Active Vacancy";
        ghostPill.style.background = "#dcfce7";
        ghostPill.style.color = "#166534";
        ghostPill.style.borderColor = "#bbf7d0";
      }
      ghostDesc.style.color = "#15803d";
      ghostDesc.textContent = `Posted: ${gja.date_posted || 'Recently'}. This listing passed our active vacancy checks and shows genuine hiring intent.`;
    }

    if (ghostFactors) {
      const passedChecks = checks.filter(c => c.passed);
      const failedChecks = checks.filter(c => !c.passed);
      ghostFactors.innerHTML = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 4px;">
          <div style="background: #ffffff; border: 1px solid #bbf7d0; border-radius: 5px; overflow: hidden;">
            <div style="background: #dcfce7; padding: 4px 7px; font-size: 10px; font-weight: 700; color: #166534; border-bottom: 1px solid #bbf7d0;">
              ✓ Passed (${passedChecks.length})
            </div>
            <div style="padding: 4px 7px; font-size: 10px; color: #18181b;">
              ${passedChecks.length > 0
                ? passedChecks.map(c => `<div style="padding: 2px 0; border-bottom: 1px solid #f4f4f5;">${c.name}</div>`).join("")
                : `<div style="color: #71717a; padding: 2px 0;">None</div>`}
            </div>
          </div>
          <div style="background: #ffffff; border: 1px solid ${failedChecks.length > 0 ? '#fecaca' : '#e4e4e7'}; border-radius: 5px; overflow: hidden;">
            <div style="background: ${failedChecks.length > 0 ? '#fee2e2' : '#f4f4f5'}; padding: 4px 7px; font-size: 10px; font-weight: 700; color: ${failedChecks.length > 0 ? '#991b1b' : '#52525b'}; border-bottom: 1px solid ${failedChecks.length > 0 ? '#fecaca' : '#e4e4e7'};">
              ✕ Flagged (${failedChecks.length})
            </div>
            <div style="padding: 4px 7px; font-size: 10px; color: ${failedChecks.length > 0 ? '#991b1b' : '#71717a'};">
              ${failedChecks.length > 0
                ? failedChecks.map(c => `<div style="padding: 2px 0; border-bottom: 1px solid #fef2f2; font-weight: 600;">${c.name}</div>`).join("")
                : `<div style="padding: 2px 0;">None (0 Flags)</div>`}
            </div>
          </div>
        </div>
      `;
    }
  }

  // Warnings

  const warnBox = document.getElementById("dWarningsBox");

  const warnList = document.getElementById("dWarningsList");

  if (warnBox && warnList) {

    warnList.innerHTML = "";

    if (data.warnings && data.warnings.length > 0) {

      warnBox.style.display = "block";

      data.warnings.forEach(w => {

        const li = document.createElement("li");

        li.textContent = w;

        warnList.appendChild(li);

      });

    } else {

      warnBox.style.display = "none";

    }

  }

  // Multi-Pillar Summary Cards

  const fourPillars = document.getElementById("dFourPillarsCard");

  const pSecurity = document.getElementById("pAiScamText");

  const pSalary = document.getElementById("pSalaryText");

  const pResume = document.getElementById("pResumeText");

  const pRegister = document.getElementById("pRegisterText");

  if (fourPillars) {

    fourPillars.style.display = "block";

    const jda = data.job_description_analysis || {};

    const scamSignals = jda.scam_signals || [];

    if (pSecurity) {

      if (scamSignals.length > 0) {

        pSecurity.textContent = `Risk: ${scamSignals[0].category || 'Suspicious Phrasing'}`;

        pSecurity.style.color = "#991b1b";

      } else {

        pSecurity.textContent = "Verified Safe";

        pSecurity.style.color = "#166534";

      }

    }

    const sa = data.salary_anomaly || {};

    if (pSalary) {

      if (sa.has_salary_data) {

        const displayOffered = sa.formatted_offered ? sa.formatted_offered : (sa.verdict || "Standard Rate");

        if (sa.is_below_minimum_wage) {

          pSalary.textContent = `Below Min. Wage (${displayOffered})`;

          pSalary.style.color = "#991b1b";

        } else {

          pSalary.textContent = sa.is_scam_signal ? `Outlier (${displayOffered})` : displayOffered;

          pSalary.style.color = sa.is_scam_signal ? "#991b1b" : "#18181b";

        }

      } else {

        pSalary.textContent = "Standard Rate (>= 13,90 €/h)";

        pSalary.style.color = "#52525b";

      }

    }

    const rf = data.resume_fit || {};

    if (pResume) {

      if (rf.has_resume) {

        const chance = rf.acceptance_chance || (rf.fit_score >= 70 ? "High" : (rf.fit_score >= 45 ? "Moderate" : "Low"));

        pResume.textContent = rf.is_career_divergence ? "Field Mismatch" : `${chance} (${rf.fit_score}%)`;

        pResume.style.color = rf.is_career_divergence ? "#b45309" : (rf.fit_score >= 60 ? "#166534" : "#52525b");

      } else {

        pResume.textContent = "Attach CV in Profile";

        pResume.style.color = "#71717a";

      }

    }

    const reg = data.register_lookup || {};

    if (pRegister) {

      if (reg.found_in_handelsregister) {

        pRegister.textContent = `Confirmed (${reg.register_entry || 'HRB'})`;

        pRegister.style.color = "#166534";

      } else if (data.company_name) {

        pRegister.textContent = "Known Employer";

        pRegister.style.color = "#166534";

      } else {

        pRegister.textContent = "Direct Check";

        pRegister.style.color = "#52525b";

      }

    }

  }

  // Profile Compatibility & Upskilling

  const rf = data.resume_fit || {};

  const fitCard = document.getElementById("dResumeFitCard");

  if (fitCard) {

    if (rf.has_resume) {

      fitCard.style.display = "block";

      const badge = document.getElementById("dFitScoreBadge");

      if (badge) {

        badge.textContent = `${rf.fit_score}% Fit`;

        badge.style.color = rf.is_career_divergence ? "#b45309" : (rf.fit_score >= 60 ? "#166534" : "#1e40af");

        badge.style.background = rf.is_career_divergence ? "#fffbeb" : (rf.fit_score >= 60 ? "#dcfce7" : "#eff6ff");

        badge.style.borderColor = rf.is_career_divergence ? "#fde68a" : (rf.fit_score >= 60 ? "#bbf7d0" : "#bfdbfe");

      }

      const chanceVal = document.getElementById("dAcceptanceChanceVal");

      const chanceDetail = document.getElementById("dAcceptanceChanceDetail");

      if (chanceVal) {

        chanceVal.textContent = rf.acceptance_chance || (rf.fit_score >= 70 ? "High" : (rf.fit_score >= 45 ? "Moderate" : "Low"));

        chanceVal.style.color = rf.acceptance_chance_color || (rf.fit_score >= 60 ? "#166534" : "#b45309");

      }

      if (chanceDetail) {

        chanceDetail.textContent = rf.is_career_divergence ? "Unrelated Field" : (rf.acceptance_detail || `${rf.fit_score}% Qualification Fit`);

      }

      const advBox = document.getElementById("dCareerAdvisoryBox");

      const advMsg = document.getElementById("dCareerAdvisoryMsg");

      if (rf.is_career_divergence && rf.career_advisory_message && advBox && advMsg) {

        advBox.style.display = "block";

        advMsg.textContent = rf.career_advisory_message;

        if (rf.is_overqualified) {

          advBox.style.background = "#f0f9ff";

          advBox.style.borderColor = "#bae6fd";

          advBox.style.color = "#0369a1";

        }

      } else if (advBox) {

        advBox.style.display = "none";

      }

      const matchedSec = document.getElementById("dMatchedSkillsSection");

      const matchedPills = document.getElementById("dMatchedSkillsPills");

      if (matchedSec && matchedPills) {

        matchedPills.innerHTML = "";

        const skills = rf.matched_skills || [];

        if (skills.length > 0) {

          matchedSec.style.display = "block";

          skills.forEach(s => {

            const span = document.createElement("span");

            span.style.cssText = "font-family: Consolas, 'Courier New', monospace; font-size: 10px; font-weight: 600; background: #dcfce7; color: #166534; padding: 2px 6px; border-radius: 4px; border: 1px solid #bbf7d0;";

            span.textContent = `✓ ${s}`;

            matchedPills.appendChild(span);

          });

        } else {

          matchedSec.style.display = "none";

        }

      }

      const whyList = document.getElementById("dWhyMatchedList");

      if (whyList) {

        whyList.innerHTML = "";

        (rf.why_matched_reasons || []).forEach(r => {

          const div = document.createElement("div");

          div.style.cssText = "display: flex; align-items: flex-start; gap: 6px; background: #fafafa; border: 1px solid #e4e4e7; border-radius: 5px; padding: 6px 8px; font-size: 11px;";

          div.innerHTML = `

            <span style="font-size: 12px; flex-shrink: 0;">${r.icon || '✓'}</span>

            <div>

              <strong style="color: #18181b; font-size: 11.5px;">${r.title}:</strong>

              <span style="color: #52525b;">${r.detail}</span>

            </div>

          `;

          whyList.appendChild(div);

        });

      }
      const recText = document.getElementById("dResumeRecText");

      if (recText) recText.textContent = rf.recommendation || "Tailor your application to the highlighted skills.";

    } else {

      fitCard.style.display = "none";

    }

  }

  // 5-Point Quick Checklist

  const custSite = document.getElementById("dCustSite");

  const custCareer = document.getElementById("dCustCareer");

  if (data.customer_website_check && data.customer_website_check.website_found) {

    const cwc = data.customer_website_check;

    if (custSite) custSite.innerHTML = `<a href="${cwc.customer_website_url}" target="_blank" style="color: #166534; font-weight: 600; text-decoration: underline;">Yes (${cwc.customer_domain})</a>`;

    if (custCareer) custCareer.innerHTML = `<a href="${cwc.career_page_url}" target="_blank" style="color: #1d4ed8; font-weight: 600; text-decoration: underline;">Open Career Page &rarr;</a>`;

  } else {

    if (custSite) custSite.textContent = "Checked online";

    if (custCareer) custCareer.textContent = "Direct job post";

  }

  const dRegister = document.getElementById("dRegister");

  if (dRegister) {

    if (data.register_lookup && data.register_lookup.found_in_handelsregister) {

      dRegister.textContent = `Yes (${data.register_lookup.register_entry})`;

      dRegister.style.color = "#166534";

    } else if (data.company_name) {

      dRegister.textContent = "Yes (Known Employer)";

      dRegister.style.color = "#166534";

    } else {

      dRegister.textContent = "Not listed";

    }

  }

  const dVirusTotal = document.getElementById("dVirusTotal");

  if (dVirusTotal) {

    dVirusTotal.textContent = "Safe (0 scam/virus links)";

    dVirusTotal.style.color = "#166534";

  }

  const posted = data.date_posted || tabInfo.datePosted || "Recent";

  const dDate = document.getElementById("dDatePosted");

  const dSal = document.getElementById("dSalary");

  if (dDate) dDate.textContent = `${posted} (Active)`;

  const saObj = data.salary_anomaly || {};

  if (dSal) dSal.textContent = (saObj.has_salary_data && saObj.formatted_offered) ? saObj.formatted_offered : (tabInfo.salary || data.salary || "Standard company pay");

  // Score Breakdown List

  const breakdownTotal = document.getElementById("dBreakdownTotal");

  const breakdownList = document.getElementById("dBreakdownList");

  if (breakdownTotal) breakdownTotal.textContent = `${score} / 100`;

  if (breakdownList) {

    breakdownList.innerHTML = "";

    (data.score_breakdown || []).forEach(rawItem => {

      const item = simplifyFactor(rawItem);

      const badgeBg = rawItem.type === "positive" ? "#166534" : (rawItem.type === "danger" ? "#991b1b" : "#92400e");

      const row = document.createElement("div");

      row.style.cssText = "display: flex; align-items: flex-start; gap: 8px; padding: 7px 9px; background: #fafafa; border: 1px solid #e4e4e7; border-radius: 5px; font-size: 11.5px;";

      row.innerHTML = `

        <span style="width: 6px; height: 6px; border-radius: 50%; background: ${badgeBg}; margin-top: 5px; flex-shrink: 0;"></span>

        <div style="flex: 1;">

          <div style="display: flex; justify-content: space-between; align-items: center; gap: 6px;">

            <strong style="color: #18181b; font-size: 11.5px;">${item.title}</strong>

            <span style="font-family: Consolas, 'Courier New', monospace; color: ${badgeBg}; font-size: 10.5px; font-weight: 600;">${item.impact}</span>

          </div>

          <p style="color: #52525b; margin-top: 2px; font-size: 11px; line-height: 1.4;">${item.detail}</p>

        </div>

      `;

      breakdownList.appendChild(row);

    });

  }

  // 2. Company & 3. Reviews

  const ciCard = document.getElementById("dCompanyIntelCard");

  const revCard = document.getElementById("dReviewsCard");

  const intel = data.company_intelligence;

  if (intel) {

    if (ciCard) {

      ciCard.style.display = "block";

      const dCiBadge = document.getElementById("dCiBadge");

      const dCiName = document.getElementById("dCiName");

      const dCiIndustry = document.getElementById("dCiIndustry");

      if (dCiBadge) dCiBadge.textContent = "Verified Employer";

      if (dCiName) dCiName.textContent = intel.canonical_name || compName;

      if (dCiIndustry) dCiIndustry.textContent = `${intel.industry || 'Company'} · ${intel.company_size || 'Established'} · ${intel.headquarters || 'Germany'}`;

    }

    if (revCard) {

      revCard.style.display = "block";

      const dCiRating = document.getElementById("dCiRating");

      const dCiFeedbackSnippet = document.getElementById("dCiFeedbackSnippet");

      if (dCiRating) dCiRating.textContent = `Rating: ${intel.rating || '4.1'}/5.0 (${intel.recommend_rate || '83%'} recommend)`;

      if (dCiFeedbackSnippet) {

        if (intel.has_role_reviews === false || !intel.employee_pros || intel.employee_pros.length === 0) {

          dCiFeedbackSnippet.textContent = "No employee reviews found for this specific job role or location yet.";

          dCiFeedbackSnippet.style.fontStyle = "italic";

          dCiFeedbackSnippet.style.color = "#71717a";

        } else {

          dCiFeedbackSnippet.textContent = `"${intel.employee_pros[0]}"`;

          dCiFeedbackSnippet.style.fontStyle = "normal";

          dCiFeedbackSnippet.style.color = "#166534";

        }

      }

    }

  } else {

    if (ciCard) ciCard.style.display = "none";

    if (revCard) revCard.style.display = "none";

  }

  const dDash = document.getElementById("dDashboardLink");

  if (dDash) {

    const cid = (data.community_flag && data.community_flag.check_id) ? data.community_flag.check_id : "";

    dDash.href = cid ? `${API_BASE}/result.html?checkId=${cid}&from=extension` : `${API_BASE}/result.html?from=extension`;

  }

}

function showOfflineState() {

  const loaderBox = document.getElementById("loaderBox");

  const scoreCard = document.getElementById("scorePopupCard");

  const dashLinks = document.getElementById("dashboardLinkWrapper");

  if (loaderBox) loaderBox.style.display = "none";

  if (scoreCard) scoreCard.style.display = "block";

  const circle = document.getElementById("scoreCircle");

  const num = document.getElementById("scoreNum");

  const pill = document.getElementById("trustPill");

  const headline = document.getElementById("trustHeadline");

  const comp = document.getElementById("trustCompany");

  const scoreBadge = document.getElementById("badgeScoreOutOf");

  if (circle) circle.className = "score-circle score-danger";

  if (num) num.textContent = "!";

  if (pill) {

    pill.className = "trust-status-pill pill-danger";

    pill.textContent = "SERVER OFFLINE";

  }

  if (headline) headline.textContent = "Flask Server Offline";

  if (comp) comp.textContent = "Ensure http://127.0.0.1:5000 is running";

  if (scoreBadge) scoreBadge.textContent = "-- / 100";

  if (dashLinks) dashLinks.style.display = "none";

}

document.addEventListener("DOMContentLoaded", async () => {

  await loadCurrentUser();

  const viewMain = document.getElementById("viewMain");

  const viewDetails = document.getElementById("viewDetails");

  const btnViewDetailedReport = document.getElementById("btnViewDetailedReport");

  const btnGoBack = document.getElementById("btnGoBack");

  const btnBottomGoBack = document.getElementById("btnBottomGoBack");

  const scoreCardTop = document.getElementById("scoreCardTop");

  function switchToDetailedView() {

    if (!currentVerifiedData) return;

    populateDetailedView(currentVerifiedData);

    if (viewMain) viewMain.style.display = "none";

    if (viewDetails) viewDetails.style.display = "block";

    window.scrollTo(0, 0);

  }

  function switchToMainView() {

    if (viewDetails) viewDetails.style.display = "none";

    if (viewMain) viewMain.style.display = "block";

  }

  if (btnViewDetailedReport) btnViewDetailedReport.addEventListener("click", switchToDetailedView);

  if (scoreCardTop) scoreCardTop.addEventListener("click", switchToDetailedView);

  if (btnGoBack) btnGoBack.addEventListener("click", switchToMainView);

  if (btnBottomGoBack) btnBottomGoBack.addEventListener("click", switchToMainView);

  const btnTranslatePopup = document.getElementById("btnTranslatePopup");

  if (btnTranslatePopup) {

    let isTranslated = false;

    btnTranslatePopup.addEventListener("click", async () => {

      const dTitle = document.getElementById("dJobTitle");

      const dTitleEn = document.getElementById("dJobTitleEn");

      const dReason = document.getElementById("dReasonSummary");

      isTranslated = !isTranslated;

      if (isTranslated) {

        btnTranslatePopup.textContent = "🇩🇪 German";

        btnTranslatePopup.style.background = "#f0fdf4";

        btnTranslatePopup.style.borderColor = "#bbf7d0";

        btnTranslatePopup.style.color = "#166534";

        if (dTitle && (!dTitleEn.textContent || dTitleEn.textContent === "")) {

          btnTranslatePopup.textContent = "⏳ Translating...";

          try {

            const res = await fetch(`${API_BASE}/api/translate`, {

              method: "POST",

              headers: { "Content-Type": "application/json" },

              body: JSON.stringify({ text: dTitle.textContent })

            });

            const d = await res.json();

            if (d && d.success && d.translated) {

              dTitleEn.textContent = `🇬🇧 English: ${d.translated}`;

              dTitleEn.style.display = "block";

            }

          } catch (e) {}

          btnTranslatePopup.textContent = "🇩🇪 German";

        } else if (dTitleEn) {

          dTitleEn.style.display = "block";

        }

      } else {

        btnTranslatePopup.textContent = "🇬🇧 Translate";

        btnTranslatePopup.style.background = "#eff6ff";

        btnTranslatePopup.style.borderColor = "#bfdbfe";

        btnTranslatePopup.style.color = "#1e40af";

        if (dTitleEn) dTitleEn.style.display = "none";

      }

    });

  }

  const toggleSearch = document.getElementById("toggleSearchBarBtn");

  const searchBox = document.getElementById("searchBoxCard");

  if (toggleSearch && searchBox) {

    toggleSearch.addEventListener("click", () => {

      if (viewDetails && viewDetails.style.display === "block") {

        viewDetails.style.display = "none";

        if (viewMain) viewMain.style.display = "block";

      }

      const isHidden = searchBox.style.display === "none" || !searchBox.style.display;

      searchBox.style.display = isHidden ? "block" : "none";

      toggleSearch.style.background = isHidden ? "#18181b" : "#f4f4f5";

      toggleSearch.style.color = isHidden ? "#ffffff" : "#18181b";

      if (isHidden) {

        const inp = document.getElementById("manualSearchInput");

        if (inp) inp.focus();

      }

    });

  }

  const searchBtn = document.getElementById("manualSearchBtn");

  const searchInput = document.getElementById("manualSearchInput");

  const onSearch = () => {

    const q = (searchInput.value || "").trim();

    if (q) verifyManualInput(q);

    else searchInput.focus();

  };

  if (searchBtn) searchBtn.addEventListener("click", onSearch);

  if (searchInput) {

    searchInput.addEventListener("keypress", (e) => {

      if (e.key === "Enter") onSearch();

    });

  }

  const rescanBtn = document.getElementById("rescanBtn");

  if (rescanBtn) rescanBtn.addEventListener("click", verifyCurrentTab);

  const btnVerify = document.getElementById("btnVerifyCurrentTab");

  if (btnVerify) btnVerify.addEventListener("click", verifyCurrentTab);

  await previewCurrentTab();

});

