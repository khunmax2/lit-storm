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
3. **ไม่ต้องเพิ่มข้อมูลใหม่ฝั่ง engine** เอเจนต์ที่วาดมาจาก event ที่มีอยู่แล้ว และแต่ละโหมดวาดตามวิธีทำงานของตัวเอง (scene แยกกัน ตั้งแต่ 2026-10-15)
   - **STORM** (`mcp_canvas/storm.js`): โต๊ะสัมภาษณ์
     - note `perspectives` ทำให้ persona นั่งล้อมผู้เชี่ยวชาญหัวข้อ เส้นสัมภาษณ์วิ่งระหว่างค้นคว้า และ note `browsed` นับหน้าที่อ่าน
     - จากนั้นต่อแถวผู้เขียน: ผู้วางโครงเรื่อง → ผู้เขียนแต่ละหัวข้อ → ผู้เกลา ตาม stage
   - **Deep Research** (`deep.js`): ต้นไม้แบ่งคอลัมน์ตามชั้น
     - note `tree` แต่ละโหนดคือนักค้นคว้าหนึ่งคน แสดงคำค้น สถานะ จำนวนแหล่ง และข้อค้นพบ
     - ทางตันจะจางลง และหัวคอลัมน์บอกจำนวนในแต่ละชั้น
   - **Agent Research** (`agent.js`): loop ตาม note `flow`
     - 4 สถานีล้อมวงแหวน (สังเกต → หาช่องว่าง → เลือกเครื่องมือ → ค้นและอ่านเว็บ) มีจุดโคจรไปที่ขั้นที่ทำงานอยู่ และตรงกลางบอกรอบ n/m
     - เอเจนต์ค้นหาของรอบนั้น spawn ข้างสถานีค้น และมีผู้เขียนเมื่อ gap agent บอกว่ารู้พอแล้ว
     - ระดับลึกแสดงหัวข้อละแถว แต่ละแถวมีวงแหวนเล็กของตัวเอง
4. **หน้าเว็บประกอบจาก shell ร่วมกับ scene ของโหมด ไม่มี library และไม่ดึงอะไรจาก network**
   - `mcp_canvas/base.html` คือ shell ร่วม (host bridge, หัว, ขั้นตอน, log, ชุดเครื่องมือวาด) ส่วน server แทรก scene และชื่อ tool ของเส้นนั้นตอนส่ง (`mcp._canvas_html`)
   - เส้นของแต่ละโหมดส่ง scene ของตัวเองเท่านั้น ที่ `ui://deeplit/<mode>-canvas.html` และเรียก `<mode>_research_events` ส่วนเส้นรวมส่งทั้งสาม scene แล้วเลือกตามโหมดของ Run
   - CSP ของ host อนุญาตเฉพาะ origin ที่ resource ประกาศ ที่นี่ไม่ประกาศเลย
   - **การวาดและเคลื่อนไหว:**
     - วาดด้วย SVG เอเจนต์ใหม่เติบโตออกจากผู้ที่ spawn มัน มีวงกระจายตรงจุดที่เกิด และเส้นค่อยๆ ลากออกไป
     - ตัวที่กำลังทำงานมีวงเต้นและเส้นวิ่ง
   - **ธีมและภาษา:** สีตามธีมของ host (`hostContext.styles.variables`) และมีโหมดมืด ภาษาไทยหรืออังกฤษตาม `hostContext.locale`
   - **ไม่ใช้ component ของเว็บ** (React Flow และฉาก 3D) ซึ่งจะทำให้ไฟล์ใหญ่หลาย MB และต้องตรวจว่า host ยอมให้ WebGL ทำงานใน sandbox ไหม ทางนี้ยังเลือกได้ภายหลัง
5. **เปิด Run ที่ทำไปแล้ว ให้เล่นซ้ำเร็วๆ** เอเจนต์ยังเกิดตามลำดับให้เห็น เกิน 160 event จะวาดทีเดียว
6. **ถ้าเปิดไฟล์นอก host ให้เล่นตัวอย่างในตัว** (`#demo=agent|agent-sections|deep|storm`) ไว้ดูและทดสอบหน้าตาโดยไม่ต้องมี server

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
- `tests/mcp_app_harness.py` เป็น host จำลอง ใช้ iframe `srcdoc` แบบ sandbox พร้อม CSP แบบไม่มี domain และแสดงทุกข้อความที่ส่งไปมา ใช้ `?mode=deep` เพื่อเปิดเส้นและ canvas ของโหมดนั้น
- `test_each_mode_draws_its_own_canvas`: หน้าของแต่ละเส้นมีเฉพาะ scene ของตัวเอง และเรียก tool ของตัวเอง
- ตรวจด้วยตาบนเครื่องนี้เมื่อ 2026-10-14
  - Agent Research ที่กำลังรัน: เห็นเอเจนต์ค้นหาเกิดทุกรอบ
  - Deep Research: ต้นไม้ 21 เอเจนต์ ใช้แนวซ้ายไปขวา
  - STORM: เห็นทุก persona
  - ทั้งไทยและอังกฤษ ทั้งธีมสว่างและมืด

## จะกลับมาพิจารณาเมื่อ

- ต้องการให้ canvas เห็นผลทันทีโดยไม่ poll ให้ใช้ `subscriptions/listen` เมื่อ host รองรับ
- Co-STORM (Discussion) เปิดผ่าน MCP เมื่อไหร่ ต้องวาดผู้ร่วมสนทนาเพิ่ม
- ตรวจ scene แยกโหมดด้วยตาเมื่อ 2026-10-15 ผ่าน harness กับ event จริงที่ export มา
  - Agent: Run ระดับลึก 4 หัวข้อ และ Run มาตรฐานที่เล่นสด (เห็นเอเจนต์ค้นหาจริงของแต่ละรอบ spawn ข้างสถานีค้น)
  - Deep: Run มาตรฐาน 2 ชั้น
  - STORM: Run ระดับลึก 6 persona
  - ทั้งธีมมืดและภาษาไทย
