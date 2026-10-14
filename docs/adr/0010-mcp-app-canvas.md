# MCP App: canvas แสดงเอเจนต์ที่งานวิจัยสร้างขึ้น แบบสด ใน workspace ของ AI client

client ที่รองรับ MCP Apps (เช่น Claude) แสดงหน้า `ui://deeplit/research-canvas.html` ข้างผลของ `research_start` และ `research_status` เป็น canvas ที่เห็นเอเจนต์ถูก spawn ทีละตัวระหว่างที่ Run ทำงาน ส่วน client ที่ไม่รองรับยังได้ผลเป็นข้อความเหมือนเดิม ตัดสินใจเมื่อ 2026-10-14 ตามงานที่ได้รับมอบหมาย: "ทำเป็น MCP และให้แสดง canvas บน workspace และแสดงการ spawn agent ขึ้นมา"

## สิ่งที่ตัดสินใจ

1. **ใช้มาตรฐาน MCP Apps (`io.modelcontextprotocol/ui`)** แทน UI เฉพาะ client
   - tool ประกาศ `_meta.ui.resourceUri`
   - resource เป็น HTML ที่มี mimeType `text/html;profile=mcp-app`
   - host แสดงใน iframe แบบ sandbox และคุยกับหน้าเว็บผ่าน JSON-RPC ทาง `postMessage`:
     - หน้าเว็บส่ง `ui/initialize` (`protocolVersion` 2026-01-26) แล้วส่ง `ui/notifications/initialized`
     - host ส่ง `ui/notifications/tool-input` และ `tool-result`
     - หน้าเว็บส่ง `tools/call` ให้ host ส่งต่อถึง server
     - หน้าเว็บส่ง `ui/notifications/size-changed`, `ui/message`, `ui/open-link` และ `ui/request-display-mode`
   - ใช้ SDK เดิม (`mcp` 1.30, FastMCP) เพราะรองรับ `meta=` และ `mime_type=` อยู่แล้ว จึงยังไม่ต้องย้ายไป SDK 2.x ที่มี `Apps` ในตัว
2. **canvas ดึงข้อมูลเองผ่าน tool `research_events`**
   - tool นี้มี `visibility: ["app"]` คือมีไว้ให้หน้าเว็บเรียก ไม่ให้ model เห็น
   - คืนข้อมูลของ Run และ event หลังเลข `after` โดยใช้ `_run_detail` ตัวเดียวกับหน้า Run บนเว็บ จึงเห็น event ชุดเดียวกับที่เจ้าของเห็น (stage, usage และ note ประเภท perspectives / tree / flow / browsed) ส่วน traceback ยังอยู่แต่ในฐานข้อมูล
   - ตรวจความเป็นเจ้าของด้วย `deps.own` ก่อนอ่านเสมอ เพื่อให้ token ไม่ได้สิทธิ์ผู้ดูแลตาม ADR 0009
   - หน้าเว็บเรียกทุก 2.5 วินาที หรือราว 24 ครั้งต่อนาที ไม่เกินเพดาน 60 ครั้งต่อนาทีต่อ token และหยุดเรียกเมื่อ Run จบ
3. **ไม่ต้องเพิ่มข้อมูลใหม่ฝั่ง engine** เอเจนต์ที่วาดมาจาก event ที่มีอยู่แล้ว
   - STORM: note `perspectives` แตกเป็นเอเจนต์ตามมุมมอง (persona) ที่สัมภาษณ์ผู้เชี่ยวชาญ แล้วตามด้วยผู้วางโครงเรื่อง ผู้เขียนแต่ละหัวข้อ และผู้เกลาเนื้อหา ตาม stage
   - Deep Research: note `tree` แต่ละโหนดคือนักค้นคว้าหนึ่งคนพร้อมคำค้นและเป้าหมาย สถานะของโหนดมาจาก status ใน event
   - Agent Research: note `flow` ให้ผู้วางแผนแตกเป็นนักค้นคว้าหัวข้อละคน (lane) แต่ละรอบแตกเป็นเอเจนต์ค้นหาหรืออ่านเว็บตาม `tasks` เมื่อจบหัวข้อก็มีผู้เขียน และมีผู้รวมรายงาน
4. **หน้าเว็บเป็นไฟล์เดียว ไม่มี library และไม่ดึงอะไรจาก network**
   - CSP ของ host อนุญาตเฉพาะ origin ที่ resource ประกาศ ที่นี่ไม่ประกาศเลย
   - วาดด้วย SVG
   - เอเจนต์ใหม่เติบโตออกจากโหนดแม่ มีวงกระจายตรงจุดที่เกิด และเส้นเชื่อมค่อยๆ ลากออกไป
   - โหนดที่กำลังทำงานมีวงเต้นและเส้นวิ่ง
   - ต้นไม้ที่กว้างเกินกรอบสลับเป็นแนวซ้ายไปขวา
   - สีตามธีมของ host (`hostContext.styles.variables`) และมีโหมดมืด
   - ภาษาไทยหรืออังกฤษตาม `hostContext.locale`
5. **เปิด Run ที่ทำไปแล้ว ให้เล่นซ้ำเร็วๆ** เอเจนต์ยังเกิดตามลำดับให้เห็น เกิน 160 event จะวาดทีเดียว
6. **ถ้าเปิดไฟล์นอก host ให้เล่นตัวอย่างในตัว** (`#demo=agent|deep|storm`) ไว้ดูและทดสอบหน้าตาโดยไม่ต้องมี server

## ทางเลือกที่ไม่เลือก

- **ให้ tool คืนรูปภาพหรือ HTML ทีละครั้ง** ไม่สด และ model ต้องเรียกซ้ำเอง
- **ส่ง event ผ่าน notification ของ tool call ที่ค้างไว้** ต้องให้ทั้ง client และ host ถือ stream ยาวๆ และ server เป็น stateless (ADR 0009)
- **ฝังหน้า Run ของเว็บ DeepLit ใน iframe** ต้องมี cookie และ CSP ข้าม origin และ integration account ไม่มีหน้าเว็บ
- **ย้ายไป SDK 2.x** ทำได้ภายหลังโดยไม่กระทบหน้าเว็บ เพราะ wire เป็นแบบเดียวกัน

## การทดสอบ

- `tests/test_mcp.py`
  - tool ทั้ง 7 ตัวมี `_meta.ui` ถูกต้อง
  - resource เป็น `text/html;profile=mcp-app` และไม่มี URL ภายนอก
  - `research_events` คืน event ชุดเดียวกับเว็บ ตาม cursor ได้ และคนอื่นที่ไม่ใช่เจ้าของอ่านไม่ได้
- `tests/canvas_demo_server.py` รัน API บน Postgres ชั่วคราว และใช้ event จริงที่ export มา ไม่มีการเรียก LLM
- `tests/mcp_app_harness.py` เป็น host จำลอง ใช้ iframe `srcdoc` แบบ sandbox พร้อม CSP แบบไม่มี domain และแสดงทุกข้อความที่ส่งไปมา
- ตรวจด้วยตาบนเครื่องนี้เมื่อ 2026-10-14
  - Agent Research ที่กำลังรัน: เห็นเอเจนต์ค้นหาเกิดทุกรอบ
  - Deep Research: ต้นไม้ 21 เอเจนต์ ใช้แนวซ้ายไปขวา
  - STORM: เห็นทุก persona
  - ทั้งไทยและอังกฤษ ทั้งธีมสว่างและมืด

## จะกลับมาพิจารณาเมื่อ

- ต้องการให้ canvas เห็นผลทันทีโดยไม่ poll ให้ใช้ `subscriptions/listen` เมื่อ host รองรับ
- Co-STORM (Discussion) เปิดผ่าน MCP เมื่อไหร่ ต้องวาดผู้ร่วมสนทนาเพิ่ม
