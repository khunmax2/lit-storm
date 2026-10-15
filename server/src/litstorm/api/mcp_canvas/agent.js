// Agent Research: its loop. Four stations round a ring (observe, find the gap, choose tools,
// search and read), a dot orbiting to the one at work, the search agents each round sends out
// spawning beside it, and the writer once the gap agent says enough is known. At depth deep a
// planner first splits the topic: then one row per section, each with a small ring of its own.
// Fed by the Run's "flow" notes (server: engines/agent/flow.py).
(() => {
  const STEPS = ["observe", "gap", "select", "search"];

  function create(K, layers) {
    const m = { sections: [], lanes: new Map(), composing: false, planning: false, searches: 0, sources: 0, spawned: 0, done: null };
    const lane = (id = "main") => {
      if (!m.lanes.has(id)) {
        const s = m.sections.find((x) => x.id === id);
        m.lanes.set(id, { id, title: s ? s.title : null, round: 0, max: 0, phase: null, observed: "", gap: "", complete: false,
          queries: [], found: null, total: 0, writing: false });
      }
      return m.lanes.get(id);
    };
    const name = (l) => l.title || K.W.researcher;

    function apply(ev) {
      const d = ev.data || {};
      if (ev.type === "stage") { if (d.stage === "plan") m.planning = true; return; }
      if (ev.type !== "note") return;
      if (d.kind === "browsed") { m.sources += (d.urls || []).length; return; }
      if (d.kind !== "flow") return;
      const l = d.event === "plan" || d.event === "compose" ? null : lane(d.lane);
      switch (d.event) {
        case "plan":
          m.sections = (d.sections || []).map((s) => ({ id: s.id, title: K.clip(s.title, 60) }));
          m.sections.forEach((s) => { lane(s.id).title = s.title; });
          m.spawned += m.sections.length;
          K.say("plan", K.W.log.plan(m.sections.length), ev.at);
          break;
        case "round":
          Object.assign(l, { round: d.round, max: d.max, phase: "observe", queries: [], found: null, gap: "", complete: false });
          break;
        case "phase": l.phase = d.phase; break;
        case "observed": l.observed = d.text || ""; break;
        case "gap":
          l.gap = d.gap || ""; l.complete = !!d.complete;
          if (d.complete) K.say("research", K.W.log.complete(name(l)), ev.at);
          else if (d.gap) K.say("research", K.W.log.gap(name(l), K.clip(d.gap, 110)), ev.at);
          break;
        case "tasks":
          l.queries = d.queries || [];
          m.searches += l.queries.length; m.spawned += l.queries.length;
          if (l.queries.length) K.say("tool", K.W.log.tasks(name(l), l.queries.length), ev.at);
          break;
        case "found":
          l.found = d.sources || 0; l.total += l.found;
          K.say("tool", K.W.log.found(name(l), l.found), ev.at);
          break;
        case "write":
          l.writing = true; l.phase = "write"; m.spawned += 1;
          K.say("write", K.W.log.write(name(l)), ev.at);
          break;
        case "compose":
          m.composing = true; m.spawned += 1;
          K.say("write", K.W.log.compose, ev.at);
          break;
      }
    }

    function settle(run) { m.done = run.status === "succeeded" ? "done" : "fail"; }

    // A ring of four dots, the one at work lit, an arc turning while it works.
    function ring(g, cx, cy, r, l, live, big) {
      const step = STEPS.indexOf(l.phase);
      K.el("circle", { class: "track" + (live ? " live" : ""), cx, cy, r, style: "--c: var(--research)" }, g);
      if (live) K.el("circle", { class: "spin", cx, cy, r: r - (big ? 9 : 5), "stroke-dasharray": `${r * 0.9} ${r * 9}`,
        style: "--c: var(--research)" }, g);
      STEPS.forEach((s, i) => {
        const a = (i * Math.PI) / 2 - Math.PI / 2;
        const cls = l.writing || m.done === "done" ? "dot done" : i < step ? "dot done" : i === step ? "dot now" : "dot";
        K.el("circle", { class: cls, cx: cx + r * Math.cos(a), cy: cy + r * Math.sin(a), r: big ? 7 : 3.5, style: "--c: var(--research)" }, g);
      });
    }

    // One loop: stations on a circle round the hub.
    function drawLoop(l) {
      const live = !m.done && !l.writing;
      const W = 720, H = 352, cx = 330, cy = 176, R = 104;
      K.view(W, H);
      const [hub] = layers.nodes.get("hub", "g");
      hub.textContent = "";
      ring(hub, cx, cy, R, l, live, true);
      // the dot that orbits to the station at work, always onwards, round after round
      const step = Math.max(0, STEPS.indexOf(l.phase));
      const turns = Math.max(0, l.round - 1) * 360 + step * 90 + (l.writing ? 90 : 0);
      const [orbit] = layers.nodes.get("orbit", "g");
      orbit.setAttribute("class", "orbit");
      orbit.style.setProperty("--c", "var(--research)");
      orbit.style.transformOrigin = `${cx}px ${cy}px`;
      orbit.style.transform = `rotate(${turns}deg)`;
      if (!orbit.firstChild) K.el("circle", { cx, cy: cy - R, r: 6 }, orbit);
      orbit.style.display = live ? "" : "none";
      K.text(hub, "hub-n", cx, cy + 2, l.round ? `${l.round}/${l.max || "?"}` : "–");
      K.text(hub, "hub-s", cx, cy + 18, l.writing ? K.W.phase.write : l.round ? K.W.roundShort + " · " + (K.W.phase[l.phase] || "") : K.W.waiting);

      const CW = 158, CH = 56;
      const boxes = {
        observe: { x: cx - CW / 2, y: cy - R - CH - 10, w: CW, h: CH },
        gap: { x: cx + R + 16, y: cy - CH / 2, w: CW, h: CH },
        select: { x: cx - CW / 2, y: cy + R + 10, w: CW, h: CH },
        search: { x: cx - R - 16 - CW, y: cy - CH / 2, w: CW, h: CH },
      };
      const detail = {
        observe: l.observed,
        gap: l.complete ? K.W.complete : l.gap,
        select: l.queries.length ? K.W.queries(l.queries.length) : "",
        search: l.found != null ? K.W.found(l.found) : "",
      };
      STEPS.forEach((s, i) => {
        const state = l.writing || m.done === "done" ? "done" : m.done === "fail" && s === l.phase ? "fail"
          : s === l.phase ? "active" : !l.round ? "idle" : i < step ? "done" : "idle";
        K.card(layers.nodes, "st:" + s, boxes[s], {
          kind: s === "search" ? "tool" : s === "select" ? "plan" : "research",
          k: K.W.captions[s], title: K.W.steps[s], sub: detail[s], state, tip: detail[s],
        });
      });
      // the search agents of this round, spawned from the search station
      const qs = l.queries.slice(0, 3);
      qs.forEach((q, i) => {
        const box = { x: boxes.search.x, y: boxes.search.y + CH + 12 + i * 32, w: CW, h: 28 };
        const g = K.card(layers.nodes, `tool:${l.id}:${l.round}:${i}`, box, {
          kind: "tool", title: K.clip(q.query, 40), state: l.found != null || l.writing ? "done" : "active",
          from: boxes.search, tip: (q.agent === "crawl" ? K.W.crawl : K.W.search) + (q.site ? " · " + q.site : ""),
        });
        g.classList.add("pill");
      });
      if (l.queries.length > 3) K.text(layers.nodes.get("more", "g")[0], "label", boxes.search.x + CW + 6, boxes.search.y + CH + 12 + 2 * 32 + 18, `+${l.queries.length - 3}`);
      else layers.nodes.get("more", "g")[0].textContent = "";
      // the writer, out of the loop once the gap agent says enough
      const wbox = { x: W - 128, y: cy + R - 14, w: 118, h: CH };
      if (l.writing) {
        K.card(layers.nodes, "writer", wbox, { kind: "write", k: K.W.captions.write, title: K.W.writer,
          state: m.done ? (m.done === "done" ? "done" : "fail") : "active", from: boxes.gap });
        K.edge(layers.edges, "gap>writer", K.curve(boxes.gap.x + CW / 2, boxes.gap.y + CH, wbox.x + 59, wbox.y, false), "write",
          m.done ? "done" : "flow");
      }
    }

    // The deep level: the planner, one row per section with its ring, the long writer.
    function drawSections() {
      const rows = m.sections.length, RH = 52, top = 30;
      const W = 720, H = Math.max(200, top + rows * RH + 20);
      K.view(W, H, 900);
      const mid = top + (rows * RH) / 2 - 24;
      const pbox = { x: 8, y: mid, w: 128, h: 48 };
      K.card(layers.nodes, "planner", pbox, { kind: "plan", k: K.W.planner, title: K.W.sections + " · " + rows, state: m.done === "fail" ? "fail" : "done" });
      const cbox = { x: W - 128, y: mid, w: 120, h: 48 };
      K.card(layers.nodes, "compose", cbox, { kind: "write", k: K.W.captions.write, title: K.W.compose,
        state: m.composing ? (m.done ? (m.done === "done" ? "done" : "fail") : "active") : "idle" });
      m.sections.forEach((s, i) => {
        const l = lane(s.id), y = top + i * RH;
        const live = !m.done && !l.writing && !m.composing && l.round > 0;
        const box = { x: 160, y, w: 252, h: 42 };
        const sub = m.done && l.round ? K.W.round(l.round, l.max) : l.writing ? K.W.phase.write
          : l.round ? `${K.W.round(l.round, l.max)} · ${K.W.phase[l.phase] || ""}` : "…";
        K.card(layers.nodes, "lane:" + s.id, box, { kind: "research", title: s.title, sub, subBadge: true,
          state: m.done === "fail" && !l.writing ? "fail" : l.writing || m.done ? "done" : live ? "active" : "idle", from: pbox });
        const [g] = layers.nodes.get("ring:" + s.id, "g");
        g.textContent = "";
        ring(g, 438, y + 21, 15, l, live, false);
        K.text(g, "label", 460, y + 25, K.W.found(l.total));
        // this round's search agents, as dots spawning after the ring
        l.queries.slice(0, 5).forEach((q, j) => {
          const [dot, born] = layers.nodes.get(`q:${s.id}:${l.round}:${j}`, "circle");
          dot.setAttribute("cx", 528 + j * 11); dot.setAttribute("cy", y + 21); dot.setAttribute("r", 4);
          dot.setAttribute("class", "dot " + (l.found != null || l.writing ? "done" : "now"));
          dot.style.setProperty("--c", "var(--tool)");
          if (born) K.burst(438, y + 21, "tool");
        });
        K.edge(layers.edges, "p>" + s.id, K.curve(pbox.x + pbox.w, pbox.y + 24, box.x, y + 21), "research", live ? "flow" : "done");
        K.edge(layers.edges, s.id + ">c", K.curve(box.x + box.w + 172, y + 21, cbox.x, cbox.y + 24), "write",
          m.composing && !m.done ? "flow" : l.writing ? "done" : null);
      });
    }

    function draw() {
      if (m.sections.length) drawSections();
      else drawLoop(lane("main"));
    }

    return {
      apply, settle, draw,
      empty: () => !m.planning && !m.lanes.size,
      stats: () => {
        const rounds = Math.max(0, ...[...m.lanes.values()].map((l) => l.round));
        return [[m.spawned, K.W.agents], [m.sources, K.W.sources], [m.searches, K.W.searches], [rounds, K.W.rounds]];
      },
    };
  }

  function demo(variant) {
    const ev = [];
    const push = (type, data) => ev.push({ type, data });
    if (variant === "sections") return sections(ev, push);
    push("stage", { stage: "research" });
    for (let r = 1; r <= 3; r++) {
      push("note", { kind: "flow", event: "round", lane: "main", round: r, max: 3 });
      push("note", { kind: "flow", event: "phase", lane: "main", round: r, phase: "observe" });
      push("note", { kind: "flow", event: "observed", lane: "main", round: r, text: "Durian exports grew fast; prices swing with Chinese demand and border checks." });
      push("note", { kind: "flow", event: "phase", lane: "main", round: r, phase: "gap" });
      push("note", { kind: "flow", event: "gap", lane: "main", round: r, gap: r === 1 ? "Current export volumes by province" : "Effect of new GACC inspection rules", complete: r === 3 });
      if (r === 3) break;
      push("note", { kind: "flow", event: "phase", lane: "main", round: r, phase: "select" });
      push("note", { kind: "flow", event: "tasks", lane: "main", round: r, queries: [
        { agent: "search", query: `Thai durian exports ${2024 + r}` }, { agent: "search", query: "Chanthaburi durian prices" },
        { agent: "crawl", query: "Customs export statistics", site: "customs.go.th" }] });
      push("note", { kind: "flow", event: "phase", lane: "main", round: r, phase: "search" });
      push("note", { kind: "browsed", urls: ["a", "b", "c", "d"] });
      push("note", { kind: "flow", event: "found", lane: "main", round: r, sources: 4 + r });
    }
    push("note", { kind: "flow", event: "write", lane: "main" });
    push("stage", { stage: "report" });
    return { run: { id: "demo", topic: "Thai durian exports to China", mode: "Agent Research", engine: "agent", depth: "standard", language: "en", status: "running" }, events: ev };
  }

  // depth deep: a planner, three sections researched at once, then the long writer
  function sections(ev, push) {
    const lanes = [["s1", "Climate and soil"], ["s2", "Pests and diseases"], ["s3", "Markets and prices"]];
    push("stage", { stage: "plan" });
    push("note", { kind: "flow", event: "plan", sections: lanes.map(([id, title]) => ({ id, title })) });
    push("stage", { stage: "research" });
    for (let r = 1; r <= 2; r++) {
      lanes.forEach(([lane]) => {
        push("note", { kind: "flow", event: "round", lane, round: r, max: 2 });
        push("note", { kind: "flow", event: "phase", lane, round: r, phase: "observe" });
      });
      lanes.forEach(([lane], i) => {
        push("note", { kind: "flow", event: "phase", lane, round: r, phase: "gap" });
        push("note", { kind: "flow", event: "gap", lane, round: r, gap: "What is still unknown", complete: r === 2 });
        if (r === 2) return;
        push("note", { kind: "flow", event: "tasks", lane, round: r, queries: [{ agent: "search", query: "query A" },
          { agent: "search", query: "query B" }, { agent: i ? "search" : "crawl", query: "query C", site: i ? null : "doa.go.th" }] });
        push("note", { kind: "flow", event: "phase", lane, round: r, phase: "search" });
      });
      if (r === 2) break;
      lanes.forEach(([lane]) => {
        push("note", { kind: "browsed", urls: ["a", "b", "c"] });
        push("note", { kind: "flow", event: "found", lane, round: r, sources: 3 });
      });
    }
    lanes.forEach(([lane]) => push("note", { kind: "flow", event: "write", lane }));
    push("note", { kind: "flow", event: "compose" });
    push("stage", { stage: "report" });
    return { run: { id: "demo", topic: "Mangosteen farming in Eastern Thailand", mode: "Agent Research", engine: "agent", depth: "deep", language: "en", status: "running" }, events: ev };
  }

  window.DL.scenes.agent = { stages: ["plan", "research", "report"], create, demo };
})();
