// The Skill DNA Map: the DSA prerequisite graph, drawn with D3 (v7, loaded by the page).
//
// One column per prerequisite depth, so every arrow points left to right, from a topic
// to something it unlocks. What each node looks like:
//   locked    dimmed, dashed outline, padlock
//   unlocked  white, fills in as mastery grows, a ring around it shows the exact level
//   mastered  solid ink with a tick and a soft glow
//   label highlighted in marker yellow = matters for the student's career path
//
// drawSkillMap(container, data, { onSelect }) draws into `container` and returns
// { select(id) } to move the selection ring from outside (e.g. when the panel's
// "master this first" buttons are used). `data` is the /dsa/map response.

const SKILLMAP = {
    radius: 24,
    colGap: 190,
    rowGap: 100,
    padX: 80,
    padTop: 44,
    padBottom: 64,
    labelChars: 14,
};

// Split a topic into at most two lines, breaking at spaces near labelChars.
function skillMapLabelLines(text) {
    const lines = [];
    let line = "";
    for (const word of text.split(" ")) {
        if (line && (line + " " + word).length > SKILLMAP.labelChars) {
            lines.push(line);
            line = word;
        } else {
            line = line ? line + " " + word : word;
        }
    }
    lines.push(line);
    return lines;
}

// Give every node an x (its depth's column) and a y (ordered within the column by where its
// prerequisites sit, so edges cross as little as they easily can). Mutates the node objects.
function layoutSkillMap(nodes) {
    const columns = d3.groups(nodes, (n) => n.layer)
        .sort((a, b) => a[0] - b[0])
        .map(([, members]) => members);
    const tallest = d3.max(columns, (c) => c.length);
    const height = (tallest - 1) * SKILLMAP.rowGap;
    const byId = new Map(nodes.map((n) => [n.id, n]));

    const stack = (column) => column.forEach((n, i) => {
        n.y = SKILLMAP.padTop + (height - (column.length - 1) * SKILLMAP.rowGap) / 2 + i * SKILLMAP.rowGap;
    });
    columns.forEach(stack);

    for (let pass = 0; pass < 4; pass++) {
        for (const column of columns.slice(1)) {
            const pull = (n) => n.prerequisites.length ? d3.mean(n.prerequisites, (p) => byId.get(p).y) : n.y;
            column.sort((a, b) => pull(a) - pull(b) || a.id - b.id);
            stack(column);
        }
    }

    nodes.forEach((n) => { n.x = SKILLMAP.padX + n.layer * SKILLMAP.colGap; });
    return {
        width: SKILLMAP.padX * 2 + (columns.length - 1) * SKILLMAP.colGap,
        height: SKILLMAP.padTop + height + SKILLMAP.padBottom,
    };
}

function skillNodeDescription(n) {
    const pct = Math.round(n.mastery_level * 100);
    let text = n.topic + ". ";
    if (n.state === "locked") {
        text += "Locked. Master " + n.blocked_by.map((b) => b.topic).join(" and ") + " first.";
    } else if (n.state === "mastered") {
        text += "Mastered.";
    } else {
        text += pct > 0 ? "Unlocked, " + pct + " percent mastered." : "Unlocked, not started.";
    }
    if (n.career_relevant) text += " Important for your career path.";
    return text;
}

function drawSkillMap(container, data, { onSelect }) {
    const nodes = data.nodes.map((n) => ({ ...n }));
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const edges = data.edges.map((e) => ({ source: byId.get(e.source), target: byId.get(e.target) }));
    const size = layoutSkillMap(nodes);
    const R = SKILLMAP.radius;

    const svg = d3.select(container).append("svg")
        .attr("class", "skillmap-svg")
        .attr("viewBox", `0 0 ${size.width} ${size.height}`)
        .attr("role", "group")
        .attr("aria-label", "Skill map: DSA topics, with arrows from each topic to the topics it unlocks");

    // One arrowhead per edge colour (markers can't inherit the line's colour reliably).
    const defs = svg.append("defs");
    for (const kind of ["open", "closed"]) {
        defs.append("marker")
            .attr("id", `skillmap-arrow-${kind}`)
            .attr("class", `arrow arrow-${kind}`)
            .attr("viewBox", "0 0 10 10").attr("refX", 9).attr("refY", 5)
            .attr("markerWidth", 9).attr("markerHeight", 9)
            .attr("markerUnits", "userSpaceOnUse").attr("orient", "auto")
            .append("path").attr("d", "M0 0 L10 5 L0 10 Z");
    }
    const glow = defs.append("filter").attr("id", "skillmap-glow").attr("x", "-60%").attr("y", "-60%").attr("width", "220%").attr("height", "220%");
    glow.append("feGaussianBlur").attr("in", "SourceGraphic").attr("stdDeviation", 5).attr("result", "blur");
    glow.append("feMerge").selectAll("feMergeNode").data(["blur", "SourceGraphic"]).join("feMergeNode").attr("in", (d) => d);

    const link = d3.linkHorizontal()
        .source((e) => [e.source.x + R + 7, e.source.y])
        .target((e) => [e.target.x - R - 8, e.target.y]);

    // An arrow is "open" once the topic it leaves is mastered: the way on has been earned.
    const edgeSel = svg.append("g").attr("class", "edges")
        .selectAll("path").data(edges).join("path")
        .attr("class", (e) => "edge " + (e.source.state === "mastered" ? "edge-open" : "edge-closed"))
        .attr("d", link)
        .attr("marker-end", (e) => `url(#skillmap-arrow-${e.source.state === "mastered" ? "open" : "closed"})`);

    const nodeSel = svg.append("g").attr("class", "nodes")
        .selectAll("g").data(nodes).join("g")
        .attr("class", (n) => `node state-${n.state}`)
        .attr("transform", (n) => `translate(${n.x},${n.y})`)
        .attr("tabindex", 0)
        .attr("role", "button")
        .attr("aria-pressed", "false")
        .attr("aria-label", skillNodeDescription);

    nodeSel.append("title").text(skillNodeDescription);
    nodeSel.append("circle").attr("class", "select-ring").attr("r", R + 12);

    // Mastery: the ring shows the exact level (a full ring = 100%); the fill deepens with it
    // until the topic counts as mastered, when the whole node turns solid.
    const fill = d3.scaleLinear().domain([0, data.mastery_threshold]).range(["#FFFFFF", "#C9D0F3"]).clamp(true);
    const arc = d3.arc().innerRadius(R + 3).outerRadius(R + 7).startAngle(0);
    nodeSel.filter((n) => n.state !== "locked").each(function (n) {
        const g = d3.select(this);
        g.append("circle").attr("class", "ring-track").attr("r", R + 5);
        if (n.mastery_level > 0) {
            g.append("path").attr("class", "ring-fill")
                .attr("d", arc({ endAngle: Math.min(n.mastery_level, 1) * 2 * Math.PI - 0.0001 }));
        }
    });
    nodeSel.append("circle").attr("class", "body").attr("r", R)
        .attr("fill", (n) => n.state === "unlocked" ? fill(n.mastery_level) : null);

    // Glyphs: tick, padlock, or the percentage.
    nodeSel.filter((n) => n.state === "mastered").append("path").attr("class", "glyph glyph-tick")
        .attr("d", "M-9 1 L-3 7 L9 -7");
    nodeSel.filter((n) => n.state === "locked").each(function () {
        const g = d3.select(this).append("g").attr("class", "glyph glyph-lock");
        g.append("rect").attr("x", -8).attr("y", -1).attr("width", 16).attr("height", 12).attr("rx", 1.5);
        g.append("path").attr("d", "M-4.5 -1 V-5 a4.5 4.5 0 0 1 9 0 V-1").attr("fill", "none");
    });
    nodeSel.filter((n) => n.state === "unlocked").append("text").attr("class", "glyph glyph-pct")
        .attr("text-anchor", "middle").attr("dy", "0.35em")
        .text((n) => Math.round(n.mastery_level * 100) + "%");

    // Labels under the node, with a highlighter stroke behind the ones that matter for this career path.
    nodeSel.each(function (n) {
        const g = d3.select(this);
        const label = g.append("g").attr("class", "label");
        const text = label.append("text").attr("text-anchor", "middle").attr("y", R + 22);
        skillMapLabelLines(n.topic).forEach((line, i) => {
            text.append("tspan").attr("x", 0).attr("dy", i === 0 ? 0 : "1.2em").text(line);
        });
        if (n.career_relevant) {
            const box = text.node().getBBox();
            label.insert("rect", "text").attr("class", "label-mark")
                .attr("x", box.x - 5).attr("y", box.y + 1)
                .attr("width", box.width + 10).attr("height", box.height - 2).attr("rx", 2);
        }
    });

    // Hovering or focusing a node picks out the arrows into and out of it.
    const focusEdges = (n) => edgeSel
        .classed("edge-hot", (e) => e.source === n || e.target === n)
        .classed("edge-faded", (e) => e.source !== n && e.target !== n);
    const clearEdges = () => edgeSel.classed("edge-hot", false).classed("edge-faded", false);

    const select = (id) => {
        nodeSel.classed("selected", (n) => n.id === id).attr("aria-pressed", (n) => (n.id === id ? "true" : "false"));
    };

    nodeSel
        .on("mouseenter", (event, n) => focusEdges(n))
        .on("mouseleave", clearEdges)
        .on("focus", (event, n) => focusEdges(n))
        .on("blur", clearEdges)
        .on("click", (event, n) => { select(n.id); onSelect(n); })
        .on("keydown", (event, n) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                select(n.id);
                onSelect(n);
            }
        });

    return { select };
}
