# Engine interface เดียวสำหรับงานวิจัยแบบ batch

ทุก Engine ทำงานภายใน subprocess ของ Run (ดู [ADR-0003](./0003-one-process-per-run.md)) ผ่าน interface เดียวกันคือ `Engine.run(config, workspace_dir, progress, cancel) -> NormalizedReport` และตาราง `runs` มีคอลัมน์ `engine` ตั้งแต่รุ่นแรก รุ่นแรกมีแค่ STORM แต่รุ่นสองต้องมี Engine อื่นที่ใช้ UI ของเราเอง ไม่ใช่ iframe

## Considered Options

- **เก็บ Deep Research และ Agent Research เป็น iframe ต่อไป** เราไม่เลือก เพราะรายงานจะไม่ผ่านคิว โควตา และสิทธิ์ของระบบ ในขณะที่ API key ส่วนกลางมีค่าใช้จ่าย
- **เรียก HTTP API ของ Agent Research** เราไม่เลือก เพราะไม่มีคำสั่งยกเลิก และเก็บ Run ไว้ในหน่วยความจำอย่างเดียว

## Consequences (งานที่ต้องทำก่อนเริ่มรุ่นสอง)

- **Agent Research** (`khunmax2/lit_agents-deep-research`) เป็น Python จึง import เป็น library มาใช้ใน subprocess ได้เลย และใช้ API key จากหน้าตั้งค่าของเรา
- **Deep Research** (`khunmax2/lit_deep-research-web`, Nuxt) ตอนนี้ขั้นตอนทำงานอยู่ใน browser ต้องเพิ่ม endpoint ใน fork ที่รัน research → report ทั้งหมดฝั่ง server แล้วส่ง SSE กลับ รับ API key ต่อคำขอ และยกเลิกด้วยการตัด connection
- **Co-STORM** ไม่เข้ากับรูปแบบ Run เพราะโต้ตอบทีละรอบ ต้องมีแนวคิดใหม่ (Discussion ที่มีหลาย Turn และเก็บ state ของ runner แบบถาวร) และไม่ต้องบังคับให้ใช้ interface นี้
