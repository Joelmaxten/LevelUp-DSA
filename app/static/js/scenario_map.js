// Scenario level map: a winding road across a drawn scene, one level node per scenario, and a small level card.
// Globals from ui.js: el, svgEl. Loaded before scenarios.js, which calls levelMap() and openLevelCard().
//
// Display only: the states, best scores and the "recommended" flag come from GET /scenarios/<slug>, and the server
// still refuses a locked scenario (403 scenario_locked). Stars are derived from the best score for show
// (70% = 1, 85% = 2, 100% = 3) and never feed back into scoring. Everything is built with el()/svgEl() and textContent.

// One flat-colour scene per career path (keys are the path slugs). ground/far/near are the land, dark/mid/light colour
// the props, motifs picks which props are drawn.
const LEVEL_THEMES = {
    "ai-engineering":         { ground: "#DDF2EC", far: "#C3E6DA", near: "#A6D9C8", dark: "#2E7D6B", mid: "#5FB39C", light: "#F5FBF9", motifs: ["chip", "cloud", "tree"] },
    "backend-engineering":    { ground: "#E3E9F1", far: "#CDD7E4", near: "#B6C3D7", dark: "#3C4E6B", mid: "#7F93B2", light: "#F7F9FC", motifs: ["server", "building", "cylinder"] },
    "cloud-engineering":      { ground: "#DCEEFB", far: "#C5E2F6", near: "#ABD4F0", dark: "#2B6A9A", mid: "#6DAAD6", light: "#FFFFFF", motifs: ["cloud", "server", "cloud"] },
    "cybersecurity":          { ground: "#E1EFE4", far: "#C6E0CD", near: "#A8D0B3", dark: "#2F6B44", mid: "#5E9E72", light: "#F4FAF6", motifs: ["shield", "pine", "rock"] },
    "data-analytics":         { ground: "#FFF0DA", far: "#FBDFB6", near: "#F5CC90", dark: "#9A5B12", mid: "#D9934A", light: "#FFFBF4", motifs: ["bars", "tree", "rock"] },
    "data-engineering":       { ground: "#DFF1F5", far: "#C4E4EC", near: "#A5D4E0", dark: "#22667A", mid: "#5AA5B9", light: "#F5FBFD", motifs: ["cylinder", "gear", "building"] },
    "data-science":           { ground: "#ECF4D8", far: "#DCEAB7", near: "#C6DD91", dark: "#56702A", mid: "#8DAA55", light: "#FAFCF3", motifs: ["bars", "tree", "pine"] },
    "devops":                 { ground: "#E0F0EE", far: "#C2E0DB", near: "#A0CEC6", dark: "#1F6A62", mid: "#B8873A", light: "#F4FAF9", motifs: ["gear", "building", "gear"] },
    "frontend-development":   { ground: "#FCE7E2", far: "#F7D1C7", near: "#F1B7A9", dark: "#9C3B28", mid: "#DB7A64", light: "#FFF8F6", motifs: ["window", "tree", "star"] },
    "full-stack-development": { ground: "#E7EDFB", far: "#D1DBF5", near: "#B8C7EE", dark: "#34509A", mid: "#7290D6", light: "#F8FAFF", motifs: ["building", "server", "window"] },
    "game-development":       { ground: "#FFE8EF", far: "#F9CEDB", near: "#F2B1C5", dark: "#9B2D55", mid: "#E0729A", light: "#FFF7FA", motifs: ["star", "rock", "pine"] },
    "machine-learning-engineering": { ground: "#E3F3EA", far: "#C8E7D4", near: "#AAD8BC", dark: "#2C6E4B", mid: "#62AE85", light: "#F5FBF8", motifs: ["chip", "tree", "bars"] },
    "mobile-app-development": { ground: "#E3F5F9", far: "#C8E9F0", near: "#AADBE7", dark: "#1E6F82", mid: "#56AFC4", light: "#F6FCFD", motifs: ["phone", "cloud", "tree"] },
    "qa-test-automation":     { ground: "#FFF5D6", far: "#F8E7AA", near: "#F0D67D", dark: "#7D6512", mid: "#C9A635", light: "#FFFCF2", motifs: ["check", "tree", "gear"] },
    "ui-ux-design":           { ground: "#FCEDE0", far: "#F6D9BF", near: "#EFC39C", dark: "#8E4F1E", mid: "#D38B52", light: "#FFFAF5", motifs: ["window", "star", "tree"] },
};
const LEVEL_THEME_DEFAULT = { ground: "#E8ECF8", far: "#D6DCEF", near: "#C3CBE6", dark: "#3A4373", mid: "#7A84B3", light: "#F8F9FD", motifs: ["tree", "rock", "cloud"] };

const LEVEL_WIDE = "(min-width: 760px)";
const LEVEL_STATE_TEXT = { locked: "Locked", open: "Ready to play", attempted: "Tried, not passed yet", passed: "Passed" };
const LEVEL_STAGE_TEXT = { foundations: "Foundations", core_decision: "Core decisions", debugging: "Debugging", trade_offs: "Trade-offs", end_to_end: "End to end" };

// ---------------------------------------------------------------- small helpers
function levelPercent(s) {
    if (s.best_score === null || s.best_score === undefined || !s.max_score) return null;
    return Math.round((s.best_score / s.max_score) * 100);
}

function levelStars(s) {
    if (s.state !== "passed") return 0;
    const p = levelPercent(s) || 0;
    return p >= 100 ? 3 : p >= 85 ? 2 : p >= 70 ? 1 : 0;
}

// A small seeded generator, so a path's scene is the same on every visit.
function levelRandom(seedText) {
    let h = 2166136261;
    for (const ch of String(seedText)) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
    return () => {
        h = Math.imul(h ^ (h >>> 15), 2246822507);
        h = Math.imul(h ^ (h >>> 13), 3266489909);
        h ^= h >>> 16;
        return (h >>> 0) / 4294967296;
    };
}

// Node centres in viewBox units. Wide: left to right in a wave; narrow: top to bottom, centre-right-centre-left.
function levelLayout(n, wide) {
    if (wide) {
        const W = 1000, H = 460;
        const step = n > 1 ? 800 / (n - 1) : 0;
        const points = Array.from({ length: n }, (_, i) => ({ x: 100 + i * step, y: i % 2 ? 150 : 300 }));
        return { W, H, wide, points, start: { x: 18, y: points[0].y }, end: { x: 982, y: points[n - 1].y } };
    }
    const W = 360, row = 156, top = 78;
    const xs = [180, 268, 180, 92];
    const points = Array.from({ length: n }, (_, i) => ({ x: xs[i % 4], y: top + i * row }));
    const H = top + (n - 1) * row + 196;
    return { W, H, wide, points, start: { x: points[0].x, y: 8 }, end: { x: points[n - 1].x, y: H - 8 } };
}

function levelCurve(p, q, wide) {
    if (wide) {
        const dx = (q.x - p.x) / 2;
        return `M${p.x} ${p.y} C${p.x + dx} ${p.y} ${q.x - dx} ${q.y} ${q.x} ${q.y}`;
    }
    const dy = (q.y - p.y) / 2;
    return `M${p.x} ${p.y} C${p.x} ${p.y + dy} ${q.x} ${q.y - dy} ${q.x} ${q.y}`;
}

// Points along a cubic, used to keep props off the road.
function levelSamples(p, q, wide) {
    const out = [];
    for (let t = 0; t <= 1.0001; t += 0.05) {
        const c1 = wide ? { x: p.x + (q.x - p.x) / 2, y: p.y } : { x: p.x, y: p.y + (q.y - p.y) / 2 };
        const c2 = wide ? { x: q.x - (q.x - p.x) / 2, y: q.y } : { x: q.x, y: q.y - (q.y - p.y) / 2 };
        const u = 1 - t;
        out.push({
            x: u * u * u * p.x + 3 * u * u * t * c1.x + 3 * u * t * t * c2.x + t * t * t * q.x,
            y: u * u * u * p.y + 3 * u * u * t * c1.y + 3 * u * t * t * c2.y + t * t * t * q.y,
        });
    }
    return out;
}

// ---------------------------------------------------------------- props (each drawn around 0,0, about 40 units tall)
function levelProp(kind, t) {
    const g = (...kids) => svgEl("g", {}, ...kids);
    const r = (x, y, w, h, fill, rx) => svgEl("rect", { x, y, width: w, height: h, fill, rx: rx || 0 });
    const c = (cx, cy, rad, fill) => svgEl("circle", { cx, cy, r: rad, fill });
    switch (kind) {
        case "tree":
            return g(r(-3, 4, 6, 16, t.dark), c(0, -4, 14, t.mid), c(-6, -10, 6, t.light));
        case "pine":
            return g(r(-3, 10, 6, 10, t.dark), svgEl("polygon", { points: "0,-22 16,12 -16,12", fill: t.dark }),
                svgEl("polygon", { points: "0,-22 8,-4 -8,-4", fill: t.mid }));
        case "rock":
            return g(svgEl("ellipse", { cx: 0, cy: 12, rx: 18, ry: 9, fill: t.mid }), svgEl("ellipse", { cx: -4, cy: 9, rx: 7, ry: 3, fill: t.light }));
        case "cloud":
            return g(c(-10, 2, 9, t.light), c(2, -4, 12, t.light), c(13, 3, 8, t.light), r(-19, 2, 40, 9, t.light, 4));
        case "building":
            return g(r(-14, -20, 28, 40, t.dark, 2), ...[-12, -2, 8].flatMap((y) => [r(-9, y, 6, 6, t.light), r(3, y, 6, 6, t.light)]));
        case "server":
            return g(...[-18, -4, 10].map((y) => g(r(-16, y, 32, 12, t.dark, 2), c(-10, y + 6, 2, t.light), r(0, y + 5, 11, 2, t.mid))));
        case "cylinder":
            return g(r(-14, -12, 28, 28, t.mid), svgEl("ellipse", { cx: 0, cy: 16, rx: 14, ry: 5, fill: t.mid }),
                svgEl("ellipse", { cx: 0, cy: -12, rx: 14, ry: 5, fill: t.dark }), svgEl("ellipse", { cx: 0, cy: 2, rx: 14, ry: 4, fill: "none", stroke: t.dark, "stroke-width": 2 }));
        case "gear": {
            const teeth = Array.from({ length: 8 }, (_, i) => r(-3, -19, 6, 8, t.mid, 1));
            teeth.forEach((tooth, i) => tooth.setAttribute("transform", `rotate(${i * 45})`));
            return g(...teeth, c(0, 0, 14, t.mid), c(0, 0, 5, t.light));
        }
        case "chip":
            return g(...[-9, -1, 7].flatMap((v) => [r(v, -19, 3, 6, t.dark), r(v, 13, 3, 6, t.dark), r(-19, v, 6, 3, t.dark), r(13, v, 6, 3, t.dark)]),
                r(-14, -14, 28, 28, t.dark, 3), r(-7, -7, 14, 14, t.mid, 2));
        case "bars":
            return g(r(-16, 20, 34, 3, t.dark), r(-14, 4, 8, 16, t.mid), r(-3, -8, 8, 28, t.dark), r(8, -2, 8, 22, t.mid));
        case "window":
            return g(r(-20, -14, 40, 30, t.light, 3), r(-20, -14, 40, 8, t.dark, 3), r(-20, -9, 40, 3, t.dark),
                c(-15, -10, 1.5, t.light), c(-10, -10, 1.5, t.light), r(-14, 0, 18, 3, t.mid), r(-14, 7, 26, 3, t.mid));
        case "phone":
            return g(r(-11, -20, 22, 40, t.dark, 4), r(-8, -15, 16, 28, t.light, 1), c(0, 16, 1.6, t.light));
        case "star":
            return g(svgEl("polygon", { points: "0,-16 4.7,-6.5 15.2,-4.9 7.6,2.5 9.4,13 0,8 -9.4,13 -7.6,2.5 -15.2,-4.9 -4.7,-6.5", fill: t.mid }));
        case "shield":
            return g(svgEl("path", { d: "M0 -18 L15 -12 L15 2 C15 12 7 18 0 21 C-7 18 -15 12 -15 2 L-15 -12 Z", fill: t.dark }),
                svgEl("path", { d: "M-6 1 L-1 6 L7 -4", fill: "none", stroke: t.light, "stroke-width": 3, "stroke-linecap": "round", "stroke-linejoin": "round" }));
        case "check":
            return g(c(0, 0, 15, t.mid), svgEl("path", { d: "M-7 0 L-2 5 L8 -6", fill: "none", stroke: t.light, "stroke-width": 3.5, "stroke-linecap": "round", "stroke-linejoin": "round" }));
        default:
            return g(c(0, 0, 10, t.mid));
    }
}

// ---------------------------------------------------------------- the scene (decorative: aria-hidden)
function levelScene(layout, scenarios, theme, seed, sceneUrl) {
    const { W, H, wide, points, start, end } = layout;
    const rnd = levelRandom(seed);
    const svg = svgEl("svg", { class: "lvl-scene", viewBox: `0 0 ${W} ${H}`, "aria-hidden": "true", focusable: "false" });
    svg.append(svgEl("rect", { x: 0, y: 0, width: W, height: H, fill: theme.ground }));
    if (sceneUrl) svg.append(svgEl("image", { href: sceneUrl, x: 0, y: 0, width: W, height: H, preserveAspectRatio: "xMidYMid slice" }));

    // Land: soft hills in two flat tones.
    if (wide) {
        svg.append(svgEl("path", { d: `M0 ${H * 0.7} C${W * 0.2} ${H * 0.55} ${W * 0.4} ${H * 0.8} ${W * 0.6} ${H * 0.66} S${W * 0.9} ${H * 0.58} ${W} ${H * 0.68} L${W} ${H} L0 ${H} Z`, fill: theme.far }));
        svg.append(svgEl("path", { d: `M0 ${H * 0.86} C${W * 0.25} ${H * 0.76} ${W * 0.5} ${H * 0.94} ${W * 0.75} ${H * 0.82} S${W} ${H * 0.86} ${W} ${H * 0.86} L${W} ${H} L0 ${H} Z`, fill: theme.near }));
    } else {
        for (let i = 0; i < points.length + 1; i++) {
            const left = i % 2 === 0;
            const cy = 40 + i * ((H - 40) / (points.length + 0.5));
            svg.append(svgEl("ellipse", { cx: left ? -20 : W + 20, cy, rx: 120 + rnd() * 50, ry: 60 + rnd() * 30, fill: i % 3 ? theme.far : theme.near }));
        }
    }

    // The road: an edge, the surface, then per segment a solid line once the next level is unlocked, dashes before.
    const all = [start, ...points, end];
    const full = all.slice(1).map((q, i) => levelCurve(all[i], q, wide)).join(" ");
    svg.append(svgEl("path", { d: full, class: "lvl-road-edge", stroke: theme.near }));
    svg.append(svgEl("path", { d: full, class: "lvl-road" }));
    for (let i = 0; i < all.length - 1; i++) {
        // Segment i leads into level i (1-based); the last one leads to the finish.
        const target = i < scenarios.length ? scenarios[i] : null;
        const done = target ? target.state !== "locked" : scenarios.every((s) => s.state === "passed");
        svg.append(svgEl("path", { d: levelCurve(all[i], all[i + 1], wide), class: done ? "lvl-trail is-done" : "lvl-trail", stroke: theme.dark }));
    }

    // Props, kept clear of the road and of each level's label area.
    const road = [];
    for (let i = 0; i < all.length - 1; i++) road.push(...levelSamples(all[i], all[i + 1], wide));
    const clear = (x, y) => road.every((p) => Math.hypot(p.x - x, p.y - y) > 52)
        && points.every((p) => Math.abs(p.x - x) > (wide ? 92 : 84) || y < p.y - 70 || y > p.y + 112);
    const gap = wide ? 64 : 56;
    for (let y = 26; y < H - 10; y += gap) {
        for (let x = 22; x < W - 10; x += gap) {
            const jx = x + (rnd() - 0.5) * 22, jy = y + (rnd() - 0.5) * 22;
            if (rnd() > 0.42 || !clear(jx, jy)) continue;
            const kind = theme.motifs[Math.floor(rnd() * theme.motifs.length)];
            const prop = levelProp(kind, theme);
            prop.setAttribute("transform", `translate(${jx.toFixed(1)} ${jy.toFixed(1)}) scale(${(0.75 + rnd() * 0.4).toFixed(2)})`);
            svg.append(prop);
        }
    }

    // Start and finish markers.
    const flag = svgEl("g", { transform: `translate(${end.x} ${end.y - (wide ? 0 : 6)})` },
        svgEl("rect", { x: -2, y: -34, width: 4, height: 36, fill: theme.dark }),
        svgEl("path", { d: "M2 -34 L24 -27 L2 -20 Z", fill: theme.dark }));
    svg.append(flag, svgEl("circle", { cx: start.x, cy: start.y, r: 7, fill: theme.dark }));
    return svg;
}

// ---------------------------------------------------------------- icons inside the nodes (aria-hidden)
function levelIcon(kind) {
    const svg = svgEl("svg", { class: "lvl-icon", viewBox: "0 0 24 24", "aria-hidden": "true", focusable: "false" });
    if (kind === "lock") {
        svg.append(svgEl("rect", { x: 5, y: 10.5, width: 14, height: 10, rx: 2, fill: "currentColor" }),
            svgEl("path", { d: "M8 10.5V8a4 4 0 0 1 8 0v2.5", fill: "none", stroke: "currentColor", "stroke-width": 2.4 }));
    } else if (kind === "play") {
        svg.append(svgEl("path", { d: "M8 5.5v13l11-6.5z", fill: "currentColor" }));
    }
    return svg;
}

function levelStarRow(count, cls) {
    const row = el("span", { className: cls || "lvl-stars", "aria-hidden": "true" });
    for (let i = 0; i < 3; i++) {
        const star = svgEl("svg", { class: `lvl-star${i < count ? " is-on" : ""}`, viewBox: "0 0 24 24", focusable: "false" },
            svgEl("path", { d: "M12 2.8l2.8 5.8 6.3.9-4.6 4.4 1.1 6.3L12 17.2l-5.6 3 1.1-6.3L2.9 9.5l6.3-.9z" }));
        row.append(star);
    }
    return row;
}

function levelAriaLabel(s, total) {
    const bits = [`Level ${s.order} of ${total}: ${s.title}`, LEVEL_STATE_TEXT[s.state] || s.state];
    if (s.state === "passed") bits.push(`${levelStars(s)} of 3 stars`);
    if (levelPercent(s) !== null) bits.push(`best ${s.best_score} of ${s.max_score}`);
    if (s.recommended) bits.push("recommended next");
    if (s.matches_goal) bits.push("matches your goal");
    return bits.join(", ");
}

// ---------------------------------------------------------------- the map
// levelMap(data, { onOpen(s, node) }) -> an element that redraws itself when the screen crosses the wide breakpoint.
function levelMap(data, opts) {
    const theme = LEVEL_THEMES[data.slug] || LEVEL_THEME_DEFAULT;
    const scenarios = [...data.scenarios].sort((a, b) => a.order - b.order);
    const wrap = el("section", { className: "lvl", "aria-labelledby": "lvl-heading" },
        el("h2", { className: "visually-hidden", id: "lvl-heading", text: `Level map for ${data.path}` }));
    const media = window.matchMedia(LEVEL_WIDE);

    function draw() {
        const focusedOrder = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.order : null;
        const layout = levelLayout(scenarios.length, media.matches);
        const map = el("div", { className: `lvl-map${layout.wide ? " is-wide" : ""}` });
        map.style.setProperty("--lvl-dark", theme.dark);
        map.append(levelScene(layout, scenarios, theme, data.slug, data.scene_url));
        const list = el("ol", { className: "lvl-stops" });
        scenarios.forEach((s, i) => {
            const p = layout.points[i];
            const inner = s.state === "locked" ? levelIcon("lock") : s.state === "open" ? levelIcon("play")
                : el("span", { className: "lvl-num", "aria-hidden": "true", text: String(s.order) });
            const node = el("button", {
                type: "button", className: `lvl-node is-${s.state}`, "data-order": String(s.order),
                "aria-label": levelAriaLabel(s, scenarios.length), "aria-haspopup": "dialog",
            }, inner);
            if (s.matches_goal) node.append(el("span", { className: "lvl-goal", "aria-hidden": "true", title: "Matches your goal", text: "★" }));
            node.addEventListener("click", () => opts.onOpen(s, node));
            const stop = el("li", { className: `lvl-stop${s.recommended ? " is-recommended" : ""}` });
            stop.style.left = `${(p.x / layout.W) * 100}%`;
            stop.style.top = `${(p.y / layout.H) * 100}%`;
            if (s.recommended) stop.append(el("span", { className: "lvl-next", "aria-hidden": "true", text: "Next" }));
            stop.append(node);
            if (s.state === "passed" || s.state === "attempted") stop.append(levelStarRow(levelStars(s)));
            stop.append(el("span", { className: "lvl-name", "aria-hidden": "true", text: s.map_node && s.map_node.label ? s.map_node.label : s.title }));
            list.append(stop);
        });
        map.append(list);
        const old = wrap.querySelector(".lvl-map");
        if (old) old.replaceWith(map); else wrap.append(map);
        if (focusedOrder) {
            const again = map.querySelector(`[data-order="${CSS.escape(focusedOrder)}"]`);
            if (again) again.focus();
        }
    }

    draw();
    const onChange = () => { if (wrap.isConnected) draw(); else media.removeEventListener("change", onChange); };
    media.addEventListener("change", onChange);
    return wrap;
}

// ---------------------------------------------------------------- the level card
// openLevelCard(s, all, { onStart(s), onShow(s) }, returnFocus): a modal <dialog>; Escape or Close returns focus to the node.
function openLevelCard(s, all, actions, returnFocus) {
    const existing = document.getElementById("lvl-card");
    if (existing) existing.remove();
    const prev = all.find((x) => x.order === s.order - 1);
    const pct = levelPercent(s);
    const stars = levelStars(s);
    let leaving = false;

    const close = el("button", { type: "button", className: "btn btn-ghost btn-sm lvl-card-close", "aria-label": "Close", text: "×" });
    const meta = el("ul", { className: "chips" },
        el("li", { className: "chip chip-line", text: LEVEL_STAGE_TEXT[s.ladder_stage] || s.ladder_stage }),
        el("li", { className: "chip chip-line", text: `${s.minutes} min` }));
    if (s.matches_goal) meta.append(el("li", { className: "chip chip-line", text: "★ Matches your goal" }));

    const score = el("div", { className: "lvl-card-score" });
    if (s.state === "passed" || s.state === "attempted") score.append(levelStarRow(stars, "lvl-stars lvl-stars-lg"));
    score.append(el("p", { className: "lvl-card-best", text: pct === null ? "Not played yet" : `Best score ${s.best_score}/${s.max_score} (${pct}%)` }));

    let note;
    if (s.state === "locked") note = `Locked. Pass ${prev ? `"${prev.title}"` : "the level before it"} first (70% or more) to open this level.`;
    else if (s.state === "passed") note = stars < 3 ? "Passed. Play again to raise your best score and earn more stars." : "Passed with a perfect score.";
    else if (s.state === "attempted") note = "Not passed yet. Score 70% or more to pass and open the next level.";
    else note = "Ready to play. Score 70% or more to pass and open the next level.";

    const buttons = [];
    if (s.state === "locked") {
        const lockedBtn = el("button", { type: "button", className: "btn", "aria-disabled": "true", text: "Locked" });
        lockedBtn.addEventListener("click", (e) => e.preventDefault());
        buttons.push(lockedBtn);
        if (prev) {
            const go = el("button", { type: "button", className: "btn btn-secondary", text: `Go to level ${prev.order}` });
            go.addEventListener("click", () => { leaving = true; dialog.close(); actions.onShow(prev); });
            buttons.push(go);
        }
    } else {
        const play = el("button", { type: "button", className: "btn", text: s.state === "open" ? "Start" : "Try again" });
        play.addEventListener("click", () => { leaving = true; dialog.close(); actions.onStart(s); });
        buttons.push(play);
    }

    const dialog = el("dialog", { className: "lvl-card", id: "lvl-card", "aria-labelledby": "lvl-card-title", "aria-describedby": "lvl-card-note" },
        el("div", { className: "lvl-card-body stack-sm" },
            el("div", { className: "lvl-card-top" },
                el("p", { className: "lvl-card-level", text: `Level ${s.order}${s.map_node && s.map_node.label ? ` · ${s.map_node.label}` : ""}` }), close),
            el("h2", { className: "lvl-card-title", id: "lvl-card-title", tabindex: "-1", text: s.title }),
            meta, score,
            el("p", { className: `lvl-card-note${s.state === "locked" ? " is-locked" : ""}`, id: "lvl-card-note", text: note }),
            el("div", { className: "actions" }, ...buttons)));
    close.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
    dialog.addEventListener("close", () => {
        dialog.remove();
        if (!leaving && returnFocus && returnFocus.isConnected) returnFocus.focus();
    });
    document.body.append(dialog);
    if (typeof dialog.showModal === "function") dialog.showModal(); else dialog.setAttribute("open", "");
    (buttons[0] && s.state !== "locked" ? buttons[0] : document.getElementById("lvl-card-title")).focus();
}
