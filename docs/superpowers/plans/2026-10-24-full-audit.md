# แผนลงมือ: ตรวจ DeepLit ทั้งระบบ

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ได้รายงานสิ่งที่เจอในทุกด้าน (ความปลอดภัย, บั๊ก, UX/UI, ความทนทาน, คุณภาพโค้ด) พร้อมหลักฐาน ให้เจ้าของเลือกว่าจะแก้ข้อไหน รอบนี้ยังไม่แก้อะไรที่ผู้ใช้เห็น

**Architecture:**
- ตรวจบน branch `audit/2026-10-24` ซึ่งรวม `main`, `feat/system-monitor` และ `feat/login-redesign`
- รันบน stack แยกที่ทิ้งได้ `litstorm-audit` (:8096)
- ข้อที่ยืนยันแล้วมีเทสต์ `xfail(strict=True)` ผูกกับรหัสข้อ เพื่อให้รอบแก้เปลี่ยนเทสต์นั้นเป็นผ่าน
- สิ่งที่เก็บถาวรใน repo: เทสต์ตารางสิทธิ์, เครื่องมือตรวจใน `server/tests/audit/` และรายงาน

**Tech Stack:** FastAPI, Postgres, worker, React/Vite, Docker Compose, pytest (testcontainers), Playwright (Edge), axe-core

**Spec:** [docs/superpowers/specs/2026-10-24-full-audit-design.md](../specs/2026-10-24-full-audit-design.md)

## Global Constraints

- ห้ามแก้สิ่งที่ผู้ใช้เห็นก่อนเจ้าของอนุมัติ งานรอบนี้จบที่รายงาน
- ค่า OpenRouter รวม (DeepLit + MRA) ไม่เกิน **$3** และหยุดลองจริงเมื่อถึง **$2.50**
- ทำในเครื่องเท่านั้น: ไม่แตะ 203, GitLab, stack `litstorm` ที่ :8095 และ stack ของ Agenta ห้าม restart Docker Desktop
- อ่าน key จาก `stack/.env` และ `../MedicalReviewerAgent/.env` ผ่านไฟล์หรือ stdin เท่านั้น ห้ามพิมพ์ key ออกจอ ใส่ใน command line หรือติดในภาพหน้าจอ
- บัญชีทดสอบใช้ `*@test.local` และรหัสผ่านทดสอบที่สร้างใหม่ ลบทิ้งเมื่อเสร็จ
- ห้าม commit `stack/secrets/`, `*.env`, `host.env`
- commit ลงท้ายด้วย `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>` และไม่ push
- ทุกข้อในรายงานต้องมีหลักฐาน ข้อที่ยืนยันไม่ได้ให้ทิ้ง หรือลงเป็น "สงสัย" แยกท้ายรายงาน
- ระดับ: **วิกฤต** / **สูง** / **กลาง** / **ต่ำ** ตามนิยามในสเปก

## Review Focus

1. **image tag ชนกัน:** stack แยกใช้ tag เดียวกับ stack หลัก (`litstorm/server:dev`, `litstorm/web:mirror`) การ build ของ audit จะทับ tag ของ stack หลัก → Task 0 ตรวจว่า container ของ `litstorm` ยังรัน image เดิม และจดไว้ในรายงานว่าต้อง rebuild stack หลักก่อนใช้ต่อ
2. **ความลับหลุดในหลักฐาน:** ภาพหน้าจอหรือข้อความในรายงานมี key, ลิงก์ตั้งรหัสผ่าน หรือ token → Task 12 สแกนไฟล์ทั้งหมดก่อน commit
3. **งานค้างจนใช้เงินเกิน:** Run ที่ค้างอยู่ยังเรียกโมเดลต่อ → Task 5 เช็กยอดใช้หลังทุก Run และยกเลิกงานที่ค้างก่อนรันงานถัดไป
4. **ข้อที่ไม่จริง:** ผู้ช่วยตรวจรายงานสิ่งที่ไม่ได้เกิดจริง → Task 3 ต้องทำซ้ำให้เห็นทุกข้อก่อนลงรายงาน
5. **ของทดสอบค้าง:** บัญชีหรือ stack ทดสอบยังอยู่หลังจบงาน → Task 12 ตรวจว่า `docker compose -p litstorm-audit ps` ว่าง และไม่มี `*@test.local` ใน DB ของ :8095

---

### Task 0: ฐานสำหรับตรวจ

**Files:**
- Create: branch `audit/2026-10-24`
- Create: `server/tests/audit/spend.py`
- Commit: spec และแผนนี้

**Interfaces:**
- Produces:
  - `python server/tests/audit/spend.py <env-file>...` พิมพ์ JSON `{"keys": [{"id": "<sha256 8 ตัวแรก>", "usage_usd": float, "limit_usd": float|null}], "total_usd": float}`
    - key ซ้ำนับครั้งเดียว และไม่พิมพ์ key
  - stack `litstorm-audit` ที่ `http://127.0.0.1:8096/litstorm`

- [ ] **Step 1:** `git checkout -b audit/2026-10-24 main` แล้ว merge `feat/system-monitor` และ `feat/login-redesign` (`--no-ff`) ต้องไม่มี conflict ยกเว้น `web/src/i18n.tsx` ซึ่งให้เก็บทั้งสองฝั่ง
- [ ] **Step 2:** `uv run pytest -q` ใน `server/` ต้องผ่าน (คาดว่า 406 passed บวกกับเทสต์จาก login) และ `npm run build` ใน `web/` ต้องผ่าน จดตัวเลขลงบันทึก
- [ ] **Step 3: เขียน `spend.py`**
  - เรียก `GET https://openrouter.ai/api/v1/key` ด้วย header `Authorization: Bearer <key>` โดยอ่าน key จากบรรทัด `OPENROUTER_API_KEY=` ของแต่ละไฟล์
  - ใช้ `urllib` ของ standard library และไม่พิมพ์ key
- [ ] **Step 4:** `python server/tests/audit/spend.py stack/.env ../MedicalReviewerAgent/.env` ต้องได้ JSON ที่มี `total_usd` จดเป็นยอดเริ่มต้น
- [ ] **Step 5: เปิด stack แยก**
  - `cd stack && LITSTORM_PORT=8096 docker compose -p litstorm-audit -f compose.yml -f compose.mirror.yml up -d --build`
  - `curl http://127.0.0.1:8096/litstorm/api/health` ต้องได้ 200
  - `docker inspect litstorm-api-1 --format '{{.Image}}'` ต้องเท่ากับค่าก่อน build (Review Focus 1)
- [ ] **Step 6:** commit spec, plan และ `spend.py`

### Task 1: ตารางสิทธิ์ของทุก endpoint (เทสต์ถาวร)

**Files:**
- Create: `server/tests/test_authz_matrix.py`
- Create: `docs/reports/audit-2026-10-24/authz-matrix.md` (ตารางที่ร่าง และช่องที่ต้องให้เจ้าของตัดสิน)

**Interfaces:**
- Produces:
  - `ACCESS: dict[tuple[str, str], str]` คือ (method, path) → ชั้นสิทธิ์ อย่างใดอย่างหนึ่งใน `"public"`, `"signed_in"`, `"owner"`, `"admin"`, `"token:read"`, `"token:research"`, `"undecided"`
  - Task 12 อ่านจำนวนช่อง `"undecided"` ไปใส่รายงาน

- [ ] **Step 1: ร่างตาราง**
  - ไล่ `create_app().routes` ทั้งหมด (ราว 104 route บวก MCP)
  - ใส่ชั้นสิทธิ์ตาม `docs/CONTEXT.md`, `docs/web-app-design.md`, ADR-0002 และ ADR-0009
  - ช่องที่เอกสารไม่ได้บอก ให้เป็น `"undecided"`
- [ ] **Step 2: เขียน `test_every_route_has_an_access_class`**
  - assert ว่า set ของ route ใน app เท่ากับ key ของ `ACCESS` พอดี
  - route ใหม่ที่ไม่ได้จัดชั้นสิทธิ์จะทำให้เทสต์ล้ม
- [ ] **Step 3: เขียน `test_access_class_holds` (parametrize ทุกช่องที่ไม่ใช่ `undecided`)**
  - ไม่ได้ login → 401 (ยกเว้น `public`)
  - ผู้ใช้ทั่วไปเรียก route ของ `admin` → 403
  - ผู้ใช้อื่นเรียกของ `owner` → 404
  - token ที่ไม่มี scope → 403
  - ส่ง method ที่เปลี่ยนข้อมูลโดยไม่มี CSRF header → 403
  - ใช้ fixture `admin`, `browser`, `make_user` และ fixture สร้าง Project/Session/Run แบบใน `test_monitor.py`
- [ ] **Step 4:** รัน `uv run pytest tests/test_authz_matrix.py -q`
  - ช่องที่ล้ม = ข้อที่เจอ → จด `SEC-xx` แล้วทำเป็น `xfail(strict=True, reason="SEC-xx")`
  - เทสต์ต้องผ่านทั้งไฟล์ (ทุกข้อที่ล้มถูก xfail ไว้)
- [ ] **Step 5:** commit

### Task 2: ความปลอดภัย

**Files:**
- Create: `server/tests/test_audit_findings.py` (เทสต์ `xfail(strict=True, reason="<รหัส>")` ของข้อที่ยืนยันแล้ว)
- Create: `docs/reports/audit-2026-10-24/security.md`

- [ ] **Step 1:** ใช้ skill `security-review` และ `senior-security` ไล่ทุกหัวข้อในสเปกส่วน 1 ทีละหัวข้อ
  - **SSRF:** ทุกช่องที่ใส่ URL ได้ ลองค่าอย่าง `http://169.254.169.254/`, `http://db:5432`, `file://`
  - **XSS:** ใส่ `<img src=x onerror=alert(1)>` ในหัวข้อ, ชื่อโปรเจกต์, ข้อความที่ส่งใน Co-STORM และ markdown ของรายงาน แล้วตรวจ CSP ของหน้า interactive, service page และ observatory
  - **path traversal:** ใน export และ `runs_dir`
  - **การ login:** login ผิดติดกัน 50 ครั้ง ดูว่ามีการจำกัดไหม และตรวจ session fixation
  - **ความลับ:** ค้น key หรือ token ใน log ของ api และ worker ระหว่าง Task 5 และในหน้าสถานะระบบ
  - **header:** ตรวจ security header ที่ edge ด้วย `curl -I`
- [ ] **Step 2: dependency**
  - `npm audit --omit=dev` ใน `web/`
  - `uv run --with pip-audit pip-audit` ใน `server/` ไม่ต้องเพิ่มเข้า project
  - จดเฉพาะช่องโหว่ที่โค้ดเราใช้ถึงจริง
- [ ] **Step 3: container**
  - อ่าน `stack/compose*.yml` และ Dockerfile ตรวจว่ารันเป็น root ไหม พอร์ตเปิดที่ไหน และ secrets อยู่ตรงไหน
  - อ่าน `compose.agenta.yml` ว่า network `agenta-mcp` เห็นอะไร (อ่านอย่างเดียว)
- [ ] **Step 4:** ทุกข้อที่ยืนยันแล้วต้องมีเทสต์ xfail ใน `test_audit_findings.py` หรือขั้นตอนทำซ้ำใน `security.md` ถ้าทำเป็นเทสต์ไม่ได้
  - ข้อระดับวิกฤตแจ้งเจ้าของในแชททันทีที่ยืนยัน
- [ ] **Step 5:** `uv run pytest tests/test_audit_findings.py -q` ต้องผ่าน (ทุกข้อเป็น xfail) แล้ว commit

### Task 3: อ่านโค้ดส่วนเสี่ยง (ผู้ช่วยหลายตัวขนานกัน)

**Files:**
- Modify: `server/tests/test_audit_findings.py`
- Create: `docs/reports/audit-2026-10-24/bugs.md`

- [ ] **Step 1:** ใช้ `superpowers:dispatching-parallel-agents` ส่งผู้ช่วยแบบอ่านอย่างเดียว 6 ตัว แต่ละตัวได้หนึ่งกลุ่ม:
  - (a) `worker/`, `runner/`: lease, cancel, deadline, heartbeat
  - (b) `quota.py`, `limits.py`, `api/research.py`: การจองและคืนโควตา และการข้ามเดือน
  - (c) `trash.py`: purge และการกู้คืน
  - (d) `api/discussions.py`, `discussion*`: Co-STORM Turn
  - (e) `monitor.py`, `outcomes.py`, `api/admin.py` ส่วนบัญชี
  - (f) `api/mcp.py`, `api/tokens.py`, `engines/deep`, `engines/medical`
  - ให้ผู้ช่วยแต่ละตัวส่งกลับ "ข้อที่สงสัย" พร้อม file:line และวิธีทำซ้ำ
- [ ] **Step 2:** ใช้ `superpowers:systematic-debugging` ทำซ้ำทีละข้อด้วยตัวเอง
  - ข้อที่ทำซ้ำได้ → เทสต์ xfail ลง `test_audit_findings.py` และลงรายการใน `bugs.md` เป็น `BUG-xx`
  - ข้อที่ทำซ้ำไม่ได้ → ลงส่วน "สงสัย" (Review Focus 4)
- [ ] **Step 3:** รันเทสต์ทั้งชุดแล้ว commit

### Task 4: ตรวจโค้ดอัตโนมัติ และ migration

**Files:**
- Modify: `docs/reports/audit-2026-10-24/bugs.md`

- [ ] **Step 1:** `uv run --with ruff ruff check src --select F,B,E9` ใน `server/` จดเฉพาะข้อที่เป็นบั๊กจริง (undefined name, unused result, mutable default)
- [ ] **Step 2: migration บน stack แยก**
  - `MSYS_NO_PATHCONV=1 docker exec -w /app/server litstorm-audit-api-1 alembic downgrade base`
  - แล้วตามด้วย `alembic upgrade head`
  - ต้องผ่านครบทุกขั้น จด revision ที่ล้ม (ถ้ามี)
- [ ] **Step 3:** `PROJECT=litstorm-audit bash stack/backup.sh <scratch>` แล้ว restore กลับ ตรวจว่าจำนวนตารางเท่าเดิม (ดู usage ใน `stack/backup.sh` ก่อนว่ารับตัวแปรอะไร)
- [ ] **Step 4:** commit

### Task 5: ลองจริงทุกโหมด (มีค่าใช้จ่าย)

**Files:**
- Create: `server/tests/audit/live_runs.py` (สร้างผู้ดูแลและผู้ใช้ทดสอบ ตั้งค่าโมเดลและบริการค้นหา แล้วสั่ง Run ผ่าน API ของ :8096)
- Create: `docs/reports/audit-2026-10-24/live.md`

**Interfaces:**
- Consumes: `spend.py` (Task 0)

- [ ] **Step 1:** ตั้งค่าครั้งแรกผ่านหน้าเว็บด้วย Playwright ใช้รหัสตั้งต้นจาก `stack/secrets/bootstrap_code` และรหัสผ่านทดสอบที่สร้างใหม่
  - ตั้งโมเดล `google/gemini-3.5-flash-lite` เป็นค่าเริ่มต้น และ SearXNG
  - ตั้ง Medical Review ชี้ไปที่ MRA ในเครื่อง (`http://host.docker.internal:8088`) ด้วย key ทดสอบของ MRA ที่มีอยู่
- [ ] **Step 2: รันทีละโหมดที่ความลึก "เร็ว"**
  - ลำดับ: STORM (ไทย), STORM (อังกฤษ), Deep, Agent, Co-STORM (เปิด + 2 Turn), Medical (ถามเร็ว), Medical (รีวิวเต็ม)
  - หลังแต่ละ Run ให้รัน `spend.py` ถ้า `total_usd - ยอดเริ่มต้น ≥ 2.50` ให้หยุด (Review Focus 3)
- [ ] **Step 3:** export ทุกรูปแบบ (html, md, pdf, interactive, observatory) จาก Run ที่สำเร็จ แล้วเปิดดูว่าไม่ว่าง และไม่มี error
- [ ] **Step 4:** สร้าง token ของ MCP แล้วเรียกผ่าน `/api/mcp` ให้ครบทุก tool ของเส้น research และ medical
- [ ] **Step 5:** ลงทุกความผิดปกติใน `live.md` (บั๊กเป็น `BUG-xx`, UX เป็น `UX-xx`) พร้อมยอดใช้จ่ายสะสม แล้ว commit

### Task 6: จำลองความล้มเหลว

**Files:**
- Create: `server/tests/audit/stub_provider.py` (HTTP server ตอบ 429 / 401 / 500 / ช้า ตามแบบที่เลือก บนพอร์ตของเครื่อง)
- Modify: `docs/reports/audit-2026-10-24/live.md`

- [ ] **Step 1:** ทำแต่ละกรณีบน stack แยก แล้วจดสามอย่าง: ผู้ใช้เห็นอะไร, หน้าสถานะระบบเห็นอะไร และโควตาคืนไหม
  - **429:** โมเดลแบบ openai-compatible ที่ `api_base` ชี้ไปที่ stub ซึ่งตอบ 429
  - **key ผิด:** stub ตอบ 401
  - **worker ตาย:** `docker stop litstorm-audit-worker-1` ระหว่าง Run แล้ว start กลับ
  - **MRA ติดต่อไม่ได้:** ชี้ Medical ไปพอร์ตที่ไม่มีอะไรฟัง ห้ามหยุด MRA จริง
  - **บริการค้นหาไม่ตอบ:** ชี้ SearXNG ไปที่ stub ที่ตอบช้าเกิน timeout
- [ ] **Step 2:** ความคาดหวัง: เหตุผลเป็น `retries_exhausted`, `bad_configuration`, `interrupted`, `service_unavailable` และ `empty_report` หรือ `retries_exhausted` ตามลำดับ, หน้าสถานะระบบขึ้น Issue ที่ตรงกัน และ `quota_refunded` เป็น true ข้อที่ไม่ตรง → `BUG-xx` พร้อมเทสต์ xfail ถ้าทำได้
- [ ] **Step 3:** commit

### Task 7: ขีดจำกัดและข้อมูลแปลกๆ

**Files:**
- Modify: `server/tests/test_audit_findings.py`, `docs/reports/audit-2026-10-24/bugs.md`

- [ ] **Step 1:** ลองผ่าน API บน stack แยก
  - สั่งงานพร้อมกันเกิน `max_concurrent_total`
  - สั่งจนคิวเต็ม (`queue_full`)
  - หัวข้อยาว 10,000 ตัวอักษร
  - หัวข้อที่มีไทย อังกฤษ emoji และอักขระ RTL ปนกัน
  - หัวข้อว่างหรือมีแต่ช่องว่าง
  - ชื่อโปรเจกต์ซ้ำ
- [ ] **Step 2:** ข้อที่ระบบรับไว้แต่พังทีหลัง หรือตอบ 500 → `BUG-xx` พร้อมเทสต์ xfail แล้ว commit

### Task 8: ถ่ายภาพหน้าจอทุกหน้า และตรวจ UX/UI

**Files:**
- Create: `server/tests/audit/screens.py` (ต่อยอดจาก `e2e_screens.py`: รับ base URL, ขนาดจอ, ธีม และภาษา ถ่ายทุกหน้าในทุกสถานะที่มี)
- Create: `docs/reports/audit-2026-10-24/ux.md`

- [ ] **Step 1:** ถ่ายทุกหน้าจากข้อมูลที่ Task 5–7 สร้างไว้
  - ขนาดจอ 1440×900, 1024×768 และ 390×844
  - ธีมสว่างและมืด, ภาษาไทยและอังกฤษ
  - เก็บภาพไว้ที่ scratch ไม่ใส่ใน repo
- [ ] **Step 2: ตรวจ accessibility ด้วย axe-core**
  - ติดตั้ง axe-core ไว้ใน scratch (`npm i axe-core` ในโฟลเดอร์ scratch) แล้ว inject ด้วย `page.add_script_tag(path=...)`
  - รัน `axe.run()` ทุกหน้า และจดเฉพาะ violation ระดับ serious และ critical
- [ ] **Step 3: ตรวจคำแปล**
  - เขียนเทสต์ `test_every_key_has_both_languages` ใน `server/tests/audit/` (หรือเป็น script) เทียบ key ของ en กับ th ใน `web/src/i18n.tsx`
  - ค้นข้อความที่ hardcode ใน `.tsx` ที่ไม่ผ่าน `t()`
- [ ] **Step 4:** ใช้ skill `ui-ux-pro-max` ไล่ภาพทุกหน้าตาม heuristic ของ Nielsen และ WCAG 2.2 AA
  - ลงเป็น `UX-xx` พร้อมภาพหลักฐาน 1 ภาพต่อข้อ
  - ภาพที่อ้างถึงคัดลอกลง `docs/reports/audit-2026-10-24/img/` เป็น WebP กว้างไม่เกิน 1200px
- [ ] **Step 5:** commit

### Task 9: ไล่ flow ที่ผู้ใช้ทำจริง

**Files:**
- Create: `server/tests/audit/flows.py`
- Modify: `docs/reports/audit-2026-10-24/ux.md`

- [ ] **Step 1:** ใช้ Playwright บน stack แยก ไล่ทีละ flow:
  - เชิญผู้ใช้ → ผู้ใช้ตั้งรหัสผ่านจากลิงก์ → login ผิด 3 ครั้งแล้วถูก
  - สร้างโปรเจกต์ → รันงาน → อ่านรายงาน → คลิกแหล่งอ้างอิง
  - Co-STORM: เปิด → พิมพ์ → ให้คุยเอง → สรุปรายงาน
  - export → ย้ายเข้าโปรเจกต์ → ลง/กู้จากถังขยะ
  - ผู้ดูแล: ตั้งค่าทุกหน้า → หน้าสถานะระบบ → รับทราบ → สร้าง token ของ MCP
- [ ] **Step 2:** จดจุดที่ต้องคลิกเกินจำเป็น, ไม่มี feedback, ข้อความไม่ชัด, ทางตัน หรือกดย้อนกลับแล้วข้อมูลหาย เป็น `UX-xx` แล้ว commit

### Task 10: การดูแลระบบ

**Files:**
- Create: `docs/reports/audit-2026-10-24/ops.md`

- [ ] **Step 1:** เทียบ `compose.host.yml` และ `docs/deploy/HOST-203.md` กับ stack ในเครื่อง ในเรื่อง health check, log rotation, restart policy, backup cron และ retention
- [ ] **Step 2:** ลง `OPS-xx` แล้ว commit

### Task 11: คุณภาพโค้ด

**Files:**
- Create: `docs/reports/audit-2026-10-24/code.md`

- [ ] **Step 1:** `uv run --with vulture vulture src --min-confidence 80` ใน `server/` ค้น TODO และ FIXME ค้นเอกสารที่อ้าง function หรือไฟล์ที่ไม่มีแล้ว และค้น key ใน i18n ที่ไม่มีใครใช้
- [ ] **Step 2:** ลง `CODE-xx` (ระดับต่ำทั้งหมด) แล้ว commit

### Task 12: รวมรายงาน เก็บกวาด และส่งมอบ

**Files:**
- Create: `docs/reports/2026-10-24-full-audit.md`

**Interfaces:**
- Consumes: ไฟล์ใน `docs/reports/audit-2026-10-24/*.md`, จำนวนช่อง `undecided` จาก Task 1 และ `spend.py`

- [ ] **Step 1: เขียนรายงานรวม**
  - สรุป 10 ข้อสำคัญ
  - ตารางทุกข้อ: รหัส, ระดับ, หลักฐาน, ผู้ใช้เห็นไหม และวิธีแก้พร้อมขนาดงาน
  - ส่วน "ต้องให้เจ้าของตัดสิน" (ช่อง undecided และข้อที่เป็นเรื่องนโยบาย)
  - ส่วน "สงสัย" และส่วนข้อเล็ก
  - ยอดใช้จ่ายจริง
- [ ] **Step 2:** สแกนทุกไฟล์ที่จะ commit ด้วย regex `sk-or-|sk-[A-Za-z0-9]{20,}|#[A-Za-z0-9_-]{30,}` และค่า `OPENROUTER_API_KEY` ต้องไม่เจอ (Review Focus 2)
- [ ] **Step 3: เก็บกวาด**
  - `docker compose -p litstorm-audit down -v`
  - ลบ image tag ที่ทับไว้ หรือจดในรายงานว่าต้อง rebuild stack หลัก
  - ตรวจว่า DB ของ :8095 ไม่มี `*@test.local` (Review Focus 5)
- [ ] **Step 4:** `uv run pytest -q` ต้องผ่าน (ข้อที่เจอเป็น xfail) แล้ว commit
- [ ] **Step 5:** ส่งสรุปให้เจ้าของในแชท แล้ว **หยุดรอเจ้าของเลือก** ว่าจะแก้ข้อไหน
  - รอบแก้จะทำแผนแยกตามข้อที่เลือก
  - แต่ละข้อแก้แบบ TDD: เปลี่ยน xfail เป็นผ่าน
