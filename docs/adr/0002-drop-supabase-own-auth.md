# เลิกใช้ Supabase และทำระบบบัญชีเองใน FastAPI

stack เดิมใช้ Supabase แบบติดตั้งเอง (GoTrue สำหรับบัญชี, PostgREST + RLS สำหรับสิทธิ์) เว็บใหม่เลิกใช้ทั้งหมด ใช้ Postgres ธรรมดา และ FastAPI ดูแลบัญชี session และสิทธิ์เอง

เหตุผลคือ flow บัญชีที่ตกลงไว้เป็น flow เฉพาะของระบบนี้ ได้แก่ ผู้ดูแลออกลิงก์ตั้งรหัสผ่านที่ใช้ได้ครั้งเดียวและมีอายุ 24 ชั่วโมง, ลิงก์ใหม่ทำให้ลิงก์เก่าใช้ไม่ได้ทันที, บังคับเปลี่ยนรหัสผ่าน และ bootstrap Admin คนแรกผ่าน Docker secret การดัดแปลง GoTrue ให้ทำแบบนี้ยากกว่าเขียนเอง นอกจากนี้ PostgREST ทำให้ถูกบังคับให้เขียน logic สิทธิ์เป็น RLS แยกจากโค้ด Python การเลิกใช้ยังลด container ลงได้ 3 ตัว

## Consequences

- session เก็บฝั่ง server (`auth_sessions`) ส่ง cookie แบบ httpOnly + SameSite=Lax และมี CSRF token สำหรับคำขอที่แก้ข้อมูล เราไม่ใช้ JWT เพราะการรีเซ็ตรหัสผ่านหรือปิดบัญชีต้องมีผลทันที
- API key ของ provider เก็บใน DB แบบเข้ารหัสด้วย Fernet โดยใช้ master key จาก Docker secret ถ้า master key หาย ผู้ดูแลต้องกรอก key ใหม่ทั้งหมด
