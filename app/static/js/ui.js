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

// Always resolves to { ok, status, data } - never throws.
// status 0 = network failure; data is null when the response body wasn't JSON
// (e.g. Flask's HTML 413 page for an oversized upload).
async function request(url, options) {
    try {
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

// A required single-choice question: OMR-style radio answers, then Previous / Next.
// Choosing an answer does NOT move on; Next stays disabled until one is chosen, so no
// question can be skipped.
//   name: unique per question, so its radios group together.
//   labelledBy: id of the heading that holds the question text.
//   options: { A: "text", ... }.  selected: the key chosen earlier (so Previous/Next
//   remembers it), or null.  canGoBack: false on the first question (Previous stays
//   visible but disabled, so the buttons don't jump around).
//   onNext(key) is only ever called with a real key. onBack(key) gets the current choice (or null).
function questionForm({ name, labelledBy, options, selected, canGoBack, nextText, onBack, onNext }) {
    let value = selected != null && Object.prototype.hasOwnProperty.call(options, selected) ? selected : null;

    const group = el("div", { className: "options", role: "radiogroup", "aria-labelledby": labelledBy, "aria-required": "true" });
    const back = el("button", { className: "btn btn-outline", type: "button", text: "Previous" });
    const next = el("button", { className: "btn", type: "submit", text: nextText || "Next" });
    const hint = el("p", { className: "note choose-hint", text: "Choose one answer to continue." });

    const sync = () => {
        next.disabled = value === null;
        hint.hidden = value !== null;
    };

    for (const [key, text] of Object.entries(options)) {
        const input = el("input", { type: "radio", name, value: key, className: "visually-hidden" });
        input.checked = key === value;
        input.addEventListener("change", () => { value = key; sync(); });
        group.append(el("label", { className: "option" },
            input,
            el("span", { className: "bubble", text: key }),
            el("span", { className: "option-text", text })
        ));
    }

    back.disabled = !canGoBack;
    sync();

    // Once a step is under way, freeze the form so a double-click can't send it twice.
    const lock = () => {
        next.disabled = true;
        back.disabled = true;
        group.querySelectorAll("input").forEach((input) => { input.disabled = true; });
    };

    const form = el("form", { className: "qform", novalidate: "" },
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
    return form;
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

// One quiz-match radio card: career path name + confidence %, reusing the
// same .options/.option/.bubble pattern questionForm() uses for quiz/
// conversation answers (.path-match-pct widens the bubble from a single
// letter into a short percentage pill - see style.css).
function _pathMatchCard(match, name, checked, onPick) {
    const safeId = `path-match-${match.career_path.replace(/[^A-Za-z0-9]+/g, "-")}`;
    const input = el("input", { type: "radio", name, id: safeId, className: "visually-hidden" });
    input.checked = checked;
    input.addEventListener("change", () => onPick(match.career_path));
    return el("label", { className: "option", for: safeId },
        input,
        el("span", { className: "bubble path-match-pct", text: `${Math.round(match.confidence_pct)}%` }),
        el("span", { className: "option-text", text: match.career_path })
    );
}

// The new, self-fetching picker: top quiz matches (if any) as radio cards,
// then a "choose a different path" <select> of all 15. Preselects only
// when the API itself says to (an unambiguous single top match) - never
// from a remembered previous choice, unlike the legacy picker.
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

    const radioGroup = el("div", { className: "options path-matches", role: "radiogroup", "aria-label": "Your quiz matches" });
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

    const choiceUi = el("div", {});
    if (hasMatches) {
        choiceUi.append(
            el("h3", { className: "block-title", text: "Your quiz matches" }),
            radioGroup,
            el("div", { className: "field path-match-other" },
                el("label", { for: "career-path-select", text: "Or choose a different path" }),
                select
            )
        );
    } else {
        choiceUi.append(el("div", { className: "field" }, el("label", { for: "career-path-select", text: "Career path" }), select));
    }

    return careerPathPickerFrame({
        lead,
        message: has_profile
            ? "Pick the career path you're generating this for."
            : "You haven't taken the career quiz, so tell us where you're headed and we'll measure against that.",
        choiceUi,
        submit,
    });
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
    container.append(row([], working("Loading career paths...")));
    getJson("/career/options").then((result) => {
        if (!result.ok) {
            container.replaceChildren(row([], el("div", { className: "msg msg-error", role: "alert" },
                el("p", { text: "Couldn't load career paths. Please try again." })
            )));
            return;
        }
        container.replaceChildren(_fullCareerPathPicker({ ...result.data, lead, submitText, onSubmit }));
    });
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
