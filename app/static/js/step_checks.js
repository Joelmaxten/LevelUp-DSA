// Verified progression on the roadmap page: a step is completed by passing a short check made from the passages the
// step was built from (server: app/routes/step_checks.py). Text only through el()/textContent; requests only through
// the CSRF helpers in ui.js. Loaded after results.js; results.js's roadmapStep() calls wireStepCheck() when the
// page passes progress.verified = true.

function _fmtWait(isoUntil) {
    const ms = new Date(isoUntil).getTime() - Date.now();
    const s = Math.max(1, Math.ceil(ms / 1000));
    return s >= 60 ? `${Math.ceil(s / 60)} min` : `${s} s`;
}

function _stepStateOf(stepProgress) {
    const states = stepProgress.states || {};
    return states[String(stepProgress.stepIndex)] || null;
}

// The control in a step's top-left slot, chosen by that step's state.
function wireStepCheck(checkSlot, stepProgress, liEl) {
    const state = _stepStateOf(stepProgress);
    if (!state || !state.checkable) {
        // No check for this step (an older roadmap, or no source passages): keep the plain tick box.
        wireStepCheckbox(checkSlot, stepProgress, liEl);
        return;
    }
    checkSlot.classList.add("step-check-verified");
    const { roadmapId, stepIndex } = stepProgress;
    // The narrow slot left of the step holds only a status mark; the actions go in the step body, under the text.
    const mark = (cls, text, label) => el("span", { className: `sc-mark ${cls}`, role: "img", "aria-label": label, text });
    const box = el("div", { className: "sc-control" });

    if (state.status === "done") {
        liEl.classList.add("step-done");
        checkSlot.append(mark("sc-mark-done", "\u2713", state.verified ? "Verified" : "Done"));
        box.append(el("span", { className: `chip ${state.verified ? "chip-ink sc-verified" : "chip-line"}`,
            text: state.verified ? "\u2713 Verified" : "Done (self-marked)" }));
    } else if (state.review_required) {
        checkSlot.append(mark("sc-mark-open", "", "Not done yet"));
        const btn = el("button", { className: "btn btn-secondary btn-sm", type: "button", text: "Review first" });
        btn.addEventListener("click", () => openStepReview(roadmapId, stepIndex, stepProgress));
        box.append(btn, el("p", { className: "muted sc-note", text: "Two misses in a row: re-read this step, then try again." }));
    } else if (state.cooldown_until && new Date(state.cooldown_until).getTime() > Date.now()) {
        checkSlot.append(mark("sc-mark-open", "", "Not done yet"));
        const btn = el("button", { className: "btn btn-sm", type: "button", text: "Take the check" });
        btn.disabled = true;
        box.append(btn, el("p", { className: "muted sc-note", text: `Try again in ${_fmtWait(state.cooldown_until)}.` }));
    } else if (state.status === "open") {
        checkSlot.append(mark("sc-mark-open", "", "Not done yet"));
        const btn = el("button", { className: "btn btn-sm", type: "button", text: "Take the check" });
        btn.addEventListener("click", () => openStepCheck(roadmapId, stepIndex, "check", stepProgress, btn));
        box.append(btn, el("p", { className: "muted sc-note", text: "Pass a short check to complete this step." }));
    } else {   // locked
        liEl.classList.add("step-locked");
        checkSlot.append(mark("sc-mark-locked", "\uD83D\uDD12", "Locked"));
        const btn = el("button", { className: "btn btn-ghost btn-sm", type: "button", text: "Test out" });
        btn.addEventListener("click", () => openStepCheck(roadmapId, stepIndex, "test_out", stepProgress, btn));
        box.append(el("p", { className: "muted sc-note", text: "Locked until the step before is done. Already know it?" }), btn);
    }
    const body = liEl.querySelector(".step-body");
    (body || checkSlot).append(box);
}

function _dialog(id, labelledBy) {
    const old = document.getElementById(id);
    if (old) old.remove();
    const dialog = el("dialog", { className: "lvl-card sc-dialog", id, "aria-labelledby": labelledBy });
    document.body.append(dialog);
    dialog.addEventListener("close", () => dialog.remove());
    return dialog;
}

function _closeBtn(dialog) {
    const btn = el("button", { className: "btn-link lvl-card-close", type: "button", "aria-label": "Close", text: "×" });
    btn.addEventListener("click", () => dialog.close());
    return btn;
}

async function openStepCheck(roadmapId, stepIndex, mode, stepProgress, trigger) {
    if (trigger) trigger.setAttribute("aria-busy", "true");
    const result = await postJson(`/roadmap/${roadmapId}/steps/${stepIndex}/check/start`, { mode });
    if (trigger) trigger.removeAttribute("aria-busy");
    const dialog = _dialog("sc-dialog", "sc-title");
    const title = mode === "test_out" ? `Test out of step ${stepIndex}` : `Check: step ${stepIndex}`;
    const body = el("div", { className: "lvl-card-body stack-sm" },
        el("div", { className: "lvl-card-top" }, el("h2", { className: "lvl-card-title", id: "sc-title", tabindex: "-1", text: title }), _closeBtn(dialog)));
    dialog.append(body);

    if (!result.ok) {
        const msg = (result.data && (result.data.message || result.data.error)) || "Couldn't start the check. Try again.";
        body.append(alertEl(result.status === 0 ? "Couldn't reach the server." : msg, "error"));
        dialog.showModal();
        return;
    }
    const data = result.data;
    body.append(el("p", { className: "muted", text: mode === "test_out"
        ? `Already know this? Get ${data.pass_mark} of ${data.total} right to complete this step without the ones before it.`
        : `Answer from what this step taught you. ${data.pass_mark} of ${data.total} correct completes the step.` }));

    const form = el("form", { className: "stack-sm sc-form" });
    data.questions.forEach((q, qi) => {
        const name = `scq-${q.id}`;
        const fieldset = el("fieldset", { className: "sc-q" },
            el("legend", { className: "sc-prompt", text: `${qi + 1}. ${q.prompt}` }),
            ...q.options.map((o) => el("label", { className: "sc-opt" },
                el("input", { type: "radio", name, value: o.id, required: true }), el("span", { text: o.text }))));
        form.append(fieldset);
    });
    const submit = el("button", { className: "btn", type: "submit", text: "Submit answers" });
    const error = el("div", { role: "alert" });
    form.append(error, submit);
    body.append(form);

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (submit.getAttribute("aria-busy") === "true") return;
        const answers = {};
        data.questions.forEach((q) => {
            const picked = form.querySelector(`input[name="scq-${q.id}"]:checked`);
            if (picked) answers[String(q.id)] = picked.value;
        });
        if (Object.keys(answers).length < data.questions.length) {
            error.replaceChildren(alertEl("Answer every question first.", "error"));
            return;
        }
        submit.setAttribute("aria-busy", "true");
        const graded = await postJson(`/roadmap/${roadmapId}/steps/${stepIndex}/check/submit`, { attempt_id: data.attempt_id, answers });
        submit.removeAttribute("aria-busy");
        if (!graded.ok) {
            error.replaceChildren(alertEl((graded.data && (graded.data.message || graded.data.error)) || "Couldn't submit. Try again.", "error"));
            return;
        }
        _showResult(body, form, graded.data, data, dialog, stepProgress);
    });

    dialog.showModal();
    dialog.querySelector("#sc-title").focus();
}

function _showResult(body, form, res, started, dialog, stepProgress) {
    const promptOf = new Map(started.questions.map((q) => [q.id, q.prompt]));
    const head = res.passed
        ? alertEl(`Passed: ${res.score} of ${res.total}. Step complete.`, "ok")
        : alertEl(`${res.score} of ${res.total}: ${res.pass_mark} needed. Re-read the passages below, then try again.`, "error");
    const list = el("ol", { className: "sc-results stack-sm" }, ...res.results.map((r) => el("li", { className: r.correct ? "sc-right" : "sc-wrong" },
        el("p", { className: "sc-prompt", text: `${r.correct ? "✓" : "✗"} ${promptOf.get(r.id) || ""}` }),
        res.passed && r.answer ? el("p", {}, el("strong", { text: "Answer: " }), el("span", { text: r.answer })) : "",
        res.passed && r.evidence ? el("p", { className: "muted" }, el("span", { text: `From “${r.source_title}”: ` }), el("em", { text: r.evidence })) : "",
        !res.passed && !r.correct && r.source_title ? el("p", { className: "muted", text: `Re-read: ${r.source_title}` }) : "")));
    const done = el("button", { className: "btn", type: "button", text: res.passed ? "Continue" : "Close" });
    done.addEventListener("click", () => dialog.close());
    form.replaceWith(el("div", { className: "stack-sm" }, head, list, done));
    if (stepProgress && stepProgress.onStepsChanged) stepProgress.onStepsChanged(res);
    done.focus();
}

async function openStepReview(roadmapId, stepIndex, stepProgress) {
    const result = await getJson(`/roadmap/${roadmapId}/steps/${stepIndex}/review`);
    const dialog = _dialog("sc-review", "sc-review-title");
    const body = el("div", { className: "lvl-card-body stack-sm" },
        el("div", { className: "lvl-card-top" }, el("h2", { className: "lvl-card-title", id: "sc-review-title", tabindex: "-1", text: "Review this step" }), _closeBtn(dialog)));
    dialog.append(body);
    if (!result.ok) {
        body.append(alertEl("Couldn't load the material. Try again.", "error"));
        dialog.showModal();
        return;
    }
    body.append(el("p", { className: "muted", text: `${result.data.title}: the passages this step's questions come from.` }));
    result.data.passages.forEach((p) => {
        body.append(el("section", { className: "sc-passage stack-sm" },
            el("h3", { className: "sc-passage-title", text: p.title }),
            el("p", { text: p.text }),
            p.resources.length ? el("ul", { className: "sc-links" }, ...p.resources.map((r) =>
                el("li", {}, el("a", { href: r.url, target: "_blank", rel: "noopener noreferrer", text: r.title || r.url })))) : ""));
    });
    const doneBtn = el("button", { className: "btn", type: "button", text: "I've reviewed it" });
    const error = el("div", { role: "alert" });
    doneBtn.addEventListener("click", async () => {
        doneBtn.setAttribute("aria-busy", "true");
        const r = await postJson(`/roadmap/${roadmapId}/steps/${stepIndex}/review`, {});
        doneBtn.removeAttribute("aria-busy");
        if (!r.ok && r.status !== 409) {
            error.replaceChildren(alertEl("Couldn't save. Try again.", "error"));
            return;
        }
        dialog.close();
        if (stepProgress && stepProgress.onStepsChanged) stepProgress.onStepsChanged(null);
    });
    body.append(error, doneBtn);
    dialog.showModal();
    dialog.querySelector("#sc-review-title").focus();
}
