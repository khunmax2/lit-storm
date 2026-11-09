# คิวของ Run อยู่ใน Postgres ไม่ใช้ Redis

คิวคือตาราง `runs` เอง Worker หยิบงานด้วย `FOR UPDATE SKIP LOCKED` ภายใต้ advisory lock (`worker/queue.py`) ไม่มี Redis, Celery หรือ message broker

Engine ต้นทางทั้งสาม (STORM, agents-deep-research, deep-research-web-ui) ไม่มีคิวมาให้ ทั้งสามรันงานตรงใน process หรือในเบราว์เซอร์ของคนที่กด คิวจึงเป็นของใหม่ที่ต้องเลือกเอง

## เหตุผล

1. **ต้องเป็น transaction เดียว** การส่งงานต้องเช็กโควตา จองโควตา และบันทึก Run ใน transaction เดียวภายใต้ lock ของแถวผู้ใช้ (ส่งงานหนึ่งครั้ง, web-app-design.md) ถ้าคิวอยู่อีกระบบ จะมีช่วงที่สองระบบไม่ตรงกัน
2. **กติกาการหยิบงานเป็น query บนข้อมูลที่อยู่ใน Postgres:** การสลับคิวระหว่างผู้ใช้ เพดานต่อคนและทั้งระบบ Turn ของ Discussion ที่ได้ก่อน งานที่รอเลือกโมเดลใหม่ และ `claim_token` ที่กัน Worker ที่เสีย lease ไปแล้วไม่ให้เขียนทับผล
3. **ลด service ที่ต้องดูแลบนเครื่อง 203 ซึ่งใช้ร่วมกับระบบอื่น:** สำรองข้อมูลที่เดียว (`stack/backup.sh`)
4. **ปริมาณงานระดับหลายงานต่อนาที:** Postgres ทั่วไปหยิบงานได้หลักร้อยต่อวินาที Redis เด่นในระดับหลักพันต่อวินาทีซึ่งเราไม่ได้ต้องการ

## ทางเลือกที่ไม่เลือก

- **Redis + Celery/RQ:** เร็วกว่า แต่ต้องทำให้สองแหล่งข้อมูลตรงกัน และต้องดูแลอีก service หนึ่ง
- **Temporal:** OpenAI ใช้กับ Codex และ Replit ใช้กับ Agent ข้อเด่นคือทำงานต่อจากขั้นที่ค้างได้เมื่อเครื่องล่ม แต่ต้องมี server และ DB ของตัวเอง Run ของเรายาว 2–12 นาที การเริ่มใหม่และคืนโควตาจึงพอ

## จะกลับมาพิจารณาเมื่อ

- งานยาวเป็นชั่วโมงจนการเริ่มใหม่แพง ให้ดู Temporal หรือ Hatchet (ใช้ Postgres เหมือนเดิม)
- Worker ต้องกระจายหลายเครื่อง
- มีงานหลายร้อยต่อวินาที

## Consequences

- API ใช้ connection pool ร่วมกับทุกคำขอ `api/deps.py` จำกัดจำนวนคำขอที่ใช้ DB พร้อมกันไม่ให้เกิน pool ถ้าไม่จำกัด คำขอพร้อมกันจำนวนมากจะติดตายรอกันเอง (load test 2026-09-30, `docs/benchmarks/2026-09-30-concurrency.md`)
- Worker ไม่ต้องรอรอบเช็กคิวแล้ว (2026-10-02, migration 0012, `litstorm/notify.py`)
  - trigger ส่ง `pg_notify` เมื่อมี Run เข้าคิวหรือมีช่องว่าง Worker ที่ LISTEN อยู่ตื่นทันที
  - ยังเช็กคิวเองทุก 5 วินาที เพื่อจับสิ่งที่ไม่มี notification บอก เช่น Admin เพิ่มเพดาน หรือ lease หมดอายุ
- หน้า Run ไม่ poll แล้ว เปลี่ยนเป็นรับ stream (SSE, `GET /api/runs/{id}/live`)
  - API แต่ละ process เปิด LISTEN 1 connection แล้วกระจายสัญญาณให้ทุก stream ใน process
  - stream ไม่ถือ connection ระหว่างรอ
  - นี่คือสิ่งที่ DeepTutor ใช้ Redis Streams ทำ แต่เราใช้ Postgres ทำได้ โดยไม่ต้องเพิ่ม service
