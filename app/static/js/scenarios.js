// Scenarios page: a map of work scenarios per career path, and a one-question-at-a-time scenario player.
// Globals from ui.js: el, request, svgEl, pbar, alertEl, emptyState, disclosure, skeleton; from scenario_map.js: levelMap,
// openLevelCard.
//
// Answer delivery: the server never sends the key. Each question is LOCKED by POST /scenarios/<id>/answer, whose
// response carries that question's explanation; a locked answer can't be changed, and the final grade is computed
// by the server at POST /scenarios/<id>/submit. All text is set through el() and textContent, so no markup can be injected.

const box = document.getElementById("scen-box");
const live = document.getElementById("scen-live");

const STATE_LABEL = { locked: "Locked", open: "Ready", attempted: "Tried", passed: "Passed" };
const STAGE_LABEL = { foundations: "Foundations", core_decision: "Core decisions", debugging: "Debugging", trade_offs: "Trade-offs", end_to_end: "End to end" };

let paths = null;       // /scenarios/paths
let mapData = null;     // /scenarios/<slug>
let run = null;         // the scenario being played
let gam = null;         // /gamification (XP, level, streak, badges); null if it could not be loaded

function announce(message) {
    live.textContent = "";
    setTimeout(() => { live.textContent = message; }, 30);
}

function errorText(result) {
    const code = result.data && result.data.error;
    // Only runner_unavailable means the checker is down; runtime_error means the student's code crashed.
    if (code === "runner_unavailable") return "Code check unavailable, try again.";
    if (code === "runtime_error") return "Your code crashed while it was being checked. Fix the error and try again.";
    if (code === "timeout") return "The code check took too long to respond. Try again in a moment.";
    if (code === "invalid_language" || code === "language_unavailable") return "That language isn't available here. Pick another one.";
    if (code === "code_too_large") return "Your code or its input is too long. Shorten it and try again.";
    if (result.status === 0) return "Couldn't reach the server. Check your connection and try again.";
    if (result.status === 401) return "You need to be logged in to continue.";
    if (result.status === 429) return "You're doing that too often. Please wait a bit and try again.";
    return "Something went wrong. Please try again.";
}

function showError(result, retry) {
    const actions = [];
    if (result.status === 401) {
        actions.push(el("a", { className: "btn", href: "/login?next=/scenarios", text: "Log in" }));
    } else if (retry) {
        const again = el("button", { className: "btn", type: "button", text: "Try again" });
        again.addEventListener("click", retry);
        actions.push(again);
    }
    box.replaceChildren(alertEl(errorText(result), "error", ...actions));
}

// The coding screen gets a wider column than the rest of the page.
function setWide(on) {
    const page = box.closest(".scen");
    if (page) page.classList.toggle("is-oa", Boolean(on));
}

function focusHeading() {
    const h = document.getElementById("scen-heading");
    if (h) h.focus();
}

function scoreText(s) {
    return s.best_score === null || s.best_score === undefined ? "" : `${s.best_score}/${s.max_score}`;
}

// ---------------------------------------------------------------- start
async function loadPaths() {
    box.replaceChildren(skeleton("Loading scenarios", 2));
    const result = await request("/scenarios/paths");
    if (!result.ok) return showError(result, loadPaths);
    paths = result.data;
    if (!paths.paths.length) {
        box.replaceChildren(emptyState("No scenarios are available yet."));
        return;
    }
    // The pilot shown when the student's own path has nothing yet.
    const pilot = paths.paths.find((p) => p.name === "Machine Learning Engineering") || paths.paths[0];
    if (paths.quiz_path && !paths.quiz_path_available) {
        const open = el("button", { type: "button", className: "btn", text: `Open ${pilot.name} scenarios instead` });
        open.addEventListener("click", () => loadMap(pilot.slug));
        box.replaceChildren(el("div", { className: "card card-pad stack-sm", role: "status" },
            el("h2", { className: "scen-path-title", text: `Scenarios for ${paths.quiz_path} are coming soon.` }),
            el("p", { className: "muted", text: `Your top career match has no scenarios yet. ${pilot.name} is available to try meanwhile.` }),
            el("div", { className: "actions" }, open)));
        return;
    }
    const first = paths.paths.find((p) => p.name === paths.quiz_path) || pilot;
    loadMap(first.slug);
}

async function loadMap(slug) {
    box.replaceChildren(skeleton("Loading the map", 2));
    const [result, g] = await Promise.all([request(`/scenarios/${encodeURIComponent(slug)}`), request("/gamification")]);
    if (!result.ok) return showError(result, () => loadMap(slug));
    mapData = result.data;
    gam = g.ok ? g.data : null;     // extra: the map works without it
    renderMap();
}

// ---------------------------------------------------------------- map
function pathPicker() {
    if (paths.paths.length < 2) return null;
    const select = el("select", { className: "select", id: "scen-path", "aria-label": "Career path" });
    for (const p of paths.paths) {
        const option = el("option", { value: p.slug, text: p.name + (p.name === paths.quiz_path ? " (your top match)" : "") });
        if (p.slug === mapData.slug) option.selected = true;
        select.append(option);
    }
    select.addEventListener("change", () => loadMap(select.value));
    return el("div", { className: "scen-picker" }, el("label", { for: "scen-path", className: "eyebrow", text: "Career path" }), select);
}

function openScenario(s) {
    if (s.state === "locked") {
        const prev = mapData.scenarios.find((x) => x.order === s.order - 1);
        announce(`Locked. Pass ${prev ? prev.title : "the previous scenario"} first (70% or more).`);
        const note = document.getElementById("scen-lock-note");
        if (note) note.textContent = `"${s.title}" opens once you pass ${prev ? `"${prev.title}"` : "the one before it"} (70% or more).`;
        return;
    }
    startScenario(s.id);
}

// The level map (scenario_map.js) opens a level card per node; Start / Try again there calls startScenario.
function levelActions() {
    const nodeFor = (s) => document.querySelector(`.lvl-node[data-order="${s.order}"]`);
    const actions = {
        onStart: (s) => openScenario(s),
        onShow: (s) => openLevelCard(s, mapData.scenarios, actions, nodeFor(s)),
    };
    return actions;
}

function scenarioRow(s) {
    const chips = el("ul", { className: "chips" },
        el("li", { className: `chip chip-state-${s.state}`, text: STATE_LABEL[s.state] + (scoreText(s) ? ` · best ${scoreText(s)}` : "") }),
        el("li", { className: "chip chip-line", text: STAGE_LABEL[s.ladder_stage] || s.ladder_stage }),
        el("li", { className: "chip chip-line", text: `${s.minutes} min` }));
    if (s.recommended) chips.append(el("li", { className: "chip chip-mark", text: "Recommended next" }));
    if (s.matches_goal) chips.append(el("li", { className: "chip chip-line", text: "★ Matches your goal" }));
    const label = s.state === "locked" ? "Locked" : s.state === "open" ? "Start" : "Try again";
    const button = el("button", { type: "button", className: `btn btn-sm${s.recommended ? "" : " btn-secondary"}`, text: label });
    if (s.state === "locked") button.setAttribute("aria-disabled", "true");
    button.addEventListener("click", () => openScenario(s));
    return el("li", { className: "card card-pad scen-row" },
        el("div", {}, el("h3", { className: "scen-row-title", text: `${s.order}. ${s.title}` }), chips), button);
}

function renderMap() {
    setWide(false);
    const kids = [];
    if (gam) kids.push(gamBar(gam));
    const picker = pathPicker();
    if (picker) kids.push(picker);
    kids.push(el("h2", { className: "scen-path-title", text: mapData.path }));
    const actions = levelActions();
    kids.push(levelMap(mapData, { onOpen: (s, node) => openLevelCard(s, mapData.scenarios, actions, node) }));
    kids.push(el("p", { className: "muted", id: "scen-lock-note", role: "status" }));
    if (mapData.weak_topics.length) {
        kids.push(el("div", { className: "card card-pad" },
            el("h3", { className: "scen-sub", text: "Worth another look" }),
            el("ul", { className: "chips" }, ...mapData.weak_topics.map((t) => el("li", { className: "chip", text: t })))));
    }
    kids.push(el("h3", { className: "scen-sub scen-list-title", text: "All scenarios" }));
    kids.push(el("ol", { className: "scen-list stack-sm" }, ...mapData.scenarios.map(scenarioRow)));
    box.replaceChildren(...kids);
}

// ---------------------------------------------------------------- scenario player
async function startScenario(scenarioId) {
    box.replaceChildren(skeleton("Opening the scenario", 2));
    const result = await request(`/scenarios/${encodeURIComponent(scenarioId)}/start`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    if (!result.ok) {
        if (result.status === 403 || result.status === 404) return renderMap();
        return showError(result, () => startScenario(scenarioId));
    }
    const { attempt_id, scenario, locked } = result.data;
    run = { attemptId: attempt_id, scenario, locked: locked || {}, index: 0, answers: {} };
    // Resume after the last locked question.
    const firstOpen = scenario.questions.findIndex((q) => !(q.id in run.locked));
    run.index = firstOpen === -1 ? scenario.questions.length - 1 : firstOpen;
    renderQuestion(firstOpen === -1);
    const title = document.getElementById("scen-title");
    if (title) title.focus();
}

// Prompt text with `backtick` spans shown as inline code. Built from text nodes and <code> elements only.
function inlineCode(text) {
    const parts = String(text).split("`");
    if (parts.length % 2 === 0) return [text];      // an unmatched backtick: show the text as it is
    return parts.map((part, i) => (i % 2 ? el("code", { className: "scen-inline-code", text: part }) : part));
}

function optionText(question, id, pool) {
    const o = (question[pool || "options"] || []).find((x) => x.id === id);
    return o ? o.text : id;
}

function header(question) {
    const total = run.scenario.questions.length;
    const done = Object.keys(run.locked).length;
    const back = el("button", { type: "button", className: "btn btn-ghost btn-sm", text: "Back to map" });
    back.addEventListener("click", () => { loadMap(mapData.slug); });
    return el("div", { className: "stack-sm" },
        el("div", { className: "scen-head" }, back, el("p", { className: "eyebrow", text: `${STAGE_LABEL[run.scenario.ladder_stage] || ""} · ${run.scenario.estimated_minutes} min` })),
        el("h2", { className: "scen-title", id: "scen-title", tabindex: "-1", text: run.scenario.title }),
        pbar((done / total) * 100, `${done} of ${total} questions answered`),
        el("p", { className: "muted", text: `Question ${Math.min(run.index + 1, total)} of ${total}` }));
}

function backgroundCard() {
    const s = run.scenario;
    return el("details", { className: "card card-pad scen-bg", open: "" },
        el("summary", { text: "The situation" }),
        el("p", { text: s.background }),
        el("h3", { className: "scen-sub", text: "Constraints" }),
        el("ul", { className: "chips" }, ...s.constraints.map((c) => el("li", { className: "chip", text: c }))));
}

// Each input builder returns { node, get(): the answer or null if incomplete, lock(result) }.
function buildChoice(question, multi) {
    const name = `q-${question.id}`;
    const wrap = el("div", { className: "scen-options" });
    const inputs = question.options.map((o) => {
        const input = el("input", { type: multi ? "checkbox" : "radio", name, value: o.id, id: `${name}-${o.id}` });
        const status = el("span", { className: "scen-opt-status" });
        const label = el("label", { className: "scen-opt", for: `${name}-${o.id}` }, input, el("span", { className: "scen-opt-text", text: o.text }), status);
        wrap.append(label);
        return { o, input, label, status };
    });
    return {
        node: wrap,
        onChange(cb) { inputs.forEach((i) => i.input.addEventListener("change", cb)); },
        get() {
            const picked = inputs.filter((i) => i.input.checked).map((i) => i.o.id);
            return picked.length ? picked : null;
        },
        lock(result, answer) {
            inputs.forEach((i) => {
                i.input.disabled = true;
                const right = result.correct_answer.includes(i.o.id);
                const chosen = (answer || []).includes(i.o.id);
                i.label.classList.toggle("is-right", right);
                i.label.classList.toggle("is-wrong", chosen && !right);
                i.status.textContent = right ? (chosen ? "Your answer · correct" : "Correct answer") : (chosen ? "Your answer · not correct" : "");
            });
        },
    };
}

function buildOrder(question) {
    let order = question.options.map((o) => o.id);
    const list = el("ol", { className: "scen-order" });
    let cb = () => {};
    let locked = false;
    function draw(focusId, focusDir) {
        list.replaceChildren(...order.map((id, i) => {
            const up = el("button", { type: "button", className: "btn btn-secondary btn-sm scen-move", "aria-label": `Move up: ${optionText(question, id)}`, text: "↑ Up" });
            const down = el("button", { type: "button", className: "btn btn-secondary btn-sm scen-move", "aria-label": `Move down: ${optionText(question, id)}`, text: "↓ Down" });
            if (locked || i === 0) up.disabled = true;
            if (locked || i === order.length - 1) down.disabled = true;
            up.addEventListener("click", () => move(i, -1));
            down.addEventListener("click", () => move(i, 1));
            const li = el("li", { className: "scen-order-item", "data-id": id },
                el("span", { className: "scen-order-text", text: optionText(question, id) }), el("span", { className: "scen-order-btns" }, up, down));
            return li;
        }));
        if (focusId) {
            const li = list.querySelector(`[data-id="${CSS.escape(focusId)}"]`);
            const buttons = li ? li.querySelectorAll("button") : [];
            const wanted = focusDir < 0 ? buttons[0] : buttons[1];
            const target = wanted && !wanted.disabled ? wanted : [...buttons].find((b) => !b.disabled);
            if (target) target.focus();
        }
    }
    function move(i, dir) {
        const j = i + dir;
        if (j < 0 || j >= order.length) return;
        const id = order[i];
        [order[i], order[j]] = [order[j], order[i]];
        draw(id, dir);
        announce(`${optionText(question, id)} is now step ${j + 1} of ${order.length}`);
        cb();
    }
    draw();
    return {
        node: list,
        onChange(fn) { cb = fn; },
        get() { return [...order]; },
        lock(result) { locked = true; draw(); },
    };
}

function buildMatch(question) {
    const wrap = el("div", { className: "scen-match" });
    const selects = question.items.map((item) => {
        const id = `m-${question.id}-${item.id}`;
        const select = el("select", { className: "select", id },
            el("option", { value: "", text: "Choose…" }),
            ...question.targets.map((t) => el("option", { value: t.id, text: t.text })));
        const status = el("span", { className: "scen-opt-status" });
        wrap.append(el("div", { className: "scen-match-row" }, el("label", { for: id, text: item.text }), select, status));
        return { item, select, status };
    });
    return {
        node: wrap,
        onChange(cb) { selects.forEach((s) => s.select.addEventListener("change", cb)); },
        get() {
            if (selects.some((s) => !s.select.value)) return null;
            return Object.fromEntries(selects.map((s) => [s.item.id, s.select.value]));
        },
        lock(result, answer) {
            selects.forEach((s) => {
                s.select.disabled = true;
                const right = result.correct_answer[s.item.id];
                const ok = answer && answer[s.item.id] === right;
                s.status.textContent = ok ? "Correct" : `Not correct. Answer: ${optionText(question, right, "targets")}`;
                s.status.classList.toggle("is-wrong", !ok);
            });
        },
    };
}

// A code question, laid out like an online assessment: the problem on the left; on the right a language picker, the
// editor (line numbers, Tab = 4 spaces) and a test panel with one tab per visible example plus a Results tab; Run and
// Submit at the bottom right. Run = every test (examples in full, hidden ones as a count), ungraded, as often as
// you like; Submit (the shared button from renderQuestion, mounted here by mountCheck) runs every test once and
// locks the answer. Hidden tests only ever arrive as counts.
const TAB_SPACES = "    ";

// The ARIA tabs pattern on the shared .tabs component: arrow keys move between tabs, one panel shows at a time.
function oaTabs(idBase, tabs) {
    const list = el("div", { className: "tabs oa-tabs", role: "tablist", "aria-label": "Test cases" });
    const panels = [];
    const buttons = tabs.map((t, i) => {
        const b = el("button", {
            type: "button", role: "tab", id: `${idBase}-tab-${i}`, "aria-controls": `${idBase}-panel-${i}`,
            "aria-selected": i === 0 ? "true" : "false", tabindex: i === 0 ? "0" : "-1", text: t.label,
        });
        const panel = el("div", { className: "oa-panel stack-sm", role: "tabpanel", id: `${idBase}-panel-${i}`, "aria-labelledby": b.id, tabindex: "0" }, ...t.body);
        if (i !== 0) panel.hidden = true;
        panels.push(panel);
        list.append(b);
        return b;
    });
    function select(i, focus) {
        buttons.forEach((b, j) => {
            b.setAttribute("aria-selected", j === i ? "true" : "false");
            b.setAttribute("tabindex", j === i ? "0" : "-1");
            panels[j].hidden = j !== i;
        });
        if (focus) buttons[i].focus();
    }
    buttons.forEach((b, i) => {
        b.addEventListener("click", () => select(i, false));
        b.addEventListener("keydown", (e) => {
            const n = buttons.length;
            const to = e.key === "ArrowRight" ? (i + 1) % n : e.key === "ArrowLeft" ? (i - 1 + n) % n
                : e.key === "Home" ? 0 : e.key === "End" ? n - 1 : -1;
            if (to < 0) return;
            e.preventDefault();
            select(to, true);
        });
    });
    return { list, panels, select };
}

function oaPre(text, extra) {
    return el("pre", { className: `scen-pre${extra ? ` ${extra}` : ""}`, text });
}

function buildCode(question) {
    const qid = question.id;
    const editorId = `code-${qid}`;
    const languages = question.languages && question.languages.length
        ? question.languages : [{ id: question.language || "python", label: "Python 3" }];
    const starters = question.starters || { python: question.starter_code };
    const draftKey = (lang) => `levelup-code:${run.attemptId}:${qid}:${lang}`;
    const readDraft = (lang) => { try { return localStorage.getItem(draftKey(lang)); } catch (_) { return null; } };
    const saveDraft = (lang, value) => { try { localStorage.setItem(draftKey(lang), value); } catch (_) { /* per-viewer convenience only */ } };
    let lang = languages[0].id;
    try { const last = localStorage.getItem(`levelup-code-lang:${run.attemptId}:${qid}`); if (languages.some((l) => l.id === last)) lang = last; } catch (_) { /* ignore */ }

    // ---- left: the problem
    const visible = question.tests;
    const problem = el("section", { className: "card card-pad oa-problem stack-sm", "aria-labelledby": `${editorId}-ptitle` },
        el("h3", { className: "oa-h", id: `${editorId}-ptitle`, text: "Problem" }),
        ...(question.pick_reason ? [el("p", { className: "hint scen-pick", text: `Why you got this problem: ${question.pick_reason}` })] : []),
        el("p", { className: "oa-prompt", id: "scen-prompt", tabindex: "-1" }, ...inlineCode(question.prompt)),
        el("h4", { className: "oa-h4", text: "Input and output" }),
        el("p", { text: "Your program reads the whole input from standard input and prints only the answer to standard output, in the format described above. Any language works the same way." }),
        ...visible.flatMap((t, i) => [
            el("h4", { className: "oa-h4", text: visible.length > 1 ? `Example ${i + 1}` : "Example" }),
            el("p", { className: "oa-label", text: "Input" }), oaPre(t.stdin),
            el("p", { className: "oa-label", text: "Output" }), oaPre(t.expected_stdout),
        ]));

    // ---- right: language, editor
    const select = el("select", { className: "select oa-lang", id: `${editorId}-lang` },
        ...languages.map((l) => el("option", { value: l.id, text: l.label })));
    select.value = lang;
    const reset = el("button", { type: "button", className: "btn btn-ghost btn-sm", text: "Reset code" });
    const gutter = el("pre", { className: "oa-gutter", "aria-hidden": "true" });
    const editor = el("textarea", {
        className: "scen-code oa-editor", id: editorId, rows: "16", spellcheck: "false", autocomplete: "off",
        autocapitalize: "off", autocorrect: "off", wrap: "off", "aria-describedby": `${editorId}-hint`,
    });
    editor.value = readDraft(lang) ?? starters[lang] ?? "";
    function drawGutter() {
        const n = editor.value.split("\n").length;
        if (gutter.dataset.lines === String(n)) return;
        gutter.dataset.lines = String(n);
        gutter.textContent = Array.from({ length: n }, (_, i) => String(i + 1)).join("\n");
    }
    drawGutter();
    editor.addEventListener("input", () => { drawGutter(); if (!editor.readOnly) saveDraft(lang, editor.value); });
    editor.addEventListener("scroll", () => { gutter.scrollTop = editor.scrollTop; });
    let trapTab = true;   // Tab inserts spaces until Escape; Escape then Tab (or Shift+Tab) moves focus on
    editor.addEventListener("keydown", (e) => {
        if (e.key === "Escape") { trapTab = false; announce("Tab now moves focus out of the editor."); return; }
        if (e.key !== "Tab" || e.shiftKey || e.ctrlKey || e.altKey || e.metaKey) return;
        if (!trapTab) { trapTab = true; return; }
        if (editor.readOnly) return;
        e.preventDefault();
        editor.setRangeText(TAB_SPACES, editor.selectionStart, editor.selectionEnd, "end");
        editor.dispatchEvent(new Event("input", { bubbles: true }));
    });
    editor.addEventListener("blur", () => { trapTab = true; });

    select.addEventListener("change", () => {
        saveDraft(lang, editor.value);
        lang = select.value;
        try { localStorage.setItem(`levelup-code-lang:${run.attemptId}:${qid}`, lang); } catch (_) { /* ignore */ }
        editor.value = readDraft(lang) ?? starters[lang] ?? "";
        editor.scrollTop = 0;
        drawGutter();
        editor.dispatchEvent(new Event("input", { bubbles: true }));
        clearOutputs();
        announce(`Language: ${select.options[select.selectedIndex].text}. Your code for each language is kept separately.`);
    });
    reset.addEventListener("click", () => {
        editor.value = starters[lang] ?? "";
        editor.dispatchEvent(new Event("input", { bubbles: true }));
        editor.focus();
        announce("The starter code is back.");
    });

    const editorCard = el("div", { className: "card oa-editor-card" },
        el("div", { className: "oa-toolbar" },
            el("label", { className: "oa-lang-label", for: select.id, text: "Language" }), select, reset),
        el("div", { className: "oa-code" }, gutter, editor),
        el("p", { className: "hint oa-hint", id: `${editorId}-hint`, text: "Tab inserts 4 spaces. Press Escape, then Tab, to move on." }));
    const editorLabel = el("label", { className: "visually-hidden", for: editorId, text: "Your code" });

    // ---- below: test cases
    const outputs = visible.map(() => el("div", { className: "oa-yours stack-sm" }));
    const verdicts = visible.map(() => el("p", { className: "oa-verdict" }));
    function clearOutputs() {
        outputs.forEach((o) => o.replaceChildren(el("p", { className: "muted", text: "Run your code to see its output here." })));
        verdicts.forEach((v) => { v.textContent = ""; v.className = "oa-verdict"; });
    }
    clearOutputs();
    const resultsBody = el("div", { className: "oa-results stack-sm", "aria-live": "polite" },
        el("p", { className: "muted", text: "Run tests your code against the example and the hidden tests, as often as you like, and nothing is saved. Submit does the same once, and locks your answer." }));
    const tabs = oaTabs(`${editorId}-tc`, [
        ...visible.map((t, i) => ({
            label: visible.length > 1 ? `Example ${i + 1}` : "Example",
            body: [verdicts[i], el("p", { className: "oa-label", text: "Input" }), oaPre(t.stdin),
                el("p", { className: "oa-label", text: "Expected output" }), oaPre(t.expected_stdout),
                el("p", { className: "oa-label", text: "Your output" }), outputs[i]],
        })),
        { label: "Results", body: [resultsBody] },
    ]);
    const runBtn = el("button", { type: "button", className: "btn btn-secondary", text: "Run" });
    const status = el("p", { className: "oa-status muted", "aria-live": "polite" });
    const actionBar = el("div", { className: "oa-actions" }, status, el("div", { className: "oa-buttons" }, runBtn));
    const testsCard = el("div", { className: "card oa-tests" }, tabs.list, ...tabs.panels, actionBar);

    let busy = false;
    runBtn.addEventListener("click", async () => {
        if (busy || !editor.value.trim()) return;
        busy = true;
        runBtn.disabled = true;
        runBtn.setAttribute("aria-busy", "true");
        status.textContent = "Running all tests…";
        const result = await request(`/scenarios/${encodeURIComponent(run.scenario.id)}/code/run`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ attempt_id: run.attemptId, question_id: qid, source: editor.value, language: lang }),
        });
        busy = false;
        runBtn.removeAttribute("aria-busy");
        runBtn.disabled = editor.readOnly;
        if (!result.ok) {
            status.textContent = errorText(result);
            return;
        }
        const results = result.data.results;
        results.forEach((r, i) => {
            if (!outputs[i]) return;
            verdicts[i].textContent = r.passed ? "Passed" : "Not passed";
            verdicts[i].className = `oa-verdict scen-verdict ${r.passed ? "is-right" : "is-wrong"}`;
            const kids = [];
            if (r.exception === "time_limit") kids.push(el("p", { className: "oa-note", text: "Your program ran out of time." }));
            else if (r.exception === "memory_limit") kids.push(el("p", { className: "oa-note", text: "Your program used too much memory." }));
            else if (r.exception === "error" || (r.stderr && !r.passed)) kids.push(el("p", { className: "oa-note", text: "Your program crashed or did not compile. The error is below." }));
            kids.push(oaPre(r.stdout || "(nothing printed)", r.stdout ? "" : "is-empty"));
            if (r.stderr) kids.push(el("p", { className: "oa-label", text: "Errors" }), oaPre(r.stderr, "is-error"));
            outputs[i].replaceChildren(...kids);
        });
        const passed = results.filter((r) => r.passed).length;
        const hiddenLine = `Hidden tests: ${result.data.hidden_passed} of ${result.data.hidden_total} passed.`;
        const allPassed = passed === results.length && result.data.hidden_passed === result.data.hidden_total;
        status.textContent = `${passed} of ${results.length} example${results.length === 1 ? "" : "s"} passed. ${hiddenLine} Not submitted yet.`;
        resultsBody.replaceChildren(
            el("p", { className: `scen-verdict ${allPassed ? "is-right" : "is-wrong"}`, text: allPassed ? "All tests passed on this run" : "Not all tests passed on this run" }),
            el("p", { text: `Example tests: ${passed} of ${results.length} passed.` }),
            el("p", { className: "oa-hidden-count", text: hiddenLine }),
            el("p", { className: "muted", text: "This was only a run. Edit and run again as often as you like, then Submit when you are happy: Submit locks your answer." }));
        tabs.select(allPassed || !results.length ? visible.length : 0, false);
        announce(status.textContent);
    });

    const node = el("div", { className: "oa", role: "region", "aria-label": "Coding question" },
        problem, el("section", { className: "oa-work stack-sm", "aria-label": "Your solution" }, editorLabel, editorCard, testsCard));
    return {
        node,
        onChange(cb) { editor.addEventListener("input", cb); },
        get() { return editor.value.trim() ? editor.value : null; },
        language() { return lang; },
        mountCheck(check) { actionBar.querySelector(".oa-buttons").append(check); },
        lock(result) {
            // A resumed attempt shows the source and language that were checked, not a starter.
            if (result && typeof result.source === "string" && result.source) editor.value = result.source;
            if (result && result.language) {
                if (![...select.options].some((o) => o.value === result.language)) {
                    select.append(el("option", { value: result.language, text: result.language }));
                }
                select.value = result.language;
                lang = result.language;
            }
            drawGutter();
            editor.readOnly = true;
            select.disabled = true;
            reset.disabled = true;
            runBtn.disabled = true;
            if (result) {
                const seen = result.visible_passed || [];
                resultsBody.replaceChildren(
                    el("p", { className: `scen-verdict ${result.correct ? "is-right" : "is-wrong"}`, text: result.correct ? "All tests passed" : "Not all tests passed" }),
                    el("p", { text: `Example tests: ${seen.filter(Boolean).length} of ${seen.length || visible.length} passed.` }),
                    el("p", { className: "oa-hidden-count", text: `Hidden tests: ${result.hidden_passed} of ${result.hidden_total} passed.` }),
                    el("p", { className: "muted", text: "Hidden test inputs stay hidden. Your answer is submitted and locked." }));
                status.textContent = "Submitted. Answer locked.";
                tabs.select(visible.length, false);
            }
        },
    };
}

function correctAnswerText(question, result) {
    if (question.type === "code") return [result.correct_answer];
    if (question.type === "match") {
        return Object.entries(result.correct_answer).map(([i, t]) => `${optionText(question, i, "items")} → ${optionText(question, t, "targets")}`);
    }
    return result.correct_answer.map((id, n) => (question.type === "order" ? `${n + 1}. ` : "") + optionText(question, id));
}

function feedbackCard(question, result) {
    const kids = [
        el("h3", { className: `scen-verdict ${result.correct ? "is-right" : "is-wrong"}`, id: "scen-feedback", tabindex: "-1", text: result.correct ? "Correct" : "Not quite" }),
        el("p", { text: result.explanation }),
    ];
    if (question.type === "code") {
        const seen = result.visible_passed || [];
        kids.push(el("p", { text: `Example tests: ${seen.filter(Boolean).length} of ${question.tests.length} passed. Hidden tests: ${result.hidden_passed} of ${result.hidden_total} passed.` }));
    }
    if (!result.correct) {
        kids.push(el("h4", { className: "scen-sub", text: question.type === "multi_select" ? "The correct answers" : question.type === "code" ? "For example" : "The correct answer" }));
        kids.push(el("ul", { className: "scen-answer-list" }, ...correctAnswerText(question, result).map((t) => el("li", { text: t }))));
    }
    const wrong = result.why_others_wrong || {};
    const rows = Object.entries(wrong);
    if (rows.length) {
        const items = rows.map(([id, why]) => (id === "common_mistake"
            ? el("li", {}, el("strong", { text: "A common mistake: " }), why)
            : el("li", {}, el("strong", { text: `${optionText(question, id)}: ` }), why)));
        kids.push(disclosure(question.type === "order" || question.type === "match" ? "Common mistake" : "Why the other options don't fit", el("ul", { className: "scen-why" }, ...items)));
    }
    return el("div", { className: "card card-pad scen-feedback", role: "region", "aria-label": "Feedback" }, ...kids);
}

function renderQuestion(allDone) {
    const scenario = run.scenario;
    const question = scenario.questions[run.index];
    const isLast = run.index === scenario.questions.length - 1;
    const lockedResult = run.locked[question.id];

    if (allDone) return renderSubmitStep();

    const input = question.type === "order" ? buildOrder(question)
        : question.type === "match" ? buildMatch(question)
        : question.type === "code" ? buildCode(question)
        : buildChoice(question, question.type === "multi_select");
    const hint = question.type === "multi_select" ? "Choose all that apply."
        : question.type === "order" ? "Use the Up and Down buttons to put the steps in order."
        : question.type === "match" ? "Pick one for each, using each option once."
        : "Choose one.";

    const check = el("button", { type: "button", className: "btn", text: question.type === "code" ? "Submit" : "Check answer" });
    const slot = el("div", { className: "stack-sm", id: "scen-slot" });
    const nextBar = el("div", { className: "actions" });   // after the feedback, so Tab reaches it next
    let card;
    if (question.type === "code") {
        // The online-assessment layout carries its own prompt, hint and action bar; Submit goes next to Run.
        input.mountCheck(check);
        card = input.node;
    } else {
        const fieldset = el("fieldset", { className: "scen-fieldset" },
            el("legend", { className: "scen-prompt", id: "scen-prompt", tabindex: "-1" }, ...inlineCode(question.prompt)),
            el("p", { className: "hint", text: hint }), input.node);
        card = el("div", { className: "card card-pad stack-sm" }, fieldset, el("div", { className: "actions" }, check));
    }
    setWide(question.type === "code");

    box.replaceChildren(header(question), backgroundCard(), card, slot, nextBar);

    function refresh() { check.disabled = input.get() === null; }
    if (input.onChange) input.onChange(refresh);
    refresh();

    function showFeedback(result, answer) {
        input.lock(result, answer);
        check.remove();
        slot.replaceChildren(feedbackCard(question, result));
        const next = el("button", { type: "button", className: "btn", text: isLast ? "See results" : "Next question" });
        next.addEventListener("click", () => {
            if (isLast) return renderSubmitStep();
            run.index += 1;
            renderQuestion(false);
            const p = document.getElementById("scen-prompt");
            if (p) p.focus();
        });
        nextBar.append(next);
        const fb = document.getElementById("scen-feedback");
        if (fb) fb.focus();
    }

    if (lockedResult) {
        // Resumed attempt: the answer was locked in an earlier visit; the server still has it, show the feedback only.
        check.remove();
        input.node.querySelectorAll("input,select,button:not([role=tab])").forEach((n) => { n.disabled = true; });
        showFeedback(lockedResult, null);
        return;
    }

    check.addEventListener("click", async () => {
        const answer = input.get();
        if (answer === null) return;
        check.disabled = true;
        check.setAttribute("aria-busy", "true");
        const result = await request(`/scenarios/${encodeURIComponent(scenario.id)}/answer`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ attempt_id: run.attemptId, question_id: question.id, answer,
                ...(input.language ? { language: input.language() } : {}) }),
        });
        check.removeAttribute("aria-busy");
        if (!result.ok) {
            check.disabled = false;
            slot.replaceChildren(alertEl(errorText(result), "error"));
            return;
        }
        run.locked[question.id] = result.data.result;
        run.answers[question.id] = answer;
        showFeedback(result.data.result, answer);
    });
}

async function renderSubmitStep() {
    box.replaceChildren(skeleton("Scoring", 1));
    const result = await request(`/scenarios/${encodeURIComponent(run.scenario.id)}/submit`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ attempt_id: run.attemptId, answers: run.answers }),
    });
    if (!result.ok) {
        if (result.status === 409) return loadMap(mapData.slug);
        return showError(result, renderSubmitStep);
    }
    mapData.scenarios = result.data.scenarios;
    mapData.weak_topics = result.data.weak_topics;
    renderSummary(result.data);
}

function renderSummary(data) {
    setWide(false);
    const scenario = run.scenario;
    const retry = el("button", { type: "button", className: "btn btn-secondary", text: "Retry" });
    retry.addEventListener("click", () => startScenario(scenario.id));
    const back = el("button", { type: "button", className: "btn", text: "Back to map" });
    back.addEventListener("click", () => loadMap(mapData.slug));

    const rows = data.results.map((r, n) => {
        const q = scenario.questions.find((x) => x.id === r.question_id) || { prompt: r.question_id };
        return el("li", { className: "card card-pad scen-result" },
            el("p", { className: `scen-verdict ${r.correct ? "is-right" : "is-wrong"}`, text: `${n + 1}. ${r.correct ? "Correct" : "Not quite"} · ${r.awarded} points` }),
            el("p", { className: "scen-result-q", text: q.prompt }),
            disclosure("Explanation", el("p", { text: r.explanation })));
    });
    const next = data.scenarios.find((s) => s.recommended);
    // The scenario after this one: unlocked only by a pass (the server's rule; the map shows the same state).
    const following = data.scenarios.find((s) => s.order === scenario.order + 1);
    const unlocked = data.passed && following && following.state !== "locked" ? following : null;
    const kids = [
        el("div", { className: "card card-pad card-hero stack-sm" },
            el("h2", { className: "scen-title", id: "scen-title", tabindex: "-1", text: data.passed ? "Scenario passed" : "Not passed yet" }),
            el("p", { className: "scen-score", text: `${data.score} of ${data.max_score} points (${data.percent}%)` }),
            el("p", { text: data.passed
                ? `You passed. The pass mark is 70%.${unlocked ? ` "${unlocked.title}" is now unlocked.` : ""}`
                : `The pass mark is 70%.${following ? ` Pass this scenario to unlock "${following.title}".` : ""} Read the explanations and try again whenever you like.` })),
        gamRewardsCard(data.rewards),
    ];
    if (data.weak_topics.length) {
        kids.push(el("div", { className: "card card-pad" }, el("h3", { className: "scen-sub", text: "Topics to revisit" }),
            el("ul", { className: "chips" }, ...data.weak_topics.map((t) => el("li", { className: "chip", text: t })))));
    }
    if (next && next.id !== scenario.id) kids.push(el("p", { className: "muted", text: `Recommended next: ${next.title}` }));
    kids.push(el("ol", { className: "stack-sm scen-results" }, ...rows));
    kids.push(el("div", { className: "actions" }, back, retry));
    box.replaceChildren(...kids);
    const t = document.getElementById("scen-title");
    if (t) t.focus();
    announce(`${data.passed ? "Scenario passed." : "Scenario not passed yet."} ${gamRewardsAnnouncement(data.rewards)}`.trim());
}

loadPaths();
