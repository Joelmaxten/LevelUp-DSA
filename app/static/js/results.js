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

// Several paths that share the top score, shown together instead of one arbitrary winner.
function tiedTopBlock(tiedPaths, ranking) {
    const byPath = new Map(ranking.map((r) => [r.career_path, r]));
    return el("div", { className: "top-match top-match-tied" },
        el("ul", { className: "tied-list" }, ...tiedPaths.map((path) =>
            el("li", { className: "top-match-name" }, el("span", { className: "mark", text: path }))
        )),
        el("p", { className: "note", text: `${byPath.get(tiedPaths[0]).confidence_pct}% of your answers pointed to each of them.` })
    );
}

// tiedTop (optional): the quiz's list of paths that share the top score. With more than one, the
// top is shown as "Your top matches"; without it (or with one path) the page is exactly as before.
function rankingRows(ranking, level, tiedTop) {
    const l = level || 2;
    const tied = Array.isArray(tiedTop) && tiedTop.length > 1;
    return [
        row(
            [rowTitle("Your career results", l), el("p", { className: "note", text: "The share of your answers that pointed to each path." })],
            el("div", { className: "split split-even-ish" },
                tied
                ? el("div", {},
                    el("p", { className: "note", text: "Your top matches" }),
                    tiedTopBlock(tiedTop, ranking),
                    el("p", { className: "top-match-next", text: "These paths scored the same on your answers. You will choose between them when you build your roadmap." })
                )
                : el("div", {},
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

// https only (not http) - every URL this page links out to (a video, a KB
// resource link) is either built by our own backend from a validated
// YouTube video id (always https://youtube.com/...) or filtered to https
// already by youtube_resources.py before it ever reaches the client, so
// this is a defense-in-depth check, not expected to reject real data.
function isSafeUrl(url) {
    return typeof url === "string" && /^https:\/\//i.test(url);
}

// Small chip list for a step's subtopics - plain text only, no links.
function subtopicChips(subtopics) {
    if (!subtopics || !subtopics.length) return "";
    return el("ul", { className: "chips step-subtopics" }, ...subtopics.map((s) => el("li", { className: "chip", text: s })));
}

// Up to 4 video links, shown directly (not collapsed) - a "search result" tag
// marks a youtube_search-sourced video; a roadmap.sh-sourced one gets no tag,
// since that's the common/expected case and doesn't need calling out.
function videosBlock(videos) {
    if (!videos || !videos.length) {
        return el("p", { className: "note", text: "No videos found for this step." });
    }
    return el("ul", { className: "watch-list" }, ...videos.slice(0, 4).map((v) => {
        const items = [];
        if (isSafeUrl(v.url)) {
            items.push(el("a", { className: "watch", href: v.url, target: "_blank", rel: "noopener noreferrer" },
                icon("play"),
                el("span", { text: v.title || v.url }),
                el("span", { className: "visually-hidden", text: "(opens in a new tab)" })
            ));
        } else {
            items.push(el("span", { className: "watch", text: v.title || "Video" }));
        }
        if (v.source === "youtube_search") items.push(el("span", { className: "tag tag-search", text: "search result" }));
        return el("li", { className: "watch-item" }, ...items);
    }));
}

// A project's grounded flag says whether it came from roadmap.sh's own
// curated project material (true) or is the model's own suggestion (false) -
// see roadmap_generator.py's _project_instructions.
function projectsBlock(projects) {
    if (!projects || !projects.length) return "";
    return el("div", { className: "step-projects" },
        el("p", { className: "note", text: "Projects" }),
        el("ul", { className: "projects" }, ...projects.map((p) => el("li", { className: "project" },
            el("p", { className: "project-title", text: p.title || "" }),
            p.description ? el("p", { className: "project-desc", text: p.description }) : "",
            el("div", { className: "project-badges" },
                p.difficulty ? el("span", { className: "badge badge-difficulty", text: p.difficulty }) : "",
                el("span", {
                    className: `badge ${p.grounded ? "badge-grounded" : "badge-suggested"}`,
                    text: p.grounded ? "from roadmap.sh" : "suggested",
                })
            )
        )))
    );
}

// Collapsed by default. A type label (official/course) sits on each link.
function resourcesDetails(resources) {
    if (!resources || !resources.length) return "";
    const details = el("details", { className: "step-resources" });
    details.append(
        el("summary", { text: `Docs and courses (${resources.length})` }),
        el("ul", { className: "resource-list" }, ...resources.map((r) => {
            const linkContent = [el("span", { className: "tag tag-type", text: r.type || "" })];
            linkContent.push(isSafeUrl(r.url)
                ? el("a", { href: r.url, target: "_blank", rel: "noopener noreferrer", text: r.title || r.url })
                : el("span", { text: r.title || "Resource" }));
            return el("li", { className: "resource-item" }, ...linkContent);
        }))
    );
    return details;
}

// Collapsed by default, and its list is built lazily on the FIRST toggle-open
// (not at initial render) - a step can have dozens of more_topics entries, and
// most students will never open this, so there's no reason to build that much
// DOM for every step up front.
function moreTopicsDetails(moreTopics) {
    if (!moreTopics || !moreTopics.length) return "";
    const details = el("details", { className: "step-more-topics" });
    const body = el("div", { className: "more-topics-body" });
    let built = false;
    details.addEventListener("toggle", () => {
        if (built || !details.open) return;
        built = true;
        body.append(el("ul", { className: "topic-list" }, ...moreTopics.map((t) => el("li", { text: t.title }))));
    });
    details.append(
        el("summary", { text: `Also covered in this step (${moreTopics.length} topic${moreTopics.length === 1 ? "" : "s"})` }),
        body
    );
    return details;
}

// Mirrors routes/roadmap.py's step_indexes(): phased shape -> each step's
// global_step_index; flat shape -> each step's step_number. A step missing
// that key falls back to its 1-based position across the WHOLE roadmap
// (not per-phase) - same fallback rule, in the same iteration order, so a
// checkbox's stepIndex always matches what POST /roadmap/<id>/progress
// will validate server-side.
function computeStepIndexes(steps) {
    if (Array.isArray(steps)) {
        return steps.map((step, i) => step.global_step_index ?? step.step_number ?? i + 1);
    }
    const flatSteps = steps.phases.flatMap((phase) => phase.steps);
    return flatSteps.map((step, i) => step.global_step_index ?? step.step_number ?? i + 1);
}

// A tiny stateful progress bar: label + thin fill, rewritten in place by
// update(done, total) rather than rebuilt by the caller each time - used
// for the overall bar, each phase's compact bar, and the dashboard's
// read-only summary bar. formatText(done, total, pct) returns the label.
function makeProgressBar(formatText) {
    const container = el("div", { className: "progress-bar-block" });
    function update(done, total) {
        const pct = total > 0 ? Math.round((done / total) * 100) : 0;
        const fill = el("span", { className: "progress-bar-fill" });
        fill.style.width = `${pct}%`;
        container.replaceChildren(
            el("p", { className: "note progress-bar-label", text: formatText(done, total, pct) }),
            el("div", { className: "progress-bar", role: "img", "aria-label": formatText(done, total, pct) }, fill)
        );
    }
    return [container, update];
}

// Fills an already-rendered step's empty .step-check placeholder with a
// real checkbox + visually-hidden label + inline error slot, and wires its
// optimistic-update / revert-on-failure behavior. stepProgress:
// {roadmapId, completed: Set, onToggle, stepIndex, refreshBars} - the
// first three come straight from roadmapStepList's optional third
// argument; stepIndex and refreshBars are computed per-step by
// roadmapStepList itself (see there). liEl: this step's own <li>, so its
// "step-done" class (muted title + check mark, via CSS) can be toggled
// live, not just at initial render.
function wireStepCheckbox(checkSlot, stepProgress, liEl) {
    const { completed, onToggle, stepIndex, roadmapId } = stepProgress;
    const checkboxId = `step-check-${roadmapId}-${stepIndex}`;
    const checkbox = el("input", { type: "checkbox", id: checkboxId });
    checkbox.checked = completed.has(stepIndex);
    const label = el("label", { className: "visually-hidden", for: checkboxId, text: `Mark step ${stepIndex} done` });
    const error = el("p", { className: "step-check-error", role: "alert" });
    error.hidden = true;

    let inFlight = false;
    checkbox.addEventListener("change", async () => {
        if (inFlight) return;
        inFlight = true;
        checkbox.disabled = true;
        error.hidden = true;

        const newDone = checkbox.checked;
        if (newDone) completed.add(stepIndex); else completed.delete(stepIndex);
        liEl.classList.toggle("step-done", newDone);
        stepProgress.refreshBars();

        const ok = await onToggle(stepIndex, newDone);

        checkbox.disabled = false;
        inFlight = false;

        if (!ok) {
            checkbox.checked = !newDone;
            if (!newDone) completed.add(stepIndex); else completed.delete(stepIndex);
            error.textContent = "Couldn't save. Try again.";
            error.hidden = false;
        }
        // completed may have been resynced from the server's authoritative
        // response inside onToggle (on success) - reflect whatever it now
        // says, not just the optimistic guess.
        liEl.classList.toggle("step-done", completed.has(stepIndex));
        stepProgress.refreshBars();
    });

    checkSlot.append(checkbox, label, error);
}

// videosPending: a "Finding videos" placeholder is shown for steps that don't have a
// video result yet (only ever true for the CURRENT shape - see fetchVideos in
// roadmap.html; an old flat roadmap loaded from /roadmap/latest is never "pending").
// isFirstOverall: true only for the very first step of the whole roadmap (gets the
// "Start here" marker) - not just the first step of whichever phase/list is being
// built, so a phased roadmap only marks one true starting point.
// displayIndex: this step's position within whatever list is currently being built -
// only used as the step-num fallback for an older roadmap that predates
// global_step_index.
// stepProgress: optional {roadmapId, completed, onToggle, stepIndex, refreshBars} -
// see roadmapStepList, which builds this per-step and is the only caller that
// ever passes it. Absent (undefined) entirely when the caller (dashboard,
// or roadmap.html before progress data is ready) didn't ask for progress
// tracking - the step then renders exactly as it did before this task,
// .step-check staying an empty placeholder.
// The step number sits on the margin rule, which is what turns the rule into a route.
//
// Renders only the fields a step actually has: an old flat-roadmap step (just
// step_number/title/description, maybe "resource") shows exactly what it did
// before this task; subtopics/projects/resources/more_topics simply don't
// appear when absent, and "videos" (new, up to 4 links) is preferred over the
// legacy single "resource" link when both would otherwise apply.
//
// tag: optional "focus" | "skim" (a personalized cached roadmap marks some steps; see personalizationOf) - a small
// label above the title. Absent for every older roadmap, which then renders exactly as before.
function roadmapStep(step, displayIndex, videosPending, isFirstOverall, stepProgress, tag) {
    const text = el("div", { className: "step-text" });
    if (isFirstOverall) text.append(el("p", { className: "start-here" }, el("span", { className: "mark", text: "Start here" })));
    if (tag === "focus") text.append(el("p", { className: "step-tag step-tag-focus", text: "Focus" }));
    if (tag === "skim") text.append(el("p", { className: "step-tag step-tag-skim", text: "Can skim" }));
    text.append(
        el("h3", { className: "step-title" },
            el("span", { className: "step-done-mark", "aria-hidden": "true" }, icon("tick")),
            el("span", { text: step.title || `Step ${displayIndex + 1}` })
        ),
        el("p", { className: "step-desc", text: step.description || "" }),
        subtopicChips(step.subtopics),
        projectsBlock(step.projects)
    );

    const aside = el("div", { className: "step-aside" });
    if ("videos" in step) {
        aside.append(
            el("p", { className: "note", text: "Videos for this step" }),
            videosBlock(step.videos),
            resourcesDetails(step.resources),
            moreTopicsDetails(step.more_topics)
        );
    } else if ("resource" in step) {
        // Legacy single-video shape (predates "videos") - same markup this
        // page has always rendered for it.
        if (step.resource && isSafeUrl(step.resource.url)) {
            aside.append(
                el("p", { className: "note", text: "Video for this step" }),
                el("a", {
                    className: "watch",
                    href: step.resource.url,
                    target: "_blank",
                    rel: "noopener noreferrer",
                }, icon("play"), el("span", { text: step.resource.title || step.resource.url }), el("span", { className: "visually-hidden", text: "(opens in a new tab)" }))
            );
        } else {
            aside.append(el("p", { className: "note", text: "No videos found for this step." }));
        }
    } else if (videosPending) {
        aside.append(el("p", { className: "note", text: "Finding videos...", role: "status" }));
    }

    const grid = el("div", { className: "step-grid" }, text, aside);

    const initialDone = stepProgress ? stepProgress.completed.has(stepProgress.stepIndex) : false;
    const checkSlot = el("div", { className: "step-check" });
    const li = el("li", { className: `row step${isFirstOverall ? " step-first" : ""}${initialDone ? " step-done" : ""}` },
        el("span", { className: "step-num num", text: String(step.global_step_index ?? step.step_number ?? displayIndex + 1), "aria-hidden": "true" }),
        el("div", { className: "margin" }, checkSlot),
        el("div", { className: "main" }, grid)
    );

    if (stepProgress) wireStepCheckbox(checkSlot, stepProgress, li);

    return li;
}

// A phase's own heading row, styled like the rest of the page's section breaks
// (row() keeps it aligned with the steps' margin/main columns and the route spine).
// Returned as a <summary> (via row()'s tag override) so roadmapStepList can use
// it directly as a <details> phase's clickable header.
function phaseHeaderRow(phase, note) {
    const stepCount = phase.steps.length;
    return row(
        [el("p", { className: "note", text: `Phase ${phase.phase_number}` }), el("div", { className: "phase-progress" })],
        [
            el("h3", { className: "phase-title", text: phase.title }),
            el("p", { className: "note", text: `${stepCount} step${stepCount === 1 ? "" : "s"}` }),
            note ? el("p", { className: "phase-note", text: note }) : "",
        ],
        "row-head phase-summary",
        "summary"
    );
}

// The optional personalization of a cached roadmap (steps.personalization, see
// app/pipeline/roadmap_personalizer.py) or null. Older roadmaps and flat ones have none.
function personalizationOf(steps) {
    if (Array.isArray(steps) || !steps || typeof steps.personalization !== "object" || !steps.personalization) return null;
    return steps.personalization;
}

// "For you" summary and the "Based on a reviewed ... roadmap" line, or "" when the roadmap is neither cached nor
// personalized (every older roadmap). All text goes through textContent (el()).
function roadmapOriginBlock(steps, careerPath) {
    const personal = personalizationOf(steps);
    const base = !Array.isArray(steps) && steps && typeof steps.base === "object" && steps.base ? steps.base : null;
    if (!personal && !base) return "";
    const main = [];
    if (personal && typeof personal.summary === "string" && personal.summary) {
        main.push(el("p", { className: "personal-summary", text: personal.summary }));
    }
    if (base) {
        main.push(el("p", { className: "note based-on", text: personal
            ? `Based on a reviewed ${careerPath} roadmap, personalized for you.`
            : `Based on a reviewed ${careerPath} roadmap.` }));
    }
    return row([el("p", { className: "note", text: personal ? "For you" : "About this roadmap" })], main, "personal-row");
}

// steps: either an older roadmap's flat step array, or the current
// {"phases": [{"phase_number", "title", "steps": [...]}]} shape. Always returns one
// node (a plain <ol class="route"> for the flat case - unchanged from before this
// task - or a sequence of collapsible <details class="phase"> for the phased case),
// since callers push this straight into a flat list of parts.
//
// progress: OPTIONAL {roadmapId, completed: Set, onToggle}. Omitted (as
// every caller except roadmap.html does), behavior is byte-for-byte what
// it was before this task - no checkboxes, no progress bars, .step-check
// and .phase-progress stay the empty placeholders they've been since the
// step-display task. Given, every step gets a live checkbox
// (wireStepCheckbox), each phase's .phase-progress gets a live "N of M"
// bar, and an overall bar is shown above the roadmap (flat roadmaps only
// get the overall bar, per computeStepIndexes/step_indexes using
// step_number for that shape - there are no phases to show a per-phase
// bar for).
function roadmapStepList(steps, videosPending, progress) {
    const indexes = computeStepIndexes(steps);
    const personal = personalizationOf(steps);
    const listOf = (name) => (personal && Array.isArray(personal[name]) ? personal[name] : []);
    const focusSteps = new Set(listOf("priority_steps"));
    const skimSteps = new Set(listOf("can_skim"));
    const phaseNotes = new Map(listOf("phase_notes").filter((n) => n && typeof n.note === "string").map((n) => [n.phase_number, n.note]));

    let overallBar = "";
    let refreshOverall = () => {};
    if (progress) {
        const [container, update] = makeProgressBar((done, total, pct) => `${done} of ${total} steps, ${pct}%`);
        overallBar = container;
        refreshOverall = () => update(indexes.filter((idx) => progress.completed.has(idx)).length, indexes.length);
    }

    if (Array.isArray(steps)) {
        const list = el("ol", { className: "route" }, ...steps.map((step, i) => {
            const stepProgress = progress ? { ...progress, stepIndex: indexes[i], refreshBars: refreshOverall } : null;
            return roadmapStep(step, i, videosPending, i === 0, stepProgress);
        }));
        if (progress) {
            refreshOverall();
            return el("div", { className: "flat-progress-wrap" }, overallBar, list);
        }
        return list;
    }

    const phaseEls = [];
    let seenAny = false;
    let cursor = 0;
    steps.phases.forEach((phase, phaseIndex) => {
        const phaseIndexes = phase.steps.map(() => indexes[cursor++]);

        const summary = phaseHeaderRow(phase, phaseNotes.get(phase.phase_number));
        let refreshPhase = () => {};
        if (progress) {
            const bar = summary.querySelector(".phase-progress");
            const [barContainer, update] = makeProgressBar((done, total) => `${done} of ${total}`);
            bar.append(barContainer);
            refreshPhase = () => update(phaseIndexes.filter((idx) => progress.completed.has(idx)).length, phaseIndexes.length);
            refreshPhase();
        }
        const refreshBars = () => { refreshPhase(); refreshOverall(); };

        const stepList = el("ol", { className: "route" }, ...phase.steps.map((step, i) => {
            const isFirstOverall = !seenAny;
            seenAny = true;
            const stepProgress = progress ? { ...progress, stepIndex: phaseIndexes[i], refreshBars } : null;
            const tag = focusSteps.has(phaseIndexes[i]) ? "focus" : (skimSteps.has(phaseIndexes[i]) ? "skim" : null);
            return roadmapStep(step, i, videosPending, isFirstOverall, stepProgress, tag);
        }));

        const details = el("details", { className: "phase" }, summary, stepList);
        details.open = phaseIndex === 0;   // first phase open, rest closed
        phaseEls.push(details);
    });

    if (progress) refreshOverall();

    const expandBtn = el("button", { className: "btn-quiet", type: "button", text: "Expand all" });
    const collapseBtn = el("button", { className: "btn-quiet", type: "button", text: "Collapse all" });
    expandBtn.addEventListener("click", () => phaseEls.forEach((d) => { d.open = true; }));
    collapseBtn.addEventListener("click", () => phaseEls.forEach((d) => { d.open = false; }));

    return el("div", { className: "phases-detail" },
        progress ? overallBar : "",
        el("div", { className: "actions phase-controls" }, expandBtn, collapseBtn),
        ...phaseEls
    );
}

// A compact summary for space-constrained contexts (the dashboard, shown alongside
// several other sections) - phase titles and step counts only, no step-by-step detail,
// since a phased roadmap can run to 20+ steps where the old flat one topped out at 12.
// An older flat-shape roadmap is short enough to just show in full via roadmapStepList.
//
// dashboardProgress: OPTIONAL {completed_count, total_steps} (the
// dashboard's own compact shape - NOT the same shape as roadmapStepList's
// "progress", which needs a live completed Set + onToggle for its
// checkboxes). Shows a small READ-ONLY bar when present; nothing when
// absent (an old dashboard payload, or a roadmap somehow missing it).
function roadmapDashboardSummary(steps, dashboardProgress) {
    const bar = (() => {
        if (!dashboardProgress) return "";
        const [container, update] = makeProgressBar((done, total, pct) => `${done} of ${total} steps, ${pct}%`);
        update(dashboardProgress.completed_count, dashboardProgress.total_steps);
        return container;
    })();

    if (Array.isArray(steps)) {
        return el("div", { className: "block" }, bar, roadmapStepList(steps, false));
    }

    const totalSteps = steps.phases.reduce((n, phase) => n + phase.steps.length, 0);
    return el("div", { className: "block" },
        bar,
        el("p", { className: "note", text: `${steps.phases.length} phases, ${totalSteps} steps in total` }),
        el("ul", { className: "dots" }, ...steps.phases.map((phase) =>
            el("li", { text: `${phase.title} — ${phase.steps.length} step${phase.steps.length === 1 ? "" : "s"}` })
        ))
    );
}

// A roadmap only counts as "fully resourced" once every step (across every phase, for
// the current shape) has been through the resolver at least once - a "videos" key
// (its array may be empty: resolved, just nothing found) or the legacy "resource"
// key (its value may be null, same meaning) both count.
function hasAllVideoResults(steps) {
    const allSteps = Array.isArray(steps) ? steps : steps.phases.flatMap((phase) => phase.steps);
    return allSteps.every((step) => "videos" in step || "resource" in step);
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

// median-only now (see the salary-simplification task) - the backend still
// computes/returns min/max (format_salary_range_summary and any future
// consumer may still need them), this column just no longer shows a Range.
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
                (st) => ({ median: formatInr(st.median) })
            ),
            salaryColumn(
                "Developer survey, India",
                "Self-reported by working developers, so usually higher. Converted from USD at an approximate rate.",
                insights.survey_respondents,
                (st) => ({ median: `~${formatInr(st.approx_inr.median)}` })
            )
        ),
    ];

    return row(
        [rowTitle("Salary expectations", level), el("p", { className: "note", text: "Per year, from two separate sources." })],
        main
    );
}

// Self-fetching: starts in a loading state, then GETs /resume/listings for
// targetCareerPath and fills itself in - independent of whatever rendered
// the rest of the page, same self-contained pattern as careerPathPicker's
// self-fetching mode. Always shows the Adzuna credit line underneath,
// regardless of load/empty/unavailable/success state.
function liveListingsRow(targetCareerPath, level) {
    const body = el("div", {});

    function renderListings(listings) {
        body.replaceChildren(el("ul", { className: "listings" }, ...listings.map((job) => {
            const whereText = [job.company, job.location].filter(Boolean).join(" · ");
            const text = [
                el("span", { className: "listing-title", text: job.title || "" }),
                whereText ? el("span", { className: "listing-where", text: whereText }) : "",
            ];
            const content = isSafeUrl(job.url)
                ? el("a", { className: "listing-link", href: job.url, target: "_blank", rel: "noopener noreferrer" },
                    ...text, el("span", { className: "visually-hidden", text: "(opens in a new tab)" }))
                : el("span", {}, ...text);

            if (job.salary_estimate == null) {
                return el("li", { className: "listing" }, content);
            }
            const figure = el("span", { className: "listing-salary" }, el("span", { className: "num", text: formatInr(job.salary_estimate) }));
            if (job.salary_is_predicted) figure.append(el("span", { className: "tag", text: "estimated" }));
            return el("li", { className: "listing" }, content, figure);
        })));
    }

    body.append(working("Finding live listings..."));
    getJson(`/resume/listings?career_path=${encodeURIComponent(targetCareerPath)}`).then((result) => {
        if (!result.ok || result.data.unavailable) {
            body.replaceChildren(el("p", { className: "note", text: "Live listings unavailable right now." }));
            return;
        }
        if (!result.data.listings.length) {
            body.replaceChildren(el("p", { className: "note", text: "No live listings found for this role." }));
            return;
        }
        renderListings(result.data.listings);
    });

    return row(
        [rowTitle("Live job listings", level), el("p", { className: "note", text: "Current openings for this career path." })],
        [
            body,
            el("p", { className: "note credit" }, "Jobs by ",
                el("a", { href: "https://www.adzuna.com", target: "_blank", rel: "noopener noreferrer", text: "Adzuna" })),
        ]
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
        liveListingsRow(data.target_career_path, level),
        ...feedbackRows(data.ai_feedback, level),
    ];
}


// ---------- "which path fits my resume" (POST /resume/discover) ----------
//
// Everything here is built with el() / textContent, never innerHTML: skill names and path
// names come from the server.

const FIT_LIMITS_NOTE = "How to read this: it is a skills match, not a hiring prediction. Paths that share most of their skills, such as AI and machine learning, score almost the same, so treat close scores as a tie rather than a ranking. Paths with few survey respondents are listed separately, only when the learning roadmaps clearly relate to your skills, and without a score.";

function fitBar(pct) {
    const fill = el("i", {});
    fill.style.width = `${Math.max(0, Math.min(100, pct))}%`;
    return el("div", { className: "fit-bar", role: "img", "aria-label": `${Math.round(pct)} percent of the top match in this list` }, fill);
}

// One path: name, how it compares with the top of its list, the skills that counted, the
// evidence behind it, and the button that analyzes the stored resume against it.
function fitCard(entry, onAnalyze) {
    const evidence = entry.basis === "based on roadmap content only"
        ? `${entry.respondent_count} survey respondents, too few to use. Ranked on roadmap content only.`
        : `${entry.respondent_count} survey respondents. Survey data and roadmap content.`;

    const analyze = el("button", { className: "btn btn-outline", type: "button", text: "Analyze against this path" });
    analyze.setAttribute("aria-label", `Analyze my resume against ${entry.path}`);
    analyze.addEventListener("click", () => onAnalyze(entry.path, analyze));

    return el("div", { className: "fit-card" },
        el("h3", { className: "fit-name", text: entry.path }),
        el("p", { className: "fit-pct" }, el("span", { className: "num", text: `${Math.round(entry.fit_pct)}%` }), " of the top match in this list"),
        fitBar(entry.fit_pct),
        entry.matched_skills.length
            ? el("div", {}, el("p", { className: "note fit-label", text: "Skills that counted" }), skillChips(entry.matched_skills.slice(0, 8), "have"))
            : el("p", { className: "note", text: "No single skill stood out for this path." }),
        el("p", { className: "note fit-evidence", text: evidence }),
        el("div", { className: "actions" }, analyze)
    );
}

// A path with limited evidence: its rank, matched skills and respondent count, but no percentage.
function thinPathCard(entry, onAnalyze) {
    const analyze = el("button", { className: "btn btn-outline", type: "button", text: "Analyze against this path" });
    analyze.setAttribute("aria-label", `Analyze my resume against ${entry.path}`);
    analyze.addEventListener("click", () => onAnalyze(entry.path, analyze));
    return el("div", { className: "fit-card" },
        el("h3", { className: "fit-name" }, el("span", { className: "num", text: `${entry.rank}. ` }), entry.path),
        entry.matched_skills.length
            ? el("div", {}, el("p", { className: "note fit-label", text: "Skills that matched" }), skillChips(entry.matched_skills.slice(0, 8), "have"))
            : el("p", { className: "note", text: "No single skill stood out for this path." }),
        el("p", { className: "note fit-evidence", text: `${entry.respondent_count} survey respondents.` }),
        el("div", { className: "actions" }, analyze)
    );
}

// The thin-path list, collapsed. Nothing at all is rendered when no thin path passed the evidence floor.
function thinPathsDetails(rows, onAnalyze) {
    if (!rows.length) return null;
    const details = el("details", { className: "fit-other" });
    details.append(
        el("summary", { text: `Other paths (limited evidence) (${rows.length})` }),
        el("p", { className: "note", text: "These paths have fewer than 30 survey respondents, so they are listed from the learning roadmaps alone, in order, without a score." }),
        ...rows.map((r) => thinPathCard(r, onAnalyze))
    );
    return details;
}

// One ranked list: a heading and explanation in the margin-style row, then the cards. The
// near-tie group (if any) is shown side by side in one row instead of as a ranking.
function fitList(title, intro, rows, tiePaths, onAnalyze, level) {
    const out = [row([rowTitle(title, level), el("p", { className: "note", text: intro })], [], "fit-head")];
    const tied = new Set(tiePaths);
    let tieShown = false;
    for (const entry of rows) {
        if (tied.has(entry.path)) {
            if (tieShown) continue;
            tieShown = true;
            out.push(row(
                [el("p", { className: "note", text: "Too close to call" }), el("p", { className: "note", text: "These are within 15% of each other. Treat them as a tie." })],
                el("div", { className: "split split-2 tie-group" }, ...rows.filter((r) => tied.has(r.path)).map((r) => fitCard(r, onAnalyze))),
                "fit-row fit-tie"
            ));
        } else {
            out.push(row([], fitCard(entry, onAnalyze), "fit-row"));
        }
    }
    return out;
}

// data: the /resume/discover response. onAnalyze(path, buttonEl) runs when a row's button is pressed.
function discoverRows(data, onAnalyze, level) {
    const skillsMargin = [rowTitle("Skills we found", level), el("p", { className: "note", text: `${data.extracted_skills.length} recognised` })];
    const skillsMain = data.extracted_skills.length
        ? skillChips(data.extracted_skills, "have")
        : el("p", { text: "We couldn't recognise any skills in this resume." });
    const rows = [row(skillsMargin, skillsMain)];

    if (data.insufficient_data) {
        rows.push(row([rowTitle("Not enough to go on", level)], el("div", { className: "msg", role: "status" },
            el("p", { text: `We recognised ${data.extracted_skills.length} skill${data.extracted_skills.length === 1 ? "" : "s"}, and we need at least 3 to compare career paths fairly.` }),
            el("p", { text: "Add or expand a skills section with the languages, tools and frameworks you have used, then upload the resume again." })
        )));
        return rows;
    }

    rows.push(...fitList(
        "Paths with survey data",
        "Ranked by how common and how distinctive your skills are among Indian developers in the Stack Overflow Developer Survey, blended with how closely your skills match each path's learning roadmap.",
        data.list_a, data.near_ties.a, onAnalyze, level
    ));
    const other = thinPathsDetails(data.list_b, onAnalyze);
    if (other) rows.push(row([], other, "fit-row"));
    rows.push(row([rowTitle("Limits of this match", level)], el("p", { className: "fit-limits", text: FIT_LIMITS_NOTE })));
    return rows;
}
