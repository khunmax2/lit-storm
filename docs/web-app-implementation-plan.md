# Web App — แผนทางเทคนิคและลำดับพัฒนา

สถานะ: แผนทางเทคนิคที่ยืนยันทิศทางแล้วเมื่อ 2026-09-24 ยังไม่ได้เริ่มพัฒนาเว็บใหม่ ขอบเขตที่ผู้ใช้ยืนยันอยู่ใน [web-app-design.md](./web-app-design.md) คำศัพท์อยู่ใน [CONTEXT.md](./CONTEXT.md) และการตัดสินใจทางสถาปัตยกรรมอยู่ใน [adr/](./adr/)

## ผลลัพธ์แรกที่ต้องทำให้ได้

เปิดระบบบน local ด้วย Docker Compose → สร้าง Admin → ตั้งค่า LLM และ Search Provider → สร้าง Project และ Research Session → ส่ง Run → Worker เรียก STORM จริง → เปิดรายงานพร้อม citation ได้ แม้ปิดหน้าเว็บระหว่างรัน

นี่เป็นชิ้นงานแรกสำหรับตรวจการเชื่อมต่อ ไม่ใช่รุ่นแรกที่เสร็จครบ ข้อกำหนดคิว สิทธิ์ โควตา และเกณฑ์รับงานทั้งหมดต้องผ่านก่อนถือว่ารุ่นแรกเสร็จ

## สิ่งที่พบจากโค้ด

- `frontend/demo_light/pages_util/CreateNewArticle.py` เรียก runner ผ่าน `st.session_state` และจัดการสถานะขั้นตอนใน Streamlit จึงไม่ใช่ Application Backend ที่นำมาให้เว็บใหม่เรียกได้ทันที
- `knowledge_storm/storm_wiki/engine.py` มี `STORMWikiRunner.run()` แยกการทำ research, outline, article และ polish ด้วย flags และโหลดผลขั้นก่อนจากไฟล์ได้
- Engine สร้างโฟลเดอร์จาก topic ใต้ `output_dir` จึงต้องกำหนด `output_dir` แยกต่อ Run ไม่ใช้หัวข้อเป็นตัวตนของงาน
- `knowledge_storm/storm_wiki/modules/callback.py` มี callbacks สำหรับ progress บางขั้น แต่ไม่ได้เป็นระบบคิวหรือระบบยกเลิกงานครบวงจร
- `frontend/demo_light/article_store.py` มี logic จัดเก็บตามเจ้าของและถังขยะที่ใช้เป็นฐานอ้างอิงได้ แต่ต้องปรับให้ผูกกับ Project/Session/Run ใหม่
- มีตัวสร้าง HTML เดิมใน `frontend/demo_light/html_report.py` ซึ่งต้องตรวจความสามารถก่อนเลือกนำกลับมาใช้กับข้อกำหนด export ใหม่
- `frontend/demo_light/article_language.py` สลับภาษาโดยแก้ docstring ของ `dspy.Signature` ซึ่งเป็นค่าที่ใช้ร่วมกันทั้ง process จึงรันสอง Run ใน process เดียวกันไม่ได้ ([ADR-0003](./adr/0003-one-process-per-run.md))
- `deploy/` ปัจจุบันมี Supabase (GoTrue, PostgREST), `research-ui` และ `agents-research` ซึ่งไม่ย้ายมาอยู่ใน stack ใหม่ของรุ่นแรก ([ADR-0002](./adr/0002-drop-supabase-own-auth.md), [ADR-0004](./adr/0004-engine-interface.md))

## โครงสร้างที่ตกลงแล้ว

```
web/        Vite + React + TS, Tailwind, shadcn/ui, TanStack Query, TS client จาก OpenAPI
server/     Python project เดียว (uv, SQLAlchemy 2, Alembic)
  api       FastAPI: บัญชี, session, สิทธิ์, Projects/Sessions, การส่งงาน, โควตา, การอ่านผล
  worker    supervisor: claim งาน, สร้าง subprocess ต่อ Run, heartbeat, งานตามเวลา
  engines/  Engine interface + STORM adapter (โค้ดที่คัดลอกมาจาก demo_light)
deploy/     compose ชุดใหม่: edge (nginx), api, worker, postgres, searxng
```

- **Web** ([ADR-0001](./adr/0001-vite-spa-and-fastapi.md)): เป็น static SPA ที่ edge เสิร์ฟ เรียก API บน origin เดียวกัน ไม่มี business logic ใช้ polling แสดงความคืบหน้าของ Run
- **API**: session เก็บฝั่ง server ส่ง cookie แบบ httpOnly และใช้ CSRF token API key ของ provider เข้ารหัสด้วย Fernet โดยใช้ master key จาก Docker secret
- **Worker**: หนึ่ง Run ต่อหนึ่ง subprocess ยกเลิกโดยส่งสัญญาณแล้ว kill ถ้าเกิน 30 วินาที เพดานเวลารวมต่อ Run 60 นาที และทุก HTTP request มี timeout
- **PostgreSQL**: เก็บสถานะและใช้เป็นคิวถาวร (`SELECT … FOR UPDATE SKIP LOCKED`) ต้องพิสูจน์การ claim งาน, คิวสลับผู้ใช้ และการกันงานซ้ำด้วย integration test
- **Persistent volume**: เก็บ `report.json`, ผลดิบ และ export ต่อ Run ส่งไฟล์ผ่าน API ที่ตรวจสิทธิ์ ([ADR-0005](./adr/0005-report-json-file.md))
- **PDF**: ใช้ Chromium (Playwright) พร้อมฟอนต์ไทย รวมอยู่ใน worker หรือแยกเป็น container `renderer`

## จุดเชื่อม engine

สร้าง module ที่รับ Run configuration, พื้นที่เก็บผลของ Run, ตัวรายงาน progress และตัวตรวจคำขอยกเลิก โดยซ่อนการสร้าง runner การตั้ง LLM/retriever และรูปแบบไฟล์เดิมไว้ภายใน

- หนึ่ง Run ใช้ runner instance และพื้นที่เก็บไฟล์ของตนเอง ไม่แชร์ mutable runner ระหว่างงาน
- เรียกแต่ละ stage ต่อเนื่องอัตโนมัติ ตรวจคำขอยกเลิกระหว่าง stage และจุดที่พิสูจน์แล้วว่าหยุดได้
- ไม่อ้างว่าการยกเลิกตัด HTTP request ภายนอกทันที ต้องกำหนด timeout ให้คำขอไม่ค้างไม่สิ้นสุด
- callbacks ส่งข้อมูล progress ที่ตรวจสิทธิ์ก่อนแสดง แยก technical logs ออกจากข้อมูลหลักฐานที่เป็นส่วนตัว
- ตรวจ retry ที่มีอยู่ใน SDK/engine ให้รวมแล้วไม่เกินคำขอแรกและการลองซ้ำอีก 2 ครั้ง
- แปลงผลเป็น Report ที่มี sections, citations และ sources; HTML/Markdown/PDF เป็นตัวแสดงผลจากข้อมูลชุดเดียวกัน
- เก็บเฉพาะหลักฐานที่มีจริง ไม่สร้างความเชื่อมโยงระดับประโยคที่ engine ไม่ได้บันทึกไว้ขึ้นมาเอง

## โครงสร้างข้อมูลเบื้องต้น

- `users`, `auth_sessions`, `password_setup_tokens`: บัญชี การล็อกอิน และลิงก์ตั้งรหัสผ่านครั้งเดียว
- `projects`, `research_sessions`: เจ้าของและการจัดกลุ่มงาน
- `runs`: Session, parent Run เมื่อกดลองใหม่, topic, language, config snapshot, status, stage, quota month และเวลาสำคัญ
- `run_events`, `worker_leases`: ประวัติสถานะ การถือสิทธิ์ประมวลผล และการตรวจ Worker ที่หายไป
- `quota_reservations`, `quota_ledger`: การจอง/ใช้/คืนที่ผูกกับ Run และรอบเดือน ป้องกันหักหรือคืนซ้ำ
- `llm_models`, `search_providers`, `provider_credentials`: รายการที่เปิดใช้ defaults และ credentials ที่เก็บฝั่ง server แยกจาก config snapshot ที่ผู้ใช้เห็น
- `reports`, `report_sources`, `report_citations`, `artifacts`: ผลลัพธ์ หลักฐาน และไฟล์ที่เชื่อมกับ Run
- `runs.engine`: มีตั้งแต่รุ่นแรกเพื่อรองรับ Engine อื่นในรุ่นสอง
- `run_usage`: token แยกตามโมเดลและจำนวนครั้งที่เรียก search ต่อ stage พร้อมค่าใช้จ่ายโดยประมาณ
- `audit_events`: ประวัติการกระทำของผู้ดูแล (`support_access_grants` ย้ายไปรุ่นสอง)
- การลบใช้ข้อมูลเวลาเข้าถังขยะ/เวลาครบกำหนด คงความสัมพันธ์กับ Run และไม่คืนโควตาเพียงเพราะลบรายงาน

ชื่อรายการเหล่านี้เป็นร่าง ไม่ใช่ SQL schema ที่อนุมัติแล้ว ต้องระบุ constraints, indexes และ transaction ก่อนทำ migration

## พฤติกรรมที่ต้องรักษาใน transaction

- ส่งงานหนึ่งครั้ง: ตรวจสิทธิ์และขนาดคิว จองโควตา และสร้าง Run อย่างเป็นอะตอม พร้อมป้องกันการส่งคำขอซ้ำ
- เริ่มงาน: ตรวจเพดานรวมและต่อผู้ใช้ เลือกเจ้าของตามรอบคิว แล้ว claim Run อย่างเป็นอะตอม
- งานรอแก้ provider/model: คงการจองเดิม ไม่ครองช่องประมวลผล เลือกใหม่แล้วเปลี่ยนเวลาเข้าคิวโดยคง Run ID
- Worker ล่ม: lease หมดอายุแล้ว mark interrupted ป้องกัน Worker เก่ากลับมาเขียนทับสถานะปลายทางด้วย claim token; ไม่ enqueue Run เดิมใหม่อัตโนมัติ
- จบ/ล้มเหลว/ยกเลิก: เปลี่ยนสถานะและลงบัญชีโควตาเพียงครั้งเดียว โดยกำหนดผู้ชนะเมื่อคำสั่งยกเลิกชนกับงานเสร็จ
- Publish report: เขียนไฟล์ให้ครบก่อนบันทึกผลที่พร้อมอ่าน ไม่แสดงไฟล์ที่เขียนไม่เสร็จเป็นรายงานสมบูรณ์

## ลำดับพัฒนา

1. **พิสูจน์ engine นอก Streamlit** — คัดลอกโค้ดที่ใช้ซ้ำเข้า `server/engines/storm/` แล้วรันหัวข้อทดสอบใน subprocess เก็บผลแยกตาม Run ทดลอง progress, retry, การยกเลิกด้วย kill และการรันภาษาไทยกับภาษาอังกฤษพร้อมกัน จากนั้นแปลงผลเป็น `report.json` และ**ทดลองทำ PDF ภาษาไทยด้วย Chromium** ใช้ fake provider สำหรับกรณีผิดพลาด และ API จริงสำหรับเส้นทางสำเร็จ
2. **ทำเส้นทางครบวงจรบน local** — Compose, migrations, bootstrap Admin, login, ตั้งค่าบริการ (มี SearXNG เป็นค่าเริ่มต้น), Project/Session, ส่งงานให้ Worker และอ่านผล วาง design token, layout หลัก และ TS client จาก OpenAPI ไว้ตั้งแต่ขั้นนี้ เพื่อไม่ต้องรื้อหน้าจอในขั้นที่ 4
3. **ทำกติกางานและข้อมูลให้ครบ** — คิวสลับผู้ใช้, โควตาพร้อมตารางการคืน, ค่า override, งานข้ามเดือน, ยกเลิก, Worker interruption, เพดานเวลา และลองใหม่ **เทสต์คิวและโควตา (pytest + Postgres จริง + FakeEngine) ต้องผ่านก่อนเริ่มทำหน้าจอของขั้นนี้**
4. **ทำรายงานและการจัดการให้ครบ** — Source Explorer, export 3 รูปแบบ, ไทย/อังกฤษ, การจัดการผู้ใช้, บันทึกค่าใช้จ่าย, ถังขยะ และหน้าจอ Dashboard/Settings
5. **ตรวจรับรุ่นแรก** — รันทุกรายการในเกณฑ์รับงานด้วย Playwright บน compose stack รวมติดตั้งใหม่และ restart container แล้วข้อมูลยังอยู่ ใช้ STORM จริงเฉพาะ smoke test จากนั้นเปลี่ยนมาใช้ระบบใหม่และลบ Streamlit กับ Supabase

## ผลขั้นที่ 1 (2026-09-24)

ได้รายงานภาษาไทยจริงโดยไม่ใช้ Streamlit แล้ว (`qwen/qwen3.7-flash` ผ่าน OpenRouter ร่วมกับ arXiv) citation ทั้ง 17 จุดชี้ไปยังแหล่งที่ถูกต้อง โค้ดอยู่ใน [server/](../server/)

**ปัญหาที่พบระหว่างรันจริงและแก้แล้ว**
- **Polish ของ STORM ทำ citation ผิด:** ขั้น polish เรียงเลข citation ใหม่ แต่ไม่เขียน `url_to_info.json` ใหม่ ผลคือข้อความกับแหล่งอ้างอิงชี้ไม่ตรงกัน แอป Streamlit เดิมก็มีปัญหานี้ ตอนนี้ engine บันทึก `url_to_info_polished.json` แยกไว้
- **Lead ของรายงานหาย:** โมเดลเขียน lead โดยขึ้นต้นด้วย heading ที่ซ้ำกับ section แรก STORM จึงรวม lead เข้ากับ section นั้นแล้วทิ้งไป แก้โดยเพิ่มคำสั่งเฉพาะสำหรับ lead ว่าห้ามมี heading
- **Retry เกินข้อกำหนด:** แอปเดิมตั้ง LiteLLM ให้ retry 6 ครั้ง และ `GoogleModel` ลองได้ 8 ครั้ง ตอนนี้จำกัดที่รวม 3 ครั้ง ส่วน error 4xx ที่ไม่ใช่ 408 หรือ 429 หยุดทันที
- **Run ทำงานต่อหลัง supervisor ตาย:** child ทำงานต่อเองโดยไม่มีใครดูแล ตอนนี้ child เฝ้า process แม่ และหยุดเมื่อ process แม่หายไป (บน Windows ห้ามใช้ pipe เพราะทำให้การ import numpy ค้าง)
- **Thai encoding บน Windows:** `knowledge_storm` เปิดไฟล์โดยไม่ระบุ encoding แก้โดยให้ child รันในโหมด UTF-8
- **OpenRouter ไม่ทำตามคำสั่งปิด reasoning:** บางโฮสต์ไม่ทำตาม แก้โดยใช้ `provider.require_parameters` แต่ `deepseek/deepseek-v4.1-flash` ยังคิดต่อบนโฮสต์ DeepInfra อยู่ดี จึงใช้กับ STORM ไม่ได้
- **PDF ตัดหลักฐานทิ้ง:** Chromium ไม่พิมพ์เนื้อหาใน `<details>` ที่ยังปิดอยู่ ตอนนี้เปิดไว้ทั้งหมดตอนพิมพ์ PDF
- **Section ท้ายเล่มหลุดเข้ารายงานภาษาไทย:** ตัวกรองของ STORM จับ "See also" และ "References" จากชื่อภาษาอังกฤษเท่านั้น "ดูเพิ่ม (See Also)" จึงหลุดเข้ามา ตอนนี้ตัวแปลงตัดทิ้งให้ทั้งภาษาไทยและอังกฤษ

**เปรียบเทียบโมเดล** (หัวข้อ RAG ภาษาไทย ค่าตั้งเดียวกัน)
- **`qwen/qwen3.7-flash`:** ภาษาไทยดี ค่าใช้จ่ายต่ำกว่า $0.01 ต่อรายงาน แต่ outline แกว่งมาก ได้ 9, 3 และ 1 section ใน 3 รอบ และคำตอบช่วง research ถูกตัดท้าย
- **`google/gemini-3.5-flash-lite`:** ได้ 15 section, 12 แหล่ง, citation 60 จุดถูกทุกจุด และคำตอบไม่ถูกตัดท้าย ค่าใช้จ่ายราว $0.04 ต่อรายงาน โมเดลนี้ปิดการคิดไม่ได้ ต้องตั้ง reasoning `effort:minimal` และงบ token สนทนา 1,500 / เขียน 4,000 เป็นตัวเลือกค่าเริ่มต้นที่ดีกว่า แต่เพิ่งทดสอบรอบเดียว

**ปัญหาที่ยังค้างอยู่**
- **คำตอบภาษาไทยในขั้น research ถูกตัดท้าย:** STORM ตัดประโยคด้วย `.!?` จึงไปตัดที่เลขข้อในรายการ เช่น `\n3.` ทำให้ข้อสุดท้ายของคำตอบหายไป ต้องแก้ใน `knowledge_storm/utils.py` ซึ่งจะกระทบแอปเดิมด้วย
- **ความยาวรายงานขึ้นกับโมเดล:** โมเดลที่เขียน outline สั้น (Qwen) ได้รายงานที่สั้นตามไปด้วย ควรกำหนดจำนวน section ขั้นต่ำ หรือบอกผู้ดูแลว่าควรเลือกโมเดลไหน
- **ข้อความไทยที่ copy จาก PDF เพี้ยน:** ภาพที่พิมพ์ออกมาถูกต้อง แต่ text layer สลับตำแหน่งสระและวรรณยุกต์ ต้องทดสอบกับ Noto Sans Thai ใน Docker
- **ขนาดของ image Worker:** `knowledge_storm` บังคับ import `sentence_transformers` ซึ่งต้องใช้ torch ควรใช้ torch แบบ CPU
- **`run_config.json` ของ STORM มีเลขท้าย 4 หลักของ API key:** STORM redact ไว้แล้วตามปกติ แต่ต้องตัดสินใจว่าจะยอมให้ข้อมูลนี้อยู่ในไฟล์ของ Run หรือไม่

## ก่อนเริ่มรุ่นสอง

- Support Access Grant
- Agent Research: import เป็น library แล้วเขียน adapter
- Deep Research: เพิ่ม endpoint ฝั่ง server ใน fork ของ Nuxt ก่อน แล้วจึงเขียน adapter
- Co-STORM: ออกแบบ Discussion (หลาย Turn และเก็บ state ถาวร) อาจเปลี่ยนความคืบหน้าเป็น SSE

## จุดตรวจแรก

ก่อนลงมือสร้างหน้าจอทั้งหมด ให้พิสูจน์ว่ารายงานจริงหนึ่งชิ้นสร้างได้โดยไม่มี Streamlit และแหล่งอ้างอิงที่แปลงออกมาตรงกับรายงาน นี่คือความเสี่ยงด้านการเชื่อมต่อที่ควรคลี่คลายก่อน
