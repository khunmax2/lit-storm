# หน้าเว็บเป็น Vite SPA และ Backend เป็น FastAPI

เว็บใหม่ใช้ Vite + React (TypeScript, Tailwind, shadcn/ui, TanStack Query) เป็น static SPA ที่ nginx edge เสิร์ฟให้ และ FastAPI เป็นที่เดียวที่เก็บ business logic ทั้งบัญชี สิทธิ์ คิว และโควตา Frontend เรียก API ผ่าน TS client ที่สร้างจาก OpenAPI

เราไม่เลือก Next.js แม้ว่าจะนิยมใช้กัน เพราะทุกหน้าต้องล็อกอินก่อนจึงไม่ได้ประโยชน์จาก SSR/SEO และถ้าใช้ Next.js ต้องมี Node runtime ฝั่ง server อีกตัว ซึ่งเสี่ยงที่ logic จะไปอยู่ใน Server Actions ซ้ำกับ Python ถ้ารุ่นหลังมีหน้าสาธารณะ เช่น การแชร์รายงานผ่านลิงก์ ให้พิจารณาเรื่องนี้ใหม่

## Consequences

- Server เป็น Python project เดียว (`server/`) มี entrypoint สองตัวคือ `api` และ `worker` ใช้ domain และ DB model ชุดเดียวกัน (SQLAlchemy 2 + Alembic, uv) เพราะกติกาใน transaction ต้องเหมือนกันทั้งสองฝั่ง
- เว็บใหม่เป็น compose stack แยกจาก Streamlit เปลี่ยนมาใช้ทีเดียวเมื่อผ่านเกณฑ์รับงาน แล้วจึงลบ `frontend/demo_light`
- ความคืบหน้าของ Run ใช้ polling ในรุ่นแรก SSE จะพิจารณาในรุ่นสองเมื่อมี Discussion
