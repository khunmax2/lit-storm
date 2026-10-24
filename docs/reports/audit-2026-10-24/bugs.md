# บั๊กที่ทำซ้ำได้ใน Worker, โควตา และถังขยะ (Task 3a ของการตรวจทั้งระบบ 2026-10-24)

ฐานที่ตรวจ: branch `audit/2026-10-24` (HEAD `46ae8e0`) · ตรวจด้วย pytest กับแอปจริงบน Postgres (testcontainers) และ process ลูกของ fake engine ไม่เรียกโมเดลหรือบริการค้นหาจริง ไม่แตะ stack Docker ใดๆ

รายงานนี้เป็นส่วนของ Task 3 (อ่านโค้ดส่วนเสี่ยง) เฉพาะ 3 กลุ่มจาก 6 กลุ่ม: (a) `worker/` กับ `runner/` · (b) โควตา, limits และการเริ่ม/ลองใหม่/ยกเลิก Run · (c) ถังขยะและการลบถาวร กลุ่ม (d) (e) (f) อยู่ใน Task 3b

ผู้อ่านโค้ดส่งข้อสงสัยมา 30 ข้อ (a 9, b 10, c 11) แต่ละข้อถูกลองทำซ้ำด้วยตัวเองตามขั้นตอนของ `superpowers:systematic-debugging`: อ่านโค้ดที่อ้าง ตั้งสมมติฐาน แล้วพยายามให้เกิดจริง ผลคือ **23 รหัสบั๊ก** (คลุม 23 ข้อสงสัยจากผู้อ่าน; ข้อที่เป็นรากเดียวกันถูกรวมเป็นรหัสเดียว และบางรหัสมีหลายเทสต์), **4 ข้อสงสัย** ที่ทำซ้ำไม่ได้, **3 ข้อที่ตัดทิ้ง**

**เกณฑ์ระดับ** ตามสเปก: **วิกฤต** ข้อมูลรั่วหรือระบบใช้ไม่ได้ · **สูง** กระทบผู้ใช้จริงบ่อย หรือต้องมีสิทธิ์บางอย่าง · **กลาง** · **ต่ำ** ไม่มีข้อใดในชุดนี้เป็น **วิกฤต** เพราะทุกข้อต้องมีบัญชีที่ login แล้ว หรือต้องมีความผิดปกติของระบบเกิดก่อน

**หลักฐาน:** ทุกบั๊กมีเทสต์ใน `server/tests/test_audit_findings.py` ที่ยืนยันพฤติกรรมที่ **ถูกต้อง** เป็น `xfail(strict=True, raises=AssertionError, reason="BUG-xx")` จึงล้มวันนี้และจะผ่านเมื่อแก้ (strict จะฟ้องให้ถอด mark) ทุกเทสต์ถูกรันครั้งหนึ่งด้วย `--runxfail` เพื่อยืนยันว่าล้มที่ assertion ของตัวเอง ไม่ใช่ error อื่น: `cd server && uv run pytest tests/test_audit_findings.py -k test_bug --runxfail`

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

---

## สงสัย (ทำซ้ำไม่ได้)

| ข้อ | สิ่งที่ลอง | สิ่งที่ควรทำใน task ที่ลองจริง |
|---|---|---|
| a-S6 (kill ตาม deadline/ยกเลิก ทับ outcome ที่ child เพิ่งเขียน และ usage ของ stage ที่ถูกฆ่าหาย) | อ่านโค้ด: child เขียน `outcome.json` แล้วเรียก `os._exit(0)` ทันที (`child.py:main`) หน้าต่างระหว่าง `proc.poll()` กับ `proc.kill()` เหลือไม่กี่มิลลิวินาที ไม่มีทางคุมจังหวะนั้นใน pytest โดยไม่จำลองจนเทสต์ไม่แสดงของจริง เทสต์ที่มีอยู่ (`test_cancel_that_loses_to_completion_keeps_the_report`) ครอบเฉพาะกรณียกเลิก ส่วน usage ของ stage ที่ถูกฆ่าไม่ถูกบันทึกเป็นลักษณะของ engine (รายงาน usage ทีละ stage) | รัน Deep Run จริงด้วย deadline สั้นแล้วเทียบ `cost_usd` กับยอดที่ OpenRouter เรียกเก็บ (ภายในเพดาน $2.50 ของ Task จริง) |
| a-S8 (Windows: `_exit_when_orphaned` ออกทันทีเมื่อเปิด handle ของ parent ไม่ได้) | อ่านโค้ด `child.py:114-126`: ถ้า `OpenProcess` คืน 0 โค้ดตกไป `os._exit(4)` จริง แต่ถ้า parent ตายไปแล้ว (pid ไม่มี) การออกคือคำตอบที่ถูก ส่วนกรณีที่ผิด (parent ยังอยู่แต่ถูกปฏิเสธสิทธิ์) หา trigger ไม่ได้: process ลูกกับ parent เป็นผู้ใช้เดียวกัน `SYNCHRONIZE` เปิดได้เสมอ และ host จริง (Linux/Docker) ไม่ใช้เส้นทางนี้ | ไม่ต้องทำในรอบนี้; ถ้าจะ harden ให้เช็ก `GetLastError()` แยก "ไม่มี process" (87) ออกจาก "ถูกปฏิเสธ" (5) |
| a-S9 (spare ที่ถูก kill ไม่ถูก wait / spare ที่ค้างตอน import ทำให้ Run รอ) | ไม่ได้ลอง: ซอมบี้เกิดเฉพาะ Linux (เครื่อง dev เป็น Windows ไม่มี `ps`) และ spare ที่ค้างต้องการ import ที่ติดเครือข่าย (LiteLLM โหลดตารางราคา) ซึ่งจำลองใน pytest ไม่ได้ซื่อตรง | บน stack ทดสอบ: `docker exec` ไปฆ่า spare ของ Worker ทันทีหลัง claim แล้วดู `ps` หา `<defunct>`; และตั้ง egress ปิดแล้วนับเวลาจนมี event แรกของ Run แรกหลังเริ่ม Worker |
| c-S11 (restore แข่งกับ purge ที่ขอบ 30 วัน) | ไม่ได้ลอง: ต้องสอดการ commit ของ restore ระหว่าง `select(Run)` กับลูปลบใน `purge` ซึ่งต้อง monkeypatch กลางฟังก์ชันจนไม่ใช่สถานการณ์จริง หน้าต่างกว้างไม่กี่วินาทีต่อรายการ และ API กับ Worker ใช้นาฬิกาเดียวกัน | ไม่คุ้มทดสอบสด; ถ้าแก้ BUG-21/17 ใน `purge` อยู่แล้ว ให้ล็อกแถวด้วย `FOR UPDATE SKIP LOCKED` ตอนเลือก |

## ตัดทิ้ง

| ข้อ | เหตุผล |
|---|---|
| b-S9 (Turn ถูกส่งก่อน Run ของทุกคนและไม่หักโควตา อาจทำให้คิวอดอยาก) | เป็นการออกแบบที่ระบุไว้: คอมเมนต์ที่ `worker/queue.py:94-95` ("A Discussion's Turn first: its owner is waiting on the page") และ `docs/web-app-design.md` (Turn เป็นงานในคิวเดียวกับ Run อยู่หน้าคิว) ผู้อ่านเองรายงานเป็น "ช่องว่างด้านความเป็นธรรม" ไม่ใช่บั๊กในการนับ และ Turn ถูกจำกัดด้วย `max_queued` และ 1 Turn ต่อ Discussion ไม่มีหลักฐานการอดอยากจริง เรื่องนี้เป็นเรื่องนโยบายให้เจ้าของตัดสินถ้าต้องการ |
| b-S10 (เดือนโควตาถูกตรึงตอนส่ง Run ที่ข้ามเดือนจึงไม่นับกับเดือนใหม่) | เป็นกติกาที่เขียนไว้ตรงๆ: `docs/web-app-design.md:206-207` ("งานที่เข้าคิวหรือกำลังทำข้ามเดือนยังนับกับเดือนที่จองไว้ตั้งแต่แรก") และ docstring ของ `quota.py` ส่วนความคลาดเคลื่อนที่ผู้อ่านเสนออีกข้อ (`new_run` เรียก `quota_month()` ซ้ำหลัง `check_submit`) ต่างกันได้เฉพาะเสี้ยววินาทีตอนเที่ยงคืนพอดี ผลกระทบเป็นศูนย์ในทางปฏิบัติ |
| c-S6 (Run ที่ถูกลบก่อนถูก purge ก่อน Session แม่ที่ถูกลบทีหลัง) | ไม่ใช่บั๊ก: ผู้ใช้เป็นคนลบ Run นั้นเองเมื่อ 30 วันก่อน การนับ 30 วันของมันเองหมดก่อนเป็นผลที่ถูกต้องตามกติกา "นับจากวันที่ลบ"; ส่วน "การกู้คืนรายการย่อยของ parent" เอกสารเองระบุว่ายังไม่ได้กำหนด (`docs/web-app-design.md:262`: "รายละเอียดการกู้คืนรายการย่อย...ต้องกำหนดเพิ่มเติม") จึงเป็นช่องว่างของข้อกำหนด ไม่ใช่ความประพฤติผิด ควรให้เจ้าของตัดสินกติกาก่อน |
