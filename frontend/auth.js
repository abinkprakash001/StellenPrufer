// StellenPrüfer Authentication & Page Transition Scripts

function getApiBase() {
    return (window.location.protocol === "file:" || window.location.port !== "5000")
        ? "http://127.0.0.1:5000"
        : "";
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

document.addEventListener("DOMContentLoaded", () => {
    ensureScreenLoader();

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
});

async function login(event) {
    event.preventDefault();
    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value.trim();
    const msg = document.getElementById("loginMessage");

    if (!email || !password) {
        if (msg) {
            msg.textContent = "Please fill in all fields.";
            msg.style.color = "#dc2626";
        }
        return;
    }

    showScreenLoader();

    try {
        const startTime = Date.now();
        const res = await fetch(`${getApiBase()}/api/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();

        const elapsed = Date.now() - startTime;
        if (elapsed < 500) {
            await new Promise(r => setTimeout(r, 500 - elapsed));
        }

        if (!res.ok || !data.success) {
            hideScreenLoader();
            if (msg) {
                msg.textContent = data.error || "Invalid email or password.";
                msg.style.color = "#dc2626";
            }
            return;
        }

        localStorage.setItem("stellenpruefer_user", JSON.stringify(data.user));
        localStorage.setItem("jobguard_user", JSON.stringify(data.user));

        if (data.user.role === "admin") {
            window.location.href = "admin.html";
        } else {
            window.location.href = "index.html";
        }

    } catch (err) {
        hideScreenLoader();
        if (msg) {
            msg.textContent = "Server error. Make sure app.py is running.";
            msg.style.color = "#dc2626";
        }
    }
}

async function register(event) {
    event.preventDefault();
    const name = document.getElementById("registerName").value.trim();
    const email = document.getElementById("registerEmail").value.trim();
    const password = document.getElementById("registerPassword").value.trim();
    const gdprCheckbox = document.getElementById("gdprConsent");
    const gdprConsent = gdprCheckbox ? gdprCheckbox.checked : false;
    const msg = document.getElementById("registerMessage");

    if (!name || !email || !password) {
        if (msg) {
            msg.textContent = "Please fill in all fields.";
            msg.style.color = "#dc2626";
        }
        return;
    }

    if (!gdprConsent) {
        if (msg) {
            msg.textContent = "Please accept the data protection consent (DSGVO / BDSG).";
            msg.style.color = "#dc2626";
        }
        return;
    }

    showScreenLoader();

    try {
        const startTime = Date.now();
        const res = await fetch(`${getApiBase()}/api/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, password, gdprConsent })
        });
        const data = await res.json();

        const elapsed = Date.now() - startTime;
        if (elapsed < 500) {
            await new Promise(r => setTimeout(r, 500 - elapsed));
        }

        if (!res.ok || !data.success) {
            hideScreenLoader();
            if (msg) {
                msg.textContent = data.error || "Registration failed.";
                msg.style.color = "#dc2626";
            }
            return;
        }

        localStorage.setItem("stellenpruefer_user", JSON.stringify(data.user));
        localStorage.setItem("jobguard_user", JSON.stringify(data.user));
        window.location.href = "index.html";

    } catch (err) {
        hideScreenLoader();
        if (msg) {
            msg.textContent = "Server error. Make sure app.py is running.";
            msg.style.color = "#dc2626";
        }
    }
}
