# ผลตรวจความทนทานและการดูแลระบบ (Task 10 ของการตรวจทั้งระบบ 2026-10-24)

ฐานที่ตรวจ: branch `audit/2026-10-24` (HEAD `bbcbcd5`) · สเปกส่วน 4 "ความทนทานและการดูแลระบบ" · **ตรวจจากไฟล์ล้วน** (ไม่ได้สั่ง docker และไม่ได้เข้า 203 ตามข้อจำกัด) จึงไม่มีข้อไหนที่อ้างตัวเลขการใช้ทรัพยากรจริง · ที่ตรวจ: `stack/compose.yml`, `compose.mirror.yml`, `compose.host.yml`, `compose.agenta.yml`, `stack/mra/compose.host.yml`, `stack/edge/nginx.conf`, `stack/host/apply-nginx.sh`, `stack/backup.sh`, `stack/mra/backup-mra.sh`, `stack/build-images.sh`, `server/Dockerfile`, `web/Dockerfile`, `web/nginx.conf`, `.github/workflows/*`, `docs/deploy/HOST-203.md`, `docs/acceptance/2026-10-23-host-203.md` และ compose ของ MRA ที่ commit `e7a8b01` ซึ่ง `stack/engines.lock.json` pin ไว้ (อ่านอย่างเดียว)

ข้อที่เป็นของรายงานอื่นแล้ว ไม่ซ้ำที่นี่: SEC-09/SEC-10 (header, ลดสิทธิ์ container, network `agenta-mcp`, รหัสผ่าน Postgres ตายตัว) และ BUG-47 (`backup.sh` นับตารางเกินจริง)

## สรุป

ไม่มีข้อระดับ **วิกฤต** · **สูง** 2 ข้อ (OPS-01, 02) · กลาง 6 ข้อ (OPS-03 ถึง 08) · ต่ำ 6 ข้อ (OPS-09 ถึง 14)

ภาพรวม: ส่วนที่ทำไว้ดีแล้วมีมาก (หมุน log, restart policy, pin digest ของ image ที่ขึ้น host, ซ้อม nginx และ backup บนเครื่อง dev ก่อน) ช่องที่เหลือส่วนใหญ่คือ **ทางถอยและทางกู้ที่ยังไม่เคยลองจริงบน host**, **ไม่มีอะไรเฝ้าหลัง 24 ชั่วโมงแรก** และ **ไม่มีเพดานทรัพยากรบนเครื่องที่ใช้ร่วมกับแอปอื่น** ข้อที่ต้องจัดการก่อนรอบขึ้น 203 ถัดไปคือ OPS-01 (รอบหน้ามี migration 0014 ที่ทำให้ทางถอยใน §7 ใช้ไม่ได้)

**เกณฑ์ระดับ** ตามสเปก: **วิกฤต** ข้อมูลรั่วหรือระบบใช้ไม่ได้ · **สูง** กระทบผู้ใช้จริงบ่อย หรือต้องมีเงื่อนไขบางอย่างก่อน แต่ผลหนัก · **กลาง** · **ต่ำ** ข้อ OPS-01 และ 02 ให้ **สูง** เพราะเป็นทางถอยและทางกู้ซึ่งเป็นด่านสุดท้ายเมื่อเกิดเหตุ แม้ยังไม่เคยเกิดเหตุ ส่วนข้อกลางลงมาไม่มีเหตุที่เกิดแล้ว เป็นความเสี่ยงที่สะสม

| รหัส | ระดับ | เรื่อง | ผู้ใช้เห็นไหม | หลักฐาน |
|---|---|---|---|---|
| OPS-01 | **สูง** | ถอย image (§7) ไม่ได้ เมื่อรอบใหม่มี migration: api เก่าไม่ขึ้น (รอบหน้ามี 0014) | ใช่ (ตอนเกิดเหตุ: เว็บล่ม) | ลองจริงด้วย alembic + อ่านไฟล์ |
| OPS-02 | **สูง** | สำรองข้อมูลอยู่ดิสก์เดียวกับข้อมูล สำเนานอก host ไม่มีหลักฐานว่าทำ `secret_key` ไม่ถูกสำเนา และยังไม่ซ้อมกู้บน host | ใช่ (ตอนเกิดเหตุ: ข้อมูลทั้งหมดหาย) | อ่านไฟล์ + acceptance |
| OPS-03 | กลาง | api, worker, web ไม่มี healthcheck และ `depends_on` รอแค่ "started" | ใช่ (ช่วงอัปเดต/reboot, process ค้างไม่ถูก restart) | อ่านไฟล์ |
| OPS-04 | กลาง | ไม่มีเพดาน RAM/CPU/pid ให้ container ใดเลย และ export PDF เปิด Chromium ต่อคำขอโดยไม่จำกัดจำนวน บนเครื่องที่ใช้ร่วมกับแอปอื่น | ใช่ (ถ้าเกิด: แอปอื่นบน 203 ก็ล่ม) | อ่านไฟล์ (ยังไม่ได้วัด) |
| OPS-05 | กลาง | ไม่มีการเฝ้าและแจ้งเตือนหลัง 24 ชั่วโมงแรก: backup ล้ม, ดิสก์เต็ม, container ตาย ไม่มีใครรู้จนผู้ใช้บอก | ใช่ | อ่านไฟล์ |
| OPS-06 | กลาง | ดิสก์เต็มช้าๆ: image เก่าสะสมรอบละราว 7 GB ไม่มีขั้นลบ และ backup เต็มทุกคืน 30 ชุดบนดิสก์เดียวกัน | ใช่ (ตอนเต็ม: ระบบหยุด) | อ่านไฟล์ |
| OPS-07 | กลาง | CI ไม่รันเทสต์ใดๆ ก่อน build image ที่ขึ้น host | ไม่ | อ่านไฟล์ |
| OPS-08 | กลาง | `backup.sh --restore`: ไม่มีด่านยืนยัน ค่าตั้งต้นคือ production ลบ volume ก่อนรู้ว่า pg_restore ผ่านไหม และ dump ที่ขาดกลางทางค้างเป็นไฟล์ | ใช่ (ผู้ดูแล) | อ่านไฟล์ |
| OPS-09 | ต่ำ | image ที่ไม่ได้ pin digest: postgres, caddy (gateway), python, node, nginx, alpine | ไม่ | อ่านไฟล์ |
| OPS-10 | ต่ำ | ที่ stack ในเครื่องต่างจาก 203 จน "ผ่านในเครื่อง" ไม่ได้แปลว่าผ่านบน 203 (fork ไม่ pin, ไม่มี TLS, embedding, เส้นทางไป MRA) | ไม่ | อ่านไฟล์ |
| OPS-11 | ต่ำ | workflow ของ GitHub: ชื่อ tag ลงใน shell โดยตรง, action ไม่ pin, workflow ของ upstream ที่มี `PYPI_API_TOKEN` ค้างอยู่ | ไม่ | อ่านไฟล์ |
| OPS-12 | ต่ำ | ความปลอดภัยของไฟล์พึ่ง `/home/search` เป็น 750 ทางเดียว: secret 664, dump 664 และสำเนาบนเครื่องผู้ดูแลไม่เข้ารหัส | ไม่ | อ่านไฟล์ + runbook |
| OPS-13 | ต่ำ | ไม่เคยซ้อม reboot ของ host; ข้อสังเกตระดับ host (inotify 128, network ภายนอก, เขตเวลาไม่ถูกบันทึก) | ไม่ | อ่านไฟล์ + acceptance |
| OPS-14 | ต่ำ | runbook เขียนไม่ตรงกับของจริงบางจุด และไม่มีด่านตรวจว่า host.env เป็น digest | ไม่ | อ่านไฟล์ |

---

## OPS-01 — ถอย image (§7) ไม่ได้เมื่อรอบใหม่มี migration

| | |
|---|---|
| ด้าน | การอัปเดตและทางถอย |
| ระดับ | **สูง** (ทางถอยที่ runbook ให้ไว้ใช้ไม่ได้ในรอบหน้าแน่นอน ผลคือเว็บล่มจนกว่าจะกู้จาก backup) |
| ผู้ใช้เห็นไหม | ใช่ ตอนเกิดเหตุ (ผู้ดูแลต้องเปลี่ยนวิธีถอย ผู้ใช้เห็นเว็บล่ม) |
| หลักฐาน | `docs/deploy/HOST-203.md:290` ("image รอบใหม่มีปัญหา: ใส่ digest ของรอบก่อนกลับใน `stack/host.env` แล้ว `$COMPOSE up -d`") · `server/Dockerfile:76` (`CMD ... alembic upgrade head && exec uvicorn ...` ตัว api ทุกครั้งที่ขึ้น) · `server/src/litstorm/migrations/versions/0014_drop_support_grants.py` (รอบหน้า: `drop_table("support_access")` และ `drop_table("support_grants")`) · ไม่มีคำว่า `downgrade` ใน HOST-203.md · 203 อยู่ที่ `0013` ตาม `docs/acceptance/2026-10-23-host-203.md` |

**ลองจริง:** ทำ DB ที่ `alembic_version = '0014'` แล้วให้ alembic ที่มี script แค่ถึง `0013` รัน `upgrade head` (สคริปต์ชั่วคราว ไม่เกี่ยวกับ docker) ได้ `CommandError: Can't locate revision identified by '0014'` เพราะ `sh -c "alembic upgrade head && exec uvicorn"` ใช้ `&&` api เก่าจึงออกก่อนถึง uvicorn แล้ว `restart: unless-stopped` วนซ้ำ ส่วน web ยังขึ้นแต่ตอบ 502

**สถานการณ์:** ผู้ดูแลขึ้นรอบหน้า (migration 0014 ลบตารางสิทธิ์ช่วยตรวจ) แล้วเจอปัญหาที่ไม่เกี่ยวกับ DB ทำตาม §7 ใส่ digest เดิมกลับ → api ขึ้นไม่ได้ เว็บ 502 ต้องหาวิธีเองกลางเหตุ ทางที่ไม่ผิดคือ `alembic downgrade 0013` ด้วย image **ใหม่** ก่อนสลับ (downgrade 0014 → 0013 ลองแล้วใช้ได้บน stack `litstorm` ที่ :8095 ตามบันทึกในสเปกส่วน "การตัดสินใจของผู้ลงมือ" ข้อ 1) แต่ downgrade นี้สร้างตารางเปล่า สิทธิ์เดิมไม่กลับ ผู้ดูแลจึงต้องรู้ล่วงหน้า ทางอื่นคือกู้จาก backup ซึ่งเสียข้อมูลตั้งแต่จุดนั้น

**วิธีแก้ที่เสนอ:** เพิ่มใน §7 และ §9: ก่อน `$COMPOSE up -d` ด้วย digest เก่า ให้รัน `$COMPOSE run --rm --no-deps api alembic downgrade <เลขของรอบก่อน>` ด้วย image ใหม่ (จด revision ของรอบก่อนไว้ใน `images-history.txt` ข้างๆ digest) และบันทึกใน acceptance ของรอบนั้นว่า migration ที่ลบข้อมูลถอยแล้วเสียอะไร ขนาด: **เล็ก** (แก้เอกสาร 2 ย่อหน้า ซ้อมครั้งเดียวบน stack ทิ้งได้)

---

## OPS-02 — สำรองข้อมูลอยู่ดิสก์เดียวกับข้อมูล และทางกู้ยังไม่เคยลองบน host

| | |
|---|---|
| ด้าน | backup และ restore |
| ระดับ | **สูง** (ถ้าดิสก์ของ 203 เสียหรือถูกลบ ข้อมูลผู้ใช้ทั้งหมดและ backup หายพร้อมกัน) |
| ผู้ใช้เห็นไหม | ใช่ ตอนเกิดเหตุ (ข้อมูลงานวิจัยทั้งหมดหาย) |
| หลักฐาน | ดูด้านล่าง |

หลักฐาน:
1. **ที่เก็บ:** `HOST-203.md:35,298` backup ไปที่ `/home/search/Thoughtmind/_litstorm_backup` ซึ่งเป็น host เดียวกับ volume `db-data` และ `run-data` (ไม่มีดิสก์หรือ mount แยก ไม่มีบรรทัดไหนบอกว่าเป็นคนละดิสก์)
2. **สำเนานอก host พึ่งคนทำมือ:** `HOST-203.md:303,321-324` เครื่องผู้ดูแล "ดึงทุกสัปดาห์" ด้วย `scp -r` (Task Scheduler เป็นแค่ "หรือ") ไม่มี cron/ตัวเตือน และ `docs/acceptance/2026-10-23-host-203.md` ไม่ได้ระบุว่าตั้งไว้แล้วหรือดึงสำเร็จครั้งไหน
3. **กุญแจถอดรหัสไม่ถูกสำเนา:** `docs/acceptance/2026-10-23-host-203.md` ("ข้ามโดยเจ้าของ: การสำเนา `secret_key` และ `.env` ของ MRA ออกนอก host") ขัดกับ `HOST-203.md:136,189` ที่สั่งให้ทำ "ทันที" และ backup ไม่เก็บกุญแจโดยตั้งใจ (`stack/backup.sh:27-30`) ถ้า host หาย backup ที่ดึงมาได้จะกู้ได้แต่ API key ทุกตัวต้องกรอกใหม่ (OpenRouter, บริการค้นหา, key ของ MRA ที่ผูกกับ `LLM_KEYS_SECRET`)
4. **ยังไม่ซ้อมกู้บน host:** `HOST-203.md:326` ช่องตรวจยังว่าง (`- [ ]`) ผลตรวจรับ §8 ระบุแค่ "สำรองข้อมูลด้วยมือผ่านทั้งสอง stack" ที่ซ้อมกู้แล้วคือบนเครื่อง dev (`HOST-203.md:16,27`) และบน stack audit (BUG-47 ระบุว่า restore ผ่าน)
5. **cron ยังยืนยันไม่ได้:** ตารางผลตรวจรับ ("ทุกคืน 04:00 และ 04:05") บอกว่าตั้งแล้ว แต่ไม่มีหลักฐานว่า cron เคยสร้างไฟล์ (บรรทัด `backup.log` หรือรายการไฟล์)
6. **ความถี่:** ฐานข้อมูลกู้ได้ถึงคืนก่อนหน้า (ไม่มี WAL/PITR) สำเนานอก host เก่าได้ถึง 7 วัน นี่เป็นการตัดสินใจที่จดไว้ (§8) จึงไม่นับเป็นข้อผิด แต่ควรให้เจ้าของรับรู้เป็นตัวเลข

**วิธีแก้ที่เสนอ:**
- ขั้นต่ำ: สำเนา `secret_key` และ `.env` ของ MRA เข้า password manager ตอนนี้ (นาทีเดียว) แล้วติ๊กใน runbook
- ตั้งให้เครื่องผู้ดูแลหรือเครื่องอื่นดึงอัตโนมัติ (Task Scheduler หรือ `rsync` ใน cron ของเครื่องที่สอง) แทนการพิมพ์เอง และให้คัดเฉพาะไฟล์ใหม่ ไม่ `scp -r` ทั้งโฟลเดอร์ซ้ำทุกสัปดาห์
- ซ้อมกู้บน host ตาม `HOST-203.md:326` หนึ่งครั้งและบันทึกผลใน `docs/acceptance/` (ดูคำเตือนในข้อ OPS-08 ก่อนซ้อม)
- ยืนยัน cron: `crontab -l` และ `tail ../_litstorm_backup/backup.log` แล้วจดผล
ขนาด: **เล็ก-กลาง** (ครึ่งวัน ส่วนใหญ่คือแตะ host ซึ่งงานนี้ทำไม่ได้)

---

## OPS-03 — ไม่มี healthcheck ของ api/worker/web และ `depends_on` รอแค่ "started"

| | |
|---|---|
| ด้าน | health check และการเริ่มลำดับ |
| ระดับ | กลาง |
| ผู้ใช้เห็นไหม | ใช่ (process ที่ค้างโดยไม่ตายไม่ถูกพา restart ผู้ใช้เห็นเป็นหน้าไม่ตอบ; ช่วงอัปเดตเห็น 502 นานกว่าที่ควร) |
| หลักฐาน | `stack/compose.yml:25-28` มี healthcheck เฉพาะ `db` · `:62-63` api รอ `db` แบบ healthy ถูกต้อง · `:74-75` worker `depends_on: api: service_started` พร้อมความเห็น "the api service runs the migrations" · `:86` web `depends_on: [api]` · ไม่มี `healthcheck:` ใน `compose.host.yml`, `compose.mirror.yml`, `stack/mra/compose.host.yml` (gateway) · `/api/health` มีอยู่แล้ว (`server/src/litstorm/api/__init__.py:34-36`) แต่ไม่ได้ถูกใช้ |

**สิ่งที่ตามมา:**
1. `service_started` ไม่ได้แปลว่า migration เสร็จ: ตอน `$COMPOSE up -d` ของรอบอัปเดต worker ตัวใหม่เริ่มทันทีที่ process ของ api เริ่ม (ขณะ `alembic upgrade head` ยังวิ่ง) ถ้ารอบนั้นเพิ่มคอลัมน์ที่ worker อ่าน query แรกจะล้ม และ loop หลักของ worker จบทั้ง process (BUG-01) จึงเห็น `RestartCount` ขึ้นเอง ไม่มีใครเสียหาย แต่ทำให้ตัวเลข "RestartCount = 0" ที่ §4/§6 ใช้ตรวจ ไม่น่าเชื่อถือในรอบอัปเดต
2. `docker ps` บอกแค่ "Up" ไม่บอกว่า api ตอบหรือไม่ และ Docker restart เฉพาะเมื่อ process ตาย ไม่ใช่เมื่อค้าง worker ที่ค้าง (เช่น connection ฐานข้อมูลที่หาย) ไม่มีสัญญาณใดนอกจากหน้าสถานะระบบซึ่งอยู่บน api เอง
3. `docker compose up -d --wait` และ `docker ps` ของ runbook (§3, §9) จึงรอหรือตรวจ "healthy" ไม่ได้

**วิธีแก้ที่เสนอ:** ใส่ใน `stack/compose.yml`
- api: `healthcheck: test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status != 200)"]`, `interval: 15s`, `start_period: 60s` (image ไม่มี curl)
- web: `wget -qO- http://127.0.0.1/` ของ busybox ใน image nginx:alpine (ที่ `__BASE__/` ตอบ 200 ตรวจ path ให้ตรงกับ base path ของ image)
- worker: ไม่มีพอร์ต ใช้ `pg_isready` ไม่ได้ผล ทางสะอาดคือให้ worker แตะไฟล์ใน `/tmp` ทุกรอบ loop แล้ว healthcheck ดูอายุไฟล์ (แก้โค้ด `worker/main.py` เล็กน้อย) หรือข้ามไว้ก่อน
- `worker` และ `web` ใช้ `depends_on: api: { condition: service_healthy }`
ขนาด: **เล็ก-กลาง** (ครึ่งวัน รวมซ้อมบน stack ทิ้งได้ว่ารอบ `up -d` ช้าลงไม่เกินที่ยอมได้)

---

## OPS-04 — ไม่มีเพดานทรัพยากรให้ container และ export PDF ไม่จำกัดจำนวน

| | |
|---|---|
| ด้าน | resource limit บนเครื่องที่ใช้ร่วมกับแอปอื่น |
| ระดับ | กลาง (ยังไม่เคยเกิด และ **ยังไม่ได้วัดการใช้ memory จริง** เพราะห้ามใช้ docker แต่ถ้าเกิดจะกระทบทั้งเครื่อง จึงควรทำก่อนมีผู้ใช้เพิ่ม) |
| ผู้ใช้เห็นไหม | ใช่ (ถ้าเกิด: ทั้ง DeepLit และแอปอื่นบน 203 ช้าหรือถูก kernel ฆ่า process) |
| หลักฐาน | `grep -nE "mem_limit\|cpus\|pids_limit\|deploy:\|resources\|ulimits" stack/*.yml stack/mra/*.yml` ได้ว่าง · `server/src/litstorm/api/research.py:1436-1440` export PDF เรียก `pdf.render` ในคำขอ (เป็น handler แบบ sync จึงรันใน threadpool ของ api) · `server/src/litstorm/render/pdf.py:34-35` เปิด Chromium ใหม่หนึ่งตัวต่อคำขอ ไม่มี semaphore, ไม่มี `limits` ต่อผู้ใช้ (`limits.py` มีเฉพาะ `refinements_per_day`, `visuals_per_day`) · RAM ต่อ Run ราว 275-520 MB (`docs/benchmarks/2026-09-30-concurrency.md:21`) และค่าตั้งต้น "Run พร้อมกัน" = 6 (`HOST-203.md:70`) · RAM และ core ของ 203 ที่วัดตาม §0 (`HOST-203.md:68`) **ไม่ได้ถูกบันทึกไว้** ใน acceptance จึงไม่รู้ว่าค่า 6 เหมาะกับเครื่องนั้นไหม |

**สถานการณ์:**
- ผู้ใช้หลายคนกด export PDF พร้อมกัน (หรือสคริปต์วนเรียก) แต่ละคำขอเปิด Chromium คนละตัวใน container ของ api (Chromium หนึ่งตัวปกติหลายร้อย MB) threadpool ของ api มีราว 40 thread ไม่มีอะไรหยุดไว้ก่อน RAM หมด ผู้ใช้ที่ login แล้วเท่านั้นทำได้
- เมื่อ RAM หมด OOM killer เลือก process ที่ใหญ่ที่สุดของ**ทั้งเครื่อง** ซึ่งอาจเป็นแอปอื่นที่อยู่ 203 (DeepWitya, HIS Mapping, Agenta, TCI) ไม่ใช่ DeepLit
- ฝั่งเครื่อง dev เจอเรื่องนี้แล้ว: BUG-48 (เทสต์ล้มเมื่อ process ลูกจองหน่วยความจำไม่ได้) และ commit memory ต่ำ

**วิธีแก้ที่เสนอ:**
- ใส่ `mem_limit` ให้ worker (เช่น = RAM ที่ §0 คำนวณให้ lit-storm ตามตาราง) และ api (เช่น 2 GB), db เหลือไว้ไม่ตั้ง หรือตั้งสูง และใส่ `pids_limit` เพื่อกัน fork ระเบิด เมื่อ container ชนเพดาน Docker ฆ่าเฉพาะ container นั้นแล้ว `restart: unless-stopped` พากลับมา
- จำกัด export PDF พร้อมกันด้วย `threading.BoundedSemaphore(2)` ครอบ `pdf.render` (ขอเกินให้รอหรือตอบ 429) · ขนาด: เล็ก
- บันทึกผล `free -m && nproc && df -h` ของ 203 ลง acceptance แล้วตรวจว่า "Run พร้อมกัน" ไม่เกินตารางใน `HOST-203.md:76-80`
ขนาดรวม: **เล็ก-กลาง** (ครึ่งวัน; ค่า `mem_limit` ที่เหมาะต้องวัดบน stack ทิ้งได้ก่อนตั้ง)

---

## OPS-05 — ไม่มีการเฝ้าและแจ้งเตือนหลัง 24 ชั่วโมงแรก

| | |
|---|---|
| ด้าน | การเฝ้าระวัง |
| ระดับ | กลาง |
| ผู้ใช้เห็นไหม | ใช่ (ปัญหาถูกพบเมื่อผู้ใช้แจ้ง) |
| หลักฐาน | `HOST-203.md:279-283` §6 เฝ้าด้วยมือ "30 นาทีแรก" และ "24 ชั่วโมง" แล้วจบ · `HOST-203.md:314-315` cron ส่ง output ไป `backup.log` เท่านั้น ไม่มีอะไรอ่านไฟล์นั้น · `server/src/litstorm/monitor.py` ไม่มีการตรวจดิสก์ ตัว worker หรืออายุของ backup (`grep -rniE "disk\|backup" server/src` ได้เฉพาะคอมเมนต์ที่ไม่เกี่ยว) · หน้าสถานะระบบอยู่บน api จึงบอกอะไรไม่ได้เมื่อ api เองตาย · งานรอบสองของหน้าสถานะระบบ (เช็กสุขภาพ, แจ้งเตือนออกนอกระบบ) ยังไม่ทำ (`system-monitor-plan.md`) |

**สิ่งที่ไม่มีใครรู้จนกว่าจะมีคนบอก:** backup คืนไหนล้ม (docker หยุดตอบ, ดิสก์เต็ม, `pg_dump` ล้ม) · ดิสก์ใกล้เต็ม (OPS-06) · worker ตายหรือค้างทั้งที่ api ปกติ · MRA ไม่ตอบ (เห็นเฉพาะตอนมีคนสั่ง Medical Review) · cert ของ nginx หมดอายุ (เป็นของ host)

**วิธีแก้ที่เสนอ:** ทำตามแผนรอบสองของหน้าสถานะระบบ แต่ให้ครอบสามเรื่องที่ดึงจากข้างนอกได้ง่าย: (1) probe จากภายนอกทุก 5 นาทีไปที่ `https://203.185.144.41/litstorm/api/health` (บริการ uptime ฟรี หรือ cron บนเครื่องผู้ดูแล) (2) cron backup ให้เขียนไฟล์สถานะ/ส่ง ping ปลายทางเมื่อสำเร็จ (healthchecks.io แบบ dead-man switch) และมี `mail`/webhook เมื่อล้ม (3) เช็กอายุ backup ล่าสุดและพื้นที่ว่างของ volume ในหน้าสถานะระบบ ขนาด: **กลาง** (1-2 วัน รวมกับงานรอบสองได้)

---

## OPS-06 — ดิสก์เต็มช้าๆ: image เก่าสะสมและ backup เต็มทุกคืน

| | |
|---|---|
| ด้าน | พื้นที่ดิสก์ |
| ระดับ | กลาง (ขึ้นกับขนาดดิสก์ของ 203 ที่ runbook ไม่ได้บันทึก ถ้าเต็ม Postgres และทุก container บนเครื่องเขียนไม่ได้) |
| ผู้ใช้เห็นไหม | ใช่ (ตอนเต็ม: ระบบหยุด) |
| หลักฐาน | `.github/workflows/images.yml:33` และ `HOST-203.md:60` (image ของ server ราว 7 GB, MRA ราว 3 GB) · `HOST-203.md:60` ต้องว่าง >= 20 GB ตอนเริ่มเท่านั้น · §9 (`:330-352`) `$COMPOSE pull` ได้ image ใหม่ทุกรอบแต่ไม่มีขั้น `docker image prune` ที่ใดใน runbook (`grep -n prune docs/deploy/HOST-203.md` ว่าง) · `stack/backup.sh:118-119` tar ของ `run-data` ทั้ง volume (ยกเว้นแค่ `search-cache`) ทุกคืน ไม่ใช่ส่วนต่าง และเก็บ 30 ชุด (`:136-139`) ที่ดิสก์เดียวกับ volume · `backup.log` (`HOST-203.md:314`) ไม่หมุน (เล็กมาก) |

**ตัวเลข:** ทุกรอบอัปเดตที่เปลี่ยน image เพิ่มราว 7 GB (server) และถ้า MRA เปลี่ยนอีก 3 GB เก่าไม่ถูกลบ ถ้าที่ว่างตอนเริ่มเป็นค่าต่ำสุดที่ runbook ยอม (20 GB) จะเหลือราว 10 GB หลังติดตั้งครั้งแรก และอัปเดตที่เปลี่ยน image server สองรอบก็เต็ม โดยยังไม่นับข้อมูลและ backup ถ้า 203 มีดิสก์ใหญ่กว่า 20 GB มากก็ยืดเวลาได้ แต่ไม่มีค่าจริงให้ดูใน runbook รอบหน้าเปลี่ยน image แน่นอน (มี migration 0014)

**วิธีแก้ที่เสนอ:** เพิ่มท้าย §9 `docker image prune -f` และ `docker image ls` เทียบ digest ใน `images-history.txt` (เก็บไว้ 1 รุ่นสำหรับถอย ลบที่เหลือด้วย `docker rmi <digest เก่า>`) อย่าใช้ `prune -a` บนเครื่องที่ใช้ร่วมกัน เพราะลบ image ของแอปอื่นที่หยุดอยู่ · ให้ `backup.sh` เก็บรายวัน 7 วัน + รายสัปดาห์ 4 สัปดาห์ แทน 30 ชุดเต็ม หรือใช้ `tar --listed-incremental` · บันทึก `df -h /` ลง acceptance และให้ OPS-05 เตือนที่ 80% ขนาด: **เล็ก** (เอกสารและ cron)

---

## OPS-07 — CI ไม่รันเทสต์ใดๆ ก่อน build image ที่ขึ้น host

| | |
|---|---|
| ด้าน | CI/CD |
| ระดับ | กลาง |
| ผู้ใช้เห็นไหม | ไม่ |
| หลักฐาน | `.github/workflows/` มี 3 ไฟล์: `format-check.yml` (black เฉพาะ `knowledge_storm` ซึ่งเป็นแพ็กเกจ upstream, เมื่อ PR เข้า main), `python-package.yml` (สั่งมือ ของ upstream) และ `images.yml` · ไม่มี workflow ที่รัน `pytest` ของ `server/`, `tsc`/`vitest` ของ `web/`, `ruff` หรือ `alembic upgrade head` · `images.yml:20-23` push tag `deploy-*` แล้ว build และ push image ทันที ไม่มี `needs:` ที่เป็นเทสต์ · `docs/deploy/HOST-203.md:93` ให้ tag ที่ commit "ที่ผ่านการตรวจรับแล้ว" ซึ่งเป็นขั้นตอนของคน (รันเทสต์ในเครื่อง) |

**สถานการณ์:** tag ผิด commit, หรือ push tag จากเครื่องที่ยังไม่ได้รันเทสต์ ได้ image ที่ใช้งานไม่ได้ซึ่งขึ้น GHCR พร้อม digest ที่น่าเชื่อถือ ผู้ดูแลที่ทำตาม runbook จะเจอเมื่อขึ้นบน host (หลัง `pull` 7 GB) เท่านั้น เทสต์ชุดนี้ใหญ่ (มี marker `db` ใช้ testcontainers, เทสต์สิทธิ์ถาวรใหม่จากการตรวจครั้งนี้) แต่ไม่มีอะไรรันมันอัตโนมัติเลย

**วิธีแก้ที่เสนอ:** เพิ่ม `.github/workflows/ci.yml` (ทุก PR และ push เข้า main) รัน `uv run pytest -q` ของ `server/` (runner ของ GitHub มี Docker สำหรับ testcontainers; `server/pyproject.toml:42` อ้าง path `../../agents-deep-research` จึงต้อง checkout fork ที่ pin ไว้เหมือน `images.yml:58-70`), `npm ci && npm run build` ของ `web/`, และ `ruff check` แล้วให้ `images.yml` ตรวจว่า commit ของ tag มี CI ผ่านแล้ว (`gh run list --commit`) หรือรันเทสต์เป็น job ก่อน build ขนาด: **กลาง** (ครึ่งถึงหนึ่งวัน)

---

## OPS-08 — `backup.sh --restore` เสี่ยงทำพลาด และ dump ที่ขาดทิ้งไฟล์ค้าง

| | |
|---|---|
| ด้าน | restore |
| ระดับ | กลาง (ต้องมีผู้ดูแลทำพลาดหรือ pg_restore ล้มกลางทาง แต่ผลคือ production ล่มหรือเสียข้อมูล) |
| ผู้ใช้เห็นไหม | ใช่ (ผู้ดูแลที่รัน script; ผู้ใช้เห็นเว็บล่มถ้า restore ล้ม) |
| หลักฐาน | `stack/backup.sh:39` `PROJECT="${PROJECT:-litstorm}"` ค่าตั้งต้นของ `--restore` คือ production และ `:80-103` ไม่มีด่านยืนยัน/ชื่อ stack ที่ต้องพิมพ์ซ้ำ · `:94` หยุด web, worker, api แล้ว `:96-97` `find /d -mindepth 1 -delete` ลบ volume ทั้งก้อน **ก่อน** `:99` pg_restore ถ้า tar หรือ pg_restore ล้ม (`set -e` ออกทันที) api, worker, web ค้างหยุด และไม่มีสำเนาของข้อมูลเดิมก่อนลบ · `:114` `docker exec ... pg_dump > "$DUMP"` ถ้า pg_dump ล้มกลางทาง `set -e` ออกก่อนถึง manifest แต่ไฟล์ `.dump` ที่เขียนไปบางส่วนค้างอยู่ และถูกดึงไป `scp -r` ด้วย `stack/mra/backup-mra.sh:56` เหมือนกัน (`rm -f` ที่ `:59` ใช้เฉพาะกรณี dump อ่านได้แต่ไม่มีตาราง ไม่ใช่กรณี pg_dump ล้ม) · `:101` `docker start worker` ทุกครั้งที่ restore: ตอนซ้อมกู้ตาม `HOST-203.md:326` (stack `litstorm-restoretest`) worker ตัวทดสอบเริ่มพร้อม `stack/secrets/secret_key` ตัวจริงและฐานข้อมูลที่เพิ่งกู้ ถ้าตอนนั้นมี Run สถานะ queued ใน dump มันจะเริ่มเรียก OpenRouter จริงด้วย key ที่ถอดได้ |
| ข้อเสริม | `stack/backup.sh:77,96,118` ใช้ image `alpine` ที่ไม่ pin ต้องดึงจาก Docker Hub ถ้าไม่มีในเครื่อง (ตอน cron 04:00 หรือตอนกู้ภัย; ถ้าทำตาม OPS-06 แล้วลบ image ที่ไม่ใช้ ต้องไม่ลบตัวนี้) |

**วิธีแก้ที่เสนอ:**
- `--restore` ต้องการ `PROJECT` ที่ตั้งชัด (ไม่มีค่าตั้งต้นสำหรับ restore) หรือถามให้พิมพ์ชื่อ project ซ้ำ ยกเว้นเมื่อมี `--yes`
- ก่อน `find -delete` ให้ `pg_restore --list` ผ่านและ tar ทดสอบอ่านได้ก่อน และเก็บ volume เดิมไว้ (เปลี่ยนชื่อ หรือ `tar` ออกไป `_pre-restore-<stamp>`) ถ้า pg_restore ล้มให้ start สามบริการกลับ
- เขียน dump ลงไฟล์ `.part` แล้ว `mv` เมื่อ `tables_in` ผ่าน (และลบ `.part` เมื่อล้มด้วย `trap`)
- ตอนซ้อมกู้ให้ตัด worker (`docker stop` ทันทีหลัง restore หรือ `--no-worker`)
ขนาด: **เล็ก** (ราว 2 ชั่วโมง; `backup.sh` เป็นแค่ bash ซ้อมบน stack ทิ้งได้)

---

## ข้อเล็ก (OPS-09 ถึง OPS-14)

### OPS-09 — image ที่ไม่ได้ pin digest (ต่ำ, ผู้ใช้เห็น: ไม่)

pin ครบแล้ว: image ที่ขึ้น host (`compose.host.yml:19,31,41` ผ่าน `host.env`, MRA ผ่าน `.env`), `searxng` (`compose.yml:92`), `uv` ใน build (`server/Dockerfile:26`) ที่ยังลอย: `postgres:17-alpine` (`compose.yml:14`, ใช้บน host จริง), `caddy:2-alpine` (`stack/mra/compose.host.yml:51`, gateway ของทาง lit-storm → MRA บน host), `nginx:1.29-alpine` (`web/Dockerfile:16`, `compose.mirror.yml:27`), `python:3.12-slim`, `node:24-slim`, `node:24-alpine` (`server/Dockerfile:9,16`, `web/Dockerfile:8`) และ `alpine` ใน `backup.sh` ผลคือ build ซ้ำจาก tag เดิมไม่ได้ image เดิม และ host ที่ถูกติดตั้งใหม่ได้ postgres/caddy รุ่นย่อยอื่น digest ของ image แอปที่ใช้จริงบน host ปลอดภัยอยู่แล้ว (host ไม่ build) ผลกระทบจริงจึงจำกัดที่ db และ gateway · **แก้:** ใส่ `@sha256:` ตามแบบ `searxng` สำหรับ postgres และ caddy พร้อมความเห็นวิธีอัปเกรด · ขนาด: เล็ก

### OPS-10 — จุดที่ stack ในเครื่องต่างจาก 203 (ต่ำ, ผู้ใช้เห็น: ไม่)

ที่ต่างกันระหว่าง stack ในเครื่องกับ 203 (`compose.host.yml` ทั้งไฟล์ซ้อมแล้วบน project `ls203` ตาม `HOST-203.md:12,24-27` และ §4/§5 ของ 2026-10-23 ปิดช่องของ TLS, embedding และ MRA บน host จริงแล้ว ช่องที่ยังเปิดจริงคือแถวแรก)

| เรื่อง | stack ในเครื่อง | 203 | ผล |
|---|---|---|---|
| fork ของ engine | `compose.yml:36-39` build จาก `../../agents-deep-research` และ `../../deep-research-web-ui` ตาม HEAD ที่ checkout อยู่ ไม่ตรวจ pin | `images.yml` build จาก commit ใน `engines.lock.json` และ `build-images.sh:55-69` ปฏิเสธถ้าไม่ตรง | เครื่อง dev ที่ fork ล้ำหน้า pin ผ่านเทสต์ แต่ image บน 203 เป็นอีกรุ่น (ต่างกันเฉพาะเมื่อลืม pin; แก้: `build-images.sh` ตรวจแบบเดียวกันก่อน `compose build` หรือให้ compose ในเครื่องเรียกมัน) |
| HTTPS และ cookie | HTTP ล้วน ไม่ตั้ง `LITSTORM_COOKIE_SECURE` (`compose.mirror.yml`) | TLS ที่ nginx ของ host, `LITSTORM_COOKIE_SECURE=true` (`compose.host.yml:24,35`) | เส้นทางที่เกี่ยวกับ cookie Secure, HSTS และ redirect http→https ซ้อมได้เฉพาะ preview ของ §4 และ §5 บน host |
| nginx ด้านหน้า | `stack/edge/nginx.conf` (ไม่มี `proxy_http_version 1.1`, ไม่มี `X-Real-IP`) | snippet จาก `apply-nginx.sh:71-89` (มีทั้งสอง) บน nginx ที่ใช้ร่วมกับแอปอื่น | ต่างกันเล็กน้อย SSE ของ `/runs/{id}/live` ส่ง comment ทุก 15 วินาที (`api/research.py:932,964`) ต่ำกว่า `proxy_read_timeout 120s` ทั้งสองฝั่ง และ §4 ลองรัน Run จริงผ่าน nginx ตัวเดียวกันแล้ว จึงไม่ถือเป็นข้อบกพร่อง |
| embedding | Ollama ของเครื่อง (`host.docker.internal`, `compose.yml:57-59`) | OpenRouter `baai/bge-m3` (`HOST-203.md:239`) | เส้นทาง embedding ของ Medical/Agent บน 203 ไม่เคยรันบนเครื่อง dev ถ้าไม่ตั้งแบบเดียวกัน (ตรวจใน §4 ครั้งเดียว) |
| ทางไป MRA | `http://host.docker.internal:8088` (MRA ที่รันตรงบนเครื่อง) | `http://mra` ผ่าน gateway บน network `litstorm-mra` (`stack/mra/compose.host.yml:50-61`) | ซ้อมบน dev 2026-10-19 และขึ้นจริงผ่านใน §4 ของ 2026-10-23 ไม่ใช่ช่องว่าง ลงไว้เพื่อให้ครบ |
| ข้อจำกัดเครื่อง | RAM 15 GB, 16 core (`docs/benchmarks/2026-09-30-concurrency.md:7`) | ไม่ได้บันทึก (OPS-04) | ผลโหลดเทสต์ใช้เทียบกับ 203 ไม่ได้จนกว่าจะรู้ค่า |

### OPS-11 — workflow ของ GitHub (ต่ำ, ผู้ใช้เห็น: ไม่)

1. `images.yml:81-84,95-96` ใส่ `${{ steps.tag.outputs.tag }}` (มาจากชื่อ tag) ลงใน `run:` ตรงๆ ชื่อ tag ของ git ใส่ `$`, `(`, `"`, `;` ได้ ผู้ที่ push tag `deploy-*` ได้ (ต้องมีสิทธิ์เขียน repo อยู่แล้ว) จึงสั่ง shell บน runner ที่มี `packages: write` ได้ **แก้:** ส่งผ่าน `env:` แล้วอ้าง `"$TAG"` (บรรทัดเดียวต่อขั้น) และเช็กชื่อ tag ด้วย regex
2. action ที่ใช้ tag ลอย ไม่ pin SHA: `actions/checkout@v4`, `docker/login-action@v3` (`images.yml`), `actions/checkout@v2`, `actions/setup-python@v2`, `psf/black@stable` (`format-check.yml`) ซึ่ง v2 เป็นรุ่นเก่ามาก
3. `python-package.yml` เป็นของ upstream STORM: `actions/checkout@master`, `pypa/gh-action-pypi-publish@release/v1` (branch ลอย) พร้อม `secrets.PYPI_API_TOKEN` เรียกได้ด้วยมือเท่านั้น ถ้า secret ตั้งไว้ จะเป็นช่องส่ง package ภายใต้ชื่อ upstream **แก้:** ลบไฟล์นี้จาก fork

ขนาดรวม: เล็ก

### OPS-12 — ความปลอดภัยของไฟล์พึ่ง `/home/search` เป็น 750 ทางเดียว (ต่ำ, ผู้ใช้เห็น: ไม่)

`HOST-203.md:135` secret ใน `stack/secrets/` เป็น 664 (container ที่ uid 10001 ต้องอ่านได้) และ `:300` ไฟล์ `.tar.gz` เป็น 644 · `stack/backup.sh:114` dump สร้างด้วย umask ของ shell (ตามที่ runbook อธิบาย 0002 → 664) ซึ่งมีรหัสผ่านที่ hash แล้ว อีเมล เนื้อรายงาน และ API key ที่เข้ารหัส · ทั้งหมดปลอดภัยด้วยเหตุผลเดียวคือ `/home/search` เป็น 750 (ตรวจ 2026-10-23) และ user อื่นบนเครื่องเข้าไม่ถึง runbook รับรู้แล้ว แต่ไม่มีอะไรตรวจซ้ำ (เช่น ใน `apply-nginx.sh --check`) · สำเนาที่ `scp` ไปเครื่องผู้ดูแล (`D:\Backups\lit-storm\`, `HOST-203.md:323`) ไม่เข้ารหัส ซึ่งมีข้อมูลผู้ใช้ของ DeepLit ทั้งหมด · **แก้:** `umask 077` ใน `backup.sh` ให้ dump/manifest เป็น 600 (tar ที่ root เขียนตั้ง `chmod 600` หลังเขียนได้) · ใส่ `stat -c %a /home/search` เป็นข้อตรวจใน §0/§9 · เก็บสำเนานอก host ในดิสก์ที่เข้ารหัส (BitLocker) · ขนาด: เล็ก

### OPS-13 — reboot และข้อสังเกตระดับ host (ต่ำ, ผู้ใช้เห็น: ไม่)

วิเคราะห์จากไฟล์: ทุก service มี `restart: unless-stopped` (`compose.yml:15,41,67,83,93`, `compose.mirror.yml:28`, gateway ของ MRA `stack/mra/compose.host.yml:54`, และ MRA เองผ่าน `docker-compose.prod.yml:10` ที่ commit `e7a8b01`) · หลัง reboot Docker เริ่ม container ขนานกันโดย **ไม่ใช้ `depends_on`** (ใช้เฉพาะ `compose up`) api อาจเริ่มก่อน db พร้อม ถ้า `alembic upgrade head` ล้มก็ออก แล้ว restart เองจนกว่า db จะพร้อม (ใช้ได้ แต่ `RestartCount` ขึ้น และ worker ที่ BUG-01 ฆ่า loop ก็ทำนองเดียวกัน) network `litstorm-mra` สร้างมือครั้งเดียว (`HOST-203.md:143`) เป็น external ถ้ามีคนรัน `docker network prune` ตอนไม่มี container เกาะอยู่ `up` จะล้ม "network not found" และ runbook ไม่มีขั้นกู้ · runbook ไม่มีขั้น "reboot ซ้อม" และไม่ตรวจ `systemctl is-enabled docker` (แอปอื่นบนเครื่องเดียวกันน่าจะทำให้เป็นจริงแล้ว แต่ไม่ได้จด) · `HOST-203.md:266` และ acceptance รายงานว่า inotify ของ host เต็ม (เพดาน 128 ของทั้งเครื่อง) ซึ่งกระทบได้ทุกอย่างที่ใช้ inotify เช่น `tail -f`, ตัวเฝ้าไฟล์ในแอปอื่น **แก้ที่เจ้าของ host:** ตั้ง `fs.inotify.max_user_instances=512` ผ่าน sysctl (ต้อง sudo ไม่ทำในงานนี้) · เขตเวลา: container เป็น UTC ทั้งหมด (ไม่มี `TZ` ใน compose) แต่ cron ของ backup ใช้เวลาของ host (`HOST-203.md:298` "04:00 เวลา host") และ runbook ไม่จดว่า host เป็นเวลาไหน · **แก้:** เพิ่มใน runbook: ผลของ `timedatectl`, `systemctl is-enabled docker`, ขั้นซ้อม reboot ครั้งเดียว (ตอนที่ไม่มี Run) และบรรทัด `docker network create litstorm-mra || true` ในขั้นกู้ · ขนาด: เล็ก

### OPS-14 — runbook เขียนไม่ตรงกับของจริงบางจุด (ต่ำ, ผู้ใช้เห็น: ไม่)

1. `HOST-203.md:72` "stack ขณะว่างใช้ RAM ราว 1 GB: api 2 process, db, web, **edge**, searxng และ Worker" บน host ไม่มี `edge` (มีเฉพาะ `compose.mirror.yml`) ตัวเลขนี้วัดบนเครื่อง dev จึงไม่ตรงกับ stack ของ 203
2. `compose.host.yml:19,31,41` ใช้ `${VAR:?...}` ตรวจเพียงว่ามีค่า ไม่ตรวจว่าเป็น digest (`@sha256:`) ซึ่ง runbook ให้ตรวจด้วยมือที่ `HOST-203.md:134` (tag ลอยก็ผ่านและทำให้ "สิ่งที่รันคือสิ่งที่ build จาก tag" ไม่จริง) **แก้:** ขั้น preflight ใน §3/§9: `grep -E '^LITSTORM_(SERVER|WEB)_IMAGE=.*@sha256:[0-9a-f]{64}$' stack/host.env | wc -l` ต้องได้ 2
3. §0 ให้วัดและบันทึกค่า (`free -m`, `nproc`, `df -h`) แต่ acceptance ไม่มีค่าเหล่านั้น (ดู OPS-04, OPS-06)
4. `HOST-203.md:152` คาดว่า migration ปัจจุบันคือ `0014` (ถูกต้องสำหรับรอบหน้า) แต่ผลตรวจรับของ 2026-10-23 เป็น `0013` ผู้ดูแลที่อ่านสองไฟล์ต่อกันอาจสับสนว่าเครื่อง 203 อยู่ที่รุ่นไหน ใส่ "ณ tag นี้" ต่อท้ายเลข

ขนาดรวม: เล็ก (แก้เอกสาร)

---

## ตรวจแล้วไม่มีปัญหา

- **หมุน log:** `compose.host.yml:26-28,37,45,48,53` ใส่ `json-file` `max-size: 10m` `max-file: 5` ให้ครบทั้ง 5 service (api, worker, web, db, searxng) เพดานรวมราว 250 MB และ gateway ของ MRA (`stack/mra/compose.host.yml:55-57`) เช่นกัน MRA เองหมุนครบทุก service ใน `docker-compose.prod.yml:10-16,26-30` ที่ commit `e7a8b01` (ตรงกับ `engines.lock.json` และ working tree สะอาด) stack ในเครื่องและ mirror ไม่ตั้ง แต่ไม่ใช่ที่ที่เก็บข้อมูลจริง
- **restart policy:** `restart: unless-stopped` ครบทุก service ของ lit-storm และ MRA (รวม gateway) ไม่มี service ที่ตายแล้วไม่กลับ
- **health/ลำดับของส่วนที่มีอยู่:** api รอ `db` แบบ `service_healthy` (`compose.yml:62-63`) MRA มี healthcheck ครบ (postgres, redis, searxng, api) และ `depends_on` แบบ `service_healthy` / `service_completed_successfully` (`docker-compose.yml:17,31,66,79-101`) nginx ของ web ใช้ `resolver 127.0.0.11 valid=10s` กับตัวแปรใน `proxy_pass` (`web/nginx.conf:12-13`, `edge/nginx.conf:13-14`) จึงไม่ล้มตอนเริ่มเมื่อ api ยังไม่มา และตามที่อยู่ใหม่หลัง recreate
- **ปิดเครื่องอย่างนุ่มนวล:** worker `stop_grace_period: 20s` และจัดการ SIGTERM (`compose.yml:78`, `worker/main.py:112`) Run ที่ค้างถูกกวาดเป็น interrupted และคืนโควตาตามที่ runbook §9 บอก
- **ลำดับ backup ไม่ชนกัน:** 04:00 (lit-storm) และ 04:05 (MRA) ห่างจาก 03:30 (DeepWitya) และ 03:45 (HIS Mapping) ตามที่วัดแล้ว (`HOST-203.md:298`)
- **retention ของ backup:** `KEEP_DAYS=30` ลบเฉพาะหลังสำเร็จ (`backup.sh:136-139` อยู่หลัง manifest) จึงไม่ลบชุดเก่าทิ้งเมื่อชุดใหม่ล้ม ชื่อ `litstorm-*` ไม่ชน `backup.log` และ `images-history.txt`
- **backup/restore ทำงานจริง:** ซ้อมบนเครื่อง dev 2026-09-30 (ทุกตารางจำนวนแถวตรงกัน login ได้ key ถอดได้ export PDF ได้) และ MRA 2026-10-19 และ Task 4 ของการตรวจนี้ผ่านบน stack audit (ข้อบกพร่องเดียวคือตัวเลข: BUG-47)
- **เขตเวลาของโควตา:** `limits.py:16` ใช้ `ZoneInfo("Asia/Bangkok")` ตรงๆ (`quota.py:13`, `models.py:278`) ไม่พึ่ง `TZ` ของ container หรือเวลาของ Postgres ("ต่อวัน/เดือนของกรุงเทพ" จึงไม่เลื่อนแม้ container เป็น UTC) และ `render/html.py:76` ใช้ `timezone(timedelta(hours=7))` คงที่ซึ่งถูกต้องเพราะไทยไม่มี DST
- **SSE ผ่าน proxy:** `/runs/{id}/live` ส่ง comment ทุก 15 วินาที (`api/research.py:932,964-967`) น้อยกว่า `proxy_read_timeout 120s` ใน web, edge และ snippet ของ host และส่ง `X-Accel-Buffering: no` ผ่านทุกชั้น (`proxy_pass_header` ใน `web/nginx.conf:31`, `edge/nginx.conf:27`)
- **การเปิดพอร์ต:** มีพอร์ตเดียวบน `127.0.0.1` (`compose.host.yml:43-44`) db, searxng ไม่เปิดสู่ host MRA เปิด `127.0.0.1:10345` เดียวและ `ports: !reset []` ให้ postgres/redis/api/web/searxng ใน `docker-compose.prod.yml:20-44`
- **image ที่ขึ้น host pin digest จริง:** `compose.host.yml` ใช้ `${VAR:?...}` บังคับให้ตั้ง และ `pull_policy: missing` ไม่เปลี่ยน image ที่มีอยู่เอง workflow พิมพ์ digest ลง job summary ไม่พิมพ์ secret และใช้เพียง `GITHUB_TOKEN` (`images.yml:86-92`) `build-images.sh` ไม่ยอม build ถ้า fork ไม่ตรง pin หรือ working tree สกปรก (`:55-69`) และตรวจ base path ของ web image หลัง build (`:96-98`)
- **secret ใน compose และ CI:** key และ bootstrap code ส่งเป็น Docker secret (ไฟล์) ไม่ใช่ env (`compose.yml:56,70,100-104`) และ `SEARXNG_SECRET` บน host บังคับตั้ง (`compose.host.yml:52`) `.dockerignore` กัน `*.env`, `.env*`, `stack/secrets/` ออกจาก build context, `.gitignore` ครอบ `stack/secrets/` และ `*.env` ไม่มีค่า secret ใน workflow (ส่วน `POSTGRES_PASSWORD: litstorm` อยู่ใน SEC-10)
- **nginx บน host:** `apply-nginx.sh` สำรองไฟล์ที่ใช้ร่วม ทำทีละ include, `nginx -t` ก่อน reload, คืนไฟล์เดิมเมื่อล้ม และถอยได้ด้วยคำสั่งเดียว (ซ้อม 18 ข้อบน layout แบบ host ตาม `HOST-203.md:26`) `--check` ไม่ต้อง sudo

## สงสัย (ยืนยันไม่ได้จากไฟล์ ต้องดูบนเครื่องหรือลองด้วย docker ที่ใช้ไม่ได้ขณะนี้)

1. **`compose pull` ในรอบอัปเดต** (`HOST-203.md:341`, `$MRA pull` ที่ `:351`) ดึง image ลอยของ db และ gateway ใหม่ด้วยหรือไม่ ขึ้นกับพฤติกรรมของ Compose กับ `pull_policy: missing` ถ้าดึง `up -d` จะ recreate db เมื่อ image เปลี่ยนโดยไม่ตั้งใจ ถ้ายืนยันได้ ข้อ OPS-09 ควรขึ้นเป็นกลาง
2. **`tzdata` ใน image:** `limits.py:16` สร้าง `ZoneInfo("Asia/Bangkok")` ตอน import แต่ `uv.lock` ใส่ `tzdata` เฉพาะ `sys_platform == 'win32'` บน Linux จึงพึ่งไฟล์ของ base image (`python:3.12-slim` ซึ่งเป็น tag ลอย) ตอนนี้ใช้ได้ (Run จริงผ่านบน 203 ตาม acceptance) ถ้า base image รุ่นใหม่ไม่มี api และ worker จะไม่ขึ้นเลย · เสนอ: ใส่ `tzdata` เป็น dependency ปกติใน `pyproject.toml` (บรรทัดเดียว) ยังไม่ลงเป็น OPS เพราะยืนยันด้วย `docker run --rm <image> ls /usr/share/zoneinfo/Asia/Bangkok` ไม่ได้
3. **cron ของ backup บน 203 ติดตั้งและเคยทำงานหรือยัง** และขนาดดิสก์/RAM จริงของ 203 (ข้อมูลที่ทำให้ OPS-02, 04, 06 ชี้ตัวเลขได้)
4. **`docker.service` เปิดเมื่อ boot หรือไม่** (OPS-13)

## วิธีตรวจซ้ำ

- OPS-01: สคริปต์ชั่วคราวที่ใช้ (alembic + sqlite, ไม่ใช่โค้ดโปรเจกต์) ให้ `CommandError: Can't locate revision identified by '0014'` ซ้ำได้โดยสร้าง script directory ที่มีเฉพาะ revision `0013` แล้วตั้ง `alembic_version = '0014'` ก่อน `command.upgrade(cfg, "head")`
- OPS-03, 04, 09: `grep -nE "healthcheck" stack/*.yml`, `grep -nE "mem_limit|cpus|pids_limit|deploy:" stack/*.yml stack/mra/*.yml`, `grep -nE "image:" stack/*.yml stack/mra/*.yml`
- OPS-06: `grep -n prune docs/deploy/HOST-203.md` ว่าง
- OPS-07: `ls .github/workflows` และ `grep -n pytest .github/workflows/*` ว่าง

## ที่ไม่ได้รัน

งานนี้เป็นการอ่านไฟล์ ไม่มีการเปลี่ยนโค้ดหรือ compose จึงไม่ได้รันชุดเทสต์ ไม่ได้ใช้ docker และไม่ได้แตะ 203 (ตามข้อจำกัด) สิ่งเดียวที่รันคือสคริปต์ alembic ชั่วคราวของ OPS-01 ซึ่งอยู่นอก repo
