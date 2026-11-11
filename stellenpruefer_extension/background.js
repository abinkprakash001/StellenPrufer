const API_BASE = "http://127.0.0.1:5000";

// Keep active job tabs in storage so state survives service worker sleep cycles
async function getActiveJobTabs() {
  try {
    const data = await chrome.storage.local.get(["activeJobTabs"]);
    return data.activeJobTabs || {};
  } catch (e) {
    return {};
  }
}

async function setActiveJobTabs(tabs) {
  try {
    await chrome.storage.local.set({ activeJobTabs: tabs });
  } catch (e) {}
}

function inspectTabForJob(tab) {
  if (!tab || !tab.url || !tab.id) return null;
  const url = tab.url.toLowerCase();
  if (url.startsWith("chrome://") || url.startsWith("edge://") || url.startsWith("about:")) return null;
  if (url.includes("127.0.0.1:5000") || url.includes("localhost:5000")) return null;
  if (url.includes("google.com/search") || url.includes("bing.com/search") || url.includes("web.whatsapp.com")) return null;

  const title = (tab.title || "").trim();
  const titleLower = title.toLowerCase();

  const isJobUrl = url.includes("indeed.") || url.includes("linkedin.com") || url.includes("stepstone.") ||
                   url.includes("stellenanzeigen.") || url.includes("arbeitsagentur.") ||
                   url.includes("karriere") || url.includes("career") ||
                   url.includes("stellen") || url.includes("vakanz") ||
                   url.includes("job") || url.includes("arbeit") ||
                   url.includes("bewerb") || url.includes("berlin.de") ||
                   url.includes("work") || url.includes("portal");

  const hasJobSignals = titleLower.includes("(m/w/d)") || titleLower.includes("(m/f/d)") ||
                        titleLower.includes("(gn)") || titleLower.includes("(w/m/d)") ||
                        titleLower.includes("(d/m/w)") || titleLower.includes("stellenangebot") ||
                        titleLower.includes("job post") || titleLower.includes("job offer") ||
                        titleLower.includes("karriere") || titleLower.includes("career") ||
                        titleLower.includes("job") || titleLower.includes("pfleger") ||
                        titleLower.includes("caregiver") || titleLower.includes("pflege") ||
                        titleLower.includes("assistant") || titleLower.includes("mitarbeit");

  if (!isJobUrl && !hasJobSignals) return null;

  let jobTitle = title;
  let companyName = "";

  const titleParts = title.split(/\s*[-|–—•]\s*/);
  if (titleParts.length >= 2) {
    jobTitle = titleParts[0].trim();
    companyName = titleParts[titleParts.length - 1].trim();
    companyName = companyName.replace(/^(jobs?|karriere|stellenangebote?|bewerbung)\s*(in|bei)?\s*/i, "").trim();
  }

  if (!companyName) {
    try {
      const u = new URL(tab.url);
      const hostPart = u.hostname.replace(/^www\./, "").split(".")[0];
      companyName = hostPart.split("-").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
    } catch (e) {}
  }

  return {
    url: tab.url,
    title: jobTitle || title,
    company: companyName,
    tabId: tab.id
  };
}

function injectIntoTab(tabId, url) {
  if (!url || (!url.startsWith("http://") && !url.startsWith("https://"))) return;
  if (url.includes("127.0.0.1:5000") || url.includes("localhost:5000")) return;
  chrome.scripting.executeScript({
    target: { tabId },
    files: ["content.js"]
  }).catch(() => {});
}

async function syncTabDirectly(tab) {
  const job = inspectTabForJob(tab);
  if (!job) return;

  const activeTabs = await getActiveJobTabs();
  activeTabs[String(tab.id)] = job;
  await setActiveJobTabs(activeTabs);

  try {
    await chrome.storage.local.set({ latest_synced_job: job });
  } catch (e) {}

  fetch(`${API_BASE}/api/sync-tab-job`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(job)
  }).catch(() => {});
}

function scanAllOpenTabs() {
  chrome.tabs.query({}, async (tabs) => {
    for (const tab of tabs) {
      if (tab.id && tab.url) {
        injectIntoTab(tab.id, tab.url);
        await syncTabDirectly(tab);
      }
    }
  });
}

chrome.runtime.onInstalled.addListener(scanAllOpenTabs);
chrome.runtime.onStartup.addListener(scanAllOpenTabs);
scanAllOpenTabs();

chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    if (tab && tab.url) {
      injectIntoTab(tab.id, tab.url);
      await syncTabDirectly(tab);
    }
  } catch (e) {}
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (tab && tab.url && (changeInfo.status === "complete" || changeInfo.title || changeInfo.url)) {
    injectIntoTab(tabId, tab.url);
    await syncTabDirectly(tab);
  }
});

chrome.tabs.onRemoved.addListener(async (tabId) => {
  const activeTabs = await getActiveJobTabs();
  const tabKey = String(tabId);
  if (!activeTabs[tabKey]) return;

  delete activeTabs[tabKey];
  await setActiveJobTabs(activeTabs);
  const remainingKeys = Object.keys(activeTabs);

  if (remainingKeys.length === 0) {
    await chrome.storage.local.remove(["latest_synced_job", "latestActiveJob"]);
    fetch(`${API_BASE}/api/clear-synced-job?tabId=${tabId}&reason=job_tab_closed`, { method: "POST" }).catch(() => {});
  } else {
    const nextJob = activeTabs[remainingKeys[0]];
    fetch(`${API_BASE}/api/sync-tab-job`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...nextJob, tabId: remainingKeys[0] })
    }).catch(() => {});
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type === "SYNC_JOB") {
    const job = message.payload || {};
    const tabId = sender && sender.tab ? sender.tab.id : null;
    (async () => {
      if (tabId && (job.title || job.company)) {
        const activeTabs = await getActiveJobTabs();
        activeTabs[String(tabId)] = job;
        await setActiveJobTabs(activeTabs);
      }
      try {
        await chrome.storage.local.set({ latest_synced_job: job });
      } catch (e) {}

      fetch(`${API_BASE}/api/sync-tab-job`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...job, tabId })
      })
        .then(res => res.json())
        .then(data => sendResponse({ ok: true, data }))
        .catch(err => sendResponse({ ok: false, error: err.message }));
    })();
    return true;
  }

  if (message && message.type === "CLEAR_SYNCED_JOB") {
    const tabId = sender && sender.tab ? sender.tab.id : null;
    (async () => {
      const activeTabs = await getActiveJobTabs();
      if (tabId) {
        delete activeTabs[String(tabId)];
        await setActiveJobTabs(activeTabs);
      }
      await chrome.storage.local.remove(["latest_synced_job", "latestActiveJob"]);
      fetch(`${API_BASE}/api/clear-synced-job${tabId ? `?tabId=${tabId}` : ""}`, { method: "POST" })
        .then(r => r.json())
        .then(d => sendResponse({ ok: true, d }))
        .catch(() => sendResponse({ ok: false }));
    })();
    return true;
  }

  if (message && message.type === "VERIFY_JOB") {
    const tabId = sender && sender.tab ? sender.tab.id : null;
    if (tabId) {
      (async () => {
        const activeTabs = await getActiveJobTabs();
        activeTabs[String(tabId)] = message.payload || {};
        await setActiveJobTabs(activeTabs);
      })();
    }
    fetch(`${API_BASE}/api/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(message.payload || {})
    })
      .then(res => res.json())
      .then(data => {
        if (sender && sender.tab && sender.tab.id && data && data.success) {
          const score = typeof data.trust_score === "number" ? data.trust_score : 50;
          const isValid = (data.result === "LIKELY VALID" || data.result === "VERIFIED" || score >= 75);
          chrome.action.setBadgeText({ tabId: sender.tab.id, text: `${score}%` });
          chrome.action.setBadgeBackgroundColor({
            tabId: sender.tab.id,
            color: isValid ? "#16a34a" : (score <= 35 || data.result === "HIGH RISK" ? "#dc2626" : "#ca8a04")
          });
        }
        sendResponse({ ok: true, data });
      })
      .catch(err => {
        sendResponse({ ok: false, error: err ? err.message : "Server offline" });
      });
    return true;
  }
});
