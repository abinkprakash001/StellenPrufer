// Content script for in-page job metadata extraction
(() => {
  const existingHost = document.getElementById("stellenpruefer-auto-popup-host");
  if (existingHost) existingHost.remove();
  if (window.__spWatchInterval) clearInterval(window.__spWatchInterval);

  function cleanText(s) {
    return (s || "").replace(/\s+/g, " ").trim();
  }

  function cleanDescription(s) {
    return (s || "")
      .replace(/\r\n/g, "\n")
      .replace(/[ \t\f\v\u00a0]+/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function isBoardName(name) {
    if (!name) return true;
    const c = name.toLowerCase().replace(/[^a-z0-9]/g, "");
    const boards = [
      "stellenanzeigen", "stellenanzeigende", "stepstone", "stepstonede",
      "indeed", "indeedcom", "linkedin", "xing", "monster", "glassdoor",
      "arbeitsagentur", "bundesagentur", "jobware", "meinestadt", "kimeta", "heyjobs"
    ];
    return boards.some(b => c === b || c.includes(b));
  }

  function isBadCompany(name) {
    if (!name) return true;
    if (isBoardName(name)) return true;
    const low = name.toLowerCase();
    return (
      low.includes("filterbar") ||
      low.includes("kein filterbarer") ||
      low.includes("arbeitgeber a-z") ||
      low.includes("jobs in ") ||
      low.includes("jobsuche der ba") ||
      low.includes("9-1") ||
      low === "employer on screen" ||
      low === "company" ||
      low === "company verified" ||
      low === "detecting employer..."
    );
  }

  function isBadTitle(t) {
    if (!t) return true;
    const low = t.toLowerCase().trim();
    return (
      /^(?:stellenangebot|jobangebot|jobsuche|jobs\s+in)[:\s]*$/i.test(low) ||
      /^\d+[\d.,]*\s+jobs\s+in/i.test(low) ||
      low.includes("jobs in ") ||
      low.includes("jobsuche der ba") ||
      low.includes("kein filterbarer") ||
      low.includes("filterbarer inhalt") ||
      low === "job listing" ||
      low === "job offer page" ||
      low === "current web page" ||
      low === "selected job position" ||
      low === "job position" ||
      low === "loading job details..."
    );
  }

  function extractPageJobData() {
    let finalUrl = window.location.href;
    const urlParams = new URLSearchParams(window.location.search);
    let urlJobId = urlParams.get("id") || urlParams.get("refnr") || urlParams.get("vjk") || urlParams.get("jobId") || urlParams.get("jobid") || urlParams.get("currentJobId") || urlParams.get("jk") || "";

    let jobTitle = "";
    let companyName = "";
    let companyAddress = "";
    let salary = "";
    let recruiterEmail = "";
    let datePosted = "";
    let description = "";

    const host = window.location.hostname.toLowerCase();
    const isSearchOrSplit = (
      window.location.pathname.includes("/suche") ||
      window.location.pathname.includes("/search") ||
      window.location.search.includes("locationIds") ||
      window.location.search.includes("suchbereich") ||
      window.location.search.includes("srp=") ||
      document.querySelector('[data-selected="true"], [data-testid="company-name-link"]') !== null
    );

    // 1. Stellenanzeigen.de (Search list & split detail view)
    if (host.includes("stellenanzeigen.de")) {
      // A. If urlJobId is present, match the exact card in the list
      let activeCard = null;
      if (urlJobId) {
        activeCard = document.querySelector(`div[data-jobid="${urlJobId}"], div[data-job-id="${urlJobId}"], a[href*="${urlJobId}"]`);
        if (activeCard && activeCard.tagName === "A") {
          activeCard = activeCard.closest('div[data-jobid]') || activeCard;
        }
      }
      if (!activeCard) {
        activeCard = document.querySelector('div[data-jobid][data-selected="true"], div[data-jobid].jobTeaser-selected');
      }

      if (activeCard) {
        const titleEl = activeCard.querySelector('[data-testid="enhanced-link"], h3, h2, [data-testid="qa-hitzone"]');
        if (titleEl) {
          const tText = cleanText(titleEl.innerText || titleEl.textContent || titleEl.getAttribute("title"));
          if (tText && !isBadTitle(tText)) jobTitle = tText.replace(/\s+Job\s+.*$/i, "").trim();
        }
        const compEl = activeCard.querySelector('[data-testid="company-name-text"], [data-testid="company-name"]');
        if (compEl && !isBadCompany(compEl.innerText)) {
          companyName = cleanText(compEl.innerText);
        }
        const locEl = activeCard.querySelector('.sc-2e10cdc6-20, [class*="location"]');
        if (locEl && !companyAddress) companyAddress = cleanText(locEl.innerText);

        const hitzone = activeCard.querySelector('a[data-testid="qa-hitzone"], a[data-testid="enhanced-link"], a[href*="/job/"]');
        if (hitzone && hitzone.getAttribute("href")) {
          try {
            const rel = hitzone.getAttribute("href");
            const resolved = new URL(rel, window.location.origin).href;
            if (resolved.includes("/job/")) finalUrl = resolved;
          } catch (e) {}
        }
      }

      // B. Right detail pane header & company link
      const compLink = document.querySelector('a[data-testid="company-name-link"]');
      if (compLink && !companyName) {
        const cText = compLink.querySelector('[data-testid="company-name-text"]') || compLink;
        if (cText && cleanText(cText.innerText) && !isBadCompany(cleanText(cText.innerText))) {
          companyName = cleanText(cText.innerText);
        }
      }

      // Right detail title
      if (!jobTitle) {
        const headings = Array.from(document.querySelectorAll('main h1, main h2, h1, h2, h3'));
        for (const h of headings) {
          if (h.closest('div[data-jobid]')) continue;
          const ht = cleanText(h.innerText);
          if (ht && (ht.includes("(m/w/d)") || ht.includes("(m/f/d)") || ht.includes("(gn)") || ht.includes("*in")) && !isBadTitle(ht)) {
            jobTitle = ht;
            break;
          }
        }
      }

      if (!jobTitle) {
        const hList = Array.from(document.querySelectorAll('main h1, h1, h2'));
        for (const h of hList) {
          if (h.closest('div[data-jobid]') || h.closest('nav') || h.closest('header')) continue;
          const ht = cleanText(h.innerText);
          if (ht && !isBadTitle(ht)) {
            jobTitle = ht;
            break;
          }
        }
      }

      if (!companyAddress) {
        const locEl = document.querySelector('[data-testid*="location"], [class*="location"]');
        if (locEl && !locEl.closest('div[data-jobid]')) {
          const txt = cleanText(locEl.innerText);
          if (txt && !txt.includes("Sortieren") && txt.length < 100) companyAddress = txt;
        }
      }

      const rightPane = Array.from(document.querySelectorAll("div, section, article")).find(el => {
        return !el.closest('div[data-jobid]') && (el.innerText || "").includes("Ref-Nr") && (el.innerText || "").length > 200;
      });
      if (rightPane) {
        description = cleanText(rightPane.innerText).slice(0, 7000);
      }

      if (!datePosted) {
        const neuMatch = (document.body ? document.body.innerText : "").match(/Neu:\s*([0-9./-]+)/i);
        if (neuMatch) datePosted = neuMatch[1].trim();
      }
    }

    // 2. Arbeitsagentur (Jobsuche der Bundesagentur für Arbeit)
    if (host.includes("arbeitsagentur.de")) {
      const refnr = urlJobId || (window.location.pathname.match(/jobdetail\/([\w\-]+)/) || [])[1] || (window.location.search.match(/[?&]id=([\w\-]+)/) || [])[1] || "";
      if (refnr) {
        finalUrl = `https://www.arbeitsagentur.de/jobsuche/jobdetail/${refnr}`;
      }

      // A. Center/Right Detail View (when viewing job or clicked in search list)
      const applyBtn = Array.from(document.querySelectorAll("button, a")).find(b => /info zur bewerbung|vormerken/i.test((b.innerText || "").trim()));
      let detailPane = applyBtn ? applyBtn.closest('jb-job-detail, jb-steadetail-kopfbereich, section, div[class*="detail"], main') : null;
      if (!detailPane) {
        detailPane = document.querySelector("jb-job-detail, jb-steadetail-kopfbereich, [id*='detail-kopfbereich'], .detailansicht");
      }

      if (detailPane) {
        const tEl = detailPane.querySelector("#detail-kopfbereich-titel, [id*='kopfbereich-titel'], h1, h2, h3");
        if (tEl && !isBadTitle(cleanText(tEl.innerText))) {
          jobTitle = cleanText(tEl.innerText).replace(/^\d+[\.\:\s]+/, "");
        }
        const fEl = detailPane.querySelector("#detail-kopfbereich-firma, [id*='kopfbereich-firma'], .firma-lane, [class*='firma']");
        if (fEl && !isBadCompany(cleanText(fEl.innerText))) {
          companyName = cleanText(fEl.innerText);
        }
        const aEl = detailPane.querySelector("#detail-kopfbereich-arbeitsort, [id*='kopfbereich-arbeitsort'], [id*='arbeitsort']");
        if (aEl) companyAddress = cleanText(aEl.innerText);

        const dEl = detailPane.querySelector("#detail-beschreibung-container, [id*='beschreibung-container'], [class*='beschreibung']");
        if (dEl) description = cleanDescription(dEl.innerText).slice(0, 7000);

        const salEl = detailPane.querySelector("[id*='gehalt'], [id*='verguetung'], .gehalt-lane");
        if (salEl) salary = cleanText(salEl.innerText);
      }

      // B. If we have refnr, look for the matching item in the search list
      if (refnr && (!jobTitle || !companyName)) {
        const linkEl = document.querySelector(`[id*="${refnr}"], a[href*="${refnr}"]`);
        if (linkEl) {
          const card = linkEl.closest('li, jb-job-listen-eintrag') || linkEl;
          const tEl = card.querySelector('h2, [id$="-titel"], .titel-lane');
          if (tEl && !isBadTitle(cleanText(tEl.innerText))) {
            const cleanT = cleanText(tEl.innerText).replace(/^\d+[\:\.\s]+/, "");
            const beiMatch = cleanT.match(/^(.*?)\s+bei\s+(.*?)$/i);
            if (beiMatch) {
              if (!jobTitle) jobTitle = cleanText(beiMatch[1]);
              if (!companyName && !isBadCompany(beiMatch[2])) companyName = cleanText(beiMatch[2]);
            } else if (!jobTitle) {
              jobTitle = cleanT;
            }
          }
          if (!companyName) {
            const fEl = card.querySelector('[id$="-firma"], .firma-lane, [class*="firma"]');
            if (fEl && !isBadCompany(cleanText(fEl.innerText))) companyName = cleanText(fEl.innerText);
          }
          if (!companyAddress) {
            const aEl = card.querySelector('[id$="-ort"], .ort-lane, [class*="ort"]');
            if (aEl) companyAddress = cleanText(aEl.innerText);
          }
          if (!salary) {
            const sEl = card.querySelector('[id$="-gehalt"], .gehalt-lane');
            if (sEl) salary = cleanText(sEl.innerText);
          }
        }
      }

      // C. Active selected card in list
      if (!jobTitle || !companyName) {
        const activeCard = document.querySelector('jb-job-listen-eintrag.active, li[id*="jobsuche"].active, [class*="eintrag"][class*="active"]');
        if (activeCard) {
          if (!jobTitle) {
            const tEl = activeCard.querySelector('h2, [id$="-titel"], .titel-lane');
            if (tEl && !isBadTitle(cleanText(tEl.innerText))) jobTitle = cleanText(tEl.innerText).replace(/^\d+[\:\.\s]+/, "");
          }
          if (!companyName) {
            const fEl = activeCard.querySelector('[id$="-firma"], .firma-lane, [class*="firma"]');
            if (fEl && !isBadCompany(cleanText(fEl.innerText))) companyName = cleanText(fEl.innerText);
          }
        }
      }

      // D. Check Angular ng-state if present
      if (!jobTitle || !companyName) {
        try {
          const ngScript = document.getElementById("ng-state");
          if (ngScript && ngScript.textContent) {
            const ngState = JSON.parse(ngScript.textContent);
            const jd = ngState.jobdetail || (ngState.jobdetails && ngState.jobdetails.b) || null;
            if (jd && typeof jd === "object") {
              if (!jobTitle && (jd.stellenangebotsTitel || jd.titel) && !isBadTitle(jd.stellenangebotsTitel || jd.titel)) {
                jobTitle = cleanText(jd.stellenangebotsTitel || jd.titel);
              }
              if (!companyName && (jd.firma || jd.arbeitgeber) && !isBadCompany(jd.firma || jd.arbeitgeber)) {
                companyName = cleanText(jd.firma || jd.arbeitgeber);
              }
              if (!companyAddress && jd.stellenlokationen && jd.stellenlokationen.length > 0) {
                const ad = jd.stellenlokationen[0].adresse || {};
                companyAddress = cleanText(`${ad.plz || ""} ${ad.ort || ""}, ${ad.land || "Deutschland"}`);
              }
            }
          }
        } catch (e) {}
      }

      if (!description) {
        const modalOrDetail = Array.from(document.querySelectorAll('div[role="dialog"], mat-dialog-container, jb-job-detail, section[class*="detail"], div[class*="detail"], div[class*="modal"]')).find(el => {
          const txt = el.innerText || "";
          return (txt.includes("Deine Rolle") || txt.includes("Du lernst") || txt.includes("Das solltest Du mitbringen") || txt.includes("Das erwartet Dich") || txt.includes("Aufgaben") || txt.includes("Profil")) && txt.length > 150 && !txt.startsWith("StartseiteJobsuche");
        });
        if (modalOrDetail) {
          description = cleanDescription(modalOrDetail.innerText).slice(0, 7000);
        }
      }

      if (companyName && isBadCompany(companyName)) companyName = "";
      if (jobTitle && isBadTitle(jobTitle)) jobTitle = "";
    }

    // 3. Indeed
    if (host.includes("indeed.")) {
      if (!jobTitle) {
        const el = document.querySelector('[data-testid="jobsearch-JobInfoHeader-title"], [data-testid="simpler-jobTitle"], h1');
        if (el && !isBadTitle(el.innerText)) jobTitle = cleanText(el.innerText).replace(/\s*-\s*(job post|stellenanzeige)$/i, "");
      }
      if (!companyName) {
        const el = document.querySelector('a[href*="/cmp/"], [data-testid="inlineHeader-companyName"], [data-company-name="true"]');
        if (el && !isBadCompany(el.innerText)) companyName = cleanText(el.innerText);
      }
      if (!companyAddress) {
        const el = document.querySelector('[data-testid="inlineHeader-companyLocation"], [data-testid="job-location"]');
        if (el) companyAddress = cleanText(el.innerText);
      }
      if (!salary) {
        const el = document.querySelector('#salaryInfoAndJobType, [data-testid="attribute_snippet_testid"]');
        if (el) salary = cleanText(el.innerText);
      }
      if (!description) {
        const el = document.querySelector("#jobDescriptionText") || document.querySelector('[data-testid="jobsearch-ViewjobPaneWrapper"]');
        if (el) description = cleanText(el.innerText).slice(0, 7000);
      }
    }

    // 4. LinkedIn
    if (host.includes("linkedin.com")) {
      if (!jobTitle) {
        const el = document.querySelector(".job-details-jobs-unified-top-card__job-title, .top-card-layout__title, h1");
        if (el && !isBadTitle(el.innerText)) jobTitle = cleanText(el.innerText);
      }
      if (!companyName) {
        const el = document.querySelector(".job-details-jobs-unified-top-card__company-name, .topcard__org-name-link, a[href*='/company/']");
        if (el && !isBadCompany(el.innerText)) companyName = cleanText(el.innerText);
      }
      const primaryDescEl = document.querySelector(".job-details-jobs-unified-top-card__primary-description-container, .topcard__flavor-row");
      if (!companyAddress && primaryDescEl) {
        companyAddress = cleanText(primaryDescEl.innerText).split("·")[0].trim();
      }
      if (!datePosted && primaryDescEl) {
        const ageMatch = primaryDescEl.innerText.match(/(?:reposted|posted|vor)\s+(\d+\+?\s*(?:day|week|month|year|tag|woche|monat|jahr)\w*\s*(?:ago)?)/i);
        if (ageMatch) datePosted = cleanText(ageMatch[1]);
      }
      if (!description) {
        const el = document.querySelector("#job-details, .jobs-description__content");
        if (el) description = cleanText(el.innerText).slice(0, 7000);
      }
      const bodyTextLower = (document.body ? document.body.innerText : "").toLowerCase();
      if (bodyTextLower.includes("no longer accepting applications") || bodyTextLower.includes("keine bewerbungen mehr")) {
        if (!description || !description.toLowerCase().includes("no longer accepting applications")) {
          description = "No longer accepting applications. " + (description || "");
        }
      }
    }

    // 5. StepStone
    if (host.includes("stepstone.") && (!jobTitle || !companyName)) {
      if (!jobTitle) {
        const el = document.querySelector('[data-genesis-element="BASE_TITLE"], h1[class*="JobTitle"], h1');
        if (el && !isBadTitle(el.innerText)) jobTitle = cleanText(el.innerText);
      }
      if (!companyName) {
        const el = document.querySelector('[data-genesis-element="COMPANY_NAME"], a[data-genesis-element="COMPANY_NAME_LINK"], span[class*="Company"]');
        if (el && !isBadCompany(el.innerText)) companyName = cleanText(el.innerText);
      }
      if (!companyAddress) {
        const el = document.querySelector('[data-genesis-element="LOCATION"], span[class*="Location"]');
        if (el) companyAddress = cleanText(el.innerText);
      }
      if (!description) {
        const el = document.querySelector('[data-genesis-element="BODY_CONTAINER"], .listing-content');
        if (el) description = cleanText(el.innerText).slice(0, 7000);
      }
    }

    // 6. JSON-LD Structured Data (Used when NOT a search page or when fields are still missing)
    if (!isSearchOrSplit || (!jobTitle && !companyName)) {
      try {
        const ldScripts = document.querySelectorAll('script[type="application/ld+json"]');
        for (const scr of ldScripts) {
          let parsed = null;
          try {
            parsed = JSON.parse(scr.textContent || "");
          } catch (e) { continue; }

          const items = Array.isArray(parsed) ? parsed : (parsed && Array.isArray(parsed["@graph"]) ? parsed["@graph"] : [parsed]);
          for (const item of items) {
            if (!item || typeof item !== "object") continue;
            const t = Array.isArray(item["@type"]) ? item["@type"].join(",") : String(item["@type"] || "");
            if (t.includes("JobPosting")) {
              if (!jobTitle && item.title && !isBadTitle(item.title)) jobTitle = cleanText(item.title);
              if (!companyName && item.hiringOrganization) {
                const org = typeof item.hiringOrganization === "object" ? item.hiringOrganization.name : item.hiringOrganization;
                if (org && !isBadCompany(org)) companyName = cleanText(org);
              }
              if (!companyAddress && item.jobLocation) {
                const locObj = Array.isArray(item.jobLocation) ? item.jobLocation[0] : item.jobLocation;
                if (locObj && locObj.address) {
                  const a = locObj.address;
                  companyAddress = typeof a === "string" ? cleanText(a) : cleanText([a.streetAddress, a.postalCode, a.addressLocality, a.addressCountry].filter(Boolean).join(", "));
                }
              }
              if (!datePosted && item.datePosted) datePosted = cleanText(String(item.datePosted).slice(0, 10));
              if (!description && item.description) {
                const tmp = document.createElement("div");
                tmp.innerHTML = item.description;
                description = cleanText(tmp.innerText || tmp.textContent || "").slice(0, 7000);
              }
            }
          }
        }
      } catch (e) {}
    }

    // 7. Generic career sites / fallback heuristics
    if (!jobTitle) {
      const genderEl = Array.from(document.querySelectorAll("h1, h2, h3, [class*='title'], [class*='job']")).find(el => {
        const t = cleanText(el.innerText);
        return t && t.length >= 5 && t.length <= 150 && /\((?:m\/w\/d|m\/f\/d|w\/m\/d|d\/m\/w|gn)\)/i.test(t) && !isBadTitle(t);
      });
      if (genderEl) jobTitle = cleanText(genderEl.innerText);
    }

    if (!jobTitle) {
      const h1 = document.querySelector("h1");
      if (h1 && !isBadTitle(h1.innerText)) jobTitle = cleanText(h1.innerText);
    }

    if (!jobTitle && !isSearchOrSplit) {
      const cand = cleanText(document.title).split(/[-|–—•]/)[0].trim();
      if (!isBadTitle(cand)) jobTitle = cand;
    }

    if (!companyName && !isSearchOrSplit) {
      const parts = document.title.split(/\s*[-|–—•]\s*/);
      if (parts.length >= 2) {
        const cand = cleanText(parts[parts.length - 1]).replace(/^(jobs?|karriere|stellenangebote?|bewerbung)\s*(in|bei)?\s*/i, "").trim();
        if (cand && cand.length >= 2 && cand.length <= 60 && cand.toLowerCase() !== (jobTitle || "").toLowerCase() && !isBadCompany(cand)) {
          companyName = cand;
        }
      }
    }

    if (!companyName) {
      const logoImg = document.querySelector('header img[alt], nav img[alt], [class*="logo"] img[alt], [class*="brand"] img[alt]');
      if (logoImg && logoImg.getAttribute("alt")) {
        const alt = cleanText(logoImg.getAttribute("alt")).replace(/\s*logo\s*/i, "").trim();
        if (alt.length >= 2 && alt.length <= 60 && !isBadCompany(alt)) companyName = alt;
      }
    }

    if (!companyName) {
      try {
        const h = window.location.hostname.replace(/^www\./, "").split(".")[0];
        if (!isBoardName(h) && !isBadCompany(h)) {
          companyName = h.split("-").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
        }
      } catch (e) {}
    }

    if (!salary && document.body) {
      const salMatch = document.body.innerText.match(/(?:compensation|gehalt|vergütung|salary|lohn|verdienst)[:\s]*([€$£]?\s*[\d.,]+\s*(?:-|bis|to)?\s*[€$£]?\s*[\d.,]*\s*(?:€|\$|eur)?\s*(?:pro|\/|per)?\s*(?:stunde|monat|jahr|hour|month|year|h|m)?)/i);
      if (salMatch) salary = cleanText(salMatch[1]);
    }

    if (!datePosted && document.body) {
      const dMatch = document.body.innerText.match(/(?:published on|veröffentlicht am|datum|stand|posted on)[:\s]*([0-9./-]+)/i);
      if (dMatch) datePosted = cleanText(dMatch[1]);
    }

    if (!description) {
      const bodyTxt = cleanDescription(document.body ? document.body.innerText : "");
      if (!bodyTxt.startsWith("StartseiteJobsuche") && !bodyTxt.includes("Ihre Suche Meine Vormerkungen")) {
        description = bodyTxt.slice(0, 5000);
      }
    }

    return {
      url: finalUrl,
      title: jobTitle,
      company: companyName,
      address: companyAddress,
      salary,
      recruiterEmail,
      datePosted,
      refNumber: urlJobId,
      description
    };
  }

  window.__spExtractPageJobData = extractPageJobData;

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg && msg.type === "GET_PAGE_JOB_DATA") {
      try {
        sendResponse({ success: true, data: extractPageJobData() });
      } catch (e) {
        sendResponse({ success: false, error: e.message });
      }
      return true;
    }
  });
})();
