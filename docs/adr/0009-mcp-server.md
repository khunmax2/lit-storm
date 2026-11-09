# MCP server: stateless HTTP ใน API process เดิม ใช้ token แบบ Bearer

DeepLit เปิดงานวิจัยให้เครื่องมือ AI (Claude Code, Claude Desktop, Cursor, VS Code) และระบบอื่น (เช่น DeepWitya) เรียกผ่าน MCP ที่ `{public_url}/api/mcp` ใช้ Streamable HTTP แบบ stateless ผ่าน SDK ทางการ (`mcp`, FastMCP) โดยเป็น route ของ FastAPI app เดิม (`api/mcp.py`) ผู้เรียกยืนยันตัวด้วย `Authorization: Bearer dlk_…` ตกลงแบบนี้กับเจ้าของเมื่อ 2026-10-06

## สิ่งที่ตัดสินใจ

1. **ใช้ stateless และอยู่ใน API process เดิม** API รัน uvicorn 2 worker (ADR-0007, benchmark 2026-09-30) ถ้า session อยู่ในหน่วยความจำ คำขอถัดไปอาจไปตก worker อีกตัวแล้วหา session ไม่เจอ ข้อมูลที่ต้องจำข้ามคำขอ (Run, สถานะ, รายงาน) อยู่ใน Postgres กับ `/data/runs` อยู่แล้ว จึงไม่ต้องมี session ของ MCP และไม่ต้องเพิ่ม service หรือ port ใหม่บนเครื่อง 203
2. **path คือ `/api/mcp` ไม่ใช่ `/litstorm/mcp`** proxy ทุกชั้น (nginx ของ stack, nginx ของเครื่อง 203, Vite dev) ส่ง `/api/` ต่อให้ API อยู่แล้ว จึงไม่ต้องแก้ config ของ proxy ตัวใด ถ้า mount เป็น sub-app ไว้ที่ path นี้ Starlette จะ redirect `/api/mcp` ไปที่ `/api/mcp/` และ client บางตัวไม่ตาม redirect ของ POST จึงเพิ่ม endpoint เป็น `Route` ตรงๆ และรัน session manager ใน lifespan ของ FastAPI
3. **token แทน OAuth ในรุ่นนี้**
   - token ขึ้นต้นด้วย `dlk_` แสดงครั้งเดียว เก็บเฉพาะ SHA-256
   - มี scope `read` (ดูรายการ สถานะ และรายงาน ไม่ใช้โควตา) และ `research` (เริ่มและยกเลิกงาน)
   - อายุ 30/90/365 วัน ค่าเริ่มต้น 90 วัน ส่วน token ของ integration ไม่หมดอายุก็ได้
   - เพิกถอนได้ และบันทึกเวลาใช้ล่าสุด
   - token ไม่มีสิทธิ์ผู้ดูแลเลย
   - client ทุกตัวที่เราตั้งเป้ารองรับ header นี้ ส่วน OAuth 2.1 ต้องมี authorization server กับ consent page จึงยกไปทำแยก
4. **integration account** คือแถวใน `users` ที่ `kind="integration"` ไม่มีรหัสผ่านและ login ไม่ได้
   - มีโควตา เพดาน และ `allowed_engines` ของตัวเอง
   - ผู้ดูแลอ่าน Run ของบัญชีนี้บนเว็บได้ (`deps.readable`) เพราะไม่มีคนจริงเป็นเจ้าของ
   - ผลจาก tool ไม่ใส่ลิงก์เว็บ
5. **ปิดการกัน DNS rebinding ของ SDK** ค่าเริ่มต้นของ SDK รับเฉพาะ Host `localhost` จึงปฏิเสธคำขอที่ผ่าน proxy ด้วยชื่อเครื่องจริง ที่ปิดได้เพราะทุกคำขอต้องมี Bearer token และเว็บอื่นในเบราว์เซอร์ส่ง header นี้มาโดยไม่มี token ไม่ได้ การโจมตีแบบ rebinding จึงไม่มีอะไรให้ได้
6. **ตรวจที่ประตูก่อนถึง SDK** (`TokenGate`, ASGI)
   - ไม่มี token หรือ token ผิดได้ 401 พร้อม `WWW-Authenticate: Bearer`
   - ปิด MCP อยู่หรือบัญชีถูกระงับได้ 403
   - ส่งเกิน 60 ครั้งต่อนาทีต่อ token ได้ 429 (นับแยกแต่ละ process 2 process จึงรับได้ถึง 120 ครั้งต่อนาที ซึ่งพอสำหรับกันการวนผิดพลาด)
   - ปัญหาเรื่อง token จึงได้คำตอบเป็น HTTP status ที่ client เข้าใจ ไม่ใช่ error ของ JSON-RPC
7. **tool 7 ตัว คำอธิบายเป็นภาษาอังกฤษ** (บวก `research_events` สำหรับ canvas ใน ADR 0010)
   - `research_options`, `research_start`, `research_status`, `research_report` (full / outline / section:N), `research_list`, `research_cancel` และ `research_export`
   - **การรอของ start และ status:**
     - รอ 20 วินาทีเป็นค่าเริ่มต้น และขอได้สูงสุด 45 วินาที
     - ระหว่างรอส่ง progress notification จากสัญญาณ `pg_notify` เดิม (`notify.runs`) แล้วคืน id ให้ถามต่อ
     - ค่าเริ่มต้นเคยเป็น 45 วินาที แต่ Agenta ตัด tool call ที่เกิน 30 วินาที client จึงเรียกซ้ำ และงานถูกสร้างซ้ำ (2026-10-14)
   - **กันการเริ่มซ้ำ:** `research_start` ที่ซ้ำกับงานที่ token เดิมเริ่มภายใน 10 นาที (หัวข้อ โหมด ความลึก ภาษา แหล่ง และโมเดลเดียวกัน) จะคืนงานเดิม และไม่ใช้โควตา
   - **`research_export`:**
     - คืนลิงก์ดาวน์โหลดไฟล์รายงาน ได้แก่ interactive HTML ที่มีกราฟ, HTML ธรรมดา, Markdown, PDF หรือ observatory (ไฟล์เล่นซ้ำการทำงานของเอเจนต์ ดู [ADR-0011](./0011-observatory.md))
     - ลิงก์เซ็นด้วย HMAC ของ secret key และใช้ได้ 15 นาที (`litstorm/exports.py`)
     - `GET /api/exports/{token}` ไม่ต้อง login เพราะลิงก์เป็นตัวให้สิทธิ์ แต่ใช้ได้กับ Run และรูปแบบเดียว และตรวจซ้ำว่า Run ยังเป็นของเจ้าของ
     - ตัวไฟล์ไม่ผ่าน MCP เพราะไฟล์ใหญ่จะล้น context ของ LLM agent จึงดาวน์โหลดเอง
     - ถ้า client เข้าถึง API ด้วยชื่ออื่นที่ไม่ใช่ public URL ให้ตั้ง `LITSTORM_EXPORT_URL` (เช่น Agenta ผ่าน Docker network)
   - ยังไม่มี Discussion (Co-STORM) เพราะต้องโต้ตอบหลายรอบกับคน
8. **เปิดเป็นค่าเริ่มต้น** การตั้งค่าที่ผู้ดูแลแก้ได้ (`system_settings["mcp"]`) คือ เปิด/ปิดทั้งระบบ และ "ผู้ใช้สร้าง token เองได้" ทั้งสองค่าเริ่มต้นเป็นเปิด เพราะไม่มี token ก็ใช้อะไรไม่ได้ และผู้ดูแลปิดได้ทันที
9. **มีเซิร์ฟเวอร์แยกต่อโหมดคู่กับตัวรวม** (2026-10-15 พี่เลี้ยงขอให้แยกเพื่อให้ client เลือกเส้นตามความสามารถ ตกลงทีละข้อกับเจ้าของ)
   - **เส้นใหม่:** `/api/mcp/storm`, `/api/mcp/deep`, `/api/mcp/agent` ชื่อ server คือ "DeepLit STORM", "DeepLit Deep Research" และ "DeepLit Agent Research" ส่วน `/api/mcp` ทำงานเหมือนเดิม
   - **ชื่อ tool ขึ้นต้นด้วยชื่อโหมด** (`deep_research_start` …) และไม่มีพารามิเตอร์ `mode`
     - client บางตัวรวม tool จากทุก server ไว้ในรายการเดียว ถ้าใช้ชื่อเดิมจะชนกัน
     - LLM เห็นจากชื่อเลยว่า tool นี้ทำอะไร
   - **เห็นเฉพาะงานของโหมดนั้น** ทุก tool รวมถึง canvas ถ้าส่ง id ของโหมดอื่นมา จะตอบว่างานนั้นเป็นโหมดอะไร และให้อ่านผ่านเส้นไหน
   - **instructions ของแต่ละเส้น:** บอกว่าโหมดนั้นเหมาะกับอะไร ไม่เหมาะกับอะไร ใช้เวลาเท่าไร และได้แหล่งประมาณเท่าไร จากตัวเลขที่วัดบน stack local (`mcp.ABOUT`) และบอกชื่อเส้นอื่น
   - **ใช้ร่วมกับตัวรวม:** token, โควตา และตัวนับ 60 ครั้งต่อนาที ต่อหลายเส้นจึงไม่ได้โควตาหรือเพดานเพิ่ม
   - **ตรวจที่ประตู:** โหมดที่ผู้ดูแลปิด หรือที่บัญชีไม่ได้รับอนุญาต ได้ 403 `mode_disabled` / `mode_not_allowed` ตั้งแต่ตอนต่อ
   - **อยู่ใน process เดิม ใช้โค้ดชุดเดียว** (`build(mode)`) งานหนักแยก process ต่อ Run อยู่แล้ว (ADR-0003) การแยก service จึงเพิ่มภาระดูแลแต่ไม่ได้ความทนทานเพิ่ม
   - **หน้าการเชื่อมต่อ:** มีตัวเลือกเส้น แต่ละเส้นมีคำอธิบายภาษาไทย snippet กับปุ่มทดสอบเปลี่ยนตามเส้น และ dialog สร้าง token ของบัญชีเชื่อมต่อก็มีตัวเลือกนี้ด้วย

## ทางเลือกที่ไม่เลือก

- **stdio server ให้ติดตั้งบนเครื่องผู้ใช้:** ต้องแจกโปรแกรมและอัปเดตตาม API ส่วน HTTP ใช้ URL เดียวได้ทุก client (Claude Desktop ใช้ `mcp-remote` เป็นสะพาน)
- **แยกเป็น service หรือ port ของตัวเอง:** ต้องเพิ่ม container, proxy rule และ pool ของ DB อีกชุด แต่ไม่ได้อะไรเพิ่ม เหตุผลเดียวกันใช้กับการแยกเซิร์ฟเวอร์รายโหมดเป็น container ของตัวเองด้วย
- **แยกรายโหมดแต่ใช้ชื่อ tool เดิม:** client ที่รวม tool จากหลายเซิร์ฟเวอร์จะเห็นชื่อชนกัน
- **แยกรายโหมดแล้วปิดตัวรวม:** ทำให้ client ที่ใช้อยู่ (Agenta, DeepWitya) และ config ที่แจกไปแล้วใช้ไม่ได้ และตัวรวมยังเหมาะกับ client ที่อยากให้ LLM เลือกโหมดเอง
- **stateful session ร่วมกับ sticky routing:** ต้องตั้ง nginx ให้ผูก client กับ worker และ session หายเมื่อ restart
- **ใช้ cookie ของเว็บ:** client ภายนอกไม่มี cookie และ cookie ทำให้เกิด CSRF

## จะกลับมาพิจารณาเมื่อ

- client ที่ต้องรองรับบังคับใช้ OAuth (เช่น remote connector ของ claude.ai) ให้เพิ่ม OAuth 2.1 โดยใช้ token เดิมเป็นฐาน
- ต้องการ resumable stream หรือ server-initiated request ซึ่งต้องมี session และ event store ร่วมกัน (Postgres)
- rate limit ต่อ process ไม่พอ ให้ย้ายตัวนับไป Postgres

## Consequences

- `Run.via_token_id` บอกว่า Run เริ่มจาก token ไหน การ์ด Run จึงแสดง "ผ่าน MCP · ชื่อ token" และหน้า Usage ของผู้ดูแลมีคอลัมน์ "ผ่าน MCP"
- หน้าการเชื่อมต่อ (`/connections`) สร้าง config ที่คัดลอกไปใช้ได้ทันทีสำหรับ 6 client และมีปุ่มทดสอบที่เรียก `research_options` จริงด้วย token นั้น
- ตรวจรับกับ client จริงบน stack local แล้ว ดู [acceptance/2026-10-06-mcp](../acceptance/2026-10-06-mcp.md)
