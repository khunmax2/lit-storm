# คุณภาพโค้ด (CODE-01…)

ตรวจเมื่อ 2026-10-24 บน `audit/2026-10-24` (0f9d755) ด้วยเครื่องมือในเครื่องเท่านั้น ไม่ได้แก้โค้ดของผลิตภัณฑ์
ทุกข้อเป็นระดับ **ต่ำ** ไม่เจอบั๊กจริงจากการตรวจหมวดนี้ ผู้ใช้ไม่เห็นผลของข้อใดเลย ยกเว้น CODE-02 ที่ลบแล้วไม่มีผลต่อหน้าจอ
ข้อที่ซ้ำกับรายงานอื่น (ruff = BUG-45, alembic check = BUG-46) ไม่ลงซ้ำที่นี่

## สรุปวิธีตรวจและตัวเลข

| งาน | ผล |
|---|---|
| vulture `--min-confidence 80` บน `server/src` | 2 รายการ ทั้งสองเป็น false positive (`max_workers` ใน `encoders.py:52` คือ signature ที่ Co-STORM บังคับ มี `noqa: ARG002` อยู่แล้ว, `exc` ใน `sources.py:101` คืออาร์กิวเมนต์ของ `__exit__`) |
| vulture `--min-confidence 60` | 258 รายการ (ฟังก์ชัน 109, เมธอด 12, คลาส 1, ตัวแปร/attribute 136) ตัดออก 254 เพราะเป็น false positive: route ของ FastAPI 81 ฟังก์ชัน, ฟิลด์ Pydantic ใน `api/` 65, Alembic `upgrade`/`downgrade` 28 กับ `revision`/`down_revision` ฯลฯ 56, คอลัมน์ SQLAlchemy และ `type_annotation_map` 3, เมธอด callback/ที่ไลบรารีหรือ http.server เรียก 7 (`on_*`, `get_total_token_usage`, `do_GET`, `log_message`), เมธอด `visuals.py` 5 ตัวที่เรียกผ่าน `getattr(checker, kind)` (บรรทัด 594), attribute ที่ตั้งให้ออบเจกต์ของ upstream 9 (`LLMConfig`, `runner.*`, `conversations.stop_at`, `daemon_threads`) ที่เหลือ 4 รายการจริง คือ CODE-03 |
| i18n | en 857 key, th 857 key ไม่มี key ซ้ำ ไม่มี key ที่มีภาษาเดียว (TypeScript บังคับด้วย `Record<Key, string>` อยู่แล้ว) |
| i18n ที่ไม่มีใครเรียก | 23 key (CODE-01) บวก 3 key ตกค้างจากฟีเจอร์ที่ถูกเอาออก (CODE-02) จาก 857; อีก 202 key ถือว่าใช้เพราะมี prefix แบบ dynamic (27 prefix เช่น `reason.`, `monitor.hint.`, `auth.feature.`, `mode.tip.`) |
| export ของเว็บที่ไม่มีใคร import | ไฟล์ทั้งไฟล์ 3 ไฟล์ (CODE-04) และ export ย่อย 11 ตัวนอก `ui/` (CODE-05) |
| TODO / FIXME / XXX / HACK | ใน `server/src`, `web/src`, `stack/` เจอ 1 ที่ และไม่ใช่ของโปรเจกต์: `engines/costorm/engine.py:19` อ้างถึง FIXME ในโค้ด upstream ของ Co-STORM ไม่มี TODO ค้างของเราเลย |

## CODE-01 key i18n ที่ไม่มีใครใช้ 23 key (ต่ำ)

หลักฐาน: `web/src/i18n.tsx` (เลขในวงเล็บเป็นบรรทัดของ dict อังกฤษ; key เดียวกันใน dict ไทยอยู่ที่บรรทัดอังกฤษ + 1049 ทุกตัว เช่น `loading` 1066, `report.withoutEvidence` 1762 ตรวจซ้ำทั้ง 23 key ใน Task 12) ค้น `"key"`, `'key'` และ template literal ใน `web/src` แล้วไม่พบ และไม่มี prefix dynamic ที่ผลิต key เหล่านี้ได้

`loading`(17) `close`(21) `project.newSession`(70) `run.topicPlaceholder`(74) `run.history`(182) `run.perspectives`(206) `quota.line`(213) `report.contents`(251) `report.sources`(252) `admin.reasoningHelp`(286) `admin.maxTokens`(287) `admin.saved`(300) `admin.price`(350) `usage.month`(356) `nav.workspace`(372) `nav.settings`(373) `home.subtitle`(376) `home.viewAll`(381) `session.newRun`(539) `run.details`(540) `run.sourcesShort`(541) `admin.subtitle`(555) `report.withoutEvidence`(713)

ข้อควรระวัง: `has()` ใน `i18n.tsx:1807` ใช้กับรหัสจาก API ด้วย แต่ key ข้างบนไม่ขึ้นต้นด้วย prefix ที่ API ส่งมา (`error.`, `status.`, `reason.`)
วิธีแก้: ลบทั้ง 23 key ออกจากทั้งสอง dict (46 บรรทัด) แล้ว `npm run build` ให้ tsc ยืนยัน ขนาด: เล็กมาก (ราว 15 นาที)

## CODE-02 ข้อความผิดพลาดตกค้างจาก Support Access Grant (ต่ำ)

หลักฐาน: `error.grant_the_discussion`, `error.grant_a_run`, `error.not_an_administrator` อยู่ที่ `web/src/i18n.tsx:151-153` (en) และ `1200-1202` (th, ตรวจซ้ำใน Task 12) ฝั่งเซิร์ฟเวอร์ไม่มีรหัสเหล่านี้เหลืออยู่ (`git grep` ใน `server/` ไม่พบ) ที่ผ่าน scan CODE-01 เพราะมี prefix `error.` แบบ dynamic บังไว้
วิธีแก้: ลบ 3 key x 2 ภาษา ขนาด: เล็กมาก

## CODE-03 โค้ด Python ที่ไม่มีใครใช้ 4 จุด (ต่ำ)

หลักฐาน (vulture 60% แล้วตรวจด้วย grep ทั้ง `src` และ `tests`):
- `engines/storm/engine.py:37` `STAGES = ("research","outline","article","polish")` ไม่มีใคร import (`tests/benchmark.py:43` และ `render/observatory.html:203` มีของตัวเอง)
- `quota.py:33` `Effective.max_concurrent` คำนวณใน `effective()` (บรรทัด 45) แต่ไม่มีใครอ่าน เพราะ worker เช็กเพดานต่อคนใน SQL (`worker/queue.py:84`) จึงมีกติกาเดียวกันอยู่สองที่ ถ้าแก้ที่หนึ่งอีกที่จะไม่ตาม
- `db/models.py:213` ค่าคงที่ `RESEARCH = "research"` ไม่มีใครใช้ (มีแต่ `DISCUSSION`; คอลัมน์ใช้สตริงตรง ๆ ที่บรรทัด 208)
- `engines/base.py:107` `class Engine(Protocol)` ไม่มีใคร import หรือใช้เป็น type ใช้เป็นเอกสารของสัญญา engine อย่างเดียว (engine จริงไม่มีตัวไหนอ้าง)

วิธีแก้: ลบ 3 รายการแรก; ข้อ `Engine` เก็บไว้ได้ถ้าถือเป็นเอกสาร แต่ควรให้ `engines/*/engine.py` อ้างถึง หรือมีเทสต์เช็กรูปร่าง ขนาด: เล็ก (30 นาที)

## CODE-04 ไฟล์ UI ของ shadcn ที่ไม่มีหน้าไหน import 3 ไฟล์ (ต่ำ)

หลักฐาน: `web/src/components/ui/tabs.tsx` (89 บรรทัด), `ui/progress.tsx` (30), `ui/field.tsx` (236) ไม่มีไฟล์ใดใน `web/src` import (ค้น `from ".../tabs|progress|field"` ไม่พบ) ส่วน `components/agent-observatory-3d.tsx` ไม่ถูก import ตรง ๆ แต่ถูกโหลดด้วย `import()` แบบ lazy จาก `pages/research.tsx:43` และ `pages/discussion.tsx:78` จึงใช้อยู่
วิธีแก้: ลบ 3 ไฟล์ (ถ้าไม่วางแผนใช้) ลดโค้ดราว 355 บรรทัด และผลของ `radix-ui` ที่ tree-shake อยู่แล้วไม่เปลี่ยนขนาด bundle ขนาด: เล็กมาก
หมายเหตุ: ไฟล์ shadcn อื่น ๆ มี sub-component ที่ไม่ได้ใช้อีกราว 60 ตัว (`AlertDialogMedia`, `AvatarGroup`, `SidebarMenuSub*`, …) ตามธรรมชาติของ shadcn ไม่แนะนำให้ไล่ลบ

## CODE-05 `export` ที่ใช้ในไฟล์เดียวกันเท่านั้น 11 ตัว (ต่ำ)

หลักฐาน: ไม่มีใคร import จากไฟล์อื่น:
`composer.tsx` `CHIP`, `MEDICAL_DEFAULT`, `MedicalForm` · `mcp-setup.tsx` `snippet` · `segmented.tsx` `Segment` · `system-status.tsx` `useSystemStatus` · `tokens.tsx` `CopyField`, `NewToken`, `SCOPES`, `ShownToken`, `TokenBody`
วิธีแก้: เอา `export` ออก เพื่อให้เครื่องมืออย่าง knip ใช้ได้ภายหลัง ขนาด: เล็กมาก
หมายเหตุ: ผู้ตรวจทานของ Task 11 ไม่ได้ตรวจรายการนี้ซ้ำ ให้ `npm run build` ยืนยันตอนแก้ (tsc จะฟ้องถ้ามีที่ import อยู่)

## CODE-06 เอกสารและคอมเมนต์ที่อ้างของที่ไม่มีแล้ว (ต่ำ)

หลักฐาน (ตัดโฟลเดอร์ `docs/acceptance/`, `docs/archive/`, บันทึกการตัดสินใจที่มีวันที่ ซึ่งเป็นประวัติ และชื่อที่เป็นของ fork/ไฟล์ตอนรัน เช่น `cli/litstorm.ts`, `report.json`, `run_options.py` ออกแล้ว):
1. `server/src/litstorm/catalog.py:28` เขียนว่า "(litstorm.engine_settings)" ไม่มีโมดูลนี้ ของจริงคือ `litstorm.modes` (`modes.py:18` `EngineSettings`)
2. `docs/web-app-design.md:503` หัวข้อ "### รุ่นสอง: Support Access Grant" ยังอยู่เป็นหัวข้อที่ดูเหมือนแผนปัจจุบัน ทั้งที่ฟีเจอร์ถูกเอาออกแล้ว (บรรทัด 627 บอกเรื่องเลิก และ `docs/CONTEXT.md:99` ระบุเลิกใช้) ควรใส่ "เลิกแล้ว 2026-10-24 ดูข้อ 627" ใต้หัวข้อ
3. `docs/web-app-implementation-plan.md:382-390` ยังบันทึก "Support Access Grant" เป็น ✅ พร้อมชื่อ `test_support_grants.py` (ไฟล์ไม่มีแล้ว) และบรรทัด 390 ยังอยู่ในรายการงานรุ่นถัดไป ควรใส่หมายเหตุว่าเลิกแล้ว
ข้อ 4 และ 5 ด้านล่างไม่ใช่ข้อบกพร่อง (ลงไว้เพื่อบอกว่าตรวจแล้ว) ข้อที่ต้องแก้มีเฉพาะ 1 ถึง 3
4. `docs/web-app-design.md:371` และ `docs/web-app-implementation-plan.md:224` อ้าง `deploy/.env` ซึ่งไม่มีแล้ว (ย้ายไป `stack/.env`; บรรทัด 371 เองบอกเรื่องย้ายอยู่แล้ว ส่วน 224 เป็นประวัติ) ไม่ต้องแก้ถ้าถือเป็นประวัติ
5. `server/tests/test_authz_matrix.py:16` ใช้ถ้อยคำถูกต้อง (บอกว่ากลุ่มนี้ถูกเอาออกแล้ว) ไม่ใช่ข้อผิดพลาด

ตรวจแล้วไม่พบปัญหา: ตัวแปรสภาพแวดล้อม `LITSTORM_*` ทุกตัวที่เอกสาร/README กล่าวถึงยังมีอยู่ใน compose หรือโค้ด, ชื่อโมดูล `litstorm.*` ทั้ง 184 ชื่อในเอกสารและคอมเมนต์มีจริง ยกเว้นข้อ 1, ไม่มีคำว่า "ช่วยตรวจ" ค้างใน README หรือ `CONTEXT.md` และโค้ด `litstorm.support`, `api/support.py`, `support-dialog.tsx` ไม่เหลือที่ใดนอกประวัติ
วิธีแก้: แก้ข้อ 1–3 รวมราว 5 บรรทัด ขนาด: เล็กมาก

## ข้อสงสัย (ยังยืนยันไม่ได้)

- รหัสข้อผิดพลาดที่เซิร์ฟเวอร์ส่ง (`HTTPException(..., "code")`) 20 รหัสไม่มี key `error.<code>` ในเว็บ: `admin_only already_purged bootstrap_code_missing cannot_cancel cannot_interpret csrf default_must_be_enabled endpoint_required invalid_credentials link_expired link_invalid no_report no_service_page no_visuals not_for_mode not_found not_signed_in run_not_finished unknown_kind unknown_provider`
  `errorMessage()` (`components/common.tsx:37`) จะแสดง "เกิดข้อผิดพลาด ลองอีกครั้ง" แทน เพราะไม่มี key บางรหัสถูกจัดการที่อื่น (`invalid_credentials` แสดง `login.failed` ที่ `pages/auth.tsx:500`) ส่วนใหญ่น่าจะเป็นรหัสที่ผู้ใช้ปกติไม่ถึง (UI ป้องกันไว้ก่อน) แต่ไม่ได้ไล่ทีละรหัสว่าหน้าจอไหนเรียก `ErrorText` กับรหัสไหน จึงไม่ลงเป็นข้อ ถ้าเจ้าของอยากให้ตรวจ ควรทำพร้อมงาน UX → **ไล่แล้วใน Task 8:** 6 รหัสผู้ใช้ไปถึงได้จริง ลงเป็น UX-13 ใน [ux.md](ux.md)
