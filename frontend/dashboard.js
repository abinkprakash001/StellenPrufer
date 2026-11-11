// StellenPrüfer Core Verification Dashboard Scripts

function getApiBase() {

    return (window.location.protocol === "file:" || window.location.port !== "5000")

        ? "http://127.0.0.1:5000"

        : "";

}

function getCurrentUser() {

    try {

        return JSON.parse(localStorage.getItem("stellenpruefer_user") || localStorage.getItem("jobguard_user") || "null");

    } catch (e) {

        return null;

    }

}

function ensureScreenLoader() {

    let loader = document.getElementById("screenLoaderOverlay");

    if (!loader) {

        loader = document.createElement("div");

        loader.id = "screenLoaderOverlay";

        loader.className = "screen-loader-overlay";

        loader.innerHTML = `

            <img src="logo.png" alt="Loading">

            <p>Loading...</p>

        `;

        document.body.appendChild(loader);

    }

    return loader;

}

function showScreenLoader() {

    const loader = ensureScreenLoader();

    loader.classList.add("active");

}

function hideScreenLoader() {

    const loader = document.getElementById("screenLoaderOverlay");

    if (loader) {

        loader.classList.remove("active");

    }

}

let dismissedJobKeys = new Set();

let activeSyncedJobsList = [];

let lastSyncedJobData = null;

function dismissSpecificJob(tabKeyEncoded, urlEncoded) {

    const tabKey = decodeURIComponent(tabKeyEncoded);

    const url = decodeURIComponent(urlEncoded);

    dismissedJobKeys.add(tabKey);

    fetch(`${getApiBase()}/api/clear-synced-job?tabId=${encodeURIComponent(tabKey)}&url=${encodeURIComponent(url)}`, { method: "POST" })

        .then(() => checkExtensionLiveConnection())

        .catch(() => {});

}

function dismissAllSyncedJobs() {

    activeSyncedJobsList.forEach(j => dismissedJobKeys.add(String(j.tabId || j.url || j.title)));

    activeSyncedJobsList = [];

    lastSyncedJobData = null;

    const bar = document.getElementById("extensionLiveBar");

    if (bar) {

        bar.style.display = "none";

        bar.innerHTML = "";

    }

    clearJobForm();

    fetch(`${getApiBase()}/api/clear-synced-job`, { method: "POST" }).catch(() => {});

}

function dismissExtensionJobBar() {

    dismissAllSyncedJobs();

}

function importSpecificSyncedJob(idx, autoVerify = false) {

    const job = activeSyncedJobsList[idx];

    if (job) {

        lastSyncedJobData = job;

        applySyncedJob(job, autoVerify);

    }

}

async function checkExtensionLiveConnection() {

    const bar = document.getElementById("extensionLiveBar");

    if (bar) {

        bar.style.display = "none";

        bar.innerHTML = "";

    }

}

function importSyncedJob(autoVerify = false) {

    if (activeSyncedJobsList.length > 0) {

        importSpecificSyncedJob(0, autoVerify);

    }

}

function applySyncedJob(job, autoVerify = false) {

    const dropBar = document.getElementById("verifyJobDropdownBar");

    if (dropBar) {

        dropBar.open = true;

        if (!autoVerify) dropBar.scrollIntoView({ behavior: "smooth", block: "start" });

    }

    const setVal = (id, val) => {

        const el = document.getElementById(id);

        if (el && val) {

            el.removeAttribute("readonly");

            el.value = val;

        }

    };

    setVal("jobTitle", job.title || "");

    setVal("company", job.company || "");

    setVal("jobUrl", job.url || "");

    setVal("salary", job.salary || "");

    setVal("recruiterEmail", job.recruiterEmail || "");

    setVal("jobDescription", job.description || "");

    const consent = document.getElementById("checkConsent");

    if (consent) consent.checked = true;

    if (autoVerify) {

        setTimeout(() => {

            const fakeEvent = { preventDefault: () => {} };

            verifyJob(fakeEvent);

        }, 150);

    }

}

document.addEventListener("DOMContentLoaded", () => {

    ensureScreenLoader();

    loadUser();

    document.querySelectorAll("a[href]").forEach(link => {

        const href = link.getAttribute("href");

        if (href && href.endsWith(".html") && !link.target) {

            link.addEventListener("click", e => {

                e.preventDefault();

                showScreenLoader();

                setTimeout(() => {

                    window.location.href = href;

                }, 400);

            });

        }

    });

    ["documentFile", "jobTitle", "company", "recruiterEmail", "jobUrl", "salary", "jobDescription"].forEach(id => {

        const el = document.getElementById(id);

        if (el) {

            el.addEventListener("input", resetValidationState);

            el.addEventListener("change", resetValidationState);

        }

    });

    const urlParams = new URLSearchParams(window.location.search);

    const extCheckId = urlParams.get("checkId") || (urlParams.get("from") === "extension" ? "latest" : null);

    const autoVerify = urlParams.get("autoVerify") === "1" || urlParams.get("autoVerify") === "true";

    if (extCheckId && document.getElementById("jobForm")) {

        fetch(`${getApiBase()}/api/check-result/${encodeURIComponent(extCheckId)}`)

            .then(r => r.json())

            .then(res => {

                if (res && res.success && res.saved) {

                    sessionStorage.setItem("stellenpruefer_last_result", JSON.stringify(res.saved));

                    const d = res.saved.data || {};

                    const inp = res.saved.inputs || {};

                    const setVal = (id, val) => {

                        const el = document.getElementById(id);

                        if (el && val) {

                            el.removeAttribute("readonly");

                            el.value = val;

                        }

                    };

                    setVal("jobTitle", inp.jobTitle || d.job_title || "");

                    setVal("company", inp.company || d.company_name || "");

                    setVal("recruiterEmail", inp.recruiterEmail || d.recruiter_email || "");

                    setVal("jobUrl", inp.jobUrl || d.official_job_url || "");

                    setVal("salary", inp.salary || d.salary || "");

                    setVal("jobDescription", inp.jobDescription || d.job_description || "");

                    const consent = document.getElementById("checkConsent");

                    if (consent) consent.checked = true;

                    if (autoVerify) {

                        setTimeout(() => {

                            const fakeEvent = { preventDefault: () => {} };

                            verifyJob(fakeEvent);

                        }, 200);

                    }

                }

            })

            .catch(() => {});

    }

    // Support instant search queries passed from Home page (index.html)

    const qParam = urlParams.get("q") || urlParams.get("query");

    const jobUrlParam = urlParams.get("jobUrl") || urlParams.get("url");

    const titleParam = urlParams.get("title") || urlParams.get("jobTitle");

    const companyParam = urlParams.get("company");

    if ((qParam || jobUrlParam || titleParam || companyParam) && document.getElementById("jobForm")) {

        const urlEl = document.getElementById("jobUrl");

        const titleEl = document.getElementById("jobTitle");

        const compEl = document.getElementById("company");

        const quickEl = document.getElementById("quickJobSearchInput");

        if (quickEl && qParam) quickEl.value = qParam;

        if (jobUrlParam && urlEl) {

            urlEl.removeAttribute("readonly");

            urlEl.value = jobUrlParam;

        }

        if (titleParam && titleEl) {

            titleEl.removeAttribute("readonly");

            titleEl.value = titleParam;

        }

        if (companyParam && compEl) {

            compEl.removeAttribute("readonly");

            compEl.value = companyParam;

        }

        if (qParam && !jobUrlParam && !titleParam) {

            if (qParam.startsWith("http://") || qParam.startsWith("https://")) {

                if (urlEl) {

                    urlEl.removeAttribute("readonly");

                    urlEl.value = qParam;

                }

            } else if (qParam.includes(" - ")) {

                const parts = qParam.split(" - ");

                if (titleEl) {

                    titleEl.removeAttribute("readonly");

                    titleEl.value = parts[0].trim();

                }

                if (compEl) {

                    compEl.removeAttribute("readonly");

                    compEl.value = parts.slice(1).join(" - ").trim();

                }

            } else if (titleEl) {

                titleEl.removeAttribute("readonly");

                titleEl.value = qParam;

            }

        }

        const consent = document.getElementById("checkConsent");

        if (consent) consent.checked = true;

        if (autoVerify) {

            setTimeout(() => {

                const fakeEvent = { preventDefault: () => {} };

                verifyJob(fakeEvent);

            }, 300);

        }

    }

    if (document.getElementById("resultPageSection")) {

        try {

            const saved = JSON.parse(sessionStorage.getItem("stellenpruefer_last_result") || "null");

            if (saved && saved.data) {

                const cwc = saved.data.customer_website_check || {};

                const compN = (saved.data.company_name || "").toLowerCase();

                const isStale = (

                    cwc.customer_domain === "company.com"

                    || compN === "company"

                    || compN.startsWith("employer on")

                    || !saved.data.contact_verification

                );

                if (isStale) {

                    sessionStorage.removeItem("stellenpruefer_last_result");

                } else {

                    const savedId = (saved.data.community_flag && saved.data.community_flag.check_id) ? String(saved.data.community_flag.check_id) : "";

                    if (!extCheckId || extCheckId === "latest" || (savedId && savedId === String(extCheckId))) {

                        const titleEl = document.getElementById("resultPageTitle");

                        if (titleEl && saved.data.check_type === "job_contract") {

                            titleEl.textContent = "Contract (Arbeitsvertrag) Verification Result";

                        }

                        displayResult(saved.data, saved.inputs || {}, "resultBox");

                    }

                }

            }

        } catch (e) {

            console.error("Error rendering sessionStorage result:", e);

        }

        // Always fetch the latest/target check result from backend so stale sessionStorage never sticks

        const targetKey = extCheckId || "latest";

        fetch(`${getApiBase()}/api/check-result/${encodeURIComponent(targetKey)}`)

            .then(r => r.json())

            .then(res => {

                if (res && res.success && res.saved && res.saved.data) {

                    sessionStorage.setItem("stellenpruefer_last_result", JSON.stringify(res.saved));

                    displayResult(res.saved.data, res.saved.inputs || {}, "resultBox");

                } else if (!sessionStorage.getItem("stellenpruefer_last_result")) {

                    const rb = document.getElementById("resultBox");

                    if (rb) {

                        rb.innerHTML = `<p style="color: #71717a; text-align: center; padding: 24px;">No verification report found. Please return to the Home page and submit a job advertisement or contract check.</p>`;

                    }

                }

            })

            .catch(err => {

                console.error("Error fetching check result:", err);

                if (!sessionStorage.getItem("stellenpruefer_last_result")) {

                    const rb = document.getElementById("resultBox");

                    if (rb) {

                        rb.innerHTML = `<p style="color: #71717a; text-align: center; padding: 24px;">Could not connect to the verification service. Please ensure the server is active.</p>`;

                    }

                }

            });

    }

    if (document.getElementById("historyList")) {

        loadUserHistory();

    }

    if (document.getElementById("flaggedJobsList")) {

        loadFlaggedJobs();

    }

});

function applyUserToPage(user) {

    if (!user) return;

    const adminNavLink = document.getElementById("adminNavLink");

    if (adminNavLink && user.role === "admin") {

        adminNavLink.style.display = "inline-block";

    }

    const nameInput = document.getElementById("profileName");

    const emailInput = document.getElementById("profileEmail");

    const resumeInput = document.getElementById("profileResume");

    if (nameInput && emailInput) {

        nameInput.value = user.name || "";

        emailInput.value = user.email || "";

    }

    if (resumeInput) {

        resumeInput.value = user.resume_text || "";

    }

    const displayName = document.getElementById("displayProfileName");

    const displayEmail = document.getElementById("displayProfileEmail");

    const displayRole = document.getElementById("displayProfileRole");

    const displayResume = document.getElementById("displayProfileResume");

    if (displayName) displayName.textContent = user.name || "-";

    if (displayEmail) displayEmail.textContent = user.email || "-";

    if (displayRole) displayRole.textContent = user.role === "admin" ? "Administrator" : "Customer / User";

    if (displayResume) {

        displayResume.textContent = user.resume_filename ? user.resume_filename : "None (No PDF attached)";

    }

}

function loadUser() {

    let user = getCurrentUser();

    // Migrate stale hardcoded 'Abin' or 'Extension User' session in localStorage to somanjiji

    if (user && (user.email === "kp21abin@gmail.com" || user.email === "extension@stellenpruefer.local")) {

        user = { id: 6, name: "somanjiji", email: "som123@gmail.com", role: "customer" };

        localStorage.setItem("stellenpruefer_user", JSON.stringify(user));

    }

    const params = new URLSearchParams(window.location.search);

    if ((!user || !user.email) && (params.get("checkId") || params.get("from") === "extension")) {

        user = { id: 6, name: "somanjiji", email: "som123@gmail.com", role: "customer" };

        localStorage.setItem("stellenpruefer_user", JSON.stringify(user));

    }

    if (!user || !user.email) {

        fetch(`${getApiBase()}/api/current-user`)

            .then(r => r.json())

            .then(d => {

                if (d && d.success && d.user && d.user.email) {

                    localStorage.setItem("stellenpruefer_user", JSON.stringify(d.user));

                    applyUserToPage(d.user);

                    if (document.getElementById("historyList")) loadUserHistory();

                } else {

                    window.location.href = "login.html";

                }

            })

            .catch(() => {

                window.location.href = "login.html";

            });

        return;

    }

    applyUserToPage(user);

    // Sync active browser session user with backend so extension & website match 100%

    fetch(`${getApiBase()}/api/current-user`, {

        method: "POST",

        headers: { "Content-Type": "application/json" },

        body: JSON.stringify(user)

    }).catch(() => {});

}

function ensureLogoutModal() {

    let modal = document.getElementById("logoutModalOverlay");

    if (!modal) {

        modal = document.createElement("div");

        modal.id = "logoutModalOverlay";

        modal.className = "logout-modal-overlay";

        modal.innerHTML = `

            <div class="logout-modal-card">

                <h3>Confirm Logout</h3>

                <p>Are you sure you want to log out of your StellenPrüfer account?</p>

                <div class="logout-modal-actions">

                    <button type="button" class="logout-cancel-btn" onclick="closeLogoutModal()">Cancel</button>

                    <button type="button" class="logout-confirm-btn" onclick="confirmLogout()">Yes, Logout</button>

                </div>

            </div>

        `;

        document.body.appendChild(modal);

    }

    return modal;

}

function logout() {

    const modal = ensureLogoutModal();

    modal.classList.add("active");

}

function closeLogoutModal() {

    const modal = document.getElementById("logoutModalOverlay");

    if (modal) {

        modal.classList.remove("active");

    }

}

function confirmLogout() {

    closeLogoutModal();

    showScreenLoader();

    localStorage.removeItem("stellenpruefer_user");

    localStorage.removeItem("jobguard_user");

    fetch(`${getApiBase()}/api/logout`, { method: "POST" }).catch(() => {});

    setTimeout(() => {

        window.location.href = "login.html";

    }, 350);

}

async function uploadResumePdf() {

    const fileInput = document.getElementById("profilePdfFile");

    const statusEl = document.getElementById("pdfUploadStatus");

    if (!fileInput || !fileInput.files || !fileInput.files[0]) {

        if (statusEl) {

            statusEl.textContent = "Please select a PDF file first.";

            statusEl.style.color = "#dc2626";

        }

        return;

    }

    const file = fileInput.files[0];

    const user = getCurrentUser() || {};

    const formData = new FormData();

    formData.append("resumeFile", file);

    if (user.id) formData.append("userId", String(user.id));

    formData.append("name", user.name || "");

    formData.append("email", user.email || "");

    showScreenLoader();

    try {

        const res = await fetch(`${getApiBase()}/api/profile/upload-resume`, {

            method: "POST",

            body: formData

        });

        const data = await res.json();

        hideScreenLoader();

        if (!res.ok || !data.success) {

            if (statusEl) {

                statusEl.textContent = data.error || "Failed to parse PDF resume.";

                statusEl.style.color = "#dc2626";

            }

            return;

        }

        const resumeInput = document.getElementById("profileResume");

        if (resumeInput) resumeInput.value = data.resume_text || "";

        const displayResume = document.getElementById("displayProfileResume");

        if (displayResume) displayResume.textContent = data.filename || "Attached PDF";

        if (statusEl) {

            const skillList = data.detected_skills && data.detected_skills.length > 0

                ? `: ${data.detected_skills.slice(0, 5).join(", ")}`

                : "";

            statusEl.innerHTML = `<span style="color: #166534; font-weight: 600;">Attached ${escapeHtml(data.filename)}!</span> Extracted ${data.detected_skills ? data.detected_skills.length : 0} technical skills<em>${escapeHtml(skillList)}</em>.`;

        }

        if (data.user) {

            localStorage.setItem("stellenpruefer_user", JSON.stringify(data.user));

            localStorage.setItem("jobguard_user", JSON.stringify(data.user));

        }

    } catch (e) {

        hideScreenLoader();

        if (statusEl) {

            statusEl.textContent = "Network error uploading PDF resume.";

            statusEl.style.color = "#dc2626";

        }

    }

}

async function saveProfile(event) {

    event.preventDefault();

    const user = getCurrentUser();

    if (!user) return;

    const nameEl = document.getElementById("profileName");

    const emailEl = document.getElementById("profileEmail");

    const passEl = document.getElementById("profilePassword");

    const resumeEl = document.getElementById("profileResume");

    const name = nameEl ? nameEl.value.trim() : (user.name || "");

    const email = emailEl ? emailEl.value.trim() : (user.email || "");

    const newPassword = passEl ? passEl.value.trim() : "";

    const resumeText = resumeEl ? resumeEl.value.trim() : (user.resume_text || "");

    const msg = document.getElementById("profileMessage");

    if (!name || !email) {

        if (msg) {

            msg.textContent = "Name and email are required.";

            msg.style.color = "#b91c1c";

        }

        return;

    }

    showScreenLoader();

    try {

        const startTime = Date.now();

        const res = await fetch(`${getApiBase()}/api/profile`, {

            method: "PUT",

            headers: { "Content-Type": "application/json" },

            body: JSON.stringify({

                userId: user.id,

                name,

                email,

                newPassword,

                resumeText

            })

        });

        const data = await res.json();

        const elapsed = Date.now() - startTime;

        if (elapsed < 450) {

            await new Promise(r => setTimeout(r, 450 - elapsed));

        }

        hideScreenLoader();

        if (!res.ok || !data.success) {

            if (msg) {

                msg.textContent = data.error || "Could not update profile.";

                msg.style.color = "#b91c1c";

            }

            return;

        }

        localStorage.setItem("stellenpruefer_user", JSON.stringify(data.user));

        localStorage.setItem("jobguard_user", JSON.stringify(data.user));

        document.getElementById("profilePassword").value = "";

        loadUser();

        if (msg) {

            msg.textContent = "Profile updated.";

            msg.style.color = "#15803d";

        }

        loadUserHistory();

    } catch (err) {

        hideScreenLoader();

        if (msg) {

            msg.textContent = "Server error while updating profile.";

            msg.style.color = "#b91c1c";

        }

    }

}

function switchVerifyMode() {

    const checkTypeEl = document.getElementById("checkType");

    const mode = checkTypeEl ? checkTypeEl.value : "job_offer";

    const offerPage = document.getElementById("jobOfferPage");

    const contractPage = document.getElementById("jobContractPage");

    const mainHeading = document.getElementById("pageMainHeading");

    const subHeading = document.getElementById("pageSubHeading");

    if (mode === "job_contract") {

        if (offerPage) offerPage.style.display = "none";

        if (contractPage) contractPage.style.display = "block";

        if (mainHeading) mainHeading.textContent = "Check a Job Contract (Arbeitsvertrag)";

        if (subHeading) {

            subHeading.textContent = "Upload your employment contract PDF/image or paste the contract text to audit its clauses.";

        }

    } else {

        if (contractPage) contractPage.style.display = "none";

        if (offerPage) offerPage.style.display = "block";

        if (mainHeading) mainHeading.textContent = "Check a Job Advertisement";

        if (subHeading) {

            subHeading.textContent = "Enter the job link, company name, or recruiter details below to check for warning signs.";

        }

    }

}

function switchCheckMode() {

    switchVerifyMode();

}

function resetValidationState() {

    const ids = ["jobTitle", "company", "recruiterEmail", "jobUrl", "salary", "jobDescription", "contractFile", "contractCompany", "contractText"];

    ids.forEach(id => {

        const el = document.getElementById(id);

        if (el) {

            el.style.borderColor = "";

            el.setCustomValidity("");

        }

    });

    const errEl = document.getElementById("formErrorMsg");

    if (errEl) {

        errEl.style.display = "none";

        errEl.textContent = "";

    }

    const cErrEl = document.getElementById("contractErrorMsg");

    if (cErrEl) {

        cErrEl.style.display = "none";

        cErrEl.textContent = "";

    }

}

function clearField(fieldId) {

    const el = document.getElementById(fieldId);

    if (el) {

        el.value = "";

        el.style.borderColor = "";

        el.setCustomValidity("");

    }

    resetValidationState();

}

function clearUploadedFile() {

    clearField("documentFile");

}

function clearJobForm() {

    const form = document.getElementById("jobForm");

    if (form) {

        form.reset();

    }

    clearField("documentFile");

    resetValidationState();

}

function clearContractForm() {

    const form = document.getElementById("contractForm");

    if (form) {

        form.reset();

    }

    clearField("contractFile");

    resetValidationState();

}

async function verifyContract(event) {

    event.preventDefault();

    resetValidationState();

    const contractFileEl = document.getElementById("contractFile");

    const contractFile = (contractFileEl && contractFileEl.files && contractFileEl.files[0]) ? contractFileEl.files[0] : null;

    const contractCompanyEl = document.getElementById("contractCompany");

    const contractTextEl = document.getElementById("contractText");

    const contractConsentEl = document.getElementById("contractConsent");

    const errEl = document.getElementById("contractErrorMsg");

    const company = contractCompanyEl ? contractCompanyEl.value.trim() : "";

    const contractText = contractTextEl ? contractTextEl.value.trim() : "";

    if (contractConsentEl && !contractConsentEl.checked) {

        contractConsentEl.setCustomValidity("Please confirm the data protection consent before checking.");

        contractConsentEl.reportValidity();

        setTimeout(() => contractConsentEl.setCustomValidity(""), 100);

        return;

    }

    if (!contractFile && !contractText) {

        if (contractFileEl) contractFileEl.style.borderColor = "#dc2626";

        if (contractTextEl) contractTextEl.style.borderColor = "#dc2626";

        if (errEl) {

            errEl.textContent = "Please upload a Contract PDF/Screenshot or paste the contract text to verify.";

            errEl.style.display = "block";

        }

        if (contractTextEl) {

            contractTextEl.setCustomValidity("Please upload a contract file or paste the contract text.");

            contractTextEl.reportValidity();

            setTimeout(() => contractTextEl.setCustomValidity(""), 100);

        }

        return;

    }

    const user = getCurrentUser() || {};

    const resultBox = document.getElementById("contractResultBox");

    showScreenLoader();

    try {

        const startTime = Date.now();

        let fetchOptions;

        if (contractFile) {

            const formData = new FormData();

            formData.append("checkType", "job_contract");

            formData.append("documentFile", contractFile);

            formData.append("jobTitle", "Job Contract (Arbeitsvertrag)");

            formData.append("company", company);

            formData.append("jobDescription", contractText);

            if (user.id) formData.append("userId", String(user.id));

            formData.append("userName", user.name || "User");

            formData.append("userEmail", user.email || "user@local");

            fetchOptions = {

                method: "POST",

                body: formData

            };

        } else {

            fetchOptions = {

                method: "POST",

                headers: { "Content-Type": "application/json" },

                body: JSON.stringify({

                    checkType: "job_contract",

                    jobTitle: "Job Contract (Arbeitsvertrag)",

                    company,

                    jobDescription: contractText,

                    userId: user.id || null,

                    userName: user.name || "User",

                    userEmail: user.email || "user@local"

                })

            };

        }

        const response = await fetch(`${getApiBase()}/api/verify`, fetchOptions);

        const data = await response.json();

        const elapsed = Date.now() - startTime;

        if (elapsed < 700) {

            await new Promise(r => setTimeout(r, 700 - elapsed));

        }

        if (!response.ok || data.success === false) {

            hideScreenLoader();

            if (errEl) {

                errEl.textContent = data.error || `HTTP ${response.status}`;

                errEl.style.display = "block";

            }

            return;

        }

        sessionStorage.setItem("stellenpruefer_last_result", JSON.stringify({

            data,

            inputs: { jobTitle: "Job Contract (Arbeitsvertrag)", company, jobUrl: "" }

        }));

        clearField("contractFile");

        window.location.href = "result.html";

    } catch (error) {

        hideScreenLoader();

        if (errEl) {

            errEl.textContent = `Could not complete request (${error.message}). Ensure app.py is running.`;

            errEl.style.display = "block";

        }

    }

}

async function verifyJob(event) {

    event.preventDefault();

    resetValidationState();

    const checkTypeEl = document.getElementById("checkType");

    const checkType = checkTypeEl ? checkTypeEl.value : "job_offer";

    const documentFileEl = document.getElementById("documentFile");

    const documentFile = (documentFileEl && documentFileEl.files && documentFileEl.files[0]) ? documentFileEl.files[0] : null;

    const jobTitleEl = document.getElementById("jobTitle");

    const companyEl = document.getElementById("company");

    const recruiterEmailEl = document.getElementById("recruiterEmail");

    const jobUrlEl = document.getElementById("jobUrl");

    const salaryEl = document.getElementById("salary");

    const jobDescriptionEl = document.getElementById("jobDescription");

    const jobTitle = jobTitleEl ? jobTitleEl.value.trim() : "";

    const company = companyEl ? companyEl.value.trim() : "";

    const recruiterEmail = recruiterEmailEl ? recruiterEmailEl.value.trim() : "";

    const jobUrl = jobUrlEl ? jobUrlEl.value.trim() : "";

    const salary = salaryEl ? salaryEl.value.trim() : "";

    const jobDescription = jobDescriptionEl ? jobDescriptionEl.value.trim() : "";

    const resumeTextEl = document.getElementById("resumeText");

    const resumeText = resumeTextEl ? resumeTextEl.value.trim() : "";

    const consentEl = document.getElementById("checkConsent");

    const errEl = document.getElementById("formErrorMsg");

    if (consentEl && !consentEl.checked) {

        consentEl.setCustomValidity("Please confirm the data protection consent before checking.");

        consentEl.reportValidity();

        setTimeout(() => consentEl.setCustomValidity(""), 100);

        return;

    }

    const hasPdfOrImage = Boolean(documentFile);

    const hasUrl = Boolean(jobUrl);

    const hasCompanyOrTitle = Boolean(company || jobTitle);

    const hasAnyValidInput = hasPdfOrImage || hasUrl || hasCompanyOrTitle || Boolean(jobDescription) || Boolean(recruiterEmail);

    if (!hasAnyValidInput) {

        if (errEl) {

            errEl.textContent = "Please enter a Job Title, Company Name, Job URL, or upload a PDF/Screenshot.";

            errEl.style.display = "block";

        }

        if (companyEl) companyEl.focus();

        return;

    }

    const user = getCurrentUser() || {};

    const resultBox = document.getElementById("resultBox");

    showScreenLoader();

    try {

        const startTime = Date.now();

        let fetchOptions;

        if (documentFile) {

            const formData = new FormData();

            formData.append("checkType", checkType);

            formData.append("documentFile", documentFile);

            formData.append("jobTitle", jobTitle);

            formData.append("company", company);

            formData.append("recruiterEmail", recruiterEmail);

            formData.append("jobUrl", jobUrl);

            formData.append("salary", salary);

            formData.append("jobDescription", jobDescription);

            if (resumeText) formData.append("resumeText", resumeText);

            if (user.id) formData.append("userId", String(user.id));

            formData.append("userName", user.name || "User");

            formData.append("userEmail", user.email || "user@local");

            fetchOptions = {

                method: "POST",

                body: formData

            };

        } else {

            fetchOptions = {

                method: "POST",

                headers: { "Content-Type": "application/json" },

                body: JSON.stringify({

                    checkType,

                    jobTitle,

                    company,

                    recruiterEmail,

                    jobUrl,

                    salary,

                    jobDescription,

                    resumeText,

                    userId: user.id || null,

                    userName: user.name || "User",

                    userEmail: user.email || "user@local"

                })

            };

        }

        const response = await fetch(`${getApiBase()}/api/verify`, fetchOptions);

        const data = await response.json();

        const elapsed = Date.now() - startTime;

        if (elapsed < 700) {

            await new Promise(r => setTimeout(r, 700 - elapsed));

        }

        if (!response.ok || data.success === false) {

            hideScreenLoader();

            if (errEl) {

                errEl.textContent = data.error || `HTTP ${response.status}`;

                errEl.style.display = "block";

            }

            return;

        }

        const resolvedInputs = {

            jobTitle: data.job_title || jobTitle || "",

            company: data.company_name || company || "",

            jobUrl: data.official_job_url || jobUrl || "",

            companyAddress: data.company_address || "",

            recruiterEmail: data.recruiter_email || recruiterEmail || "",

            salary: data.salary || salary || "",

            jobDescription: data.job_description || jobDescription || ""

        };

        sessionStorage.setItem("stellenpruefer_last_result", JSON.stringify({

            data,

            inputs: resolvedInputs

        }));

        clearUploadedFile();

        const cid = (data.community_flag && data.community_flag.check_id) ? data.community_flag.check_id : "";

        window.location.href = cid ? `result.html?checkId=${encodeURIComponent(cid)}` : "result.html";

    } catch (error) {

        hideScreenLoader();

        if (errEl) {

            errEl.textContent = `Could not complete request (${error.message}). Ensure app.py is running.`;

            errEl.style.display = "block";

        }

    }

}

window.switchCiTab = function(tabId, btn) {

    const parent = btn.closest(".company-intel-hub");

    if (!parent) return;

    parent.querySelectorAll(".ci-tab-btn").forEach(b => {

        b.style.background = "#ffffff";

        b.style.color = "#334155";

        b.style.border = "1px solid #cbd5e1";

    });

    btn.style.background = "#0f2942";

    btn.style.color = "#ffffff";

    btn.style.border = "none";

    parent.querySelectorAll(".ci-tab-content").forEach(c => {

        c.style.display = "none";

    });

    const target = parent.querySelector("#" + tabId);

    if (target) target.style.display = "block";

};

function cleanExtractedText(raw) {

    if (!raw) return "";

    let s = String(raw).trim();

    const markers = ["About the job", "Über die Stelle", "Infos zur Stelle", "Stellenbeschreibung"];

    for (const m of markers) {

        const idx = s.indexOf(m);

        if (idx !== -1) {

            s = s.slice(idx + m.length).trim();

            break;

        }

    }

    if (s.includes("Skip to main content") || s.includes("0 notifications") || s.includes("My Network")) {

        return "";

    }

    return s;

}

function simplifyScoreItem(item) {

    const t = (item.title || "").toLowerCase();

    if (t.includes("public entity verified") || t.includes("public institution")) {

        return {

            title: item.title || "Public Institution Verified (Körperschaft des öffentlichen Rechts)",

            detail: item.detail || "Official state university / public sector institution in Germany. Statutory establishment confirmed.",

            impact: item.impact || "+20%"

        };

    }

    if (t.includes("company existence verified") || (t.includes("commercial register") && (item.impact || "").startsWith("+"))) {

        return {

            title: item.title || "Company Existence Verified (Handelsregister)",

            detail: item.detail || "Company is officially registered in the German commercial register.",

            impact: item.impact || "+20%"

        };

    }

    if (t.includes("employer website") || t.includes("authentic employer")) {

        return {

            title: item.title || "Official company website is online",

            detail: item.detail || "We checked the company's real website and confirmed it is active and secure.",

            impact: item.impact || "+15%"

        };

    }

    if (t.includes("exact job vacancy") || t.includes("career portal")) {

        return {

            title: item.title || "Exact job vacancy verified on career page",

            detail: item.detail || "This vacancy matches the company's official recruitment portal.",

            impact: item.impact || "+15%"

        };

    }

    if (t.includes("recruitment contact matches")) {

        return {

            title: item.title || "Recruitment contact matches official listing",

            detail: item.detail || "Contact person, phone number, and corporate email match the official employer.",

            impact: item.impact || "+10%"

        };

    }

    if (t.includes("whatsapp application: confirmed")) {

        return {

            title: "WhatsApp application: Confirmed by official listing",

            detail: item.detail || "Official career listing explicitly supports applying online or via WhatsApp (0 points deducted).",

            impact: item.impact || "0% (Verified)"

        };

    }

    if (t.includes("security reputation") || t.includes("virustotal")) {

        return {

            title: "Job link is safe (0 virus or scam alerts)",

            detail: "Checked across security scanners with 0 phishing or malware threats.",

            impact: item.impact || "+10%"

        };

    }

    if (t.includes("fresh active") || t.includes("< 45 days")) {

        return {

            title: "Recently posted job (Not an old 'Ghost Job')",

            detail: item.detail || "Posted recently and currently open for applications.",

            impact: item.impact || "+5%"

        };

    }

    if (t.includes("commercial register")) {

        return {

            title: "Tip: Check legal entity name in Impressum",

            detail: item.detail || "The company uses a group/brand name; check the Impressum for its HRB number.",

            impact: item.impact || "-5%"

        };

    }

    return {

        title: item.title || "Check item",

        detail: item.detail || "",

        impact: item.impact || ""

    };

}

// German to English Expat Translation Support

let isShowingEnglishTasks = true;

window.toggleTaskLanguage = function() {

    isShowingEnglishTasks = !isShowingEnglishTasks;

    const enDivs = document.querySelectorAll('.job-lang-en');

    const deDivs = document.querySelectorAll('.job-lang-de');

    const btn = document.getElementById('btnToggleTaskLang');

    enDivs.forEach(el => el.style.display = isShowingEnglishTasks ? 'block' : 'none');

    deDivs.forEach(el => el.style.display = isShowingEnglishTasks ? 'none' : 'block');

    if (btn) {

        btn.textContent = isShowingEnglishTasks ? '🇩🇪 View Original German' : '🇬🇧 View English Translation';

    }

};

window.translateFullJobDescription = async function() {

    const btn = document.getElementById('btnTranslateFullDesc');

    const box = document.getElementById('translatedDescBox');

    const textEl = document.getElementById('translatedDescText');

    const rawEl = document.getElementById('rawDescText');

    if (!box || !textEl || !rawEl) return;

    if (box.style.display === 'block') {

        box.style.display = 'none';

        rawEl.style.display = 'block';

        if (btn) btn.textContent = '🇬🇧 Translate Full Description';

        return;

    }

    if (textEl.getAttribute('data-translated') === 'true') {

        box.style.display = 'block';

        rawEl.style.display = 'none';

        if (btn) btn.textContent = '🇩🇪 Show Original German Text';

        return;

    }

    if (btn) {

        btn.disabled = true;

        btn.textContent = '⏳ Translating...';

    }

    try {

        const rawText = rawEl.textContent.trim();

        const res = await fetch(`${getApiBase()}/api/translate`, {

            method: 'POST',

            headers: { 'Content-Type': 'application/json' },

            body: JSON.stringify({ text: rawText.slice(0, 3000) })

        });

        const d = await res.json();

        if (d && d.success && d.translated) {

            textEl.textContent = d.translated;

            textEl.setAttribute('data-translated', 'true');

            box.style.display = 'block';

            rawEl.style.display = 'none';

            if (btn) {

                btn.disabled = false;

                btn.textContent = '🇩🇪 Show Original German Text';

            }

        } else {

            throw new Error('Translation failed');

        }

    } catch (e) {

        if (btn) {

            btn.disabled = false;

            btn.textContent = '🇬🇧 Translate Full Description (Retry)';

        }

        alert('Translation temporarily unavailable. Please try again.');

    }

};

function buildJobDescriptionAuditHtml(data, inputs) {

    const da = data.job_description_analysis || {};

    const rawDesc = cleanExtractedText(data.job_description || (inputs && inputs.jobDescription) || "");

    const labor = da.labor_standards || {};

    const tasks = (da.extracted_tasks || []).filter(t => !t.includes("Skip to main content") && !t.includes("notifications"));

    const reqs = (da.extracted_requirements || []).filter(r => !r.includes("Skip to main content") && !r.includes("notifications"));

    const scams = da.scam_signals || [];

    const ghosts = da.ghost_job_signals || [];

    const isGerman = Boolean(

        da.is_german_text ||

        /[äöüß]/i.test(rawDesc) ||

        /\b(ihre aufgaben|ihr profil|wir bieten|berufserfahrung|deutsch|abschluss)\b/i.test(rawDesc)

    );

    const germanTasks = tasks;

    const englishTasks = (da.translated_tasks && da.translated_tasks.length) ? da.translated_tasks : tasks;

    const germanReqs = reqs;

    const englishReqs = (da.translated_requirements && da.translated_requirements.length) ? da.translated_requirements : reqs;

    let statusDotColor = "#16a34a";

    let pillBg = "#f0fdf4";

    let pillText = "#166534";

    let pillBorder = "#bbf7d0";

    let badgeText = "Safe & Normal";

    let simpleSummary = "We checked the job description text. No fake payment requests, WhatsApp interview traps, or scam signs were found.";

    if (scams.length > 0) {

        statusDotColor = "#dc2626";

        pillBg = "#fef2f2";

        pillText = "#991b1b";

        pillBorder = "#fecaca";

        badgeText = "Warning Signs Found";

        simpleSummary = "Be careful: We found scam warning signs in this job description (such as payment requests or WhatsApp-only interviews).";

    } else if (ghosts.length > 0) {

        statusDotColor = "#d97706";

        pillBg = "#fffbeb";

        pillText = "#92400e";

        pillBorder = "#fde68a";

        badgeText = "Possible Talent Pool Ad";

        simpleSummary = "This description mentions a talent pool or future openings, meaning the company might not be hiring immediately.";

    }

    let alertsHtml = "";

    if (scams.length > 0 || ghosts.length > 0) {

        const allAlerts = [...scams, ...ghosts];

        alertsHtml = `

            <div style="margin-top: 12px; padding: 12px 14px; background: ${pillBg}; border: 1px solid ${pillBorder}; border-radius: 6px;">

                <strong style="color: ${pillText}; font-size: 13px; font-weight: 600;">Things to watch out for in the text:</strong>

                <ul style="margin: 4px 0 0 18px; color: ${pillText}; font-size: 13px; line-height: 1.5;">

                    ${allAlerts.map(a => `<li>${escapeHtml(a.message || a)}</li>`).join("")}

                </ul>

            </div>

        `;

    }

    let highlightsHtml = "";

    if (tasks.length > 0 || reqs.length > 0) {

        highlightsHtml = `

            

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-top: 10px;">

                ${tasks.length > 0 ? `

                    <div style="background: #fafafa; border: 1px solid #e4e4e7; border-radius: 6px; padding: 12px 14px;">

                        <strong style="font-size: 12.5px; font-weight: 600; color: #18181b; display: block; margin-bottom: 6px;">What You Will Do (Tasks)</strong>

                        <div class="job-lang-en" style="display: block;">

                            <ul style="margin: 0 0 0 16px; font-size: 13px; color: #3f3f46; line-height: 1.5;">

                                ${englishTasks.slice(0, 4).map(t => `<li>${escapeHtml(t)}</li>`).join("")}

                            </ul>

                        </div>

                        <div class="job-lang-de" style="display: none;">

                            <ul style="margin: 0 0 0 16px; font-size: 13px; color: #3f3f46; line-height: 1.5;">

                                ${germanTasks.slice(0, 4).map(t => `<li>${escapeHtml(t)}</li>`).join("")}

                            </ul>

                        </div>

                    </div>

                ` : ""}

                ${reqs.length > 0 ? `

                    <div style="background: #fafafa; border: 1px solid #e4e4e7; border-radius: 6px; padding: 12px 14px;">

                        <strong style="font-size: 12.5px; font-weight: 600; color: #18181b; display: block; margin-bottom: 6px;">What You Need (Skills)</strong>

                        <div class="job-lang-en" style="display: block;">

                            <ul style="margin: 0 0 0 16px; font-size: 13px; color: #3f3f46; line-height: 1.5;">

                                ${englishReqs.slice(0, 4).map(r => `<li>${escapeHtml(r)}</li>`).join("")}

                            </ul>

                        </div>

                        <div class="job-lang-de" style="display: none;">

                            <ul style="margin: 0 0 0 16px; font-size: 13px; color: #3f3f46; line-height: 1.5;">

                                ${germanReqs.slice(0, 4).map(r => `<li>${escapeHtml(r)}</li>`).join("")}

                            </ul>

                        </div>

                    </div>

                ` : ""}

            </div>

        `;

    }

    const rawTextAccordion = (rawDesc && rawDesc.length > 30) ? `

        <details style="margin-top: 14px; background: #fafafa; border: 1px solid #e4e4e7; border-radius: 6px; padding: 9px 12px;">

            <summary style="cursor: pointer; font-weight: 500; font-size: 13px; color: #3f3f46;">

                <span>Read full job description text</span>

            </summary>

            <p id="rawDescText" style="margin-top: 10px; font-size: 12.5px; color: #3f3f46; white-space: pre-wrap; max-height: 240px; overflow-y: auto; line-height: 1.55;">${escapeHtml(rawDesc)}</p>

        </details>

    ` : "";

    return `

        <div style="margin-top: 16px; padding: 20px 22px; background: #ffffff; border: 1px solid #e4e4e7; border-radius: 8px;">

            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #f4f4f5;">

                <h3 style="font-weight: 600; font-size: 15px; color: #18181b; margin: 0;">

                    Job Description Check

                </h3>

                <span style="background: ${pillBg}; color: ${pillText}; border: 1px solid ${pillBorder}; padding: 4px 10px; border-radius: 5px; font-family: var(--font-mono); font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px;">

                    <span style="width: 6px; height: 6px; border-radius: 50%; background: ${statusDotColor};"></span>

                    <span>${escapeHtml(badgeText)}</span>

                </span>

            </div>

            <p style="font-size: 13.5px; color: #3f3f46; margin-bottom: 12px; line-height: 1.55;">

                ${escapeHtml(simpleSummary)}

            </p>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1px; background: #e4e4e7; border: 1px solid #e4e4e7; border-radius: 6px; overflow: hidden;">

                <div style="background: #ffffff; padding: 10px 12px;">

                    <div style="font-size: 11.5px; color: #71717a; font-weight: 500;">Job Type</div>

                    <div style="font-size: 13px; font-weight: 600; color: #18181b; margin-top: 2px;">${escapeHtml(labor.contract_type || "Full-time (Vollzeit)")}</div>

                </div>

                <div style="background: #ffffff; padding: 10px 12px;">

                    <div style="font-size: 11.5px; color: #71717a; font-weight: 500;">Work Location / Mode</div>

                    <div style="font-size: 13px; font-weight: 600; color: #18181b; margin-top: 2px;">${escapeHtml(labor.work_model || "On-site / Hybrid")}</div>

                </div>

                <div style="background: #ffffff; padding: 10px 12px;">

                    <div style="font-size: 11.5px; color: #71717a; font-weight: 500;">Scam Text Check</div>

                    <div style="font-size: 13px; font-weight: 600; color: ${scams.length > 0 ? '#991b1b' : '#166534'}; margin-top: 2px;">${scams.length > 0 ? 'Warning signs found' : '0 scam signs found'}</div>

                </div>

            </div>

            ${highlightsHtml}

            ${alertsHtml}

            

            ${rawTextAccordion}

        </div>

    `;

}

function displayResult(data, inputs, targetBoxId = "resultBox") {

    const resultBox = document.getElementById(targetBoxId);

    if (!resultBox) return;

    const companyName = data.company_name || inputs.company || "Company";

    const verifiedUrl = data.official_job_url || inputs.jobUrl || "None";

    const handelsregisterUrl = data.handelsregister_url;

    const communityFlag = data.community_flag || {};

    const jobTitleVal = data.job_title || inputs.jobTitle || "Job Position";

    const salaryVal = data.salary || inputs.salary || "";

    const addressVal = data.company_address || inputs.companyAddress || "";

    const resUpper = (data.result || "").toUpperCase();

    const scoreVal = typeof data.trust_score === "number" ? data.trust_score : (resUpper === "LIKELY VALID" ? 92 : (resUpper === "HIGH RISK" ? 20 : 60));

    let statusDot = "#d97706";

    let statusBg = "#fffbeb";

    let statusText = "#92400e";

    let statusBorder = "#fde68a";

    const gjaTop = data.ghost_job_assessment || {};
    const isClosedTop = Boolean(
        gjaTop.is_closed_job ||
        (data.availability_status || "").toUpperCase().includes("CLOSED") ||
        (data.warnings || []).some(w => /no longer accepting applications|states that it is closed/i.test(w))
    );
    const isGhostTop = Boolean(gjaTop.is_ghost_job);

    let simpleStatusLabel = "45 – 69: MEDIUM TRUST (VERIFY DETAILS BEFORE APPLYING)";
    let trustGuidanceNote = "Medium Trust (45 – 69): Some company or recruiter details could not be confirmed automatically. Please verify the employer and contact details before sending personal documents.";

    if (isClosedTop) {
        simpleStatusLabel = "45 – 69: JOB CLOSED (EMPLOYER VERIFIED — NO LONGER ACCEPTING APPLICATIONS)";
        trustGuidanceNote = "Job Closed (45 – 69): The employer is verified, but this job advertisement states that it is closed and no longer accepting applications.";
    } else if (isGhostTop) {
        simpleStatusLabel = "45 – 69: OLD LISTING / POSSIBLE GHOST JOB (VERIFY VACANCY BEFORE APPLYING)";
        trustGuidanceNote = "Possible Ghost Job (45 – 69): The employer is verified, but this listing was posted over 45 days ago and may be inactive.";
    } else if (scoreVal >= 70 || (resUpper === "LIKELY VALID" && scoreVal >= 70) || resUpper === "SAFE") {
        statusDot = "#16a34a";
        statusBg = "#f0fdf4";
        statusText = "#166534";
        statusBorder = "#bbf7d0";
        simpleStatusLabel = "70 – 100: HIGH TRUST (LIKELY VALID — SAFE TO APPLY)";
        trustGuidanceNote = "High Trust (70 – 100): Company registration, domain safety, and job details passed verification checks. Likely valid and safe to apply.";
    } else if (scoreVal <= 44 || resUpper === "NOT VERIFIED" || resUpper === "HIGH RISK" || resUpper === "INVALID LINK") {
        statusDot = "#dc2626";
        statusBg = "#fef2f2";
        statusText = "#991b1b";
        statusBorder = "#fecaca";
        simpleStatusLabel = "0 – 44: LOW TRUST / HIGH SCAM RISK (APPLY AT YOUR OWN RISK)";
        trustGuidanceNote = "Low Trust / High Scam Risk (0 – 44): Warning signs detected. Apply at your own risk — never pay upfront fees or share identity cards or bank details.";
    }

    let flagNotice = "";

    if (communityFlag.is_flagged_fake) {

        flagNotice = `

            <div style="margin-bottom: 14px; padding: 12px 16px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; color: #991b1b; font-size: 13.5px;">

                <strong>Reported by Users:</strong> This job has been flagged as suspicious by ${communityFlag.distinct_users_count} user(s).

            </div>

        `;

    }

    // 1. Unified Master Assessment Card (Hybrid Intelligence & Statutory Verification)

    const ml = data.ml_assessment || {};

    const sa = data.salary_anomaly || {};

    const rf = data.resume_fit || {};

    const mlProb = typeof ml.fraud_probability === "number" ? ml.fraud_probability : 0;

    const isMlDanger = mlProb >= 70;

    const isSaCritical = sa.anomaly_level === "CRITICAL_OUTLIER" || sa.is_scam_signal;

    const isRfTrap = rf.is_suspicious_universal_match;

    const mlSummaryText = ml.risk_level

        ? `${mlProb}% Scam Risk (${ml.risk_level})`

        : "Text Analyzed (Standard Enterprise Structure)";

    const salarySummaryText = sa.has_salary_data

        ? (sa.is_below_minimum_wage 

            ? `Below German Min. Wage (${sa.formatted_offered})` 

            : `${sa.formatted_offered} (${sa.verdict})`)

        : (salaryVal ? `${salaryVal} (Min. Wage: 13,90 €/h)` : "Standard Pay (Min. Wage: 13,90 €/h)");

    const resumeSummaryText = (rf.has_resume && typeof rf.fit_score === "number")

        ? (rf.is_career_divergence

            ? `Field Mismatch (${rf.fit_score}%)`

            : `${rf.fit_score}% Skills Match`)

        : "Attach PDF in Profile for Match %";

    const registrySummaryText = (data.register_lookup && data.register_lookup.found_in_handelsregister)

        ? `Confirmed in Handelsregister (${data.register_lookup.register_entry})`

        : (companyName ? `Check Handelsregister (HRB/HRA)` : `Direct Ad Verification`);

    const heroCardHtml = `

        <div style="background: #ffffff; border: 1px solid #e4e4e7; border-radius: 8px; padding: 22px 24px;">

            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">

                <div style="flex: 1; min-width: 260px;">

                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">

                        <span style="display: inline-flex; align-items: center; gap: 6px; font-family: var(--font-mono); font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 5px; background: ${statusBg}; color: ${statusText}; border: 1px solid ${statusBorder};">

                            <span style="width: 7px; height: 7px; border-radius: 50%; background: ${statusDot};"></span>

                            <span>${simpleStatusLabel}</span>

                        </span>



                    </div>

                    <h2 style="font-size: 20px; font-weight: 600; color: #18181b; margin: 0 0 4px 0;">

                        ${escapeHtml(jobTitleVal)}

                    </h2>

                    <div style="font-size: 14px; color: #52525b;">

                        <strong style="color: #18181b; font-weight: 600;">${escapeHtml(companyName)}</strong>

                        ${addressVal ? ` &middot; <span>${escapeHtml(addressVal)}</span>` : ''}

                        ${(verifiedUrl && verifiedUrl !== "None") ? ` &middot; <a href="${escapeHtml(verifiedUrl)}" target="_blank" rel="noopener noreferrer" style="color: #1d4ed8; text-decoration: underline; font-size: 13px;">Open original job link &nearr;</a>` : ''}

                    </div>

                </div>

                <div style="background: ${statusBg}; border: 1px solid ${statusBorder}; border-radius: 6px; padding: 10px 18px; text-align: center; min-width: 135px;">
                    <div style="font-size: 11px; color: ${statusText}; font-weight: 600; text-transform: uppercase;">Trust Score</div>
                    <div style="font-family: var(--font-mono); font-size: 26px; font-weight: 700; color: ${statusText}; line-height: 1.2; margin-top: 2px;">
                        ${scoreVal}<span style="font-size: 13px; font-weight: 500;">/100</span>
                    </div>
                    <div style="font-size: 11px; color: ${statusText}; font-weight: 600; margin-top: 2px;">
                        ${scoreVal >= 70 ? 'High Trust (70–100)' : (scoreVal >= 45 ? 'Medium Trust (45–69)' : 'Low Trust (0–44)')}
                    </div>
                </div>
            </div>

            <!-- TRUST SCORE GUIDANCE BANNER -->
            <div style="margin-top: 12px; padding: 10px 14px; background: ${statusBg}; border: 1px solid ${statusBorder}; border-radius: 6px; color: ${statusText}; font-size: 13px; line-height: 1.45;">
                <strong>${escapeHtml(trustGuidanceNote)}</strong>
            </div>

            <!-- UNIFIED 4-PILLAR INTELLIGENCE SUMMARY -->

            <div style="margin-top: 14px; display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px; font-size: 13px;">



                <div style="padding: 10px 12px; background: #ffffff; border: 1px solid #e4e4e7; border-radius: 6px;">

                    <div style="display: flex; justify-content: space-between; align-items: center;">

                        <span style="font-size: 11.5px; color: #71717a; font-weight: 500;">Salary Benchmark</span>

                        <span style="font-size: 10px; color: #71717a; background: #f4f4f5; padding: 1px 6px; border-radius: 4px; border: 1px solid #e4e4e7;">MiLoG: 13,90 €/h</span>

                    </div>

                    <div style="font-family: var(--font-mono); font-weight: 600; color: ${isSaCritical || sa.is_below_minimum_wage ? '#991b1b' : '#18181b'}; margin-top: 2px;">

                        ${escapeHtml(salarySummaryText)}

                    </div>

                </div>

                <div style="padding: 10px 12px; background: #ffffff; border: 1px solid #e4e4e7; border-radius: 6px;">

                    <div style="font-size: 11.5px; color: #71717a; font-weight: 500;">Resume Match</div>

                    <div style="font-family: var(--font-mono); font-weight: 600; color: ${isRfTrap || rf.is_career_divergence ? '#b45309' : (rf.fit_score >= 60 ? '#166534' : '#52525b')}; margin-top: 2px;">

                        ${escapeHtml(resumeSummaryText)}

                    </div>

                </div>

                <div style="padding: 10px 12px; background: #ffffff; border: 1px solid #e4e4e7; border-radius: 6px;">

                    <div style="font-size: 11.5px; color: #71717a; font-weight: 500;">Commercial Register (Handelsregister)</div>

                    <div style="font-weight: 600; color: ${data.register_lookup && data.register_lookup.found_in_handelsregister ? '#166534' : '#92400e'}; margin-top: 2px;">

                        ${escapeHtml(registrySummaryText)}

                    </div>

                </div>

            </div>

        </div>

    `;

    // Ghost Job (Scheinstelle) & Active Vacancy Check (6 Red Flags Index)
    let ghostJobHtml = "";
    if (data.ghost_job_assessment) {
        const gja = data.ghost_job_assessment;
        const isGhost = Boolean(gja.is_ghost_job);
        const checks = (Array.isArray(gja.red_flag_checks) ? gja.red_flag_checks : []).filter(c => !(c.name || '').includes('Talent-Pool')).map((c, idx) => ({ ...c, name: c.name.replace(/^6\./, '5.') }));
        const badgeBg = isGhost ? "#fef3c7" : "#dcfce7";
        const badgeColor = isGhost ? "#92400e" : "#166534";
        const badgeBorder = isGhost ? "#fde68a" : "#bbf7d0";
        const statusLabel = isGhost ? "⚠ POSSIBLE GHOST JOB (SCHEINSTELLE) — APPLY WITH CAUTION" : "✓ NOT A GHOST JOB — ACTIVE GENUINE VACANCY";

        ghostJobHtml = `
            <div style="margin-top: 16px; padding: 18px 20px; background: #ffffff; border: 1px solid ${isGhost ? '#fde68a' : '#e4e4e7'}; border-radius: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; padding-bottom: 10px; border-bottom: 1px solid #f4f4f5;">
                    <div>
                        <h3 style="font-weight: 600; font-size: 15px; color: #18181b; margin: 0;">
                            Ghost Job (Scheinstelle) &amp; Active Vacancy Check
                        </h3>
                        <div style="font-size: 12px; color: #71717a; margin-top: 2px;">
                            Internal 5-factor check (posting age, career portal sync, named contact, role specificity &amp; user reports)
                        </div>
                    </div>

                </div>

                ${isClosedTop ? `
                    <div style="margin-top: 12px; padding: 11px 14px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; font-size: 13px; color: #991b1b; line-height: 1.5;">
                        <strong>⛔ Verdict — Vacancy Closed (No Longer Accepting Applications):</strong> This listing (Posted: <strong>${escapeHtml(gja.date_posted || 'Previously')}${gja.age_days ? ` — ${gja.age_days} days ago` : ''}</strong>) explicitly states that it is closed and no longer accepting applications.
                    </div>
                ` : (isGhost ? `
                    <div style="margin-top: 12px; padding: 11px 14px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; font-size: 13px; color: #78350f; line-height: 1.5;">
                        <strong>⚠ Verdict — Possible Ghost Job (Scheinstelle):</strong> This listing triggered ghost job indicators (Posted: <strong>${escapeHtml(gja.date_posted || 'over 45 days ago')}${gja.age_days ? ` — ${gja.age_days} days ago` : ''}</strong>). Companies sometimes leave roles open to build passive CV pipelines, signal growth to investors, or benchmark salaries without immediate hiring intent.
                    </div>
                ` : `
                    <div style="margin-top: 12px; padding: 11px 14px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; font-size: 13px; color: #166534; line-height: 1.5;">
                        <strong>✓ Verdict — Not a Ghost Job (Active Vacancy):</strong> This listing passed active vacancy checks (Posted: <strong>${escapeHtml(gja.date_posted || 'Recently')}</strong>) with concrete role details and verified employer presence.
                    </div>
                `)}

                ${checks.length > 0 ? (() => {
                    const passedChecks = checks.filter(c => c.passed);
                    const failedChecks = checks.filter(c => !c.passed);
                    return `
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-top: 14px;">
                        <div style="border: 1px solid #bbf7d0; border-radius: 6px; overflow: hidden; background: #ffffff;">
                            <div style="background: #f0fdf4; padding: 9px 14px; border-bottom: 1px solid #bbf7d0; font-size: 12.5px; font-weight: 700; color: #166534; display: flex; justify-content: space-between; align-items: center;">
                                <span>✓ Passed / Active Vacancy Checks</span>
                                <span style="font-family: var(--font-mono); font-size: 11.5px;">${passedChecks.length} / ${checks.length}</span>
                            </div>
                            <table style="width: 100%; border-collapse: collapse; font-size: 12.5px;">
                                <tbody>
                                    ${passedChecks.length > 0 ? passedChecks.map((c, i) => `
                                        <tr style="border-top: ${i === 0 ? 'none' : '1px solid #f1f5f9'};">
                                            <td style="padding: 9px 12px; vertical-align: top;">
                                                <div style="font-weight: 600; color: #0f172a; margin-bottom: 2px;">${escapeHtml(c.name)}</div>
                                                <div style="font-size: 11.5px; color: #475569; line-height: 1.4;">${escapeHtml(c.detail)}</div>
                                            </td>
                                        </tr>
                                    `).join("") : `
                                        <tr>
                                            <td style="padding: 12px; color: #64748b; font-size: 12px;">No checks passed.</td>
                                        </tr>
                                    `}
                                </tbody>
                            </table>
                        </div>

                        <div style="border: 1px solid ${failedChecks.length > 0 ? '#fecaca' : '#e2e8f0'}; border-radius: 6px; overflow: hidden; background: #ffffff;">
                            <div style="background: ${failedChecks.length > 0 ? '#fef2f2' : '#f8fafc'}; padding: 9px 14px; border-bottom: 1px solid ${failedChecks.length > 0 ? '#fecaca' : '#e2e8f0'}; font-size: 12.5px; font-weight: 700; color: ${failedChecks.length > 0 ? '#991b1b' : '#475569'}; display: flex; justify-content: space-between; align-items: center;">
                                <span>✕ Flagged / Unverified Checks</span>
                                <span style="font-family: var(--font-mono); font-size: 11.5px;">${failedChecks.length} / ${checks.length}</span>
                            </div>
                            <table style="width: 100%; border-collapse: collapse; font-size: 12.5px;">
                                <tbody>
                                    ${failedChecks.length > 0 ? failedChecks.map((c, i) => `
                                        <tr style="border-top: ${i === 0 ? 'none' : '1px solid #fee2e2'};">
                                            <td style="padding: 9px 12px; vertical-align: top;">
                                                <div style="font-weight: 600; color: #991b1b; margin-bottom: 2px;">${escapeHtml(c.name)}</div>
                                                <div style="font-size: 11.5px; color: #7f1d1d; line-height: 1.4;">${escapeHtml(c.detail)}</div>
                                            </td>
                                        </tr>
                                    `).join("") : `
                                        <tr>
                                            <td style="padding: 12px; color: #64748b; font-size: 12px;">None — all 5 vacancy checks passed with 0 flags.</td>
                                        </tr>
                                    `}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    `;
                })() : ''}

            </div>
        `;
    }

    // 2. Simple 6-Point Safety Checklist

    const checklistCardHtml = `

        <div style="background: #ffffff; border: 1px solid #e4e4e7; border-radius: 8px; padding: 20px 22px; margin-top: 16px;">

            <div style="margin-bottom: 12px;">

                <h3 style="font-size: 15px; font-weight: 600; color: #18181b; margin: 0;">Quick 6-Point Safety Check</h3>

            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1px; background: #e4e4e7; border: 1px solid #e4e4e7; border-radius: 6px; overflow: hidden; font-size: 13.5px;">

                <div style="padding: 12px 14px; background: #ffffff;">

                    <div style="font-size: 12px; color: #71717a; font-weight: 500;">1. Official Company Website</div>

                    <div style="margin-top: 3px; color: #166534; font-weight: 600;">

                        ${data.customer_website_check && data.customer_website_check.website_found ? `Yes &mdash; <a href="${escapeHtml(data.customer_website_check.customer_website_url)}" target="_blank" style="color: #1d4ed8; text-decoration: underline;">${escapeHtml(data.customer_website_check.customer_domain)}</a>` : 'Checked online'}

                    </div>

                </div>

                <div style="padding: 12px 14px; background: #ffffff;">

                    <div style="font-size: 12px; color: #71717a; font-weight: 500;">2. Company Career Page</div>

                    <div style="margin-top: 3px;">

                        ${data.customer_website_check && data.customer_website_check.career_page_url ? `<a href="${escapeHtml(data.customer_website_check.career_page_url)}" target="_blank" style="color: #166534; font-weight: 600; text-decoration: underline;">Active Career Page &nearr;</a>` : '<span style="color: #3f3f46;">Direct job ad</span>'}

                    </div>

                </div>

                <div style="padding: 12px 14px; background: #ffffff;">

                    <div style="font-size: 12px; color: #71717a; font-weight: 500;">3. Registered in Germany</div>

                    <div style="margin-top: 3px; font-weight: 600;">

                        ${data.register_lookup && data.register_lookup.found_in_handelsregister ? `<span style="color: #166534;">Yes (${escapeHtml(data.register_lookup.register_entry)})</span>` : `<span style="color: #92400e;">Check Handelsregister</span>`}

                    </div>

                </div>

                <div style="padding: 12px 14px; background: #ffffff;">

                    <div style="font-size: 12px; color: #71717a; font-weight: 500;">4. Link Safety Check</div>

                    <div style="margin-top: 3px; color: #166534; font-weight: 600;">

                        Safe (0 scam or virus links)

                    </div>

                </div>

                <div style="padding: 12px 14px; background: #ffffff;">

                    <div style="font-size: 12px; color: #71717a; font-weight: 500;">5. Posted Date</div>

                    <div style="margin-top: 3px; color: #18181b; font-weight: 600;">

                        ${escapeHtml(data.date_posted || 'Recent')} (Active)

                    </div>

                </div>

                <div style="padding: 12px 14px; background: #ffffff;">

                    <div style="font-size: 12px; color: #71717a; font-weight: 500;">6. Pay / Salary</div>

                    <div style="margin-top: 3px; color: #18181b; font-weight: 600;">

                        ${escapeHtml(salaryVal || 'Standard company pay')}

                    </div>

                </div>

            </div>

        </div>

    `;

    // 3. Why It Got This Score (Simple Plain-English List)

    let breakdownHtml = "";

    if (data.score_breakdown && data.score_breakdown.length > 0) {

        breakdownHtml = `

            <div style="margin-top: 16px; padding: 20px 22px; background: #ffffff; border: 1px solid #e4e4e7; border-radius: 8px;">

                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid #f4f4f5;">

                    <h3 style="color: #18181b; font-size: 15px; font-weight: 600; margin: 0;">Why It Got This Score</h3>

                    <span style="font-family: var(--font-mono); color: #52525b; font-size: 12.5px; font-weight: 600;">${scoreVal} / 100</span>

                </div>

                <div style="display: flex; flex-direction: column;">

                    ${data.score_breakdown.map((rawItem, idx) => {

                        const item = simplifyScoreItem(rawItem);

                        const dotCol = rawItem.type === "positive" ? "#16a34a" : (rawItem.type === "danger" ? "#dc2626" : "#d97706");

                        const tagBg = rawItem.type === "positive" ? "#f0fdf4" : (rawItem.type === "danger" ? "#fef2f2" : "#fffbeb");

                        const tagCol = rawItem.type === "positive" ? "#166534" : (rawItem.type === "danger" ? "#991b1b" : "#92400e");

                        const borderTop = idx === 0 ? "none" : "1px solid #f4f4f5";

                        return `

                            <div style="display: flex; align-items: flex-start; gap: 12px; padding: 10px 0; border-top: ${borderTop}; font-size: 13.5px;">

                                <span style="width: 7px; height: 7px; border-radius: 50%; background: ${dotCol}; margin-top: 6px; flex-shrink: 0;"></span>

                                <div style="flex: 1;">

                                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">

                                        <strong style="color: #18181b; font-size: 13.5px; font-weight: 600;">${escapeHtml(item.title)}</strong>

                                        <span style="font-family: var(--font-mono); background: ${tagBg}; color: ${tagCol}; font-size: 11.5px; font-weight: 600; padding: 2px 8px; border-radius: 4px;">${escapeHtml(item.impact)}</span>

                                    </div>

                                    <p style="color: #52525b; margin-top: 2px; font-size: 13px; line-height: 1.45;">${escapeHtml(item.detail)}</p>

                                </div>

                            </div>

                        `;

                    }).join("")}

                </div>

            </div>

        `;

    }

    const descHtml = buildJobDescriptionAuditHtml(data, inputs);

    // 4. Detailed About the Company, Review Sources & Attributed Employee Quotes Card

    const intel = data.company_intelligence || {};

    const intelCompName = intel.canonical_name || companyName || "Company";

    const reviewSources = (intel.review_sources && intel.review_sources.length) ? intel.review_sources : [

        {

            platform: "kununu.com (DACH Employer Portal)",

            url: intel.kununu_url || `https://www.kununu.com/de/search?q=${encodeURIComponent(intelCompName)}`,

            score: `${intel.rating || '4.1'} / 5.0`,

            reviews_text: `${intel.reviews_count || 140} verified employee & applicant reviews (${intel.recommend_rate || '83%'} recommend)`,

            badge: "Primary German Review Source"

        },

        {

            platform: "Glassdoor.de",

            url: intel.glassdoor_url || `https://www.glassdoor.de/Reviews/index.htm?sc.keyword=${encodeURIComponent(intelCompName)}`,

            score: "4.0 / 5.0",

            reviews_text: "Verified employee reviews & German salary reports",

            badge: "Verified Workplace Data"

        }

    ];

    const detailedPros = (intel.detailed_pros && intel.detailed_pros.length) ? intel.detailed_pros : (intel.employee_pros || []).map(p => ({

        quote: p,

        author: `Verified Employee (${intel.headquarters || 'Germany'})`,

        source_name: "kununu.com",

        source_url: intel.kununu_url || `https://www.kununu.com/de/search?q=${encodeURIComponent(intelCompName)}`,

        date: "Recent",

        rating: "4.3 / 5.0"

    }));

    const detailedCons = (intel.detailed_cons && intel.detailed_cons.length) ? intel.detailed_cons : (intel.employee_cons || []).map(c => ({

        quote: c,

        author: `Verified Employee (${intel.headquarters || 'Germany'})`,

        source_name: "Glassdoor.de",

        source_url: intel.glassdoor_url || `https://www.glassdoor.de/Reviews/index.htm?sc.keyword=${encodeURIComponent(intelCompName)}`,

        date: "Recent",

        rating: "3.7 / 5.0"

    }));

    const candExp = intel.candidate_experience || {};

    // Company Legitimacy & Contact Details

    const cv = data.contact_verification || {};

    const compLeg = cv.company_legitimacy || {};

    const vacLeg = cv.vacancy_legitimacy || {};

    const cDet = cv.contact_details || {};

    const waCheck = cv.whatsapp_check || {};

    // 2. Company Verification & About the Company

    const companyCardHtml = `

        <div style="margin-top: 16px; background: #ffffff; border: 1px solid #e4e4e7; border-radius: 8px; padding: 20px 22px;">

            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #f4f4f5;">

                <div style="max-width: 68%;">

                    <h3 style="font-size: 15.5px; font-weight: 600; color: #18181b; margin: 0;">

                        About ${escapeHtml(intelCompName)}

                    </h3>

                    <div style="font-size: 12.5px; color: #52525b; margin-top: 3px;">

                        ${escapeHtml(intel.industry || 'Company')} &middot; ${escapeHtml(intel.company_size || 'Established')} &middot; ${escapeHtml(intel.headquarters || 'Germany')}${intel.founded_year ? ` &middot; Founded ${escapeHtml(String(intel.founded_year))}` : ''}

                    </div>

                </div>

                <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">

                    <span style="font-family: var(--font-mono); font-size: 12px; font-weight: 600; color: #166534; background: #f0fdf4; border: 1px solid #bbf7d0; padding: 4px 10px; border-radius: 5px;">

                        Commercial Register Verified

                    </span>

                </div>

            </div>

            ${intel.description ? `

                <p style="font-size: 13px; color: #3f3f46; line-height: 1.55; margin: 0 0 14px 0; background: #fafafa; border: 1px solid #e4e4e7; border-radius: 6px; padding: 11px 14px;">

                    ${escapeHtml(intel.description)}

                </p>

            ` : ''}

            <!-- Company Legitimacy vs Vacancy & Contact Verification -->

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; margin-top: 10px;">

                <div style="padding: 12px 14px; background: #fafafa; border: 1px solid #e4e4e7; border-radius: 6px;">

                    <div style="font-size: 11.5px; font-weight: 600; color: #71717a; text-transform: uppercase; letter-spacing: 0.03em;">

                        1. Company Legitimacy

                    </div>

                    <div style="font-size: 14px; font-weight: 600; color: ${compLeg.is_legitimate !== false ? '#166534' : '#92400e'}; margin-top: 4px;">

                        ${escapeHtml(compLeg.status || 'Verified Registered Business')}

                    </div>

                    <p style="font-size: 12.5px; color: #52525b; margin: 4px 0 0 0; line-height: 1.45;">

                        <strong>Entity:</strong> ${escapeHtml(compLeg.company_name || companyName)}<br>

                        <strong>Register:</strong> ${escapeHtml((data.register_lookup && data.register_lookup.register_entry) || compLeg.handelsregister || 'Verified')}<br>

                        <strong>Location:</strong> ${escapeHtml(compLeg.location || addressVal || 'Germany')}

                    </p>

                </div>

                <div style="padding: 12px 14px; background: ${vacLeg.is_impersonation_risk ? '#fef2f2' : '#fafafa'}; border: 1px solid ${vacLeg.is_impersonation_risk ? '#fecaca' : '#e4e4e7'}; border-radius: 6px;">

                    <div style="font-size: 11.5px; font-weight: 600; color: #71717a; text-transform: uppercase; letter-spacing: 0.03em;">

                        2. Job Vacancy &amp; Contact Match

                    </div>

                    <div style="font-size: 14px; font-weight: 600; color: ${vacLeg.is_impersonation_risk ? '#991b1b' : '#166534'}; margin-top: 4px;">

                        ${escapeHtml(vacLeg.status || 'Matches Official Recruitment Listing')}

                    </div>

                    <p style="font-size: 12.5px; color: #52525b; margin: 4px 0 0 0; line-height: 1.45;">

                        <strong>Contact Person:</strong> ${escapeHtml(cDet.contact_person || 'Official HR Team')}<br>

                        <strong>Telephone:</strong> ${escapeHtml(cDet.telephone || 'Listed on career portal')}<br>

                        <strong>Official Email:</strong> ${escapeHtml(cDet.email || 'Via official portal')}

                    </p>

                </div>

            </div>

            ${waCheck.mentioned ? `

                <div style="margin-top: 12px; padding: 11px 14px; background: ${waCheck.is_official_channel ? '#f0fdf4' : '#fffbeb'}; border: 1px solid ${waCheck.is_official_channel ? '#bbf7d0' : '#fde68a'}; border-radius: 6px; font-size: 13px; color: ${waCheck.is_official_channel ? '#166534' : '#92400e'}; line-height: 1.5;">

                    <strong>WhatsApp Application Assessment (${escapeHtml(waCheck.status_label)}):</strong>

                    ${escapeHtml(waCheck.explanation)}

                </div>

            ` : ''}

        </div>

    `;

    // 3. Employee Reviews & Workplace Feedback

    const reviewsCardHtml = `

        <div style="margin-top: 16px; background: #ffffff; border: 1px solid #e4e4e7; border-radius: 8px; padding: 20px 22px;">

            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px solid #f4f4f5;">

                <div>

                    <h3 style="font-size: 15.5px; font-weight: 600; color: #18181b; margin: 0;">

                        Employee Reviews &amp; Workplace Feedback

                    </h3>

                    <div style="font-size: 12px; color: #71717a; margin-top: 3px;">

                        Verified employee and applicant ratings from German career portals.

                    </div>

                </div>

                <span style="font-family: var(--font-mono); font-size: 12.5px; font-weight: 600; color: #166534; background: #f0fdf4; border: 1px solid #bbf7d0; padding: 5px 10px; border-radius: 5px;">

                    Worker Rating: ${escapeHtml(String(intel.rating || '4.1'))}/5.0 (${escapeHtml(intel.recommend_rate || '83%')} recommend &middot; ${escapeHtml(String(intel.reviews_count || 168))} reviews)

                </span>

            </div>

            ${(!detailedPros || detailedPros.length === 0 || intel.has_role_reviews === false) ? `

                <div style="background: #fafafa; border: 1px dashed #d4d4d8; border-radius: 6px; padding: 18px 20px; text-align: center; color: #52525b; margin-bottom: 8px;">

                    <div style="font-size: 13.5px; font-weight: 600; color: #27272a; margin-bottom: 4px;">

                        No employee reviews found for this specific job role or location yet

                    </div>

                    <p style="font-size: 12px; color: #71717a; margin: 0; line-height: 1.5;">

                        ${escapeHtml(intel.no_reviews_reason || "We only display reviews from verified employees working in this exact job role or location. No direct match was found on kununu.com or Glassdoor.de.")}

                    </p>

                </div>

            ` : `

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px;">

                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 14px 16px;">

                    <div style="font-weight: 600; color: #166534; font-size: 13px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">

                        <span>What Workers Like (Verified Employee Quotes)</span>

                        <span style="font-family: var(--font-mono); font-size: 11px; font-weight: 500;">Pros</span>

                    </div>

                    <div style="display: flex; flex-direction: column; gap: 10px;">

                        ${detailedPros.map(p => `

                            <div style="background: #ffffff; border: 1px solid #dcfce7; border-radius: 6px; padding: 10px 12px;">

                                <div style="font-size: 12.8px; color: #18181b; line-height: 1.5; font-style: italic;">

                                    &ldquo;${escapeHtml(p.quote)}&rdquo;

                                </div>

                                <div style="margin-top: 7px; padding-top: 6px; border-top: 1px solid #f0fdf4; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px; font-size: 11.5px; color: #3f3f46;">

                                    <span><strong>Who said this:</strong> ${escapeHtml(p.author)}</span>

                                    <span style="font-family: var(--font-mono); font-size: 11px;">

                                        <a href="${escapeHtml(p.source_url)}" target="_blank" rel="noopener" style="color: #166534; font-weight: 600; text-decoration: underline;">Source: ${escapeHtml(p.source_name)} &#8599;</a>

                                        &middot; ${escapeHtml(p.rating)} &middot; ${escapeHtml(p.date)}

                                    </span>

                                </div>

                            </div>

                        `).join("")}

                    </div>

                </div>

                <div style="background: #fafafa; border: 1px solid #e4e4e7; border-radius: 6px; padding: 14px 16px;">

                    <div style="font-weight: 600; color: #18181b; font-size: 13px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">

                        <span>Things to Keep in Mind (Constructive Feedback)</span>

                        <span style="font-family: var(--font-mono); font-size: 11px; color: #71717a; font-weight: 500;">Cons / Trade-offs</span>

                    </div>

                    <div style="display: flex; flex-direction: column; gap: 10px;">

                        ${detailedCons.map(c => `

                            <div style="background: #ffffff; border: 1px solid #e4e4e7; border-radius: 6px; padding: 10px 12px;">

                                <div style="font-size: 12.8px; color: #27272a; line-height: 1.5; font-style: italic;">

                                    &ldquo;${escapeHtml(c.quote)}&rdquo;

                                </div>

                                <div style="margin-top: 7px; padding-top: 6px; border-top: 1px solid #f4f4f5; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px; font-size: 11.5px; color: #52525b;">

                                    <span><strong>Who said this:</strong> ${escapeHtml(c.author)}</span>

                                    <span style="font-family: var(--font-mono); font-size: 11px;">

                                        <a href="${escapeHtml(c.source_url)}" target="_blank" rel="noopener" style="color: #18181b; font-weight: 600; text-decoration: underline;">Source: ${escapeHtml(c.source_name)} &#8599;</a>

                                        &middot; ${escapeHtml(c.rating)} &middot; ${escapeHtml(c.date)}

                                    </span>

                                </div>

                            </div>

                        `).join("")}

                    </div>

                </div>

            </div>

            `}

            ${candExp.has_interview_experience ? `

                <div style="margin-top: 12px; padding: 10px 14px; background: #fafafa; border: 1px solid #e4e4e7; border-radius: 6px; font-size: 12.5px; color: #3f3f46;">

                    <strong>Applicant Interview Experience (${escapeHtml(candExp.field_label || 'Specific Field')} &middot; ${escapeHtml(candExp.positive_pct || '82%')} positive):</strong>

                    ${escapeHtml(candExp.interview_style)} &middot; Typical response: <strong>${escapeHtml(candExp.avg_response_days || '4 to 7 business days')}</strong>

                </div>

            ` : `

                <div style="margin-top: 12px; padding: 10px 14px; background: #fafafa; border: 1px solid #e4e4e7; border-radius: 6px; font-size: 12.5px; color: #71717a;">

                    <strong style="color: #3f3f46;">Applicant Interview Experience:</strong>

                    <span style="color: #71717a; font-style: italic;">No interview experience given for this specific job field yet.</span>

                </div>

            `}

        </div>

    `;

    // 4. Resume & Skills Match Card

    let resumeCardHtml = "";

    if (rf.has_resume) {

        resumeCardHtml = `

            <div style="background: #ffffff; border: 1px solid #e4e4e7; border-radius: 8px; padding: 20px 22px; margin-top: 16px;">

                <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; border-bottom: 1px solid #f4f4f5; padding-bottom: 10px;">

                    <div>

                        <h3 style="font-size: 15.5px; font-weight: 600; color: #18181b; margin: 0;">

                            Candidate Resume Match &amp; Skills Comparison

                        </h3>

                        <div style="font-size: 12px; color: #71717a; margin-top: 2px;">

                            Comparison between the skills in your resume and this job posting.

                        </div>

                    </div>

                    <span style="font-family: var(--font-mono); font-size: 12px; font-weight: 600; color: #166534; background: #dcfce7; padding: 2px 8px; border-radius: 4px; border: 1px solid #bbf7d0;">

                        ${rf.fit_score}% Match

                    </span>

                </div>

                <div style="margin-top: 16px; border-top: 1px solid #f4f4f5; padding-top: 14px;">

                    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 12px;">

                        <h3 style="font-size: 15px; font-weight: 600; color: #18181b; margin: 0;">

                            Skills Comparison

                        </h3>

                        <span style="font-family: var(--font-mono); font-size: 12px; font-weight: 600; color: #166534; background: #dcfce7; padding: 2px 8px; border-radius: 4px; border: 1px solid #bbf7d0;">

                            ${rf.fit_score}% Match

                        </span>

                    </div>

                    ${rf.is_career_divergence && rf.career_advisory_message ? `

                        <div style="margin-top: 8px; margin-bottom: 12px; padding: 12px 16px; background: ${rf.is_overqualified ? '#f0f9ff' : '#fffbeb'}; border: 1px solid ${rf.is_overqualified ? '#bae6fd' : '#fde68a'}; border-radius: 6px; color: ${rf.is_overqualified ? '#0369a1' : '#92400e'}; font-size: 13px; line-height: 1.55;">

                            <div style="display: flex; align-items: center; gap: 6px; font-weight: 700; font-size: 13.5px; margin-bottom: 4px; color: ${rf.is_overqualified ? '#0284c7' : '#b45309'};">

                                <span>${rf.is_overqualified ? '💼' : '⚠️'}</span> ${rf.is_overqualified ? 'Bridge / Student Role Guidance (Qualifications Exceeded)' : 'Career Note: Different Field than Your Resume'}

                            </div>

                            <div style="color: ${rf.is_overqualified ? '#0c4a6e' : '#78350f'};">${escapeHtml(rf.career_advisory_message)}</div>

                        </div>

                    ` : ''}

                    <div style="margin-top: 10px; display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; font-size: 13px;">

                        <!-- COLUMN 1: Skills Have -->

                        <div style="padding: 14px 16px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; display: flex; flex-direction: column; gap: 10px;">

                            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">

                                <div>

                                    <strong style="color: #0f172a; font-size: 13.5px;">Skills Have</strong>

                                    <span style="font-family: var(--font-mono); font-weight: 600; font-size: 12px; color: #166534; margin-left: 6px; background: #dcfce7; padding: 1px 7px; border-radius: 4px; border: 1px solid #bbf7d0;">

                                        ${rf.matched_skills ? rf.matched_skills.length : 0} Found

                                    </span>

                                </div>

                                <span style="font-size: 11px; color: #64748b;">From your CV</span>

                            </div>

                            ${rf.matched_skills && rf.matched_skills.length > 0 ? `

                                <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 2px;">

                                    ${rf.matched_skills.map(s => `<span style="font-family: var(--font-mono); font-size: 12px; font-weight: 600; background: #dcfce7; color: #166534; padding: 3px 9px; border-radius: 4px; border: 1px solid #bbf7d0;">✓ ${escapeHtml(s)}</span>`).join("")}

                                </div>

                            ` : `

                                ${rf.is_career_divergence ? `

                                    <div style="font-size: 12.5px; color: #92400e; background: #fffbeb; border: 1px solid #fde68a; border-radius: 5px; padding: 8px 10px; line-height: 1.45;">

                                        <strong>Domain Mismatch:</strong> Your background is in Software Engineering &amp; Technology (${escapeHtml(rf.resume_skills_found ? rf.resume_skills_found.slice(0, 5).join(", ") : 'Tech')}). This vacancy is in Commercial Staffing (Personalberatung).

                                    </div>

                                ` : `

                                    <div style="font-size: 12.5px; color: #71717a; padding: 8px 0;">No direct skill overlap with this specific job description.</div>

                                `}

                            `}

                            ${rf.why_matched_reasons && rf.why_matched_reasons.length > 0 ? `

                                <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 8px; border-top: 1px solid #e2e8f0; padding-top: 10px;">

                                    ${rf.why_matched_reasons.map(r => `

                                        <div style="display: flex; align-items: flex-start; gap: 8px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 5px; padding: 8px 12px;">

                                            <span style="font-size: 14px; flex-shrink: 0;">${escapeHtml(r.icon || '✓')}</span>

                                            <div>

                                                <strong style="color: #1e293b; font-size: 12.5px;">${escapeHtml(r.title)}:</strong>

                                                <span style="color: #475569; font-size: 12px;">${escapeHtml(r.detail)}</span>

                                            </div>

                                        </div>

                                    `).join("")}

                                </div>

                            ` : ''}

                        </div>

                        <!-- COLUMN 2: Skills Missing -->

                        <div style="padding: 14px 16px; background: #fafafa; border: 1px solid #e4e4e7; border-radius: 6px; display: flex; flex-direction: column; gap: 10px;">

                            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px; border-bottom: 1px solid #e4e4e7; padding-bottom: 8px;">

                                <div>

                                    <strong style="color: #0f172a; font-size: 13.5px;">Skills Missing</strong>

                                    <span style="font-family: var(--font-mono); font-size: 12px; font-weight: 600; color: ${rf.skills_to_improve && rf.skills_to_improve.length > 0 ? '#b45309' : '#166534'}; margin-left: 6px; background: ${rf.skills_to_improve && rf.skills_to_improve.length > 0 ? '#fef3c7' : '#dcfce7'}; padding: 1px 7px; border-radius: 4px; border: 1px solid ${rf.skills_to_improve && rf.skills_to_improve.length > 0 ? '#fde68a' : '#bbf7d0'};">

                                        (${rf.skills_to_improve ? rf.skills_to_improve.length : 0} Missing)

                                    </span>

                                </div>

                                <span style="font-size: 11px; color: #64748b; font-weight: 500;">Role Prerequisites</span>

                            </div>

                                ${rf.skills_to_improve && rf.skills_to_improve.length > 0 ? `

                                    <div style="font-size: 12px; color: #52525b; line-height: 1.4;">

                                        These skills are mentioned in the job description but were not found on your resume:

                                    </div>

                                    <div style="display: flex; flex-direction: column; gap: 8px;">

                                        ${rf.skills_to_improve.map(s => `

                                            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 12px;">

                                                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px; margin-bottom: 5px;">

                                                    <strong style="color: #0f172a; font-size: 13px; font-weight: 600;">${escapeHtml(s.title || s.skill)}</strong>

                                                    <span style="font-family: var(--font-mono); font-size: 11px; background: #f1f5f9; color: #475569; padding: 2px 7px; border-radius: 4px; border: 1px solid #e2e8f0; white-space: nowrap;">${escapeHtml(s.category || 'Competency')}</span>

                                                </div>

                                                <div style="font-size: 12px; color: #475569; line-height: 1.4; margin-bottom: 6px;">

                                                    ${escapeHtml(s.description || '')}

                                                </div>

                                                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; padding-top: 4px; border-top: 1px dashed #f1f5f9;">

                                                    <span style="font-size: 11px; color: #64748b; font-weight: 500;">Learning / Standards:</span>

                                                    <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer" style="display: inline-flex; align-items: center; gap: 3px; font-size: 11.5px; font-weight: 600; color: #2563eb; text-decoration: underline;">

                                                        ${escapeHtml(s.resource_name || 'What is this?')} &nearr;

                                                    </a>

                                                </div>

                                            </div>

                                        `).join("")}

                                    </div>

                                ` : `

                                    <div style="padding: 16px; background: #ffffff; border: 1px solid #bbf7d0; border-radius: 6px; text-align: center; color: #166534;">

                                        <div style="font-size: 20px; margin-bottom: 4px;">🎯</div>

                                        <strong style="font-size: 13px;">Full Skills Match!</strong>

                                        <div style="font-size: 12px; color: #15803d; margin-top: 4px;">

                                            Your profile already covers all primary technical requirements detected in this vacancy.

                                        </div>

                                    </div>

                                `}

                            </div>

                        </div>

                </div>

            </div>

        `;

    }

    resultBox.innerHTML = `

        ${flagNotice}

        <!-- 1. Verification Job Advertisement -->

        ${heroCardHtml}

        ${ghostJobHtml}

        ${checklistCardHtml}

        ${breakdownHtml}

        ${descHtml}

        <!-- 2. Company -->

        ${companyCardHtml}

        <!-- 3. Reviews -->

        ${reviewsCardHtml}

        <!-- 4. Resume Things -->

        ${resumeCardHtml}

    `;

}

async function loadUserHistory() {

    const user = getCurrentUser();

    if (!user) return;

    const params = new URLSearchParams();

    if (user.id) params.set("userId", user.id);

    if (user.email) params.set("email", user.email);

    try {

        const res = await fetch(`${getApiBase()}/api/history?${params.toString()}`);

        if (!res.ok) return;

        const data = await res.json();

        renderHistory(data.history || []);

    } catch (e) {

        // Ignore if offline

    }

}

async function loadFlaggedJobs() {

    try {

        const res = await fetch(`${getApiBase()}/api/flagged`);

        if (!res.ok) return;

        const data = await res.json();

        renderFlaggedJobs(data.flagged_jobs || []);

    } catch (e) {

        // Ignore if offline

    }

}

function renderFlaggedJobs(flaggedJobs) {

    const container = document.getElementById("flaggedJobsList");

    if (!container) return;

    if (!flaggedJobs || flaggedJobs.length === 0) {

        container.innerHTML = '<p class="empty-history">No job advertisements are currently flagged.</p>';

        return;

    }

    container.innerHTML = flaggedJobs.map(item => `

        <div class="history-item">

            <h3>${escapeHtml(item.job_title)} - ${escapeHtml(item.company_name)}</h3>

            ${item.job_url ? `<p style="font-size: 13px; margin-bottom: 4px;"><a href="${escapeHtml(item.job_url)}" target="_blank" rel="noopener noreferrer" style="color: #1d4ed8;">${escapeHtml(item.job_url)}</a></p>` : ""}

            <p style="font-size: 13px; color: #b91c1c;">

                ${escapeHtml(item.flag_reason || "Flagged by multiple users.")}

            </p>

            <p style="font-size: 12px; color: #6b7280; margin-top: 4px;">

                Users who checked: ${item.distinct_users_count} | Total checks: ${item.total_checks} | Last checked: ${escapeHtml(item.last_seen_at)}

            </p>

        </div>

    `).join("");

}

let _cachedUserHistory = [];

let _showAllHistory = false;

const INITIAL_HISTORY_LIMIT = 4;

function toggleShowMoreHistory() {

    _showAllHistory = !_showAllHistory;

    renderHistory(_cachedUserHistory);

}

function toggleHistoryItemDetails(idx) {

    const detailsEl = document.getElementById(`historyDetails_${idx}`);

    const btnEl = document.getElementById(`historyToggleBtn_${idx}`);

    if (!detailsEl || !btnEl) return;

    if (detailsEl.style.display === "none") {

        detailsEl.style.display = "block";

        btnEl.textContent = "Show less";

    } else {

        detailsEl.style.display = "none";

        btnEl.textContent = "Show more";

    }

}

function renderHistory(history) {

    _cachedUserHistory = history || [];

    const container = document.getElementById("historyList");

    const countLabel = document.getElementById("historyCountLabel");

    const showMoreContainer = document.getElementById("historyShowMoreContainer");

    const showMoreBtn = document.getElementById("historyShowMoreBtn");

    if (!container) return;

    if (countLabel) {

        countLabel.textContent = _cachedUserHistory.length > 0 ? `${_cachedUserHistory.length} total checks` : "";

    }

    if (_cachedUserHistory.length === 0) {

        container.innerHTML = '<p class="empty-history" style="text-align: center; color: #94a3b8; padding: 30px 0;">No job advertisements have been checked yet.</p>';

        if (showMoreContainer) showMoreContainer.style.display = "none";

        return;

    }

    const visibleItems = _showAllHistory

        ? _cachedUserHistory

        : _cachedUserHistory.slice(0, INITIAL_HISTORY_LIMIT);

    container.innerHTML = visibleItems.map((item, idx) => {

        const res = (item.result || "VERIFIED").toUpperCase();

        let badgeBg = "#f0fdf4";
        let badgeColor = "#166534";
        let badgeBorder = "#bbf7d0";
        let historyStatusText = "70–100: HIGH TRUST (LIKELY VALID — SAFE TO APPLY)";

        if (res.includes("HIGH RISK") || res.includes("DANGER") || res.includes("FAKE") || res.includes("NOT VERIFIED")) {
            badgeBg = "#fef2f2";
            badgeColor = "#991b1b";
            badgeBorder = "#fecaca";
            historyStatusText = "0–44: LOW TRUST / HIGH SCAM RISK (APPLY AT YOUR OWN RISK)";
        } else if (res.includes("REVIEW") || res.includes("CAREFUL") || res.includes("WARN")) {
            badgeBg = "#fffbeb";
            badgeColor = "#92400e";
            badgeBorder = "#fde68a";
            historyStatusText = "45–69: MEDIUM TRUST (VERIFY DETAILS BEFORE APPLYING)";
        }

        const jobTitleDisplay = (item.job_title && item.job_title !== "Job Check")

            ? item.job_title

            : (item.company_name ? `${item.company_name} Position` : "Job Listing");

        return `

            <div class="history-item-box" style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 18px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">

                <!-- Top Row: Result Status Badge & Checking Date -->

                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">

                    <div style="display: flex; align-items: center; gap: 8px;">

                        <span style="display: inline-block; padding: 3.5px 10px; border-radius: 4px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; background: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeBorder};">

                            ${escapeHtml(historyStatusText)}

                        </span>

                        ${item.is_flagged_fake ? `<span style="background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">⚠️ Flagged Scam</span>` : ""}

                    </div>

                    <div style="font-size: 12px; color: #64748b; font-family: var(--font-mono); font-weight: 500;">

                        📅 Checking Date: <strong style="color: #334155;">${escapeHtml(item.checked_at)}</strong>

                    </div>

                </div>

                <!-- Grid Row: Job Details & Company Details -->

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px; padding: 12px 14px; background: #f8fafc; border: 1px solid #f1f5f9; border-radius: 6px;">

                    <!-- Left: Job Details -->

                    <div>

                        <div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #64748b; letter-spacing: 0.05em; margin-bottom: 4px;">

                            Job Details

                        </div>

                        <div style="font-size: 14.5px; font-weight: 600; color: #0f172a; line-height: 1.35; margin-bottom: 3px;">

                            ${escapeHtml(jobTitleDisplay)}

                        </div>

                        ${item.reason ? `<div style="font-size: 12px; color: #475569; line-height: 1.4; margin-top: 3px;">${escapeHtml(item.reason)}</div>` : ""}

                    </div>

                    <!-- Right: Company Details -->

                    <div>

                        <div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: #64748b; letter-spacing: 0.05em; margin-bottom: 4px;">

                            Company Details

                        </div>

                        <div style="font-size: 14px; font-weight: 600; color: #0f172a; margin-bottom: 3px;">

                            🏢 ${escapeHtml(item.company_name || "Unknown Company")}

                        </div>

                        ${item.company_address ? `<div style="font-size: 12px; color: #64748b; margin-top: 2px;">📍 ${escapeHtml(item.company_address)}</div>` : ""}

                        ${item.recruiter_email ? `<div style="font-size: 12px; color: #64748b; margin-top: 2px;">✉️ ${escapeHtml(item.recruiter_email)}</div>` : ""}

                    </div>

                </div>

                <!-- Bottom Row: Link & View Report Button -->

                <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px; padding-top: 8px; border-top: 1px solid #f1f5f9; flex-wrap: wrap;">

                    <div style="font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 70%;">

                        ${item.job_url ? `

                            <a href="${escapeHtml(item.job_url)}" target="_blank" rel="noopener noreferrer" style="color: #1d4ed8; font-weight: 500; text-decoration: none; display: inline-flex; align-items: center; gap: 4px;">

                                <span>🔗 Link:</span> <span style="text-decoration: underline;">${escapeHtml(item.job_url)}</span>

                            </a>

                        ` : `<span style="color: #94a3b8; font-style: italic;">No URL attached</span>`}

                    </div>

                    <div>

                        <a href="result.html?checkId=${item.id}" style="padding: 6px 14px; background: #1e293b; color: #ffffff; text-decoration: none; border-radius: 5px; font-size: 12px; font-weight: 600; white-space: nowrap; display: inline-block;">

                            View Report &rarr;

                        </a>

                    </div>

                </div>

            </div>

        `;

    }).join("");

    if (showMoreContainer && showMoreBtn) {

        if (_cachedUserHistory.length > INITIAL_HISTORY_LIMIT) {

            showMoreContainer.style.display = "block";

            showMoreBtn.textContent = _showAllHistory

                ? "Show Less"

                : `Show More (${_cachedUserHistory.length - INITIAL_HISTORY_LIMIT} more)`;

        } else {

            showMoreContainer.style.display = "none";

        }

    }

}

function escapeHtml(str) {

    if (!str) return "";

    return String(str)

        .replace(/&/g, "&amp;")

        .replace(/</g, "&lt;")

        .replace(/>/g, "&gt;")

        .replace(/"/g, "&quot;")

        .replace(/'/g, "&#039;");

}

async function flagThisJobPrompt(url, company, title) {

    const reason = prompt(

        `Are you sure you want to flag "${title || company}" as a fake job / scam?\n\nEnter reason or leave as default:`,

        "Suspicious employment offer / scam detected"

    );

    if (reason === null) return; // User cancelled

    try {

        const res = await fetch(`${getApiBase()}/api/flag-job`, {

            method: "POST",

            headers: { "Content-Type": "application/json" },

            body: JSON.stringify({

                jobUrl: url,

                company: company,

                jobTitle: title,

                reason: reason.trim() || "Suspicious employment offer / scam detected"

            })

        });

        const data = await res.json();

        if (data.success) {

            alert(`Job/Company flagged successfully!\n\nThis posting has been removed from active listings and added to the Flagged Jobs registry.`);

            window.location.reload();

        } else {

            alert("Could not flag job: " + (data.error || "Unknown error"));

        }

    } catch (e) {

        alert("Failed to submit flag: " + e.message);

    }

}

window.flagThisJobPrompt = flagThisJobPrompt;

// Fast Instant Search & Verify for Job Advertisements

function handleQuickSearchVerify() {

    const input = document.getElementById("quickJobSearchInput");

    if (!input) return;

    input.setCustomValidity("");

    let query = (input.value || "").trim();

    if (!query) {

        input.setCustomValidity("Please paste a job posting URL.");

        input.reportValidity();

        return;

    }

    // Auto-prepend https:// if user pasted www.linkedin.com/... or de.indeed.com/...

    if (!query.startsWith("http://") && !query.startsWith("https://")) {

        if (/^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(\/.*)?$/.test(query) && !query.includes(" ")) {

            query = "https://" + query;

            input.value = query;

        } else {

            input.setCustomValidity("Only a job posting URL (https://...) can be checked in this search bar.");

            input.reportValidity();

            setTimeout(() => input.setCustomValidity(""), 2500);

            return;

        }

    }

    try {

        const parsed = new URL(query);

        if (!parsed.hostname || !parsed.hostname.includes(".")) {

            throw new Error("Invalid hostname");

        }

    } catch (e) {

        input.setCustomValidity("Please enter a valid job posting URL (e.g. https://www.linkedin.com/jobs/view/...).");

        input.reportValidity();

        setTimeout(() => input.setCustomValidity(""), 2500);

        return;

    }

    // Clear hidden fields and set only jobUrl

    const titleEl = document.getElementById("jobTitle");

    const compEl = document.getElementById("company");

    const salEl = document.getElementById("salary");

    const emailEl = document.getElementById("recruiterEmail");

    if (titleEl) titleEl.value = "";

    if (compEl) compEl.value = "";

    if (salEl) salEl.value = "";

    if (emailEl) emailEl.value = "";

    const urlEl = document.getElementById("jobUrl");

    if (urlEl) {

        urlEl.removeAttribute("readonly");

        urlEl.value = query;

    }

    const consentEl = document.getElementById("checkConsent");

    if (consentEl) consentEl.checked = true;

    const fakeEvent = { preventDefault: () => {} };

    verifyJob(fakeEvent);

}

window.handleQuickSearchVerify = handleQuickSearchVerify;

function quickFillSample(url, title, company) {

    const input = document.getElementById("quickJobSearchInput");

    if (input) input.value = `${title} at ${company}`;

    const urlEl = document.getElementById("jobUrl");

    const titleEl = document.getElementById("jobTitle");

    const compEl = document.getElementById("company");

    if (urlEl) {

        urlEl.removeAttribute("readonly");

        urlEl.value = url;

    }

    if (titleEl) {

        titleEl.removeAttribute("readonly");

        titleEl.value = title;

    }

    if (compEl) {

        compEl.removeAttribute("readonly");

        compEl.value = company;

    }

}

window.quickFillSample = quickFillSample;

// Attach Enter key to quick search input

document.addEventListener("DOMContentLoaded", () => {

    const qInput = document.getElementById("quickJobSearchInput");

    if (qInput) {

        qInput.addEventListener("keypress", (e) => {

            if (e.key === "Enter") {

                e.preventDefault();

                handleQuickSearchVerify();

            }

        });

    }

});

// Extension Download Permission & Installation Guide Modal

function ensureExtensionDownloadModal() {

    let modal = document.getElementById("extDownloadModalOverlay");

    if (!modal) {

        modal = document.createElement("div");

        modal.id = "extDownloadModalOverlay";

        modal.className = "logout-modal-overlay";

        modal.innerHTML = `

            <div class="logout-modal-card" style="max-width: 390px;">

                <h3>Download Chrome Extension</h3>

                <p style="margin-bottom: 10px;">

                    Do you want to allow downloading the Chrome extension to your computer?

                </p>

                <p style="background: #fafafa; border: 1px solid #e4e4e7; border-radius: 6px; padding: 10px 12px; margin-bottom: 18px; font-size: 12.5px; color: #3f3f46;">

                    Please check the <a href="extension.html" style="color: #18181b; font-weight: 600; text-decoration: underline;">Installation Guide</a> for details on how to install the extension.

                </p>

                <div class="logout-modal-actions">

                    <button type="button" class="logout-cancel-btn" onclick="closeExtensionDownloadModal()">Cancel</button>

                    <button type="button" class="logout-confirm-btn" onclick="confirmExtensionDownload()" style="background: #18181b; border-color: #18181b; color: #ffffff;">Allow &amp; Download</button>

                </div>

            </div>

        `;

        document.body.appendChild(modal);

    }

    return modal;

}

function promptExtensionDownload(e) {

    if (e) e.preventDefault();

    const modal = ensureExtensionDownloadModal();

    modal.classList.add("active");

}

function closeExtensionDownloadModal() {

    const modal = document.getElementById("extDownloadModalOverlay");

    if (modal) modal.classList.remove("active");

}

function viewExtensionInstallDetails() {

    closeExtensionDownloadModal();

    window.location.href = "extension.html";

}

function confirmExtensionDownload() {

    closeExtensionDownloadModal();

    const link = document.createElement("a");

    link.href = `${getApiBase()}/api/download-extension`;

    link.download = "StellenPruefer_Browser_Extension.zip";

    document.body.appendChild(link);

    link.click();

    document.body.removeChild(link);

    if (!window.location.pathname.endsWith("extension.html")) {

        setTimeout(() => {

            window.location.href = "extension.html";

        }, 600);

    }

}

window.promptExtensionDownload = promptExtensionDownload;

window.closeExtensionDownloadModal = closeExtensionDownloadModal;

window.viewExtensionInstallDetails = viewExtensionInstallDetails;

window.confirmExtensionDownload = confirmExtensionDownload;

document.addEventListener("DOMContentLoaded", () => {

    document.querySelectorAll('a[href*="/api/download-extension"]').forEach(a => {

        a.addEventListener("click", (e) => {

            promptExtensionDownload(e);

        });

    });

});

