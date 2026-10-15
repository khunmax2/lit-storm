// Deep Research: its tree, a level per column. The plan writes the first queries (level 1, as
// broad as the depth asks); each query's researcher searches, learns, and sends deeper ones on
// what it learned (level 2, 3...). A researcher shows its query, what it is doing and what it
// found; one that found nothing usable fades. Fed by the Run's "tree" notes (the fork's
// research tree: id "0" is the plan, "0-1" its first child, "0-1-0" that one's).
(() => {
  function create(K, layers) {
    const m = { nodes: new Map(), order: [], writing: false, done: null, sources: 0, searches: 0 };
    const depthOf = (id) => String(id).split("-").length - 1;
    const parentOf = (d) => (d.parent != null ? String(d.parent) : String(d.id).split("-").slice(0, -1).join("-") || null);

    function apply(ev) {
      const d = ev.data || {};
      if (ev.type === "stage") { if (d.stage === "report") m.writing = true; return; }
      if (ev.type !== "note") return;
      if (d.kind === "browsed") { m.sources += (d.urls || []).length; return; }
      if (d.kind !== "tree") return;
      const id = String(d.id);
      let n = m.nodes.get(id);
      if (!n) {
        n = { id, parent: id === "0" ? null : parentOf(d), depth: depthOf(id), query: "", goal: "", status: "", sources: null, learnings: null };
        if (n.parent && !m.nodes.has(n.parent)) {
          m.nodes.set(n.parent, { id: n.parent, parent: null, depth: depthOf(n.parent), query: "", goal: "", status: "", sources: null, learnings: null });
          m.order.push(n.parent);
        }
        m.nodes.set(id, n);
        m.order.push(id);
      }
      if (d.query && !n.query && id !== "0") K.say("research", K.W.log.node(K.clip(d.query, 80)), ev.at);
      if (d.query) n.query = d.query;
      if (d.goal) n.goal = d.goal;
      if (d.status) { if (d.status === "searching" && n.status !== "searching") m.searches += 1; n.status = d.status; }
      if (d.sources != null) n.sources = d.sources;
      if (d.learnings != null) n.learnings = d.learnings;
    }

    function settle(run) { m.done = run.status === "succeeded" ? "done" : "fail"; }

    const kids = (id) => m.order.filter((k) => m.nodes.get(k).parent === id);
    const state = (n) => {
      if (n.status === "no_evidence") return "muted";
      if (n.status === "error") return "fail";
      if (n.status === "node_complete" || m.writing) return "done";
      if (m.done) return m.done === "done" ? "done" : "fail";
      return "active";
    };

    function draw() {
      const CW = 196, CH = 56, COL = CW + 52, ROW = CH + 12, TOP = 30, LEFT = 10;
      // leaves down the page in tree order, each parent centred on its children
      const pos = new Map();
      let cursor = 0;
      const place = (id) => {
        const k = kids(id);
        let at;
        if (!k.length) { at = cursor; cursor += ROW; } else { const all = k.map(place); at = (all[0] + all[all.length - 1]) / 2; }
        pos.set(id, at);
        return at;
      };
      m.order.filter((k) => !m.nodes.get(k).parent).forEach(place);
      const levels = Math.max(1, ...[...m.nodes.values()].map((n) => n.depth + 1));
      const W = Math.max(720, LEFT * 2 + (levels + (m.writing ? 1 : 0)) * COL);
      const H = Math.max(180, TOP + Math.max(cursor, ROW) + 10);
      K.view(W, H, 1600);

      const [heads] = layers.nodes.get("heads", "g");
      heads.textContent = "";
      for (let lv = 0; lv < levels; lv++) {
        const count = [...m.nodes.values()].filter((n) => n.depth === lv).length;
        K.text(heads, "label", LEFT + lv * COL + 4, 18, lv === 0 ? K.W.plan : `${K.W.level(lv)} · ${count}`);
      }
      m.order.forEach((id) => {
        const n = m.nodes.get(id);
        const box = { x: LEFT + n.depth * COL, y: TOP + pos.get(id), w: CW, h: CH };
        const p = n.parent && m.nodes.get(n.parent);
        const pbox = p && { x: LEFT + p.depth * COL, y: TOP + pos.get(p.id), w: CW, h: CH };
        const bits = [K.W.tree[n.status] || n.status];
        if (n.sources != null) bits.push(K.W.found(n.sources));
        if (n.learnings != null) bits.push(K.W.learnings(n.learnings));
        const s = state(n);
        K.card(layers.nodes, "n:" + id, box, {
          kind: id === "0" ? "plan" : "research", k: id === "0" ? K.W.planner : K.W.researcher,
          title: id === "0" ? K.W.plan : n.query || K.W.researcher, sub: bits.filter(Boolean).join(" · "), subBadge: true,
          state: s, from: pbox, tip: n.goal,
        });
        if (pbox) K.edge(layers.edges, "e:" + id, K.curve(pbox.x + CW, pbox.y + CH / 2, box.x, box.y + CH / 2), "research",
          s === "active" ? "flow" : "done");
      });
      if (m.writing) {
        const roots = m.order.filter((k) => !m.nodes.get(k).parent);
        const y = roots.length ? TOP + pos.get(roots[0]) : TOP;
        const wbox = { x: LEFT + levels * COL, y, w: CW - 40, h: CH };
        K.card(layers.nodes, "writer", wbox, { kind: "write", k: K.W.captions.write, title: K.W.writer,
          state: m.done ? (m.done === "done" ? "done" : "fail") : "active" });
        m.order.filter((k) => !kids(k).length && m.nodes.get(k).status !== "no_evidence").forEach((k) => {
          const n = m.nodes.get(k), b = { x: LEFT + n.depth * COL, y: TOP + pos.get(k) };
          K.edge(layers.edges, "w:" + k, K.curve(b.x + CW, b.y + CH / 2, wbox.x, wbox.y + CH / 2), "write", m.done ? "done" : "flow");
        });
      }
    }

    return {
      apply, settle, draw,
      empty: () => m.nodes.size === 0,
      stats: () => {
        const levels = Math.max(0, ...[...m.nodes.values()].map((n) => n.depth));
        const learned = [...m.nodes.values()].reduce((a, n) => a + (n.learnings || 0), 0);
        const out = [[Math.max(0, m.nodes.size - 1), K.W.agents], [m.sources, K.W.sources], [m.searches, K.W.searches]];
        if (levels) out.push([levels, K.W.levels]);
        if (learned) out.push([learned, K.W.findings]);
        return out;
      },
    };
  }

  function demo() {
    const ev = [];
    const push = (type, data) => ev.push({ type, data });
    push("stage", { stage: "research" });
    push("note", { kind: "tree", id: "0", status: "node_complete" });
    const qs = ["Thailand solar capacity 2026", "Rooftop solar policy in Thailand", "PV module costs in Southeast Asia"];
    qs.forEach((q, i) => {
      push("note", { kind: "tree", id: `0-${i}`, parent: "0", status: "generating_query" });
      push("note", { kind: "tree", id: `0-${i}`, query: q, goal: "Find current figures", status: "searching" });
    });
    qs.forEach((q, i) => {
      push("note", { kind: "browsed", urls: ["a", "b", "c", "d"] });
      push("note", { kind: "tree", id: `0-${i}`, query: q, status: "search_complete", sources: 4 + i });
      push("note", { kind: "tree", id: `0-${i}`, query: q, status: "processing_search_result" });
      push("note", { kind: "tree", id: `0-${i}-0`, parent: `0-${i}`, query: q + ": what changed this year", status: "searching" });
      if (i !== 1) push("note", { kind: "tree", id: `0-${i}-1`, parent: `0-${i}`, query: q + ": who decides", status: "searching" });
      push("note", { kind: "tree", id: `0-${i}`, query: q, status: "node_complete", learnings: 3 + i });
    });
    push("note", { kind: "browsed", urls: ["e", "f", "g"] });
    ["0-0-0", "0-0-1", "0-1-0", "0-2-0", "0-2-1"].forEach((id, i) =>
      push("note", { kind: "tree", id, status: i === 2 ? "no_evidence" : "node_complete", learnings: i === 2 ? 0 : 2 }));
    push("stage", { stage: "report" });
    return { run: { id: "demo", topic: "Solar energy in Thailand", mode: "Deep Research", engine: "deep", depth: "standard", language: "en", status: "running" }, events: ev };
  }

  window.DL.scenes.deep = { stages: ["research", "report"], create, demo };
})();
