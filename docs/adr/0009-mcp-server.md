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
7. **tool 6 ตัว คำอธิบายเป็นภาษาอังกฤษ**
   - `research_options`, `research_start`, `research_status`, `research_report` (full / outline / section:N), `research_list` และ `research_cancel`
   - start และ status รอได้นานสุด 45 วินาที ระหว่างรอส่ง progress notification จากสัญญาณ `pg_notify` เดิม (`notify.runs`) แล้วคืน id ให้ถามต่อ จึงไม่ติด timeout ของ client ทั่วไป
   - ยังไม่มี Discussion (Co-STORM) เพราะต้องโต้ตอบหลายรอบกับคน
8. **เปิดเป็นค่าเริ่มต้น** การตั้งค่าที่ผู้ดูแลแก้ได้ (`system_settings["mcp"]`) คือ เปิด/ปิดทั้งระบบ และ "ผู้ใช้สร้าง token เองได้" ทั้งสองค่าเริ่มต้นเป็นเปิด เพราะไม่มี token ก็ใช้อะไรไม่ได้ และผู้ดูแลปิดได้ทันที

## ทางเลือกที่ไม่เลือก

- **stdio server ให้ติดตั้งบนเครื่องผู้ใช้:** ต้องแจกโปรแกรมและอัปเดตตาม API ส่วน HTTP ใช้ URL เดียวได้ทุก client (Claude Desktop ใช้ `mcp-remote` เป็นสะพาน)
- **แยกเป็น service หรือ port ของตัวเอง:** ต้องเพิ่ม container, proxy rule และ pool ของ DB อีกชุด แต่ไม่ได้อะไรเพิ่ม
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
