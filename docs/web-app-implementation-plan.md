# Web App — แผนทางเทคนิคและลำดับพัฒนา

สถานะ: ร่างข้อเสนอทางเทคนิค ยังไม่ได้เริ่มพัฒนาเว็บใหม่ ขอบเขตที่ผู้ใช้ยืนยันอยู่ใน [web-app-design.md](./web-app-design.md) และคำศัพท์อยู่ใน [CONTEXT.md](../CONTEXT.md)

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

## โครงสร้างที่เสนอ

- **Web**: หน้าล็อกอิน Dashboard Projects Sessions Reports Sources และ Settings เรียก Application Backend เท่านั้น
- **Application Backend (Python)**: รวมบัญชี สิทธิ์ Projects/Sessions การส่งงาน โควตา และการอ่านผลในแอปเดียวก่อน เพื่อใช้ภาษาเดียวกับ engine และลดส่วนเชื่อมต่อระหว่างภาษา
- **Worker (Python)**: แยก process/container จาก Backend เรียก engine และสร้างผลลัพธ์ งานวิจัยไม่อยู่ใน HTTP request
- **PostgreSQL**: ข้อมูลผู้ใช้ ownership สถานะ Run การจองโควตา และการจัดสรรคิว
- **Persistent file volume**: เก็บผลดิบ ผลที่แปลงแล้ว และ export ตาม Run; ส่งไฟล์ผ่าน Backend ที่ตรวจสิทธิ์ ไม่เปิดไดเรกทอรีโดยตรงให้ browser

เริ่มจาก Web, Backend, Worker และ PostgreSQL ใน Compose เดียว ระบบบัญชีเป็นส่วนหนึ่งของ Backend ได้ ไม่จำเป็นต้องมี container สำหรับทุกหน้าที่ ส่วน framework และ library จะเลือกพร้อมตรวจความเข้ากันได้ก่อนสร้างโครงโปรเจกต์

ข้อเสนอสำหรับคิวรุ่นแรกคือใช้ PostgreSQL เป็นแหล่งสถานะและคิวถาวร เพื่อลดการประสานข้อมูลข้ามระบบบนเครื่องเดียว ต้องพิสูจน์การ claim งาน การจัดคิวแบบสลับผู้ใช้ และการป้องกันงานซ้ำด้วย integration tests ก่อนยึดเป็นข้อสรุป หากเลือก queue framework เพิ่มเติม ต้องปิดพฤติกรรมเริ่ม Run ใหม่อัตโนมัติหลัง Worker ล่มให้ตรงกับข้อกำหนด

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
- `support_access_grants`, `audit_events`: สิทธิ์อ่านเฉพาะ Run ตามผู้รับและเวลา พร้อมประวัติเข้าดู
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

1. **พิสูจน์ engine นอก Streamlit** — รันหัวข้อทดสอบผ่าน module ใหม่ เก็บผลแยกตาม Run ทดลอง progress, retry และ cancellation โดยใช้ fake provider สำหรับกรณีผิดพลาด และ API จริงสำหรับเส้นทางสำเร็จ
2. **ทำเส้นทางครบวงจรบน local** — Compose, migrations, bootstrap Admin, login, ตั้งค่าบริการ, Project/Session, ส่งงานให้ Worker และอ่านผล ใช้หน้าจอพื้นฐานก่อน
3. **ทำกติกางานและข้อมูลให้ครบ** — คิวสลับผู้ใช้ โควตา ค่า override งานข้ามเดือน ยกเลิก Worker interruption และลองใหม่ พร้อมทดสอบหลายผู้ใช้และคำขอพร้อมกัน
4. **ทำรายงานและการจัดการให้ครบ** — Source Explorer, export 3 รูปแบบ, ไทย/อังกฤษ, member management, support grants, ถังขยะ และหน้าจอ Dashboard/Settings
5. **ตรวจรับรุ่นแรก** — รันทุกรายการในเกณฑ์รับงาน รวมติดตั้งใหม่และ restart container แล้วข้อมูลยังอยู่ ก่อนเริ่มขอบเขตรุ่นสอง

## จุดตรวจแรก

ก่อนลงมือสร้างหน้าจอทั้งหมด ให้พิสูจน์ว่ารายงานจริงหนึ่งชิ้นสร้างได้โดยไม่มี Streamlit และแหล่งอ้างอิงที่แปลงออกมาตรงกับรายงาน นี่คือความเสี่ยงด้านการเชื่อมต่อที่ควรคลี่คลายก่อน
