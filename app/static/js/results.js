// Renderers for saved results, shared by the dashboard and the individual pages
// (quiz, conversation, roadmap, resume) so a result looks the same wherever it's shown.
// Loaded via a plain <script> tag after ui.js (uses el() and row()); everything is a global.
//
// Functions ending in "Rows" return an array of .row elements to place directly in a sheet.
// Functions ending in "Block" return content for the right-hand column of a row.
// `level` is the heading level for row titles, so the page's heading outline stays correct
// (a page's rows are h2 under its h1; the dashboard's are h3 under its section h2s).

// ---------- formatting ----------

function formatDate(iso) {
    const date = new Date(iso);
    if (!iso || Number.isNaN(date.getTime())) return "";
    return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function formatInr(n) {
    if (n === null || n === undefined) return "not listed";
    if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
    if (n >= 1e5) return `₹${(n / 1e5).toFixed(1)} L`;
    return `₹${Math.round(n).toLocaleString("en-IN")}`;
}

function formatUsd(n) {
    return `$${Math.round(n).toLocaleString("en-US")}`;
}

// ---------- career profile ----------

// The top match, set large. confidence_pct is the share of the student's answers that pointed here.
function topMatchBlock(top) {
    return el("div", { className: "top-match" },
        el("p", { className: "top-match-name" }, el("span", { className: "mark", text: top.career_path })),
        el("p", { className: "note", text: `${top.confidence_pct}% of your answers pointed here.` })
    );
}

// Every path in rank order. Rank is genuinely ordered content, so it is numbered.
function meritList(ranking) {
    const max = Math.max(...ranking.map((r) => r.confidence_pct)) || 1;
    return el("ol", { className: "merit" }, ...ranking.map((r, i) => {
        const fill = el("span", { className: "merit-fill" });
        fill.style.width = `${(r.confidence_pct / max) * 100}%`;
        return el("li", { className: `merit-item${i < 3 ? " merit-top" : ""}` },
            el("span", { className: "merit-rank num", text: String(i + 1) }),
            el("span", { className: "merit-name", text: r.career_path }),
            el("span", { className: "merit-pct num", text: `${r.confidence_pct}%` }),
            el("span", { className: "merit-track", "aria-hidden": "true" }, fill)
        );
    }));
}

function rankingRows(ranking, level) {
    const l = level || 2;
    return [
        row(
            [rowTitle("Your career results", l), el("p", { className: "note", text: "The share of your answers that pointed to each path." })],
            el("div", { className: "split split-even-ish" },
                el("div", {},
                    el("p", { className: "note", text: "Your top match" }),
                    topMatchBlock(ranking[0]),
                    el("p", { className: "top-match-next", text: "Your roadmap is built around this path." })
                ),
                el("div", {},
                    el(`h${Math.min(l + 1, 6)}`, { className: "block-title", text: "Every path, ranked" }),
                    meritList(ranking)
                )
            )
        ),
    ];
}

// {question, answer} pairs: the conversation answers behind a profile.
function answersBlock(items) {
    return el("dl", { className: "recap-list" }, ...items.map((item) =>
        el("div", { className: "recap-item" },
            el("dt", { text: item.question }),
            el("dd", { text: item.answer })
        )
    ));
}

function answersRow(title, items, level, note) {
    return row([rowTitle(title, level), note ? el("p", { className: "note", text: note }) : ""], answersBlock(items));
}

// ---------- roadmap ----------

function isSafeUrl(url) {
    return typeof url === "string" && /^https?:\/\//i.test(url);
}

// videosPending: a "Finding a video" placeholder is shown for steps that don't have a video result yet.
// isFirstOverall: true only for the very first step of the whole roadmap (gets the
// "Start here" marker) - not just the first step of whichever phase/list is being
// built, so a phased roadmap only marks one true starting point.
// displayIndex: this step's position within whatever list is currently being built -
// only used as the step-num fallback for an older roadmap that predates
// global_step_index.
// The step number sits on the margin rule, which is what turns the rule into a route.
function roadmapStep(step, displayIndex, videosPending, isFirstOverall) {
    const text = el("div", { className: "step-text" });
    if (isFirstOverall) text.append(el("p", { className: "start-here" }, el("span", { className: "mark", text: "Start here" })));
    text.append(
        el("h3", { className: "step-title", text: step.title || `Step ${displayIndex + 1}` }),
        el("p", { className: "step-desc", text: step.description || "" })
    );

    const grid = el("div", { className: "step-grid" }, text);

    if ("resource" in step) {
        if (step.resource && isSafeUrl(step.resource.url)) {
            grid.append(el("div", { className: "step-aside" },
                el("p", { className: "note", text: "Video for this step" }),
                el("a", {
                    className: "watch",
                    href: step.resource.url,
                    target: "_blank",
                    rel: "noopener noreferrer",
                }, icon("play"), el("span", { text: step.resource.title || step.resource.url }), el("span", { className: "visually-hidden", text: "(opens in a new tab)" }))
            ));
        } else {
            grid.append(el("div", { className: "step-aside" }, el("p", { className: "note", text: "No video found for this step." })));
        }
    } else if (videosPending) {
        grid.append(el("div", { className: "step-aside" }, el("p", { className: "note", text: "Finding a video for this step...", role: "status" })));
    }

    return el("li", { className: `row step${isFirstOverall ? " step-first" : ""}` },
        el("span", { className: "step-num num", text: String(step.global_step_index ?? step.step_number ?? displayIndex + 1), "aria-hidden": "true" }),
        el("div", { className: "margin" }),
        el("div", { className: "main" }, grid)
    );
}

// A phase's own heading row, styled like the rest of the page's section breaks
// (row() keeps it aligned with the steps' margin/main columns and the route spine).
function phaseHeaderRow(phase) {
    return row(
        el("p", { className: "note", text: `Phase ${phase.phase_number}` }),
        el("h3", { className: "phase-title", text: phase.title }),
        "row-head"
    );
}

// steps: either an older roadmap's flat step array, or the current
// {"phases": [{"phase_number", "title", "steps": [...]}]} shape. Always returns one
// node (a plain <ol class="route"> for the flat case, a phase-headed sequence of them
// for the phased case), since callers push this straight into a flat list of parts.
function roadmapStepList(steps, videosPending) {
    if (Array.isArray(steps)) {
        return el("ol", { className: "route" }, ...steps.map((step, i) => roadmapStep(step, i, videosPending, i === 0)));
    }

    const blocks = [];
    let seenAny = false;
    for (const phase of steps.phases) {
        blocks.push(phaseHeaderRow(phase));
        blocks.push(el("ol", { className: "route" }, ...phase.steps.map((step, i) => {
            const isFirstOverall = !seenAny;
            seenAny = true;
            return roadmapStep(step, i, videosPending, isFirstOverall);
        })));
    }
    return el("div", { className: "phases-detail" }, ...blocks);
}

// A compact summary for space-constrained contexts (the dashboard, shown alongside
// several other sections) - phase titles and step counts only, no step-by-step detail,
// since a phased roadmap can run to 20+ steps where the old flat one topped out at 12.
// An older flat-shape roadmap is short enough to just show in full via roadmapStepList.
function roadmapDashboardSummary(steps) {
    if (Array.isArray(steps)) return roadmapStepList(steps, false);

    const totalSteps = steps.phases.reduce((n, phase) => n + phase.steps.length, 0);
    return el("div", { className: "block" },
        el("p", { className: "note", text: `${steps.phases.length} phases, ${totalSteps} steps in total` }),
        el("ul", { className: "dots" }, ...steps.phases.map((phase) =>
            el("li", { text: `${phase.title} — ${phase.steps.length} step${phase.steps.length === 1 ? "" : "s"}` })
        ))
    );
}

// A roadmap only counts as "fully resourced" once every step (across every phase, for
// the current shape) has a "resource" key (its value may be null = searched but nothing found).
function hasAllVideoResults(steps) {
    const allSteps = Array.isArray(steps) ? steps : steps.phases.flatMap((phase) => phase.steps);
    return allSteps.every((step) => "resource" in step);
}

// ---------- resume analysis ----------

function skillChips(skills, kind) {
    return el("ul", { className: "skills" }, ...skills.map((skill) =>
        el("li", { className: `skill skill-${kind}` }, kind === "have" ? icon("tick") : "", el("span", { text: skill }))
    ));
}

// One segment per skill: solid = on the resume, marker = still to learn. Makes the gap countable.
function gaugeFor(matchedCount, missingCount) {
    const total = matchedCount + missingCount;
    const gauge = el("div", {
        className: total > 16 ? "gauge gauge-dense" : "gauge",
        role: "img",
        "aria-label": `${matchedCount} of ${total} skills found on your resume`,
    });
    for (let i = 0; i < total; i++) {
        const cell = el("i", { className: i < matchedCount ? "have" : "gap" });
        cell.style.setProperty("--i", String(i));
        gauge.append(cell);
    }
    return gauge;
}

function skillsRow(data, level) {
    const matched = data.matched_skills;
    const missing = data.missing_skills;
    const total = matched.length + missing.length;
    const matchedSet = new Set(matched);
    const others = data.student_skills.filter((s) => !matchedSet.has(s));

    const main = [];

    if (total === 0) {
        main.push(el("p", { text: "There isn't enough data yet to benchmark the skills this career path needs." }));
    } else {
        main.push(
            el("p", { className: "stat-sentence" },
                el("span", { className: "big-num num", text: `${matched.length} of ${total}` }),
                ` of the skills most used in this career path are already on your resume.`
            ),
            gaugeFor(matched.length, missing.length)
        );
    }

    const groups = [el("div", { className: "block" },
        el("h3", { className: "block-title", text: "Already on your resume" }),
        matched.length ? skillChips(matched, "have") : el("p", { className: "note", text: "None of the commonly needed skills were found in your resume." })
    )];

    if (total > 0) {
        groups.push(el("div", { className: "block" },
            el("h3", { className: "block-title", text: "Learn these next" }),
            missing.length ? skillChips(missing, "gap") : el("p", { text: "You cover all of them. Nice work." })
        ));
    }

    if (others.length) {
        groups.push(el("div", { className: "block" },
            el("h3", { className: "block-title", text: "Other skills we found" }),
            skillChips(others, "extra")
        ));
    }
    main.push(el("div", { className: "skill-cols" }, ...groups));

    return row(
        [rowTitle("Skills match", level), el("p", { className: "note", text: "Compared with the skills most used for this career path." })],
        main
    );
}

function atsRow(ats, level) {
    const margin = [
        rowTitle("ATS friendliness", level),
        el("p", { className: "note", text: "A lightweight check of how easily an applicant tracking system can read your resume. It is not a full layout analysis." }),
    ];

    // ats is null when the score couldn't be recomputed for a saved analysis
    // (the original PDF is no longer on the server, or can't be read any more).
    if (!ats) {
        return row(margin, el("p", { text: "This score can't be shown for a saved analysis because the original PDF is no longer available. Upload the resume again to get a fresh score." }));
    }

    const band = ats.score >= 80
        ? { text: "Reads well to most systems.", low: false }
        : ats.score >= 60
            ? { text: "Readable, with room to improve.", low: false }
            : { text: "Needs work before you send it out.", low: true };

    const fill = el("span", { className: "scale-fill" });
    fill.style.display = "block";
    fill.style.width = `${Math.max(0, Math.min(100, ats.score))}%`;
    const tick = (label, at, cls) => {
        const t = el("span", { text: label, className: cls || "" });
        if (!cls) t.style.left = `${at}%`;
        return t;
    };

    return row(margin, el("div", { className: "split split-even-ish" },
        el("div", {},
            el("p", { className: "score" },
                el("span", { className: "score-num num", text: String(ats.score) }),
                el("span", { className: "score-of", text: "out of 100" })
            ),
            el("p", { className: `score-band${band.low ? " score-band-low" : ""}`, text: band.text }),
            el("div", { className: "scale", "aria-hidden": "true" }, fill),
            el("div", { className: "scale-ticks", "aria-hidden": "true" },
                tick("0", 0, "at-start"), tick("60", 60), tick("80", 80), tick("100", 100, "at-end")
            )
        ),
        el("div", {},
            el(`h${Math.min((level || 2) + 1, 6)}`, { className: "block-title", text: "What we found" }),
            el("ul", { className: "dots" }, ...ats.reasons.map((reason) => el("li", { text: reason })))
        )
    ));
}

function salaryColumn(title, note, stats, formatter) {
    const col = el("div", {}, el("h3", { className: "block-title", text: title }));
    if (!stats) {
        col.append(el("p", { className: "note", text: "No data available for this career path." }));
        return col;
    }
    const s = formatter(stats);
    col.append(
        el("p", { className: "figure-label", text: "Median per year" }),
        el("p", { className: "figure num", text: s.median }),
        el("dl", { className: "facts" },
            el("dt", { text: "Range" }), el("dd", { text: `${s.min} to ${s.max}` }),
            el("dt", { text: "Based on" }), el("dd", { text: `${stats.count} ${stats.count === 1 ? "entry" : "entries"}` })
        ),
        el("p", { className: "note", text: note })
    );
    return col;
}

function salaryRow(insights, level) {
    // The two sources are shown separately on purpose: job postings skew toward
    // freshers, survey respondents are working developers. Averaging them
    // would blend two different populations.
    const main = [
        el("div", { className: "cols" },
            salaryColumn(
                "Job postings in India",
                "Real listings, skewing toward fresher and entry-level roles.",
                insights.job_postings,
                (st) => ({ median: formatInr(st.median), min: formatInr(st.min), max: formatInr(st.max) })
            ),
            salaryColumn(
                "Developer survey, India",
                "Self-reported by working developers, so usually higher. Converted from USD at an approximate rate; trust the median more than the extremes.",
                insights.survey_respondents,
                (st) => ({
                    median: `~${formatInr(st.approx_inr.median)}`,
                    min: `~${formatInr(st.approx_inr.min)}`,
                    max: `~${formatInr(st.approx_inr.max)}`,
                })
            )
        ),
    ];

    if (insights.survey_respondents) {
        const sr = insights.survey_respondents;
        main.push(el("p", { className: "note survey-usd", text: `Survey figures in USD: median ${formatUsd(sr.median)}, range ${formatUsd(sr.min)} to ${formatUsd(sr.max)}.` }));
    }

    if (insights.sample_listings.length) {
        main.push(el("div", { className: "block" },
            el("h3", { className: "block-title", text: "Sample job postings" }),
            el("ul", { className: "listings" }, ...insights.sample_listings.map((job) =>
                el("li", { className: "listing" },
                    el("span", {}, job.job_title, el("span", { className: "listing-where", text: job.location || "Location not listed" })),
                    el("span", { className: "num", text: formatInr(job.annual_salary) })
                )
            ))
        ));
    }

    return row(
        [rowTitle("Salary expectations", level), el("p", { className: "note", text: "Per year, from two separate sources." })],
        main
    );
}

const FEEDBACK_HEADERS = ["Resume Suggestions", "30-Day Action Plan", "Keyword Suggestions"];
const FEEDBACK_TITLES = {
    "Resume Suggestions": "Resume suggestions",
    "30-Day Action Plan": "30-day action plan",
    "Keyword Suggestions": "Keyword suggestions",
};

// The LLM is asked for exactly these three plain-text headers. Split on them
// when all three are present; otherwise the caller falls back to one block.
function parseFeedback(text) {
    const sections = [];
    let current = null;
    for (const line of text.split("\n")) {
        const cleaned = line.replace(/[*#]/g, "").replace(/^\s*\d+[.)]\s*/, "").replace(/:\s*$/, "").trim();
        const header = FEEDBACK_HEADERS.find((h) => h.toLowerCase() === cleaned.toLowerCase());
        if (header) {
            current = { title: header, lines: [] };
            sections.push(current);
        } else if (current) {
            current.lines.push(line);
        }
    }
    return sections.length === FEEDBACK_HEADERS.length ? sections : null;
}

function feedbackRows(feedback, level) {
    if (!feedback) {
        return [row(
            rowTitle("Feedback", level),
            el("p", { text: "Written feedback isn't available for this analysis because the AI service didn't respond at the time. Your skill analysis was still saved. Upload your resume again later to get feedback." })
        )];
    }

    const clean = (t) => t.replace(/\*\*/g, "").trim();
    const sections = parseFeedback(feedback);
    if (!sections) {
        return [row(rowTitle("Feedback", level), el("p", { className: "prose", text: clean(feedback) }))];
    }
    const columns = sections.map((sec) => {
        // The action plan is the thing to do next, so it gets the marker.
        const heading = el(`h${Math.min((level || 2) + 1, 6)}`, { className: "block-title" });
        heading.append(sec.title === "30-Day Action Plan"
            ? el("span", { className: "mark", text: FEEDBACK_TITLES[sec.title] })
            : FEEDBACK_TITLES[sec.title]);
        return el("div", {}, heading, el("p", { className: "prose", text: clean(sec.lines.join("\n")) }));
    });
    return [row(
        [rowTitle("Feedback", level), el("p", { className: "note", text: "Written by an AI from the text of your resume. Treat it as a starting point." })],
        el("div", { className: "split split-feedback" }, ...columns)
    )];
}

// Everything in a resume analysis except the page-specific header and buttons.
function resumeAnalysisRows(data, level) {
    return [
        skillsRow(data, level),
        atsRow(data.ats_score, level),
        salaryRow(data.salary_insights, level),
        ...feedbackRows(data.ai_feedback, level),
    ];
}
