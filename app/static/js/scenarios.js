// Scenarios page: a map of work scenarios per career path, and a one-question-at-a-time scenario player.
// Globals from ui.js: el, request, svgEl, pbar, alertEl, emptyState, disclosure, skeleton.
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

function announce(message) {
    live.textContent = "";
    setTimeout(() => { live.textContent = message; }, 30);
}

function errorText(result) {
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
    const first = paths.paths.find((p) => p.name === paths.quiz_path) || paths.paths[0];
    loadMap(first.slug);
}

async function loadMap(slug) {
    box.replaceChildren(skeleton("Loading the map", 2));
    const result = await request(`/scenarios/${encodeURIComponent(slug)}`);
    if (!result.ok) return showError(result, () => loadMap(slug));
    mapData = result.data;
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

function nodeLabel(s) {
    const bits = [`Scenario ${s.order}: ${s.title}`, STATE_LABEL[s.state]];
    if (scoreText(s)) bits.push(`best ${scoreText(s)}`);
    if (s.recommended) bits.push("recommended next");
    if (s.matches_goal) bits.push("matches your goal");
    return bits.join(", ");
}

function openScenario(s) {
    if (s.state === "locked") {
        const prev = mapData.scenarios.find((x) => x.order === s.order - 1);
        announce(`Locked. Try ${prev ? prev.title : "the previous scenario"} first.`);
        const note = document.getElementById("scen-lock-note");
        if (note) note.textContent = `"${s.title}" opens once you've tried ${prev ? `"${prev.title}"` : "the one before it"}.`;
        return;
    }
    startScenario(s.id);
}

function mapCanvas() {
    const canvas = el("div", { className: "smap", role: "group", "aria-label": `Map of ${mapData.path} scenarios` });
    if (mapData.scene_url) {
        canvas.append(el("img", { className: "smap-scene", src: mapData.scene_url, alt: "", "aria-hidden": "true" }));
    }
    const byId = Object.fromEntries(mapData.scenarios.map((s) => [s.id, s]));
    const lines = svgEl("svg", { class: "smap-edges", viewBox: "0 0 100 100", preserveAspectRatio: "none", "aria-hidden": "true", focusable: "false" });
    for (const [a, b] of mapData.edges) {
        const from = byId[a], to = byId[b];
        if (!from || !to) continue;
        lines.append(svgEl("line", {
            x1: String(from.map_node.x * 100), y1: String(from.map_node.y * 100),
            x2: String(to.map_node.x * 100), y2: String(to.map_node.y * 100),
            class: `smap-edge${to.state === "locked" ? " is-locked" : ""}`,
        }));
    }
    canvas.append(lines);
    for (const s of mapData.scenarios) {
        const mark = s.state === "passed" ? "✓" : s.state === "locked" ? "\u{1F512}" : String(s.order);
        const node = el("button", {
            type: "button", className: `smap-node is-${s.state}${s.recommended ? " is-recommended" : ""}`,
            "aria-label": nodeLabel(s),
        }, el("span", { className: "smap-num", "aria-hidden": "true", text: mark }),
            el("span", { className: "smap-name", "aria-hidden": "true", text: s.map_node.label }));
        if (s.state === "locked") node.setAttribute("aria-disabled", "true");
        node.style.left = `${s.map_node.x * 100}%`;
        node.style.top = `${s.map_node.y * 100}%`;
        if (s.matches_goal) node.append(el("span", { className: "smap-goal", "aria-hidden": "true", title: "Matches your goal", text: "★" }));
        node.addEventListener("click", () => openScenario(s));
        canvas.append(node);
    }
    return canvas;
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
    const kids = [];
    const picker = pathPicker();
    if (picker) kids.push(picker);
    kids.push(el("h2", { className: "scen-path-title", text: mapData.path }));
    kids.push(mapCanvas());
    kids.push(el("p", { className: "muted", id: "scen-lock-note", role: "status" }));
    if (mapData.weak_topics.length) {
        kids.push(el("div", { className: "card card-pad" },
            el("h3", { className: "scen-sub", text: "Worth another look" }),
            el("ul", { className: "chips" }, ...mapData.weak_topics.map((t) => el("li", { className: "chip", text: t })))));
    }
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

function correctAnswerText(question, result) {
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
    if (!result.correct) {
        kids.push(el("h4", { className: "scen-sub", text: question.type === "multi_select" ? "The correct answers" : "The correct answer" }));
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
        : buildChoice(question, question.type === "multi_select");
    const hint = question.type === "multi_select" ? "Choose all that apply."
        : question.type === "order" ? "Use the Up and Down buttons to put the steps in order."
        : question.type === "match" ? "Pick one for each, using each option once." : "Choose one.";

    const fieldset = el("fieldset", { className: "scen-fieldset" },
        el("legend", { className: "scen-prompt", id: "scen-prompt", tabindex: "-1", text: question.prompt }),
        el("p", { className: "hint", text: hint }), input.node);
    const check = el("button", { type: "button", className: "btn", text: "Check answer" });
    const slot = el("div", { className: "stack-sm", id: "scen-slot" });
    const actions = el("div", { className: "actions" }, check);
    const nextBar = el("div", { className: "actions" });   // after the feedback, so Tab reaches it next
    const card = el("div", { className: "card card-pad stack-sm" }, fieldset, actions);

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
        input.node.querySelectorAll("input,select,button").forEach((n) => { n.disabled = true; });
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
            body: JSON.stringify({ attempt_id: run.attemptId, question_id: question.id, answer }),
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
    const kids = [
        el("div", { className: "card card-pad card-hero stack-sm" },
            el("h2", { className: "scen-title", id: "scen-title", tabindex: "-1", text: data.passed ? "Scenario passed" : "Not passed yet" }),
            el("p", { className: "scen-score", text: `${data.score} of ${data.max_score} points (${data.percent}%)` }),
            el("p", { text: data.passed ? "You passed. The pass mark is 70%." : "The pass mark is 70%. Read the explanations and try again whenever you like." })),
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
    announce(data.passed ? "Scenario passed." : "Scenario not passed yet.");
}

loadPaths();
