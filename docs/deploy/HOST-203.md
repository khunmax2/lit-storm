# HOST-203 — lit-storm ขึ้น `/litstorm` บน 203.185.144.41

runbook สำหรับวันขึ้น host ครั้งแรก และรอบอัปเดตหลังจากนั้น ทำตามแบบของ DeepWitya ซึ่งอยู่บน host เดียวกัน (`D:\Vscode\Upstream_Deeptutor\deploy\GO-LIVE.md`) บทเรียนจากรอบนั้นใส่ไว้ในขั้นที่เกี่ยวข้องแล้ว

**ยังไม่ได้ขึ้น** ขึ้นได้เมื่อรุ่นสองผ่านครบบนเครื่อง dev แล้วเท่านั้น (ผ่านแล้ว 2026-09-30, ดู `docs/web-app-implementation-plan.md`) และผู้ดูแลสั่งขึ้นเอง

**หลักคิด**
- host ไม่ build อะไร: pull image ตาม digest ที่ workflow `images.yml` build จาก tag
- ไม่มีขั้นไหนแตะ nginx บน :443 จนถึง §5 และ §5 ถอยได้ในไม่กี่วินาทีด้วยคำสั่งเดียว (§7)
- ถ้า host ไม่ตรงกับที่ runbook เขียน ให้หยุดแล้วแก้ runbook ไม่ใช่แก้ host

**ซ้อมไว้แล้วบนเครื่อง dev (2026-09-30)**
- `stack/build-images.sh` build ทั้งสอง image จาก fork ที่ pin ไว้ และตรวจว่า web image เสิร์ฟใต้ `/litstorm`
- `stack/compose.host.yml` ขึ้น stack จาก image เหล่านั้นได้ พอร์ตเดียวบน loopback, cookie Secure, log หมุนเวียน
- `stack/host/rehearse-nginx.sh` ซ้อม `apply-nginx.sh` ทุกโหมดบน layout แบบ host ผ่าน 18 ข้อ (preview, ปฏิเสธพอร์ตที่มีคนใช้, `nginx -t` ล้มแล้วคืนไฟล์เดิมทุก byte, install, uninstall แล้วไฟล์กลับเหมือนเดิม, แอปอื่นบน :443 ไม่กระทบ)
- `stack/backup.sh` สำรอง stack ที่ใช้ประจำแล้วกู้คืนลง stack ใหม่: ทุกตารางจำนวนแถวตรงกัน, login ได้, API key ถอดได้, รายงานและ Discussion อ่านได้, export PDF ได้

| | ค่า |
|---|---|
| path | `https://203.185.144.41/litstorm/` |
| พอร์ต loopback ของ stack | `10340` (DeepWitya ใช้ 10310/10320/10330) |
| พอร์ต preview บน host | `9443` (8443 เป็นของ Kong ของแอปอื่น) |
| checkout บน host | `/home/search/Thoughtmind/lit-storm` |
| backup บน host | `/home/search/Thoughtmind/_litstorm_backup` |
| Compose project | `litstorm` |
| image | `ghcr.io/khunmax2/lit-storm-server`, `ghcr.io/khunmax2/lit-storm-web` (build สำหรับ `/litstorm`) |

คำสั่ง compose ที่ใช้ทั้งไฟล์ (บน host):

```bash
COMPOSE="docker compose -p litstorm -f stack/compose.yml -f stack/compose.host.yml --env-file stack/host.env"
```

---

## 0. วัดก่อน อย่าเดา (บน host)

```bash
docker compose version                      # ต้อง >= 2.24 (ใช้ !reset)
ss -ltnp | grep -E ':(10340|9443)\s'        # ต้องว่างทั้งคู่
sudo nginx -T 2>/dev/null | grep -n 'litstorm'   # ต้องว่าง: ยังไม่มีใครใช้ /litstorm
sudo nginx -T 2>/dev/null | grep -nE 'ssl_certificate|server_name|listen'   # :443 อยู่ในไฟล์ sansarnnews-ssl, :80 ในไฟล์ ade
df -h / && docker system df                 # ต้องว่าง >= 15 GB (server image ~7 GB)
docker ps --format '{{.Names}}\t{{.Ports}}' | grep -i litstorm   # ต้องว่าง
```

- [ ] ไฟล์ :443 คือ `/etc/nginx/sites-available/sansarnnews-ssl` และ :80 คือ `/etc/nginx/sites-available/ade` ถ้าไม่ใช่ ให้ส่งค่าจริงผ่าน env `SSL=` / `HTTP=` ของ `stack/host/apply-nginx.sh` และแก้ตารางนี้
- [ ] ถ้าพอร์ตไม่ว่าง เลือกเลขใหม่ แล้วใช้เลขนั้นทุกที่ที่เขียน 10340 / 9443
- [ ] ออกอินเทอร์เน็ตได้: `curl -sI https://ghcr.io | head -1` และ `curl -sI https://openrouter.ai | head -1`

---

## 1. ทำจากเครื่อง dev (ไม่ต้องเข้า host)

### 1.1 tag และ image

รอบแรกให้ตั้ง tag ที่ commit ที่ผ่านการตรวจรับแล้ว:

```bash
git tag -a deploy-YYYY-MM-DD -m "..." origin/main
git push origin deploy-YYYY-MM-DD
```

การ push tag `deploy-*` สั่ง workflow `.github/workflows/images.yml` ให้เอง (หรือสั่งมือ `gh workflow run images.yml --ref deploy-YYYY-MM-DD`)

- workflow checkout fork ทั้งสองตาม `stack/engines.lock.json` แล้วเรียก `stack/build-images.sh` ซึ่งไม่ยอม build ถ้า checkout ไม่ตรง pin
- ใช้เวลาราว 15–25 นาที; ดูด้วย `gh run watch --repo khunmax2/lit-storm`
- job summary พิมพ์สองบรรทัดสำหรับ `stack/host.env`: `LITSTORM_SERVER_IMAGE=...@sha256:...` และ `LITSTORM_WEB_IMAGE=...@sha256:...`

- [ ] **ครั้งแรกเท่านั้น:** GitHub → Packages → `lit-storm-server` และ `lit-storm-web` → Package settings → **Change visibility → Public** (ครั้งแรกเป็น private; repo เป็น public และ image ไม่มี secret — ถ้าอยากเก็บ private ต้อง `docker login ghcr.io` บน host ด้วย PAT `read:packages`)
- [ ] ทดสอบ pull จากเครื่อง dev: `docker pull <LITSTORM_WEB_IMAGE>` แล้ว `docker run --rm --entrypoint cat <ref> /etc/nginx/base-path` ต้องได้ `/litstorm`

### 1.2 ย้าย pin ของ fork (เฉพาะเมื่อ fork เปลี่ยน)

แก้ `stack/engines.lock.json` เป็น commit ใหม่ที่ push แล้ว, commit, แล้วค่อย tag ใหม่

---

## 2. เตรียมบน host (ยังไม่มีอะไรรัน)

```bash
cd /home/search/Thoughtmind
git clone https://github.com/khunmax2/lit-storm.git   # ครั้งแรก
cd lit-storm
git fetch origin --tags && git checkout deploy-YYYY-MM-DD
git log --oneline -1 && git status --short             # ต้องได้ commit ของ tag และ status ว่าง

sh stack/init-secrets.sh                               # สร้าง secret_key และ bootstrap_code (มีอยู่แล้วจะไม่ทับ)
cp stack/host.env.example stack/host.env && chmod 600 stack/host.env
openssl rand -hex 32                                   # → SEARXNG_SECRET
nano stack/host.env                                    # ใส่ digest สองตัวจาก §1.1 และ SEARXNG_SECRET
```

- [ ] `LITSTORM_SERVER_IMAGE` และ `LITSTORM_WEB_IMAGE` ลงท้ายด้วย `@sha256:` ไม่ใช่ tag
- [ ] **สำเนา `stack/secrets/secret_key` ออกนอก host ทันที** (เก็บในที่ปลอดภัยของผู้ดูแล เช่น password manager) — ไม่มี key นี้ API key ที่เก็บไว้ทั้งหมดต้องกรอกใหม่, และ backup ไม่เก็บ key นี้โดยตั้งใจ (§8)

---

## 3. ขึ้น stack (ยังไม่แตะ nginx)

```bash
$COMPOSE pull           # ขั้นแยก: ช้าหรือค้างก็ไม่กระทบใคร (บทเรียน DeepWitya 2026-09-12)
$COMPOSE up -d
docker ps --filter label=com.docker.compose.project=litstorm --format '{{.Names}}\t{{.Status}}'
```

- [ ] 5 container รัน: db (healthy), api, worker, web, searxng
- [ ] `curl -s http://127.0.0.1:10340/litstorm/api/health` → `{"status":"ok"}`
- [ ] `curl -s http://127.0.0.1:10340/litstorm/api/setup` → `"needed":true,"code_configured":true`
- [ ] `docker exec litstorm-db-1 psql -U litstorm -tAc "select version_num from alembic_version"` → `0010` (หรือเลขล่าสุดใน `server/src/litstorm/migrations/versions/`)
- [ ] `bash stack/host/apply-nginx.sh --check` → `app: /litstorm/api/health → 200` (ไม่ต้อง sudo)

---

## 4. ทดสอบของจริงก่อนเปิด (preview ผ่าน SSH tunnel)

บน host (คนพิมพ์เอง — sudo):

```bash
sudo bash stack/host/apply-nginx.sh --preview 10340 9443
```

บนเครื่องคุณ (PowerShell ใหม่ ปล่อยค้าง; เลขซ้ายเลือกพอร์ตว่างบนเครื่องคุณ):

```bash
ssh -L 18443:127.0.0.1:9443 search@203.185.144.41
```

เปิด **https://localhost:18443/litstorm/** (เบราว์เซอร์เตือน cert เพราะ cert เป็นของ IP — กดผ่าน)

ก่อนเริ่ม ยืนยันว่าถึงตัวจริง: `curl -k -s https://localhost:18443/litstorm/api/health` ต้องได้ `{"status":"ok"}` — ถ้าได้ `Server: kong` หรือกล่อง Basic auth แปลว่าพอร์ตชน

- [ ] หน้าตั้งค่าครั้งแรก: ใส่โค้ดจาก `stack/secrets/bootstrap_code` สร้างผู้ดูแลคนแรก (ใช้อีเมลจริงของผู้ดูแล)
- [ ] ตั้งค่า › โมเดล: API key ของ OpenRouter, โมเดลหลัก (Gemini 3.1 Flash Lite, `effort:minimal`, 1500/4000), โมเดลเร็ว, กดทดสอบผ่าน
- [ ] ตั้งค่า › โมเดล › Embedding: OpenRouter `baai/bge-m3` กดทดสอบผ่าน (บน host ไม่ใช้ Ollama ของเครื่อง dev)
- [ ] ตั้งค่า › บริการค้นหา: SearXNG และ SearXNG LDR-academic มีให้แล้ว กดทดสอบ; เพิ่ม TCI-ThaiJO และ arXiv ถ้าต้องการ
- [ ] Run จริง 1 ครั้งภาษาไทย ระดับเร็ว (STORM) สำเร็จ, เปิดรายงาน, คลิก citation, export PDF อ่านภาษาไทยได้
- [ ] Deep Research 1 ครั้ง แผนผังการค้นคว้าแสดง
- [ ] Co-STORM: เริ่ม Discussion, พิมพ์แทรก 1 ครั้ง, สร้างรายงาน
- [ ] สร้างผู้ใช้ทดสอบ ส่งลิงก์ตั้งรหัสผ่าน (ลิงก์ต้องขึ้นต้นด้วย `https://203.185.144.41/litstorm/` — ใน preview ให้เปลี่ยน host เป็น `localhost:18443` เอง)
- [ ] devtools → Network: ไม่มีคำขอใดออกนอก `/litstorm/` และไม่มี 404
- [ ] `docker ps` ทุกตัวยังรัน, `docker inspect litstorm-worker-1 --format '{{.RestartCount}}'` = 0

ถ้าข้อใดไม่ผ่าน: ยังไม่ได้แตะ :443 เลย แก้แล้ว `$COMPOSE up -d` ซ้ำได้

---

## 5. เปิดใช้ (จุดเดียวที่แตะ :443)

```bash
sudo bash stack/host/apply-nginx.sh --install 10340
sudo bash stack/host/apply-nginx.sh --remove-preview
```

script: ตรวจว่าไม่มี `/litstorm` ของคนอื่นใน :443/:80 และมีแอปฟังที่ 10340 → backup สองไฟล์ → เขียน snippet ของเรา (`/etc/nginx/snippets/litstorm.conf`, `litstorm-http.conf`) → เพิ่มบรรทัด `include` ไฟล์ละบรรทัด → `nginx -t` (ไม่ผ่าน = คืนไฟล์เดิม ไม่ reload) → reload

จากเครื่องคุณ (ไม่ผ่าน tunnel):

- [ ] `curl -s https://203.185.144.41/litstorm/api/health -k` → `{"status":"ok"}`
- [ ] `curl -sI http://203.185.144.41/litstorm/ | grep -iE "HTTP|location"` → `301` ไป `https://…/litstorm/`
- [ ] `curl -sI https://203.185.144.41/deepwitya -k | head -1` → ยังเหมือนก่อน (แอปอื่นไม่กระทบ)
- [ ] เบราว์เซอร์ปกติ: login → Run → รายงาน เหมือน §4

---

## 6. เฝ้า

- 30 นาทีแรก ทุก 10 นาที: `docker ps --filter label=com.docker.compose.project=litstorm`, `RestartCount` = 0, `docker logs --since 10m litstorm-worker-1 | grep -ciE "error|traceback"`
- สถานะจาก nginx (sudo): `sudo awk '$7 ~ /litstorm/ {print $9}' /var/log/nginx/access.log | sort | uniq -c` ไม่มี 502
- 24 ชั่วโมง: หน้าตั้งค่า › การใช้งาน ดูค่าใช้จ่ายและ Run ที่ล้ม

---

## 7. ถอย

- **หน้าเว็บมีปัญหา:** `sudo bash stack/host/apply-nginx.sh --uninstall` (ไม่กี่วินาที) `/litstorm` เลิกเสิร์ฟ, stack และข้อมูลอยู่ครบ, ไฟล์ nginx กลับเหมือนก่อน §5 ทุก byte
- **image รอบใหม่มีปัญหา:** ใส่ digest ของรอบก่อนกลับใน `stack/host.env` (จดไว้ใน §9) แล้ว `$COMPOSE up -d`
- **ข้อมูลเสีย:** กู้จาก backup (§8) — `PROJECT=litstorm bash stack/backup.sh --restore <stamp> ../_litstorm_backup`

---

## 8. สำรองข้อมูล (ต้องตั้งก่อนเปิดให้คนใช้จริง)

**ตัดสินแล้ว (2026-09-30)**
- ทุกวัน 03:45 เวลา host (หลัง backup ของ DeepWitya 03:30) ด้วย `stack/backup.sh` เก็บ 30 วันที่ `/home/search/Thoughtmind/_litstorm_backup`
- หนึ่งชุดมี 3 ไฟล์: database (`pg_dump -Fc`), ไฟล์ของทุก Run (volume `run-data` ยกเว้นแคชผลค้นหา), และ manifest
- script ตรวจเองว่า dump มีตาราง ไม่งั้นไม่นับเป็น backup
- **`secret_key` ไม่อยู่ใน backup โดยตั้งใจ:** ถ้าเก็บไว้ด้วยกัน ใครได้ backup ก็ถอด API key ได้ทั้งหมด manifest เก็บแค่ fingerprint ของ key ไว้ให้ restore เตือนเมื่อ key ไม่ตรง — สำเนา key อยู่นอก host ตาม §2
- **สำเนานอก host:** เครื่องของผู้ดูแลดึงทุกสัปดาห์ (ข้างล่าง) backup บน host อย่างเดียวไม่พอ ถ้า host เสียทั้งเครื่อง

```bash
# บน host — ครั้งแรก ทดสอบมือก่อน
cd /home/search/Thoughtmind/lit-storm && PROJECT=litstorm bash stack/backup.sh ../_litstorm_backup
PROJECT=litstorm bash stack/backup.sh --verify <stamp> ../_litstorm_backup

# cron (crontab -e ของ user ที่อยู่ในกลุ่ม docker)
45 3 * * * cd /home/search/Thoughtmind/lit-storm && PROJECT=litstorm bash stack/backup.sh ../_litstorm_backup >> ../_litstorm_backup/backup.log 2>&1
```

```powershell
# บนเครื่องผู้ดูแล — ทุกสัปดาห์ (หรือตั้ง Task Scheduler)
scp -r search@203.185.144.41:/home/search/Thoughtmind/_litstorm_backup D:\Backups\lit-storm\
```

- [ ] ซ้อมกู้คืนบน host อย่างน้อยครั้งหนึ่งหลังเปิดใช้: ขึ้น stack อีกชุดชื่อ `litstorm-restoretest` บนพอร์ตอื่น (`LITSTORM_HOST_PORT=10341` ใน env file แยก), `PROJECT=litstorm-restoretest bash stack/backup.sh --restore <stamp> ../_litstorm_backup`, เทียบจำนวน Run กับ manifest, แล้ว `down -v` ชุดทดสอบ — ขั้นตอนเดียวกับที่ซ้อมบนเครื่อง dev 2026-09-30

---

## 9. รอบอัปเดต (tag ใหม่)

```bash
# เครื่อง dev: tag ใหม่ → workflow build → ได้ digest ใหม่ (§1.1)

# host
cd /home/search/Thoughtmind/lit-storm
git fetch origin --tags && git checkout deploy-YYYY-MM-DD && git status --short   # ต้องว่าง
grep IMAGE stack/host.env | tee -a ../_litstorm_backup/images-history.txt        # จด digest เดิมไว้ถอย (§7)
PROJECT=litstorm bash stack/backup.sh ../_litstorm_backup                         # จุดถอยของข้อมูลก่อนเปลี่ยน image
nano stack/host.env                                                               # digest ใหม่
$COMPOSE pull                                                                     # ขั้นแยก ไม่มีอะไรดับ
# ---- จุดรอ: ดูว่าไม่มี Run กำลังทำอยู่ (หน้าตั้งค่า › การใช้งาน) — Run ที่ทำอยู่จะถูกทำเครื่องหมาย interrupted และคืนโควตา
$COMPOSE up -d
docker inspect litstorm-api-1 --format '{{.Config.Image}}'                        # ต้องเป็น digest ใหม่ ไม่ใช่แค่ "รันอยู่"
```

- [ ] `curl -sk https://203.185.144.41/litstorm/api/health` → ok
- [ ] สิ่งที่รอบนั้นแก้ ทดสอบตรง ๆ
- ไม่ต้องแตะ nginx; ไม่ต้อง sudo เลยในรอบอัปเดต

---

## 10. วิธีสั่ง Claude วันขึ้น host

จากรอบ DeepWitya: Claude บน host ใช้ sudo ไม่ได้ (ไม่มี TTY) — ทุกขั้น sudo (§0 บางบรรทัด, §4, §5, §7 บรรทัดแรก) คนพิมพ์เองแล้ววาง output ให้

```
host 203.185.144.41, checkout ที่ /home/search/Thoughtmind/lit-storm
วันนี้ขึ้น lit-storm ตาม docs/deploy/HOST-203.md ของ tag deploy-YYYY-MM-DD
ขั้น 0 ก่อนอ่านอะไร: git fetch origin --tags && git checkout deploy-YYYY-MM-DD && git log --oneline -1 && git status --short
แล้วอ่าน runbook จาก checkout นี้ ทำ §0 → §2 → §3 → §4 ทีละหัวข้อ รายงานค่าที่วัดได้จริงทุกข้อ
กติกา:
1. ค่าใดไม่ตรง runbook ให้หยุดแล้วเสนอแก้ runbook ไม่ใช่แก้ host
2. ห้ามข้าม checklist; ข้อไหนไม่ผ่านให้หยุดและบอก
3. ขั้น sudo ให้พิมพ์คำสั่งมาให้ฉันรันเอง แล้วรอ output
4. §5 ทำเมื่อฉันพิมพ์ "เปิดใช้" เท่านั้น; ถ้าพังหลัง §5 ทำ §7 บรรทัดแรกทันที
5. digest ของ image: <LITSTORM_SERVER_IMAGE> และ <LITSTORM_WEB_IMAGE>
```
