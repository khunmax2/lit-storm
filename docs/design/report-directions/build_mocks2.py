"""Throwaway: four more directions for the interactive report — the chosen
Brief+Canvas mix, and three bolder ones. Static mockups on the durian report."""
import os

from build_mocks import E, FONTS, HOST, LEAD, POLLEN, SECTIONS, SRC, TITLE, R, cites, hbars

HERE = os.path.dirname(os.path.abspath(__file__))
TOPS = [(n, h) for d, n, h, _ in SECTIONS if d == 0]
SUBS = {n: [(m, h) for d, m, h, _ in SECTIONS if d == 1 and m.startswith(n + ".")] for n, _ in TOPS}

# ---------------------------------------------------------------- E · Brief + Canvas
src_cards = ""
for i, sid in enumerate([3, 23, 11]):
    s = SRC[sid]
    on = i == 0
    ev = s["evidence"][0]
    k = ev.find("36 วัน")
    snip = (E(ev[max(0, k - 95):k + 70]).replace("36 วัน", "<mark>36 วัน</mark>") if on else "")
    src_cards += (f'<div class="sc{" on" if on else ""}"><div class="h"><span class="n">{sid}</span>{E(HOST(s["url"]))}</div>'
                  f'<div class="tt">{E(s["title"][:66])}</div>{"<div class=ev>…" + snip + "…</div>" if on else ""}</div>')
EE = f"""<!doctype html><html lang="th"><head><meta charset="utf-8"><style>{FONTS}
body{{background:radial-gradient(70rem 36rem at 92% -5%,#E2DCFF 0%,transparent 60%),radial-gradient(60rem 40rem at -5% 30%,#D6E9FF 0%,transparent 60%),#EEF3FB;color:#14213D;padding:34px 40px}}
.chips span{{display:inline-block;font-size:13px;padding:5px 12px;border-radius:999px;background:rgb(255 255 255/.8);margin-right:6px;color:#4A5875;border:1px solid rgb(30 58 138/.1)}}
.chips span.b{{background:#1E3A8A;color:#fff;border-color:#1E3A8A}}
h1{{font-family:var(--serif);font-weight:400;font-size:58px;margin:12px 0 22px}}
.bento{{display:grid;grid-template-columns:1.6fr 1fr 1fr 1fr;grid-template-rows:140px 196px;gap:14px}}
.t{{background:rgb(255 255 255/.78);backdrop-filter:blur(16px);border:1px solid rgb(30 58 138/.1);border-radius:22px;padding:20px 22px;box-shadow:0 14px 34px -24px rgb(30 58 138/.45)}}
.lbl{{font-size:11px;font-weight:600;letter-spacing:.08em;color:#6B7A99;text-transform:uppercase}}
.sum{{grid-row:span 2}} .sum p{{font-size:15.5px;line-height:1.85;margin:10px 0 0;color:#22304F}}
.big{{font-size:44px;font-weight:600;letter-spacing:-.02em;margin-top:10px;line-height:1}} .big small{{font-size:16px;color:#6B7A99;margin-left:4px}}
.sub{{font-size:13px;color:#4A5875;margin-top:8px}} .c{{color:#2563EB;font-weight:600}}
.ch{{grid-column:span 2}}
.read{{display:grid;grid-template-columns:1fr 380px;gap:22px;margin-top:22px}}
.paper{{background:rgb(255 255 255/.86);border:1px solid rgb(30 58 138/.1);border-radius:22px;padding:34px 44px}}
.paper h2{{font-family:var(--serif);font-weight:400;font-size:30px;margin:0 0 10px}} .paper h2 span{{font-family:var(--sans);font-size:14px;color:#2563EB;margin-right:10px}}
.paper p{{font-size:17px;line-height:1.95;color:#22304F;margin:12px 0 0}}
sup.c{{display:inline-block;padding:1px 6px;border-radius:999px;background:rgb(37 99 235/.12);font-size:11px;vertical-align:4px}}
.hl{{background:linear-gradient(transparent 58%,rgb(37 99 235/.2) 58%)}} .on-c{{background:#2563EB!important;color:#fff!important}}
.side .ttl{{font-size:13px;font-weight:600;color:#4A5875;margin:4px 0 10px}}
.sc{{background:rgb(255 255 255/.7);border:1px solid rgb(30 58 138/.1);border-radius:16px;padding:12px 14px;margin-bottom:10px}}
.sc.on{{background:#fff;border-color:#2563EB;box-shadow:0 0 0 4px rgb(37 99 235/.12)}}
.sc .h{{display:flex;gap:8px;align-items:center;font-size:12px;color:#6B7A99}} .sc .n{{width:22px;height:22px;border-radius:7px;background:#2563EB;color:#fff;display:grid;place-items:center;font-size:11px;font-weight:600}}
.sc .tt{{font-size:14px;font-weight:600;margin-top:6px;line-height:1.5}} .ev{{font-size:12.5px;line-height:1.75;color:#4A5875;margin-top:8px;padding:8px 10px;border-radius:10px;background:#F4F7FD;border-left:3px solid #2563EB}}
mark{{background:#FDE68A;padding:0 3px;border-radius:3px;color:#14213D}}
</style></head><body>
<div class="chips"><span class="b">Co-STORM</span><span>29 ก.ย. 2569</span><span>อ่าน 14 นาที</span><span>35 แหล่ง · ตรวจหลักฐานแล้ว</span></div>
<h1>{E(TITLE)}</h1>
<div class="bento"><div class="t sum"><div class="lbl">สรุปใน 30 วินาที</div><p>{cites(LEAD[0][:330], "c")}…</p></div>
<div class="t"><div class="lbl">ละอองเรณูที่ 0 °C</div><div class="big" style="color:#2563EB">36<small>วัน</small></div><div class="sub">นานสุดในการทดลอง <span class="c">[3]</span></div></div>
<div class="t"><div class="lbl">IoT ระบบรดน้ำ</div><div class="big" style="color:#0F9F6E">−40<small>%</small></div><div class="sub">น้ำและไฟฟ้า <span class="c">[23]</span></div></div>
<div class="t"><div class="lbl">แหล่งอ้างอิง</div><div class="big">35</div><div class="sub">ทุกแหล่งมีข้อความหลักฐาน</div></div>
<div class="t ch"><div class="lbl">ละอองเรณูเก็บได้นานเท่าไร</div>{hbars("#2563EB", "#E6EDFA", "#14213D", width=620, annotate=False)}</div>
<div class="t"><div class="lbl">Smart farming</div><div class="big" style="font-size:24px;white-space:nowrap">7,000 → 10,452.66</div><div class="sub">กก./รอบเก็บเกี่ยว <span class="c">[11]</span></div></div></div>
<div class="read"><div class="paper"><h2><span>02</span>นวัตกรรมเกษตรและเทคโนโลยีเพื่อการผลิต</h2>
<p>…การเก็บรักษาละอองเรณูเป็นอีกปัจจัยของการผลิต <span class="hl">ละอองเรณูที่เก็บไว้ที่ 0 องศาเซลเซียสเก็บได้นาน 36 วัน</span><sup class="c on-c">3</sup> ขณะที่ระบบรดน้ำด้วย IoT ลดการใช้น้ำและไฟฟ้าได้ 40%<sup class="c">23</sup> และ Smart farming เพิ่มผลผลิตต่อรอบได้<sup class="c">11</sup>…</p>
<p>{cites((LEAD[1] if len(LEAD) > 1 else LEAD[0])[:420], "c")}…</p></div>
<div class="side"><div class="ttl">แหล่งที่อ้างในย่อหน้านี้ · 3</div>{src_cards}</div></div>
</body></html>"""

# ---------------------------------------------------------------- F · Story Mode
chapters = "".join(
    f'<div class="ch{" on" if i == 1 else ""}"><span>{n.zfill(2)}</span>{E(h[:26])}{"…" if len(h) > 26 else ""}</div>'
    for i, (n, h) in enumerate([("0", "บทนำ")] + TOPS)
)
F = f"""<!doctype html><html lang="th"><head><meta charset="utf-8"><style>{FONTS}
body{{background:#0F1A2E;color:#F4F1EA;overflow:hidden}}
.rail{{position:fixed;left:34px;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;gap:14px;z-index:3}}
.ch{{font-size:12px;color:rgb(244 241 234/.45);display:flex;gap:10px;align-items:center}} .ch span{{font-family:var(--sans);font-weight:600;width:28px;height:28px;border-radius:50%;border:1px solid rgb(244 241 234/.3);display:grid;place-items:center;font-size:11px}}
.ch.on{{color:#F4F1EA}} .ch.on span{{background:#F2A65A;border-color:#F2A65A;color:#0F1A2E}}
.stage{{position:fixed;inset:0;left:300px;display:grid;grid-template-columns:1.15fr .85fr;align-items:center}}
.viz{{height:100vh;display:flex;flex-direction:column;justify-content:center;padding:0 60px;background:radial-gradient(50rem 30rem at 40% 50%,#1D3355 0%,transparent 70%)}}
.kick{{font-size:13px;letter-spacing:.2em;color:#F2A65A;font-weight:600}}
.huge{{font-family:var(--serif);font-size:210px;line-height:.9;letter-spacing:-.03em;background:linear-gradient(180deg,#FFE3C2,#F2A65A);-webkit-background-clip:text;background-clip:text;color:transparent}}
.huge small{{font-size:54px;-webkit-text-fill-color:#F4F1EA}}
.therm{{display:flex;gap:26px;align-items:flex-end;height:220px;margin-top:20px}}
.bar{{width:90px;border-radius:14px 14px 4px 4px;background:linear-gradient(180deg,#F2A65A,#C2410C);position:relative}}
.bar b{{position:absolute;top:-34px;left:0;right:0;text-align:center;font-size:22px}} .bar i{{position:absolute;bottom:-30px;left:0;right:0;text-align:center;font-style:normal;font-size:14px;color:rgb(244 241 234/.7)}}
.bar.dim{{opacity:.35}}
.steps{{padding:0 70px 0 10px;display:flex;flex-direction:column;gap:22px}}
.step{{background:rgb(244 241 234/.06);border:1px solid rgb(244 241 234/.12);border-radius:20px;padding:24px 26px;font-size:17px;line-height:1.9;backdrop-filter:blur(8px)}}
.step.on{{background:#F4F1EA;color:#0F1A2E;box-shadow:0 30px 60px -30px #000}}
.step .s{{display:inline-block;margin-left:4px;padding:1px 7px;border-radius:999px;background:#F2A65A;color:#0F1A2E;font-size:11px;font-weight:700;vertical-align:3px}}
.prog{{position:fixed;left:0;top:0;height:3px;width:42%;background:#F2A65A}}
.title{{position:fixed;left:34px;top:30px;font-family:var(--serif);font-size:22px;color:rgb(244 241 234/.8)}}
</style></head><body><div class="prog"></div><div class="title">{E(TITLE)}</div>
<div class="rail">{chapters}</div>
<div class="stage"><div class="viz"><div class="kick">บทที่ 01 · การเก็บรักษาละอองเรณู</div>
<div class="huge">36<small> วัน</small></div>
<div class="therm"><div class="bar" style="height:216px"><b>36</b><i>0 °C</i></div><div class="bar dim" style="height:168px"><b>28</b><i>5 °C</i></div><div class="bar dim" style="height:36px"><b>6</b><i>25 °C</i></div></div></div>
<div class="steps"><div class="step">ทุเรียนถูกยกย่องให้เป็น “ราชาแห่งผลไม้” และไทยส่งออกไปจีนเป็นหลัก<span class="s">1</span></div>
<div class="step on">ละอองเรณูที่เก็บไว้ที่ <b>0 องศาเซลเซียส</b> เก็บได้นาน <b>36 วัน</b> ที่ 5 °C ได้ 28 วัน และที่ 25 °C เพียง 6 วัน<span class="s">3</span><br><span style="font-size:13px;opacity:.6">เลื่อนต่อ → อุณหภูมิอื่นจะสว่างขึ้นทีละแท่ง</span></div>
<div class="step">ระบบรดน้ำด้วย IoT ลดการใช้น้ำและไฟฟ้าได้ 40%<span class="s">23</span></div></div></div>
</body></html>"""

# ---------------------------------------------------------------- G · Knowledge Map
T1, T2 = TOPS[0][1], TOPS[1][1]
SUB1, SUB2 = [h for _, h in SUBS[TOPS[0][0]]], [h for _, h in SUBS[TOPS[1][0]]]
LAYOUT = [  # x, y, w, label, kind, sources, focus
    (360, 70, 240, TITLE, "root", [], False),
    (110, 250, 290, T1, "big", [1, 2, 6, 7], False),
    (560, 250, 290, T2, "big", [5, 11, 23, 3], False),
    (40, 540, 250, SUB1[0], "sub", [8, 9], False),
    (300, 600, 230, SUB1[1], "sub", [10, 12], False),
    (550, 560, 220, SUB2[0], "sub", [5, 23], False),
    (790, 600, 220, SUB2[-1], "sub", [3, 4], True),
]
EDGES = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6)]
nodes, paths = [], []
for x, y, w, lab, kind, srcs, focus in LAYOUT:
    if kind == "root":
        nodes.append(f'<div class="node root" style="left:{x}px;top:{y}px">{E(lab)}<small>35 แหล่ง · 13 หัวข้อ</small></div>')
        continue
    chips = "".join(f"<i>{n}</i>" for n in srcs)
    nodes.append(f'<div class="node{" big" if kind == "big" else ""}{" focus" if focus else ""}" style="left:{x}px;top:{y}px;width:{w}px">'
                 f'<span class="k">{"ประเด็นหลัก" if kind == "big" else "หัวข้อย่อย"}</span>{E(lab[:44])}{"…" if len(lab) > 44 else ""}<span class="srcs">{chips}</span></div>')
for a_, b_ in EDGES:
    xa, ya, wa = LAYOUT[a_][0], LAYOUT[a_][1], LAYOUT[a_][2]
    xb, yb, wb = LAYOUT[b_][0], LAYOUT[b_][1], LAYOUT[b_][2]
    x1, y1, x2, y2 = xa + wa / 2, ya + 80, xb + wb / 2, yb
    focus = LAYOUT[b_][6]
    paths.append(f'<path d="M{x1:.0f} {y1} C {x1:.0f} {(y1 + y2) / 2:.0f}, {x2:.0f} {(y1 + y2) / 2:.0f}, {x2:.0f} {y2}" '
                 f'stroke="{"#2563EB" if focus else "#9DB4E6"}" stroke-width="{3 if focus else 2}"{" stroke-dasharray=\"6 6\"" if focus else ""}/>')
lines = f'<svg class="links" width="1100" height="900"><g fill="none">{"".join(paths)}</g></svg>'
labels = [lab for _, _, _, lab, _, _, _ in LAYOUT]
G = f"""<!doctype html><html lang="th"><head><meta charset="utf-8"><style>{FONTS}
body{{margin:0;height:900px;overflow:hidden;color:#14213D;background:radial-gradient(circle,#C9D6EE 1px,transparent 1.2px) 0 0/26px 26px,linear-gradient(135deg,#F3F6FC,#EAF0FB 60%,#F1ECFD)}}
.links{{position:absolute;inset:0}}
.node{{position:absolute;width:250px;padding:14px 16px;border-radius:18px;background:rgb(255 255 255/.82);backdrop-filter:blur(12px);border:1px solid rgb(30 58 138/.12);box-shadow:0 18px 40px -26px rgb(30 58 138/.5);font-size:14.5px;font-weight:500;line-height:1.5}}
.node .k{{display:block;font-size:10.5px;letter-spacing:.08em;color:#6B7A99;margin-bottom:4px;font-weight:600}}
.node.big{{width:290px;font-size:17px;border-color:rgb(37 99 235/.3)}}
.node.root{{width:240px;text-align:center;background:#1E3A8A;color:#fff;font-family:var(--serif);font-size:22px;font-weight:400}}
.node.root small{{display:block;font-family:var(--sans);font-size:12px;opacity:.7;margin-top:4px}}
.node.focus{{border:2px solid #2563EB;box-shadow:0 0 0 6px rgb(37 99 235/.14),0 24px 50px -24px rgb(30 58 138/.6)}}
.srcs{{display:flex;gap:4px;margin-top:10px}} .srcs i{{font-style:normal;font-size:11px;font-weight:600;width:22px;height:22px;border-radius:7px;display:grid;place-items:center;background:#E8EFFD;color:#2563EB}}
.drawer{{position:absolute;right:26px;top:26px;bottom:26px;width:380px;border-radius:24px;background:#fff;box-shadow:-20px 0 60px -30px rgb(30 58 138/.5);padding:26px 26px}}
.drawer .k{{font-size:11px;letter-spacing:.08em;color:#2563EB;font-weight:600}}
.drawer h3{{font-family:var(--serif);font-weight:400;font-size:26px;margin:8px 0 12px;line-height:1.35}}
.drawer p{{font-size:15px;line-height:1.85;color:#22304F}}
.tools{{position:absolute;left:26px;bottom:26px;display:flex;gap:8px}} .tools span{{background:#fff;border:1px solid rgb(30 58 138/.12);border-radius:12px;padding:8px 14px;font-size:13px;box-shadow:0 6px 16px -10px rgb(30 58 138/.4)}}
.title{{position:absolute;left:30px;top:26px;font-size:13px;color:#6B7A99}}
</style></head><body><div class="title">มุมมองแผนที่ความรู้ · ลากเพื่อเลื่อน · คลิกหัวข้อเพื่ออ่าน</div>
{lines}{"".join(nodes)}
<div class="drawer"><div class="k">หัวข้อย่อย · 2 แหล่ง</div><h3>{E(labels[-1][:60])}</h3>
<div style="margin:6px 0 14px">{hbars("#2563EB", "#E6EDFA", "#14213D", width=330, label_w=52, annotate=False)}</div>
<p>ละอองเรณูที่เก็บไว้ที่ 0 องศาเซลเซียสเก็บได้นาน 36 วัน ที่ 5 °C ได้ 28 วัน และที่ 25 °C เพียง 6 วัน <b style="color:#2563EB">[3]</b></p></div>
<div class="tools"><span>＋</span><span>－</span><span>จัดเรียงอัตโนมัติ</span><span>แสดงแหล่งอ้างอิง</span></div>
</body></html>"""

# ---------------------------------------------------------------- H · Bauhaus Infographic
H = f"""<!doctype html><html lang="th"><head><meta charset="utf-8"><style>{FONTS}
body{{background:#F3EDE2;color:#111;padding:40px 56px;background-image:radial-gradient(#D9CFBE 1.2px,transparent 1.3px);background-size:22px 22px}}
.grid{{display:grid;grid-template-columns:repeat(12,1fr);gap:18px}}
.box{{border:3px solid #111;box-shadow:7px 7px 0 #111;background:#fff;padding:22px 24px;position:relative}}
.hero{{grid-column:span 8;background:#1D4ED8;color:#fff;padding:34px 36px;min-height:290px}}
.hero .k{{font-size:13px;letter-spacing:.2em;font-weight:700}}
.hero h1{{font-family:var(--serif);font-weight:500;font-size:76px;line-height:1.05;margin:16px 0 14px}}
.hero p{{font-size:16px;line-height:1.8;max-width:620px;opacity:.92}}
.circle{{position:absolute;right:-30px;bottom:-30px;width:170px;height:170px;border-radius:50%;background:#FACC15;border:3px solid #111}}
.tri{{position:absolute;right:46px;top:30px;width:0;height:0;border-left:44px solid transparent;border-right:44px solid transparent;border-bottom:76px solid #EF4444}}
.num{{grid-column:span 4;background:#FACC15;min-height:290px;display:flex;flex-direction:column;justify-content:space-between}}
.num .v{{font-size:150px;font-weight:700;line-height:.85;letter-spacing:-.04em}} .num .v small{{font-size:40px}}
.num .l{{font-size:17px;font-weight:600;line-height:1.5}}
.lbl{{font-size:12px;font-weight:700;letter-spacing:.14em}}
.c4{{grid-column:span 4}} .c5{{grid-column:span 5}} .c3{{grid-column:span 3}}
.red{{background:#EF4444;color:#fff}} .ink{{background:#111;color:#F3EDE2}}
.big{{font-size:72px;font-weight:700;letter-spacing:-.03em;line-height:1}}
.bars{{display:flex;flex-direction:column;gap:12px;margin-top:16px}}
.b{{display:flex;align-items:center;gap:12px;font-weight:600}} .b span{{width:56px}} .b div{{height:30px;border:3px solid #111;background:#1D4ED8}}
.src{{font-size:12px;margin-top:12px;font-weight:600;opacity:.7}}
.steps{{display:flex;gap:10px;margin-top:16px}} .steps div{{flex:1;border:3px solid #111;padding:12px;font-size:13.5px;font-weight:600;background:#F3EDE2;line-height:1.5}}
</style></head><body><div class="grid">
<div class="box hero"><div class="k">อินโฟกราฟิกจากรายงานวิจัย · CO-STORM</div><h1>{E(TITLE)}</h1>
<p>ทุเรียนไทยพึ่งตลาดจีน ความได้เปรียบมาจากคุณภาพตามแหล่งผลิตและเทคโนโลยี ส่วนโลจิสติกส์ข้ามแดนยังเป็นจุดอ่อน</p><div class="tri"></div><div class="circle"></div></div>
<div class="box num"><div class="lbl">ละอองเรณูที่ 0 °C เก็บได้</div><div class="v">36<small>วัน</small></div><div class="l">นานกว่าที่ 25 °C ถึงราว 6 เท่า · แหล่ง [3]</div></div>
<div class="box c5"><div class="lbl">อุณหภูมิ vs อายุละอองเรณู</div><div class="bars">{"".join(f'<div class="b"><span>{k}</span><div style="width:{v * 9}px"></div>{v} วัน</div>' for k, v in POLLEN)}</div><div class="src">แหล่ง [3] li01.tci-thaijo.org</div></div>
<div class="box c4 red"><div class="lbl">IOT ระบบรดน้ำ</div><div class="big">−40%</div><div style="font-weight:600;margin-top:8px">ทั้งน้ำและไฟฟ้า</div><div class="src" style="color:#fff">แหล่ง [23]</div></div>
<div class="box c3 ink"><div class="lbl">แหล่งอ้างอิง</div><div class="big">35</div><div style="margin-top:8px;font-weight:600">ทุกแหล่งมีหลักฐาน</div></div>
<div class="box" style="grid-column:span 12"><div class="lbl">ห่วงโซ่จากสวนถึงตลาด</div><div class="steps"><div>① สวน · มาตรฐาน GAP</div><div>② คัดคุณภาพ · GI ศรีสะเกษ</div><div>③ ข้อมูล Smart Farming + PMCS</div><div>④ โลจิสติกส์ข้ามแดน</div><div>⑤ ตลาดจีน</div></div></div>
</div></body></html>"""

for name, page in (("E-brief-canvas", EE), ("F-story", F), ("G-map", G), ("H-bauhaus", H)):
    open(os.path.join(HERE, f"{name}.html"), "w", encoding="utf-8").write(page)
    print(name)
