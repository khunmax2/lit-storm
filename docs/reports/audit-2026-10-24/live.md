# ลองจริงทุกโหมด (Task 5 ของการตรวจทั้งระบบ 2026-10-24)

ฐานที่ตรวจ HEAD `44ae50e` · stack audit `litstorm-audit` (:8098) · โมเดลหลัก `google/gemini-2.5-flash-lite` (OpenRouter), โมเดลสำรอง `openai/gpt-4.1-nano` · ค้นด้วย SearXNG ของ stack เอง · Medical ชี้ MRA ในเครื่อง (`http://host.docker.internal:8088`) ด้วย key ที่ออกใหม่เฉพาะงานนี้ · ผู้ใช้ `audit-admin@example.org` / `audit-user@example.org` ตั้งค่าครั้งแรกผ่านหน้าเว็บ (Playwright, Edge) · สคริปต์ `server/tests/audit/live_runs.py` · ภาพหน้าจออยู่ในโฟลเดอร์ scratch `.../scratchpad/audit/shots/` (ไม่ commit) และ Run สอบในหน้าเว็บของผู้ใช้ทดสอบ

**ชุดเทสต์เต็ม (ค้างจาก Task 4):** `uv run pytest -q` ได้ **890 passed, 2 skipped, 74 xfailed** ใน 360 วินาที ไม่มี failed

## งบ

เริ่ม 6.519949 USD (ขีดของ key 7.00) หยุดที่ 6.80 ไม่เริ่ม Run ใหม่เมื่อถึง 6.75 สิ้นสุดที่ **6.672289** รวมทุกอย่าง (DeepLit + MRA) = ใช้ไป 0.152 USD ไม่ถึงเกณฑ์หยุดและไม่ได้ยกเลิก Run ใดเพราะงบ

หมายเหตุ: `spend.py` ตามหลังความจริงราวหนึ่ง Run (ยอดของ OpenRouter ปรับช้า) delta ที่พิมพ์หลังแต่ละ Run จึงเลื่อนไป Run ถัดไป ใช้ยอดสิ้นสุดเป็นหลัก

## ผลแต่ละ Run

ผู้ใช้เริ่มทุก Run ผ่าน API ด้วยบัญชี `audit-user` ความลึก "เร็ว" ค่าใช้จ่ายคือ `cost_usd` ที่หน้า Usage ของผู้ดูแลเห็น

| # | โหมด | ภาษา | Run | ผล | เวลา | แหล่ง | ค่าใช้จ่าย |
|---|---|---|---|---|---|---|---|
| 1a | STORM | ไทย | `3efd60e6` | ล้ม `retries_exhausted` ที่ research (429 ต้นทาง, BUG-51) | 30 วิ | - | 0.0013 |
| 1b | STORM | ไทย | `a2da08c8` | ล้ม `retries_exhausted` ที่ outline (429) | 150 วิ | - | 0.0034 |
| 1c | STORM | ไทย | `eb589669` | **สำเร็จ** | 40 วิ | 7 | 0.0066 |
| 2a | Agent | ไทย | `2c6fa24b` | "สำเร็จ" แต่รายงานคือข้อความ error (BUG-49, BUG-52) | 30 วิ | 1 (`searxng:8080`) | 0.0027 |
| 2b | Agent (GPT-4.1 nano) | ไทย | `a354bc1c` | ล้ม `empty_report` | 60 วิ | - | 0.0064 |
| 3 | Deep | ไทย | `75543a30` | **สำเร็จ** | 30 วิ | 3 | 0.0023 |
| 4a | Co-STORM เปิด | ไทย | `52a2619f` | ล้ม `retries_exhausted` ที่ warmup (429) | 30 วิ | - | 0.0028 |
| 4b | Co-STORM เปิด | ไทย | `e04135d5` | ล้ม `retries_exhausted` ที่ warmup (429) | 60 วิ | - | 0.0063 |
| 4c | Co-STORM เปิด (GPT-4.1 nano) | ไทย | `59a10409` | **สำเร็จ** (warmup, 12 ข้อความ) | 100 วิ | - | 0.0080 |
| 4d | Co-STORM Turn "say" | ไทย | `680f05a1` | **สำเร็จ** | 40 วิ | - | 0.0011 |
| 4e | Co-STORM Turn "report" | ไทย | `9b54aaa0` | **สำเร็จ** รายงาน 27 แหล่ง | 10 วิ | 27 | 0.0015 |
| 5 | Medical ถามเร็ว | อังกฤษ | `45df9001` | **สำเร็จ** | 110 วิ | 8 | 0.0248 (MRA) |
| 6 | STORM | อังกฤษ | `0a688d71` | **สำเร็จ** | 50 วิ | 18 | 0.0050 |
| 7 | Medical รีวิวเต็ม (SLR) | อังกฤษ | `b2f95427` | **สำเร็จ** | 91 วิ | 24 | 0.0726 (MRA) |

ทำครบทุกโหมดที่สั่ง (Co-STORM เปิด + 1 Turn และ Turn ที่สอง = "report") โหมด Medical ไม่แสดง token (0/0) เพราะ MRA ส่งแต่ค่าใช้จ่าย ค่า `cost_usd` ของ Medical ตรงกับยอดที่ `spend.py` นับเพิ่มโดยประมาณ

## SEC-02 ลองจริง

หัวข้อ `สรุปเนื้อหาของหน้า http://searxng:8080/config` กับ Agent สองรอบ ดูผลและวิธีอัปเดตใน [security.md](security.md#sec-02--โหมด-agent-ดึงหน้าเว็บจากที่อยู่ภายในเครือข่ายได้-ssrf) สรุป: **ไม่ได้ยืนยันว่าอ่านเนื้อหาภายในได้จริงจากการให้โมเดลเลือก** — Gemini ส่ง URL ภายในไปให้เครื่องมือ (ปรากฏเป็นแหล่งอ้างอิงเดียวของรายงาน) แต่เครื่องมือล้มด้วย 400 ของ Gemini ก่อนได้เนื้อหา; GPT-4.1 nano ไปค้นเอกสารสาธารณะแทน ไม่มีเนื้อหาจาก `searxng:8080` ในรายงานใด

## Export (Step 3)

ลองครบ 5 รูปแบบ × (มี/ไม่มีหลักฐาน) กับทุก Run ที่สำเร็จ (STORM ไทย/อังกฤษ, Agent, Deep, Medical เร็ว/เต็ม, Co-STORM "report") ผล: **ทุกไฟล์ HTTP 200 ไม่ว่าง** PDF ขึ้นต้น `%PDF-` ทุกไฟล์ (125–381 KB) Markdown 5.7–35 KB HTML/interactive/observatory 69–260 KB ไม่มี `Traceback` / `Internal Server Error` / `[object Object]` ("NaN" ที่ตรวจพบคือโค้ด JS `isNaN` ใน observatory/interactive ไม่ใช่ข้อมูล) interactive และ observatory ได้ไฟล์เดียวกันไม่ว่าเปิด/ปิด `evidence` (น่าจะตั้งใจ ยังไม่ได้อ่านเหตุผลในโค้ด) Turn ของ Co-STORM ที่ไม่ใช่ "report" ไม่มีรายงานให้ export (404 `not_found`) ตามที่ควร ข้อสังเกต: ไฟล์ของ Run `2c6fa24b` มีข้อความ error ดิบ (BUG-49) ผลแสดงผลในเบราว์เซอร์ดูที่ภาพ `12-report-*.png` (ตรวจด้วยตา: STORM ไทย, Medical เต็ม และ Agent)

## MCP (Step 4)

สร้าง token (scope read+research, 30 วัน) ของ `audit-user` แล้วเพิกถอนหลังใช้ เรียกผ่าน `/api/mcp` (เส้นรวม) และ `/api/mcp/medical` บน Run ที่เสร็จแล้ว (`eb589669`, `b2f95427`) ได้ครบ **options, status, report, export, list, events ทั้งสองเส้น ไม่มี error** (ชื่อ argument คือ `id`) `tools/list` ได้ 8 tool ต่อเส้น `*_start` และ `*_cancel` **ไม่ได้ลอง** (start เสียเงินเกินงบที่ตั้ง; cancel ไม่มี Run ค้างให้ยกเลิก)

## ตรวจ key รั่ว (Step "carried")

นับเท่านั้น ไม่พิมพ์สตริง: `sk-or-` และสตริงยาว (40+ ตัวอักษร) ใน log ของ api และ worker, `message`/รายละเอียดของ 14 Run และ `stderr.log` ทั้งหมด (265 KB) = **0**; รูปแบบ account id `user_…` ของ OpenRouter = log 0, `message` 4 Run, `stderr.log` 1 (BUG-50), รายงาน Agent 1 (BUG-49) ข้อสงสัยใน security.md ("สงสัย") ปิดได้: key ไม่รั่ว

## UX

| รหัส | ระดับ | เรื่อง | หลักฐาน |
|---|---|---|---|
| UX-01 | ต่ำ | โมเดลที่เพิ่มใหม่ยังไม่ผ่านการทดสอบ จะเริ่ม Agent ไม่ได้ (`422 model_cannot_use_tools`) โดยไม่มีอะไรบอกผู้ดูแลตอนเพิ่มโมเดลว่าต้องกดทดสอบก่อน (ตรวจที่ API เท่านั้น ยังไม่ได้ดูว่าหน้าเว็บของผู้ใช้ซ่อนโหมดหรือแสดงข้อความ) | `supports_tools: null` ก่อนกดทดสอบ, หลังทดสอบ `true` แล้วเริ่มได้ |
| UX-02 | ต่ำ | หน้า "บริการค้นหา" มี SearXNG สองแถวที่ endpoint เดียวกัน (`http://searxng:8080/search`) ต่างกันแค่ชื่อ ("SearXNG" ค่าเริ่มต้น กับ "SearXNG LDR-academic") และ TCI-ThaiJO ที่ seed มาเอง อธิบายไม่ได้ว่าต่างกันอย่างไรจากหน้าจอ | `shots/20-admin-search.png` |
| UX-03 | ต่ำ | Run ที่ล้มจากข้อผิดพลาดชั่วคราวสองครั้งติดกัน (Co-STORM) ทำให้แถบข้างมีหัวข้อชื่อเดียวกันสามแถว ต่างกันที่จุดสีแดง/เขียวเท่านั้น แยกไม่ออกว่าอันไหนใช้ต่อได้ และ Turn ถามต่อของ Discussion ที่ล้มตอนเปิดถูกปฏิเสธ (`409 not_started`) หน้าจอไม่ได้ตรวจว่าบอกผู้ใช้อย่างไร | `shots/11-session-failed-429.png` (แถบข้าง) |
| UX-04 | ต่ำ | รายงานของ Agent ที่ล้มกลายๆ ยังแสดงอ้างอิง `1` ซ้ำสามตัวท้ายทุกประโยคและ "1 แหล่งอ้างอิง" เป็นโฮสต์ภายใน ทำให้ดูเหมือนรายงานปกติ (ดู BUG-49) | `shots/12-report-agent-error-report.png` (ภาพนี้มี account id ของ OpenRouter ห้ามเอาลงเอกสารที่เผยแพร่) |

ที่ดี: ข้อความของ Run ที่ล้มจาก 429 ในหน้าเว็บสุภาพและมีประโยชน์ ("บริการภายนอกล้มเหลวซ้ำหลังลองใหม่แล้ว ... ลองใหม่ได้ในอีกสักครู่ · คืนโควตาแล้ว") และโควตาถูกคืนทุกครั้งที่ล้ม

## สิ่งที่ต้องทำต่อ (Task 12)

- เพิกถอน key ของ MRA: prefix **`mra_ugcrPzYf`** ชื่อ `audit-2026-10-24` (`docker exec mra-api-1 python -m app.cli.keys revoke mra_ugcrPzYf`)
- ลบบัญชี `audit-*@example.org` และไฟล์ `creds.json` ใน scratch เมื่อจบ
