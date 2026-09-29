# Report เก็บเป็นไฟล์ report.json ที่มีรูปแบบกลางชุดเดียว

ผลลัพธ์ของทุก Engine จะถูกแปลงเป็น `report.json` ต่อ Run ประกอบด้วย sections (โครงต้นไม้ของ markdown), citations `[n]` ที่ชี้ไปยัง source_id และ sources (url, title, snippets[]) ไฟล์นี้เก็บใน persistent volume ส่วน Postgres เก็บแค่ index สำหรับค้นหาและแสดงรายการ หน้าอ่านรายงาน, Source Explorer และ export ทั้ง HTML, Markdown และ PDF สร้างจากไฟล์นี้ทั้งหมด

เราเก็บเป็นไฟล์แทน JSONB เพราะ Report เขียนครั้งเดียวแล้วไม่แก้ และถังขยะกับการลบถาวรจะใช้กลไกเดียวกับ artifact อื่นได้ ส่วน `snippets` ว่างได้ เพราะแต่ละ Engine ให้หลักฐานละเอียดไม่เท่ากัน (STORM มี snippet ต่อ citation แต่ Engine อื่นมีแค่ลิงก์) เราจะไม่สร้างหลักฐานที่ Engine ไม่ได้บันทึกไว้ขึ้นมาเอง

## Consequences

- PDF พิมพ์จาก HTML export ด้วย Chromium (Playwright) พร้อมฝังฟอนต์ไทย (Noto Sans Thai / Sarabun) เพราะตัดคำภาษาไทยได้ถูกต้อง แม้ image จะใหญ่ขึ้นประมาณ 300–400MB
- ต้องเขียนไฟล์ให้ครบก่อนบันทึกใน DB ว่ารายงานพร้อมอ่าน
