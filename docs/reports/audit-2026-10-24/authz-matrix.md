# ตารางสิทธิ์ของทุก endpoint

การตรวจ DeepLit ทั้งระบบ 2026-10-24 งานที่ 1 ([สเปก](../../superpowers/specs/2026-10-24-full-audit-design.md)) · เทสต์ถาวร `server/tests/test_authz_matrix.py` · ตรวจบน branch `audit/2026-10-24`

## สรุป

- **ไม่พบข้อระดับวิกฤต**
  - ผู้ใช้อ่าน แก้ หรือลบของผู้อื่นไม่ได้ทุก route ทั้งทาง path และทาง body
  - ผู้ดูแลอ่านงานวิจัยของบุคคลไม่ได้ และหน้าของผู้ดูแลไม่มีหัวข้อวิจัยของใคร
  - ไม่มี route ของผู้ดูแลที่เรียกได้โดยไม่ login หรือด้วย token ของ MCP
- **ข้อที่เจอ 1 ข้อ:** SEC-01 ระดับต่ำ (token ของบัญชีที่ถูกปิดได้ 401 แทน 403 ตาม ADR-0009)
- **ต้องให้เจ้าของตัดสิน 10 ช่อง** รวมเป็น 3 คำถาม (Q1–Q3 ด้านล่าง) และมีคำถามเพิ่มเติมอีก 1 ข้อที่ไม่ใช่ช่องในตาราง
- **ขนาดของตาราง:** 142 ช่อง
  - route ของ HTTP 102 คู่ (method, path)
    - ใน `/api` 98 คู่: route ของ API 93 คู่ และประตูของ MCP 5 เส้น
    - หน้าของ FastAPI นอก `/api` 4 คู่
  - tool ของ MCP 40 ตัว (8 ตัว × 5 เส้น)
- **จำนวนช่องตามชั้น:**

| ชั้น | route ของ HTTP | tool ของ MCP | รวม |
|---|---|---|---|
| public | 7 | – | 7 |
| signed_in | 16 | – | 16 |
| owner | 26 | – | 26 |
| admin | 43 | – | 43 |
| token:read | 5 (ประตู) | 25 | 30 |
| token:research | – | 10 | 10 |
| undecided | 5 | 5 | 10 |

- **ผลเทสต์:** `uv run pytest tests/test_authz_matrix.py -q` ได้ 484 passed, 5 xfailed ในราว 25 วินาที
  - เป็นการตรวจตามชั้น 485 ข้อ ผ่าน 480 ข้อ อีก 5 ข้อเป็น xfail ของ SEC-01
  - บวกเทสต์ว่าทุก endpoint มีชั้น 1 ข้อ และเทสต์ Project ของผู้อื่นใน body อีก 3 ข้อ

## ชั้นสิทธิ์และที่มา

ชั้นของแต่ละช่องมาจากเอกสาร ไม่ได้มาจากสิ่งที่โค้ดทำอยู่ ช่องที่เอกสารไม่ได้บอกเป็น `undecided` และไม่ใส่ในเทสต์ เพื่อไม่ให้พฤติกรรมของโค้ดตอนนี้ถูกล็อกว่าถูกต้อง

| ชั้น | ใครเรียกได้ | ที่มา |
|---|---|---|
| `public` | ทุกคน ไม่ต้อง login | ตั้งค่าครั้งแรกด้วยรหัสตั้งต้น, ลิงก์ตั้งรหัสผ่าน ([web-app-design](../../web-app-design.md) 2026-09-23); health check ([HOST-203](../../deploy/HOST-203.md)); ลิงก์ export เป็นตัวให้สิทธิ์เอง ([ADR-0009](../../adr/0009-mcp-server.md) ข้อ 7) |
| `signed_in` | ผู้ใช้ที่ login แล้วทุกคน | "ผู้ใช้ต้องล็อกอินเพื่อเข้าใช้งานเว็บ" (2026-09-23); ทุกคำขอที่แก้ข้อมูลต้องมี CSRF header ([ADR-0002](../../adr/0002-drop-supabase-own-auth.md)) |
| `owner` | เจ้าของ Project, หัวข้อ, Run หรือ token ใน path เท่านั้น คนอื่นได้ 404 แบบเดียวกับ id ที่ไม่มีอยู่ รวมถึงผู้ดูแล | Project ส่วนตัว ([CONTEXT](../../CONTEXT.md)); ผู้ดูแลไม่อ่านเนื้อหางานวิจัยของบุคคล (2026-09-23 และ 2026-10-24 ที่เลิก Support Access Grant) ยกเว้นงานของบัญชีเชื่อมต่อที่อ่านได้อย่างเดียว (ADR-0009 ข้อ 4) |
| `admin` | ผู้ดูแลเท่านั้น และไม่ผ่าน token | หน้าของผู้ดูแลทุกหน้าในเอกสารออกแบบ; "token ไม่มีสิทธิ์ผู้ดูแลเลย" (ADR-0009 ข้อ 3) |
| `token:read` | token ของ MCP ที่ยังใช้ได้และมี scope `read` ไม่รับ cookie ของเว็บ | scope `read` = ดูรายการ สถานะ และรายงาน (ADR-0009 ข้อ 3); ประตูตอบ 401/403 (ข้อ 6); ไม่ใช้ cookie (ทางเลือกที่ไม่เลือก) |
| `token:research` | token ที่มี scope `research` | `research` = เริ่มและยกเลิกงาน (ADR-0009 ข้อ 3) |
| `undecided` | เอกสารไม่ได้บอก | ดู Q1–Q3 |

**ประตูของ MCP ใช้ชั้น `token:read`:** ประตู (`TokenGate`) รับ token ที่ยังใช้ได้ทุก scope ส่วนแต่ละ scope ทำอะไรได้ tool เป็นคนตรวจ ตารางจึงแยก tool เป็นช่องของตัวเอง ใช้ key `("TOOL", "<path>#<ชื่อ tool>")` และเทสต์ดึงรายชื่อ tool จริงจาก `tools/list` ของแต่ละเส้น tool ที่เพิ่มใหม่โดยไม่มีชั้นจึงทำให้เทสต์ล้มเหมือน route ใหม่

## เทสต์ตรวจอะไรในแต่ละชั้น

| ชั้น | สิ่งที่ตรวจ |
|---|---|
| `public` | ไม่ login แล้วไม่ถูกปฏิเสธด้วย 401 |
| `signed_in` | ไม่ login ได้ 401 · ผู้ใช้ทั่วไปเรียกได้ (เฉพาะ GET) · method ที่แก้ข้อมูลแต่ไม่มี CSRF header ได้ 403 `csrf` |
| `owner` | ไม่ login ได้ 401 · ผู้ใช้อื่นได้ 404 `not_found` · ผู้ดูแลได้ 404 `not_found` · เจ้าของเรียกได้ (เฉพาะ GET) · ไม่มี CSRF ได้ 403 · ผู้ดูแลอ่าน Run และหัวข้อของบัญชีเชื่อมต่อได้ (GET ใต้ `/api/runs/{run_id}` และ `/api/sessions/{session_id}`) |
| `admin` | ไม่ login ได้ 401 · ผู้ใช้ทั่วไปได้ 403 `admin_only` · token ของผู้ดูแลเองได้ 401 · ผู้ดูแลเรียกได้ (เฉพาะ GET) และคำตอบไม่มีหัวข้อวิจัยของบุคคล · ไม่มี CSRF ได้ 403 |
| ประตูของ MCP | ไม่มี token ได้ 401 พร้อม `WWW-Authenticate: Bearer` · login บนเว็บแล้วส่ง cookie กับ CSRF header มาได้ 401 · token ที่ไม่มีอยู่ได้ 401 · token ของบัญชีที่ถูกปิดได้ 403 · token ที่ใช้ได้เข้าได้ |
| tool ของ MCP | token ที่ไม่มี scope ที่ต้องใช้ถูก tool ปฏิเสธ · token ที่มี scope นั้นไม่ถูกปฏิเสธเรื่อง scope · tool ที่รับ id (status, report, export, cancel, events) เมื่อใช้ token ของผู้ใช้อื่นหรือของผู้ดูแลได้ "No research with that id belongs to this account." |

- **นอกตาราง:** `test_a_body_cannot_name_another_users_project` ใส่ Project ของผู้อื่นใน body ของ `POST /api/sessions`, `PATCH /api/sessions/{id}` และ `POST /api/discussions` แล้วต้องได้ 404
- **method ที่แก้ข้อมูล:** เทสต์ไม่ได้ให้ผู้มีสิทธิ์แก้จริง เพื่อไม่ให้ข้อมูลชุดทดสอบเปลี่ยนกลางทาง แต่ใช้ "ไม่มี CSRF ได้ 403" เป็นหลักฐานว่าระบบรู้จักผู้เรียกแล้ว ส่วนการเรียกของผู้ใช้อื่นส่ง body ที่ถูกต้อง เพื่อให้ไปถึงขั้นตรวจเจ้าของจริง
- **ข้อมูลชุดทดสอบ:** สร้างครั้งเดียวต่อไฟล์ บน Postgres ชั่วคราว (testcontainers) ได้แก่
  - ผู้ดูแล
  - Alice: Project, หัวข้อที่มี Run สำเร็จพร้อมรายงาน, Run ที่ล้มด้วย 429 โดยข้อความมีหัวข้อติดอยู่, Project ในถังขยะ, Discussion และ token แบบ read, research และตัวสำรอง
  - Bob: ผู้ใช้อื่น
  - Carol: token ที่สร้างก่อนบัญชีถูกปิด
  - บัญชีเชื่อมต่อที่มี Run ของตัวเอง
  - ตั้งค่า Medical Review ไว้ให้ครบทุกเส้น MCP เปิด แต่ไม่ติดต่อ MRA จริง

### หลักฐานว่าเทสต์จับได้จริง

รันไฟล์นี้กับการป้องกันที่ถูกทำให้อ่อนลงทีละอย่าง ผ่าน plugin ของ pytest ชั่วคราวนอก repo (ไม่ได้แก้โค้ดของระบบ):

| ทำให้อ่อนลง | ข้อที่ล้ม |
|---|---|
| `deps.own` ไม่ตรวจเจ้าของ | other_user_404 24 ช่อง, admin_404 24 ช่อง, tool ที่รับ id 50 ข้อ และเทสต์ body ทั้ง 3 ข้อ (อีก 2 ช่อง owner คือกู้คืนจากถังขยะ และเพิกถอน token ของตัวเอง ตรวจเจ้าของในโค้ดของตัวเอง ไม่ผ่าน `deps.own`) |
| ไม่ตรวจ CSRF | no_csrf_403 ทั้ง 48 ช่อง |
| `tokens.require` ไม่ตรวจ scope | missing_scope_refused ทั้ง 35 ช่อง |
| `deps.readable` ให้ผู้ดูแลอ่านทุกอย่าง | admin_404 ของ GET ทั้ง 10 ช่อง |

ตรวจด้วยว่าความล้มเหลวของ Alice ขึ้นบนหน้าสถานะระบบจริง (`/api/admin/monitor` มี Issue `retries_exhausted` ของ alice ที่ข้อความเป็น "Failed while researching …. Last error: Too Many Requests") ข้อ "ไม่มีหัวข้อวิจัย" จึงไม่ได้ผ่านเพราะไม่มีข้อมูล

## ข้อที่เจอ

### SEC-01 — token ของบัญชีที่ถูกปิดได้ 401 "token ไม่ถูกต้อง" แทน 403

| ช่อง | รายละเอียด |
|---|---|
| endpoint | ประตูของ MCP ทั้ง 5 เส้น: `/api/mcp`, `/api/mcp/storm`, `/api/mcp/deep`, `/api/mcp/agent`, `/api/mcp/medical` |
| ที่ควรเป็น | ADR-0009 ข้อ 6: "ปิด MCP อยู่หรือบัญชีถูกระงับได้ 403" |
| ที่เป็นจริง | 401 `{"error": "bad_token", "message": "That token is not valid: unknown, expired or revoked."}` |
| สาเหตุ | `tokens.authenticate` (`server/src/litstorm/tokens.py`) โยน `Refused("bad_token")` เมื่อ `user.is_active` เป็นเท็จ แล้ว `TokenGate` (`server/src/litstorm/api/mcp.py`) แปลง `bad_token` เป็น 401 |
| ระดับ | **ต่ำ** บัญชียังถูกกันไว้ถูกต้อง ผิดแค่รหัสและข้อความ แต่ผู้ดูแลของระบบปลายทาง (เช่น DeepWitya) จะเข้าใจว่า token เสีย แล้วขอ token ใหม่ ซึ่งก็ใช้ไม่ได้ เพราะต้นเหตุคือบัญชีถูกปิด |
| ผู้ใช้เห็นไหม | ใช่ client ของ MCP ได้รหัสและข้อความต่างจากเดิม |
| วิธีแก้ที่เสนอ | ให้ `authenticate` โยน `Refused("account_disabled")` เมื่อบัญชีถูกปิด แล้ว `TokenGate` จะตอบ 403 เอง เพราะไม่ใช่ `no_token` หรือ `bad_token` เพิ่มข้อความใน `_REFUSED` เช่น "An Administrator has switched this account off." ถ้าเจ้าของเห็นว่า 401 ถูกแล้ว ให้แก้ ADR-0009 ข้อ 6 แทน **ขนาดงาน:** เล็ก (ราว 5 บรรทัด และเอา `FINDINGS` ของ SEC-01 ออกจากเทสต์) |
| หลักฐาน | `test_access_class_holds[* /api/mcp \| suspended_403]` และอีก 4 เส้น เป็น `xfail(strict=True, reason="SEC-01")` |

## ช่องที่ต้องให้เจ้าของตัดสิน (10 ช่อง)

ช่องเหล่านี้ไม่อยู่ในเทสต์ เมื่อเจ้าของตัดสินแล้ว ให้เปลี่ยนค่าใน `ACCESS` เป็นชั้นที่เลือก เทสต์จะเริ่มตรวจช่องนั้นเอง

### Q1 — หน้าเอกสาร API ของ FastAPI (4 ช่อง)

`GET /openapi.json`, `GET /docs`, `GET /docs/oauth2-redirect`, `GET /redoc`

- **ตอนนี้:** ทุกคนเปิดได้โดยไม่ต้อง login (ตอบ 200) แต่อยู่นอก `/api` และ nginx ของ stack (`web/nginx.conf`) ส่งต่อเฉพาะ `{base}/api/` จึงเปิดผ่านหน้าเว็บไม่ได้ เว้นแต่มีทางถึงพอร์ตของ api โดยตรง (งานที่ 2 ตรวจพอร์ต)
- **เอกสาร:** ไม่ได้พูดถึง
- **คำถาม:** เลือกข้อไหน
  - (ก) ปิดใน production (`docs_url`, `redoc_url`, `openapi_url` เป็น `None`) และเปิดเฉพาะเครื่อง dev การสร้าง `web/src/api/openapi.json` เรียก `app.openapi()` ตรงได้ จึงไม่ต้องพึ่ง route นี้
  - (ข) เปิดไว้แบบนี้ เพราะ nginx กันไว้แล้ว ถ้าเลือกข้อนี้ ชั้นของช่องคือ `public`
  - (ค) ให้เฉพาะผู้ดูแล

### Q2 — ออกจากระบบ (1 ช่อง)

`POST /api/auth/logout`

- **ตอนนี้:** ไม่ต้อง login และไม่ต้องมี CSRF header
  - ไม่ได้ login ได้ 204
  - ส่ง cookie มาโดยไม่มี CSRF header ได้ 204 และ session นั้นใช้ไม่ได้อีก (ลองแล้ว `/api/me` ได้ 401)
- **เอกสาร:** ADR-0002 บอกว่าคำขอที่แก้ข้อมูลต้องมี CSRF token แต่ไม่ได้พูดถึงการออกจากระบบโดยตรง
- **ความเสี่ยง:** หน้าอื่นสั่งให้ผู้ใช้ออกจากระบบได้ (logout CSRF)
  - cookie เป็น SameSite=Lax เบราว์เซอร์จึงไม่ส่ง cookie กับ POST จากเว็บอื่น
  - แต่บน 203 DeepLit อยู่ที่ `https://203.185.144.41/litstorm` ซึ่งเป็น origin เดียวกับ DeepWitya SameSite จึงไม่กันหน้าของ DeepWitya (ส่งต่อให้งานที่ 2)
  - ผลร้ายที่สุดคือผู้ใช้ถูกพาออกจากระบบ ไม่มีข้อมูลรั่ว
- **คำถาม:** ออกจากระบบควรต้องมี CSRF header เหมือนคำขอที่แก้ข้อมูลอื่นไหม
  - ถ้าต้องมี ชั้นคือ `signed_in` (ต้องตัดสินด้วยว่าคนที่ไม่ได้ login ควรได้ 401 หรือ 204)
  - ถ้าคงแบบเดิม ชั้นคือ `public`

### Q3 — tool `*_options` ของ MCP (5 ช่อง)

`research_options`, `storm_research_options`, `deep_research_options`, `agent_research_options`, `medical_research_options`

- **ตอนนี้:** token ทุก scope เรียกได้ (`_caller(ctx)` ไม่ระบุ scope)
  - ให้ข้อมูลโหมด ความลึก แหล่ง โมเดล ภาษา และโควตาที่เหลือ
  - ลองแล้วทั้ง token แบบ read อย่างเดียวและ research อย่างเดียว ได้คำตอบทั้งคู่
- **เอกสาร:** ADR-0009 ข้อ 3 แบ่ง `read` (ดูรายการ สถานะ และรายงาน) กับ `research` (เริ่มและยกเลิกงาน) แต่ไม่ได้จัด options ไว้ที่ใด ส่วนปุ่ม "ทดสอบการเชื่อมต่อ" ในหน้าการเชื่อมต่อเรียก `research_options` ด้วย token ที่กำลังทดสอบ
- **คำถาม:** เลือกข้อไหน
  - (ก) token ทุก scope เรียกได้ แบบปัจจุบัน
    - token ที่สั่งค้นคว้าอย่างเดียวต้องรู้ตัวเลือกก่อนเริ่ม และปุ่มทดสอบใช้ได้กับทุก token
    - เทสต์ต้องเพิ่มชั้นใหม่ เช่น `token:any`
  - (ข) ต้องมี `read` ถ้าเลือกข้อนี้ ปุ่มทดสอบจะล้มกับ token ที่มีแต่ `research`

### คำถามเพิ่มเติม (ไม่ใช่ช่องในตาราง) — token ที่ขาด scope ควรได้ HTTP 403 ไหม

- **ตอนนี้:** tool ตอบเป็น tool error (`isError`) ข้อความ "This token may not do that: it lacks the 'read' scope." โดย HTTP เป็น 200
- **แผนงานของงานนี้:** เขียนว่า "token ที่ไม่มี scope → 403"
- **ADR-0009 ข้อ 6:** ให้ HTTP status เฉพาะปัญหาที่ประตู ได้แก่ ไม่มี token, token ผิด, ปิด MCP, บัญชีถูกระงับ และเกินอัตรา ส่วน scope ตรวจราย tool เพราะ token หนึ่งเรียกหลาย tool ผ่านประตูเดียว
- **เทสต์ตรวจตามแบบที่เอกสารออกแบบไว้** คือ tool ปฏิเสธ
- **ถ้าเจ้าของต้องการ 403:** ต้องตรวจ scope ที่ประตูโดยอ่านชื่อ tool จาก JSON-RPC ก่อนส่งให้ SDK

## ตารางสิทธิ์ทั้งหมด

### tool ของ MCP (เหมือนกันทั้ง 5 เส้น)

ชื่อ tool ขึ้นต้นตามเส้น: `research_` (`/api/mcp`), `storm_research_`, `deep_research_`, `agent_research_` และ `medical_research_`

| tool | ชั้น | ที่มา |
|---|---|---|
| `*_start` | token:research | เริ่มงาน (ADR-0009 ข้อ 3) |
| `*_cancel` | token:research | ยกเลิกงาน |
| `*_status` | token:read | ดูสถานะ |
| `*_report` | token:read | อ่านรายงาน |
| `*_export` | token:read | ลิงก์ดาวน์โหลดรายงาน เป็นการอ่านรายงาน |
| `*_list` | token:read | ดูรายการ |
| `*_events` | token:read | สถานะและ event ของ Run ชุดเดียวกับที่เจ้าของเห็น ([ADR-0010](../../adr/0010-mcp-app-canvas.md)) |
| `*_options` | **undecided** | Q3 |

### หน้าของ FastAPI (นอก `/api`)

| method | path | ชั้น |
|---|---|---|
| `GET` | `/openapi.json` | **undecided** |
| `GET` | `/docs` | **undecided** |
| `GET` | `/docs/oauth2-redirect` | **undecided** |
| `GET` | `/redoc` | **undecided** |

### การเข้าสู่ระบบ (`api/auth.py`)

| method | path | ชั้น |
|---|---|---|
| `GET` | `/api/health` | public |
| `GET` | `/api/setup` | public |
| `POST` | `/api/setup` | public |
| `POST` | `/api/auth/login` | public |
| `POST` | `/api/auth/logout` | **undecided** |
| `POST` | `/api/auth/password-link` | public |
| `POST` | `/api/auth/password` | public |
| `GET` | `/api/me` | signed_in |
| `PUT` | `/api/me/language` | signed_in |

### ผู้ดูแล (`api/admin.py`)

| method | path | ชั้น |
|---|---|---|
| `GET` | `/api/admin/users` | admin |
| `POST` | `/api/admin/users` | admin |
| `POST` | `/api/admin/users/{user_id}/link` | admin |
| `PATCH` | `/api/admin/users/{user_id}` | admin |
| `DELETE` | `/api/admin/users/{user_id}` | admin |
| `GET` | `/api/admin/llm-credentials` | admin |
| `PUT` | `/api/admin/llm-credentials/{provider}` | admin |
| `DELETE` | `/api/admin/llm-credentials/{provider}` | admin |
| `GET` | `/api/admin/llm-models` | admin |
| `POST` | `/api/admin/llm-models` | admin |
| `PUT` | `/api/admin/llm-models/{model_id}` | admin |
| `POST` | `/api/admin/llm-models/{model_id}/test` | admin |
| `POST` | `/api/admin/llm-models/check` | admin |
| `GET` | `/api/admin/search-providers` | admin |
| `POST` | `/api/admin/search-providers` | admin |
| `PUT` | `/api/admin/search-providers/{provider_id}` | admin |
| `POST` | `/api/admin/search-providers/{provider_id}/test` | admin |
| `POST` | `/api/admin/search-providers/check` | admin |
| `GET` | `/api/admin/model-roles` | admin |
| `PUT` | `/api/admin/model-roles` | admin |
| `GET` | `/api/admin/embedding` | admin |
| `PUT` | `/api/admin/embedding` | admin |
| `POST` | `/api/admin/embedding/check` | admin |
| `GET` | `/api/admin/engines` | admin |
| `PUT` | `/api/admin/engines/{engine}` | admin |
| `GET` | `/api/admin/usage` | admin |
| `GET` | `/api/admin/runs` | admin |
| `GET` | `/api/admin/monitor` | admin |
| `GET` | `/api/admin/monitor/open` | admin |
| `POST` | `/api/admin/monitor/acknowledge` | admin |
| `GET` | `/api/admin/limits` | admin |
| `PUT` | `/api/admin/limits` | admin |

### งานวิจัย: Project, หัวข้อ, Run, ถังขยะ (`api/research.py`)

| method | path | ชั้น |
|---|---|---|
| `GET` | `/api/options` | signed_in |
| `GET` | `/api/projects` | signed_in |
| `POST` | `/api/projects` | signed_in |
| `PATCH` | `/api/projects/{project_id}` | owner |
| `GET` | `/api/projects/{project_id}` | owner |
| `DELETE` | `/api/projects/{project_id}` | owner |
| `POST` | `/api/refine` | signed_in |
| `POST` | `/api/sessions` | signed_in |
| `POST` | `/api/projects/{project_id}/sessions` | owner |
| `GET` | `/api/sessions/recent` | signed_in |
| `GET` | `/api/sessions` | signed_in |
| `PATCH` | `/api/sessions/{session_id}` | owner |
| `GET` | `/api/sessions/{session_id}` | owner |
| `DELETE` | `/api/sessions/{session_id}` | owner |
| `POST` | `/api/sessions/{session_id}/runs` | owner |
| `POST` | `/api/runs/{run_id}/selection` | owner |
| `POST` | `/api/runs/{run_id}/retry` | owner |
| `GET` | `/api/me/quota` | signed_in |
| `GET` | `/api/runs/{run_id}` | owner |
| `GET` | `/api/runs/{run_id}/live` | owner |
| `POST` | `/api/runs/{run_id}/cancel` | owner |
| `DELETE` | `/api/runs/{run_id}` | owner |
| `GET` | `/api/trash` | signed_in |
| `POST` | `/api/trash/{kind}/{item_id}/restore` | owner |

### รายงาน (`api/research.py`)

| method | path | ชั้น |
|---|---|---|
| `GET` | `/api/runs/{run_id}/report` | owner |
| `GET` | `/api/runs/{run_id}/visuals` | owner |
| `POST` | `/api/runs/{run_id}/visuals` | owner |
| `PATCH` | `/api/runs/{run_id}/visuals` | owner |
| `GET` | `/api/runs/{run_id}/interactive` | owner |
| `GET` | `/api/runs/{run_id}/service-page` | owner |
| `GET` | `/api/runs/{run_id}/observatory` | owner |
| `GET` | `/api/runs/{run_id}/export` | owner |
| `GET` | `/api/exports/{token}` | public |

### Discussion (`api/discussions.py`)

| method | path | ชั้น |
|---|---|---|
| `POST` | `/api/discussions` | signed_in |
| `GET` | `/api/discussions/{session_id}` | owner |
| `POST` | `/api/discussions/{session_id}/turns` | owner |

### token และบัญชีเชื่อมต่อ (`api/tokens.py`)

| method | path | ชั้น |
|---|---|---|
| `GET` | `/api/me/connection` | signed_in |
| `GET` | `/api/me/tokens` | signed_in |
| `POST` | `/api/me/tokens` | signed_in |
| `DELETE` | `/api/me/tokens/{token_id}` | owner |
| `GET` | `/api/admin/mcp` | admin |
| `PUT` | `/api/admin/mcp` | admin |
| `GET` | `/api/admin/tokens` | admin |
| `DELETE` | `/api/admin/tokens/{token_id}` | admin |
| `GET` | `/api/admin/integrations` | admin |
| `POST` | `/api/admin/integrations` | admin |
| `PATCH` | `/api/admin/integrations/{account_id}` | admin |
| `POST` | `/api/admin/integrations/{account_id}/tokens` | admin |

### Medical Review (`api/medical.py`)

| method | path | ชั้น |
|---|---|---|
| `GET` | `/api/medical/status` | signed_in |
| `GET` | `/api/admin/medical` | admin |
| `PUT` | `/api/admin/medical` | admin |
| `POST` | `/api/admin/medical/check` | admin |

### ประตูของ MCP (`api/mcp.py`, `TokenGate`, ทุก method)

| method | path | ชั้น |
|---|---|---|
| `*` | `/api/mcp` | token:read |
| `*` | `/api/mcp/storm` | token:read |
| `*` | `/api/mcp/deep` | token:read |
| `*` | `/api/mcp/agent` | token:read |
| `*` | `/api/mcp/medical` | token:read |

## ข้อจำกัดของเทสต์ (จากผู้ตรวจทาน รวมใน Task 12)

- xfail ของ SEC-01 ใส่ `raises=AssertionError` เหมือนเทสต์ใน `test_audit_findings.py` ถ้าวันหนึ่งประตูตอบ 500 แทน 401 ช่องนั้นจะล้มจริง ไม่เป็น xfail เงียบๆ
- การตรวจชั้น `public` ดูแค่ว่า "ไม่ได้ 401" จึงผ่านแม้ route ตอบ 500
- ข้อความ `admin_only` และ `csrf` ที่เทสต์คาด มาจากโค้ด ไม่ได้มาจากเอกสาร (เอกสารบอกแค่ว่าถูกปฏิเสธ)
- ยังไม่ครอบ: ADR-0009 ข้อ 6 "ปิด MCP อยู่ได้ 403" (เทสต์เปิด MCP ไว้ตลอด) และการปฏิเสธเพราะโหมดถูกปิด (`mode_disabled`) หรือบัญชีไม่ได้รับอนุญาตให้ใช้โหมด (`mode_not_allowed`)
- การเรียกของ "ผู้ใช้อื่น" ส่ง body ที่ถูกต้องเพื่อให้ไปถึงการตรวจเจ้าของ ถ้าการป้องกันพังวันหนึ่ง คำขอที่แก้ข้อมูล (เช่น DELETE) จะลงมือจริงกับข้อมูลชุดทดสอบที่ใช้ร่วมทั้งไฟล์ เทสต์ถัดไปอาจล้มต่อกันเป็นทอด (ข้อแรกที่ล้มคือข้อที่บอกสาเหตุ)

## วิธีใช้เทสต์

- **รัน:** `cd server && uv run pytest tests/test_authz_matrix.py -q` (ต้องมี Docker สำหรับ Postgres ชั่วคราว)
- **เพิ่ม endpoint หรือ tool ใหม่:** `test_every_route_has_an_access_class` จะล้มจนกว่าจะใส่ชั้นใน `ACCESS` ให้ตัดสินชั้นจากเอกสาร ถ้าเอกสารไม่บอกให้ใส่ `undecided` แล้วถามเจ้าของ
- **แก้ SEC-01 แล้ว:** ทั้ง 5 ช่องจะผ่าน ซึ่ง `xfail(strict=True)` นับเป็นล้ม ให้ลบรายการ SEC-01 ออกจาก `FINDINGS`
- **เจ้าของตัดสินช่อง `undecided` แล้ว:** เปลี่ยนค่าใน `ACCESS` ถ้าโค้ดยังไม่ตรงกับที่ตัดสิน ให้จดเป็นข้อที่เจอใหม่ แล้วใส่ใน `FINDINGS`
