// Small helpers shared by the page templates (conversation, roadmap, resume).
// Loaded via a plain <script> tag, so these are globals.

// el("div", { className: "card", text: "hi", role: "alert" }, child1, child2)
// Builds DOM nodes with textContent (never innerHTML), so server/LLM text can't inject markup.
function el(tag, props = {}, ...children) {
    const { className, text, ...attrs } = props;
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
    node.append(...children);
    return node;
}

// The session's CSRF token, rendered into layout.html as <meta name="csrf-token">.
// The server rejects every POST/PUT/PATCH/DELETE without it (400 {"error":"csrf"}).
// ANY new state-changing fetch must go through request()/postJson()/postForm()
// below - never call fetch() directly for those - so the header is always sent.
function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
}

const CSRF_SAFE_METHODS = ["GET", "HEAD", "OPTIONS"];

// Always resolves to { ok, status, data } - never throws.
// status 0 = network failure; data is null when the response body wasn't JSON
// (e.g. Flask's HTML 413 page for an oversized upload).
async function request(url, options) {
    try {
        const method = (options && options.method ? options.method : "GET").toUpperCase();
        if (!CSRF_SAFE_METHODS.includes(method)) {
            // Headers object, so a caller's own headers (Content-Type) are kept and
            // multipart bodies still get the browser's boundary.
            const headers = new Headers(options.headers || {});
            headers.set("X-CSRF-Token", csrfToken());
            options = { ...options, headers };
        }
        const response = await fetch(url, options);
        let data = null;
        try {
            data = await response.json();
        } catch (_) {
            // Non-JSON body - fall through with data = null.
        }
        return { ok: response.ok, status: response.status, data };
    } catch (_) {
        return { ok: false, status: 0, data: null };
    }
}

// True if a failed request is the backend asking for a career path (the user has no
// quiz result, so there is no top match to default to). data.options is the list of
// valid paths; data.message is a student-safe explanation. "invalid_career_path" means
// a path was sent but wasn't in the list, so the picker is simply shown again.
function isCareerPathSignal(result) {
    return result.status === 400
        && result.data
        && (result.data.error === "career_path_required" || result.data.error === "invalid_career_path")
        && Array.isArray(result.data.options);
}

// ---------- Layout + small components shared by every page ----------
//
// Every page is a "sheet" of rows: a quiet margin on the left (titles, dates, notes)
// and the work on the right. Anything rendered by JS is built from row() so it lines
// up with the server-rendered rows and the margin rule.

// row(marginNodes, mainNodes, className, tag). Either node argument may be a single node or an array.
function row(margin, main, className, tag) {
    return el(tag || "div", { className: `row ${className || ""}`.trim() },
        el("div", { className: "margin" }, ...[].concat(margin || [])),
        el("div", { className: "main" }, ...[].concat(main || []))
    );
}

// A row title (rendered in the margin). level = which heading element, so the page's outline stays correct.
function rowTitle(text, level, extraProps) {
    return el(`h${level || 2}`, { className: "row-title", text, ...extraProps });
}

function svgEl(tag, attrs, ...children) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [name, value] of Object.entries(attrs || {})) node.setAttribute(name, value);
    node.append(...children);
    return node;
}

// Small inline icons that inherit the text colour. Decorative: the words next to them carry the meaning.
function icon(name) {
    const svg = svgEl("svg", { width: "14", height: "14", viewBox: "0 0 14 14", "aria-hidden": "true", focusable: "false" });
    if (name === "tick") {
        svg.append(svgEl("path", { d: "M2 7.5 5.5 11 12 3.5", fill: "none", stroke: "currentColor", "stroke-width": "2.5" }));
    } else if (name === "play") {
        svg.setAttribute("width", "18");
        svg.setAttribute("height", "18");
        svg.setAttribute("viewBox", "0 0 18 18");
        svg.append(
            svgEl("circle", { cx: "9", cy: "9", r: "8", fill: "none", stroke: "currentColor", "stroke-width": "2" }),
            svgEl("path", { d: "M7.2 5.6 12.4 9l-5.2 3.4Z", fill: "currentColor" })
        );
    }
    return svg;
}

// role="status" text with a line that "draws" while something takes a while.
function working(message) {
    return el("div", { className: "msg", role: "status" },
        el("p", { text: message }),
        el("div", { className: "working", "aria-hidden": "true" })
    );
}

// ---------- Design-system builders (the markup is styled in style.css, "3. Components") ----------
// Everything here is built with el() / textContent, never innerHTML.

// A shimmering placeholder in place of "Loading..." text. role="status" so a screen reader hears one short message.
function skeleton(label, lines) {
    const box = el("div", { className: "skel", role: "status", "aria-label": label || "Loading" });
    box.append(el("span", { className: "skel-line w-40" }));
    for (let i = 0; i < (lines || 2); i++) box.append(el("span", { className: i % 2 ? "skel-line w-70" : "skel-line" }));
    box.append(el("span", { className: "skel-line skel-block" }));
    return box;
}

// Inline alert: one line plus (optionally) one action. kind: "error" | "ok" | "info".
function alertEl(message, kind, ...actions) {
    const box = el("div", { className: `alert${kind === "error" ? " alert-error" : kind === "ok" ? " alert-ok" : ""}`, role: kind === "error" ? "alert" : "status" },
        el("p", { text: message }));
    if (actions.length) box.append(el("div", { className: "actions" }, ...actions));
    return box;
}

// An empty state: a line icon, one line, one action (a node, usually a .btn).
function emptyState(title, action) {
    const art = svgEl("svg", { class: "empty-icon", viewBox: "0 0 48 48", "aria-hidden": "true", focusable: "false" },
        svgEl("path", { d: "M6 40h12v-9h12v-9h12V8", fill: "none", stroke: "currentColor", "stroke-width": "4", "stroke-linejoin": "round" }));
    return el("div", { className: "empty" }, art, el("p", { className: "empty-title", text: title }), action || "");
}

// A "How this works"-style disclosure: one summary line, then the notes.
function disclosure(summary, ...notes) {
    return el("details", { className: "disclosure" }, el("summary", { text: summary }), ...notes);
}

// Thin progress bar: pct 0-100. label is read by screen readers (the bar itself has no text).
function pbar(pct, label, large) {
    const fill = el("span", {});
    fill.style.width = `${Math.max(0, Math.min(100, pct))}%`;
    return el("div", { className: `pbar${large ? " pbar-lg" : ""}`, role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100",
        "aria-valuenow": String(Math.round(pct)), "aria-label": label }, fill);
}

// Progress ring with text in the middle. Returns the node; node.setRing(pct, centerText, subText) updates it in place.
function ring(pct, centerText, subText, size) {
    const px = size || 96;
    const stroke = Math.max(6, Math.round(px / 10));
    const r = (px - stroke) / 2;
    const c = 2 * Math.PI * r;
    const fill = svgEl("circle", { class: "ring-fill", cx: String(px / 2), cy: String(px / 2), r: String(r), "stroke-width": String(stroke), "stroke-dasharray": String(c) });
    const svg = svgEl("svg", { width: String(px), height: String(px), viewBox: `0 0 ${px} ${px}`, "aria-hidden": "true", focusable: "false" },
        svgEl("circle", { class: "ring-track", cx: String(px / 2), cy: String(px / 2), r: String(r), "stroke-width": String(stroke) }), fill);
    const main = el("span", { className: "num", text: "" });
    const small = el("small", { text: "" });
    const label = el("span", { className: "ring-label" }, el("span", {}, main, small));
    const node = el("div", { className: "ring", role: "img" }, svg, label);
    node.style.width = node.style.height = `${px}px`;
    label.style.fontSize = `${Math.round(px / 4.2)}px`;
    node.setRing = (value, center, sub) => {
        const p = Math.max(0, Math.min(100, value));
        fill.style.strokeDashoffset = String(c * (1 - p / 100));
        main.textContent = center;
        small.textContent = sub || "";
        node.setAttribute("aria-label", `${center}${sub ? " " + sub : ""}`);
    };
    node.setRing(pct, centerText, subText);
    return node;
}

// One section at a time: tabs on a wide screen, accordion headers on a narrow one (switches live when the
// window crosses 48rem). items: [{ title, node }]. Only one section is open; on a narrow screen it can also be closed.
let _sectionTabsCount = 0;
function sectionTabs(items, label) {
    const uid = ++_sectionTabsCount;
    const wide = window.matchMedia("(min-width: 48rem)");
    let active = 0;

    const tablist = el("div", { className: "tabs", role: "tablist", "aria-label": label || "Sections" });
    const root = el("div", { className: "sections" }, tablist);
    const parts = items.map((item, i) => {
        const tab = el("button", { type: "button", role: "tab", id: `sec-tab-${uid}-${i}`, "aria-controls": `sec-panel-${uid}-${i}`, text: item.title });
        const head = el("button", { type: "button", className: "acc-head", id: `sec-head-${uid}-${i}`, "aria-controls": `sec-panel-${uid}-${i}` },
            el("span", { text: item.title }), el("span", { className: "acc-chev", "aria-hidden": "true" }));
        const panel = el("div", { className: "sec-panel", id: `sec-panel-${uid}-${i}` }, item.node);
        tab.addEventListener("click", () => { active = i; render(); });
        head.addEventListener("click", () => { active = active === i ? -1 : i; render(); });
        tab.addEventListener("keydown", (event) => {
            const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
            if (!step) return;
            event.preventDefault();
            active = (i + step + items.length) % items.length;
            render();
            parts[active].tab.focus();
        });
        tablist.append(tab);
        root.append(head, panel);
        return { tab, head, panel };
    });

    function render() {
        const isWide = wide.matches;
        if (isWide && active < 0) active = 0;
        parts.forEach((part, i) => {
            const on = i === active;
            part.panel.hidden = !on;
            part.tab.setAttribute("aria-selected", on ? "true" : "false");
            part.tab.tabIndex = on ? 0 : -1;
            part.head.setAttribute("aria-expanded", on ? "true" : "false");
            part.panel.setAttribute("role", isWide ? "tabpanel" : "region");
            part.panel.setAttribute("aria-labelledby", isWide ? part.tab.id : part.head.id);
        });
    }
    wide.addEventListener("change", render);
    render();
    return root;
}

// A required single-choice question: large option cards, then Previous / Next.
// Choosing an answer does NOT move on; Next stays disabled until one is chosen, so no
// question can be skipped. Keys 1-4 (up to 9) pick the matching option; Enter moves on once one is picked.
//   name: unique per question, so its radios group together.
//   labelledBy: id of the heading that holds the question text.
//   options: { A: "text", ... }.  selected: the key chosen earlier (so Previous/Next
//   remembers it), or null.  canGoBack: false on the first question (Previous stays
//   visible but disabled, so the buttons don't jump around).
//   onNext(key) is only ever called with a real key. onBack(key) gets the current choice (or null).
// The cards are real radio buttons (visually hidden but focusable) inside labels, so arrow keys,
// screen readers and clicking anywhere on a card all work.
function questionForm({ name, labelledBy, options, selected, canGoBack, nextText, onBack, onNext }) {
    let value = selected != null && Object.prototype.hasOwnProperty.call(options, selected) ? selected : null;

    const group = el("div", { className: "opt-list", role: "radiogroup", "aria-labelledby": labelledBy, "aria-required": "true" });
    const back = el("button", { className: "btn btn-ghost", type: "button", text: "Previous" });
    const next = el("button", { className: "btn", type: "submit", text: nextText || "Next" });
    const hint = el("p", { className: "kbd-hint", text: `Press 1-${Math.min(Object.keys(options).length, 9)} to choose, Enter to continue.` });

    const sync = () => { next.disabled = value === null; };

    Object.entries(options).forEach(([key, text], i) => {
        const input = el("input", { type: "radio", name, value: key, className: "visually-hidden" });
        input.checked = key === value;
        input.addEventListener("change", () => { value = key; sync(); });
        group.append(el("label", { className: "opt-card" },
            input,
            el("span", { className: "opt-key", "aria-hidden": "true", text: String(i + 1) }),
            el("span", { className: "opt-text", text })
        ));
    });

    back.disabled = !canGoBack;
    sync();

    // Once a step is under way, freeze the form so a double-click can't send it twice.
    const lock = () => {
        next.disabled = true;
        back.disabled = true;
        group.querySelectorAll("input").forEach((input) => { input.disabled = true; });
    };

    const form = el("form", { className: "qform stack-sm", novalidate: "" },
        group,
        hint,
        el("div", { className: "qnav" }, back, next)
    );
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        if (value === null) return;
        lock();
        onNext(value);
    });
    back.addEventListener("click", () => {
        lock();
        onBack(value);
    });

    // Keyboard: 1-9 picks an option, Enter (with nothing focused) continues. Removed once this form leaves the page.
    const onKey = (event) => {
        if (!form.isConnected) {
            document.removeEventListener("keydown", onKey);
            return;
        }
        if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
        const target = event.target;
        if (target && target.matches && target.matches("textarea, select, input:not([type=radio])")) return;
        const onControl = target && target.matches && target.matches("button, a, input");
        if (event.key === "Enter" && value !== null && !onControl) {
            event.preventDefault();
            form.requestSubmit();
            return;
        }
        const n = Number(event.key);
        if (!Number.isInteger(n) || n < 1 || n > 9) return;
        const input = group.querySelectorAll("input")[n - 1];
        if (!input || input.disabled) return;
        event.preventDefault();
        input.checked = true;
        input.dispatchEvent(new Event("change"));
        input.focus();
    };
    document.addEventListener("keydown", onKey);
    return form;
}

// "Question 3" on the left, a note on the right, a bar underneath. pct is 0-100.
function questionProgress(left, right, pct, label) {
    return el("div", { className: "qprogress" },
        el("div", { className: "cluster between" },
            el("span", { className: "num", text: left }),
            right ? el("span", { className: "muted", text: right }) : ""
        ),
        pbar(pct, label || left)
    );
}

// Move keyboard/screen-reader focus to a newly rendered heading, so a changed question is announced.
function focusHeading(node) {
    if (!node) return;
    node.setAttribute("tabindex", "-1");
    node.focus({ preventScroll: true });
}

// The frame every career-path picker shares: margin notes, heading, message,
// and an actions row around whatever "choice UI" (a select, or matches +
// select) the caller builds. Keeps the two render paths below visually
// identical apart from that one piece.
function careerPathPickerFrame({ lead, message, choiceUi, submit }) {
    const picker = row(
        [
            lead ? el("p", { className: "note", text: lead }) : "",
            el("p", { className: "note", text: "This choice applies to this one request. It doesn't change your quiz results." }),
        ],
        el("div", { className: "split split-2 ask-grid" },
            el("div", {},
                el("h2", { id: "career-path-heading", className: "phase-title", text: "Which career path are you aiming for?" }),
                el("p", { className: "ask-text", text: message })
            ),
            el("div", {}, choiceUi, el("div", { className: "actions" }, submit))
        ),
        "ask"
    );
    picker.setAttribute("role", "group");
    picker.setAttribute("aria-labelledby", "career-path-heading");
    return picker;
}

// The legacy picker: a single <select> of exactly the given `options`, with
// `preselected` picked by default if it's one of them. Returns the node
// immediately (no fetch) - BYTE-IDENTICAL to careerPathPicker's behavior
// before the shared-picker task, since dsa.html still calls it this way
// (passing `options` from its own 400 career_path_required/invalid_career_path
// signal) and isn't part of this task.
function _legacyCareerPathPicker({ options, message, lead, submitText, preselected, onSubmit }) {
    const select = el("select", { id: "career-path-select", className: "select" },
        el("option", { value: "", text: "Choose a career path", disabled: "", hidden: "" }),
        ...options.map((path) => el("option", { value: path, text: path }))
    );
    select.value = options.includes(preselected) ? preselected : "";

    const submit = el("button", { className: "btn", type: "button", text: submitText });
    submit.disabled = select.value === "";
    select.addEventListener("change", () => { submit.disabled = select.value === ""; });
    submit.addEventListener("click", () => {
        if (select.value !== "") onSubmit(select.value);
    });

    return careerPathPickerFrame({
        lead,
        message: message || "You haven't taken the career quiz, so tell us where you're headed and we'll measure against that.",
        choiceUi: el("div", { className: "field" }, el("label", { for: "career-path-select", text: "Career path" }), select),
        submit,
    });
}

// One quiz-match card: career path name + confidence %, the same large option card the quiz uses
// (the % takes the place of the 1-4 key).
function _pathMatchCard(match, name, checked, onPick) {
    const safeId = `path-match-${match.career_path.replace(/[^A-Za-z0-9]+/g, "-")}`;
    const input = el("input", { type: "radio", name, id: safeId, className: "visually-hidden" });
    input.checked = checked;
    input.addEventListener("change", () => onPick(match.career_path));
    return el("label", { className: "opt-card", for: safeId },
        input,
        el("span", { className: "opt-key opt-pct", text: `${Math.round(match.confidence_pct)}%` }),
        el("span", { className: "opt-text", text: match.career_path })
    );
}

// The new, self-fetching picker, as cards: top quiz matches (if any) as option cards, and a
// "choose another path" <select> of all 15. Preselects only when the API itself says to (an
// unambiguous single top match) - never from a remembered previous choice, unlike the legacy picker.
function _fullCareerPathPicker({ has_profile, top_matches, preselect, all_paths, lead, submitText, onSubmit }) {
    const RADIO_NAME = "career-path-match";
    const hasMatches = has_profile && top_matches.length > 0;
    let chosen = preselect || null;

    const select = el("select", { id: "career-path-select", className: "select" },
        el("option", { value: "", text: "Choose a career path", disabled: "", hidden: "" }),
        ...all_paths.map((path) => el("option", { value: path, text: path }))
    );
    // Without this, a native <select> shows its first non-disabled option as
    // if chosen even though nothing was ever picked - wrong whenever
    // preselect is null (an ambiguous/tied set of matches, or no profile).
    select.value = all_paths.includes(preselect) ? preselect : "";

    const submit = el("button", { className: "btn", type: "button", text: submitText });
    const sync = () => { submit.disabled = !chosen; };

    const radioGroup = el("div", { className: "opt-list", role: "radiogroup", "aria-label": "Your quiz matches" });
    if (hasMatches) {
        top_matches.forEach((match) => {
            radioGroup.append(_pathMatchCard(match, RADIO_NAME, match.career_path === preselect, (path) => {
                select.value = "";
                chosen = path;
                sync();
            }));
        });
    }

    select.addEventListener("change", () => {
        if (select.value) {
            radioGroup.querySelectorAll("input").forEach((input) => { input.checked = false; });
            chosen = select.value;
        } else {
            chosen = null;
        }
        sync();
    });
    submit.addEventListener("click", () => { if (chosen) onSubmit(chosen); });
    sync();

    const selectField = el("div", { className: "field" }, el("label", { for: "career-path-select", text: hasMatches ? "Another path" : "Career path" }), select);
    const card = el("div", { className: "card card-pad stack picker", role: "group", "aria-labelledby": "career-path-heading" },
        el("h2", { className: "h2", id: "career-path-heading", text: hasMatches ? "Pick a path" : "Which path?" }),
        lead ? el("span", { className: "chip chip-line", text: lead }) : ""
    );
    if (hasMatches) {
        const other = el("details", { className: "disclosure" }, el("summary", { text: "Choose another path" }), selectField);
        other.open = select.value !== "";   // a preselected path that isn't one of the matches: show it
        card.append(radioGroup, other);
    } else {
        card.append(selectField);
    }
    card.append(
        el("div", { className: "actions" }, submit),
        disclosure("How this works", el("p", { text: "This choice applies to this one request. It doesn't change your quiz results." }))
    );
    return card;
}

// A row asking which career path to use. onSubmit(path) runs when the user confirms.
// lead: extra margin text (e.g. which file this is for).
//
// Two modes, chosen by whether `options` is given:
// - options given (legacy, synchronous): see _legacyCareerPathPicker -
//   exactly today's single-<select> picker, for any caller (dsa.html)
//   that already has its own options list (e.g. from a 400 signal) and
//   isn't part of the shared-picker task.
// - options omitted (new): returns a container immediately (a brief
//   loading state), then GETs /career/options and fills the container in
//   with _fullCareerPathPicker's richer UI once that resolves. Used by
//   roadmap.html and resume.html, both of which now show this picker
//   up front rather than only after a career_path_required signal.
// preselected only applies to the legacy mode - the new mode's preselect
// comes solely from the API (see _fullCareerPathPicker).
function careerPathPicker({ options, message, lead, submitText, preselected, onSubmit }) {
    if (options) {
        return _legacyCareerPathPicker({ options, message, lead, submitText, preselected, onSubmit });
    }

    const container = el("div", {});
    const load = () => {
        container.replaceChildren(el("div", { className: "card card-pad" }, skeleton("Loading career paths", 2)));
        getJson("/career/options").then((result) => {
            if (!result.ok) {
                const again = el("button", { className: "btn", type: "button", text: "Try again" });
                again.addEventListener("click", load);
                container.replaceChildren(alertEl("Couldn't load career paths.", "error", again));
                return;
            }
            container.replaceChildren(_fullCareerPathPicker({ ...result.data, lead, submitText, onSubmit }));
        });
    };
    load();
    return container;
}

// GET a JSON endpoint.
function getJson(url) {
    return request(url, { method: "GET" });
}

// POST, optionally with a JSON body.
function postJson(url, body) {
    const options = { method: "POST" };
    if (body) {
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify(body);
    }
    return request(url, options);
}

// POST a FormData (multipart). The browser sets the Content-Type boundary itself,
// so no Content-Type header is set here.
function postForm(url, formData) {
    return request(url, { method: "POST", body: formData });
}
