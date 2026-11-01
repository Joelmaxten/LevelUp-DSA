// "Your skills" card for the dashboard: what the student has verified (and what proved it), what is in progress, and what
// is only on the resume. The numbers come from GET /skills/evidence; the rules live in app/pipeline/skill_evidence.py.
// Globals from ui.js: el, pbar, disclosure. All text goes through el() / textContent only, so no markup is injected.

const SKILL_SOURCE_LABELS = {
    step_check: "Passed step check",
    test_out: "Passed test-out",
    scenario: "Passed scenario",
    code: "Solved code problem",
};
const SKILL_SHOW_FIRST = 8;      // verified skills shown before "Show more"
const SKILL_EVIDENCE_SHOWN = 3;  // pieces of evidence listed per skill before "+ N more"

function skillDate(iso) {
    const moment = iso ? new Date(iso) : null;
    if (!moment || Number.isNaN(moment.getTime())) return "";
    return moment.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

// Why a skill counts: one line per piece of evidence, with its date.
function skillWhy(evidence) {
    const lines = evidence.slice(0, SKILL_EVIDENCE_SHOWN).map((piece) => {
        const when = skillDate(piece.date);
        const label = SKILL_SOURCE_LABELS[piece.source] || "Evidence";
        return el("li", { text: `${label}: ${piece.title}${when ? ` · ${when}` : ""}` });
    });
    if (evidence.length > SKILL_EVIDENCE_SHOWN) {
        lines.push(el("li", { className: "muted", text: `+ ${evidence.length - SKILL_EVIDENCE_SHOWN} more` }));
    }
    return el("ul", { className: "skill-why" }, ...lines);
}

function skillRow(skill) {
    const pct = Math.round(skill.confidence * 100);
    const kindLabel = skill.kind === "concept" ? "Concept" : "Tool";
    const kids = [
        el("div", { className: "skill-head" },
            el("div", { className: "cluster" },
                el("span", { className: "skill-name", text: skill.skill }),
                el("span", { className: "chip chip-line", text: kindLabel })),
            el("span", { className: "num skill-pct", text: `${pct}%` })),
        pbar(pct, `${skill.skill}: ${pct}% confidence`),
    ];
    if (skill.status === "in_progress") {
        const count = skill.evidence.length;
        kids.push(el("p", { className: "muted skill-note",
            text: `In progress: ${count} piece${count === 1 ? "" : "s"} of evidence so far. One more passed step, scenario or problem verifies it.` }));
    }
    kids.push(skillWhy(skill.evidence));
    return el("li", { className: "skill-row" }, ...kids);
}

function skillList(skills) {
    if (skills.length <= SKILL_SHOW_FIRST) return el("ul", { className: "skill-list" }, ...skills.map(skillRow));
    const rest = skills.slice(SKILL_SHOW_FIRST);
    return el("div", { className: "stack-sm" },
        el("ul", { className: "skill-list" }, ...skills.slice(0, SKILL_SHOW_FIRST).map(skillRow)),
        disclosure(`Show ${rest.length} more`, el("ul", { className: "skill-list" }, ...rest.map(skillRow))));
}

function skillRulesNote(rules) {
    const w = rules.weights;
    const pc = (value) => `${Math.round(value * 100)}%`;
    return disclosure("How this is worked out",
        el("p", { className: "muted", text: `Each pass adds confidence: a step check ${pc(w.step_check)}, a test-out ${pc(w.test_out)}, a scenario ${pc(w.scenario)}, a coding problem ${pc(w.code)}. Passes combine, so more evidence means more confidence.` }),
        el("p", { className: "muted", text: `A tool (like Python) counts as verified at ${pc(rules.verified_at.tool)}. A concept (like Caching) needs ${pc(rules.verified_at.concept)}, which takes two separate pieces of evidence. Skills only on your resume are claims until you pass something that covers them.` }));
}

function skillsCard(data) {
    const all = (data && data.skills) || [];
    const verified = all.filter((s) => s.status === "verified");
    const progress = all.filter((s) => s.status === "in_progress");
    const unverified = all.filter((s) => s.status === "unverified");
    const kids = [
        el("div", { className: "cluster between" },
            el("h2", { className: "h3", id: "skills-title", text: "Your skills" }),
            el("span", { className: `chip ${verified.length ? "chip-ink" : "chip-line"}`, text: `${verified.length} verified` })),
    ];
    if (!all.length) {
        kids.push(el("p", { className: "muted", text: "No skills yet. Pass a roadmap step check or a scenario to verify your first skill, or analyze your resume to list the skills you already claim." }));
    }
    if (verified.length) kids.push(skillList(verified));
    else if (all.length) kids.push(el("p", { className: "muted", text: "Nothing verified yet. Pass a step check, a scenario or a coding problem that covers a skill to verify it." }));
    if (progress.length) {
        kids.push(el("div", { className: "stack-sm" }, el("h3", { className: "skill-sub", text: "In progress" }), skillList(progress)));
    }
    if (unverified.length) {
        kids.push(el("div", { className: "stack-sm" },
            el("h3", { className: "skill-sub", text: "On your resume, not yet verified" }),
            el("ul", { className: "chips" }, ...unverified.map((s) => el("li", { className: "chip chip-line", text: s.skill })))));
    }
    if (data && data.rules) kids.push(skillRulesNote(data.rules));
    return el("section", { className: "card card-pad stack skills-card", "aria-labelledby": "skills-title" }, ...kids);
}
