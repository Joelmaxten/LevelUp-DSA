// Renderers for saved results, shared by the dashboard and the individual pages
// (conversation, roadmap, resume) so a result looks the same wherever it's shown.
// Loaded via a plain <script> tag after ui.js (uses el()); everything is a global.

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

// [ "top match" card, "all paths ranked" card ] for a career_ranking list.
function rankingCards(ranking) {
    const top = ranking[0];
    const maxPct = Math.max(...ranking.map((r) => r.confidence_pct)) || 1;

    const rows = ranking.map((r, i) => {
        const fill = el("div", { className: "rank-fill" });
        fill.style.width = `${(r.confidence_pct / maxPct) * 100}%`;
        return el("li", { className: "rank-row" },
            el("div", { className: "rank-label" },
                el("span", { text: `${i + 1}. ${r.career_path}` }),
                el("span", { className: "muted", text: `${r.confidence_pct}%` })
            ),
            el("div", { className: "rank-track" }, fill)
        );
    });

    return [
        el("div", { className: "card card-highlight" },
            el("p", { className: "muted", text: "Your top match" }),
            el("h3", { text: top.career_path, style: "font-size: 1.5rem; margin: 0.25rem 0;" }),
            el("p", { className: "muted", text: `${top.confidence_pct}% confidence` })
        ),
        el("div", { className: "card" },
            el("h3", { text: "All career paths, ranked", style: "margin-bottom: 1rem;" }),
            el("ol", { className: "rank-list" }, ...rows)
        ),
    ];
}

// A card listing {question, answer} pairs - the conversation answers behind a profile.
function answersCard(title, items) {
    return el("div", { className: "card" },
        el("h3", { text: title, style: "margin-bottom: 1rem;" }),
        el("dl", {}, ...items.map((item) =>
            el("div", { className: "recap-item" },
                el("dt", { text: item.question }),
                el("dd", { text: item.answer })
            )
        ))
    );
}

// ---------- roadmap ----------

function isSafeUrl(url) {
    return typeof url === "string" && /^https?:\/\//i.test(url);
}

// videosPending: a "Finding a video..." placeholder is shown for steps that don't have a video result yet.
function roadmapStep(step, index, videosPending) {
    const body = el("div", { className: "step-body" },
        el("h3", { text: step.title || `Step ${index + 1}` }),
        el("p", { className: "muted", text: step.description || "" })
    );

    if ("resource" in step) {
        if (step.resource && isSafeUrl(step.resource.url)) {
            body.append(el("a", {
                className: "video-link",
                href: step.resource.url,
                target: "_blank",
                rel: "noopener noreferrer",
                text: `▶ ${step.resource.title || step.resource.url}`,
            }));
        } else {
            body.append(el("p", { className: "muted", text: "No video found for this step.", style: "margin-top: 0.75rem; font-size: 0.9rem;" }));
        }
    } else if (videosPending) {
        body.append(el("p", { className: "muted", text: "Finding a video...", role: "status", style: "margin-top: 0.75rem; font-size: 0.9rem;" }));
    }

    return el("li", { className: "card step-card" },
        el("div", { className: "step-number", text: String(step.step_number ?? index + 1) }),
        body
    );
}

function roadmapStepList(steps, videosPending) {
    return el("ol", { className: "step-list" }, ...steps.map((step, i) => roadmapStep(step, i, videosPending)));
}

// A roadmap only counts as "fully resourced" once every step has a "resource" key
// (its value may be null = searched but nothing found).
function hasAllVideoResults(steps) {
    return steps.every((step) => "resource" in step);
}

// ---------- resume analysis ----------

function chips(skills, extraClass) {
    return el("ul", { className: "chip-list" },
        ...skills.map((skill) => el("li", { className: `chip ${extraClass || ""}`.trim(), text: skill }))
    );
}

function skillsCard(data) {
    const matched = data.matched_skills;
    const missing = data.missing_skills;
    const total = matched.length + missing.length;
    const matchedSet = new Set(matched);
    const others = data.student_skills.filter((s) => !matchedSet.has(s));

    const card = el("div", { className: "card section-card" }, el("h3", { text: "Skills match" }));

    if (total === 0) {
        card.append(el("p", { className: "muted", text: "There isn't enough data yet to benchmark required skills for this career path." }));
    } else {
        const fill = el("div", { className: "rank-fill" });
        fill.style.width = `${(matched.length / total) * 100}%`;
        card.append(
            el("p", { text: `You have ${matched.length} of the ${total} skills most commonly used in this career path.` }),
            el("div", { className: "rank-track", style: "margin-top: 0.5rem;" }, fill)
        );
    }

    card.append(el("h4", { text: "Skills you already have" }));
    card.append(matched.length ? chips(matched, "chip-match") : el("p", { className: "muted", text: "None of the commonly required skills were found in your resume." }));

    if (total > 0) {
        card.append(el("h4", { text: "Skills to learn next" }));
        card.append(missing.length ? chips(missing, "chip-missing") : el("p", { className: "muted", text: "You cover all of them. Nice work." }));
    }

    if (others.length) {
        card.append(el("h4", { text: "Other skills we found" }), chips(others));
    }
    return card;
}

function atsCard(ats) {
    // ats is null when the score couldn't be recomputed for a saved analysis
    // (the original PDF is no longer on the server, or can't be read any more).
    if (!ats) {
        return el("div", { className: "card section-card" },
            el("h3", { text: "ATS friendliness" }),
            el("p", { className: "muted", text: "This score can't be shown for a saved analysis because the original PDF is no longer available. Upload the resume again to get a fresh score." })
        );
    }

    const band = ats.score >= 80 ? "score-good" : ats.score >= 60 ? "score-ok" : "score-low";
    return el("div", { className: "card section-card" },
        el("h3", { text: "ATS friendliness" }),
        el("p", {},
            el("span", { className: `score-big ${band}`, text: String(ats.score) }),
            el("span", { className: "muted", text: " / 100" })
        ),
        el("p", { className: "muted", style: "font-size: 0.9rem; margin-top: 0.5rem;", text: "A lightweight check of how easily an applicant-tracking system can read your resume. It is not a full layout analysis." }),
        el("ul", { className: "plain-list", style: "margin-top: 1rem;" },
            ...ats.reasons.map((reason) => el("li", { text: reason }))
        )
    );
}

function salaryBlock(title, note, stats, formatter) {
    const block = el("div", { style: "margin-top: 1rem;" },
        el("h4", { text: title, style: "margin-top: 0;" })
    );
    if (!stats) {
        block.append(el("p", { className: "muted", text: "No data available for this career path." }));
        return block;
    }
    const s = formatter(stats);
    block.append(
        el("div", { className: "stat-grid" },
            el("div", {}, el("div", { className: "stat-label", text: "Median" }), el("div", { className: "stat-value", text: s.median })),
            el("div", {}, el("div", { className: "stat-label", text: "Range" }), el("div", { className: "stat-value", text: `${s.min} – ${s.max}` })),
            el("div", {}, el("div", { className: "stat-label", text: "Based on" }), el("div", { className: "stat-value", text: `${stats.count} ${stats.count === 1 ? "entry" : "entries"}` }))
        ),
        el("p", { className: "muted", style: "font-size: 0.9rem;", text: note })
    );
    return block;
}

function salaryCard(insights) {
    const card = el("div", { className: "card section-card" },
        el("h3", { text: "Salary expectations (per year)" })
    );

    // The two sources are shown separately on purpose: job postings skew toward
    // freshers, survey respondents are working developers - averaging them
    // would blend two different populations.
    card.append(
        salaryBlock(
            "Job postings in India",
            "Real listings, skewing toward fresher and entry-level roles.",
            insights.job_postings,
            (st) => ({ median: formatInr(st.median), min: formatInr(st.min), max: formatInr(st.max) })
        ),
        salaryBlock(
            "Developer survey, India",
            "Self-reported by working developers, so usually higher. Converted from USD at an approximate rate; the median is more reliable than the extremes.",
            insights.survey_respondents,
            (st) => ({
                median: `~${formatInr(st.approx_inr.median)}`,
                min: `~${formatInr(st.approx_inr.min)}`,
                max: `~${formatInr(st.approx_inr.max)}`,
            })
        )
    );

    if (insights.survey_respondents) {
        const sr = insights.survey_respondents;
        card.append(el("p", { className: "muted", style: "font-size: 0.85rem; margin-top: 0.5rem;", text: `Survey figures in USD: median ${formatUsd(sr.median)}, range ${formatUsd(sr.min)} – ${formatUsd(sr.max)}.` }));
    }

    if (insights.sample_listings.length) {
        card.append(
            el("h4", { text: "Sample job postings" }),
            el("ul", { className: "plain-list" },
                ...insights.sample_listings.map((job) =>
                    el("li", { text: `${job.job_title} — ${job.location || "location not listed"} — ${formatInr(job.annual_salary)}` })
                )
            )
        );
    }
    return card;
}

const FEEDBACK_HEADERS = ["Resume Suggestions", "30-Day Action Plan", "Keyword Suggestions"];

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

function feedbackCards(feedback) {
    if (!feedback) {
        return [el("div", { className: "card section-card" },
            el("h3", { text: "AI feedback" }),
            el("p", { className: "muted", text: "AI feedback isn't available for this analysis because the AI service didn't respond at the time. The skill analysis was still saved. Upload your resume again later to get feedback." })
        )];
    }

    const clean = (t) => t.replace(/\*\*/g, "").trim();
    const sections = parseFeedback(feedback);
    if (!sections) {
        return [el("div", { className: "card section-card" },
            el("h3", { text: "AI feedback" }),
            el("p", { className: "feedback-text", text: clean(feedback) })
        )];
    }
    return sections.map((s) => el("div", { className: "card section-card" },
        el("h3", { text: s.title }),
        el("p", { className: "feedback-text", text: clean(s.lines.join("\n")) })
    ));
}

// Everything in a resume analysis except the page-specific header and buttons.
function resumeAnalysisCards(data) {
    return [
        skillsCard(data),
        atsCard(data.ats_score),
        salaryCard(data.salary_insights),
        ...feedbackCards(data.ai_feedback),
    ];
}
