# หนึ่ง Run ต่อหนึ่ง OS process

Worker เป็น supervisor ที่สร้าง subprocess แยกให้แต่ละ Run และจะไม่รันสอง Run ใน process เดียวกัน

เหตุผลหลักคือ `article_language.py` สลับภาษารายงานโดยแก้ docstring ของคลาส `dspy.Signature` ซึ่งเป็นค่าที่ใช้ร่วมกันทั้ง process ถ้า Run ภาษาไทยกับภาษาอังกฤษทำงานพร้อมกันใน process เดียว ภาษาจะปนกัน การแก้ให้สลับภาษาเฉพาะ Run (thread-local) ต้องไปแก้ส่วนภายในของ DSPy ซึ่งเสี่ยงกว่า

## Consequences

- supervisor เป็นตัวต่ออายุ lease (heartbeat) ให้ ไม่ใช่ subprocess เพราะแต่ละ stage ของ STORM เป็นการเรียกแบบ blocking ที่ใช้เวลานาน
- การยกเลิก: ส่งสัญญาณให้หยุดที่ขอบ stage ถ้าเกิน 30 วินาทีแล้วยังไม่หยุดให้ kill subprocess โดยเก็บไฟล์ของ stage ที่เสร็จแล้วไว้
- เพดานเวลารวมต่อ Run (ค่าเริ่มต้น 60 นาที ผู้ดูแลปรับได้) ถ้าเกินให้ kill แล้วเป็น `failed` สาเหตุ timeout ต้องมีเพดานนี้เพราะ supervisor ยังส่ง heartbeat ต่อไปได้แม้ subprocess จะค้าง
- งานตามเวลา (lease หมดอายุ, ลบถาวรจากถังขยะ, ลบลิงก์ตั้งรหัสผ่านที่หมดอายุ) รันใน loop ของ supervisor ใช้ Postgres advisory lock กันการทำงานซ้ำ
