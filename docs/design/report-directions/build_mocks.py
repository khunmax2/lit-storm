"""Throwaway: four design directions for the interactive report, on the real
durian report. Static mockups for choosing — not the renderer."""
import html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "..", "sample-report.json"), encoding="utf-8"))
E = html.escape


def cites(text, cls="c"):
    return re.sub(r"\[(\d+)\]", lambda m: f'<sup class="{cls}">{m.group(1)}</sup>', E(text))


LEAD = [p.strip() for p in R["lead"].split("\n\n") if p.strip()]
TITLE = R["title"]
SRC = {s["id"]: s for s in R["sources"]}
HOST = lambda u: re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
SECTIONS = []


def walk(s, depth=0, prefix=""):
    for i, x in enumerate(s, 1):
        n = f"{prefix}.{i}" if prefix else str(i)
        SECTIONS.append((depth, n, x["heading"], x["body"]))
        walk(x["children"], depth + 1, n)


walk(R["sections"])
BODY1 = next(b for d, n, h, b in SECTIONS if b.strip())
PARAS = [p for p in BODY1.split("\n\n") if p.strip()]

FONTS = """
@font-face{font-family:'LS Latin';src:url(fonts/geist-latin-wght-normal.woff2) format('woff2');font-weight:100 900;unicode-range:U+0000-00FF,U+2000-206F}
@font-face{font-family:'LS Thai';src:url(fonts/ibm-plex-sans-thai-thai-400-normal.woff2) format('woff2');font-weight:400;unicode-range:U+0E01-0E5B,U+200C-200D}
@font-face{font-family:'LS Thai';src:url(fonts/ibm-plex-sans-thai-thai-600-normal.woff2) format('woff2');font-weight:500 700;unicode-range:U+0E01-0E5B,U+200C-200D}
@font-face{font-family:'LS Serif Latin';src:url(fonts/instrument-serif-latin-400-normal.woff2) format('woff2');font-weight:400;unicode-range:U+0000-00FF,U+2000-206F}
@font-face{font-family:'LS Serif Thai';src:url(fonts/noto-serif-thai-thai-wght-normal.woff2) format('woff2');font-weight:100 900;unicode-range:U+0E01-0E5B,U+200C-200D}
:root{--sans:'LS Latin','LS Thai',sans-serif;--serif:'LS Serif Latin','LS Serif Thai',serif}
*{box-sizing:border-box}body{margin:0;font-family:var(--sans);-webkit-font-smoothing:antialiased}
"""

POLLEN = [("0 °C", 36), ("5 °C", 28), ("25 °C", 6)]


def hbars(color, track, ink, width=560, label_w=70, unit="วัน", annotate=True):
    rows = []
    for i, (k, v) in enumerate(POLLEN):
        w = (width - label_w - 70) * v / 36
        y = 14 + i * 46
        rows.append(
            f'<text x="0" y="{y + 19}" font-size="14" fill="{ink}" font-family="LS Latin">{k}</text>'
            f'<rect x="{label_w}" y="{y}" width="{width - label_w - 70}" height="28" rx="6" fill="{track}"/>'
            f'<rect x="{label_w}" y="{y}" width="{w:.0f}" height="28" rx="6" fill="{color}"/>'
            f'<text x="{label_w + w + 10:.0f}" y="{y + 20}" font-size="15" font-weight="600" fill="{ink}" font-family="LS Latin,LS Thai">{v} {unit}</text>'
        )
    note = (f'<text x="{label_w}" y="166" font-size="12" fill="{ink}" opacity=".65" font-family="LS Thai">ยิ่งเย็น ละอองเรณูยิ่งเก็บได้นาน — 0 °C นานกว่า 25 °C ราว 6 เท่า</text>' if annotate else "")
    return f'<svg viewBox="0 0 {width} 176" width="100%" role="img">{"".join(rows)}{note}</svg>'


# ---------------------------------------------------------------- A · Editorial
A = f"""<!doctype html><html lang="th"><head><meta charset="utf-8"><style>{FONTS}
body{{background:#FBF8F1;color:#1C1B19}}
.hero{{padding:72px 0 40px;text-align:center;border-bottom:1px solid #E7DFCF;background:
 radial-gradient(60rem 22rem at 50% 0%,#F3E3C8 0%,transparent 70%)}}
.kicker{{font-size:13px;letter-spacing:.18em;text-transform:uppercase;color:#B4461A;font-weight:600}}
h1{{font-family:var(--serif);font-weight:400;font-size:84px;line-height:1.05;margin:18px auto 22px;max-width:1000px;letter-spacing:-.01em}}
.deck{{font-family:var(--serif);font-size:24px;line-height:1.6;color:#4A4640;max-width:760px;margin:0 auto}}
.byline{{margin-top:28px;font-size:14px;color:#77716A;display:flex;gap:18px;justify-content:center}}
.byline b{{color:#1C1B19}}
.wrap{{max-width:680px;margin:0 auto;padding:48px 0}}
p{{font-size:19px;line-height:2;margin:0 0 26px;color:#2B2925}}
.drop::first-letter{{font-family:var(--serif);float:left;font-size:92px;line-height:.9;padding:6px 12px 0 0;color:#B4461A}}
.pull{{font-family:var(--serif);font-size:34px;line-height:1.45;color:#B4461A;margin:44px -90px;padding:26px 0;border-top:2px solid #1C1B19;border-bottom:1px solid #E7DFCF;text-align:center}}
.fig{{max-width:900px;margin:30px auto 60px;padding:34px 40px;background:#fff;border:1px solid #EAE2D2}}
.fig .k{{font-size:12px;letter-spacing:.14em;color:#B4461A;font-weight:600}}
.fig h3{{font-family:var(--serif);font-weight:400;font-size:30px;margin:6px 0 18px}}
.cap{{font-size:13px;color:#77716A;margin-top:14px;border-top:1px solid #EFE8DA;padding-top:10px}}
sup.c{{font-size:11px;color:#B4461A;font-weight:600;padding:0 2px}}
</style></head><body>
<div class="hero"><div class="kicker">รายงานวิจัย · เกษตรและอาหาร</div>
<h1>{E(TITLE)}</h1><div class="deck">จากสวนภูเขาไฟศรีสะเกษถึงตลาดจีน: ห่วงโซ่อุปทาน เทคโนโลยี และนวัตกรรมที่กำลังเปลี่ยน “ราชาแห่งผลไม้”</div>
<div class="byline"><span><b>Co-STORM</b></span><span>29 ก.ย. 2569</span><span>อ่าน 14 นาที</span><span>35 แหล่งอ้างอิง</span></div></div>
<div class="wrap"><p class="drop">{cites(LEAD[0][:520])}…</p>
<div class="pull">“ยิ่งเย็น ละอองเรณูทุเรียนยิ่งมีชีวิตยืนยาว — ที่ 0 °C อยู่ได้ถึง 36 วัน”</div>
<p>{cites(LEAD[1][:420] if len(LEAD) > 1 else PARAS[0][:420])}…</p></div>
<div class="fig"><div class="k">ภาพที่ 1</div><h3>ละอองเรณูเก็บรักษาได้นานแค่ไหน ในแต่ละอุณหภูมิ</h3>
{hbars("#B4461A", "#F3EBDD", "#1C1B19", width=820, label_w=80)}
<div class="cap">ที่มา: ความมีชีวิตและการเก็บรักษาละอองเรณูทุเรียนที่ปลูกในจังหวัดอุตรดิตถ์ [3] · ตัวเลขตรวจกับข้อความต้นทางแล้ว</div></div>
</body></html>"""

# ---------------------------------------------------------------- B · Bento
srcs = "".join(
    f'<li><span class="n">{s["id"]}</span><span class="t">{E(s["title"][:52])}…</span></li>' for s in R["sources"][:4]
)
tree = "".join(
    f'<li class="d{d}"><span>{E(n)}</span>{E(h[:34])}{"…" if len(h) > 34 else ""}</li>' for d, n, h, _ in SECTIONS if d < 2
)
B = f"""<!doctype html><html lang="th"><head><meta charset="utf-8"><style>{FONTS}
body{{background:#F5F5F7;color:#1D1D1F;padding:44px 56px}}
.top{{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:26px}}
.chips span{{display:inline-block;font-size:13px;padding:5px 12px;border-radius:999px;background:#fff;margin-right:6px;color:#515154;box-shadow:0 1px 2px rgb(0 0 0/.05)}}
.chips span.b{{background:#0071E3;color:#fff}}
h1{{font-family:var(--serif);font-weight:400;font-size:60px;margin:14px 0 0;letter-spacing:-.01em}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);grid-auto-rows:150px;gap:18px}}
.t{{background:#fff;border-radius:24px;padding:24px 26px;box-shadow:0 1px 2px rgb(0 0 0/.04),0 8px 24px -12px rgb(0 0 0/.12);overflow:hidden;position:relative}}
.lbl{{font-size:12px;font-weight:600;letter-spacing:.06em;color:#86868B;text-transform:uppercase}}
.sum{{grid-column:span 2;grid-row:span 2}}
.sum p{{font-size:17px;line-height:1.85;color:#3A3A3C;margin:12px 0 0}}
.sum ul{{margin:14px 0 0;padding-left:18px;font-size:15px;line-height:1.9;color:#1D1D1F}}
.big{{font-size:52px;font-weight:600;letter-spacing:-.02em;line-height:1;margin-top:14px}}
.big small{{font-size:18px;font-weight:500;color:#86868B;margin-left:6px}}
.sub{{font-size:14px;color:#515154;margin-top:10px;line-height:1.5}}
.s1 .big{{color:#0071E3}} .s2 .big{{color:#1F9D57}}
.chart{{grid-column:span 2;grid-row:span 2}}
.chart h4,.map h4,.src h4{{font-size:19px;margin:8px 0 14px;font-weight:600}}
.map{{grid-column:span 2;grid-row:span 2}}
.map ul{{list-style:none;margin:0;padding:0;font-size:14px;line-height:2.05}}
.map li span{{display:inline-block;min-width:32px;color:#0071E3;font-weight:600}}
.map li.d1{{padding-left:22px;color:#515154}}
.src{{grid-column:span 2;grid-row:span 2}}
.src ul{{list-style:none;margin:0;padding:0}}
.src li{{display:flex;gap:10px;align-items:baseline;font-size:14px;padding:9px 0;border-bottom:1px solid #F0F0F2}}
.src .n{{flex:none;width:24px;height:24px;border-radius:8px;background:#E8F1FD;color:#0071E3;font-size:12px;font-weight:600;display:grid;place-items:center}}
.ring{{position:absolute;right:26px;top:24px}}
.cite{{font-size:12px;color:#0071E3;font-weight:600}}
</style></head><body>
<div class="top"><div><div class="chips"><span class="b">Co-STORM</span><span>29 ก.ย. 2569</span><span>อ่าน 14 นาที</span><span>35 แหล่ง</span></div>
<h1>{E(TITLE)}</h1></div></div>
<div class="grid">
<div class="t sum"><div class="lbl">สรุปใน 30 วินาที</div><p>{cites(LEAD[0][:300], "cite")}…</p>
<ul><li>ห่วงโซ่อุปทานและการส่งออกไปจีนคือแกนหลัก</li><li>IoT และเกษตรแม่นยำช่วยลดน้ำและไฟฟ้า</li><li>อุณหภูมิต่ำยืดอายุละอองเรณูได้หลายเท่า</li></ul></div>
<div class="t s1"><div class="lbl">ละอองเรณูที่ 0 °C</div><div class="big">36<small>วัน</small></div><div class="sub">เก็บได้นานสุดในการทดลอง <span class="cite">[3]</span></div></div>
<div class="t s2"><div class="lbl">IoT ระบบรดน้ำ</div><div class="big">−40<small>%</small></div><div class="sub">ทั้งน้ำและไฟฟ้า ในแปลงข้าวโพดเลี้ยงสัตว์ <span class="cite">[23]</span></div></div>
<div class="t"><div class="lbl">Smart farming · มะระขี้นก</div><div class="big" style="font-size:28px;white-space:nowrap">7,000 → 10,452.66</div><div class="sub">กิโลกรัมต่อรอบเก็บเกี่ยว <span class="cite">[11]</span></div></div>
<div class="t"><div class="lbl">แหล่งอ้างอิง</div><div class="big">35</div><div class="sub">ทุกแหล่งมีข้อความหลักฐาน</div>
<svg class="ring" width="64" height="64" viewBox="0 0 36 36"><circle cx="18" cy="18" r="15" fill="none" stroke="#EDEDF0" stroke-width="5"/><circle cx="18" cy="18" r="15" fill="none" stroke="#0071E3" stroke-width="5" stroke-dasharray="94 100" transform="rotate(-90 18 18)" stroke-linecap="round"/></svg></div>
<div class="t chart"><div class="lbl">กราฟ</div><h4>ละอองเรณูเก็บได้นานเท่าไรตามอุณหภูมิ</h4>{hbars("#0071E3", "#F0F4FA", "#1D1D1F", width=560, annotate=False)}<div class="sub">ที่มา <span class="cite">[3]</span></div></div>
<div class="t map"><div class="lbl">โครงเรื่อง</div><h4>13 หัวข้อ ใน 2 ประเด็นหลัก</h4><ul>{tree}</ul></div>
</div></body></html>"""

# ---------------------------------------------------------------- C · Distill / Tufte
side = "".join(
    f'<div class="sn" style="top:{40 + i * 150}px"><b>{s["id"]}</b> {E(s["title"][:70])}… <span>{E(HOST(s["url"]))}</span></div>'
    for i, s in enumerate(R["sources"][:4])
)
C = f"""<!doctype html><html lang="th"><head><meta charset="utf-8"><style>{FONTS}
body{{background:#fff;color:#111}}
.head{{max-width:1180px;margin:0 auto;padding:64px 40px 30px;display:grid;grid-template-columns:1fr 300px;gap:60px;border-bottom:1px solid #eee}}
h1{{font-family:var(--serif);font-weight:500;font-size:56px;line-height:1.15;margin:0}}
.desc{{font-size:20px;line-height:1.7;color:#555;margin-top:18px;font-family:var(--serif)}}
.meta{{font-size:13px;line-height:2;color:#666;border-left:1px solid #eee;padding-left:22px}}
.meta b{{display:block;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#999;margin-top:10px}}
.body{{max-width:1180px;margin:0 auto;padding:40px;display:grid;grid-template-columns:180px 1fr 300px;gap:40px;position:relative}}
.toc{{font-size:13px;line-height:2.1;color:#888;position:sticky;top:20px;align-self:start}}
.toc div.on{{color:#0E7C7B;font-weight:600}}
.text p{{font-family:var(--serif);font-size:19px;line-height:1.95;color:#222;margin:0 0 22px}}
sup.c{{color:#0E7C7B;font-family:var(--sans);font-size:11px;font-weight:700;padding:0 1px}}
.key{{background:#F2F8F8;border-left:3px solid #0E7C7B;padding:20px 24px;margin:6px 0 30px;font-size:16px;line-height:1.85}}
.key b{{display:block;font-size:12px;letter-spacing:.12em;color:#0E7C7B;margin-bottom:6px}}
.figure{{margin:34px 0}} .figure .cap{{font-size:14px;color:#666;line-height:1.7;margin-top:10px}} .figure .cap b{{color:#111}}
.side{{position:relative}}
.sn{{position:absolute;left:0;right:0;font-size:13px;line-height:1.7;color:#555;border-top:1px solid #eee;padding-top:8px}}
.sn b{{color:#0E7C7B;margin-right:4px}} .sn span{{display:block;color:#999;font-size:12px}}
</style></head><body>
<div class="head"><div><h1>{E(TITLE)}</h1><div class="desc">{E(LEAD[0][:190])}…</div></div>
<div class="meta"><b>โหมด</b>Co-STORM<b>วันที่</b>29 ก.ย. 2569<b>แหล่งอ้างอิง</b>35 แหล่ง พร้อมข้อความหลักฐาน<b>อ่าน</b>ราว 14 นาที</div></div>
<div class="body"><div class="toc">{"".join(f'<div class="{"on" if i == 0 else ""}">{n} {E(h[:18])}…</div>' for i, (d, n, h, _) in enumerate(SECTIONS[:9]) if d == 0 or i < 5)}</div>
<div class="text"><div class="key"><b>สาระสำคัญ</b>ทุเรียนไทยพึ่งตลาดจีนเป็นหลัก ความได้เปรียบมาจากคุณภาพตามแหล่งผลิต (GI) และเทคโนโลยีการผลิต ขณะที่โลจิสติกส์ข้ามพรมแดนยังเป็นจุดอ่อน</div>
<p>{cites(LEAD[0][:430])}…</p>
<div class="figure">{hbars("#0E7C7B", "#EEF5F5", "#111", width=620, annotate=False)}<div class="cap"><b>ภาพที่ 1</b> ระยะเวลาที่ละอองเรณูทุเรียนยังมีชีวิต เมื่อเก็บที่อุณหภูมิต่างกัน ข้อมูลจาก [3]</div></div>
<p>{cites((LEAD[1] if len(LEAD) > 1 else PARAS[0])[:300])}…</p></div>
<div class="side">{side}</div></div></body></html>"""

# ---------------------------------------------------------------- D · Research Canvas
cards = ""
for i, sid in enumerate([3, 23, 11, 2]):
    s = SRC[sid]
    on = i == 0
    ev = s["evidence"][0] if s["evidence"] else ""
    k = ev.find("36 วัน") if sid == 3 else -1
    snippet = E(ev[max(0, k - 110):k + 90]) if k >= 0 else E(ev[:170])
    if sid == 3:
        snippet = snippet.replace("36 วัน", "<mark>36 วัน</mark>")
    cards += (f'<div class="card{" on" if on else ""}"><div class="h"><span class="n">{sid}</span><span class="f">{E(HOST(s["url"])[0].upper())}</span>{E(HOST(s["url"]))}</div>'
              f'<div class="tt">{E(s["title"][:80])}</div>{"<div class=ev>…" + snippet + "…</div>" if on else ""}</div>')
D = f"""<!doctype html><html lang="th"><head><meta charset="utf-8"><style>{FONTS}
body{{background:radial-gradient(60rem 36rem at 90% 0%,#E2DCFF 0%,transparent 60%),radial-gradient(60rem 40rem at 0% 40%,#D6E9FF 0%,transparent 60%),#EEF3FB;color:#14213D;min-height:100vh}}
.bar{{display:flex;align-items:center;gap:14px;padding:18px 32px}}
.seg{{display:inline-flex;background:rgb(37 99 235/.08);border-radius:12px;padding:4px}}
.seg span{{font-size:14px;padding:6px 16px;border-radius:9px;color:#4A5875}} .seg span.on{{background:#fff;color:#14213D;box-shadow:0 1px 3px rgb(30 58 138/.15)}}
.main{{display:grid;grid-template-columns:1fr 420px;gap:26px;padding:0 32px 32px}}
.paper{{background:rgb(255 255 255/.78);backdrop-filter:blur(16px);border:1px solid rgb(30 58 138/.1);border-radius:22px;padding:44px 56px;box-shadow:0 20px 50px -30px rgb(30 58 138/.35)}}
h1{{font-family:var(--serif);font-weight:400;font-size:52px;margin:6px 0 10px}}
.meta{{font-size:13px;color:#4A5875}}
p{{font-size:18px;line-height:1.95;margin:20px 0 0;color:#22304F}}
sup.c{{display:inline-block;min-width:20px;padding:1px 6px;margin:0 2px;border-radius:999px;background:rgb(37 99 235/.12);color:#2563EB;font-size:11px;font-weight:600;text-align:center;vertical-align:4px}}
.hl{{background:linear-gradient(transparent 55%,rgb(37 99 235/.18) 55%);}}
.side{{display:flex;flex-direction:column;gap:12px}}
.side .ttl{{display:flex;justify-content:space-between;font-size:14px;font-weight:600;padding:6px 4px}}
.card{{background:rgb(255 255 255/.7);backdrop-filter:blur(14px);border:1px solid rgb(30 58 138/.1);border-radius:16px;padding:14px 16px}}
.card.on{{background:#fff;border-color:#2563EB;box-shadow:0 0 0 4px rgb(37 99 235/.12),0 12px 30px -16px rgb(30 58 138/.4)}}
.card .h{{display:flex;align-items:center;gap:8px;font-size:12px;color:#4A5875}}
.card .n{{width:22px;height:22px;border-radius:7px;background:#2563EB;color:#fff;display:grid;place-items:center;font-size:11px;font-weight:600}}
.card .f{{width:18px;height:18px;border-radius:5px;background:#E3ECFB;color:#1E3A8A;display:grid;place-items:center;font-size:10px;font-weight:700}}
.card .tt{{font-size:15px;font-weight:600;margin-top:8px;line-height:1.5}}
.card .ev{{font-size:13px;line-height:1.75;color:#4A5875;margin-top:10px;padding:10px 12px;border-radius:10px;background:#F4F7FD;border-left:3px solid #2563EB}}
mark{{background:#FDE68A;color:#14213D;padding:0 3px;border-radius:3px}}
.mini{{margin-top:26px;padding:20px 24px;border-radius:16px;background:linear-gradient(135deg,#EEF4FF,#F5F0FF);border:1px solid rgb(37 99 235/.12)}}
.mini .k{{font-size:12px;font-weight:600;color:#2563EB;letter-spacing:.06em}}
</style></head><body>
<div class="bar"><div class="seg"><span class="on">บทความ</span><span>ภาพรวม</span><span>แหล่งอ้างอิง 35</span></div></div>
<div class="main"><div class="paper"><div class="meta">Co-STORM · 29 ก.ย. 2569 · อ่าน 14 นาที</div><h1>{E(TITLE)}</h1>
<p>{cites(LEAD[0][:360])}…</p>
<p>…การเก็บรักษาละอองเรณูเป็นอีกปัจจัยของการผลิต <span class="hl">ละอองเรณูที่เก็บไว้ที่ 0 องศาเซลเซียสเก็บได้นาน 36 วัน</span><sup class="c" style="background:#2563EB;color:#fff">3</sup> ขณะที่ระบบรดน้ำด้วย IoT ลดการใช้น้ำและไฟฟ้าได้ 40%<sup class="c">23</sup></p>
<div class="mini"><div class="k">ภาพประกอบ · ตรวจกับหลักฐานแล้ว</div>{hbars("#2563EB", "#E6EDFA", "#14213D", width=640, annotate=False)}</div></div>
<div class="side"><div class="ttl"><span>แหล่งที่อ้างในส่วนนี้</span><span style="color:#2563EB">4</span></div>{cards}</div></div>
</body></html>"""

for name, page in (("A-editorial", A), ("B-bento", B), ("C-distill", C), ("D-canvas", D)):
    open(os.path.join(HERE, f"{name}.html"), "w", encoding="utf-8").write(page)
    print(name)
