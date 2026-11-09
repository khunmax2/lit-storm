"""A MedicalReviewerAgent review as report.json (docs/adr/0005, 0013).

MRA's result carries more than report.json holds: a literature matrix,
PRISMA counts, pooled estimates with their forest plots, a concept map.
This keeps what reads as a report: the answer, the key findings with their
certainty, the comparison of studies, any pooled estimates, the grade and
its reasons, the gaps, how it was done, and the studies. MRA's own page,
kept beside the report, shows the rest (engines/medical/engine.py).

Each paper is a Source. Its Evidence is the sentences of its abstract that
MRA checked every number against (`outcomes[].evidence_quote`), so the
reader's evidence panel shows where a number came from. MRA cites papers
as [P1, P2]; here they become [1][2], numbered in order of first citation.
"""

import re

from litstorm import report as report_mod

# MRA's markers: [P1], [P1, P3], [P1; P3].
MARKER = re.compile(r"\[\s*(P\d+(?:\s*[,;]\s*P\d+)*)\s*\]")

WORDS = {
    "en": {
        "key_findings": "Key findings", "summary": "Discussion", "comparison": "Comparison of studies",
        "consensus": "Where studies agree", "conflicts": "Where studies disagree", "pooled": "Pooled analysis",
        "certainty": "Certainty of the evidence", "gaps": "Research gaps", "methods": "How this review was done",
        "studies": "Studies included", "outcome": "Outcome", "study": "Study", "finding": "Finding",
        "effect": "Effect", "certainty_of": "certainty", "k": "studies", "question": "Question as reviewed",
        "framework": "Framework", "assumptions": "Assumptions", "sources": "Sources searched (records)",
        "screening": "Screening", "found": "found", "screened": "screened", "selected": "selected",
        "searched_at": "Searched", "model": "Synthesis model", "pooled_note":
            "Computed by MRA from numbers verified in the abstracts, not the result of any one study.",
        "levels": {"high": "high", "moderate": "moderate", "low": "low", "very_low": "very low"},
        "type": {"slr": "systematic review", "meta_analysis": "meta-analysis", "scoping": "scoping review",
                 "narrative": "narrative review"},
        "quick": "Quick answer", "design": "design", "n": "n",
    },
    "th": {
        "key_findings": "ข้อค้นพบหลัก", "summary": "อภิปรายผล", "comparison": "เปรียบเทียบงานวิจัย",
        "consensus": "จุดที่งานวิจัยสอดคล้องกัน", "conflicts": "จุดที่งานวิจัยขัดแย้งกัน", "pooled": "ผลการวิเคราะห์อภิมาน",
        "certainty": "ความน่าเชื่อถือของหลักฐาน", "gaps": "ช่องว่างงานวิจัย", "methods": "วิธีการทบทวน",
        "studies": "งานวิจัยที่รวมไว้", "outcome": "ผลลัพธ์", "study": "งานวิจัย", "finding": "ผลที่พบ",
        "effect": "ขนาดผล", "certainty_of": "ความน่าเชื่อถือ", "k": "งานวิจัย", "question": "คำถามที่ใช้ทบทวน",
        "framework": "กรอบคำถาม", "assumptions": "ข้อสมมติ", "sources": "แหล่งที่ค้น (จำนวนรายการ)",
        "screening": "การคัดกรอง", "found": "พบ", "screened": "คัดกรอง", "selected": "คัดเลือก",
        "searched_at": "วันที่ค้น", "model": "โมเดลที่ใช้สังเคราะห์", "pooled_note":
            "MRA คำนวณจากตัวเลขที่ตรวจกับบทคัดย่อแล้ว ไม่ใช่ผลของงานวิจัยชิ้นใดชิ้นหนึ่ง",
        "levels": {"high": "สูง", "moderate": "ปานกลาง", "low": "ต่ำ", "very_low": "ต่ำมาก"},
        "type": {"slr": "การทบทวนวรรณกรรมอย่างเป็นระบบ", "meta_analysis": "การวิเคราะห์อภิมาน",
                 "scoping": "การทบทวนขอบเขต", "narrative": "การทบทวนเชิงบรรยาย"},
        "quick": "คำตอบแบบเร็ว", "design": "รูปแบบ", "n": "n",
    },
}
PICO = {"population": "P", "intervention_or_exposure": "I", "comparator": "C", "outcomes": "O"}


class _Refs:
    """MRA's paper refs (P1...) to Source ids, in order of first citation."""

    def __init__(self):
        self.ids = {}

    def id(self, ref):
        if ref not in self.ids:
            self.ids[ref] = len(self.ids) + 1
        return self.ids[ref]

    def marks(self, refs):
        return "".join(f"[{self.id(r)}]" for r in refs)

    def text(self, value):
        """MRA's text with its markers in this report's form."""
        return MARKER.sub(lambda m: self.marks(re.split(r"\s*[,;]\s*", m.group(1))), value or "")


def _num(value):
    if value is None:
        return ""
    return f"{value:g}" if isinstance(value, float) else str(value)


def _effect(measure, value, low, high):
    if value is None:
        return ""
    ci = f" (95% CI {_num(low)}–{_num(high)})" if low is not None and high is not None else ""
    return f"{measure or ''} {_num(value)}{ci}".strip()


def _cell(text):
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def _section(n, heading, body):
    return {"id": f"s{n}", "heading": heading, "body": body.strip(), "children": []}


def to_report(review, language, topic):
    """report.json from MRA's `GET /reviews/{id}` answer."""
    w = WORDS.get(language, WORDS["en"])
    result = review.get("result") or {}
    synthesis = result.get("synthesis") or {}
    papers = {p["ref"]: p for p in result.get("papers") or [] if p.get("ref")}
    refs = _Refs()
    quick = result.get("mode") == "quick"
    level = synthesis.get("evidence_strength") or synthesis.get("grade_baseline")

    lead = refs.text(result.get("summary") if quick else synthesis.get("answer") or result.get("summary"))
    sections = []

    def add(heading, body):
        if body and body.strip():
            sections.append(_section(len(sections) + 1, heading, body))

    findings = []
    for f in synthesis.get("key_findings") or []:
        tail = []
        if f.get("certainty"):
            tail.append(f"{w['certainty_of']}: {w['levels'].get(f['certainty'], f['certainty'])}")
        if f.get("k"):
            tail.append(f"k={f['k']}")
        extra = f" ({'; '.join(tail)})" if tail else ""
        findings.append(f"- **{f.get('outcome', '')}**: {refs.text(f.get('statement'))} {refs.marks(f.get('refs') or [])}{extra}")
    add(w["key_findings"], "\n".join(findings))

    if not quick and synthesis.get("executive_summary") and synthesis.get("executive_summary") != synthesis.get("answer"):
        add(w["summary"], refs.text(synthesis["executive_summary"]))

    rows = []
    for row in synthesis.get("comparison") or []:
        for cell in row.get("cells") or []:
            rows.append(f"| {_cell(row.get('outcome'))} | {refs.marks([cell['ref']])} | {_cell(cell.get('finding'))} | "
                        f"{_cell(_effect(cell.get('effect_measure'), cell.get('effect_value'), cell.get('ci_lower'), cell.get('ci_upper')))} |")
    if rows:
        add(w["comparison"], f"| {w['outcome']} | {w['study']} | {w['finding']} | {w['effect']} |\n|---|---|---|---|\n"
            + "\n".join(dict.fromkeys(rows)))

    for key in ("consensus", "conflicts"):
        items = [f"- {refs.text(c.get('statement'))} {refs.marks(c.get('refs') or [])}"
                 + (f" — {refs.text(c['explanation'])}" if c.get("explanation") else "")
                 for c in synthesis.get(key) or [] if isinstance(c, dict)]
        add(w[key], "\n".join(items))

    pools = ((result.get("meta_analysis") or {}).get("pools")) or []
    lines = []
    for pool in pools:
        est = pool.get("pooled") or {}
        studies = [s["ref"] for s in pool.get("studies") or [] if s.get("ref")]
        lines.append(f"- **{pool.get('outcome_display') or pool.get('outcome', '')}**: "
                     f"{_effect(pool.get('measure'), est.get('est'), est.get('ci_lower'), est.get('ci_upper'))}, "
                     f"I² {_num(pool.get('i2'))}%, k={pool.get('k')} {refs.marks(studies)}")
    if lines:
        add(w["pooled"], f"{w['pooled_note']}\n\n" + "\n".join(lines))

    if level or synthesis.get("evidence_rationale"):
        head = f"**{w['levels'].get(level, level)}**" if level else ""
        add(w["certainty"], "\n\n".join(x for x in (head, refs.text(synthesis.get("answer")) if quick else "",
                                                    refs.text(synthesis.get("evidence_rationale"))) if x))

    add(w["gaps"], "\n".join(f"- {refs.text(g)}" for g in synthesis.get("research_gaps") or [] if g))

    add(w["methods"], _methods(result, review, w))

    # Every paper is a Source, so every one is cited here at least.
    listed = []
    for ref, paper in papers.items():
        card = paper.get("card") or {}
        bits = [b for b in (card.get("study_design"), f"{w['n']}={card['sample_size']}" if card.get("sample_size") else "",
                            paper.get("journal"), str(paper["year"]) if paper.get("year") else "") if b]
        listed.append(f"- {refs.marks([ref])} {paper.get('title', '')}" + (f" — {', '.join(bits)}" if bits else ""))
    add(w["studies"], "\n".join(listed))

    sources = []
    for ref, n in sorted(refs.ids.items(), key=lambda kv: kv[1]):
        paper = papers.get(ref)
        if paper is None:
            continue
        sources.append(_source(n, paper))
    report = {
        "schema": report_mod.SCHEMA, "engine": "medical", "title": topic, "language": language,
        "lead": lead, "sections": sections, "sources": sources,
    }
    return _drop_dangling(report, {s["id"] for s in sources})


def _methods(result, review, w):
    question = result.get("question") or {}
    out = []
    kind = w["type"].get(result.get("review_type"), result.get("review_type") or "")
    if result.get("mode") == "quick":
        kind = f"{w['quick']} ({kind})" if kind else w["quick"]
    if kind:
        out.append(f"**{kind}**")
    if question.get("refined_question"):
        out.append(f"**{w['question']}:** {question['refined_question']}")
    pico = question.get("pico") or {}
    parts = []
    for key, letter in PICO.items():
        value = pico.get(key)
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value if v)
        if value:
            parts.append(f"{letter}: {value}")
    if parts:
        out.append(f"**{w['framework']} ({question.get('framework') or 'PICO'}):** " + " · ".join(parts))
    if question.get("assumptions"):
        out.append(f"**{w['assumptions']}:** " + "; ".join(question["assumptions"]))
    methods = result.get("methods") or {}
    counts = methods.get("sources") or {}
    if counts:
        out.append(f"**{w['sources']}:** " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    stats = result.get("stats") or {}
    if stats:
        out.append(f"**{w['screening']}:** {w['found']} {stats.get('found', 0)} → {w['screened']} {stats.get('screened', 0)}"
                   f" → {w['selected']} {stats.get('selected', 0)}")
    if methods.get("searched_at"):
        out.append(f"**{w['searched_at']}:** {methods['searched_at'][:10]}")
    model = (methods.get("synthesis") or {}).get("model")
    if model:
        out.append(f"**{w['model']}:** {model}")
    return "\n\n".join(out)


def _source(n, paper):
    authors = paper.get("authors") or []
    byline = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
    bits = [b for b in (byline, paper.get("journal"), str(paper["year"]) if paper.get("year") else "") if b]
    url = paper.get("url") or (f"https://doi.org/{paper['doi']}" if paper.get("doi") else "") \
        or (f"https://pubmed.ncbi.nlm.nih.gov/{paper['pmid']}/" if paper.get("pmid") else "")
    quotes = [o.get("evidence_quote", "").strip() for o in (paper.get("card") or {}).get("outcomes") or []]
    return {
        "id": n, "url": url, "title": paper.get("title") or url, "description": " · ".join(bits),
        "evidence": list(dict.fromkeys(q for q in quotes if q)),
    }


def _drop_dangling(report, kept):
    """A marker for a paper MRA did not return is removed rather than left to fail validation."""
    def clean(text):
        return report_mod.CITATION.sub(lambda m: m.group(0) if int(m.group(1)) in kept else "", text or "")

    report["lead"] = clean(report["lead"])
    for section in report_mod.walk(report["sections"]):
        section["body"] = clean(section["body"])
    return report
