// STORM: a round table, then a line of writers. The perspective finder seats the personas it
// finds round the topic expert; each interviews the expert, who searches the web to answer
// (the lines flow while they talk, the pages read count up). Then the outline writer, the
// section writers and the polisher take it in turn to the report. Fed by the Run's stages,
// its "perspectives" note and its "browsed" notes.
(() => {
  const LINE = ["outline", "article", "polish"];

  function create(K, layers) {
    const m = { stage: null, personas: [], pages: 0, done: null, finding: false };

    function apply(ev) {
      const d = ev.data || {};
      if (ev.type === "stage") { m.stage = d.stage; if (d.stage === "research") m.finding = true; return; }
      if (ev.type !== "note") return;
      if (d.kind === "browsed") { m.pages += (d.urls || []).length; return; }
      if (d.kind === "perspectives") {
        m.personas = (d.perspectives || []).map((p) => {
          const [name, ...rest] = String(p).split(":");
          return { name: K.clip(name, 40), about: K.clip(rest.join(":"), 90) };
        });
        K.say("persona", K.W.log.perspectives(m.personas.length), ev.at);
      }
    }

    function settle(run) { m.done = run.status === "succeeded" ? "done" : "fail"; }

    function draw() {
      const W = 720, H = 340, cx = 250, cy = 172, RX = 178, RY = 114;
      K.view(W, H);
      const researching = m.stage === "research" && !m.done;
      const at = LINE.indexOf(m.stage);
      const after = at >= 0 || m.stage === "normalize" || m.done === "done";

      // the table: the expert in the middle, the personas round it
      const ebox = { x: cx - 64, y: cy - 27, w: 128, h: 54 };
      K.card(layers.nodes, "expert", ebox, {
        kind: "persona", k: K.W.experts, title: K.W.pages(m.pages), sub: researching ? K.W.tree.searching : "",
        state: researching ? "active" : after ? "done" : m.done === "fail" ? "fail" : "idle",
      });
      const fbox = { x: 8, y: 6, w: 150, h: 44 };
      if (m.finding) {
        K.card(layers.nodes, "finder", fbox, { kind: "persona", k: K.W.perspective, title: K.W.persona + " · " + m.personas.length,
          state: m.personas.length ? "done" : m.done ? "fail" : "active" });
      }
      const n = m.personas.length, PW = 128, PH = 42;
      m.personas.forEach((p, i) => {
        const a = -Math.PI / 2 + (i * 2 * Math.PI) / Math.max(n, 1) + (n % 2 ? 0 : Math.PI / n);
        const px = cx + RX * Math.cos(a), py = cy + RY * Math.sin(a);
        const box = { x: px - PW / 2, y: py - PH / 2, w: PW, h: PH };
        K.card(layers.nodes, "p:" + i, box, { kind: "persona", k: K.W.persona, title: p.name, tip: p.about,
          state: researching ? "active" : after ? "done" : m.done === "fail" ? "fail" : "idle", from: fbox });
        // the interview: persona and expert, the line flowing while they talk
        const ex = cx + (px - cx) * 0.3, ey = cy + (py - cy) * 0.3;
        K.edge(layers.edges, "i:" + i, `M${px},${py} L${ex},${ey}`, "persona", researching ? "flow" : "done");
      });
      if (n) {
        const [cap] = layers.nodes.get("cap", "g");
        cap.textContent = "";
        K.text(cap, "label", 8, H - 8, K.W.interview);
      }

      // the line of writers
      const LX = 540, LW = 172, LH = 50, gap = 26;
      const top = (H - (LINE.length + 1) * LH - LINE.length * gap) / 2;
      let prev = ebox;
      LINE.forEach((s, i) => {
        const box = { x: LX, y: top + i * (LH + gap), w: LW, h: LH };
        const st = m.done === "fail" && i === at ? "fail" : i < at || (after && at < 0) || (m.done === "done") ? "done"
          : i === at ? "active" : "idle";
        if (st !== "idle" || m.personas.length) {
          K.card(layers.nodes, "w:" + s, box, { kind: "write", k: K.W.writer, title: K.W[s], state: st,
            from: st === "active" && i === at ? prev : null });
          const from = i === 0 ? { x: ebox.x + ebox.w, y: ebox.y + ebox.h / 2 } : { x: prev.x + LW / 2, y: prev.y + LH };
          const to = i === 0 ? { x: box.x, y: box.y + LH / 2 } : { x: box.x + LW / 2, y: box.y };
          K.edge(layers.edges, "l:" + s, K.curve(from.x, from.y, to.x, to.y, i === 0), "write",
            st === "active" ? "flow" : st === "done" ? "done" : null);
        }
        prev = box;
      });
      if (m.done === "done") {
        const box = { x: LX, y: top + LINE.length * (LH + gap), w: LW, h: LH };
        K.card(layers.nodes, "report", box, { kind: "lead", k: "DeepLit", title: K.W.report, state: "done", from: prev });
        K.edge(layers.edges, "l:report", K.curve(prev.x + LW / 2, prev.y + LH, box.x + LW / 2, box.y, false), "lead", "done");
      }
    }

    return {
      apply, settle, draw,
      empty: () => !m.finding && !m.personas.length,
      stats: () => [[m.personas.length + (m.finding ? 2 : 0) + Math.max(0, LINE.indexOf(m.stage) + 1), K.W.agents],
        [m.personas.length, K.W.perspectives], [m.pages, K.W.sources]],
    };
  }

  function demo() {
    const ev = [];
    const push = (type, data) => ev.push({ type, data });
    push("stage", { stage: "research" });
    push("note", { kind: "perspectives", perspectives: [
      "Basic fact writer: the basic facts of the topic", "Retrieval architect: vector stores, rankers and indexes",
      "Evaluator: how retrieval-augmented generation is measured", "Practitioner: running RAG in products",
      "Skeptic: where RAG fails and why"] });
    for (let i = 0; i < 6; i++) push("note", { kind: "browsed", urls: ["a", "b", "c"] });
    ["outline", "article", "polish"].forEach((s) => push("stage", { stage: s }));
    return { run: { id: "demo", topic: "Retrieval-augmented generation", mode: "STORM", engine: "storm", depth: "standard", language: "en", status: "running" }, events: ev };
  }

  window.DL.scenes.storm = { stages: ["research", "outline", "article", "polish"], create, demo };
})();
