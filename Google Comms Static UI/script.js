console.log("Connected!");

/* ============================================================
   SHARED DATA
   ============================================================ */

const DOMAINS = [
    { name: "Agriculture",           color: "#34A853" },
    { name: "Technology",            color: "#3C84FC" },
    { name: "Retail",                color: "#F73B25" },
    { name: "Hospitality",           color: "#FBBC2E" },
    { name: "Healthcare",            color: "#F73B25" },
    { name: "Finance",               color: "#34A853" },
    { name: "Manufacturing",         color: "#3C84FC" },
    { name: "Education",             color: "#FBBC2E" },
    { name: "Energy",                color: "#34A853" },
    { name: "Media & Entertainment", color: "#F73B25" },
    { name: "Transportation",        color: "#3C84FC" },
    { name: "Government",            color: "#5f6368" },
    { name: "Telecommunications",    color: "#FBBC2E" },
    { name: "Real Estate",           color: "#34A853" },
];

// Where the local Flask server is listening (subscribe_server.py)
const API_BASE = "http://localhost:8000";


/* ============================================================
   COLOR HELPERS
   ============================================================ */

function hexToRgb(hex) {
    hex = hex.replace("#", "");
    if (hex.length === 3) hex = hex.split("").map(c => c + c).join("");
    const n = parseInt(hex, 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

// mix = how far toward white (0 = full color, 1 = white). Higher = more pastel.
function pastel(hex, mix) {
    const { r, g, b } = hexToRgb(hex);
    const p = c => Math.round(c + (255 - c) * mix);
    return `rgb(${p(r)}, ${p(g)}, ${p(b)})`;
}


/* ============================================================
   CLIENT DROPDOWN (home view)
   ============================================================ */

const dropdown      = document.getElementById("client-dropdown");
const input         = document.getElementById("client-input");
const menu          = document.getElementById("dropdown-menu");
const sidebar       = document.querySelector(".sidebar");
const selectedLabel = document.getElementById("selected-client");
let activeIndex = -1;

function renderMenu(filter = "") {
    const q = filter.trim().toLowerCase();
    const matches = DOMAINS.filter(d => d.name.toLowerCase().includes(q));
    menu.innerHTML = "";
    activeIndex = -1;

    if (matches.length === 0) {
        const empty = document.createElement("li");
        empty.className = "dropdown-empty";
        empty.textContent = "No matching domains";
        menu.appendChild(empty);
        return;
    }

    matches.forEach(({ name, color }) => {
        const li = document.createElement("li");
        li.className = "dropdown-item";
        li.setAttribute("role", "option");
        li.innerHTML = `<span class="dot" style="background:${color}"></span>${name}`;
        li.addEventListener("mousedown", (e) => {   // mousedown fires before blur
            e.preventDefault();
            selectItem(name);
        });
        menu.appendChild(li);
    });
}

function openMenu()  { dropdown.classList.add("open"); renderMenu(""); }
function closeMenu() { dropdown.classList.remove("open"); activeIndex = -1; }

function selectItem(name) {
    input.value = name;
    closeMenu();

    const domain = DOMAINS.find(d => d.name === name);
    const color = domain ? domain.color : "#3C84FC";

    sidebar.style.backgroundImage =
        `linear-gradient(160deg, ${pastel(color, 0.73)} 0%, ${pastel(color, 0.88)} 100%)`;

    selectedLabel.innerHTML = `Selected client<strong>${name}</strong>`;
    selectedLabel.classList.add("show");

    // re-trigger the fade animation each time
    sidebar.classList.remove("theme-fade");
    void sidebar.offsetWidth;            // forces reflow so the animation restarts
    sidebar.classList.add("theme-fade");
}

function setActive(items) {
    items.forEach(el => el.classList.remove("active"));
    if (items[activeIndex]) {
        items[activeIndex].classList.add("active");
        items[activeIndex].scrollIntoView({ block: "nearest" });
    }
}

input.addEventListener("focus", () => { input.select(); openMenu(); });
document.getElementById("client-select").addEventListener("click", () => input.focus());

input.addEventListener("input", () => {
    dropdown.classList.add("open");
    renderMenu(input.value);
});

input.addEventListener("keydown", (e) => {
    const items = [...menu.querySelectorAll(".dropdown-item")];
    if (e.key === "ArrowDown") {
        e.preventDefault();
        if (!dropdown.classList.contains("open")) openMenu();
        activeIndex = Math.min(activeIndex + 1, items.length - 1);
        setActive(items);
    } else if (e.key === "ArrowUp") {
        e.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        setActive(items);
    } else if (e.key === "Enter" && items[activeIndex]) {
        e.preventDefault();
        selectItem(items[activeIndex].textContent);
    } else if (e.key === "Escape") {
        closeMenu();
        input.blur();
    }
});

// Close when clicking outside
document.addEventListener("click", (e) => {
    if (!dropdown.contains(e.target)) closeMenu();
});


/* ============================================================
   SIDEBAR RESIZE
   ============================================================ */

(function initSidebarResize() {
    const resizer = document.getElementById("sidebar-resizer");
    const root = document.documentElement;
    const STORAGE_KEY = "cc-sidebar-width";
    const MIN = 260;
    const MAX = 560;

    const saved = parseInt(localStorage.getItem(STORAGE_KEY), 10);
    if (saved && saved >= MIN && saved <= MAX) {
        root.style.setProperty("--sidebar-width", `${saved}px`);
    }

    function currentWidth() {
        return parseInt(getComputedStyle(root).getPropertyValue("--sidebar-width"), 10) || 383;
    }

    function setWidth(px) {
        const clamped = Math.min(MAX, Math.max(MIN, px));
        root.style.setProperty("--sidebar-width", `${clamped}px`);
        return clamped;
    }

    let dragging = false;

    resizer.addEventListener("mousedown", (e) => {
        e.preventDefault();
        dragging = true;
        resizer.classList.add("dragging");
        document.body.classList.add("sidebar-resizing");
    });

    document.addEventListener("mousemove", (e) => {
        if (!dragging) return;
        setWidth(e.clientX);
    });

    document.addEventListener("mouseup", () => {
        if (!dragging) return;
        dragging = false;
        resizer.classList.remove("dragging");
        document.body.classList.remove("sidebar-resizing");
        localStorage.setItem(STORAGE_KEY, currentWidth());
    });

    // Keyboard support for the aria "separator" role — arrow keys nudge the width.
    resizer.addEventListener("keydown", (e) => {
        if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
        e.preventDefault();
        const delta = e.key === "ArrowRight" ? 20 : -20;
        const next = setWidth(currentWidth() + delta);
        localStorage.setItem(STORAGE_KEY, next);
    });
})();


/* ============================================================
   VIEW SWITCHING (sidebar nav)
   ============================================================ */

const navButtons = document.querySelectorAll(".dashboard-button[data-view]");
const views = document.querySelectorAll(".view");

function showView(id) {
    views.forEach(v => v.classList.toggle("active", v.id === id));
    navButtons.forEach(b => b.classList.toggle("active", b.dataset.view === id));
}

navButtons.forEach(b => b.addEventListener("click", () => showView(b.dataset.view)));


/* ============================================================
   NEW CHAT BUTTON
   ============================================================ */
const newChatButton = document.querySelector(".new-chat-btn");
const askInput = document.getElementById("ask-input");

newChatButton.addEventListener("click", () => {
    // Clear input
    askInput.value = "";
    askInput.disabled = false;

    // Go back to Ask Comms, wiped back to its empty state
    showView("view-askcomms");
    chatHistory.innerHTML = "";
    askCommsView.classList.remove("has-messages");

    // Reset the sidebar color to the original
    sidebar.style.backgroundImage = "";

    // Remove the selected client
    input.value = "";
    selectedLabel.innerHTML = "";
    selectedLabel.classList.remove("show");

    // Focus the input
    askInput.focus();
});


/* ============================================================
   ASK COMMS — chat send / receive
   ============================================================ */

const chatHistory  = document.getElementById("chat-history");
const askCommsView = document.getElementById("view-askcomms");
let askBusy = false;

function appendMessage(role, text) {
    const div = document.createElement("div");
    div.className = `message ${role === "user" ? "user-message" : "agent-message"}`;

    if (role === "user") {
        // The TAM's own typed text — plain, no markdown to render, and
        // textContent auto-escapes it so it can never be read as HTML.
        div.textContent = text;
    } else {
        // The agent's answer is real markdown (bold, bullet lists, links) —
        // parse it to HTML, then sanitize before inserting, in case a
        // response ever contains something that looks like a raw tag.
        div.innerHTML = DOMPurify.sanitize(marked.parse(text));
    }

    chatHistory.appendChild(div);
    chatHistory.scrollTo({ top: chatHistory.scrollHeight, behavior: "smooth" });
    return div;
}

function showTyping() {
    const div = document.createElement("div");
    div.className = "message agent-message typing-indicator";
    div.id = "typing-indicator";
    div.innerHTML = "<span></span><span></span><span></span>";
    chatHistory.appendChild(div);
    chatHistory.scrollTo({ top: chatHistory.scrollHeight, behavior: "smooth" });
}

function hideTyping() {
    const el = document.getElementById("typing-indicator");
    if (el) el.remove();
}

async function sendAsk(question) {
    question = (question || "").trim();
    if (!question || askBusy) return;

    askBusy = true;
    askCommsView.classList.add("has-messages");

    appendMessage("user", question);
    askInput.value = "";
    askInput.disabled = true;
    showTyping();

    try {
        const res = await fetch(`${API_BASE}/ask`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question })
        });
        const data = await res.json();
        hideTyping();
        appendMessage("agent", data.ok ? data.answer : (data.error || "Something went wrong."));
    } catch (err) {
        console.error(err);
        hideTyping();
        appendMessage("agent", "Couldn't reach the server — is subscribe_server.py running?");
    } finally {
        askInput.disabled = false;
        askInput.focus();
        askBusy = false;
    }
}

askInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendAsk(askInput.value);
    }
});

// Suggestion pills send immediately instead of just filling the input —
// one click to a real answer feels a lot smoother than click-then-Enter.
document.querySelectorAll(".suggest-pill").forEach(pill => {
    pill.addEventListener("click", () => sendAsk(pill.textContent));
});


/* ============================================================
   SUBSCRIBE PAGE
   ============================================================ */

const subIndustry = document.getElementById("sub-industry");
const subMsg      = document.getElementById("sub-msg");
const subSubmit   = document.getElementById("sub-submit");

// Build the industry list from the same DOMAINS array — one source of truth.
DOMAINS.forEach(d => {
    const opt = document.createElement("option");
    opt.value = d.name;
    opt.textContent = d.name;
    subIndustry.appendChild(opt);
});

subSubmit.addEventListener("click", async () => {
    const name     = document.getElementById("sub-name").value.trim();
    const email    = document.getElementById("sub-email").value.trim();
    const industry = subIndustry.value;

    // --- client-side validation (the server re-checks these too) ---
    if (!name || !email || !industry) {
        subMsg.textContent = "Please fill out all three fields.";
        subMsg.classList.add("error");
        return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        subMsg.textContent = "That email doesn't look right.";
        subMsg.classList.add("error");
        return;
    }

    // --- send to the local server ---
    subMsg.classList.remove("error");
    subMsg.textContent = "Subscribing...";
    subSubmit.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/subscribe`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ first_name: name, email, industry })
        });
        const data = await res.json();

        if (data.ok) {
            subMsg.classList.remove("error");
            subMsg.textContent = `Thanks ${name} — you're subscribed to ${industry} updates.`;
            document.getElementById("sub-name").value = "";
            document.getElementById("sub-email").value = "";
            subIndustry.value = "";
        } else {
            subMsg.textContent = data.error || "Something went wrong.";
            subMsg.classList.add("error");
        }
    } catch (err) {
        console.error(err);
        subMsg.textContent = "Couldn't reach the server — is subscribe_server.py running?";
        subMsg.classList.add("error");
    } finally {
        subSubmit.disabled = false;
    }
});
