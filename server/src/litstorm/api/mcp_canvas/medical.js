// Medical Review: MedicalReviewerAgent's review as it goes. Five stations across the top (frame the
// question, search, screen, read and check numbers, synthesize), the one at work ringing and the line to it
// flowing; under them the question as MRA framed it, the records found and the screening funnel; then a card
// per paper, spawned from the reading station as MRA starts it, done when its numbers are checked, faded when
// it had none, marked when two models disagreed. Fed by the Run's "medical" notes: MRA's own events
// (engines/medical/engine.py).
(() => {
  const STEPS = ["refine", "search", "screen", "read", "synthesize"];
  const STEP_OF = {
    checking_topic: 0, refining: 0, question_refined: 0, planning: 1, searching: 1, enriching: 1,
    screening: 2, screened: 2, external_lookup: 3, citations_fetched: 3, reading: 3, extracted: 3,
    synthesizing: 4, pooled: 4, localizing: 4, finalizing: 4, done: 5, error: 5, rejected: 5, cancelled: 5,
  };

  function create(K, layers) {
    const m = { step: -1, question: "", queries: 0, found: null, screened: null, papers: [], pools: null, done: null };
    const paper = (ref) => {
      let p = m.papers.find((x) => x.ref === ref);
      if (!p) m.papers.push((p = { ref, title: ref, done: false }));
      return p;
    };

    function apply(ev) {
      const d = ev.data || {};
      if (ev.type !== "note" || d.kind !== "medical") return;
      if (STEP_OF[d.event] != null) m.step = Math.max(m.step, STEP_OF[d.event]);
      switch (d.event) {
        case "question_refined":
          m.question = d.refined_question || d.interpretation || "";
          K.say("plan", m.question, ev.at);
          break;
        case "planning": m.queries = (d.queries || []).length; break;
        case "searching": m.found = d.found; K.say("research", K.W.med.records(d.found), ev.at); break;
        case "screened":
          m.screened = { kept: d.kept, total: d.total };
          K.say("research", `${K.W.med.screen}: ${K.W.med.kept(d.kept, d.total)}`, ev.at);
          break;
        case "reading": paper(d.ref).title = d.title || d.ref; break;
        case "extracted":
          Object.assign(paper(d.ref), { done: true, ok: d.ok, verified: d.verified || 0, uncertain: d.uncertain, design: d.design });
          break;
        case "pooled": m.pools = d.pools; break;
        case "done": case "error": case "rejected": case "cancelled":
          m.done = d.event === "done" ? "done" : "fail";
          break;
      }
    }

    function settle(run) { m.done = run.status === "succeeded" ? "done" : "fail"; }

    function draw() {
      const W = 720, SW = 128, SH = 46, GAP = (W - 16 - SW * 5) / 4;
      const PW = 172, PH = 40, PCOLS = 4, top = 130;
      const rows = Math.ceil(m.papers.length / PCOLS);
      const H = Math.max(200, top + rows * (PH + 8) + 12);
      K.view(W, H, 1400);

      const at = (i) => ({ x: 8 + i * (SW + GAP), y: 8, w: SW, h: SH });
      STEPS.forEach((s, i) => {
        const state = m.done === "fail" && i === m.step ? "fail"
          : i < m.step || m.done === "done" ? "done" : i === m.step && !m.done ? "active" : "idle";
        K.card(layers.nodes, "st:" + s, at(i), { kind: i === 3 ? "research" : i === 4 ? "write" : "plan", title: K.W.med[s], state });
        if (i > 0) {
          const a = at(i - 1), b = at(i);
          K.edge(layers.edges, "e:" + s, `M${a.x + SW},${a.y + SH / 2} L${b.x},${b.y + SH / 2}`, "plan",
            state === "active" ? "flow" : state === "done" ? "done" : null);
        }
      });

      // The question and the funnel, under the stations.
      const [info] = layers.nodes.get("info", "g");
      info.textContent = "";
      if (m.question) {
        K.text(info, "label", 8, 76, K.W.med.question);
        K.text(info, "t", 8, 94, K.fit(m.question, W - 16));
      }
      const funnel = [m.found != null ? K.W.med.records(m.found) : "", m.screened ? K.W.med.kept(m.screened.kept, m.screened.total) : "",
        m.pools != null ? K.W.med.pools(m.pools) : ""].filter(Boolean).join(" · ");
      if (funnel) K.text(info, "badge", 8, 114, funnel);

      // A card per paper, spawned from the reading station.
      const reader = at(3);
      m.papers.forEach((p, i) => {
        const box = { x: 8 + (i % PCOLS) * (PW + 8), y: top + Math.floor(i / PCOLS) * (PH + 8), w: PW, h: PH };
        const sub = p.done ? [p.verified ? K.W.med.checked(p.verified) : K.W.med.noNumbers, p.uncertain ? K.W.med.disagreed : ""]
          .filter(Boolean).join(" · ") : "";
        K.card(layers.nodes, "p:" + p.ref, box, {
          kind: "research", title: `${p.ref} ${p.title}`, sub, subBadge: true, tip: p.title,
          state: !p.done ? (m.done ? "fail" : "active") : p.ok === false ? "fail" : p.verified ? "done" : "muted",
          from: reader,
        });
      });
    }

    return {
      apply, settle, draw,
      empty: () => m.step < 0,
      stats: () => [[m.papers.length, K.W.med.papers], [m.papers.reduce((a, p) => a + (p.verified || 0), 0), K.W.med.numbers],
        [m.found || 0, K.W.sources]],
    };
  }

  function demo() {
    const ev = [];
    const note = (event, data = {}) => ev.push({ type: "note", data: { kind: "medical", event, ...data } });
    const stage = (s) => ev.push({ type: "stage", data: { stage: s } });
    stage("refine");
    note("checking_topic"); note("refining");
    note("question_refined", { refined_question: "In older adults, does exercise versus usual care reduce depressive symptoms?" });
    stage("search");
    note("planning", { queries: ["exercise depression older adults RCT", "resistance training depressive symptoms elderly"] });
    note("searching", { found: 354 }); note("enriching", { candidates: 120 });
    stage("screen");
    note("screening", { batch: 1 }); note("screened", { kept: 8, total: 120 });
    stage("read");
    const titles = ["Aerobic and resistance training on depression: a meta-analysis", "Floor-seated exercise in older adults: a cluster RCT",
      "Resistance training and quality of life in adults over 60", "Exercise for depression: a network meta-analysis",
      "Physical activity as a treatment for depression in the elderly", "Exercise in mild to moderate depression",
      "A live online exercise programme: a pilot RCT", "Dual-task resistance exercise in cognitive impairment"];
    titles.forEach((title, i) => note("reading", { ref: `P${i + 1}`, title }));
    titles.forEach((_, i) => note("extracted", { ref: `P${i + 1}`, ok: true, verified: [2, 1, 2, 2, 0, 3, 1, 1][i], uncertain: i === 4 }));
    stage("synthesize");
    note("synthesizing", { papers: 8 }); note("localizing"); note("finalizing"); note("done", { cost_usd: 0.09 });
    return { run: { id: "demo", topic: "Exercise and depression in older adults", mode: "Medical Review", engine: "medical", depth: "full", language: "en", status: "running" }, events: ev };
  }

  window.DL.scenes.medical = { stages: ["refine", "search", "screen", "read", "synthesize"], create, demo };
})();
