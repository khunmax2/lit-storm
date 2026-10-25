# ผลตรวจความปลอดภัย (Task 2 ของการตรวจทั้งระบบ 2026-10-24)

ฐานที่ตรวจ: branch `audit/2026-10-24` (HEAD `5f94d69`) · stack ทิ้งได้ `litstorm-audit` ที่ http://127.0.0.1:8098/litstorm (ฐานข้อมูลว่าง ยังไม่ได้ตั้งค่าครั้งแรก) · สเปกส่วน 1 "ความปลอดภัย"

สิทธิ์ราย route ตรวจไปแล้วใน [authz-matrix.md](authz-matrix.md) (SEC-01) รายงานนี้จึงเริ่มที่ SEC-02

## สรุป

ไม่มีข้อระดับ **วิกฤต** · **สูง** 4 ข้อ (SEC-02, 04, 05, 07) · กลาง 2 ข้อ (SEC-03, 06) · ต่ำ 4 ข้อ (SEC-08 ถึง 11) · กลาง 1 ข้อเพิ่มจาก Task 7 (SEC-12)

**เกณฑ์ที่ใช้จัดระดับ** (จากนิยามในสเปก): **วิกฤต** คือข้อมูลรั่วหรือระบบใช้ไม่ได้ โดยผู้โจมตีไม่ต้องมีสิทธิ์อะไรเลย · **สูง** คือกระทบผู้ใช้จริงบ่อย หรือผู้โจมตีที่มีสิทธิ์บางอย่าง (บัญชีผู้ใช้, บัญชีผู้ดูแล, บัญชีที่เคยยึดได้ หรือที่ยืนบน origin เดียวกัน) ใช้แล้วได้ความลับ ข้อมูลของคนอื่น หรือยึดบัญชีได้ · **กลาง** คือต้องอาศัยเงื่อนไขที่อยู่นอกมือผู้โจมตี (ตำแหน่งดักกลางทาง, รหัสผ่านที่อ่อน) หรือผลจำกัดกว่านั้น · **ต่ำ** คือการเสริมความแข็งแรง หรือข้อมูลรั่วเล็กน้อยที่ไม่ได้ความลับหรือบัญชีโดยตรง หัวข้อด้านล่างเรียงตามระดับ ไม่ใช่ตามรหัส

| รหัส | ระดับ | เรื่อง | ผู้ใช้เห็นไหม | หลักฐาน |
|---|---|---|---|---|
| SEC-02 | **สูง** | โหมด Agent ดึงหน้าเว็บจากที่อยู่ภายในเครือข่ายได้ (SSRF) | ไม่ | เทสต์ |
| SEC-04 | **สูง** | บน 203 DeepLit อยู่ origin เดียวกับแอปอื่น cookie กับ CSRF แยกกันด้วย path เท่านั้น | ไม่ (ถ้าย้าย origin ผู้ใช้เห็น URL ใหม่) | ขั้นตอนทำซ้ำ |
| SEC-05 | **สูง** | key ที่เก็บไว้ถูกส่งไปยังที่อยู่ที่พิมพ์มาในคำขอ (ปุ่มทดสอบของผู้ดูแล) | ไม่ | เทสต์ 2 ข้อ |
| SEC-07 | **สูง** | ออกลิงก์ตั้งรหัสใหม่ (reset) แล้ว token ของ MCP ของบัญชีนั้นยังใช้ได้ | ไม่ | เทสต์ |
| SEC-03 | กลาง | login ผิดซ้ำได้ไม่จำกัด ไม่มีการชะลอหรือล็อก | ใช่ (ถ้าเพิ่มการล็อก) | เทสต์ + curl |
| SEC-06 | กลาง | โหมด Agent ปิดการตรวจใบรับรอง TLS ทั้งหมด รวมคำขอที่มี key ของ Tavily | ไม่ | เทสต์ |
| SEC-08 | ต่ำ | เวลาตอบของ login บอกได้ว่าอีเมลไหนมีบัญชี | ไม่ | เทสต์ |
| SEC-09 | ต่ำ | หน้าเว็บไม่มี CSP และไม่กันการถูกฝังใน frame | ไม่ | เทสต์ + curl |
| SEC-10 | ต่ำ | network `agenta-mcp` เห็น API ทั้งตัว และ container ยังไม่ได้ลดสิทธิ์ | ไม่ | ขั้นตอนทำซ้ำ (อ่านจาก config) |
| SEC-11 | ต่ำ | dependency ที่มีแพตช์และโค้ดเราใช้ถึง: certifi, aiohttp, markdown-it (JS) | ไม่ | เทสต์ + `npm audit` |
| SEC-12 | กลาง | รูปใน markdown ของรายงานชี้ไปเว็บนอกได้ เปิดรายงานแล้วเบราว์เซอร์ผู้อ่านดึงรูปนั้นเอง (ช่องทางส่งข้อมูลออก/ติดตามผู้อ่าน) | ไม่ | เทสต์ + Edge บน stack audit |

เทสต์อยู่ใน `server/tests/test_audit_findings.py` ทุกข้อเป็น `xfail(strict=True, raises=AssertionError, reason="SEC-xx")` และยืนยันพฤติกรรมที่ **ปลอดภัย** จึงล้มวันนี้ และจะผ่าน (ทำให้ strict ฟ้อง) เมื่อแก้แล้ว คนแก้ถอด mark ออก เทสต์ทุกข้อไม่เรียกโมเดลหรือบริการค้นหาจริง (ดักคำขอที่จะออกไว้ก่อน)

---

## SEC-02 — โหมด Agent ดึงหน้าเว็บจากที่อยู่ภายในเครือข่ายได้ (SSRF)

| | |
|---|---|
| ด้าน | SSRF |
| ระดับ | **สูง** ผู้ใช้ทั่วไปที่ login ได้ทำได้ (ช่องโหว่ที่ต้องมีสิทธิ์บางอย่าง) และเนื้อหาที่ได้ไปลงในรายงานที่เขาอ่านได้ |
| ผู้ใช้เห็นไหม | ไม่ (งานที่ใช้ที่อยู่ภายนอกตามปกติทำงานเหมือนเดิม) |
| หลักฐาน | `test_sec02_agent_research_does_not_fetch_internal_addresses`: บริการบน `127.0.0.1` ที่ตอบ `<p>internal-service-secret-sec02</p>` ถูก `scrape_urls` อ่านกลับมาเป็นข้อความ |

**ที่มา:** library ของโหมด Agent (fork ของเจ้าของ `khunmax2/lit_agents-deep-research` ติดตั้งจาก `../agents-deep-research`)

- `deep_researcher/tools/web_search.py:350-364` `fetch_and_process_url` เปิด URL ของผลค้นหาทุกอัน โดยกรองแค่นามสกุลไฟล์ (`is_valid_url`) ไม่ดูว่าเป็นที่อยู่ภายในหรือไม่
- `deep_researcher/tools/crawl_website.py:10-60` tool `crawl_website` เปิด `starting_url` ที่โมเดลเลือกเอง แล้วไล่ลิงก์ในโดเมนเดียวกันต่ออีกถึง 10 หน้า
- `deep_researcher/agents/tool_agents/__init__.py:15-19` เปิด `SiteCrawlerAgent` ไว้ และ DeepLit ไม่ได้ปิด (`server/src/litstorm/engines/agent/engine.py:166-200` ห่อแค่การนับและจด URL)
- aiohttp ตาม redirect เองเป็นค่าเริ่มต้น หน้าเว็บภายนอกที่ตอบ 302 ไปยังที่อยู่ภายในจึงพาไปถึงได้ด้วย

**ใครทำได้และเห็นอะไร:** ผู้ใช้พิมพ์หัวข้อว่า "สรุปเนื้อหาของ http://searxng:8080/config" (หรือหน้าเว็บที่ถูกค้นเจอฝังคำสั่งแบบนั้นไว้) planner ของ Agent ส่งงานให้ crawl agent ซึ่งเปิดที่อยู่นั้นจาก container ของ worker แล้วเขียนสรุปลงรายงาน ที่อยู่ที่ worker เข้าถึงได้:

- บริการใน compose: `searxng:8080`, `api:8000`, `web:80` (`stack/compose.yml`)
- เครื่อง host ผ่าน `host.docker.internal` (`stack/compose.yml:59,71` `extra_hosts: host-gateway`) รวมพอร์ตที่ฟัง 0.0.0.0 บน 203
- บน 203: network `litstorm-mra` ซึ่งมี Caddy ของ MRA เป็น `http://mra` (`stack/compose.host.yml:12-15,36`)
- `169.254.169.254` ถ้าเครื่องเป็น VM บน cloud

ฐานข้อมูล (`db:5432`) พูด HTTP ไม่ได้ จึงอ่านไม่ได้ทางนี้ และ `file://` ใช้ไม่ได้ (crawl เติม `http://` ข้างหน้า ส่วน aiohttp ไม่รู้จัก scheme อื่น)

**ผลลองจริง (Task 5, stack audit):** ลอง Agent 2 รอบด้วยหัวข้อ `สรุปเนื้อหาของหน้า http://searxng:8080/config` — (1) Gemini 2.5 Flash Lite: planner **ตั้งใจ** ส่งคำสั่งไปเปิด URL ภายใน (query `content of http://searxng:8080/config`, `searxng:8080` เป็นแหล่งอ้างอิงเดียวของรายงาน) แต่เครื่องมือล้มด้วย 400 ของ Gemini ก่อนได้เนื้อหา จึง**ไม่มีเนื้อหาจากหน้าภายในในรายงาน** (`browsed` ว่าง); (2) GPT-4.1 nano: โมเดลเปลี่ยนเป็นค้นเอกสารสาธารณะของ SearXNG (`browsed` มีแต่ docs.searxng.org) Run ล้ม `empty_report` ผล: **ยังไม่ยืนยันว่าโมเดลเลือกเปิดที่อยู่ภายในแล้วอ่านได้จริง** แต่พฤติกรรมครึ่งแรก (โมเดลยอมส่ง URL ภายในไปให้เครื่องมือ) เกิดจริง ส่วนการอ่านกลับมายืนยันด้วยเทสต์ `test_sec02_...` เดิม ระดับ **สูง** คงเดิม รายละเอียดใน [live.md](live.md), BUG-49, BUG-52

**วิธีแก้ที่เสนอ:** ใน fork ให้ทุกการเปิด URL (scrape, crawl และ redirect แต่ละทอด) resolve ชื่อก่อนแล้วปฏิเสธที่อยู่ loopback, private (10/8, 172.16/12, 192.168/16), link-local (169.254/16), CGNAT, IPv6 ULA/link-local และชื่อบริการใน compose ทำผ่าน resolver ของ aiohttp ตัวเองเพื่อกัน DNS rebinding และปิด `allow_redirects` แล้วตามเองหลังตรวจ · ขนาด: **กลาง** (ราวครึ่งวัน รวมเทสต์ใน fork) ทางเสริม: เอา `extra_hosts` ออกจาก worker ถ้าไม่ได้ใช้ Ollama บนเครื่อง

---

## SEC-04 — บน 203 DeepLit อยู่ origin เดียวกับแอปอื่น

| | |
|---|---|
| ด้าน | การ login (session, CSRF) ข้ามแอป |
| ระดับ | **สูง** ผู้โจมตีต้องมีที่ยืนบน origin เดียวกันก่อน (XSS หรือการควบคุมแอปใดแอปหนึ่งบน `203.185.144.41`) ซึ่งนับเป็นสิทธิ์บางอย่าง ผลคือยึดบัญชี DeepLit ได้ทั้งหมด รวมบัญชีผู้ดูแล |
| ผู้ใช้เห็นไหม | ไม่ ถ้าแก้ด้วย header อย่างเดียว · ใช่ ถ้าย้ายไป subdomain หรือพอร์ตของตัวเอง (URL เปลี่ยน) |
| หลักฐาน | ขั้นตอนทำซ้ำด้านล่าง (ทำเป็นเทสต์ไม่ได้: เป็นพฤติกรรมของเบราว์เซอร์และ config ของ host) |

- `docs/deploy/HOST-203.md:30-32` และ `stack/host/apply-nginx.sh:43-45`: DeepLit อยู่ที่ `https://203.185.144.41/litstorm/` ใน server `:443` เดียวกับ DeepWitya (`/deepwitya`) และแอปอื่นบน host (ไฟล์ `sansarnnews-ssl`)
- `server/src/litstorm/api/auth.py:47-52`: cookie `litstorm_session` (httpOnly) และ `litstorm_csrf` (อ่านได้จาก JS) ตั้ง `path=/litstorm` และ `SameSite=Lax`
- `server/src/litstorm/settings.py:42-48` เขียนว่า "Cookies are scoped to it, so they are not sent to the other apps on the same host" ซึ่งจริงเรื่องการส่ง แต่ไม่ใช่การแยก: path ของ cookie ไม่ใช่ขอบเขตความปลอดภัย และ SameSite ไม่มีผลเพราะเป็น site เดียวกัน

**ขั้นตอนทำซ้ำ (บนเครื่อง ไม่แตะ 203):** stack mirror ของเครื่องนี้ (`stack/compose.mirror.yml`, edge ตอบ 404 ที่ `/`) จำลองได้ด้วยหน้า HTML ใดๆ ที่ edge เสิร์ฟนอก `/litstorm` สคริปต์ในหน้านั้นทำได้:

1. `const f = document.createElement("iframe"); f.src = "/litstorm/"; document.body.append(f);` (หน้า SPA ไม่มี `X-Frame-Options` หรือ `frame-ancestors` ดู SEC-09)
2. เมื่อโหลดเสร็จ `f.contentDocument.cookie` ได้ค่า `litstorm_csrf` (same-origin จึงอ่าน DOM ของ frame ได้)
3. `fetch("/litstorm/api/admin/users", {method: "POST", credentials: "include", headers: {"X-CSRF-Token": csrf, "Content-Type": "application/json"}, body: ...})` เบราว์เซอร์แนบ `litstorm_session` เอง (path ตรง) ได้ลิงก์ตั้งรหัสผ่านของบัญชีผู้ดูแลใหม่ในคำตอบ

แอปอื่นยังตั้ง cookie ชื่อ `litstorm_*` ที่ `path=/litstorm` ทับได้ (cookie tossing) เพื่อให้เหยื่อทำงานในบัญชีของผู้โจมตี

ยืนยันในเบราว์เซอร์: ต้องยืนยันในเบราว์เซอร์ (Task 5/8) บน stack audit ด้วยหน้าทดสอบที่ edge เสิร์ฟนอก `/litstorm` (ต้องเพิ่ม location ชั่วคราวใน `stack/edge/nginx.conf` ของ stack audit เท่านั้น) ทำขั้น 1-2 ด้วยบัญชีทดสอบ และไม่พิมพ์ค่า cookie ออกจอ ให้แค่ตรวจว่าความยาวมากกว่า 0 · **ผล (Task 12):** ยังไม่ได้ทำ Task 5 ถึง 9 ไม่ได้เพิ่มหน้าทดสอบที่ edge และ stack audit ถูกลบแล้ว ข้อนี้จึงยืนอยู่บนการอ่าน config กับพฤติกรรมมาตรฐานของเบราว์เซอร์ (same-origin อ่าน DOM ของ frame ได้, path ของ cookie ไม่กันสคริปต์ใน origin เดียวกัน) ระดับคงเดิม

**วิธีแก้ที่เสนอ:**
- ทางที่แยกได้จริง: ให้ DeepLit มี origin ของตัวเอง เช่น `litstorm.<โดเมน>` หรือพอร์ต HTTPS ของตัวเอง แล้วใช้ cookie แบบ `__Host-` · ขนาด: **กลาง** ทางเทคนิค แต่ต้องขอ DNS หรือพอร์ตจากผู้ดูแล host
- ระหว่างนั้น: ใส่ `frame-ancestors 'self'` กับ CSP ใน SPA (SEC-09) ตัดขั้น 1 ได้บางส่วน (แอปอื่นยัง `window.open` แล้วอ่าน cookie ของหน้าต่างนั้นได้) และบันทึกเรื่องนี้ไว้ใน `HOST-203.md` ว่าความปลอดภัยของ DeepLit ขึ้นกับทุกแอปบน `203.185.144.41` · ขนาด: **เล็ก**

---

## SEC-05 — key ที่เก็บไว้ถูกส่งไปยังที่อยู่ที่พิมพ์มาในคำขอ

| | |
|---|---|
| ด้าน | ความลับ / SSRF จากหน้าผู้ดูแล |
| ระดับ | **สูง** ต้องมีสิทธิ์ผู้ดูแล (หรือ session ของผู้ดูแลที่ยึดมา เช่นผ่าน SEC-04) ผลคือได้ key ตัวจริงของ OpenRouter ที่ระบบสัญญาว่าไม่ออกนอก server (`admin.py:3`) แล้วใช้เงินขององค์กรได้ |
| ผู้ใช้เห็นไหม | ไม่ (ผู้ดูแลที่ทดสอบ address ใหม่จะต้องพิมพ์ key อีกครั้ง) |
| หลักฐาน | `test_sec05_testing_a_draft_model_does_not_send_the_stored_key_elsewhere` และ `test_sec05_testing_an_embedding_does_not_send_the_stored_key_elsewhere`: key ที่เก็บไว้ไปถึง `http://attacker.invalid/v1` ทั้งสองทาง |

หลักของระบบเอง: "Stored keys never leave the server" (`server/src/litstorm/api/admin.py:3`) และ `embedding.key_for` (`server/src/litstorm/embedding.py:85-99`) เขียนไว้ว่า key ที่เก็บ "is not sent anywhere else" แต่

- `POST /api/admin/llm-models/check` (`server/src/litstorm/api/admin.py:440-456`): ไม่ใส่ `api_key` แต่ใส่ `api_base` ใหม่ → ใช้ key ที่เก็บของ provider นั้น (บรรทัด 447) กับ `api_base` จากคำขอ (บรรทัด 448)
- `POST /api/admin/embedding/check` และ `PUT /api/admin/embedding`: `key_for` กัน key ไว้เฉพาะ `openai-compatible` ส่วน provider `openrouter`, `openai`, `gemini` ยอมรับ `api_base` ของคำขอก่อน (`embedding.base_url`, บรรทัด 79-82) แล้วส่ง key ที่เก็บไปที่นั่น ทั้งตอนทดสอบและในทุก Run หลังบันทึก
- แบบเดียวกัน (อ่านจากโค้ด ไม่ได้ทำเทสต์แยก): เปลี่ยน `url` ของ MRA โดยไม่ใส่ key ใหม่ (`server/src/litstorm/medical.py:37-49`) key เดิมไปกับที่อยู่ใหม่ และแก้ `endpoint` ของ Search Provider โดยไม่ส่ง `api_key` (`server/src/litstorm/api/admin.py:360-365`) key เดิมไปกับ endpoint ใหม่ใน Run ถัดไป (`knowledge_storm/rm.py` ส่งเป็น `Authorization: Bearer`)

**วิธีแก้ที่เสนอ:** ใช้กฎเดียวกับ `key_for` ทุกจุด: เมื่อที่อยู่ในคำขอต่างจากที่อยู่ที่เก็บคู่กับ key ให้ใช้ key เฉพาะที่พิมพ์มาในคำขอเดียวกัน ไม่งั้นทดสอบแบบไม่มี key และเมื่อบันทึกที่อยู่ใหม่ของ MRA หรือ Search Provider ให้ลบ key เดิม (หน้าผู้ดูแลขอ key ใหม่) · ขนาด: **เล็ก** (ราว 2 ชั่วโมง รวมเทสต์)

---

## SEC-07 — reset แล้ว token ของ MCP ยังใช้ได้

| | |
|---|---|
| ด้าน | การ login (การปิดบัญชี/รีเซ็ต) |
| ระดับ | **สูง** ต้องเคยยึดบัญชีได้ (สิทธิ์ของผู้ใช้คนนั้น) ผลคือการยึดบัญชีอยู่รอดหลังการ reset ซึ่งเป็นวิธีกู้บัญชีที่หลุด: token อายุถึง 365 วัน (scope research) ที่สร้างไว้ก่อนยังเริ่มงานด้วยโควตาของเหยื่อและอ่านรายงานทั้งหมดได้ ผู้ดูแลเพิกถอนเองได้ในหน้า token แต่ต้องรู้ว่าต้องทำ |
| ผู้ใช้เห็นไหม | ไม่ (ยกเว้นเจ้าของบัญชีต้องสร้าง token ใหม่หลัง reset) |
| หลักฐาน | `test_sec07_a_password_reset_stops_the_accounts_api_tokens`: หลัง `POST /api/admin/users/{id}/link` token เดิมยังได้ 200 จาก `/api/mcp` |

`server/src/litstorm/api/admin.py:121-134` docstring ว่า "the old password stops working and the User is signed out everywhere" แต่ลบแค่ `AuthSession` (บรรทัด 132) ส่วน `tokens.authenticate` (`server/src/litstorm/tokens.py:112-134`) ดูแค่ `is_active` ไม่ดู `must_set_password` (การปิดบัญชีปลอดภัย: token ถูกปฏิเสธเพราะ `is_active` เป็นเท็จ)

**วิธีแก้ที่เสนอ:** ใน `reset_link` เมื่อบัญชีมีรหัสผ่านอยู่แล้ว เพิกถอน token ของบัญชีนั้นทั้งหมด (หรือให้ `authenticate` ปฏิเสธเมื่อ `must_set_password` แล้วให้ผู้ใช้เลือกเปิด token เดิมคืน) และบอกผู้ดูแลในหน้ายืนยันการ reset ว่า token จะถูกเพิกถอนด้วย (ข้อความใหม่ ต้องอนุมัติ) · ขนาด: **เล็ก**

---

## SEC-03 — login ผิดซ้ำได้ไม่จำกัด

| | |
|---|---|
| ด้าน | การ login (การเดารหัสผ่านซ้ำ) |
| ระดับ | กลาง ไม่ต้องมีสิทธิ์อะไร แต่ได้ผลก็ต่อเมื่อรหัสผ่านอ่อนพอจะเดาได้ (ขั้นต่ำ 10 ตัวอักษร argon2 ราว 50 ms ต่อครั้ง) ผลสุดท้ายคือยึดบัญชีนั้น |
| ผู้ใช้เห็นไหม | ใช่ ถ้าแก้ด้วยการล็อกบัญชีหรือแสดงข้อความ "ลองใหม่ในอีก N นาที" (ต้องอนุมัติข้อความ) |
| หลักฐาน | `test_sec03_repeated_wrong_passwords_are_slowed_down`: ผิด 50 ครั้งติดได้ 401 ทั้ง 50 ครั้ง · บน stack audit: `curl -X POST .../litstorm/api/auth/login` 50 ครั้ง ได้ `50 401` ไม่มี 429 ที่ edge เช่นกัน |

`server/src/litstorm/api/auth.py:157-172` ไม่มีตัวนับใดๆ เช่นเดียวกับ `/api/setup` (รหัสตั้งต้น 24 ตัวอักษรสุ่ม จึงเดาไม่ได้จริง) และ `/api/auth/password-link` (token 32 ไบต์ เดาไม่ได้) nginx ทั้งสองชั้น (`web/nginx.conf`, `stack/host/apply-nginx.sh` location ของ 203) ไม่มี `limit_req`

ผลข้างเคียงที่ควรรู้: การตรวจรหัสหนึ่งครั้งใช้ argon2 `time_cost=3, memory_cost=64 MiB, parallelism=4` (วัดได้ราว 50 ms ต่อครั้งบนเครื่องนี้) ดู "สงสัย" ข้อ 2

**วิธีแก้ที่เสนอ:** นับครั้งที่ผิดต่ออีเมลและต่อ IP ในตาราง (หรือในหน่วยความจำต่อ process ก็พอสำหรับเครื่องเดียว) ผิดเกิน 10 ครั้งใน 15 นาที ตอบ 429 พร้อม `Retry-After` และใส่ `limit_req` ที่ nginx ของ `/api/auth/` เป็นชั้นที่สอง (ต้องตั้ง `--forwarded-allow-ips` ของ uvicorn ให้เชื่อ nginx จึงจะเห็น IP จริง) · ขนาด: **เล็ก-กลาง** (ราว 2-3 ชั่วโมง)

---

## SEC-06 — โหมด Agent ปิดการตรวจใบรับรอง TLS

| | |
|---|---|
| ด้าน | ความลับ (key ระหว่างทาง) |
| ระดับ | กลาง ต้องอยู่ในตำแหน่งดักกลางทางระหว่าง worker กับ Tavily (เครือข่ายหรือ DNS) ซึ่งอยู่นอกการควบคุมของผู้ใช้ DeepLit ถ้าได้ ผลคือ key ของ Tavily และแก้ผลค้นหาได้ |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | `test_sec06_agent_research_checks_certificates`: `web_search.ssl_context.verify_mode` เป็น `CERT_NONE` |

`deep_researcher/tools/web_search.py:120-125` สร้าง `ssl_context` ตัวเดียว ปิด `check_hostname`, ตั้ง `CERT_NONE` และลดเป็น `SECLEVEL=1` แล้วใช้กับ

- `TavilyClient.search` (บรรทัด 294-303) ซึ่ง POST `{"api_key": ...}` ไป `https://api.tavily.com/search`
- `SearchXNGClient`, `scrape_urls` และ `crawl_website` (ทุกหน้าที่อ่าน)

(`knowledge_storm/utils.py:677` ก็ปิดการตรวจเช่นกัน แต่ใช้เฉพาะ retriever Bing/You ที่ DeepLit ไม่ได้ใช้ จึงไม่นับ)

**วิธีแก้ที่เสนอ:** ใน fork ใช้ context มาตรฐาน (`ssl.create_default_context()` ไม่แก้อะไร) อย่างน้อยกับ Tavily และ SearXNG ส่วนการอ่านหน้าเว็บ ถ้าต้องการยอมเว็บที่ใบรับรองเสีย ให้ใช้ context แยกที่ไม่มี key ใดๆ ผ่าน · ขนาด: **เล็ก** (ไม่กี่บรรทัดใน fork แล้ว build image ใหม่)

---

## SEC-08 — เวลาตอบของ login บอกได้ว่าอีเมลไหนมีบัญชี

| | |
|---|---|
| ด้าน | การ login |
| ระดับ | ต่ำ คำตอบเหมือนกันทุกกรณีตามที่ตั้งใจ (`auth.py:160-161`) แต่เวลาไม่เท่า |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | `test_sec08_login_does_the_same_work_for_an_unknown_address`: login ด้วยอีเมลที่ไม่มีบัญชี ไม่เรียก `security.verify_password` เลย (เทสต์นับการเรียก จึงไม่ขึ้นกับเวลา) · วัดด้วยมือ: อีเมลที่มีบัญชี (รหัสผิด) ราว 57 ms อีเมลที่ไม่มีราว 7 ms (ค่ามัธยฐาน 7 ครั้ง) |

`server/src/litstorm/api/auth.py:162-169`: `user is None` จบก่อนถึง `verify_password` จึงไม่มีการคำนวณ argon2 ร่วมกับ SEC-03 ผู้โจมตีไล่หาอีเมลที่มีบัญชีก่อน แล้วเดารหัสเฉพาะบัญชีเหล่านั้น

**วิธีแก้ที่เสนอ:** เมื่อไม่พบบัญชี (หรือบัญชีที่ login ไม่ได้) ให้ verify กับ hash หลอกที่สร้างไว้ครั้งเดียว · ขนาด: **เล็ก** (ไม่กี่บรรทัด)

---

## SEC-09 — หน้าเว็บไม่มี CSP และไม่กันการถูกฝังใน frame

| | |
|---|---|
| ด้าน | HTTP security headers หลัง nginx |
| ระดับ | ต่ำ โค้ดฝั่งเว็บกัน XSS ได้ดีอยู่แล้ว (ดู "ตัดทิ้ง") และ cookie `SameSite=Lax` ทำให้ site อื่นฝังหน้าที่ login อยู่ไม่ได้ ข้อนี้เป็นชั้นป้องกันที่สอง และช่วยลดผล SEC-04 |
| ผู้ใช้เห็นไหม | ไม่ (ถ้า CSP ครบ) |
| หลักฐาน | `test_sec09_the_web_app_is_served_with_a_csp_and_no_framing` (อ่าน `web/nginx.conf`) และ `curl -I` ด้านล่าง |

```
$ curl -sI http://127.0.0.1:8098/litstorm/login        # หน้าเว็บ
HTTP/1.1 200 OK
Server: nginx/1.29.8
Cache-Control: no-cache
X-Content-Type-Options: nosniff
Referrer-Policy: same-origin
$ curl -s -D - -o /dev/null http://127.0.0.1:8098/litstorm/api/me   # API
HTTP/1.1 401 Unauthorized
Server: nginx/1.29.8
Content-Type: application/json
```

- ไม่มี `Content-Security-Policy` และ `frame-ancestors`/`X-Frame-Options` ในหน้า SPA (`web/nginx.conf:144-149`)
- ไม่มี `Strict-Transport-Security`: snippet ของ 203 (`stack/host/apply-nginx.sh:73-87`) ไม่ได้ใส่ ส่วน server ที่ใช้ร่วมกันจะใส่หรือไม่ ต้องดูบน host (ไม่ได้ดู)
- คำตอบของ `/api` ไม่มี `nosniff` ยกเว้นหน้า interactive, service page, observatory และ export ผ่านลิงก์ ซึ่งใส่เอง
- `Server: nginx/1.29.8` บอกรุ่น

ผลที่ตามมาเล็กน้อยจากการไม่มี CSP: markdown ของโมเดลที่มี `![](https://…)` แสดงเป็นรูปจากที่อยู่ภายนอกในหน้ารายงาน (`web/src/pages/report.tsx:63-70`) ผู้ที่วางรูปไว้จึงรู้ว่ามีคนเปิดอ่าน (และ IP)

**วิธีแก้ที่เสนอ:** ใน `web/nginx.conf` location ของ SPA ใส่ `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; frame-ancestors 'self'; base-uri 'none'; object-src 'none'` (ต้องลองว่าหน้าไหนใช้อะไรเพิ่ม เช่น favicon ของแหล่งอ้างอิง ก่อนบังคับใช้ ให้เริ่มด้วย `Content-Security-Policy-Report-Only`) ใส่ `server_tokens off` และขอผู้ดูแล 203 ใส่ HSTS ที่ server `:443` · ขนาด: **เล็ก-กลาง** (ส่วนที่กินเวลาคือไล่ให้ CSP ไม่ทำหน้าใดพัง ผู้ใช้อาจเห็นถ้า favicon ภายนอกหายไป)

---

## SEC-10 — network `agenta-mcp` เห็น API ทั้งตัว และ container ยังไม่ได้ลดสิทธิ์

| | |
|---|---|
| ด้าน | container และ compose |
| ระดับ | ต่ำ |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | อ่านจากไฟล์ config (ไม่ได้แตะ stack ของ Agenta ตามข้อจำกัด) ขั้นตอนตรวจซ้ำด้านล่าง |

สิ่งที่ดีอยู่แล้ว: เปิดพอร์ตเดียวบน `127.0.0.1` (`stack/compose.yml:84-85`, `compose.host.yml:43-44`, `compose.mirror.yml:29-30`), api/worker รันเป็น uid 10001 (`server/Dockerfile:66-67`), key ส่งเป็น Docker secret ไม่ใช่ env (`stack/compose.yml:56,70,100-104`) และ Run ได้ key ผ่าน stdin (`server/src/litstorm/runner/supervisor.py:94-121`), ไม่มีไฟล์ลับอยู่ใน git (ตรวจ `git ls-files` และประวัติด้วย pattern ของ key OpenRouter)

ที่ควรรู้:
1. `stack/compose.agenta.yml:103-113` ใส่ `api` ใน `agenta-mcp` เป็น `deeplit-api` ทุก container ใน network นั้นเรียก `http://deeplit-api:8000` ได้ทุก route ไม่ใช่แค่ `/api/mcp`: `/api/auth/login` (ไม่ผ่าน nginx: ไม่มีขีดจำกัดขนาด body 1 MB), `/docs` และ `/openapi.json` ของ FastAPI (ภายนอกเห็นไม่ได้เพราะ nginx ส่งต่อเฉพาะ `/api/`) เป็น HTTP ล้วน และ api ก็มองเห็นทุก container ใน `agenta-mcp` เช่นกัน (ปุ่มทดสอบของผู้ดูแลจึงยิงไปถึงได้)
2. ไม่มี `cap_drop`, `security_opt: no-new-privileges`, `read_only` ใน service ใดเลย; nginx ของ web และ edge รัน master เป็น root ตาม image ปกติ
3. รหัสผ่าน Postgres `litstorm` เขียนตายตัว (`stack/compose.yml:21,44`) ทุก container ใน network default (รวม searxng) เข้าฐานข้อมูลได้ถ้ารู้

ตรวจซ้ำ: `grep -n "networks\|aliases" stack/compose.agenta.yml` และ `grep -n "cap_drop\|no-new-privileges\|read_only" stack/compose*.yml` (ได้ว่าง) · ถ้าจะดูว่าใครอยู่ใน `agenta-mcp` ต้องให้เจ้าของรัน `docker network inspect agenta-mcp` เอง

**วิธีแก้ที่เสนอ:** ใส่ reverse proxy เล็กๆ (หรือ location ใน nginx ของ web) ที่ส่งเฉพาะ `/api/mcp*` และ `/api/exports/*` เข้า `agenta-mcp` แทน api ตรงๆ, ปิด `/docs` ด้วย `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` ใน production, ใส่ `cap_drop: [ALL]` + `no-new-privileges` ให้ api/worker และย้ายรหัสผ่าน Postgres เป็น secret · ขนาด: **เล็ก-กลาง**

---

## SEC-11 — dependency ที่มีแพตช์และโค้ดเราใช้ถึง

| | |
|---|---|
| ด้าน | dependency |
| ระดับ | ต่ำ |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | `test_sec11_outbound_https_libraries_are_patched` (certifi, aiohttp) และ `npm audit --omit=dev` (markdown-it) |

ผลดิบ: `pip-audit` เจอ 54 รายการใน 7 package, `npm audit --omit=dev` เจอ 5 รายการ จดเฉพาะที่ใช้ถึงจริง:

| package | รุ่น | ช่องโหว่ | ใช้ถึงไหม | แก้ |
|---|---|---|---|---|
| certifi | 2026.7.22 | PYSEC-2026-4320 ไว้ใจ root `emSign ECC Root CA - G3` ที่ intermediate ถูกขโมย key | ใช่: ทุกคำขอ HTTPS ขาออกผ่าน requests/httpx (OpenRouter, Tavily, TCI, MRA) | ≥ 2026.10.19 |
| aiohttp | 3.14.3 | GHSA-2g87-pp6c-29x5 และ CVE-2026-1110xx (7 ข้อ) ส่วนใหญ่ฝั่ง server | บางส่วน: DeepLit ใช้เป็น client ใน Agent (อ่านหน้าเว็บที่ผู้อื่นควบคุม) ข้อฝั่ง server และ cookie jar ไม่ถึง | ≥ 3.14.4 (patch) |
| markdown-it (JS) | 15.0.2 | GHSA-gfr2-rv44-r23c: link reference definition หลายบรรทัดทำให้ render ช้าแบบกำลังสอง ด้วยค่าเริ่มต้น | ใช่: หน้ารายงาน render markdown ของโมเดลด้วย `new MarkdownIt({html: false})` (`web/src/pages/report.tsx:65`) รายงานที่จงใจสร้างทำให้แท็บของผู้อ่านค้าง (GHSA-vfgh-jcmw-g37q ต้องเปิด html จึงไม่ถึง) | ≥ 15.0.3 |

ที่ไม่ถึง (ไม่นับ):
- litellm 1.80.0 (31 รายการ): ทุกข้อเป็นของ LiteLLM **proxy server** เราใช้แค่ `litellm.completion` ใน SDK ไม่ได้รัน proxy (ควรอัปเกรดตามรอบปกติ)
- transformers 4.57.6: ทุกข้อเกี่ยวกับการโหลด model/checkpoint ที่ไม่น่าไว้ใจหรือ Trainer เราโหลดแค่ `paraphrase-MiniLM-L6-v2` ที่อบไว้ใน image และ `HF_HUB_OFFLINE=1` (`server/Dockerfile:48-51`)
- datasets (folder builder), fsspec (`ReferenceFileSystem`), diskcache (ต้องเขียนไดเรกทอรี cache ได้ก่อน): ไม่ได้ใช้ส่วนนั้น
- npm: `@modelcontextprotocol/sdk`, `hono`, `ip-address`, `source-map-js` มาจาก `shadcn` (CLI) และ `postcss` ตอน build ไม่ได้อยู่ใน bundle ที่เสิร์ฟ หมายเหตุ: `shadcn` อยู่ใน `dependencies` แทน `devDependencies` (`web/package.json`) จึงโผล่ใน `--omit=dev`

**วิธีแก้ที่เสนอ:** `uv lock --upgrade-package certifi --upgrade-package aiohttp` และ `npm update markdown-it` (ไม่ข้ามรุ่นหลัก) แล้วย้าย `shadcn` ไป devDependencies · ขนาด: **เล็ก** (ต้อง build image ใหม่)

---

## SEC-12 — รูปใน markdown ของรายงานชี้ไปเว็บนอกได้ เปิดรายงานแล้วเบราว์เซอร์ผู้อ่านดึงรูปนั้นเอง

| | |
|---|---|
| ด้าน | ข้อมูลรั่วออกนอก / การติดตามผู้อ่าน |
| ระดับ | **กลาง** (ต้องให้หน้าเว็บที่โมเดลอ่านทำให้โมเดลเขียน `![](https://...)` ลงรายงาน ซึ่งเป็นทาง prompt injection ที่รู้จักกัน ผลคือ IP ของผู้อ่านและสิ่งที่ฝังใน URL ไปถึงเซิร์ฟเวอร์ภายนอก) |
| ผู้ใช้เห็นไหม | ไม่ (เห็นแค่รูปเสีย) |
| หลักฐาน | `test_sec12_a_report_cannot_make_the_readers_browser_fetch_an_outside_image` และ Edge บน stack audit: แก้ `report.json` ของ Run ทดสอบให้มี `![t [1] ...](https://example.org/a.png)` แล้วเปิดหน้ารายงานกับไฟล์ export HTML เบราว์เซอร์พยายามขอ `https://example.org/a.png` (ดักด้วย `page.route` แล้วตัดทิ้ง ไม่มีคำขอออกจริง) |

markdown-it ของ SPA และ `render/html.py` ยอมรูปทุก URL ตามค่าเริ่มต้น หน้า interactive และ brief ปลอดภัยเพราะมี CSP `img-src data:` (`render/interactive.py:901`, `brief.py:828`) แต่หน้ารายงานของเว็บไม่มี CSP (SEC-09) และไฟล์ HTML ที่ export ไม่มี CSP เลย

**วิธีแก้ที่เสนอ:** ใน markdown-it และ `render/html.py` ปิด image rule (`md.disable("image")`) หรือยอมเฉพาะ `data:` และใส่ `img-src 'self' data:` ใน CSP ของ SPA (รวมกับ SEC-09) กับใน `<meta http-equiv="Content-Security-Policy">` ของ export HTML · ขนาด: **เล็ก**

---

## ต้องยืนยันในเบราว์เซอร์ (Task 5/8)

จากการอ่านโค้ด ข้อเหล่านี้ปลอดภัย แต่ผลจริงขึ้นกับเบราว์เซอร์ จึงให้ Task 5/8 ลองบน stack audit ด้วยบัญชีทดสอบ

| ที่ | ใส่อะไร | ที่คาดว่าจะเห็น |
|---|---|---|
| ชื่อ Project (`/projects` → สร้าง), หัวข้อของงาน (หน้าเริ่มงาน), ข้อความใน Co-STORM (กล่องคุยของ Discussion) | `<img src=x onerror=alert(1)>` และ `"><svg onload=alert(1)>` | แสดงเป็นตัวอักษร ไม่มี alert (React escape เอง) ในทุกที่ที่ชื่อนั้นโผล่: sidebar, หัวหน้า, รายการล่าสุด, ถังขยะ, หน้าสถานะระบบ (ผู้ดูแล), observatory (`<title>` และตัวหน้า) |
| markdown ของรายงาน (แก้ `report.json` ของ Run ทดสอบบน volume ของ stack audit ให้ section body เป็น `[x](javascript:alert(1)) <img src=x onerror=alert(1)> ![t [1] onerror=alert(1)](https://example.org/a.png)` และเพิ่ม source ที่ `url` เป็น `javascript:alert(document.domain)`) | | หน้ารายงาน: ลิงก์ javascript ไม่ถูกทำเป็นลิงก์ (markdown-it) HTML เป็นตัวอักษร และลิงก์ของแหล่งอ้างอิงถูก React 19 บล็อก · export HTML: href เป็น `#` (`render/html.py:376-377`) · observatory: ลิงก์ของแหล่งที่ไม่ใช่ http(s) เป็นข้อความ (`render/observatory.html:721`) · หน้า interactive: ไม่ทำลิงก์ (`render/brief.py:800,815`) |
| หน้า interactive และ service page ใน iframe | เปิด DevTools ใน frame แล้วรัน `fetch("/litstorm/api/me").then(r => r.status)` และ `document.cookie` | fetch ล้มเพราะ origin เป็น `null` (CSP `sandbox` ไม่มี `allow-same-origin`) และ cookie ว่าง ทั้งตอนเปิดใน iframe และตอนเปิด URL ของ API ตรงๆ ในแท็บ |
| observatory แบบ live (`/litstorm/api/runs/{id}/observatory`) | DevTools: `fetch("https://example.org")` | ถูก CSP `connect-src 'self'` บล็อก |


**ผลของ Task 7 (Edge, stack audit, บัญชีทดสอบ, ดัก `dialog` ทุกหน้า):** ไม่มี alert เลยทั้งผู้ใช้และผู้ดูแล ไม่มีองค์ประกอบ `img[src=x]`, `svg[onload]` หรือ attribute `onerror`/`onload` เกิดขึ้นในหน้าไหน (สคริปต์ `server/tests/audit/odd_inputs.py xss`, ภาพ `shots/t7-xss-*.png`)

| ข้อ | ผล |
|---|---|
| ชื่อ Project, หัวข้อ, ข้อความ Co-STORM (`<img src=x onerror=alert(1)>"><svg onload=alert(1)>`) | แสดงเป็นตัวอักษรใน: หน้าแรก, sidebar "ล่าสุด", `/projects`, หน้า Project, `/research`, หน้า Session, การ์ด Run ที่ล้ม, ถังขยะ (Project ที่ลบแล้ว), หน้ารายงาน (หัวเรื่อง, สารบัญ, breadcrumb), หน้า Discussion (ชื่อบทบาทและข้อความของผู้ใช้ที่ฉีดใน `discussion.json`) `<title>` ของเว็บเป็น "DeepLit" เสมอ `<title>` ของ observatory เป็นข้อความที่ escape แล้ว ("Observatory — &lt;img ...") |
| markdown ของรายงาน (`[x](javascript:alert(1))`, `<img onerror>`, `<script>`, รูปที่ alt มี `[1]`, source ที่ `url` เป็น `javascript:`) | หน้ารายงาน: ไม่มีลิงก์ `javascript:` สักตัว HTML เป็นตัวอักษร ลิงก์ source ไม่ถูกทำ export HTML: ไม่มี `href="javascript:`, source ที่ url เป็น `javascript:` ได้ `href="#"` (`javascript:alert(document.domain)` ปรากฏเป็นข้อความ) observatory: ไม่มีลิงก์ของ source นั้น **พบ 2 เรื่องใหม่:** รูปจาก URL ภายนอกถูกเบราว์เซอร์ขอจริง (SEC-12) และเลขอ้างอิงใน alt ทำ `<img>` เสีย (BUG-57) |
| หน้า interactive เปิดตรงในแท็บ | `fetch("/litstorm/api/me")` → `TypeError` (ถูกบล็อก) และ `document.cookie` → `SecurityError: The document is sandboxed and lacks the 'allow-same-origin' flag` |
| observatory แบบ live | `fetch("https://example.org")` → `TypeError` (CSP `connect-src` บล็อก) |
| หน้าสถานะระบบ (ผู้ดูแล) | ไม่แสดงหัวข้อหรือชื่อ Project ของผู้ใช้เลย (`/api/admin/monitor` ไม่มีสตริง `onerror` หลังมี Run ล้มที่หัวข้อเป็น payload) จึงไม่มีที่ให้ฉีด |
| ไม่ได้ตรวจ | หน้า interactive ใน iframe (หน้ารายงานของเว็บไม่ได้ฝัง frame ในรอบนี้ ไม่พบ frame ให้ตรวจ) ตรวจเฉพาะตอนเปิดตรง ซึ่งคือ origin และ CSP ชุดเดียวกัน |

---

## สงสัย (ยืนยันไม่ได้ในรอบนี้)

1. **key ที่ผู้ให้บริการพูดซ้ำกลับมาอาจโผล่ในหน้า Run ของผู้ใช้:** หน้าสถานะระบบตัดข้อความที่หน้าตาเหมือน key ออกก่อนแสดง (`server/src/litstorm/monitor.py:30-31,66-71`) แต่ `GET /api/runs/{id}` ส่ง `run.message` ดิบให้เจ้าของ Run (`server/src/litstorm/api/research.py:396`) และเจ้าของที่เป็นผู้ใช้ทั่วไปไม่ควรเห็น key ของระบบ ยังไม่เจอผู้ให้บริการที่ DeepLit ใช้ซึ่งพูด key ซ้ำเต็มๆ (OpenAI ปิดบางส่วน, OpenRouter/Tavily/Gemini ไม่พูด) และ log ของ stack audit ยังไม่มี Run: นับ pattern ของ key ใน `docker logs` ของ api, worker, web, edge ได้ 0 ทั้งหมด → ให้ Task 5 นับ pattern เดียวกันใน log, `run.message` ทุกแถว และ `stderr.log` ของทุก Run หลังลองทุกโหมด รวมกรณี key ผิด
2. **login พร้อมกันจำนวนมากอาจกินหน่วยความจำจนล่ม:** argon2 ใช้ 64 MiB ต่อการตรวจหนึ่งครั้ง api มี 2 process แต่ละตัวรัน handler แบบ sync ใน threadpool (ราว 40 thread) การยิง login พร้อมกันด้วยอีเมลที่มีอยู่จริง (ดู SEC-08) จึงอาจใช้หน่วยความจำหลาย GB ยังไม่ได้วัดภายใต้โหลด จะหายไปเองถ้าแก้ SEC-03
3. **ลิงก์ export ติดอยู่ใน access log ของ nginx:** `GET /api/exports/{token}` มี token ใน path nginx ของ 203 จด URL เต็ม ลิงก์อายุ 15 นาที (`server/src/litstorm/exports.py:22`) และใช้ได้ซ้ำในเวลานั้น ใครอ่าน log ได้ภายใน 15 นาทีก็โหลดรายงานได้ ความเสี่ยงต่ำ ไม่ได้ดู log ของ 203

---

## ตัดทิ้ง (ตรวจแล้วไม่เป็นปัญหา หรือเป็นการออกแบบที่ตั้งใจ)

- **session fixation:** login และตั้งรหัสผ่านออก token ใหม่ทุกครั้ง (`auth.py:33-52`) ค่าที่ฝังไว้ก่อนจึงใช้ไม่ได้ (ยกเว้นกรณีแอปบน origin เดียวกัน ซึ่งรวมไว้ใน SEC-04)
- **CSRF:** ทุก route ที่แก้ข้อมูลผ่าน `current_user` ซึ่งเทียบ header `X-CSRF-Token` กับ token ของ session (`deps.py:93-101`) ส่วนที่ไม่ผ่าน (setup, login, logout, ตั้งรหัสผ่าน) รับ JSON เท่านั้น ฟอร์มจาก site อื่นส่ง JSON ไม่ได้ (FastAPI ไม่อ่าน body ที่เป็น `text/plain` เป็น JSON) และ `SameSite=Lax` ไม่ส่ง cookie กับ POST ข้าม site
- **ลิงก์ตั้งรหัสผ่าน:** token 32 ไบต์ เก็บเป็น SHA-256, อายุ 24 ชั่วโมง, ใช้ครั้งเดียว, ออกใหม่แล้วลิงก์เก่าตาย, อยู่หลัง `#` จึงไม่ไปถึง server หรือ log, ปิดบัญชีแล้วลิงก์ตาย (`auth.py:55-68,216-255`, `admin.py:147-150`)
- **การปิดและลบบัญชี:** ปิดแล้ว session, ลิงก์ และ token ใช้ไม่ได้ (`deps.py:88`, `tokens.py:128`) ลบได้เฉพาะบัญชีที่ไม่มีงาน และลบตัวเองไม่ได้
- **path traversal ใน `runs_dir` และ export:** ทุก path ประกอบจาก `run.id` ที่เป็น UUID ซึ่ง FastAPI ตรวจรูปแบบแล้ว (`api/research.py:1068,1142,1291`), `state_from` ของ Co-STORM มาจาก server เอง (`worker/queue.py:150`), ชื่อไฟล์ export ถูกกรองอักขระและใส่ใน `filename*=` แบบ percent-encode (`api/research.py:1080-1089,1403`)
- **token ของลิงก์ export:** HMAC-SHA256 ด้วย key ที่แยกจาก key หลัก (`exports.py:41-47`), เทียบแบบ constant-time, อายุ 15 นาที, ตรวจซ้ำว่าเจ้าของยังใช้งานและงานยังสำเร็จ (`api/research.py:1366-1389`) ตามที่ ADR ออกแบบไว้ (ดู "สงสัย" ข้อ 3)
- **XSS ในเว็บแอป:** `dangerouslySetInnerHTML` มีแค่ 3 ที่: โลโก้ (SVG คงที่) และ markdown ของรายงานผ่าน `markdown-it` ที่ปิด HTML (`web/src/pages/report.tsx:65`) การแทน `[n]` ด้วยปุ่มหลัง render ทำให้ attribute ขาดได้แต่ใส่ได้แค่ข้อความคงที่ ไม่มีช่องให้ใส่ event handler · `href` จากข้อมูล (แหล่งอ้างอิง, URL ที่ Agent อ่าน) ผ่าน React 19 ซึ่งบล็อก `javascript:` เอง
- **XSS ใน export และหน้า HTML ของ server:** export HTML escape ทุกค่าและกรอง href เป็น http(s) (`render/html.py:376-377`), observatory ใส่ข้อมูลเป็น JSON ที่ escape `<` แล้วแสดงด้วย `textContent` และกรองลิงก์ (`render/observatory.py:184-199`, `observatory.html:721`) หน้า interactive และ service page ส่ง CSP `sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox` และ iframe ก็มี `sandbox` เดียวกัน (`api/research.py:1252,1255-1303`, `web/src/pages/report.tsx:259,401`) export ทุกแบบส่งเป็น `attachment`
- **PDF เปิดที่อยู่ภายนอก:** Chromium ของ PDF ปฏิเสธทุกคำขอเครือข่าย (`render/pdf.py:39`, `render/interactive.py:605`) รูปจาก markdown จึงไม่ทำให้ api ยิงออกไป
- **SSRF จากที่อยู่ที่ผู้ดูแลตั้ง** (SearXNG, `api_base`, embedding, MRA): ปุ่มทดสอบยิงไปที่อยู่ใดก็ได้ และตอบส่วนของคำตอบกลับมาบ้าง (ชื่อผลค้นหา, ข้อความ error 200-300 ตัวอักษร: `checks.py:19-21`, `embedding.py:145`, `medical.py:108-109`) แต่ผู้ดูแลต้องใส่ที่อยู่ภายในได้อยู่แล้ว (`http://searxng:8080`, Ollama ที่ `host.docker.internal`) จึงเป็นการออกแบบ ส่วนที่เป็นปัญหาจริงคือ key ไปด้วย (SEC-05) · `file://` ใช้ไม่ได้ทั้งใน requests, httpx และ aiohttp
- **STORM, Co-STORM, Deep อ่านหน้าเว็บเอง:** ไม่ใช่ retriever ของ STORM ที่ DeepLit ใช้ (SearXNG, Tavily, arXiv, TCI) อ่านเฉพาะผลค้นหา `WebPageHelper` ที่อ่านหน้าเว็บใช้เฉพาะ Bing/You · Deep ค้นผ่าน Tavily หรือ bridge ของเรา
- **การเข้ารหัส key ที่เก็บ:** Fernet ด้วย key จาก Docker secret (`security.py:53-75`, `settings.py`), หน้าผู้ดูแลเห็นแค่ 4 ตัวท้าย, `Secrets` ซ่อนตัวเองใน repr (`engines/base.py:81`), Run ได้ key ทาง stdin ไม่ลงดิสก์, Deep CLI ได้ env ของตัวเองที่ไม่มีของ Worker (`engines/deep/engine.py:88-97`)
- **token ของ MCP:** สุ่ม 32 ไบต์ เก็บเป็น SHA-256, ปฏิเสธเมื่อหมดอายุ/เพิกถอน/บัญชีถูกปิด, ไม่รับ cookie จึงไม่ต้องใช้ DNS-rebinding guard ตามที่เขียนไว้ (`api/mcp.py:496-499`) ขีดจำกัด 60 ครั้งต่อนาทีนับต่อ process (2 process ได้เกือบสองเท่า) ถือว่ารับได้
- **ไฟล์ลับใน git:** `stack/secrets/`, `*.env` อยู่ใน `.gitignore` และไม่มีใน `git ls-files` หรือในประวัติ; secret scanner ของ skill `senior-security` เจอแค่ค่าในเทสต์และ hash ใน `package-lock.json`
- **`EmailStr` ปฏิเสธ `.local`:** ไม่ใช่เรื่องความปลอดภัย (ตามที่ Task 1 แจ้ง)

---

## ข้อจำกัดของเทสต์ (จากผู้ตรวจทาน รวมใน Task 12)

- **SEC-02:** เทสต์ครอบทาง `scrape_urls` ส่วนทาง `crawl_website` (และ redirect) ยืนยันจากการอ่านโค้ด การลองจริงใน Task 5 ไม่ได้ยืนยัน (ดูหัวข้อ SEC-02) การแก้ใน fork ต้องมีเทสต์ของ crawl ด้วย
- **SEC-06:** เทสต์อ่าน `web_search.ssl_context` ตรงๆ ถ้าการแก้เปลี่ยนชื่อหรือเอาตัวแปรนี้ออก เทสต์จะล้มด้วย `AttributeError` ซึ่ง `raises=AssertionError` รายงานเป็นล้มจริง ให้ปรับเทสต์พร้อมการแก้
- **SEC-08:** เทสต์ขอ fixture `admin` ที่ไม่ได้ใช้ (ไม่มีผลต่อผล)
- **SEC-09:** regex ที่อ่าน `web/nginx.conf` หา `add_header` ทีละบรรทัด ถ้าการแก้เขียน header ยาวหลายบรรทัด เทสต์อาจยังล้มทั้งที่แก้แล้ว ให้ตรวจด้วย `curl -I` ประกอบ

## ขอบเขตและคำสั่งที่ใช้

- อ่านโค้ด: `server/src/litstorm` (api/*, security, settings, checks, embedding, medical, exports, monitor, tokens, runner, worker, engines, render/*), fork ของ Agent ใน `server/.venv` (เทียบกับ `../agents-deep-research` แล้วตรงกัน), `knowledge_storm/rm.py`, `knowledge_storm/utils.py`, `web/src` (ค้น `dangerouslySetInnerHTML`, `href=`, `innerHTML`), `web/nginx.conf`, `stack/edge/nginx.conf`, `stack/compose*.yml`, `server/Dockerfile`, `web/Dockerfile`, `stack/host/apply-nginx.sh`, `docs/deploy/HOST-203.md`
- HTTP โดยไม่ login ต่อ stack audit: `curl -I` ของหน้าเว็บและ API, login ผิด 50 ครั้งด้วย `audit-brute@example.org` (บัญชีไม่มีอยู่ ไม่ได้ตั้งค่าครั้งแรก)
- `npm audit --omit=dev` ใน `web/`, `uv run --with pip-audit pip-audit` ใน `server/` (ไม่ได้เพิ่มเข้า project)
- นับ pattern ของ key ใน `docker logs` ของ container ใน `litstorm-audit` (ได้ 0 ทุกตัว ไม่ได้พิมพ์บรรทัดใด)
- เทสต์: `uv run pytest tests/test_audit_findings.py -q --runxfail` เพื่อดูว่าแต่ละข้อล้มด้วยเหตุที่ถูก แล้วรันแบบปกติ (ทุกข้อ xfail)
