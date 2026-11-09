# บั๊กที่ทำซ้ำได้ (BUG-01 ถึง BUG-59)

ฐานที่ตรวจ: branch `audit/2026-10-24` (HEAD `46ae8e0`) · ตรวจด้วย pytest กับแอปจริงบน Postgres (testcontainers) และ process ลูกของ fake engine ไม่เรียกโมเดลหรือบริการค้นหาจริง ไม่แตะ stack Docker ใดๆ

รายงานนี้เป็นส่วนของ Task 3 (อ่านโค้ดส่วนเสี่ยง) เฉพาะ 3 กลุ่มจาก 6 กลุ่ม: (a) `worker/` กับ `runner/` · (b) โควตา, limits และการเริ่ม/ลองใหม่/ยกเลิก Run · (c) ถังขยะและการลบถาวร กลุ่ม (d) (e) (f) อยู่ใน Task 3b (ย่อหน้าถัดไปและรหัส BUG-24 ขึ้นไป)

ผู้อ่านโค้ดส่งข้อสงสัยมา 30 ข้อ (a 9, b 10, c 11) แต่ละข้อถูกลองทำซ้ำด้วยตัวเองตามขั้นตอนของ `superpowers:systematic-debugging`: อ่านโค้ดที่อ้าง ตั้งสมมติฐาน แล้วพยายามให้เกิดจริง ผลคือ **23 รหัสบั๊ก** (คลุม 23 ข้อสงสัยจากผู้อ่าน; ข้อที่เป็นรากเดียวกันถูกรวมเป็นรหัสเดียว และบางรหัสมีหลายเทสต์), **4 ข้อสงสัย** ที่ทำซ้ำไม่ได้, **3 ข้อที่ตัดทิ้ง**

**ส่วนที่สอง (Task 3b): กลุ่ม (d) (e) (f)** ฐานที่ตรวจ HEAD `15687d5` · (d) Discussion/Co-STORM Turn · (e) หน้าสถานะระบบ (`monitor.py`, `outcomes.py`), บัญชีผู้ใช้ใน `api/admin.py`, การ login/ตั้งรหัส · (f) MCP, token, engine Deep และ Medical (MRA) ผู้อ่านส่งข้อสงสัยมา 35 ข้อ (d 11, e 12, f 12) ลองทำซ้ำทีละข้อตาม `superpowers:systematic-debugging` ผลคือ **21 รหัสบั๊กใหม่ (BUG-24 ถึง BUG-44) คลุม 22 ข้อสงสัย** (e-S3 กับ f-S11 เป็นรากเดียวกันจึงรวมเป็น BUG-30), **2 ข้อสงสัย** ที่ต้องใช้เบราว์เซอร์ (ส่งต่อ Task 8/9 หรือ Task 5), **3 ข้อที่ซ้ำ** กับรหัสที่มีอยู่แล้ว (BUG-09, 12/15, 19) และ **8 ข้อที่ตัดทิ้ง** เทสต์ใหม่ทุกข้อต่อท้าย `server/tests/test_audit_findings.py` ใต้หัวข้อ `Task 3b` และรันด้วย `--runxfail` ครั้งหนึ่งแล้วว่าล้มที่ assertion ของตัวเอง ไม่มีข้อใดเป็น **วิกฤต** ข้อเดียวที่เป็น **กลาง** คือ BUG-26 นอกนั้นเป็น **ต่ำ**: `cd server && uv run pytest tests/test_audit_findings.py -k "bug24 or bug25 or bug26 or bug27 or bug28 or bug29 or bug3 or bug4" --runxfail`

**ส่วนที่สาม (Task 4): ตรวจโค้ดอัตโนมัติ, migration และ backup** ฐานที่ตรวจ HEAD `d61f170` · `ruff check src --select F,B,E9` 162 รายการ: B008 138 (`Depends(...)` ในค่าเริ่มต้นของ argument ซึ่งเป็นแบบแผนของ FastAPI), B904 9 (raise ใน except ไม่มี `from`), B905 7 (`zip` ไม่มี `strict`; ตรวจ 4 จุดที่ไม่ใช่ render แล้ว ไม่มีการตัดข้อมูลเงียบๆ), F401 4 (import ที่ไม่ใช้), B023 1 (false positive), B007 1, F811 1 ไม่ใช่บั๊กทั้งหมด เหลือ 1 รายการจริงคือ invalid-syntax (BUG-45) · migration ลง base แล้วขึ้น head ผ่านทุกขั้น แต่ `alembic check` พบ model กับ migration ไม่ตรง (BUG-46) · backup/restore ผ่าน แต่ตัวเลขใน `backup.sh` หลอกตา (BUG-47) · เทสต์ที่ไม่เสถียรที่รู้อยู่แล้วลงเป็น BUG-48 **รหัสใหม่ BUG-45 ถึง BUG-48 เป็น ต่ำ ทั้งหมด**

**เกณฑ์ระดับ** ตามสเปก: **วิกฤต** ข้อมูลรั่วหรือระบบใช้ไม่ได้ · **สูง** กระทบผู้ใช้จริงบ่อย หรือต้องมีสิทธิ์บางอย่าง · **กลาง** · **ต่ำ** ไม่มีข้อใดในชุดนี้เป็น **วิกฤต** เพราะทุกข้อต้องมีบัญชีที่ login แล้ว หรือต้องมีความผิดปกติของระบบเกิดก่อน

**หลักฐาน:** BUG-01 ถึง BUG-44 และ BUG-53 ถึง BUG-57 มีเทสต์ใน `server/tests/test_audit_findings.py` (ข้อยกเว้น: BUG-45 ถึง 48 มีหลักฐานเป็นคำสั่งที่รันซ้ำได้ ไม่มี xfail · BUG-49 ถึง 52 มาจาก Run จริงใน [live.md](live.md) · BUG-58, 59 เป็นขั้นตอนทำซ้ำในเบราว์เซอร์ เพราะเว็บไม่มี test framework) เทสต์เหล่านั้นยืนยันพฤติกรรมที่ **ถูกต้อง** เป็น `xfail(strict=True, raises=AssertionError, reason="BUG-xx")` จึงล้มวันนี้และจะผ่านเมื่อแก้ (strict จะฟ้องให้ถอด mark) ทุกเทสต์ถูกรันครั้งหนึ่งด้วย `--runxfail` เพื่อยืนยันว่าล้มที่ assertion ของตัวเอง ไม่ใช่ error อื่น: `cd server && uv run pytest tests/test_audit_findings.py -k test_bug --runxfail`

## สรุป

| รหัส | ระดับ | เรื่อง | ผู้ใช้เห็นไหม | ข้อสงสัยที่คลุม |
|---|---|---|---|---|
| BUG-09 | **สูง** | เริ่มงานสองอันพร้อมกันจากบัญชีเดียวกัน (สอง tab, ลูกค้า MCP ที่เรียกขนาน) เกิด deadlock ใน Postgres คนหนึ่งได้ 500 | ใช่ | b-S1 (ส่วนเริ่ม) |
| BUG-01 | **สูง** | ขั้นใดขั้นหนึ่งใน loop หลักของ Worker (purge, sweep, claim) พลาดครั้งเดียว process ก็จบ | ไม่ (เห็นเป็นคิวค้าง) | a-S1, c-S3 |
| BUG-02 | กลาง | Run ที่ค้างอยู่ในคิวหลังถูก purge ทำให้ `claim()` พังทุกรอบ ไม่มีใครได้เริ่มงาน | ไม่ (เห็นเป็นคิวค้าง) | b-S8 |
| BUG-03 | กลาง | Run ที่เข้าคิวระหว่างที่ Session ถูกลบ ถูก Worker หยิบไปทำทั้งที่อยู่ในถังขยะ | ไม่ | c-S5 |
| BUG-04 | กลาง | supervisor พลาดกลางทาง process ลูกยังวิ่งต่อโดยไม่มีใครดู ส่วน Run ถูกเขียนเป็น failed และคืนโควตา | ใช่ | a-S2 |
| BUG-05 | กลาง | Run ที่เสีย lease (ถูกกวาดเป็น interrupted) ยังวิ่งต่อจนจบ แล้วรายงานถูกทิ้ง | ใช่ | a-S3 |
| BUG-13 | กลาง | กด "ลองใหม่" ซ้ำสร้าง Run ใหม่ทุกครั้ง หักโควตาทุกครั้ง | ใช่ | b-S4 |
| BUG-17 | กลาง | หลังลบถาวร ข้อความที่ผู้ใช้พิมพ์ (`runs.turn`) และบันทึก (`runs.notes`) ยังอยู่ในฐานข้อมูล | ไม่ | c-S1 |
| BUG-18 | กลาง | รายการงานของ MCP และหน้าบัญชี integration แสดงงานในถังขยะ และเปลือกว่างหลัง purge | ใช่ | c-S2 |
| BUG-26 | กลาง | ปิดโหมด Co-STORM แล้ว Discussion ที่เริ่มไว้แล้วยังถามต่อได้ (ทุก Turn รวม auto 10 ขั้นและรายงาน) ผู้ดูแลหยุดค่าใช้จ่ายด้วยสวิตช์นี้ไม่ได้ | ใช่ | d-S4 |
| BUG-06 | ต่ำ | รายงานที่โหลดไม่ผ่านทำให้ thread ของ Run จบเงียบๆ Run ค้าง "running" แล้วถูกกวาดเป็น interrupted + คืนโควตา | ใช่ | a-S4 |
| BUG-07 | ต่ำ | กดยกเลิกในช่วงท้าย Run ถูกบันทึกเป็น succeeded หรือ failed + คืนโควตา แทน cancelled | ใช่ | a-S5 |
| BUG-08 | ต่ำ | Run ของ MRA ที่หมดเวลาไม่ปล่อย review ที่ MRA (ปล่อยเฉพาะ cancelled) | ไม่ | a-S7 |
| BUG-10 | ต่ำ | ส่ง Turn เดียวกันสองครั้งพร้อมกัน ครั้งที่สองได้ 409 ทั้งที่ Turn ถูกสร้างแล้ว | ใช่ | b-S1 (ส่วน Turn) |
| BUG-11 | ต่ำ | ส่งงานเดียวกันสองครั้งพร้อมกันตอนเหลือโควตาหน่วยสุดท้าย ครั้งที่สองได้ 429 ทั้งที่งานถูกสร้างแล้ว | ใช่ | b-S2 |
| BUG-12 | ต่ำ | "ลองใหม่" ของ Turn ที่ล้มไม่ล็อก Discussion สองคำขอพร้อมกันได้สอง Turn คิวซ้อน | ใช่ | b-S3 |
| BUG-14 | ต่ำ | "ลองใหม่" ข้ามการตรวจที่การส่งงานใหม่ทำ (โหมดที่ผู้ดูแลปิดแล้วก็ยังเข้าคิว) | ใช่ | b-S5 |
| BUG-15 | ต่ำ | "ลองใหม่" ของ Turn ที่เปิดชุดใหม่แล้วล้ม (โควตาคืน) ตอบ 409 `turns_exhausted` เสมอ | ใช่ | b-S6 |
| BUG-16 | ต่ำ | เลือกโมเดลใหม่ให้ Run ที่ถูกพักไม่ตรวจว่าโมเดลใช้กับโหมดได้ไหม | ใช่ | b-S7 |
| BUG-19 | ต่ำ | MCP start ซ้ำภายใน 10 นาทีหลังลบ Session ได้ 404 และไม่เริ่มงานใหม่ | ใช่ | c-S4 |
| BUG-20 | ต่ำ | ผู้ดูแลอ่านงานของบัญชี integration ที่อยู่ใน Session ที่ถูกลบได้ (ทางเจ้าของได้ 404) | ไม่ | c-S7 |
| BUG-21 | ต่ำ | ลบไฟล์ของ Run ไม่สำเร็จแต่ตั้ง `purged_at` ไปแล้ว ไฟล์ค้างบนดิสก์ตลอด | ไม่ | c-S8 |
| BUG-22 | ต่ำ | กู้คืน Session ที่ Project อยู่ในถังขยะ ตอบ 204 แต่ Session ยังมองไม่เห็น | ใช่ | c-S9 |
| BUG-23 | ต่ำ | รายการหัวข้อ (`/sessions`) ยิง query หนึ่งครั้งต่อหัวข้อ (สูงสุด 500) | ไม่ (ช้าลงตามประวัติ) | c-S10 |
| BUG-24 | ต่ำ | ผู้ดูแลเปลี่ยน `turns_per_quota` ระหว่างที่ Discussion ใช้อยู่ ชุด Turn ที่จ่ายไปแล้วถูกคำนวณใหม่ย้อนหลัง (ลดค่า: Turn ที่จ่ายแล้วถูกปฏิเสธ; เพิ่มค่า: Turn ที่ใช้ไปแล้วกลายเป็นของฟรี) | ใช่ | d-S1 |
| BUG-25 | ต่ำ | รายงานที่เสร็จตอนเจ้าของกดหยุดพอดี ถูกบันทึกเป็น cancelled (หน่วยโควตาไม่คืน) แต่ไม่ถูกแสดงในรายการรายงานของหน้า Discussion | ใช่ | d-S2 |
| BUG-27 | ต่ำ | หัวข้อ Discussion ยาว 301-500 ตัวอักษรผ่านการตรวจแล้วถูกตัดเหลือ 300 กลางประโยค และ Co-STORM ค้นจากหัวข้อที่ตัดแล้ว | ใช่ | d-S8 |
| BUG-28 | ต่ำ | ผู้ดูแลสองคนกด "รับทราบ" พร้อมกัน: อีกคนหาย หรือ (ครั้งแรกสุด) ได้ 500 | ใช่ (ได้ 500 / รับทราบหาย) | e-S1 |
| BUG-29 | ต่ำ | ปิดบัญชีผู้ใช้ที่มี Run ในคิว: Run ค้าง `queued` ตลอด นับในคิวและเวลารอที่เพิ่มขึ้นเรื่อยๆ บนหน้าสถานะระบบ | ใช่ | e-S2 |
| BUG-30 | ต่ำ | PATCH บัญชีผู้ใช้หรือ integration ด้วยค่า null ใน `is_active`/`name`/`role` ได้ 500; ชื่อเว้นวรรคล้วนถูกเก็บเป็นชื่อว่าง | ใช่ (ได้ 500) | e-S3, f-S11 |
| BUG-31 | ต่ำ | `auth_sessions` ที่หมดอายุไม่เคยถูกลบ เพิ่มหนึ่งแถวต่อการ login ตลอดไป | ไม่ | e-S4 |
| BUG-32 | ต่ำ | หัวข้อสั้นถูกแทนที่ในข้อความผิดพลาดแม้อยู่กลางคำ ทำให้ข้อความอ่านไม่ออกและแตกความล้มเหลวเดียวเป็นหลาย Issue | ใช่ | e-S6 |
| BUG-33 | ต่ำ | คำในหัวข้อ ("rate limit", "401k") ตัดสินสาเหตุของ engine_error จึงถูกจัดเป็นผู้ให้บริการปฏิเสธทั้งที่เป็นความผิดของโค้ดเรา | ใช่ | e-S8 |
| BUG-34 | ต่ำ | กุญแจของ Issue: id แบบ hex ทำให้ความล้มเหลวเดียวกันแตกเป็นหลาย Issue, ส่วนข้อความที่เหมือนกัน 40 ตัวแรกรวมสาเหตุต่างกันเป็น Issue เดียว | ใช่ | e-S9 |
| BUG-35 | ต่ำ | ลิงก์ตั้งรหัสผ่านใช้ได้สองครั้งถ้าสองคำขอมาพร้อมกัน (ทั้งคู่ได้ 200 และ login) | ใช่ | e-S10 |
| BUG-36 | ต่ำ | `PATCH /api/admin/users/{id}` แก้บัญชี integration ได้ (แม้ตั้ง role เป็น admin) ทั้งที่ลิงก์รีเซ็ตและลบตอบ 404 | ไม่ | e-S11 |
| BUG-37 | ต่ำ | `request_key` ที่เคยใช้กับ Turn ของ Discussion A ส่งกับ Discussion B: ได้ Turn ของ A กลับมา 201 และ B ไม่ได้ถูกถามอะไร | ใช่ (เฉพาะ client ที่ใช้ API ตรง) | d-S9 |
| BUG-38 | ต่ำ | รายงาน Co-STORM ที่อ้าง `[4][9]` (สอง snippet ของหน้าเดียวกัน) ถูกเขียนเป็น `[1][1]` | ใช่ | d-S11 |
| BUG-39 | ต่ำ | สั่ง MCP start ซ้ำทันทีหลัง cancel ได้ Run ที่กำลังถูกยกเลิกกลับมา พร้อมข้อความว่า "ไม่ใช้โควตา" | ใช่ | f-S2 |
| BUG-40 | ต่ำ | Medical: 503 ครั้งเดียวตอนถามสถานะหลัง stream ปิด หรือตอนดึงผลสุดท้าย ทำให้ Run ล้มทั้งที่ review ของ MRA ไม่เป็นอะไร; 401 บน stream ถูกรายงานเป็น service_unavailable | ใช่ | f-S4 |
| BUG-41 | ต่ำ | Medical: POST ที่ timeout แต่ MRA รับไปแล้ว พอส่งซ้ำได้ `cached` แล้ว Run ถูกนับเป็นฟรี ราคา 0 และคืนโควตา | ใช่ | f-S5 |
| BUG-42 | ต่ำ | Medical: `evidence_quote` เป็น null ทำให้ `to_report` พัง (AttributeError) หลังจ่ายค่า review แล้ว | ใช่ | f-S6 |
| BUG-43 | ต่ำ | Deep: กดหยุดไม่ถูกสังเกตตราบที่ CLI ยังเขียนบรรทัดถี่กว่าวินาทีละครั้ง (ถูก kill หลัง 30 วินาทีแทน) | ใช่ | f-S8 |
| BUG-44 | ต่ำ | MCP: เลขหัวข้อย่อยที่ `outline` พิมพ์ (`2.1`) อ่านด้วย `section:2.1` ไม่ได้; เลขยูนิโค้ด (`²`) ทำให้ ValueError แทน ToolError | ใช่ | f-S12 |

"ผู้ใช้เห็นไหม" = ใช่ หมายถึงการแก้เปลี่ยนสิ่งที่ผู้ใช้เห็นหรือรู้สึก จึงต้องได้รับอนุมัติจากเจ้าของก่อนแก้ ตามข้อจำกัดของแผน ข้อ "ไม่" คือการแก้ที่ผู้ใช้ไม่เห็นความเปลี่ยนแปลง

ขนาดงานที่ให้: **เล็ก** ไม่เกินครึ่งวัน ไม่แตะ schema · **กลาง** หนึ่งวันขึ้นไป หรือแตะหลายที่

---

## BUG-09 — เริ่มงานสองอันพร้อมกันจากบัญชีเดียวกัน เกิด deadlock

| | |
|---|---|
| ระดับ | **สูง** กระทบผู้ใช้จริงบ่อย: ทำซ้ำได้ง่ายมาก และ client ของ MCP (Agenta, DeepWitya) เรียก tool ขนานกันเป็นปกติ |
| ผู้ใช้เห็นไหม | ใช่ (ปัจจุบันได้หน้า error 500; หลังแก้งานเริ่มได้ทั้งสองอัน) |
| หลักฐาน | `api/research.py:660-663` (`_start_session` แทรก `ResearchSession` แล้ว `flush()` ก่อน) → `:663` `new_run` → `quota.py:292` (`check_submit` ล็อกแถวผู้ใช้ `FOR UPDATE`); เส้นเดียวกันที่ `api/discussions.py:251-255` (`start` แทรก Session แล้วค่อยเข้า `new_turn` → `check_submit`) · `api/mcp.py:570` เรียก `_start_session` เหมือนกัน · เทสต์ `test_bug09_two_research_starts_by_one_account_at_once_do_not_deadlock` และ `test_bug09_two_discussion_starts_by_one_account_at_once_do_not_deadlock` |

**สถานการณ์:** ผู้ใช้คนเดียว (หรือ token เดียว) ส่งคำขอเริ่มหัวข้อใหม่สองคำขอเกือบพร้อมกัน แต่ละคำขอแทรกแถว `research_sessions` ซึ่งมี foreign key ไปที่แถวของผู้ใช้ จึงได้ล็อกแบบแบ่งปัน (`FOR KEY SHARE`) บนแถวนั้น แล้วจึงขอล็อก `FOR UPDATE` บนแถวเดียวกันใน `check_submit` ซึ่งชนกับล็อกแบ่งปันของอีกคำขอ ต่างฝ่ายต่างถือและรอกัน Postgres ตัดคำขอหนึ่งทิ้งด้วย `DeadlockDetected`

**วัดจริง:** ยิงสองคำขอ (คนละ `request_key`) พร้อมกัน 8 รอบ โดยไม่ใส่ตัวช่วยจังหวะใดๆ: 7 รอบมีคำขอหนึ่งได้ `OperationalError: deadlock detected` (`while locking tuple in relation "users"`) เทสต์ใส่ barrier ที่ `_existing` เพื่อให้เกิดซ้ำได้ทุกครั้ง

**ข้อสังเกตเรื่อง b-S1 (เริ่ม Discussion ซ้ำด้วย key เดียว):** ผู้อ่านคาดว่าจะได้ IntegrityError ที่ `flush` แต่ในทางปฏิบัติ deadlock เกิดก่อน จึงแยกพิสูจน์ IntegrityError ไม่ได้ ส่วนที่แยกได้ (Turn ซ้ำ) อยู่ที่ BUG-10

**วิธีแก้ที่เสนอ:** ล็อกแถวผู้ใช้ (`FOR UPDATE`) ก่อนแทรก Session (ย้าย `check_submit` ขึ้นก่อน `flush`, หรือเรียก `select(User.id)...with_for_update()` เป็นบรรทัดแรกของ `_start_session` และ `start`) เพื่อให้ลำดับการล็อกเหมือนกันทุกเส้นทาง · ขนาด: เล็ก

## BUG-01 — ขั้นเดียวใน loop หลักของ Worker พลาด process ก็จบ

| | |
|---|---|
| ระดับ | **สูง** ไม่มี Run ไหนถูกหยิบจนกว่า process จะถูกเริ่มใหม่ และถ้าสาเหตุคงอยู่ (purge เป็นขั้นแรกของทุกการเริ่ม) ก็วนเป็น crash loop; Run ที่กำลังทำถูกกวาดเป็น interrupted และคืนโควตา |
| ผู้ใช้เห็นไหม | ไม่ (ผู้ใช้เห็นคิวค้างหรือ Run "interrupted"; การแก้ไม่เปลี่ยนสิ่งที่เห็น นอกจากทำให้ไม่เกิด) |
| หลักฐาน | `worker/main.py:128-147`: `purge_now()`, `queue.sweep_interrupted`, `queue.claim` เรียกตรงๆ ไม่มี try/except (ต่างจาก `run_one` ที่มี "the Run must still end" ที่ `main.py:89`) · เทสต์ `test_bug01_one_failed_step_does_not_end_the_workers_process` (3 รูปแบบ: `purge`, `sweep_interrupted`, `claim`) |

**สถานการณ์:** Postgres รีสตาร์ต/connection หลุดชั่วคราว, deadlock, หรือ purge เจอแถวผิดปกติ (ดู BUG-02) ใน 3 ขั้นนั้น ข้อยกเว้นหลุดออกจาก `main()` เทสต์สั่ง `OperationalError` ในแต่ละขั้น: `main()` ยก `OperationalError` ออกมาทั้ง 3 กรณี

**วิธีแก้ที่เสนอ:** ครอบแต่ละขั้นด้วย `try/except Exception` ที่ log (`log.exception`) แล้วไปรอบถัดไป (พร้อมหน่วงสั้นๆ กันวนถี่) · ขนาด: เล็ก

## BUG-02 — Run ที่ถูก purge ทั้งที่ยัง queued ทำให้ `claim()` พังทุกรอบ

| | |
|---|---|
| ระดับ | กลาง ผลต่อทุกคนรุนแรง (ไม่มีใครได้เริ่มงาน) แต่ต้องเกิดความผิดปกติก่อน (BUG-03) |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | `trash.py:171-179` (purge เลือก Run ที่ `status not in ACTIVE` ซึ่งรวม `queued`/`needs_selection`) → `trash.py:191` (`run.config = {"llm": {...}}` ลบ `search` ทิ้ง) → `worker/queue.py:173-174` (`_secrets`: `llm["provider"]` → `KeyError: 'provider'`, ก่อนถึง `queue.py:138` ที่ `run.config["search"]`) · `claim` เรียงตามลำดับเดิมทุกครั้ง Run นี้จึงอยู่หัวแถวตลอด · เทสต์ `test_bug02_a_purged_run_that_was_still_queued_does_not_stop_everyone_elses` |

**สถานการณ์:** Run ที่ยัง queued อยู่ใน Session ที่ถูกลบ ครบ 30 วัน purge ล้าง config ของมัน (ไม่คืนโควตา) Run ยัง `queued` อยู่ `claim()` ยก `KeyError: 'provider'` ทุกครั้ง ผู้ใช้คนอื่นไม่ได้เริ่มงาน (ร่วมกับ BUG-01 คือ process ตายวนซ้ำ) วิธีให้ Run แบบนี้เกิดจริงที่พบคือ BUG-03

**ข้อสังเกตเรื่อง b-S8 (key ถอดรหัสไม่ได้):** สมมติฐานเดิมของผู้อ่าน (credential ที่เข้ารหัสด้วย secret key เก่า) **ทำซ้ำไม่ได้**: `security.decrypt` จับ `InvalidToken` แล้วคืน `""` (`security.py:74-75`) ทดลองใส่ ciphertext ขยะแล้ว `claim()` ผ่าน กลไก poison pill ที่ผู้อ่านอธิบายนั้นจริง แต่ตัวกระตุ้นคือ config ที่ว่างเปล่าด้วยทางนี้

**วิธีแก้ที่เสนอ:** (1) purge ไม่แตะ Run ที่รออยู่ ให้ยกเลิก+คืนโควตาก่อน (เหมือน `_stop`) · (2) `claim` ครอบการสร้าง `Claim` ด้วย try/except: ถ้าสร้างไม่ได้ ให้ปิด Run นั้นเป็น `failed/bad_configuration` (คืนโควตา) แล้วไปตัวถัดไป · ขนาด: เล็ก

## BUG-03 — Run ที่เข้าคิวระหว่างที่ Session ถูกลบ ถูกหยิบไปทำ

| | |
|---|---|
| ระดับ | กลาง (race แคบ แต่เงินของเจ้าของถูกใช้ในที่ที่เขาลบทิ้ง และเป็นทางเกิดของ BUG-02) |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | `api/research.py:764-768` (`create_run`: `deps.own` แล้ว `new_run` แล้ว commit ไม่มีการล็อกหรือตรวจ Session ซ้ำ) กับ `trash.py:72-93` (`_stop` หยุดเฉพาะ Run ที่มีอยู่ ณ ขณะนั้น) · `worker/queue.py:81-99` (`_next_run` ไม่ดู Session/Project ที่ถูกลบ) · เทสต์ `test_bug03_a_run_queued_while_its_session_is_trashed_is_not_started` (สอดแทรกการลบ Session ผ่าน connection ที่สองระหว่าง `deps.own` กับ `check_submit` ซึ่งเป็นช่วงที่คำขอลบจริงจะแทรกได้) |

**สถานการณ์:** คำขอ A (สร้าง Run ใน Session) ผ่านการตรวจสิทธิ์แล้วกำลังเช็กโควตา คำขอ B (ลบ Session) commit ก่อน A แทรก Run Run ของ A เป็น `queued` ใน Session ที่อยู่ในถังขยะ `claim()` คืน Claim ของมัน

**วิธีแก้ที่เสนอ:** ให้ `claim`/`_next_run` ข้าม Run ที่ `trash.run_alive` เป็นเท็จ (ยกเลิกและคืนโควตาถ้าเจอ) และ/หรือให้ `create_run` ล็อกแถว Session แล้วตรวจ `trashed_at` ใหม่ก่อนแทรก · ขนาด: เล็ก

## BUG-04 — supervisor พลาดกลางทาง process ลูกยังวิ่งต่อ

| | |
|---|---|
| ระดับ | กลาง (ต้องมี DB กระตุกหรือไฟล์ events เสีย แต่ผลคือเงินรั่วและงานซ้ำ) |
| ผู้ใช้เห็นไหม | ใช่ (ผู้ใช้เห็น Run "failed" พร้อมคืนโควตา และอาจกดลองใหม่ทำให้งานซ้ำสองชุด) |
| หลักฐาน | `runner/supervisor.py:203-221` (loop เรียก `drain()`, `heartbeat()`, `should_cancel()` ไม่มี try/finally; `proc` ไม่ถูก kill/wait); `supervisor.py:66` (`json.loads` บรรทัดเสียยกข้อยกเว้น) → `worker/main.py:89-93` (catch-all เขียน `failed/engine_error` ไม่มี usage) · เทสต์ `test_bug04_an_error_in_the_supervisor_does_not_leave_the_child_running` (heartbeat ยก `RuntimeError` ครั้งที่สอง: `supervise` ยกข้อยกเว้นออกมา และ process ลูก (fake engine นอนหลับ 30 วินาที) ยังมีชีวิตหลังจากนั้น) |

**วิธีแก้ที่เสนอ:** `try/finally` ใน `supervise` ที่ `kill()`+`wait()` process ลูกเมื่อออกด้วยข้อยกเว้น; ครอบ `heartbeat`/`should_cancel` ให้ล้มเงียบแบบมี log (การต่อ DB พลาดครั้งเดียวไม่ควรฆ่า Run); ข้ามบรรทัด event ที่ parse ไม่ได้ · ขนาด: เล็ก

## BUG-05 — Run ที่เสีย lease วิ่งต่อจนจบ

| | |
|---|---|
| ระดับ | กลาง (ต้องมี heartbeat ช้าเกิน 60 วินาที เช่น host หลับหรือ DB ไม่ตอบ แต่ผลคือรายงานที่ทำเสร็จถูกทิ้งและเกินจำนวน Run พร้อมกัน) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `worker/main.py:58-60` (`heartbeat` เมื่อ `renew` คืน False แค่ log) · `worker/queue.py:236-240` (`renew`), `:312-328` (`sweep_interrupted`), `:232-233` (`_held`: `finish` ไม่เจอแถวจึงทิ้งผล) · เทสต์ `test_bug05_a_run_that_lost_its_lease_is_stopped` (หลัง 1 วินาที เทสต์ทำให้ lease หมดอายุและกวาด; `run_one` ใช้เวลา **11.1 วินาที** ใกล้เคียงงานทั้งชุดที่นอน 10 วินาที ไม่ได้หยุดทันที; สถานะสุดท้าย `interrupted`) |

**ผลที่ตามมา:** (1) child ใช้โทเคนต่อจนจบหรือ deadline (2) slot ที่ว่างเพราะกวาดไปแล้วถูกคนอื่นเติม เกิน `max_concurrent_total` (3) รายงานที่เสร็จถูกทิ้งเพราะ `finish` ไม่ตรงแถว ผู้ใช้เห็น "interrupted" และได้โควตาคืน (4) ปุ่มยกเลิกไม่ทำงานอีก

**วิธีแก้ที่เสนอ:** เมื่อ `renew` คืน False ให้ supervisor ฆ่า process ลูกทันที (ส่งสัญญาณกลับจาก `heartbeat`) และไม่เขียนผลใดๆ · ขนาด: เล็กถึงกลาง

## BUG-13 — "ลองใหม่" ซ้ำสร้าง Run ใหม่ทุกครั้ง

| | |
|---|---|
| ระดับ | กลาง (เสียโควตาและเงินจริง; ปุ่มแสดงอยู่ที่การ์ดของ Run ที่ล้มตลอด จึงกดซ้ำได้ทุกเมื่อ) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `api/research.py:806-859` (`retry`: สร้าง Run โดยไม่มี `request_key` และไม่ทำเครื่องหมายว่า `old` ถูกลองใหม่แล้ว; เงื่อนไขมีแค่ `old.status in (FAILED, INTERRUPTED, CANCELLED)` ซึ่งจริงตลอด) · `web/src/pages/research.tsx:746` (ปุ่มแสดงเมื่อ `canRetry`) · เทสต์ `test_bug13_trying_a_failed_run_again_twice_does_not_queue_it_twice` (เรียก retry สองครั้ง: ได้ 201 สองครั้งคนละ id, `reserved` = 2) |

**วิธีแก้ที่เสนอ:** ปฏิเสธ (409) หรือคืน Run ลูกเดิมเมื่อ Run ที่ลองใหม่จาก `old` นี้ยังรอ/ทำอยู่ (หรือกำหนด `request_key` จาก id ของ `old`) · ขนาด: เล็ก

## BUG-17 — หลังลบถาวร ข้อความของผู้ใช้ยังอยู่ในฐานข้อมูล

| | |
|---|---|
| ระดับ | กลาง (ผิดสัญญาที่ docstring ของ `trash.py` ให้ไว้ว่าลบ "topic, events, files, the report" และเก็บเพียงข้อมูลบัญชี; ไม่ถึงขั้นเปิดให้คนอื่นอ่าน) |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | `trash.py:180-191`: purge ล้าง `topic, report_title, message, request_key, source_count, config` แต่ไม่แตะ `turn` (`db/models.py:285`: มี `text` ที่ผู้ใช้พิมพ์ใน Turn แบบ say) และ `notes` (`models.py:301`: `interpretation` ที่ระบบตีความหัวข้อ, review_id ฯลฯ) · เทสต์ `test_bug17_the_purge_blanks_what_a_discussions_owner_typed` (สร้าง Discussion พิมพ์ "my private question about the clinic", ลบ, อายุ 31 วัน, purge: ทั้ง 2 แถวยังมี `turn` และแถวหนึ่งยังมี `notes.interpretation`) |

**วิธีแก้ที่เสนอ:** ใน purge ตั้ง `run.turn = None` และ `run.notes = {}` (หรือเก็บเฉพาะ `notes.cost` ถ้าต้องใช้บัญชี) · ขนาด: เล็ก

## BUG-18 — MCP และหน้า integration แสดงงานในถังขยะ

| | |
|---|---|
| ระดับ | กลาง (ผู้ใช้/agent เห็นรายการที่เปิดไม่ได้ และหลัง purge เป็นแถวว่างถาวร) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `api/mcp.py:755` และ `api/tokens.py:247` กรองแค่ `Run.trashed_at.is_(None)` การลบ Session/Project ทำเครื่องหมายที่แถวนั้น ไม่ใช่ที่ Run (`trash.py:5-6`) ขณะที่ลิสต์ของเว็บใช้การตรวจ parent และ `purged_at` · เทสต์ `test_bug18_mcp_list_does_not_show_research_in_a_trashed_session` (ลบ Session แล้ว `research_list` ยังคืน Run สถานะ cancelled; `GET /api/runs/{id}` ของเว็บตอบ 404), `test_bug18_mcp_list_does_not_show_an_empty_shell_after_the_purge` (หลัง purge ยังคืนแถว `topic: ""`), `test_bug18_an_integrations_recent_runs_leave_out_the_trash` |

**วิธีแก้ที่เสนอ:** กรองด้วย `Run.purged_at IS NULL` และเงื่อนไขว่า Session/Project ยังไม่ถูกลบ (join แบบเดียวกับ `trash.listing`) หรือใช้ตัวช่วยร่วมกัน · ขนาด: เล็ก

## BUG-06 — รายงานโหลดไม่ผ่านทำให้ Run ค้างแล้วถูกกวาดเป็น interrupted

| | |
|---|---|
| ระดับ | ต่ำ (ต้องมี `report.json` ที่ validator ปัจจุบันไม่ยอมรับ ซึ่งเกิดยาก; แต่ผลคือรายงานที่ทำเสร็จถูกประกาศว่า interrupted) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `worker/main.py:99-103` (`report_mod.load` และ `medical.release` อยู่นอก try ก่อน `queue.finish`); `report.py:133-137` (`load` ตรวจซ้ำ) · เทสต์ `test_bug06_a_report_that_cannot_be_read_does_not_leave_the_run_running` (`report.json` = `{}`: `run_one` ยกข้อยกเว้น และสถานะยังเป็น `running`) |

**วิธีแก้ที่เสนอ:** ครอบ 3 ขั้นหลัง `supervise` ด้วย try: ถ้าโหลดรายงานไม่ได้ ให้ปิดเป็น `failed/engine_error` พร้อม usage ที่เก็บได้ · ขนาด: เล็ก

## BUG-07 — กดยกเลิกช่วงท้ายแล้ว Run ถูกบันทึกเป็น succeeded หรือ failed

| | |
|---|---|
| ระดับ | ต่ำ (ผลต่อ Run หนึ่งๆ น้อย: สถานะและการคืนโควตาผิดไปจากที่ออกแบบ) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `worker/queue.py:269-309` (`finish` เขียนทับ `cancelling` ด้วยสถานะที่ได้รับ; `_held` รับ `ACTIVE` ซึ่งรวม `cancelling`); `runner/supervisor.py:208-229` (ดูคำขอยกเลิกเฉพาะรอบ poll เทียบ throttle 5 วินาทีที่ `main.py:84`; คอมเมนต์ที่ `:226` สัญญาว่า "the owner said stop, so the Run is cancelled") · เทสต์ `test_bug07_a_run_the_owner_cancelled_is_not_recorded_as_succeeded` (สถานะ `cancelling` แล้ว outcome succeeded → ได้ `succeeded`) และ `test_bug07_a_failure_after_cancel_was_pressed_does_not_give_the_quota_back` (outcome failed/engine_error → ได้ `failed` + `quota_refunded=True` ขณะที่ออกแบบให้ Run ที่เริ่มแล้วถูกยกเลิก "เก็บโควตา") |

**วิธีแก้ที่เสนอ:** ใน `finish` (หรือหลัง `supervise`) ตรวจสถานะปัจจุบัน: ถ้าเป็น `cancelling` ให้บันทึกเป็น `cancelled` (เก็บรายงานถ้ามี, ไม่คืนโควตา) · ขนาด: เล็ก

## BUG-08 — Run ของ MRA ที่หมดเวลาไม่ปล่อย review ที่ MRA

| | |
|---|---|
| ระดับ | ต่ำ (ต้นทุนอยู่ฝั่ง MRA ซึ่งทำ review ต่อให้ไม่มีใครรอ; "best effort" ตามคำอธิบายของ `medical.release`) |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | `worker/main.py:95-97` เรียก `medical.release` เฉพาะ `outcome.status == "cancelled"`; Run ที่ failed/timed_out/ถูก kill ไม่ปล่อย · เทสต์ `test_bug08_a_timed_out_medical_run_releases_its_review` (outcome `failed/timed_out` ของ Run แบบ remote: `release` ไม่ถูกเรียก) |

**ส่วนของ a-S7 ที่ไม่นับเป็นบั๊ก:** Run ที่เป็น `cancelling` แล้ว Worker ตาย ถูกกวาดเป็น `interrupted` + คืนโควตา สอดคล้องกติกา "ความผิดของ Worker คืนโควตาเสมอ" (`queue.py:312-328`), และการที่ Run ที่ตายค้างนับใน `max_concurrent_total` อีกไม่เกิน 60 วินาทีเป็นการออกแบบ lease (ผู้อ่านเองก็ระบุว่า "by design")

**วิธีแก้ที่เสนอ:** เรียก `release` กับทุกผลลัพธ์ที่ไม่ใช่ succeeded ของ Run แบบ remote (ภายใน `release` ตรวจ review_id และการใช้ร่วมกันอยู่แล้ว) · ขนาด: เล็ก

## BUG-10 — ส่ง Turn เดียวกันสองครั้งพร้อมกัน ครั้งที่สองได้ 409

| | |
|---|---|
| ระดับ | ต่ำ (Turn ถูกสร้างครั้งเดียว แต่หน้าเว็บของคำขอที่สองแสดงข้อผิดพลาดว่ากำลังมี Turn ทำอยู่) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `api/discussions.py:273-280` (`ask`: ตรวจ `_existing` ก่อนล็อก Discussion แล้วไม่ตรวจอีก) → `:154-161`, `new_turn` `in_progress` → 409 `turn_in_progress` · เทสต์ `test_bug10_the_same_turn_sent_twice_at_once_makes_one_turn` (คำขอเดียวกัน `request_key` เดียวกัน พร้อมกัน: ได้ `[409, 201]` ต้องเป็น `[201, 201]` และ id เดียวกัน) |

**วิธีแก้ที่เสนอ:** หลังได้ล็อก Discussion ให้เรียก `_existing` อีกครั้ง (idempotency ต้องตรวจในล็อก) · ขนาด: เล็ก

## BUG-11 — ส่งงานเดียวกันสองครั้งพร้อมกันตอนโควตาหน่วยสุดท้าย ครั้งที่สองได้ 429

| | |
|---|---|
| ระดับ | ต่ำ (ลักษณะเดียวกับ BUG-10; เกิดตรง "ขีดจำกัดพอดี" ซึ่งเป็นตอนที่คนดับเบิลคลิกมากที่สุด) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `api/research.py:760-769` (`create_run`), `:656-667` (`_start_session`), `quota.py:288-301` (`check_submit` นับ Run ของคำขอแรกแล้วตอบ 429 `quota_exhausted`/`queue_full`); `_commit_once` จับ `IntegrityError` ตอน commit เท่านั้น · เทสต์ `test_bug11_the_same_submit_sent_twice_at_the_last_unit_of_quota_is_not_refused` (โควตา 2 ใช้ไปแล้ว 1: คำขอเดียวกันสองครั้งพร้อมกันได้ `[201, 429]`) |

**วิธีแก้ที่เสนอ:** ตรวจ `_existing` อีกครั้งหลัง `check_submit` ได้ล็อก (หรือเปลี่ยนให้ `check_submit` คืน Run เดิมถ้า key ซ้ำ) · ขนาด: เล็ก (แก้ร่วมกับ BUG-10)

## BUG-12 — "ลองใหม่" ของ Turn ที่ล้มไม่ล็อก Discussion

| | |
|---|---|
| ระดับ | ต่ำ (ต้องกดสองครั้งพร้อมกัน; ผลคือสอง Turn คิวซ้อน ต่อจากสถานะเดียวกัน และเกินชุดโควตาหนึ่ง Turn) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `api/research.py:818-823` (`retry` กิ่ง Turn: ใช้ `deps.own` ไม่ล็อก) เทียบ `api/discussions.py:154-161,278` (`ask` ล็อกแถว Session) · เทสต์ `test_bug12_two_retries_of_a_failed_turn_at_once_make_one_turn` (retry สองคำขอพร้อมกัน: 2 Turn อยู่ในสถานะ queued ใน Discussion เดียว ต้องไม่เกิน 1) |

**วิธีแก้ที่เสนอ:** ใช้ `_discussion(..., lock=True)` ในกิ่ง Turn ของ `retry` · ขนาด: เล็ก

## BUG-14 — "ลองใหม่" ข้ามการตรวจของการส่งงานใหม่

| | |
|---|---|
| ระดับ | ต่ำ (ผู้ดูแลปิดโหมดแล้วงานเก่ายังเข้าคิวและหักโควตา) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `api/research.py:806-859` (`retry` ตรวจแค่ว่าโมเดล/provider ยังเปิด) เทียบ `:561-593` (`new_run`: `modes.offered`, `owner.allowed_engines`, `search_fits`, `model_fits`) · เทสต์ `test_bug14_trying_again_a_run_of_a_mode_that_was_switched_off_is_refused` (ปิดโหมด `storm` แล้วลองใหม่: ได้ 201 ต้องเป็น 422 `engine_not_available`) |

**หมายเหตุ:** ส่วน `allowed_engines` ของบัญชี integration ไม่ได้ลอง เพราะ integration ไม่มี session เว็บเรียก `retry`; ตรวจเฉพาะส่วน `modes.offered` ที่ทำซ้ำได้ (ปัญหาเดียวกัน: ไม่ใช้การตรวจร่วม)

**วิธีแก้ที่เสนอ:** แยกการตรวจใน `new_run` เป็นฟังก์ชันร่วมที่ `retry` เรียกด้วย · ขนาด: เล็ก

## BUG-15 — "ลองใหม่" ของ Turn ที่เปิดชุดใหม่แล้วล้ม ตอบ 409 เสมอ

| | |
|---|---|
| ระดับ | ต่ำ (ปุ่มที่หน้าเว็บเสนอสำหรับ Turn ที่ล้มกดแล้วสำเร็จไม่ได้ ผู้ใช้ต้องหาปุ่ม "ต่อเวลา" เองแล้วพิมพ์ใหม่) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `api/research.py:818-823` (`retry` เรียก `new_turn(..., extend=False)`); `api/discussions.py:183-190` (`allowed.blocks > 0 and not extend` → 409 `turns_exhausted`); `discussion.py:51-53` (`allowance` ไม่นับแถวที่คืนโควตา) · เทสต์ `test_bug15_a_turn_that_opened_a_block_and_failed_can_be_tried_again` (ชุดละ 2 Turn ใช้หมด, Turn ที่ต่อเวลาล้มแบบคืนโควตา: retry ได้ 409 `turns_exhausted`) |

**วิธีแก้ที่เสนอ:** ให้ `retry` ของ Turn ส่ง `extend=True` เมื่อ Turn เดิมเปิดชุด (`quota_units == 1`) · ขนาด: เล็ก

## BUG-16 — เลือกโมเดลใหม่ให้ Run ที่ถูกพัก ไม่ตรวจว่าใช้กับโหมดได้

| | |
|---|---|
| ระดับ | ต่ำ (Run เข้าคิวด้วยโมเดลที่โหมดไม่รับ แล้วล้มกลางทาง หลังแย่งเวลา slot) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `api/research.py:777-803` (`choose_again` เรียก `_pick` อย่างเดียว ไม่เรียก `modes.model_fits`/`search_fits`) เทียบ `new_run` · เทสต์ `test_bug16_choosing_again_checks_the_new_model_for_the_mode` (Run โหมด Agent ที่พักเพราะโมเดลถูกปิด เลือกโมเดลที่ไม่รองรับ tools: ได้ 200 ต้องเป็น 422 `model_cannot_use_tools`) |

**ส่วนของ b-S7 ที่ไม่ได้ทำซ้ำ:** ผู้อ่านบอกว่า key เก่า (`fast_llm`, `interpret`) ค้างใน config เพราะ `{**run.config, **_snapshot(...)}` ไม่ได้ลองเป็นเทสต์แยก (ผลต่อพฤติกรรมไม่ชัด) แนะนำให้ผู้แก้ตรวจพร้อมกัน

**วิธีแก้ที่เสนอ:** เรียกการตรวจเดียวกับ `new_run` (ฟังก์ชันร่วมเดียวกับ BUG-14) · ขนาด: เล็ก

## BUG-19 — MCP start ซ้ำหลังลบ Session ได้ 404 และไม่เริ่มงาน

| | |
|---|---|
| ระดับ | ต่ำ (agent ได้ error และไม่มีงานเริ่มจนกว่าจะเกิน 10 นาที) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `api/mcp.py:343-370` (`_repeat_of` ไม่ตรวจ `trashed_at`/`run_alive`), ผู้เรียก `:558-560`; ทางเว็บ `api/research.py:494-496` (`_existing` ก็ไม่ตรวจ) · เทสต์ `test_bug19_a_repeated_mcp_start_does_not_return_a_run_in_the_trash` (Run สำเร็จแล้ว ผู้ใช้ลบ Session, agent ส่ง `research_start` ซ้ำ: tool ตอบ `Error executing tool research_start: 404: not_found`) |

**วิธีแก้ที่เสนอ:** `_repeat_of` (และ `_existing`) กรอง Run ที่อยู่ในถังขยะ (`trash.run_alive`) · ขนาด: เล็ก

## BUG-20 — ผู้ดูแลอ่านงานของ integration ที่อยู่ใน Session ที่ถูกลบได้

| | |
|---|---|
| ระดับ | ต่ำ (ผู้ดูแลมีสิทธิ์อ่านงานของ integration อยู่แล้ว (ADR-0009); ผิดเฉพาะความสม่ำเสมอกับทางเจ้าของและทาง token) |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | `api/deps.py:141-147` (`readable` ทางสำรองทดสอบ `trashed_at` ของแถวเอง ไม่ใช่ `session_alive`/`run_alive`/`purged_at`) · เทสต์ `test_bug20_an_administrator_cannot_read_an_integrations_run_that_is_in_a_trashed_session` (ลบ Session ของ integration: `GET /api/runs/{id}` โดยผู้ดูแลยังได้ 200 ต้องเป็น 404) |

**วิธีแก้ที่เสนอ:** ใช้ `trash.run_alive`/`session_alive` ในทางสำรองของ `readable` · ขนาด: เล็ก

## BUG-21 — ลบไฟล์ไม่สำเร็จแต่ตั้ง `purged_at` ไปแล้ว

| | |
|---|---|
| ระดับ | ต่ำ (ต้องมีไฟล์ที่ลบไม่ได้ เช่น ถูกเปิดค้าง หรือ mount อ่านอย่างเดียว; ผลคือเนื้อหาที่ "ลบถาวร" ค้างบนดิสก์โดยไม่มี log) |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | `trash.py:182-183` (`shutil.rmtree(..., ignore_errors=True)` แล้ว `run.purged_at = now`; รอบ purge ถัดไปกรอง `purged_at is None` จึงข้าม) · เทสต์ `test_bug21_a_run_whose_files_could_not_be_deleted_is_not_marked_purged` (จำลองการลบล้มเหลวที่ `shutil.rmtree`: Run ถูกตั้ง purged และไดเรกทอรียังอยู่) |

**วิธีแก้ที่เสนอ:** ไม่ใช้ `ignore_errors`; ถ้าลบไม่ได้ให้ log และไม่ตั้ง `purged_at` (ลองใหม่รอบหน้า) · ขนาด: เล็ก

## BUG-22 — กู้คืน Session ที่ Project อยู่ในถังขยะ ตอบ 204 แต่ยังมองไม่เห็น

| | |
|---|---|
| ระดับ | ต่ำ (รายการกู้คืนที่หน้าเว็บแสดงจะไม่เสนอรายการนี้ เกิดจาก tab เก่าหรือ API ตรงเท่านั้น) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `trash.py:150-158` (`restore` ไม่ตรวจ parent); `api/research.py:1057-1060` · เทสต์ `test_bug22_restoring_a_session_inside_a_trashed_project_is_refused_or_works` (ลบ Session แล้วลบ Project; restore Session: 204 และ `GET /api/sessions/{id}` ยัง 404) |

**วิธีแก้ที่เสนอ:** ถ้า parent ยังอยู่ในถังขยะ ให้ตอบ 409 (เช่น `parent_in_trash`) · ขนาด: เล็ก

## BUG-23 — รายการหัวข้อยิง query หนึ่งครั้งต่อหัวข้อ

| | |
|---|---|
| ระดับ | ต่ำ (ประสิทธิภาพ ไม่ใช่ผลลัพธ์ผิด; ช้าลงตามประวัติของผู้ใช้ที่ไม่มีวันลด) |
| ผู้ใช้เห็นไหม | ไม่ (ถ้าแก้ผลเหมือนเดิมแต่เร็วขึ้น) |
| หลักฐาน | `api/research.py:703-709` (`_sessions`: `session.scalar(select(Run.status)...)` ในลูป; `list_sessions` อนุญาต `limit=500`) · เทสต์ `test_bug23_listing_topics_does_not_cost_a_query_per_topic` (นับ statement ด้วย event listener: 5 หัวข้อใช้ **8** statement, 45 หัวข้อใช้ **48**) |

**วิธีแก้ที่เสนอ:** คำนวณสถานะล่าสุดใน query เดียว (`DISTINCT ON (session_id)` หรือ subquery ที่ join) · ขนาด: เล็ก

## BUG-24 — เปลี่ยน `turns_per_quota` กลางทาง ชุด Turn ที่จ่ายแล้วถูกคำนวณใหม่

| | |
|---|---|
| ระดับ | ต่ำ (ต้องมีผู้ดูแลเปลี่ยนค่านี้ขณะมี Discussion ใช้อยู่; ผลคือผู้ใช้ถูกปฏิเสธ Turn ที่จ่ายแล้ว หรือได้ Turn ฟรี) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `discussion.py:40-41,51-53` (`remaining = max(0, per_block * blocks - used)` ใช้ `per_block` จากค่าตั้งปัจจุบัน ไม่ได้เก็บขนาดชุดไว้กับหน่วยที่จ่าย) · `api/discussions.py:181-191` (`new_turn`) · เทสต์ `test_bug24_changing_turns_per_quota_does_not_change_what_a_paid_block_allows` |

**สถานการณ์:** ตั้ง `turns_per_quota=4` เริ่ม Discussion ใช้ครบชุดแรก (4 Turn) แล้วขยายชุดที่สอง (จ่ายหน่วยที่สอง) ใช้ไปรวม 5 Turn เหลือ 3 จาก 8 ผู้ดูแลลดค่าเป็น 2: `allowance` กลายเป็น `{per_block: 2, blocks: 2, used: 5, remaining: 0}` และ Turn ถัดไปตอบ `409 turns_exhausted` ทั้งที่เจ้าของจ่ายหน่วยที่สองไปแล้ว ต้องยอมจ่ายหน่วยที่สามเพื่อได้ Turn ที่เป็นของตนอยู่แล้ว เพิ่มค่าให้ผลตรงข้าม (Turn ที่ใช้ไปแล้วกลับกลายเป็นว่าง) ประวัติของ Run จึงถูกเขียนใหม่ย้อนหลังด้วยค่าตั้งปัจจุบัน

**เจตนาเป็นการตัดสินของเจ้าของ:** โค้ดและเอกสารไม่ได้บอกว่าค่า `turns_per_quota` ใหม่ใช้กับชุดที่จ่ายไปแล้วหรือไม่ รายงานนี้ถือว่า "ชุดที่จ่ายแล้วคงขนาดเดิม" ถูก ถ้าเจ้าของต้องการให้ค่าใหม่มีผลทันที (เช่น ใช้ลดค่าใช้จ่ายฉุกเฉิน) ข้อนี้ไม่ใช่บั๊ก ให้ลบเทสต์ออกแทนการแก้

**วิธีแก้ที่เสนอ:** เก็บขนาดชุดไว้กับ Run ที่เปิดชุด (เช่นใน `config` ของ Turn ที่มี `quota_units > 0`) แล้ว `allowance` รวมจากขนาดที่เก็บไว้ · ขนาด: เล็ก (ไม่แตะ schema ถ้าเก็บใน `config`)

## BUG-25 — รายงานที่เสร็จตอนกดหยุดพอดี ไม่ปรากฏในรายการรายงานของ Discussion

| | |
|---|---|
| ระดับ | ต่ำ (ต้องกดหยุดในช่วงท้าย Turn; แต่เจ้าของเสียหน่วยโควตาและค่า token จริง) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `runner/supervisor.py:226-229` ("Asked to stop, but finished first": ผลเป็น `cancelled`/`finished while stopping` และคอมเมนต์ระบุว่ารายงานที่ทำเสร็จ "is kept for them to read") · `api/discussions.py:143-150` (`reports` เอาเฉพาะ `SUCCEEDED`) · `outcomes.py` (`CANCELLED` ไม่อยู่ใน `REFUNDED`) · เทสต์ `test_bug25_a_report_that_finished_while_its_owner_pressed_stop_is_listed_with_the_others` |

**สถานการณ์:** Turn แบบ `report` ถูกกดหยุดแล้ว child เขียนรายงานเสร็จก่อนรับรู้ เทสต์ใช้ Worker จริงกับ fake engine: ตั้งสถานะ `cancelling` ตั้งแต่ก่อนเริ่ม supervisor เห็นคำขอหยุดในรอบแรก ส่วน fake engine (นอนหลับ 1.5 วินาที ไม่ดู cancel) จบแบบสำเร็จ ผล: Turn เป็น `cancelled`, `quota_refunded=False`, `report_title` ถูกตั้ง (รายงานถูกเก็บ) แต่ `GET /api/discussions/{id}` ได้ `reports: []` ส่วนที่ผู้อ่านเสนอเพิ่ม (state ของ Turn ที่หยุดแล้วไม่ถูกใช้ต่อ `last_state` รับเฉพาะ `SUCCEEDED`) เป็นพฤติกรรมที่ตรงกับเอกสารของโมดูล ("a Turn that ... is stopped ... costs only itself") จึงไม่นับเป็นบั๊ก

**เจตนาเป็นการตัดสินของเจ้าของ:** คอมเมนต์ของ supervisor บอกว่ารายงานที่เสร็จ "is kept for them to read" แต่ไม่ได้บอกว่าจะแสดงในรายการของ Discussion หรือไม่ และหน่วยโควตาที่ไม่คืนถูกหรือไม่ ถ้าเจ้าของเห็นว่า "กดหยุดแล้ว = ไม่ต้องการรายงาน" ข้อนี้ไม่ใช่บั๊ก แต่ควรลบรายงานนั้นด้วยเพื่อไม่ให้ค้างโดยมองไม่เห็น

**วิธีแก้ที่เสนอ:** ให้ `reports` รวม Turn แบบ report ที่ `cancelled` และมี `report_title` (ไฟล์รายงานมีอยู่) · ขนาด: เล็ก

## BUG-26 — ปิดโหมด Co-STORM แล้ว Discussion ที่เริ่มไว้แล้วยังถามต่อได้

| | |
|---|---|
| ระดับ | **กลาง** สวิตช์ปิดโหมดของผู้ดูแล (ที่ใช้ปิดด้วยเหตุผลเรื่องค่าใช้จ่าย) ไม่หยุด Discussion ที่เปิดอยู่ซึ่งใช้ token ได้ต่อไม่จำกัด รวม `auto` สูงสุด 10 ขั้นต่อ Turn และรายงาน |
| ผู้ใช้เห็นไหม | ใช่ (ผู้ใช้จะถูกปฏิเสธ Turn หลังผู้ดูแลปิดโหมด) |
| หลักฐาน | `api/discussions.py:237-240` (`start` ตรวจ `modes.offered` และ `allowed_engines`) เทียบ `:164-224` (`new_turn` และ `ask` ที่ `:274-280` ไม่ตรวจ) · `api/research.py:561-571` (`new_run` ตรวจทุกครั้งสำหรับ Run ของโหมดอื่นใน Session เดิม) · เทสต์ `test_bug26_a_turn_in_a_discussion_is_refused_once_the_mode_is_switched_off` (ปิด `co-storm` ผ่าน `PUT /api/admin/engines/co-storm`: Discussion ใหม่ได้ 422 แต่ `POST .../turns` ได้ 201) |

**ข้อสังเกต:** เจตนาอาจเป็น "Discussion ที่เริ่มแล้วให้จบได้" แต่โค้ดไม่มีกฎนั้นเขียนไว้ และ `retry` (BUG-14) ผ่านทาง `new_turn` เดียวกัน ควรให้เจ้าของตัดสินกติกา ส่วนครึ่ง `allowed_engines` ที่ผู้อ่านเสนอ ทำซ้ำไม่ได้ในทางปฏิบัติ: ค่านี้ตั้งได้เฉพาะบัญชี integration ซึ่งไม่ login ผ่านเว็บและ MCP ไม่เปิด Co-STORM (`api/mcp.py`: "Discussions ... not offered through MCP yet")

**วิธีแก้ที่เสนอ:** ย้ายการตรวจ `modes.offered` (และ `allowed_engines`) เข้า `new_turn` ให้ทั้ง `start`/`ask`/`retry` ผ่านจุดเดียว (ตอบ `422 engine_not_available`) หรือเพิ่มกติกาที่ชัดว่า Discussion ที่เปิดอยู่ทำต่อได้ · ขนาด: เล็ก

## BUG-27 — หัวข้อ Discussion 301-500 ตัวอักษรถูกตัดเหลือ 300

| | |
|---|---|
| ระดับ | ต่ำ (หัวข้อยาวเกิน 300 ตัวหายาก แต่คำถามที่ Co-STORM ตอบไม่ใช่คำถามที่ผู้ใช้ถาม และไม่มีข้อความแจ้ง) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `api/discussions.py:46` (`topic` `max_length=500`) กับ `:252` (`title=body.topic.strip()[:300]`) และ `:211` (`topic=rs.title` ของ Run ของ Turn) ต่างจาก STORM ที่ `api/research.py` เก็บ `Run.topic = body.topic.strip()` เต็ม · เทสต์ `test_bug27_a_long_topic_is_researched_whole_or_refused` (หัวข้อ 450 ตัวอักษร: `POST /api/discussions` ได้ 201 และ `turns[0].topic` ยาว 300) |

**วิธีแก้ที่เสนอ:** ให้ `Run.topic` ของ warm start เก็บหัวข้อเต็ม (ตัดเฉพาะ `title` ที่แสดง) หรือจำกัด `max_length` ของ Discussion ที่ 300 · ขนาด: เล็ก

## BUG-28 — ผู้ดูแลสองคนกด "รับทราบ" พร้อมกัน อีกคนหาย หรือได้ 500

| | |
|---|---|
| ระดับ | ต่ำ (ต้องกดพร้อมกันเป๊ะ; ผลคือ Issue ที่ผู้ดูแลคิดว่ารับทราบแล้วยังเปิดอยู่ ต้องกดซ้ำ) |
| ผู้ใช้เห็นไหม | ใช่ (ได้หน้า error 500 หรือ Issue ที่ยังเปิด) |
| หลักฐาน | `monitor.py:86-96` (`acknowledge` อ่านแถว `monitor.acks` ทั้งแถว แล้วเขียน dict ใหม่ทั้งก้อนกลับ ไม่ล็อก; ครั้งแรกสุดทั้งสองคำขอ `session.add` แถวเดียวกัน) · `api/admin.py:808-810` · เทสต์ `test_bug28_two_administrators_acknowledging_at_once_keep_both_acknowledgements` (barrier คั่นระหว่างอ่านกับเขียน: ทั้งคู่ได้ 204 แต่เหลือ `{first:seen, issue:a}` `issue:b` หาย) และ `test_bug28_the_very_first_two_acknowledgements_at_once_do_not_end_in_a_500` (`IntegrityError: duplicate key ... system_settings_pkey`) |

**ส่วนที่ไม่นับเป็นบั๊ก (จาก e-S1):** ผู้อ่านเสนอว่า acknowledge ควรลงเวลาที่ผู้ดูแล "เห็น" ไม่ใช่เวลาที่กดปุ่ม เพราะความล้มเหลวที่เกิดระหว่างโหลดหน้ากับกดปุ่ม (สูงสุด 60 วินาทีของรอบ poll) จะถูกรับทราบไปโดยไม่เห็น นี่เป็นพฤติกรรมแบบเดียวกับ "resolve" ของระบบติดตามข้อผิดพลาดทั่วไป และ Issue เปิดใหม่เมื่อเกิดซ้ำภายหลัง จึงตัดสินว่าเป็นการออกแบบที่ยอมรับได้ ไม่ใส่เป็นบั๊ก (ถ้าเจ้าของต้องการ ให้ส่ง `last_at` ของ Issue ไปกับคำขอ)

**วิธีแก้ที่เสนอ:** ล็อกแถวด้วย `SELECT ... FOR UPDATE` (หรือ `INSERT ... ON CONFLICT DO UPDATE` ด้วยการรวม JSONB ในฐานข้อมูล) ก่อนอ่าน-เขียน · ขนาด: เล็ก

## BUG-29 — Run ของบัญชีที่ถูกปิดค้างอยู่ในคิวตลอดไป

| | |
|---|---|
| ระดับ | ต่ำ (หน้าสถานะระบบดูเหมือนคิวค้าง แต่ไม่กระทบผู้ใช้อื่น; Run ที่กำลังทำอยู่ยังวิ่งต่อและเมื่อเปิดบัญชีกลับ Run เก่าจะเริ่มทันที) |
| ผู้ใช้เห็นไหม | ใช่ (ผู้ดูแลเห็นตัวเลขคิวเปลี่ยน) |
| หลักฐาน | `worker/queue.py:91` (`User.is_active.is_(True)` ใน `_next_run`) · `api/admin.py:138-152` (`patch_user` ปิดบัญชีแล้วลบ session และลิงก์ แต่ไม่แตะ Run) · `monitor.py:169-179` (`queue` นับ `queued` ทุกแถว) · เทสต์ `test_bug29_runs_waiting_for_an_account_that_was_turned_off_do_not_stay_in_the_queue` (ปิดบัญชี: `claim` คืน None และ `monitor.queue` ได้ `{'queued': 1, ...}`) |

**หมายเหตุ:** Run ที่ `running` ของบัญชีที่ถูกปิดไม่ถูกหยุด (อ่านจากโค้ด ไม่ได้เขียนเทสต์แยก)

**วิธีแก้ที่เสนอ:** ตอนปิดบัญชี ยกเลิก Run ที่รอ (คืนโควตาแบบ `trash._stop`) และขอหยุด Run ที่กำลังทำ · ขนาด: เล็ก

## BUG-30 — PATCH ด้วยค่า null ได้ 500 (บัญชีผู้ใช้และ integration) และชื่อว่างผ่านได้

| | |
|---|---|
| ระดับ | ต่ำ (ผู้ดูแลเท่านั้น; ได้หน้า 500 และการเปลี่ยนอื่นในคำขอเดียวกันหาย) |
| ผู้ใช้เห็นไหม | ใช่ (ได้ 500 แทนข้อความผิด) |
| หลักฐาน | `api/admin.py:87-96` (`UserPatch`: ทุกฟิลด์ `X \| None = None`) และ `:142-146` (`setattr` ทุก key ของ `exclude_unset`) · `api/tokens.py:208-215,276-284` (`IntegrationPatch` เหมือนกัน) · เทสต์ `test_bug30_an_account_patched_with_an_explicit_null_is_refused_not_a_500` (3 ค่า: `is_active`, `name`, `role` ทุกตัวได้ `IntegrityError`), `test_bug30_an_integration_patched_with_an_explicit_null_is_refused_not_a_500` (`is_active`, `name`), `test_bug30_an_account_cannot_be_given_a_blank_name` (`{"name": "   "}` ได้ 200 และเก็บ `"   "`; `create_user` ตัดช่องว่างแต่ `patch_user` ไม่ตัด) |

**วิธีแก้ที่เสนอ:** ปฏิเสธ null ของฟิลด์ที่คอลัมน์เป็น NOT NULL (validator หรือแยก "เคลียร์ค่า" ไว้เฉพาะ 3 ฟิลด์โควตา) และตัดช่องว่างของ `name` ใน patch ให้เหมือน create · ขนาด: เล็ก

## BUG-31 — `auth_sessions` ที่หมดอายุไม่เคยถูกลบ

| | |
|---|---|
| ระดับ | ต่ำ (ตารางโตตามจำนวนการ login ตลอดไป ไม่ผิดผลลัพธ์ เพราะ `deps` ข้ามแถวที่หมดอายุ) |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | `api/auth.py:33-52` (`_start_session` เพิ่มแถวละ 14 วันต่อการ login) · `api/deps.py:80` (`_signed_in` ข้ามแถวหมดอายุแต่ไม่ลบ) · ไม่มีตัวลบที่ไหนในโค้ด (ค้น `AuthSession` นอก `auth.py`, `admin.py`, `deps.py`, `models.py` ไม่พบ) · เทสต์ `test_bug31_signed_in_browsers_that_expired_are_cleaned_up` (แทรก 3 แถวหมดอายุ, login อีกครั้ง, รอบหนึ่งของ Worker: ยังเหลือ 3) เทสต์ไม่ผูกกับที่ที่จะทำความสะอาด: ผ่านถ้าลบตอน login หรือตอน Worker ทำงาน |

**วิธีแก้ที่เสนอ:** ลบแถวที่ `expires_at < now()` ในรอบ housekeeping ของ Worker (ข้างๆ purge) หรือตอน login · ขนาด: เล็ก

## BUG-32 — หัวข้อสั้นถูกแทนที่ในข้อความผิดพลาดแม้อยู่กลางคำ

| | |
|---|---|
| ระดับ | ต่ำ (หัวข้อสั้นหรือคำทั่วไปหายาก; ผลคือข้อความอ่านไม่ออกและ Issue แตกเป็นสองอัน) |
| ผู้ใช้เห็นไหม | ใช่ (ผู้ดูแลเห็นข้อความและจำนวน Issue) |
| หลักฐาน | `monitor.py:66-71` (`said.replace(run.topic, "…")` เป็น substring ล้วน) และ `:55` (`said` เป็นส่วนของกุญแจ Issue) · เทสต์ `test_bug32_a_short_topic_does_not_split_one_failure_into_two_issues` (ข้อความ `rate limit reached for key` เดียวกัน หัวข้อ "limit" กับ "weather": ได้ 2 Issue ข้อความหนึ่งอ่านว่า `rate … reached for key`) |

**หมายเหตุ:** การตัดหัวข้อเอาเฉพาะข้อความที่ตรงตัวเท่านั้น ถ้าผู้ให้บริการสะท้อนหัวข้อในรูปอื่นยังไปถึงหน้าผู้ดูแล (จำกัดที่ 300 ตัวอักษร) เป็นข้อจำกัดของวิธีนี้ ไม่ได้ทำซ้ำ

**วิธีแก้ที่เสนอ:** ตัดหัวข้อก่อนแล้วคำนวณกุญแจจากข้อความที่ไม่มีหัวข้อ โดยแทนเฉพาะการตรงทั้งคำเมื่อหัวข้อสั้นกว่า (เช่น 8 ตัว) หรือใช้ขอบเขตคำ · ขนาด: เล็ก

## BUG-33 — คำในหัวข้อตัดสินสาเหตุของ engine_error

| | |
|---|---|
| ระดับ | ต่ำ (ทุกสาเหตุคืนโควตาเหมือนกัน ผลอยู่ที่ป้ายกับคำแนะนำที่ผู้ดูแลเห็น: ไปไล่ผู้ให้บริการที่ปกติดี) |
| ผู้ใช้เห็นไหม | ใช่ (ผู้ดูแลเห็นป้ายสาเหตุ) |
| หลักฐาน | `monitor.py:74-78` (`_reason` เรียก `outcomes.from_message(run.message)` กับข้อความทั้งก้อนของทุก Run ที่เป็น engine_error) · `outcomes.py:94-109` (regex `rate[ -]?limit`, `\b40[12]\b`, `timed? ?out` ฯลฯ) · `runner/child.py` (ข้อความ = ชนิด + `str(error)`) · เทสต์ `test_bug33_words_of_the_topic_do_not_decide_why_an_engine_error_is_filed` (`KeyError: could not find a section for 'rate limit policy'` จัดเป็น `retries_exhausted`) |

**วิธีแก้ที่เสนอ:** ตัดหัวข้อออกจากข้อความก่อนจัดสาเหตุ (ที่ `child.py` ตอน `classify` หรือที่ `_reason`) · ขนาด: เล็ก

## BUG-34 — กุญแจ Issue: id แบบ hex แตกเป็นหลาย Issue และ 40 ตัวแรกรวมสาเหตุต่างกัน

| | |
|---|---|
| ระดับ | ต่ำ (หน้าสถานะระบบอ่านยากขึ้น; การรับทราบ Issue หนึ่งอาจปิดสาเหตุอื่นที่ข้อความขึ้นต้นเหมือนกัน) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `monitor.py:29,52-55` (`DIGITS = \d+` เปลี่ยนเป็น `#` เท่านั้น แล้วตัด 40 ตัวแรก) · เทสต์ `test_bug34_one_fault_with_different_ids_in_its_words_is_one_issue` (`request ab12cd34/ef56ab78/cd90ef12 refused`: ได้ 3 Issue) และ `test_bug34_two_different_faults_with_the_same_first_words_are_two_issues` (`litellm.BadRequestError: OpenrouterException - ...` สองสาเหตุที่ต่างกันหลังตัวที่ 40: ได้ 1 Issue) |

**วิธีแก้ที่เสนอ:** ทำให้ข้อความเป็นรูปมาตรฐานก่อนทำกุญแจ (hex/uuid/path ชั่วคราวเป็น `#`) และใช้ส่วนที่ยาวกว่า 40 ตัว หรือกุญแจเป็น hash ของข้อความมาตรฐาน · ขนาด: เล็ก

## BUG-35 — ลิงก์ตั้งรหัสผ่านใช้ได้สองครั้งถ้าสองคำขอมาพร้อมกัน

| | |
|---|---|
| ระดับ | ต่ำ (ต้องถือลิงก์และยิงพร้อมกัน; ผลคือ "ใช้ครั้งเดียว" ไม่เป็นจริง และรหัสผ่านของคนที่แพ้ถูกทับเงียบๆ) |
| ผู้ใช้เห็นไหม | ใช่ (ผลคือคนที่สองได้ 410 แทน 200) |
| หลักฐาน | `api/auth.py:216-255` (`_link` อ่านแถว, `hash_password`, ตั้งรหัสผ่าน, `session.delete(row)` ไม่ล็อกแถว) · เทสต์ `test_bug35_a_set_password_link_can_be_used_once_even_by_two_at_the_same_moment` (barrier ที่ `security.hash_password` ซึ่งอยู่ถัดจากการอ่านลิงก์: ทั้งสองคำขอตอบ **200** ทั้งคู่ และ login ทั้งคู่) |

**ส่วนที่ยังไม่ได้ตรวจ (e-S10 ส่วน B, ต้องใช้เบราว์เซอร์; ส่ง Task 8/9):** `SetPasswordPage` (`web/src/pages/auth.tsx` ราว :497-516) ใช้ `!link.data?.valid` แสดง "ลิงก์ไม่ถูกต้อง" ผู้อ่านสงสัยว่า query `password-link` ที่ล้มเพราะเครือข่าย/5xx หรือที่ React Query ดึงซ้ำตอนกลับมาโฟกัสหน้าต่างหลังบันทึกสำเร็จ (token ถูกลบแล้ว) จะทำให้ผู้ใช้เห็นข้อความว่าลิงก์เสีย ขั้นตอน: เปิดลิงก์ตั้งรหัสผ่านบนสภาพแวดล้อมทดสอบ → (1) ตัดเครือข่ายด้วย DevTools แล้วโหลดหน้าซ้ำ ดูข้อความ (2) ตั้งรหัสผ่านสำเร็จ แล้วสลับ tab ไปมาก่อนที่หน้าจะเปลี่ยนเส้นทาง ดูว่ามีข้อความ "ลิงก์ไม่ถูกต้อง" โผล่ไหม

**วิธีแก้ที่เสนอ:** ใช้ `DELETE ... WHERE token_hash = ... RETURNING` เป็นตัวตัดสินว่าใช้ได้ (ถ้าลบไม่ได้แถว ตอบ 410) หรือ `SELECT ... FOR UPDATE` ที่แถวลิงก์ · ขนาด: เล็ก

## BUG-36 — `PATCH /api/admin/users/{id}` แก้บัญชี integration ได้

| | |
|---|---|
| ระดับ | ต่ำ (บัญชี integration ไม่มีรหัสผ่านและ `deps.admin` ใช้ cookie เข้าสู่ระบบ จึงไม่ทำให้ได้สิทธิ์จริง ผิดเฉพาะความสม่ำเสมอ และเปิดทางให้ role admin ค้างบนบัญชีที่ไม่ควรมี) |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | `api/admin.py:138-152` (`patch_user` ไม่ตรวจ `kind`) เทียบ `:122-128` (`reset_link`) และ `:156-163` (`delete_user`) ที่ตอบ 404 สำหรับ integration · เทสต์ `test_bug36_an_integration_account_is_not_patched_through_the_people_endpoint` (`PATCH {"role": "admin"}` ได้ 200 และเก็บ role `admin`) |

**วิธีแก้ที่เสนอ:** ตรวจ `user.kind != PERSON` แล้วตอบ 404 เหมือนสองเส้นทางที่เหลือ · ขนาด: เล็ก

## BUG-37 — `request_key` ที่ใช้ซ้ำกับ Discussion อื่นคืน Turn ของ Discussion แรก

| | |
|---|---|
| ระดับ | ต่ำ (หน้าเว็บไม่ส่ง key มากับ Turn และสร้าง key ใหม่ทุกครั้งที่เริ่ม จึงเกิดเฉพาะ client ที่ใช้ API หรือ MCP ตรงแล้วใช้ key ซ้ำ) |
| ผู้ใช้เห็นไหม | ใช่ (client เห็นว่า "สำเร็จ" ทั้งที่ไม่มีอะไรถูกถามใน Discussion B) |
| หลักฐาน | `api/research.py:493-496` (`_existing` กรอง `owner_id` กับ `request_key` เท่านั้น) · ใช้ที่ `api/discussions.py:234-236,275-277` · เทสต์ `test_bug37_a_request_key_used_again_for_another_discussion_does_not_hand_back_the_first_turn` (key เดียวกัน: Turn `step` ของ A แล้ว `say` ของ B ได้ 201 พร้อม `session_id` ของ A) |

**ผลที่ลองแล้วไม่เป็นบั๊กเพิ่ม:** ส่ง `POST /api/discussions` ซ้ำด้วย key ของ Session วิจัยธรรมดาได้ 201 พร้อม Discussion ว่างที่ชื่อเดิม ไม่ใช่ 500

**เจตนาเป็นการตัดสินของเจ้าของ:** `request_key` ผูกกับบัญชีหรือกับ Discussion เอกสารไม่ได้กำหนด ถ้าผูกกับบัญชี (แบบที่โค้ดทำ) การใช้ key ซ้ำกับ Discussion อื่นเป็นความผิดของ client และทางแก้คือบอกให้รู้ (409) ไม่ใช่คืน Turn ของ A ถ้าผูกกับ Discussion ต้องเปลี่ยน `_existing` ให้กรอง Session ด้วย

**วิธีแก้ที่เสนอ:** เมื่อเจอ key เดิม ตรวจว่า Session, action และข้อความตรงกัน ถ้าไม่ตรงตอบ `409 request_key_reused` (แบบที่ API ที่ใช้ idempotency key ทำ) · ขนาด: เล็ก

## BUG-38 — `[4][9]` ของหน้าเดียวกันถูกเขียนเป็น `[1][1]`

| | |
|---|---|
| ระดับ | ต่ำ (เครื่องหมายอ้างอิงซ้ำติดกัน ดูเลอะแต่ไม่ผิดความหมาย) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `engines/costorm/engine.py:256-260` (`re.sub(r"\[(\d+)\]", ...)` แปลงทีละเครื่องหมาย) · เทสต์ `test_bug38_two_snippets_of_one_page_cited_together_are_one_citation` (สอง snippet ของ `https://a.test` เลข 4 และ 9: เนื้อหา `A claim [4][9].` ออกมาเป็น `A claim [1][1].` หลัง `normalize`) |

**ส่วนที่ไม่ได้ทำซ้ำ:** `[2019]` ที่ตรงกับเลข snippet ต้องมี snippet เกิน 2,000 ชิ้นใน Discussion เดียว ไม่สมจริง

**วิธีแก้ที่เสนอ:** หลังแปลงเลข ยุบเครื่องหมายที่เหมือนกันติดกัน (`(\[\d+\])\1+` เป็น `\1`) · ขนาด: เล็ก

## BUG-39 — MCP start ซ้ำหลัง cancel คืน Run ที่กำลังถูกยกเลิก

| | |
|---|---|
| ระดับ | ต่ำ (ช่วงสั้นสูงสุดราว 30 วินาที; agent ที่ยกเลิกแล้วลองใหม่ได้ id เดิมและข้อความว่าไม่ใช้โควตา แล้ว Run นั้นก็ถูกยกเลิก) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `api/mcp.py:354` (`Run.status.not_in(("failed", "cancelled", "interrupted"))` ไม่รวม `cancelling`) · เทสต์ `test_bug39_starting_again_after_cancelling_does_not_hand_back_the_run_being_cancelled` (Run `running` ถูกยกเลิกผ่านเว็บ → `cancelling`; `research_start` ซ้ำได้ id เดิม) |

**ส่วนที่ไม่ได้เขียนเทสต์:** `needs_selection` ก็ผ่านตัวกรองเดียวกัน แต่ Run นั้นยังเป็นคำขอเดิมที่รอเจ้าของเลือกโมเดล การคืนมันจึงพอฟังได้ ไม่นับเป็นบั๊ก

**วิธีแก้ที่เสนอ:** เติม `cancelling` ในรายการสถานะที่ไม่นับ · ขนาด: เล็ก

## BUG-40 — Medical: ความผิดพลาดชั่วคราวระหว่างติดตาม review ทำให้ Run ล้ม

| | |
|---|---|
| ระดับ | ต่ำ (ต้องเจอ MRA รีสตาร์ตหรือ 5xx ชั่วคราวพอดี; Run ล้มแต่คืนโควตา และลองใหม่ได้ review จาก cache; ผู้ใช้เสียเวลารอ 2-3 นาที) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `engines/medical/engine.py:168` (GET สถานะหลัง stream ปิดโดยไม่มีตอนจบ นอก `try` ของการลองซ้ำ), `:98` (GET ผลสุดท้าย), `:149-150` (`raise_for_status` ใน `try` ที่ลองซ้ำ 6 ครั้ง ไม่แยก 4xx) · เทสต์ `test_bug40_a_blip_when_the_stream_closed_early_does_not_fail_a_review_mra_is_still_running` (stream ปิดหลัง 5 event, GET แรกได้ 503: Run จบด้วย `HTTPStatusError`), `test_bug40_a_blip_on_the_final_fetch_does_not_throw_away_a_review_that_is_done` (GET ผลสุดท้ายได้ 503 หนึ่งครั้ง: `HTTPStatusError`), `test_bug40_a_refused_key_on_the_stream_is_not_reported_as_an_mra_that_went_quiet` (401 บน stream: ลองซ้ำ 6 ครั้งแล้วรายงาน `service_unavailable`; `_submit` รายงาน 401 เป็น `bad_configuration`) |

**วิธีแก้ที่เสนอ:** ครอบสองขั้นนั้นด้วยการลองซ้ำแบบเดียวกับ stream (นับรวมใน `drops`) และให้ 401/403/404 บน stream เป็น `bad_configuration` ทันที · ขนาด: เล็ก

## BUG-41 — Medical: POST ที่ timeout แต่ MRA รับไปแล้ว ถูกนับเป็นฟรี

| | |
|---|---|
| ระดับ | ต่ำ (ต้องให้ MRA ตอบ POST ช้ากว่า 40 วินาที ซึ่งปกติตอบเร็ว; ผลคือเจ้าของได้ review ฟรีและยอดค่าใช้จ่าย MRA ที่ผู้ดูแลเห็นต่ำกว่าจริง) |
| ผู้ใช้เห็นไหม | ใช่ (โควตาที่เห็นเปลี่ยน) |
| หลักฐาน | `engines/medical/engine.py:116-121` (ลองซ้ำเมื่อ `httpx.HTTPError` รวม `ReadTimeout`), `:128` (`cached`), `:92-93,102` (`cached` เขียน `service_cache` และ `usd=None`) · `worker/queue.py:296` (คืนโควตาเมื่อสำเร็จและมี `service_cache`) · เทสต์ `test_bug41_a_review_started_by_the_run_itself_is_not_given_back_as_free` (POST แรกช้ากว่า read timeout; POST ที่สองตอบ `cached: true`: notes มี `service_cache` และ `usage` เป็น `[0.0]` แทน 0.0421) |

**วิธีแก้ที่เสนอ:** ถ้า POST ก่อนหน้าของ Run นี้เองหมดเวลา (อาจถูกรับไปแล้ว) ให้ถือว่า `cached` ที่ได้กลับมาไม่ใช่การประหยัด (ไม่เขียน `service_cache` และบันทึกราคาตามที่ MRA รายงาน) · ขนาด: เล็ก

## BUG-42 — Medical: `evidence_quote` เป็น null ทำให้ `to_report` พัง

| | |
|---|---|
| ระดับ | ต่ำ (MRA จริงบังคับ `evidence_quote: str` และตัดผลลัพธ์ที่ไม่มีคำพูดออก (`schemas.py:178,223-227`) แต่ stub engine ของ MRA เองส่ง `evidence_quote: None` (`stub_result.py:40`) จึงเกิดกับ MRA ที่รันแบบ stub หรือรุ่นที่เปลี่ยนไป) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `engines/medical/convert.py:230` (`o.get("evidence_quote", "").strip()` ค่าเริ่มต้นใช้เฉพาะเมื่อไม่มี key) · เทสต์ `test_bug42_an_outcome_without_a_quote_does_not_lose_the_review` (`AttributeError: 'NoneType' object has no attribute 'strip'`; Run จบ engine_error หลังจ่ายค่า review และลองใหม่ได้ผลเดิมจาก cache แล้วพังเหมือนเดิม) |

**วิธีแก้ที่เสนอ:** `(o.get("evidence_quote") or "").strip()` และข้าม outcome ที่ไม่ใช่ dict · ขนาด: เล็ก

## BUG-43 — Deep: กดหยุดไม่ถูกสังเกตขณะ CLI ยังเขียนถี่

| | |
|---|---|
| ระดับ | ต่ำ (ช่องโหว่ของโค้ดยืนยันได้ แต่ CLI จริงที่รอโมเดลมักเงียบเกินหนึ่งวินาทีจึงรู้เร็วกว่าตัวเลขในเทสต์; กรณีแย่สุด supervisor kill หลัง 30 วินาที เสีย usage ของช่วงนั้น) |
| ผู้ใช้เห็นไหม | ใช่ (ปุ่มหยุดตอบช้า) |
| หลักฐาน | `engines/deep/engine.py:143-150` (`cancel.requested()` ดูเฉพาะในสาขา `queue.Empty` และตอน event `stage`) · เทสต์ `test_bug43_a_stop_is_noticed_while_the_deep_cli_keeps_talking` (เพิ่มสคริปต์ `[stream]` ใน `tests/fake_deep_cli.py` ที่เขียน event `node` ทุก 50 มิลลิวินาทีนาน 8 วินาที; ขอหยุดที่วินาทีที่ 1: engine ยก `Cancelled` หลังสคริปต์เขียนจบหรือใกล้จบ ไม่ใช่ภายใน 4 วินาทีที่เทสต์กำหนด ค่าที่วัดได้ในการรันหลายครั้งอยู่ระหว่างราว 5.6 ถึง 12 วินาที ขึ้นกับภาระของเครื่อง) |

**วิธีแก้ที่เสนอ:** ตรวจ `cancel.requested()` ทุกรอบของ loop (หลังอ่านแต่ละบรรทัดด้วย) · ขนาด: เล็ก

## BUG-44 — MCP: เลขหัวข้อย่อยจาก `outline` อ่านด้วย `section:N` ไม่ได้

| | |
|---|---|
| ระดับ | ต่ำ (agent ที่เห็น `2.1. Methods` ในโครงแล้วขอ `section:2.1` ได้ข้อความว่าไม่มีหัวข้อ; อ่านได้ทางหัวข้อแม่) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `api/mcp.py:392-404` (`_outline` พิมพ์เลขซ้อนเช่น `2.1`), `:407-416` (`_section` รับเฉพาะเลขหลักของหัวข้อบนสุดหรือชื่อหัวข้อบนสุด และ `wanted.isdigit()` เป็นจริงกับ `²`, `٣` แล้ว `int()` ยก `ValueError`) · เทสต์ `test_bug44_every_section_number_the_outline_prints_can_be_read` (`ToolError: No section '2.1'. The report has sections 1 to 2`) และ `test_bug44_a_section_number_that_is_not_a_number_is_told_so` (`ValueError` แทน `ToolError`) |

**วิธีแก้ที่เสนอ:** แยกเลขซ้อนด้วย `.` แล้วเดินตามลำดับลูก และใช้ `str.isdecimal()`/regex `^\d+$` แทน `isdigit()` · ขนาด: เล็ก

## BUG-45 — `render/brief.py` ใช้ f-string แบบ Python 3.12 แต่ `pyproject.toml` ประกาศว่ารองรับ 3.11

| | |
|---|---|
| ระดับ | ต่ำ (ภาพ Docker ใช้ Python 3.12 จึงไม่กระทบระบบจริงวันนี้; กระทบเมื่อมีคนรันบน 3.11 ตามที่ประกาศ: รายงานแบบโต้ตอบ (`interactive`) สร้างไม่ได้) |
| ผู้ใช้เห็นไหม | ไม่ (ในการติดตั้งปัจจุบัน) |
| หลักฐาน | `server/pyproject.toml:5` (`requires-python = ">=3.11,<3.13"`) · `server/src/litstorm/render/brief.py:558` (`f'<div class="tile c{i}"{f' id="{block_id}"' if block_id else ""}>...'` ใช้เครื่องหมายคำพูดตัวนอกซ้ำในนิพจน์ซ้อน ซึ่งเพิ่งถูกต้องใน Python 3.12 / PEP 701) · `ruff check src --select F,B,E9` รายงาน `invalid-syntax: Cannot reuse outer quote character in f-strings on Python 3.11` · ยืนยันด้วยตัวแปล 3.11.15 จริง: `uv run --no-project --python 3.11 python -c "compile(open('src/litstorm/render/brief.py',encoding='utf-8').read(),'brief.py','exec')"` ได้ `SyntaxError: f-string: expecting '}'` ที่บรรทัด 558 · `render/interactive.py:936` import `brief` แบบ lazy จึงพังตอนสร้างรายงาน ไม่ใช่ตอนเริ่มระบบ |

**สถานการณ์:** นักพัฒนาหรือผู้ติดตั้งที่ใช้ Python 3.11 (ซึ่งอยู่ในช่วงที่ประกาศ) เริ่มระบบได้ปกติ Run ทำงานได้ แต่เมื่อ Run จบแล้วสร้าง `interactive-*.html` จะได้ `SyntaxError` ที่ import `brief` และไม่มีรายงานแบบโต้ตอบ เทสต์ทั้งชุดรันบน 3.12 จึงไม่เคยเห็น

**วิธีแก้ที่เสนอ:** ดึงนิพจน์ซ้อนออกเป็นตัวแปร (`ident = f' id="{block_id}"' if block_id else ""`) หรือเปลี่ยนเป็น `requires-python = ">=3.12,<3.13"` ให้ตรงกับภาพ Docker · ขนาด: เล็ก

## BUG-46 — โมเดล SQLAlchemy กับ migration ไม่ตรงกัน: `alembic check` ล้มด้วย index 3 ตัว

| | |
|---|---|
| ระดับ | ต่ำ (ฐานข้อมูลทำงานถูก; ผลคือ autogenerate ครั้งหน้าจะสร้าง migration ที่ลบ index เดิมแล้วสร้างตัวใหม่เอง และ `alembic check` ใช้เป็นด่านใน CI ไม่ได้) |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | บน stack `litstorm-audit` ที่ migration 0014: `docker exec -w /app/server litstorm-audit-api-1 alembic check` ได้ `FAILED: New upgrade operations detected` มี 6 รายการ (ลบ+เพิ่มอย่างละ 3): `api_tokens_user` vs `ix_api_tokens_user_id` · `question_refinements_user (user_id, created_at)` vs `ix_question_refinements_user_id (user_id)` · `visuals_requests_user (user_id, created_at)` vs `ix_visuals_requests_user_id (user_id)` · migration สร้างด้วยชื่อเอง (`server/src/litstorm/migrations/versions/0013_api_tokens.py:42`, `server/src/litstorm/migrations/versions/0007_question_refinements.py:24`, `server/src/litstorm/migrations/versions/0011_visuals_requests.py:24`) ขณะที่โมเดลใช้ `index=True` (`server/src/litstorm/db/models.py:77, 240, 251`) · schema หลัง downgrade base แล้ว upgrade head เหมือนเดิมทุกบรรทัด (ดู `task-4-report.md`) แปลว่า migration เป็นฝ่ายที่ใช้งานจริง และ index แบบ `(user_id, created_at)` คือสิ่งที่ฐานข้อมูลมี |

**สถานการณ์:** นักพัฒนารัน `alembic revision --autogenerate` เพื่อเพิ่มตารางใหม่ แล้วได้ migration ที่แอบมี `drop_index`/`create_index` ของสามตารางนี้ติดมา ถ้าไม่ตรวจก็จะเปลี่ยน index ประกอบ `(user_id, created_at)` ที่ใช้นับโควตารายวันเป็น index เดี่ยว

**วิธีแก้ที่เสนอ:** ให้โมเดลประกาศ `Index("question_refinements_user", "user_id", "created_at")` ฯลฯ ตรงกับ migration (หรือสร้าง migration ใหม่ที่ปรับชื่อ) แล้วเพิ่มเทสต์ที่เรียก `alembic.autogenerate.compare_metadata` ให้ได้รายการว่าง · ขนาด: เล็ก

## BUG-47 — `backup.sh` นับ "ตารางที่มีข้อมูล" จากทุกตารางในไฟล์ dump จึงรายงานเกินจริงและด่าน "ไม่ใช่ backup" ไม่เคยกันฐานข้อมูลว่าง

| | |
|---|---|
| ระดับ | ต่ำ (ข้อความหลอกคนอ่านผล backup/verify; ข้อมูลไม่เสีย) |
| ผู้ใช้เห็นไหม | ใช่ (ผู้ดูแลที่รัน `backup.sh` หรือ `--verify` เห็นจำนวนที่ไม่จริง) |
| หลักฐาน | `stack/backup.sh:64-66` (`tables_in`: `pg_restore --list \| grep -c 'TABLE DATA'`) ซึ่ง pg_restore เขียนรายการ `TABLE DATA` ให้ทุกตารางไม่ว่ามีแถวหรือไม่ · `:124-125` ใช้เป็นด่านก่อนเขียน manifest · ลองจริงบน `litstorm-audit` (มีแถวแค่ 3 ตาราง: `system_settings` 1, `search_providers` 1, `alembic_version` 1 จาก `pg_stat_user_tables`; 12 ตารางที่เหลือว่าง): `PROJECT=litstorm-audit bash stack/backup.sh <dest>` พิมพ์ `verified  15 tables with data` และ manifest ใส่ `tables=15`; `--verify` พิมพ์ `tables with data: 15`; `--restore` พิมพ์ `database restored (15 tables with data)` ·  ผลข้างเคียง: dump ของฐานข้อมูลที่ถูกล้างหมดก็ผ่านด่าน (ตัวเลขเท่าเดิม) |

**สถานการณ์:** ผู้ดูแลเห็น `15 tables with data` เชื่อว่าฐานข้อมูลสำรองครบ ทั้งที่ dump ว่างทั้งหมดก็ได้ตัวเลขเท่ากัน การเตือนว่า "ไม่ใช่ backup" (`lists no table data`) จึงเกิดได้เฉพาะ dump เสียจน `pg_restore --list` อ่านไม่ได้เท่านั้น

**วิธีแก้ที่เสนอ:** เปลี่ยนข้อความเป็น "tables in dump" และให้ manifest เก็บแถวของตารางหลัก (`select count(*)` ของ `users`, `runs`) เทียบกับหลัง restore · ขนาด: เล็ก

## BUG-48 — เทสต์ `test_two_runs_at_once_keep_their_own_language` ไม่เสถียร: ล้มเมื่อ process ลูกจองหน่วยความจำไม่ได้ และเทสต์ซ่อนสาเหตุ

| | |
|---|---|
| ระดับ | ต่ำ (เทสต์ไม่เสถียร ไม่ใช่ผลิตภัณฑ์; แต่ทำให้ชุดเทสต์เต็มแดงบน baseline ทำให้แยกบั๊กจริงยาก) |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | `tests/test_supervisor.py:128-147` · รายงาน Task 3a และ 3b บันทึกว่าล้มในชุดเต็มบน baseline (889 passed, 1 failed; `KeyError: 'th'`) และผ่านเมื่อรันเดี่ยว (รอบนั้นไม่ได้เก็บ `stderr.log` ไว้ จึง**ไม่ยืนยัน**ว่าเป็นสาเหตุเดียวกับรอบ Task 4 ด้านล่าง เป็นเพียงอาการเดียวกัน) · ในรอบ Task 4 (หน่วยความจำ commit ว่างของเครื่อง dev เหลือ 1.7 GB จาก 32 GB เพราะ Docker Desktop) **ล้มเมื่อรันเดี่ยว 3 จาก 3 ครั้ง**: `uv run pytest -q tests/test_supervisor.py::test_two_runs_at_once_keep_their_own_language` · สาเหตุที่ขุดได้ด้วยสคริปต์ที่พิมพ์ `outcome`: Run หนึ่งจบ `failed`/`engine_error` ("the run's process exited with code 1 and no outcome") และ `stderr.log` ของมันเต็มไปด้วย `OpenBLAS error: Memory allocation still failed after 10 retries, giving up.` (process ลูกที่ import numpy พร้อมกันสองตัว แต่ละตัวเปิด thread ตามจำนวน core = 16) · Run เดี่ยวแบบเดียวกันผ่าน · หลังหน่วยความจำ commit ว่างกลับมา (11 GB) เทสต์เดียวกันผ่านใน `pytest -m "not db"` (222 passed) ซึ่งสนับสนุนสาเหตุเรื่องหน่วยความจำ · เทสต์ใช้ `assert` ใน thread (`:138`) ซึ่ง pytest เก็บเป็นแค่ warning แล้วเทสต์ล้มที่ `KeyError: 'th'` บรรทัด 146 จึงไม่บอกสาเหตุ · ไม่มีการจำกัด `OPENBLAS_NUM_THREADS`/`OMP_NUM_THREADS` ที่ใดใน `server/` และ `stack/` (grep ไม่พบ) |

**สถานการณ์:** เครื่องที่หน่วยความจำ commit ใกล้เต็ม (หรือ container ที่มี memory limit เล็ก) เมื่อ Worker เริ่มสอง Run พร้อมกัน process ลูกของ Run หนึ่งอาจตายตั้งแต่ import numpy ผู้ใช้เห็น Run ล้มเป็น engine error โดยสาเหตุจริงอยู่แค่ใน `stderr.log` ของ Run

**วิธีแก้ที่เสนอ:** (1) ทำให้เทสต์เก็บ `outcome` จาก thread แล้ว assert ในเธรดหลักพร้อมแนบ `stderr.log` · (2) ตั้ง `OPENBLAS_NUM_THREADS=1` (หรือค่าเล็ก) ใน environment ของ process ลูกที่ supervisor เปิด เพื่อไม่ให้แต่ละ Run จอง buffer ตามจำนวน core · ขนาด: เล็ก

---

## ส่วนที่สี่ (Task 5): ลองจริงทุกโหมด

ฐานที่ตรวจ HEAD `44ae50e` บน stack audit (:8098) ด้วยโมเดลจริงผ่าน OpenRouter รายละเอียดของแต่ละ Run อยู่ใน [live.md](live.md) **รหัสใหม่ BUG-49 ถึง BUG-52** หลักฐานของข้อเหล่านี้มาจาก Run จริง (id ใน live.md) ไม่ใช่เทสต์ xfail

## BUG-49 — Run ของโหมด Agent จบ "เสร็จแล้ว" ทั้งที่รายงานคือข้อความ error ดิบของผู้ให้บริการ และข้อความนั้นมี account id ของ OpenRouter

| | |
|---|---|
| ระดับ | **กลาง** |
| ผู้ใช้เห็นไหม | ใช่ (อยู่ในรายงาน และทุกไฟล์ export) |
| หลักฐาน | Run `2c6fa24b` (Agent, ไทย, เร็ว, Gemini 2.5 Flash Lite): status `succeeded`, source_count 1; ย่อหน้าแรกของรายงานคือ `Error code: 400 - {'error': {... 'Function calling with a response mime type: application/json is unsupported' ... 'user_id': 'user_…'}}` ตามด้วยคำอธิบายที่โมเดลแต่งเอง และอ้างอิง [1][1][1] ซ้ำท้ายทุกประโยค แหล่งอ้างอิงเดียวคือ `searxng:8080` (หน้าจอ `shots/12-report-agent-error-report.png`) |

เครื่องมือค้นของ Agent ล้มด้วย 400 แล้ว library ส่งข้อความ error เป็น "ผลค้น" ให้โมเดลเขียนต่อ DeepLit ไม่ตรวจว่าแหล่งอ้างอิงมีเนื้อหาจริง จึงนับเป็นสำเร็จและไม่คืนโควตา ผู้ใช้ได้รายงานที่ไม่มีข้อมูลหนึ่งบรรทัด และเห็น id บัญชี OpenRouter ของเจ้าของระบบ

**แก้ที่เสนอ:** ถ้าไม่มี browsed/found ที่ได้เนื้อหาเลย ให้ Run ล้มด้วยเหตุ `empty_report` (มีอยู่แล้ว ใช้กับ Run `a354bc1c`) และกรองข้อความ error ของผู้ให้บริการก่อนเข้ารายงาน · ขนาด: เล็ก (ประเมินตอนรวมรายงาน)

## BUG-50 — `message` ของ Run ที่ล้มส่ง error ดิบของผู้ให้บริการ รวม account id ของ OpenRouter ให้เจ้าของ Run

| | |
|---|---|
| ระดับ | **ต่ำ** (id บัญชี ไม่ใช่ key) |
| ผู้ใช้เห็นไหม | ผ่าน API และ MCP เท่านั้น (หน้าเว็บแสดงข้อความสุภาพ) |
| หลักฐาน | 4 Run ที่ล้มด้วย 429 (`3efd60e6`, `a2da08c8`, `52a2619f`, `e04135d5`): `GET /api/runs/{id}` ของผู้ใช้ทั่วไปมี `message` 722 ตัวอักษร ที่มี `"user_id":"user_…"` ของ OpenRouter และชื่อผู้ให้บริการ/URL ตั้งค่า (`openrouter.ai/settings/integrations`) หน้าสถานะระบบไม่แสดง (ตัดแล้ว) นับ `sk-or-` ได้ 0 ทั้งใน log, `message` และ stderr.log — `stderr.log` พบรูปแบบ `user_…` 1 ครั้ง |

ยืนยันข้อสงสัย e-S7 ของ Task 3 (คืนค่า `message` ดิบให้เจ้าของ): key ไม่รั่ว แต่ id บัญชีของ operator รั่ว **แก้ที่เสนอ:** ใช้ตัวกรองเดียวกับหน้าสถานะระบบ (`monitor.KEYLIKE` ขยายให้ครอบ `user_…`) กับ `run_out` (และ `_run_facts` ของ MCP) ก่อนส่งให้เจ้าของ · ขนาด: เล็ก (ประเมินตอนรวมรายงาน)

## BUG-51 — ผู้ให้บริการตอบ 429 ชั่วคราว Run ล้ม "retries_exhausted" ภายใน 30–60 วินาที ไม่มี backoff ที่ทนได้

| | |
|---|---|
| ระดับ | **กลาง** |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | โมเดล `google/gemini-2.5-flash-lite` ผ่าน OpenRouter: STORM ไทย ล้มสองครั้งแรก (30 วินาที ที่ขั้น research, 150 วินาที ที่ขั้น outline) ครั้งที่สามผ่านใน 40 วินาที; Co-STORM เปิดล้ม 2 จาก 2 (ขั้น warmup 30 และ 60 วินาที) ข้อความ: `google/gemini-2.5-flash-lite is temporarily rate-limited upstream` (429 จาก pool ร่วมของ Google AI Studio) ปุ่มทดสอบโมเดล (เรียกครั้งเดียว) ผ่านทุกครั้ง |

429 จาก pool ร่วมเป็นเรื่องชั่วคราว แต่ engine ลองซ้ำไม่กี่ครั้งแล้วยอมแพ้ภายในครึ่งนาที (Run จริงใช้ LLM หลายตัวพร้อมกัน จึงชนบ่อยกว่าการทดสอบครั้งเดียว) ผู้ใช้เห็น "ล้มเหลว" แต่โควตาคืนให้ (ถูกต้อง) โมเดลถูกที่สุดที่ README แนะนำจึงใช้งานจริงไม่ได้ในบางช่วง **แก้ที่เสนอ:** backoff แบบยาวขึ้นสำหรับ 429 (ตามเวลา `Retry-After` ถ้ามี) หรือรองรับ fallback model · ขนาด: กลาง (ประเมินตอนรวมรายงาน: การลองซ้ำอยู่คนละที่ในแต่ละ engine และใน library ของ upstream)

## BUG-52 — ปุ่มทดสอบโมเดลบอก "เรียก tool ได้" แต่โหมด Agent ใช้ Gemini 2.5 Flash Lite ไม่ได้

| | |
|---|---|
| ระดับ | **กลาง** |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | ทดสอบโมเดลได้ `tools: true` จึงเลือกโหมด Agent ได้; Run `2c6fa24b` ล้มที่เครื่องมือค้นด้วย 400 `Function calling with a response mime type: 'application/json' is unsupported` (ดู BUG-49) การทดสอบของ DeepLit เรียก tool แบบธรรมดา แต่เครื่องมือของ Agent ขอ JSON ผ่าน function calling ร่วมกัน ซึ่ง Gemini ไม่รองรับ |

โมเดลที่ผ่านการทดสอบจึงไม่การันตีว่าใช้กับ Agent ได้ (อีกโมเดลที่ผ่านคือ `openai/gpt-4.1-nano` ก็ได้ `empty_report` ที่ Run `a354bc1c`) **แก้ที่เสนอ:** ให้การทดสอบเลียนแบบการเรียกของ Agent หรือแสดงว่าโหมดไหนใช้กับโมเดลนั้นได้จริง · ขนาด: เล็กถึงกลาง (ประเมินตอนรวมรายงาน)

## สงสัย (ทำซ้ำไม่ได้)

| ข้อ | สิ่งที่ลอง | สิ่งที่ควรทำใน task ที่ลองจริง |
|---|---|---|
| a-S6 (kill ตาม deadline/ยกเลิก ทับ outcome ที่ child เพิ่งเขียน และ usage ของ stage ที่ถูกฆ่าหาย) | อ่านโค้ด: child เขียน `outcome.json` แล้วเรียก `os._exit(0)` ทันที (`child.py:main`) หน้าต่างระหว่าง `proc.poll()` กับ `proc.kill()` เหลือไม่กี่มิลลิวินาที ไม่มีทางคุมจังหวะนั้นใน pytest โดยไม่จำลองจนเทสต์ไม่แสดงของจริง เทสต์ที่มีอยู่ (`test_cancel_that_loses_to_completion_keeps_the_report`) ครอบเฉพาะกรณียกเลิก ส่วน usage ของ stage ที่ถูกฆ่าไม่ถูกบันทึกเป็นลักษณะของ engine (รายงาน usage ทีละ stage) | รัน Deep Run จริงด้วย deadline สั้นแล้วเทียบ `cost_usd` กับยอดที่ OpenRouter เรียกเก็บ (ภายในเพดาน $2.50 ของ Task จริง) |
| a-S8 (Windows: `_exit_when_orphaned` ออกทันทีเมื่อเปิด handle ของ parent ไม่ได้) | อ่านโค้ด `child.py:114-126`: ถ้า `OpenProcess` คืน 0 โค้ดตกไป `os._exit(4)` จริง แต่ถ้า parent ตายไปแล้ว (pid ไม่มี) การออกคือคำตอบที่ถูก ส่วนกรณีที่ผิด (parent ยังอยู่แต่ถูกปฏิเสธสิทธิ์) หา trigger ไม่ได้: process ลูกกับ parent เป็นผู้ใช้เดียวกัน `SYNCHRONIZE` เปิดได้เสมอ และ host จริง (Linux/Docker) ไม่ใช้เส้นทางนี้ | ไม่ต้องทำในรอบนี้; ถ้าจะ harden ให้เช็ก `GetLastError()` แยก "ไม่มี process" (87) ออกจาก "ถูกปฏิเสธ" (5) |
| a-S9 (spare ที่ถูก kill ไม่ถูก wait / spare ที่ค้างตอน import ทำให้ Run รอ) | ไม่ได้ลอง: ซอมบี้เกิดเฉพาะ Linux (เครื่อง dev เป็น Windows ไม่มี `ps`) และ spare ที่ค้างต้องการ import ที่ติดเครือข่าย (LiteLLM โหลดตารางราคา) ซึ่งจำลองใน pytest ไม่ได้ซื่อตรง | บน stack ทดสอบ: `docker exec` ไปฆ่า spare ของ Worker ทันทีหลัง claim แล้วดู `ps` หา `<defunct>`; และตั้ง egress ปิดแล้วนับเวลาจนมี event แรกของ Run แรกหลังเริ่ม Worker |
| c-S11 (restore แข่งกับ purge ที่ขอบ 30 วัน) | ไม่ได้ลอง: ต้องสอดการ commit ของ restore ระหว่าง `select(Run)` กับลูปลบใน `purge` ซึ่งต้อง monkeypatch กลางฟังก์ชันจนไม่ใช่สถานการณ์จริง หน้าต่างกว้างไม่กี่วินาทีต่อรายการ และ API กับ Worker ใช้นาฬิกาเดียวกัน | ไม่คุ้มทดสอบสด; ถ้าแก้ BUG-21/17 ใน `purge` อยู่แล้ว ให้ล็อกแถวด้วย `FOR UPDATE SKIP LOCKED` ตอนเลือก |
| e-S7 (`GET /api/runs/{id}` ส่ง `run.message` ดิบให้เจ้าของ ขณะที่หน้าสถานะระบบตัดข้อความที่หน้าตาเหมือน key) | ยืนยันด้านโค้ดแล้ว: `api/research.py:396` (`message=run.message`) และ `api/mcp.py:306` (`facts["message"] = run.message`) ส่งข้อความดิบ ส่วน `monitor._said` ตัด KEYLIKE เฉพาะฝั่งผู้ดูแล แต่ทำซ้ำการรั่วจริงไม่ได้ เพราะต้องมีผู้ให้บริการที่พูด key ซ้ำในข้อผิดพลาด (OpenAI ปิดบางส่วน, OpenRouter/Tavily/Gemini ไม่พูด) หน้าเว็บไม่แสดง `message` (FailureNote แสดงเฉพาะ `service_declined`) ข้อนี้ตรงกับข้อสังเกตที่ 1 ท้าย `security.md` ที่ส่งต่อ Task 5 ไว้แล้ว | Task 5 (ตามที่ `security.md` ระบุ): นับ pattern ของ key ใน `runs.message` ทุกแถวหลังลองทุกโหมดรวมกรณี key ผิด และสแกน field `message` ของ `research_status` ทาง MCP ด้วย; ถ้าเจอ ให้เป็น SEC ระดับกลาง (ผู้ใช้ทั่วไปเห็น key ของระบบ) และแนวแก้คือเอา KEYLIKE ไปใช้ที่ `run_out`/`_run_facts` ด้วย |
| e-S12 (หน้า login แสดง "login failed" กับทุกความผิดพลาด รวม 500, 429 และเครือข่ายล้ม) | อ่านโค้ดแล้ว: `web/src/pages/auth.tsx` (ราว :393-398) แสดง `t("login.failed")` เมื่อ `login.error` มีค่า ไม่ดูชนิด/รหัสของข้อผิดพลาด จึงเป็นไปได้สูง แต่โปรเจกต์ไม่มี test framework ฝั่งเว็บ (ไม่มี vitest/jest ใน `package.json`) และการพิสูจน์ต้องรันหน้า จึงยังไม่ลงเป็นบั๊ก | Task 8/9 ด้วย Playwright (`server/tests/ui.py` และ `LITSTORM_PDF_BROWSER_CHANNEL=msedge`): (1) เปิดหน้า login ของ stack ทดสอบ (2) ดัก route `**/api/auth/login` ให้ตอบ 503 (และอีกรอบให้ `abort` เพื่อจำลองเครือข่ายล้ม) (3) กรอกอีเมลกับรหัสอะไรก็ได้แล้วกดเข้าสู่ระบบ (4) ถ้าข้อความเป็น "อีเมลหรือรหัสผ่านไม่ถูกต้อง" ในทั้งสองกรณี ให้ลงเป็น BUG ระดับต่ำ (ผู้ใช้เข้าใจผิดว่ารหัสผ่านผิด แล้วขอให้ผู้ดูแลออกลิงก์รีเซ็ต ซึ่งออกจากระบบทุกเครื่อง) |

## ตัดทิ้ง

| ข้อ | เหตุผล |
|---|---|
| b-S9 (Turn ถูกส่งก่อน Run ของทุกคนและไม่หักโควตา อาจทำให้คิวอดอยาก) | เป็นการออกแบบที่ระบุไว้: คอมเมนต์ที่ `worker/queue.py:94-95` ("A Discussion's Turn first: its owner is waiting on the page") และ `docs/web-app-design.md` (Turn เป็นงานในคิวเดียวกับ Run อยู่หน้าคิว) ผู้อ่านเองรายงานเป็น "ช่องว่างด้านความเป็นธรรม" ไม่ใช่บั๊กในการนับ และ Turn ถูกจำกัดด้วย `max_queued` และ 1 Turn ต่อ Discussion ไม่มีหลักฐานการอดอยากจริง เรื่องนี้เป็นเรื่องนโยบายให้เจ้าของตัดสินถ้าต้องการ |
| b-S10 (เดือนโควตาถูกตรึงตอนส่ง Run ที่ข้ามเดือนจึงไม่นับกับเดือนใหม่) | เป็นกติกาที่เขียนไว้ตรงๆ: `docs/web-app-design.md:206-207` ("งานที่เข้าคิวหรือกำลังทำข้ามเดือนยังนับกับเดือนที่จองไว้ตั้งแต่แรก") และ docstring ของ `quota.py` ส่วนความคลาดเคลื่อนที่ผู้อ่านเสนออีกข้อ (`new_run` เรียก `quota_month()` ซ้ำหลัง `check_submit`) ต่างกันได้เฉพาะเสี้ยววินาทีตอนเที่ยงคืนพอดี ผลกระทบเป็นศูนย์ในทางปฏิบัติ |
| c-S6 (Run ที่ถูกลบก่อนถูก purge ก่อน Session แม่ที่ถูกลบทีหลัง) | ไม่ใช่บั๊ก: ผู้ใช้เป็นคนลบ Run นั้นเองเมื่อ 30 วันก่อน การนับ 30 วันของมันเองหมดก่อนเป็นผลที่ถูกต้องตามกติกา "นับจากวันที่ลบ"; ส่วน "การกู้คืนรายการย่อยของ parent" เอกสารเองระบุว่ายังไม่ได้กำหนด (`docs/web-app-design.md:262`: "รายละเอียดการกู้คืนรายการย่อย...ต้องกำหนดเพิ่มเติม") จึงเป็นช่องว่างของข้อกำหนด ไม่ใช่ความประพฤติผิด ควรให้เจ้าของตัดสินกติกาก่อน |
| d-S3 (ลองใหม่ของ Turn: ไม่ล็อก, เล่น Turn เก่าซ้ำ, ขยายชุดไม่ได้) | **ซ้ำกับ BUG-12** (A: กดลองใหม่สองครั้งพร้อมกันได้สอง Turn คิวซ้อน) และ **ซ้ำกับ BUG-15** (C: `retry` ไม่ส่ง `extend` จึงตอบ 409 `turns_exhausted` เมื่อชุดเต็ม; BUG-15 ทดสอบกรณีโควตาคืน กรณี Turn ที่ไม่คืนโควตาเป็นรากเดียวกัน) ส่วน B (ลองใหม่ Turn เก่าหลัง Turn อื่นสำเร็จแล้ว คำถามเก่าถูกถามเป็น Turn ใหม่ท้ายบทสนทนา): ทำซ้ำได้แต่ไม่ใช่บั๊ก: `retry` ตั้งใจให้ "ถามอีกครั้งเป็น Turn ใหม่" (`api/research.py:817-820`) และหน้า Discussion เสนอปุ่มลองใหม่เฉพาะ Turn สุดท้ายที่ล้ม (`pages/discussion.tsx:394-398`) ซึ่งเรียก `/turns` ที่มีล็อกและกล่องขอขยายชุด ไม่ได้เรียก `/runs/{id}/retry` จึงเกิดได้เฉพาะ API ตรง |
| d-S5 (Turn บันทึกอะไรเมื่อจบทั้งหมดเท่านั้น ล้มช้าๆ ทิ้งทุกขั้นที่จ่ายไปแล้ว) | เป็นการออกแบบที่เขียนไว้: `discussion.py` ("a Turn that fails, is stopped or loses its Worker costs only itself": Turn ที่ล้มไม่ทิ้งสถานะ) และเหตุผลที่คืนโควตาให้ เจ้าของจึงไม่เสียเงิน ส่วนค่า token ที่เสียไปกับขั้นที่ทิ้งเป็นต้นทุนของผู้ดูแล เป็นข้อเสนอปรับปรุงมากกว่าบั๊ก (บันทึกสถานะทุกขั้นของ `auto`) ที่เหลือที่ผู้อ่านเสนอ (usage ของ `runner.step(user_utterance)` และ `with_lead` ที่ล้มกลางทางไม่ถูกบันทึก; docstring ของ `auto` พูดถึง "stop" ที่ไม่มี) กระทบเฉพาะกรณีที่ขั้นนั้นล้มเอง และไม่มี runner จริงให้ทำซ้ำ จึงไม่ลงเป็นบั๊ก |
| d-S6 (ไฟล์ state ของ Turn ล่าสุดหาย: Discussion ถอยไปใช้ state เก่าเงียบๆ) | ทำซ้ำพฤติกรรมได้ (start + 3 step แล้วลบ `costorm_state.json` ของ step ที่ 3: หน้าแสดง view ของ step ที่ 2 และ `allowance.used` ยังนับ step ที่ 3) แต่ไม่ใช่บั๊กของแอป: `last_state` ถูกออกแบบให้ข้าม Turn ที่ "ไม่ได้ทิ้ง state ไว้" (docstring: "the latest finished Turn that left a state") และต้องมีไฟล์หายจากภายนอกก่อน (volume ถูกสลับ, ล้างดิสก์) ถ้าเจ้าของต้องการให้ตกใจเสียงดังแทนถอยเงียบๆ เป็นการตัดสินใจของเจ้าของ |
| d-S7 (ทุกการ poll ส่ง Discussion ทั้งก้อน ขนาดโตตามบทสนทนา) | วัดแล้ว: Discussion 301 Turn กับ view ที่มี 300 บรรทัดสนทนาและ 300 แหล่ง แหล่งละ 3 snippet ได้ response 1.0 MB ใช้ 40 มิลลิวินาที (เรียกซ้ำ 3 ครั้งนิ่ง) และหน้าเว็บ poll เฉพาะตอนมี Turn รอ (ทุก 3 วินาที) หรือกำลังทำ (ทุก 30 วินาที เพราะมี push ให้) ไม่ poll ตอนว่าง (`pages/discussion.tsx:342-346`) ผลกระทบเล็กและจำกัด จึงไม่ใช่บั๊ก |
| d-S10 (หน่วยโควตาของ Discussion ผูกกับเดือนของ Turn ที่เปิดชุด) | เป็นกติกาที่เขียนไว้: `docs/web-app-design.md:206-207` ("งานที่เข้าคิวหรือกำลังทำข้ามเดือนยังนับกับเดือนที่จองไว้ตั้งแต่แรก" เหตุผลเดียวกับ b-S10 ที่ตัดทิ้งใน Task 3a) และ "หนึ่งชุด = หนึ่งหน่วย" ตามโมดูล `discussion.py` ผู้อ่านเองให้ความมั่นใจต่ำและระบุว่าเป็นเรื่องที่ควรให้เจ้าของตัดสิน |
| e-S5 (ตรา badge ด้านข้างโหลดทุก Run ที่ล้มในช่วงเวลาทั้งแถว ทุกนาทีต่อแท็บผู้ดูแล) | วัดแล้ว: เพิ่ม 3,000 Run ที่ล้มใน 7 วัน (ข้อความ 5 KB ต่อแถว ซึ่งเป็นกรณีที่ระบบแย่มาก) `GET /api/admin/monitor/open` ใช้ 0.49-0.72 วินาที ต่อครั้ง และหน้าเต็ม 0.67 วินาที เวลาโตตามจำนวนความล้มเหลวจริง แต่ที่ระดับปกติ (หลักสิบ-ร้อย) ไม่มีนัยสำคัญ และเป็นช่วงที่ระบบกำลังมีปัญหาอยู่แล้ว จึงไม่ถึงเกณฑ์บั๊ก (ถ้าจะปรับ: เลือกเฉพาะคอลัมน์ที่ใช้แทน `select(Run)`) |
| f-S1 (`research_start` ซ้ำหลังเจ้าของลบ Run ลงถังขยะได้ 404) | **ซ้ำกับ BUG-19** (รากเดียวกัน: `_repeat_of` ไม่ตรวจ `trashed_at`/`trash.run_alive`; ผู้อ่านยกกรณีลบ Run เดี่ยว BUG-19 ยกกรณีลบ Session แต่แก้ที่ฟังก์ชันเดียวกัน ด้วย `trash.run_alive` ที่ครอบทั้งสองกรณี) |
| f-S3 (`research_start` สองครั้งพร้อมกันด้วยอาร์กิวเมนต์เดียวกัน เริ่มสองอันและหักโควตาสองครั้ง) | **ซ้ำกับ BUG-09** ลองจริงแล้ว (barrier หลัง `_repeat_of`, สอง tool call ขนานผ่าน MCP client, ทำ 3 รอบ): ทุกรอบคำขอหนึ่งชน `DeadlockDetected` (BUG-09) และเหลือ Run เดียว จึงเห็นการเริ่มซ้ำสองอันไม่ได้ เพราะ deadlock มาก่อน หน้าต่างเดียวกัน (`_repeat_of` อ่านก่อน `_start_session` แทรกแถวและ commit) จะโผล่เมื่อแก้ BUG-09 ด้วยการล็อกแถวผู้ใช้ จึงต้องตรวจ `_repeat_of` ซ้ำภายใต้ล็อกด้วย (เช่นเดียวกับ BUG-10/11) ควรเพิ่มเงื่อนไขนี้ในการแก้ BUG-09 ส่วนช่วงที่ `via_token_id` ถูกเขียนหลัง commit ของ Run (Run ไม่มี token ชั่วคราว) ตัดสินจากโค้ดว่าเป็นช่วงสั้นและเทสต์ไม่ได้ |
| f-S7 (event ของ MRA ที่มี key `kind`/`event`/`seq` ชนกับอาร์กิวเมนต์ของ `progress.note`) | ตรวจ payload ที่ MRA ส่งจริงแล้วที่ `../MedicalReviewerAgent/backend/app` (`graph/nodes/*.py`, `worker/runner.py`): ทุก event ใช้ key `type`, `ref`, `title`, `found`, `queries`, `kept`, `total`, `ok`, `verified`, `uncertain`, `direction`, `design`, `refined_question` ฯลฯ และ worker เพิ่มเฉพาะ `elapsed_s` ไม่มี event ใดใช้ `kind`, `event` หรือ `seq` ความล้มเหลวเป็นทฤษฎีล้วน (ผู้อ่านเองให้ความมั่นใจต่ำและบอกให้ตรวจก่อน) |
| f-S9 (Run ที่ถูก kill ทิ้ง Node CLI วิ่งต่อและใช้ token ต่อ) | อ่านต้นฉบับ CLI แล้ว (`../deep-research-web-ui/cli/litstorm.ts`): มี `process.stdin.on('end', () => (done ? process.exit(3) : ...))` และ stdin อยู่ในโหมด flowing (`on('data')`) เมื่อ process แม่ถูก kill ท่อ stdin ปิดและ CLI ออกเอง แม้กำลังรอ fetch (event loop ยังทำงาน) เอกสารบนหัวไฟล์ระบุไว้ ("It also exits when stdin closes, so it never outlives the process that started it") จึงไม่ใช่บั๊ก (ยังไม่ได้ลองกับ CLI ที่ bundle แล้วในคอนเทนเนอร์ Worker จริง แต่ตรรกะปิดช่องแล้ว) |
| f-S10 (Deep CLI: usage ก่อน stage แรกหาย, ไม่มี `markdown` ได้ KeyError, เริ่มไม่ขึ้นทำให้ handle รั่ว) | อ่านต้นฉบับ CLI แล้ว: (a) `emit({type:'stage', stage:'research'})` ออกก่อนที่ `deepResearch` จะเรียกโมเดลตัวแรก จึงไม่มี usage ก่อน stage แรก (`onUsage` เรียกในโมเดลเท่านั้น); (b) event `report` ถูกสร้างพร้อม `markdown` เสมอ (สตริงว่างได้ ไม่ใช่ไม่มี key); (c) แต่ละ Run ทำงานใน process ของตัวเองที่จบเมื่อ Run จบ handle ที่ไม่ปิดไม่สะสม และ `BrokenPipe` ต้องแข่งกับการตายของ Node ภายในไม่กี่ร้อยมิลลิวินาที (ถ้า `node` หาไม่เจอ `Popen` ยกข้อยกเว้นเอง) ผลสุดท้ายคือ Run `engine_error` ที่คืนโควตา ไม่มีผลต่อผู้ใช้เกินข้อความ |

---

## ส่วนที่ห้า (Task 6): จำลองความล้มเหลว

ฐานที่ตรวจ HEAD `92f2934` บน stack audit (:8098) ด้วย stub ที่ตอบ 429/401/ช้าเอง ไม่เสียเงินจริง รายละเอียดทั้งห้ากรณีอยู่ใน [live.md](live.md#จำลองความล้มเหลว) ผล 4 ใน 5 กรณีตรงที่คาดทุกข้อ (เหตุผล, Issue ที่เปิด, คืนโควตา) มี 1 ข้อใหม่คือ **BUG-53**

## BUG-53 — บริการค้นหาที่ไม่ตอบ ถูกรายงานว่า "ค้นไม่พบเนื้อหา" และผู้ดูแลไม่ได้รับแจ้ง

| | |
|---|---|
| ระดับ | **กลาง** |
| ผู้ใช้เห็นไหม | ใช่ (ข้อความโทษหัวข้อ) และผู้ดูแลไม่เห็น |
| หลักฐาน | Run `5c48bf01` (STORM, ไทย, เร็ว): Search Provider ชนิด SearXNG ชี้ไป stub ที่ตอบหลัง 75 วินาที (เกิน timeout 30 วินาที) Run ล้ม `empty_report` ที่ขั้น research ใน 71 วินาที `system_fault=false` `message="the research found no sources for this topic"` การ์ดบอกผู้ใช้ "ค้นคว้าแล้วไม่พบเนื้อหาที่จะเขียนรายงาน ลองเขียนหัวข้อให้กว้างขึ้น หรือเลือกบริการค้นหาอื่น" หน้าสถานะระบบขึ้นเป็น Issue ระดับ `watch` และ `open=false` ป้ายแจ้งเตือน (`/api/admin/monitor/open`) ไม่เพิ่ม |

`knowledge_storm/rm.py` (`SearXNG.forward`) จับทุก exception ใน `except Exception` แล้วแค่ log จึงไม่นับเป็น `refused` ทั้งที่ engine มีทางบอก "the search provider refused N searches" อยู่แล้ว (`engines/storm/engine.py:204`, `costorm/engine.py:361`) timeout, connection refused และ 5xx ของบริการค้นหาจึงเหมือนหัวข้อที่ไม่มีแหล่ง โควตาคืนถูกต้อง แต่ถ้าบริการค้นหาล่มจริง ผู้ใช้ทุกคนจะถูกบอกให้แก้หัวข้อ และผู้ดูแลไม่ถูกเตือนเลย (Issue ที่เป็น `watch` ไม่เปิดป้าย)

**แก้ที่เสนอ:** นับ timeout/ConnectionError/5xx เป็น `refused` พร้อม `last_refusal` และถ้าทุกคำค้นของ Run ล้มด้วยเหตุแบบนี้ ให้ล้มเป็น `retries_exhausted` (ระดับ system) ขนาด: เล็ก **เทสต์:** `test_bug53_a_search_service_that_cannot_be_reached_counts_as_refusing` (xfail strict)

**ซ้ำกับของเดิม (ไม่เพิ่มรหัสใหม่):** `message` ดิบของผู้ให้บริการ/ระบบที่ API ส่งให้เจ้าของ Run (เช่น `AuthenticationError: litellm.AuthenticationError: ... OpenAIException - Incorrect API key provided`, `MRA cannot be reached: [Errno 101] Network is unreachable`) คือ BUG-50 เรื่องเดียวกัน


---

## ส่วนที่หก (Task 7): ขีดจำกัดและข้อมูลแปลกๆ

ฐานที่ตรวจ HEAD `fdd97f5` บน stack audit (:8098) ผ่าน HTTP จริง (stub ของ Task 6 ไม่เสียเงิน) และ pytest ค่าที่ลอง: คิวเต็ม, Run พร้อมกันเกินเพดาน, หัวข้อ 10,000 ตัว, ไทย/อังกฤษ/emoji/RTL ปน, ชื่อโปรเจกต์ซ้ำ **ทำงานถูกต้อง** (ดู [live.md](live.md#ขีดจำกัดและข้อมูลแปลกๆ)) ที่พังมี 4 ข้อด้านล่าง ส่วนที่เกี่ยวกับ XSS อยู่ใน [security.md](security.md) (SEC-12 และตาราง "ผลของ Task 7")

## BUG-54 — ตัวอักษร NUL หรือ surrogate เดี่ยวในข้อความที่ผู้ใช้พิมพ์ ทำให้ได้ 500

| | |
|---|---|
| ระดับ | **กลาง** |
| ผู้ใช้เห็นไหม | ใช่ (ข้อผิดพลาดทั่วไป ไม่รู้สาเหตุ) แต่ต้องมีคนส่งค่านั้นจริง (วางข้อความจากไฟล์ไบนารีหรือ PDF เสีย หรือ client ที่ยิง API ตรง) |
| หลักฐาน | live บน stack audit: `POST /api/sessions` ด้วย `topic` ที่มี `\u0000` และอีกครั้งด้วย `\ud800` → `500 Internal Server Error` ทั้งคู่ เช่นเดียวกับ `POST /api/projects` (`name`), `request_key`, `sections[]`, `refinement[].answer` และ `PATCH /api/projects/{id}` (`search_scope`, `writing_style`) |

ความยาวผ่าน pydantic แล้วค่อยพังตอนเขียน: Postgres `text` ไม่รับ NUL (`psycopg.DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes` ส่วน `sections` และ `refinement` ที่เก็บเป็น JSONB ได้ `UntranslatableCharacter: \u0000 cannot be converted to text`) และ UTF-8 เข้ารหัส surrogate เดี่ยว `\ud800` ไม่ได้ (`UnicodeEncodeError`) JSON มาตรฐานยอมให้เขียนทั้งสองเป็น escape จึงไม่ถูกกันตอน parse Run ไม่ถูกสร้างและโควตาไม่ถูกหัก แต่ได้ 500 (log ขึ้น traceback) แทน 422 ข้อความของ Co-STORM (`text` ของ Turn เก็บใน `runs.turn` ซึ่งเป็น JSONB) น่าจะเป็นแบบเดียวกันตามโค้ด แต่ไม่ได้ทดสอบ เพราะต้องรอ warm start เสร็จ จึงไม่นับ

**แก้ที่เสนอ:** ตัด `\x00` และปฏิเสธ surrogate ที่ชั้นเดียว เช่น validator กลางของ pydantic ใช้กับ `RunIn`, `DiscussionIn`, `TurnIn`, `ProjectIn`, `ProjectPatch`, `QuestionAnswer` และ `sections` แล้วตอบ 422 ขนาด: เล็ก **เทสต์:** `test_bug54_a_character_the_database_cannot_hold_is_refused_not_a_500` (2 ตัวแปร xfail strict)

## BUG-55 — หัวข้อที่มีแต่ช่องว่างผ่านการตรวจ ได้ Run ที่ไม่มีหัวข้อ

| | |
|---|---|
| ระดับ | **กลาง** |
| ผู้ใช้เห็นไหม | ใช่ผ่าน API/MCP/token integration (หน้าเว็บกันเองด้วย `topic.trim().length >= 3`, `composer.tsx:598`) |
| หลักฐาน | live: `POST /api/sessions` ด้วย `topic: "     "` (และ `"\n\n\n"`) → 201 `title: ""`; Run ถูกหยิบไปทำจริง `running` แล้วล้ม `empty_report` ที่ขั้น research ใน ~20 วินาที (ใช้ stub) `topic: ""` ในรายละเอียด Run และรายการ Session แสดงแถวไม่มีชื่อ |

`RunIn.topic` มี `min_length=3` ซึ่งนับช่องว่าง แล้ว `new_run` ค่อย `.strip()` (`research.py:608`) topic ว่างจึงไปถึง engine: ขั้นอ่านโจทย์และค้นหารันด้วยหัวข้อว่าง กับโมเดลจริงจะเสียค่าโมเดลไปเรียก "ตีความหัวข้อว่าง" (ไม่ได้ลองกับโมเดลจริงเพราะห้ามเสียเงิน) กับ stub โควตาคืนเพราะ `empty_report` แต่ระหว่างนั้นกิน slot ของ Worker ผู้ใช้ MCP (`start` ใช้ `RunIn` เดียวกัน) ก็ผ่านได้

**แก้ที่เสนอ:** strip ก่อนตรวจความยาว (`StringConstraints(strip_whitespace=True, min_length=3)`) ใช้กับ `RunIn`, `DiscussionIn`, `RefineIn` ขนาด: เล็ก **เทสต์:** `test_bug55_a_topic_of_only_spaces_is_refused`

## BUG-56 — ชื่อโปรเจกต์ที่มีแต่ช่องว่างผ่านการตรวจ ได้โปรเจกต์ไม่มีชื่อ

| | |
|---|---|
| ระดับ | ต่ำ |
| ผู้ใช้เห็นไหม | ใช่ (การ์ดโปรเจกต์ไม่มีชื่อ แยกจากอันอื่นไม่ออก) |
| หลักฐาน | live: `POST /api/projects {"name":"     "}` → 201 `name: ""`; `shots/t7-projects-blank-dup.png` เห็นการ์ดไม่มีชื่อ เทสต์พบว่า `PATCH` ตั้งชื่อ `"   "` ก็ผ่าน |

สาเหตุเดียวกับ BUG-55: `ProjectIn.name` และ `ProjectPatch.name` มี `min_length` ก่อน `.strip()` (`research.py:196,208`) (BUG-30 ว่าด้วยชื่อว่างของ *บัญชีผู้ใช้* ต่างเรื่องกัน) **แก้ที่เสนอ:** วิธีเดียวกับ BUG-55 ขนาด: เล็ก **เทสต์:** `test_bug56_a_project_named_with_only_spaces_is_refused`

## BUG-57 — เลขอ้างอิง `[n]` ในข้อความ alt ของรูป ทำให้ tag `<img>` เสีย

| | |
|---|---|
| ระดับ | ต่ำ |
| ผู้ใช้เห็นไหม | ใช่ (ข้อความแปลกๆ ต่อท้ายรูป) ต้องมีรูป markdown ที่มี `[n]` ใน alt (โมเดลเขียนได้) |
| หลักฐาน | `html.render` และ export interactive (live): `<img src="https://example.org/a.png" alt="t <a class="cite" href="#src-1"><span class="b">[</span>1...` หน้ารายงานในเว็บแสดง `t <button type=` เป็นข้อความต่อจากรูป (`shots/t7-xss-report.png`) ไม่ทำให้ script รัน (ตรวจแล้ว ไม่มี attribute `onerror` เกิดขึ้น) |

`CITATION.sub` ทำงานหลัง markdown ถูก render เป็น HTML จึงแทน `[1]` ที่อยู่ในค่า attribute ด้วย `<a class="cite" ...>` ที่มีเครื่องหมายคำพูด attribute `alt` จึงจบกลางคัน (เว็บแอปเกิดแบบเดียวกันด้วย `<button>`) **แก้ที่เสนอ:** ทำเลขอ้างอิงเป็น rule ของ markdown-it ก่อน render แทน regex หลัง render ขนาด: เล็ก **เทสต์:** `test_bug57_a_citation_in_an_images_alt_text_does_not_break_the_tag`

## ส่วนที่เจ็ด (Task 8): ข้อที่ต้องใช้เบราว์เซอร์

ฐานที่ตรวจ HEAD `35daeec` บน stack audit (:8098) ด้วย Playwright (Edge) ดัก route ด้วย `page.route` (ไม่ยิงโมเดล ไม่เสียเงิน) ไม่มีเทสต์ pytest เพราะโปรเจกต์ไม่มี test framework ฝั่งเว็บ และเทสต์ถาวรต้องไม่ผูกกับเบราว์เซอร์ จึงลงเป็นบั๊กที่มีขั้นตอนทำซ้ำเท่านั้น ข้อที่เกี่ยวกับการแสดงผลล้วนๆ อยู่ใน `ux.md`

## BUG-58 — หน้าตั้งรหัสผ่านบอกว่า "ลิงก์หมดอายุหรือถูกใช้แล้ว" เมื่อแค่เครือข่ายล้ม (ส่วน B ของ BUG-35 / e-S10)

| | |
|---|---|
| ระดับ | ต่ำ (ผู้ใช้เชื่อว่าลิงก์เสีย ขอลิงก์ใหม่จากผู้ดูแลทั้งที่ลิงก์ยังใช้ได้) |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `web/src/pages/auth.tsx` ราว :497-516 ใช้ `!link.data?.valid` ตัดสินโดยไม่ดู `link.isError` · ทำซ้ำ: เปิดลิงก์ตั้งรหัสผ่านที่ยังใช้ได้ แล้วดัก `POST /api/auth/password-link` ให้ล้ม (`route.abort()`) ผล: จอหมุนว่างราว 3-6 วินาที (React Query ลองใหม่ 2 ครั้ง) แล้วขึ้น "ลิงก์นี้หมดอายุหรือถูกใช้ไปแล้ว ขอลิงก์ใหม่จากผู้ดูแลระบบ" · ภาพ `img/ux-21-setpassword-network.webp` |

ส่วนที่สองของข้อสงสัยเดิม (หลังตั้งรหัสผ่านสำเร็จ แล้ว query ถูกดึงซ้ำจนขึ้นข้อความเสียก่อนเปลี่ยนหน้า): **ทำซ้ำไม่ได้** ดักการเปลี่ยนแปลง DOM ด้วย `MutationObserver` ตั้งแต่กดบันทึกจนเปลี่ยนไปหน้าแรก ไม่พบข้อความ "ไม่ถูกต้อง/หมดอายุ" แม้แต่เฟรมเดียว (ลองแล้ว 1 รอบ ลิงก์ใหม่ที่ผู้ดูแลออกให้)

**วิธีแก้ที่เสนอ:** แยกกรณี `link.isError` (แสดง "เชื่อมต่อไม่ได้ ลองอีกครั้ง" พร้อมปุ่มลองใหม่) ออกจาก `valid === false` · ขนาด: เล็กมาก

## BUG-59 — หน้า login บอก "อีเมลหรือรหัสผ่านไม่ถูกต้อง" กับทุกความผิดพลาด รวม 503, 429 และเครือข่ายล้ม (e-S12)

| | |
|---|---|
| ระดับ | ต่ำ |
| ผู้ใช้เห็นไหม | ใช่ |
| หลักฐาน | `web/src/pages/auth.tsx` ราว :478-482 แสดง `t("login.failed")` เมื่อ `login.error` มีค่า ไม่ดูชนิดข้อผิดพลาด · ทำซ้ำด้วย Playwright ดัก `**/api/auth/login` ให้ตอบ 503, `abort()`, 429 (`too_many_attempts`) และ 401: ทั้งสี่กรณีได้ข้อความเดียวกันคือ "อีเมลหรือรหัสผ่านไม่ถูกต้อง" · ภาพ `img/ux-14-login-503.webp` (กรณี 503) |

ผลต่อผู้ใช้: ถูกล็อกชั่วคราวเพราะลองผิดบ่อย (429) ก็ยังเห็นว่ารหัสผ่านผิด จึงลองซ้ำหรือขอรีเซ็ต ซึ่งออกจากระบบทุกเครื่อง

**วิธีแก้ที่เสนอ:** แยกตาม `ApiError.status`: 401 ใช้ข้อความเดิม, 429 บอกให้รอสักครู่, อื่นๆ และเครือข่ายล้มบอกว่า "ติดต่อระบบไม่ได้" · ขนาด: เล็ก

---

## ข้อจำกัดของเทสต์ที่ผู้ตรวจทานบันทึกไว้ (รวมใน Task 12)

ไม่เปลี่ยนผลของข้อใด แต่คนที่แก้ควรรู้ก่อนถอด mark:

- **BUG-21:** เทสต์ใช้ `monkeypatch.undo()` กลางเทสต์ (ควรใช้ `monkeypatch.context()`) และการแก้ที่เลิก `ignore_errors` อาจทำให้เทสต์ล้มด้วย `PermissionError` แทน `AssertionError` ซึ่ง `raises=AssertionError` จะรายงานเป็นล้มจริง ไม่ใช่ xfail ที่ผ่าน ให้ปรับเทสต์พร้อมการแก้
- **BUG-02:** การเตรียมข้อมูลอาศัย race ของ BUG-03 (Run ที่ queued ใน Session ที่ถูกลบ) ถ้าแก้ BUG-03 ก่อน ให้สร้างแถวนั้นตรงในฐานข้อมูลแทน
- **BUG-09:** มีโอกาสเล็กที่ลำดับการทำงานของ thread ทำให้ไม่เกิด deadlock ในรอบนั้น (ผู้ตรวจทานรัน 3 ครั้ง xfail ทั้ง 3) strict xfail จะฟ้องเป็น XPASS ถ้าเกิด ให้รันซ้ำก่อนสรุปว่าแก้แล้ว
- **BUG-54:** หนึ่งเทสต์ยิงหกคำขอ (หลายฟิลด์) เมื่อแก้บางฟิลด์ เทสต์ยังล้มจนกว่าจะครบทุกฟิลด์
- **BUG-55:** เทสต์ขอ fixture `db` ที่ไม่ได้ใช้ (ไม่มีผลต่อผล)
- **เวลา:** เทสต์ของการตรวจนี้เพิ่มเวลาชุดเต็มราว 1.5 นาที (ส่วนใหญ่คือ Worker จริงกับ fake engine)
- **BUG-48:** เป็นเทสต์เดิมของโปรเจกต์ที่ไม่เสถียร ไม่ใช่เทสต์ของการตรวจ
