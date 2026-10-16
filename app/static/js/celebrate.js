// The roadmap-complete moment: a banner on a finished roadmap and a congratulations dialog the moment the last
// step is ticked (and again from the banner). Uses el() from ui.js and formatDate() from results.js; text only,
// no HTML strings. The confetti is decorative and is left out when the student prefers reduced motion.

function _celebrateMedal(size) {
    const s = String(size);
    return svgEl("svg", { class: "rc-medal", width: s, height: s, viewBox: "0 0 64 64", "aria-hidden": "true", focusable: "false" },
        svgEl("path", { d: "M20 4h10l6 18h-10Z", fill: "#151C4F" }),
        svgEl("path", { d: "M44 4H34l-6 18h10Z", fill: "#262F78" }),
        svgEl("circle", { cx: "32", cy: "40", r: "20", fill: "#F6E84B", stroke: "#151C4F", "stroke-width": "3" }),
        svgEl("circle", { cx: "32", cy: "40", r: "14", fill: "none", stroke: "#151C4F", "stroke-width": "1.5", "stroke-dasharray": "2 3" }),
        svgEl("path", { d: "M24.5 40.5 30 46l10-12", fill: "none", stroke: "#151C4F", "stroke-width": "3.5", "stroke-linecap": "round", "stroke-linejoin": "round" })
    );
}

function _daysBetween(fromIso, toIso) {
    const a = new Date(fromIso), b = new Date(toIso);
    if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return null;
    return Math.max(1, Math.round((b - a) / 86400000));
}

function _phaseCount(steps) {
    return Array.isArray(steps) ? 0 : (steps.phases || []).length;
}

function _firstName(name) {
    const first = String(name || "").trim().split(/\s+/)[0];
    return first || "there";
}

// A card shown at the top of a finished roadmap. onOpen re-opens the congratulations dialog.
function roadmapCompleteBanner(roadmap, onOpen) {
    const when = formatDate(roadmap.completed_on);
    const btn = el("button", { type: "button", className: "btn btn-secondary btn-sm", text: "See your achievement" });
    btn.addEventListener("click", onOpen);
    return el("section", { className: "card rc-banner", "aria-labelledby": "rc-banner-title" },
        _celebrateMedal(44),
        el("div", { className: "rc-banner-text" },
            el("h2", { className: "rc-banner-title", id: "rc-banner-title", text: "Roadmap complete" }),
            el("p", { className: "muted", text: `All ${roadmap.total_steps} steps done${when ? `, finished ${when}` : ""}.` })
        ),
        btn
    );
}

function _confetti() {
    const colours = ["#151C4F", "#F6E84B", "#E8ECF8", "#262F78", "#B3122F", "#F6E84B"];
    const layer = el("div", { className: "rc-confetti", "aria-hidden": "true" });
    for (let i = 0; i < 48; i++) {
        const piece = el("span");
        piece.style.left = `${(i * 37) % 100}%`;
        piece.style.background = colours[i % colours.length];
        piece.style.animationDelay = `${(i % 12) * 0.07}s`;
        piece.style.animationDuration = `${2.2 + (i % 5) * 0.25}s`;
        piece.style.setProperty("--rc-drift", `${((i * 53) % 80) - 40}px`);
        piece.style.setProperty("--rc-spin", `${(i % 2 ? 1 : -1) * (360 + (i * 29) % 360)}deg`);
        layer.append(piece);
    }
    return layer;
}

// The congratulations dialog. info: {name, path, totalSteps, steps, createdAt, completedOn}.
function openRoadmapCelebration(info) {
    const existing = document.getElementById("rc-dialog");
    if (existing) existing.remove();

    const days = info.createdAt && info.completedOn ? _daysBetween(info.createdAt, info.completedOn) : null;
    const phases = _phaseCount(info.steps);
    const stat = (value, label) => el("div", { className: "rc-stat" },
        el("p", { className: "rc-stat-num num", text: String(value) }), el("p", { className: "rc-stat-label", text: label }));
    const stats = [stat(info.totalSteps, info.totalSteps === 1 ? "Step completed" : "Steps completed")];
    if (phases) stats.push(stat(phases, phases === 1 ? "Phase" : "Phases"));
    if (days) stats.push(stat(days, days === 1 ? "Day" : "Days"));

    const next = (href, title, text) => el("li", {},
        el("a", { href, className: "rc-next-link" }, el("strong", { text: title }), el("span", { className: "muted", text })));

    const closeBtn = el("button", { type: "button", className: "btn btn-secondary", text: "Close" });
    const dialog = el("dialog", { className: "rc-dialog", id: "rc-dialog", "aria-labelledby": "rc-title", "aria-describedby": "rc-lead" },
        window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "" : _confetti(),
        el("div", { className: "rc-body stack-sm" },
            _celebrateMedal(88),
            el("p", { className: "eyebrow", text: "Roadmap complete" }),
            el("h2", { className: "rc-title", id: "rc-title", tabindex: "-1", text: `Congratulations, ${_firstName(info.name)}!` }),
            el("p", { className: "rc-lead", id: "rc-lead",
                text: `You have completed every step of your ${info.path} roadmap. That takes steady, consistent work, and it shows.` }),
            el("div", { className: "rc-stats" }, ...stats),
            el("h3", { className: "rc-next-title", text: "Keep the momentum going" }),
            el("ol", { className: "rc-next" },
                next("/scenarios", "Prove it in scenarios", "Real-world problems and coding questions for your path."),
                next("/dashboard", "Check your placement readiness", "See how this progress moves your readiness score."),
                next("/resume", "Update your resume", "Add what you learned and re-run the analysis.")
            ),
            el("div", { className: "actions rc-actions" },
                el("a", { className: "btn", href: "/scenarios", text: "Practise scenarios" }),
                closeBtn
            )
        )
    );
    closeBtn.addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => dialog.remove());
    // A click on the backdrop (outside the panel) closes it too.
    dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
    document.body.append(dialog);
    if (typeof dialog.showModal === "function") {
        dialog.showModal();
    } else {
        dialog.setAttribute("open", "");
    }
    document.getElementById("rc-title").focus();
}
