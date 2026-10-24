const app = document.querySelector("#app");
const navigation = document.querySelector("#navigation");
const notice = document.querySelector("#notice");
const positions = ["President", "Vice President", "Secretary", "Treasury"];
let viewState = {};

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[character]);
}

async function api(path, options = {}) {
    const response = await fetch(`${window.API_BASE_URL}${path}`, {
        ...options,
        credentials: "include",
        headers: {
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...options.headers
        }
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.message || `Request failed (${response.status})`);
    return data;
}

function showNotice(message, isError = false) {
    notice.textContent = message;
    notice.className = isError ? "error" : "success";
    notice.style.display = "block";
    window.setTimeout(() => { notice.style.display = "none"; }, 5000);
}

function formValues(form) {
    return Object.fromEntries(new FormData(form).entries());
}

function link(label, page, secondary = true) {
    return `<button class="${secondary ? "secondary" : ""}" data-page="${page}">${label}</button>`;
}

function setNavigation() {
    if (viewState.admin) {
        navigation.innerHTML = `${link("Dashboard", "admin")}${link("Results", "results")}${link("Blockchain", "blockchain")}<button data-action="logout" class="secondary">Log out</button>`;
    } else if (viewState.authenticated) {
        navigation.innerHTML = `${link("Vote", "vote")}${link("Results", "results")}${link("Blockchain", "blockchain")}<button data-action="logout" class="secondary">Log out</button>`;
    } else {
        navigation.innerHTML = `${link("Login", "home")}${link("Register", "register")}${link("Results", "results")}`;
    }
}

function renderLogin() {
    if (viewState.pending_otp) {
        app.innerHTML = `<section class="card narrow"><h1>Verify your email</h1><p class="muted">Enter the six-digit code sent to your registered email.</p><form data-form="otp"><label for="otp">One-time code</label><input id="otp" name="otp" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" required><button>Verify code</button></form><button class="secondary" data-action="resend">Resend code</button></section>`;
        return;
    }
    app.innerHTML = `<section class="card narrow"><h1>Sign in</h1><p class="muted">Students need an approved account. Administrators use their configured ID and phone.</p><form data-form="login"><label>Roll number / Admin ID</label><input name="rollno" required><label>Mobile / Admin phone</label><input name="mobile" required><label>Password</label><input name="password" type="password" required><button>Continue</button></form><p>New student? ${link("Register", "register", false)}</p></section>`;
}

function renderRegister() {
    app.innerHTML = `<section class="card narrow"><h1>Student registration</h1><form data-form="register"><label>Name</label><input name="name" minlength="2" required><label>Roll number</label><input name="rollno" minlength="3" required><label>Mobile</label><input name="mobile" required><label>Email</label><input name="email" type="email" required><label>Password (at least 8 characters)</label><input name="password" type="password" minlength="8" required><button>Register</button></form><p>${link("Back to login", "home")}</p></section>`;
}

async function renderVote() {
    const data = await api("/api/vote");
    viewState.user = data.user;
    const sections = positions.map(position => {
        const candidates = data.candidates[position] || [];
        return `<section class="candidate"><h3>${escapeHtml(position)}</h3>${candidates.map(candidate => `<label><input type="radio" name="${escapeHtml(position)}" value="${escapeHtml(candidate.name)}" required>${escapeHtml(candidate.name)} (${escapeHtml(candidate.symbol)})</label>`).join("") || '<p class="muted">No candidates have been added.</p>'}</section>`;
    }).join("");
    app.innerHTML = `<section class="card"><h1>Cast your vote</h1><p>Welcome, ${escapeHtml(data.user.name)}.</p>${!data.voting_open ? '<p class="error">Voting is currently closed.</p>' : ""}${data.has_voted ? '<p class="success">Your vote has already been recorded.</p>' : `<form data-form="vote">${sections}<button ${!data.voting_open ? "disabled" : ""}>Submit vote</button></form>`}</section>`;
}

function renderRows(title, values, field) {
    const rows = values || [];
    return `<section class="card"><h2>${escapeHtml(title)}</h2>${rows.length ? rows.map(row => `<div class="result-row"><span>${escapeHtml(row.candidate)}</span><strong>${escapeHtml(row.votes)} votes</strong></div>`).join("") : '<p class="muted">No votes recorded.</p>'}</section>`;
}

async function renderResults() {
    const data = await api("/api/results");
    if (!data.released && !viewState.admin) {
        app.innerHTML = '<section class="card"><h1>Election results</h1><p>Results have not been released yet.</p></section>';
        return;
    }
    app.innerHTML = `<h1>Election results</h1>${positions.map(position => renderRows(position, (data.results || {})[position])).join("")}`;
}

async function renderAdmin() {
    const data = await api("/api/admin");
    const pending = data.pending_users || [];
    const users = data.users || [];
    app.innerHTML = `<h1>Administrator dashboard</h1>
        <section class="card"><h2>Election controls</h2><div class="settings">
        <button data-action="setting" data-value="${data.voting_open ? "close_voting" : "open_voting"}">${data.voting_open ? "Close voting" : "Open voting"}</button>
        <button data-action="setting" data-value="${data.results_released ? "hide" : "release"}">${data.results_released ? "Hide results" : "Release results"}</button>
        <button class="danger" data-action="setting" data-value="clear_candidates">Clear all candidates</button></div></section>
        <section class="card"><h2>Add a candidate</h2><form data-form="candidate"><label>Name</label><input name="name" required><label>Symbol</label><input name="symbol" required><label>Position</label><select name="position">${positions.map(p => `<option>${escapeHtml(p)}</option>`).join("")}</select><button>Add candidate</button></form></section>
        <section class="card"><h2>Pending registrations (${pending.length})</h2>${pending.map(user => `<div class="user-row row"><span>${escapeHtml(user.name)} — ${escapeHtml(user.rollno)}</span><button data-action="user" data-value="approve" data-rollno="${escapeHtml(user.rollno)}">Approve</button><button class="danger" data-action="user" data-value="reject" data-rollno="${escapeHtml(user.rollno)}">Reject</button></div>`).join("") || '<p class="muted">No pending users.</p>'}</section>
        <section class="card"><h2>Registered students (${users.length})</h2>${users.map(user => `<div class="user-row">${escapeHtml(user.name)} — ${escapeHtml(user.rollno)} — ${user.approved ? "Approved" : "Pending"} — ${user.voted ? "Voted" : "Not voted"}</div>`).join("")}</section>`;
}

async function renderBlockchain() {
    const data = await api("/api/blockchain");
    app.innerHTML = `<section class="card"><h1>Blockchain</h1><p>Chain status: ${data.valid ? "Valid" : "Invalid"}</p><p>Blocks: ${data.blocks.length} · Pending transactions: ${data.pending.length}</p>${viewState.admin ? '<button data-action="mine">Mine pending block</button>' : ""}</section>${data.blocks.map(block => `<section class="card"><h2>Block #${escapeHtml(block.index)}</h2><p>Hash: <code>${escapeHtml(block.hash)}</code></p><p>${escapeHtml(block.transactions.length)} transactions</p></section>`).join("")}`;
}

async function navigate(page) {
    setNavigation();
    try {
        if (page === "register") renderRegister();
        else if (page === "vote") await renderVote();
        else if (page === "results") await renderResults();
        else if (page === "admin") await renderAdmin();
        else if (page === "blockchain") await renderBlockchain();
        else renderLogin();
    } catch (error) {
        app.innerHTML = `<section class="card"><h1>Unable to load this page</h1><p class="error">${escapeHtml(error.message)}</p><button data-page="home">Return to sign in</button></section>`;
    }
}

document.addEventListener("click", async event => {
    const pageButton = event.target.closest("[data-page]");
    if (pageButton) {
        event.preventDefault();
        navigate(pageButton.dataset.page);
        return;
    }
    const actionButton = event.target.closest("[data-action]");
    if (!actionButton) return;
    try {
        const action = actionButton.dataset.action;
        if (action === "logout") {
            await api("/api/logout", { method: "POST" });
            viewState = {};
            navigate("home");
        } else if (action === "resend") {
            const result = await api("/api/resend-otp", { method: "POST", body: "{}" });
            showNotice(result.message);
        } else if (action === "setting") {
            await api("/api/admin/settings", { method: "POST", body: JSON.stringify({ action: actionButton.dataset.value }) });
            showNotice("Election settings updated.");
            navigate("admin");
        } else if (action === "user") {
            await api(`/api/admin/users/${encodeURIComponent(actionButton.dataset.rollno)}/${actionButton.dataset.value}`, { method: "POST", body: "{}" });
            showNotice("Student record updated.");
            navigate("admin");
        } else if (action === "mine") {
            await api("/api/blockchain/mine", { method: "POST", body: "{}" });
            showNotice("Mining request completed.");
            navigate("blockchain");
        }
    } catch (error) {
        showNotice(error.message, true);
    }
});

document.addEventListener("submit", async event => {
    const form = event.target.closest("form[data-form]");
    if (!form) return;
    event.preventDefault();
    const type = form.dataset.form;
    const values = formValues(form);
    try {
        let result;
        if (type === "register") {
            result = await api("/api/register", { method: "POST", body: JSON.stringify(values) });
            viewState = {};
            navigate("home");
        } else if (type === "login") {
            result = await api("/api/login", { method: "POST", body: JSON.stringify(values) });
            if (result.admin) {
                viewState = { authenticated: true, admin: true };
                navigate("admin");
            } else {
                viewState.pending_otp = true;
                renderLogin();
            }
        } else if (type === "otp") {
            result = await api("/api/verify-otp", { method: "POST", body: JSON.stringify(values) });
            viewState = { authenticated: true };
            navigate("vote");
        } else if (type === "vote") {
            const choices = Object.fromEntries(positions.map(position => [position, values[position]]));
            result = await api("/api/vote", { method: "POST", body: JSON.stringify(choices) });
            navigate("vote");
        } else if (type === "candidate") {
            result = await api("/api/admin/candidates", { method: "POST", body: JSON.stringify(values) });
            navigate("admin");
        }
        if (result?.message) showNotice(result.message);
    } catch (error) {
        showNotice(error.message, true);
    }
});

api("/api/session").then(state => {
    viewState = state;
    navigate(state.admin ? "admin" : state.authenticated ? "vote" : "home");
}).catch(error => {
    app.innerHTML = `<section class="card"><h1>Backend is unavailable</h1><p class="error">${escapeHtml(error.message)}</p><p>Check the API URL in <code>config.js</code> and the backend CORS environment variable.</p></section>`;
});
