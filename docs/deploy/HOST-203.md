# HOST-203 — lit-storm ขึ้น `/litstorm` บน 203.185.144.41

runbook สำหรับวันขึ้น host ครั้งแรก และรอบอัปเดตหลังจากนั้น ทำตามแบบของ DeepWitya ซึ่งอยู่บน host เดียวกัน (`D:\Vscode\Upstream_Deeptutor\deploy\GO-LIVE.md`) บทเรียนจากรอบนั้นใส่ไว้ในขั้นที่เกี่ยวข้องแล้ว

**ยังไม่ได้ขึ้น** ขึ้นได้เมื่อรุ่นสองผ่านครบบนเครื่อง dev แล้วเท่านั้น (ผ่านแล้ว 2026-09-30, ดู `docs/web-app-implementation-plan.md`) และผู้ดูแลสั่งขึ้นเอง

**เพิ่ม 2026-10-19:** แท็บ Medical Review ต้องมี MedicalReviewerAgent (MRA, [ADR-0013](../adr/0013-remote-engine-medical-review.md)) รันอยู่บน host เดียวกัน ขั้นของ MRA อยู่ใน §M ทำหลัง §3 และก่อน §4
- MRA เป็น compose project แยก (`mra`) รันจาก checkout ของ MRA เองตาม commit ที่ pin ไว้ ใช้ image จาก GHCR เหมือน lit-storm
- **หน้าเว็บของ MRA ไม่เปิดสู่ภายนอก:** เปิดเฉพาะ loopback port เดียวสำหรับหน้า admin ซึ่งผู้ดูแลเข้าผ่าน `ssh -L`
- **ทางเชื่อม:** api และ worker ของ lit-storm คุยกับ MRA ผ่าน Docker network `litstorm-mra` ที่ `http://mra` ซึ่งเป็น gateway ตัวเล็กที่ส่งต่อให้ Caddy ของ MRA
  - ไม่ให้ Caddy ของ MRA อยู่บน network นี้เอง เพราะ Caddy ส่งต่อไปที่ชื่อ `api` และบน network นี้ `api` คือ API ของ lit-storm (เจอตอนซ้อม 2026-10-19 ได้ 404 จาก lit-storm แทน MRA)
- **ซ้อมบนเครื่อง dev แล้ว (2026-10-19):** image ทั้ง 5 ตัวจาก `stack/build-images.sh`, lit-storm ด้วย `compose.host.yml` (project `ls203`) และ MRA ด้วย compose 3 ไฟล์จาก clone ที่ pin (project `mra203`) ผ่าน 13 ข้อ
  - §3 ครบ: 5 container, health, หน้าตั้งค่าครั้งแรก, migration `0013`
  - §M ครบ: MRA ขึ้นครบ, เปิดแค่ `127.0.0.1:10350`, lit-storm เรียก `http://mra` ได้, สร้าง key ด้วย CLI ได้
  - §4: ทดสอบโมเดลผ่าน, ทดสอบการเชื่อม MRA ผ่าน (แหล่งค้น 9), แท็บ Medical Review แสดง, STORM ระดับเร็วภาษาไทยสำเร็จ (มีขั้นตีความหัวเรื่องก่อน), export PDF ได้, Medical Review ถามเร็วภาษาไทยสำเร็จ (ค่าใช้จ่ายจาก MRA), MCP เส้น medical ตอบ
  - §8: `backup.sh` และ `backup-mra.sh` สำรองได้ กู้คืนฐานข้อมูลของ MRA แล้วรีวิวอยู่ครบ

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
| พอร์ต loopback ของ stack | `10343` (DeepWitya ใช้ 10310/10320/10330; วัด 2026-10-20: 10340 เป็นของ HIS Mapping, 10341 ของ Agenta (traefik), 10342 ของ TCI-AP-Web) |
| พอร์ต preview บน host | `9443` (8443 เป็นของ Kong ของแอปอื่น) |
| checkout บน host | `/home/search/Thoughtmind/lit-storm` |
| backup บน host | `/home/search/Thoughtmind/_litstorm_backup` |
| Compose project | `litstorm` |
| image | `ghcr.io/khunmax2/lit-storm-server`, `ghcr.io/khunmax2/lit-storm-web` (build สำหรับ `/litstorm`) |
| MRA: checkout บน host | `/home/search/Thoughtmind/MedicalReviewerAgent` (commit ตาม `stack/engines.lock.json`) |
| MRA: Compose project | `mra` |
| MRA: พอร์ต loopback ของหน้า admin | `10350` (ไม่ผ่าน nginx; เข้าด้วย `ssh -L`) |
| MRA: image | `ghcr.io/khunmax2/mra-backend`, `mra-web`, `mra-searxng` |
| network ระหว่างสอง stack | `litstorm-mra` (MRA เป็น `http://mra` ผ่าน gateway ของ MRA) |

คำสั่ง compose ที่ใช้ทั้งไฟล์ (บน host):

```bash
COMPOSE="docker compose -p litstorm -f stack/compose.yml -f stack/compose.host.yml --env-file stack/host.env"
```

---

## 0. วัดก่อน อย่าเดา (บน host)

```bash
docker compose version                      # ต้อง >= 2.24 (ใช้ !reset)
ss -ltnp | grep -E ':(10343|9443|10350)\s'  # ต้องว่างทั้งหมด
sudo nginx -T 2>/dev/null | grep -n 'litstorm'   # ต้องว่าง: ยังไม่มีใครใช้ /litstorm
sudo nginx -T 2>/dev/null | grep -nE 'ssl_certificate|server_name|listen'   # :443 อยู่ในไฟล์ sansarnnews-ssl, :80 ในไฟล์ ade
df -h / && docker system df                 # ต้องว่าง >= 20 GB (server image ~7 GB, MRA ~3 GB)
docker ps --format '{{.Names}}\t{{.Ports}}' | grep -iE 'litstorm|mra'   # ต้องว่าง
docker network ls | grep litstorm-mra       # ต้องว่าง (สร้างใน §3)
```

- [ ] ไฟล์ :443 คือ `/etc/nginx/sites-available/sansarnnews-ssl` และ :80 คือ `/etc/nginx/sites-available/ade` ถ้าไม่ใช่ ให้ส่งค่าจริงผ่าน env `SSL=` / `HTTP=` ของ `stack/host/apply-nginx.sh` และแก้ตารางนี้
- [ ] ถ้าพอร์ตไม่ว่าง เลือกเลขใหม่ แล้วใช้เลขนั้นทุกที่ที่เขียน 10343 / 9443 / 10350
- [ ] ออกอินเทอร์เน็ตได้: `curl -sI https://ghcr.io | head -1` และ `curl -sI https://openrouter.ai | head -1`
- [ ] RAM ว่างและจำนวน core: `free -m && nproc` แล้วเลือกเพดานจากตารางด้านล่าง

**Run พร้อมกันกี่งาน** ตั้งหลังติดตั้งที่ ตั้งค่า › ขีดจำกัด › "Run พร้อมกันทั้งระบบ" ค่าตั้งต้นคือ 6 ตัวเลขในตารางมาจาก load test (`docs/benchmarks/2026-09-30-concurrency.md`)

- stack ขณะว่างใช้ RAM ราว 1 GB: api 2 process, db, web, edge, searxng และ Worker
- ถ้าผู้ใช้เกินราว 100 คนเปิดดูงานสดพร้อมกัน ให้ตั้ง `LITSTORM_API_WORKERS=3` หรือ `4` ใน `host.env` process หนึ่งรับได้ราว 60 คำขอต่อวินาที และ Postgres รับ connection ได้พอสำหรับไม่เกิน 4 process
- Run หนึ่งใช้เพิ่มราว 0.3 GB ถ้า embed ผ่านบริการ (ตั้งค่า › Embedding) หรือราว 0.55 GB ถ้าใช้โมเดลในตัว

| RAM ที่เหลือให้ lit-storm | embed ผ่านบริการ | โมเดลในตัว |
|---|---|---|
| 4 GB | 8 | 4 |
| 8 GB | 18 | 10 |
| 16 GB | 40 | 22 |

- ตัวเลขในตารางเผื่อไว้ราว 20% แล้ว
- เกิน 6–8 Run ต้องใช้ Search Provider แบบ API เช่น Tavily, Serper, Brave หรือ Exa เป็นหลัก เพราะ SearXNG จะติด CAPTCHA ก่อน RAM หมด
- ดู rate limit ของ OpenRouter ของบัญชีด้วย
- CPU ไม่ใช่คอขวด process ของ Run มีลำดับความสำคัญต่ำกว่า API (nice 10) จึงไม่แย่ง CPU จนหน้าเว็บช้า

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
- และอีกสามบรรทัดสำหรับ `.env` ของ MRA (§M): `MRA_BACKEND_IMAGE`, `MRA_WEB_IMAGE`, `MRA_SEARXNG_IMAGE`

- repo ที่ workflow ดึงทั้งหมดเป็น public (fork สองตัวเปลี่ยนเป็น public 2026-10-20) จึงไม่ต้องใช้ token หรือ secret เพิ่ม
  - [ ] ถ้า fork ตัวไหนกลับเป็น private ขั้น checkout จะล้มด้วย "repository not found" ต้องเพิ่ม `token:` ให้ขั้นนั้นใน `images.yml` ด้วย fine-grained token ที่อ่านได้อย่างเดียว

- [ ] **ครั้งแรกเท่านั้น:** GitHub → Packages → `lit-storm-server`, `lit-storm-web`, `mra-backend`, `mra-web` และ `mra-searxng` → Package settings → **Change visibility → Public** (ครั้งแรกเป็น private; repo เป็น public และ image ไม่มี secret — ถ้าอยากเก็บ private ต้อง `docker login ghcr.io` บน host ด้วย PAT `read:packages`)
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
docker network create litstorm-mra   # ครั้งแรกเท่านั้น: ทางที่ api และ worker คุยกับ MRA (§M)
$COMPOSE pull           # ขั้นแยก: ช้าหรือค้างก็ไม่กระทบใคร (บทเรียน DeepWitya 2026-09-12)
$COMPOSE up -d
docker ps --filter label=com.docker.compose.project=litstorm --format '{{.Names}}\t{{.Status}}'
```

- [ ] 5 container รัน: db (healthy), api, worker, web, searxng
- [ ] `curl -s http://127.0.0.1:10343/litstorm/api/health` → `{"status":"ok"}`
- [ ] `curl -s http://127.0.0.1:10343/litstorm/api/setup` → `"needed":true,"code_configured":true`
- [ ] `docker exec litstorm-db-1 psql -U litstorm -tAc "select version_num from alembic_version"` → `0013` (หรือเลขล่าสุดใน `server/src/litstorm/migrations/versions/`)
- [ ] `bash stack/host/apply-nginx.sh --check` → `app: /litstorm/api/health → 200` (ไม่ต้อง sudo)

---

## M. MedicalReviewerAgent (หลัง §3 ก่อน §4)

MRA เป็น stack ของตัวเอง รันจาก checkout ของ MRA ด้วยไฟล์ compose ของ MRA สองไฟล์บวก `stack/mra/compose.host.yml` ของเรา
- image มาจาก GHCR ตาม digest ไม่ build บน host
- ไฟล์ตั้งค่าของ MRA (ค่าโมเดล, Caddyfile, SearXNG) mount จาก checkout เพราะ compose รันบน host ตรง ๆ
- ไม่มี port ไหนเปิดบน host นอกจาก `127.0.0.1:10350` สำหรับหน้า admin

```bash
cd /home/search/Thoughtmind
git clone https://github.com/santipongth/MedicalReviewerAgent.git   # ครั้งแรก
cd MedicalReviewerAgent
git fetch origin && git checkout <commit ของ mra ใน stack/engines.lock.json ของ tag>
git log --oneline -1 && git status --short             # ต้องได้ commit ที่ pin และ status ว่าง
cp .env.example .env && chmod 600 .env
docker run --rm <MRA_BACKEND_IMAGE> python -m app.cli.admin llm-keys-secret   # → LLM_KEYS_SECRET
openssl rand -hex 32                                   # → SEARXNG_SECRET
openssl rand -hex 16                                   # → IP_HASH_SALT
nano .env
```

ค่าใน `.env` ของ MRA ที่ต้องแก้ ที่เหลือคงตาม `.env.example`:

| ค่า | ตั้งเป็น |
|---|---|
| `APP_ENV` | `prod` |
| `LLM_KEYS_SECRET`, `SEARXNG_SECRET`, `IP_HASH_SALT` | ค่าที่สุ่มข้างบน |
| `OPENROUTER_API_KEY` | key ของ OpenRouter (หรือเว้นว่าง แล้วใส่ในหน้า admin ของ MRA) |
| `MAX_USD_PER_DAY` | `2` เริ่มต่ำไว้ก่อน ปรับทีหลังได้ |
| `PUBLIC_BASE_URL` | `http://localhost:10350` (ที่อยู่ที่ผู้ดูแลเปิดผ่าน tunnel) |
| เพิ่มบรรทัด `MRA_BACKEND_IMAGE`, `MRA_WEB_IMAGE`, `MRA_SEARXNG_IMAGE` | digest จาก §1.1 |
| เพิ่มบรรทัด `MRA_HOST_PORT` | `10350` |

- [ ] **สำเนา `.env` ของ MRA ออกนอก host ทันที** เหมือน `secret_key` ใน §2 ไม่มี `LLM_KEYS_SECRET` key ที่ใส่ในหน้า admin ของ MRA ต้องกรอกใหม่หมด

```bash
MRA="docker compose -p mra -f docker-compose.yml -f docker-compose.prod.yml -f /home/search/Thoughtmind/lit-storm/stack/mra/compose.host.yml"
$MRA pull
$MRA up -d
$MRA ps                                                # postgres, redis, searxng, api, worker, web, caddy, gateway รัน; migrate จบด้วย exit 0
```

- [ ] `curl -s http://127.0.0.1:10350/api/v1/status` → ขึ้นต้นด้วย `{"accepting":true` และมี `"sources"` 9 แหล่ง
- [ ] lit-storm มองเห็น MRA: `docker exec litstorm-api-1 python -c "import urllib.request; print(urllib.request.urlopen('http://mra/api/v1/status').status)"` → `200` (ถ้าได้ 404 แปลว่าคำขอไปถึง API ของ lit-storm เอง: ตรวจว่ามีแค่ `mra-gateway-1` จาก MRA อยู่บน network `docker network inspect litstorm-mra`)
- [ ] `docker ps --format '{{.Names}}\t{{.Ports}}' | grep mra` มีพอร์ตเดียว คือ `127.0.0.1:10350->80/tcp`

**ผู้ดูแลตั้งเอง (คนพิมพ์รหัสผ่าน ไม่ใช่ Claude):**

```bash
$MRA exec api python -m app.cli.admin create admin           # ถามรหัสผ่านสองครั้ง
$MRA exec api python -m app.cli.keys mint --name deeplit     # พิมพ์ key ครั้งเดียว: คัดไว้ใช้ใน §4
```

- [ ] เปิดหน้า admin ของ MRA ผ่าน tunnel: บนเครื่องคุณ `ssh -L 10350:127.0.0.1:10350 search@203.185.144.41` แล้วเปิด http://localhost:10350/admin ล็อกอินได้

---

## 4. ทดสอบของจริงก่อนเปิด (preview ผ่าน SSH tunnel)

บน host (คนพิมพ์เอง — sudo):

```bash
sudo bash stack/host/apply-nginx.sh --preview 10343 9443
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
- [ ] การตีความหัวเรื่อง: Run ข้างบนมีขั้น "ตีความหัวเรื่อง" ก่อน และการ์ด Run มี "ตีความหัวเรื่องว่า …"
- [ ] Medical Review (ต้องทำ §M ก่อน):
  - ตั้งค่า › โหมดวิจัย › การ์ด Medical Review: ที่อยู่ `http://mra`, ที่อยู่หน้าเว็บ `http://localhost:10350`, API key จาก §M แล้วกด "ทดสอบการเชื่อมต่อ" ต้องผ่านครบ (ติดต่อได้, รับงาน, รับ key, แหล่งค้น 9 แหล่ง)
  - แท็บ Medical Review ปรากฏ แบบถามเร็ว 1 ครั้งภาษาไทย สำเร็จ ค่าใช้จ่ายขึ้นจาก MRA
  - แบบรีวิวเต็ม 1 ครั้ง มุมมอง "รายงานแบบเต็ม (MRA)" เปิดได้
- [ ] MCP: ตั้งค่า › การเชื่อมต่อ สร้าง token แล้ว `curl -sk -X POST https://localhost:18443/litstorm/api/mcp/medical -H "Authorization: Bearer <token>" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'` ได้รายชื่อ tool ขึ้นต้นด้วย `medical_research_`
- [ ] สร้างผู้ใช้ทดสอบ ส่งลิงก์ตั้งรหัสผ่าน (ลิงก์ต้องขึ้นต้นด้วย `https://203.185.144.41/litstorm/` — ใน preview ให้เปลี่ยน host เป็น `localhost:18443` เอง)
- [ ] devtools → Network: ไม่มีคำขอใดออกนอก `/litstorm/` และไม่มี 404
- [ ] `docker ps` ทุกตัวยังรัน, `docker inspect litstorm-worker-1 --format '{{.RestartCount}}'` = 0

ถ้าข้อใดไม่ผ่าน: ยังไม่ได้แตะ :443 เลย แก้แล้ว `$COMPOSE up -d` ซ้ำได้

---

## 5. เปิดใช้ (จุดเดียวที่แตะ :443)

```bash
sudo bash stack/host/apply-nginx.sh --install 10343
sudo bash stack/host/apply-nginx.sh --remove-preview
```

script: ตรวจว่าไม่มี `/litstorm` ของคนอื่นใน :443/:80 และมีแอปฟังที่ 10343 → backup สองไฟล์ → เขียน snippet ของเรา (`/etc/nginx/snippets/litstorm.conf`, `litstorm-http.conf`) → เพิ่มบรรทัด `include` ไฟล์ละบรรทัด → `nginx -t` (ไม่ผ่าน = คืนไฟล์เดิม ไม่ reload) → reload

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

# ฐานข้อมูลของ MRA (§M): ทดสอบมือครั้งแรกด้วย
bash stack/mra/backup-mra.sh ../_litstorm_backup

# cron (crontab -e ของ user ที่อยู่ในกลุ่ม docker)
45 3 * * * cd /home/search/Thoughtmind/lit-storm && PROJECT=litstorm bash stack/backup.sh ../_litstorm_backup >> ../_litstorm_backup/backup.log 2>&1
50 3 * * * cd /home/search/Thoughtmind/lit-storm && bash stack/mra/backup-mra.sh ../_litstorm_backup >> ../_litstorm_backup/backup.log 2>&1
```

- MRA: ไฟล์เดียวต่อรอบ (`mra-<stamp>.dump`) ไม่สำรอง Redis โดยตั้งใจ ถ้าหายเสียแค่งานที่กำลังรันอยู่ และตัวนับค่าใช้จ่ายของวันนั้นเริ่มนับใหม่
- `LLM_KEYS_SECRET` ใน `.env` ของ MRA ไม่อยู่ใน backup เหตุผลเดียวกับ `secret_key` สำเนาไว้นอก host ตาม §M

```powershell
# บนเครื่องผู้ดูแล — ทุกสัปดาห์ (หรือตั้ง Task Scheduler)
scp -r search@203.185.144.41:/home/search/Thoughtmind/_litstorm_backup D:\Backups\lit-storm\
```

- [ ] ซ้อมกู้คืนบน host อย่างน้อยครั้งหนึ่งหลังเปิดใช้: ขึ้น stack อีกชุดชื่อ `litstorm-restoretest` บนพอร์ตอื่น (`LITSTORM_HOST_PORT=10344` ใน env file แยก; 10341 เป็นของ Agenta), `PROJECT=litstorm-restoretest bash stack/backup.sh --restore <stamp> ../_litstorm_backup`, เทียบจำนวน Run กับ manifest, แล้ว `down -v` ชุดทดสอบ — ขั้นตอนเดียวกับที่ซ้อมบนเครื่อง dev 2026-09-30

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

# MRA: ทำเฉพาะเมื่อ pin ของ mra ใน stack/engines.lock.json หรือ digest ของ MRA เปลี่ยน ($MRA ตั้งตาม §M)
cd /home/search/Thoughtmind/MedicalReviewerAgent
git fetch origin && git checkout <commit ใหม่ของ mra> && git status --short      # ต้องว่าง
bash ../lit-storm/stack/mra/backup-mra.sh ../_litstorm_backup                     # จุดถอยก่อนเปลี่ยน
nano .env                                                                         # MRA_*_IMAGE ใหม่
$MRA pull && $MRA up -d && $MRA ps
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
แล้วอ่าน runbook จาก checkout นี้ ทำ §0 → §2 → §3 → §M → §4 ทีละหัวข้อ รายงานค่าที่วัดได้จริงทุกข้อ
กติกา:
1. ค่าใดไม่ตรง runbook ให้หยุดแล้วเสนอแก้ runbook ไม่ใช่แก้ host
2. ห้ามข้าม checklist; ข้อไหนไม่ผ่านให้หยุดและบอก
3. ขั้น sudo และขั้นที่ต้องพิมพ์รหัสผ่าน (สร้าง admin ของ MRA) ให้พิมพ์คำสั่งมาให้ฉันรันเอง แล้วรอ output
4. §5 ทำเมื่อฉันพิมพ์ "เปิดใช้" เท่านั้น; ถ้าพังหลัง §5 ทำ §7 บรรทัดแรกทันที
5. digest ของ image: <LITSTORM_SERVER_IMAGE> และ <LITSTORM_WEB_IMAGE>
   ของ MRA: <MRA_BACKEND_IMAGE>, <MRA_WEB_IMAGE> และ <MRA_SEARXNG_IMAGE>
```
