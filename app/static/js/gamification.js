// Gamification pieces shared by the dashboard and the scenarios page: the level card, the compact level bar,
// the badge grid and the reward card shown after a scenario is submitted.
// Globals from ui.js: el, svgEl, pbar, icon. All text goes through el() / textContent only, so no markup is injected.
// The numbers come from GET /gamification (or a submit's "rewards"); the rules live in app/pipeline/gamification.py.

function gamStreakText(streak) {
    if (!streak || !streak.current) return "No streak yet";
    return `${streak.current}-day streak`;
}

function gamNextText(level) {
    if (level.next_at === null) return "Top level reached";
    return `${level.next_at - level.xp} XP to ${level.next_title}`;
}

// A small medal: a ribbon and a disc. Decorative; the badge name next to it carries the meaning.
function gamMedal(earned) {
    return svgEl("svg", { class: `gam-medal${earned ? " is-earned" : ""}`, viewBox: "0 0 32 32", "aria-hidden": "true", focusable: "false" },
        svgEl("path", { d: "M10 2h5l3 9h-5zM17 2h5l-3 9h-5z", fill: "currentColor", opacity: "0.55" }),
        svgEl("circle", { cx: "16", cy: "20", r: "9", fill: earned ? "currentColor" : "none", stroke: "currentColor", "stroke-width": "2.5" }),
        earned ? svgEl("path", { d: "M12 20.5l3 3 5-6", fill: "none", stroke: "var(--surface)", "stroke-width": "2.5", "stroke-linecap": "round", "stroke-linejoin": "round" }) : "");
}

// Full card for the dashboard: level and title, XP bar to the next level, streak, badges earned.
function gamLevelCard(g) {
    const lv = g.level;
    const stats = [
        el("li", { className: "chip chip-ink", text: `${g.xp} XP` }),
        el("li", { className: `chip ${g.streak.current ? "chip-ink" : "chip-line"}`, text: gamStreakText(g.streak) }),
        el("li", { className: "chip", text: `Best streak ${g.streak.best} day${g.streak.best === 1 ? "" : "s"}` }),
        el("li", { className: "chip", text: `${g.counts.badges_earned} of ${g.counts.badges_total} badges` }),
    ];
    const kids = [
        el("div", { className: "cluster between" },
            el("div", { className: "stack-sm" },
                el("p", { className: "eyebrow", text: `Level ${lv.level}` }),
                el("h2", { className: "h2", id: "gam-title", text: lv.title })),
            el("span", { className: "num gam-xp", text: `${g.xp} XP` })),
        pbar(lv.progress_pct, `${lv.progress_pct}% of the way to ${lv.next_title || "the top"}`, true),
        el("p", { className: "muted", text: gamNextText(lv) }),
        el("ul", { className: "chips" }, ...stats),
    ];
    if (g.streak.current && !g.streak.active_today) {
        kids.push(el("p", { className: "hint", text: "Submit a scenario or tick a roadmap step today to keep your streak going." }));
    }
    return el("section", { className: "card card-pad stack-sm gam-card", "aria-labelledby": "gam-title" }, ...kids);
}

// One line for the top of the scenarios page.
function gamBar(g) {
    return el("div", { className: "card card-pad gam-bar", role: "group", "aria-label": "Your progress" },
        el("p", { className: "gam-bar-title" }, el("strong", { text: `Level ${g.level.level} · ${g.level.title}` })),
        el("div", { className: "gam-bar-meter" }, pbar(g.level.progress_pct, gamNextText(g.level))),
        el("ul", { className: "chips" },
            el("li", { className: "chip chip-ink", text: `${g.xp} XP` }),
            el("li", { className: `chip ${g.streak.current ? "chip-ink" : "chip-line"}`, text: gamStreakText(g.streak) }),
            el("li", { className: "chip", text: `${g.counts.badges_earned}/${g.counts.badges_total} badges` })));
}

// Every badge: earned ones filled, locked ones with how to earn them and progress towards it.
function gamBadgeGrid(badges) {
    return el("ul", { className: "gam-badges" }, ...badges.map((b) => {
        const kids = [gamMedal(b.earned), el("p", { className: "gam-badge-name", text: b.name }), el("p", { className: "gam-badge-how", text: b.how })];
        if (b.earned) {
            kids.push(el("p", { className: "gam-badge-state" }, icon("tick"), el("span", { text: "Earned" })));
        } else if (b.target > 1) {
            const pct = Math.round((100 * b.progress) / b.target);
            kids.push(el("p", { className: "gam-badge-state", text: `${b.progress} of ${b.target}` }), pbar(pct, `${b.name}: ${b.progress} of ${b.target}`));
        } else {
            kids.push(el("p", { className: "gam-badge-state muted", text: "Not earned yet" }));
        }
        return el("li", { className: `gam-badge${b.earned ? " is-earned" : ""}` }, ...kids);
    }));
}

function gamBadgesSection(g) {
    return el("details", { className: "card card-pad gam-badges-card" },
        el("summary", {}, el("span", { className: "h3", text: "Badges" }),
            el("span", { className: "chip chip-ink", text: `${g.counts.badges_earned} of ${g.counts.badges_total}` })),
        gamBadgeGrid(g.badges));
}

// After a submit: XP gained, level-up and new badges. Returns "" when the server sent no rewards.
function gamRewardsCard(r) {
    if (!r) return "";
    const kids = [
        el("p", { className: "gam-gain num", text: r.xp_gained > 0 ? `+${r.xp_gained} XP` : "No new XP" }),
        el("p", { className: "muted", text: r.xp_gained > 0 ? `You now have ${r.xp} XP.` : "XP counts your best score on each scenario, so a lower or equal score adds nothing." }),
    ];
    if (r.leveled_up) {
        kids.push(el("p", { className: "gam-levelup" }, el("strong", { text: `Level up! You are now Level ${r.level.level}: ${r.level.title}.` })));
    } else {
        kids.push(pbar(r.level.progress_pct, gamNextText(r.level)), el("p", { className: "hint", text: `Level ${r.level.level} · ${r.level.title} · ${gamNextText(r.level)}` }));
    }
    if (r.new_badges.length) {
        kids.push(el("h3", { className: "scen-sub", text: r.new_badges.length === 1 ? "New badge" : "New badges" }),
            el("ul", { className: "gam-new-badges" }, ...r.new_badges.map((b) =>
                el("li", { className: "gam-badge is-earned" }, gamMedal(true), el("p", { className: "gam-badge-name", text: b.name }), el("p", { className: "gam-badge-how", text: b.how })))));
    }
    if (r.streak && r.streak.current) kids.push(el("p", { className: "chip chip-ink", text: gamStreakText(r.streak) }));
    return el("section", { className: "card card-pad stack-sm gam-rewards", role: "status", "aria-label": "Rewards" }, ...kids);
}

function gamRewardsAnnouncement(r) {
    if (!r) return "";
    const parts = [];
    if (r.xp_gained > 0) parts.push(`${r.xp_gained} XP gained.`);
    if (r.leveled_up) parts.push(`Level up: ${r.level.title}.`);
    if (r.new_badges.length) parts.push(`New badge${r.new_badges.length > 1 ? "s" : ""}: ${r.new_badges.map((b) => b.name).join(", ")}.`);
    return parts.join(" ");
}
