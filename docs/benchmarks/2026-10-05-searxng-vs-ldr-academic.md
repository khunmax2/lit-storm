# SearXNG ของ lit-storm เทียบกับ searxng-LDR-academic (2026-10-05)

คำถาม: lit-storm ไม่ได้รัน fork `porespellar/searxng-LDR-academic` แต่ใช้ SearXNG upstream ตัวเดียว แล้วตั้ง Search Provider "SearXNG LDR-academic" ให้ค้นด้วย engine ชุดของ fork (`stack/searxng/settings.yml`, `api/auth.py` `ACADEMIC_ENGINES`) การทำแบบนี้ตกหล่นอะไรไปบ้าง

## fork เปลี่ยนอะไรจาก upstream

fork แยกจาก upstream `b876d0bed` (2025-11-21) และมี commit ของตัวเอง 22 ตัว ใน `D:\Vscode\deep_research_lit\searxng-LDR-academic`

- **ไม่ได้เพิ่มหรือแก้โค้ด engine เลย** มีแต่ลบ engine ราว 60 ตัว เช่น วิดีโอ เพลง torrent และโซเชียล แก้หน้าตาและ Dockerfile และแก้ `searx/settings.yml`
- **ใน `settings.yml`:**
  - engine วิชาการอยู่ในหมวด `academic` และ **`general`** ด้วย การค้นปกติจึงได้ผลเว็บกับผลวิชาการปนกัน
  - `default_lang: en-US`
  - `safe_search: 2`
  - `request_timeout: 3.0`
  - JSON ไม่เปิด แอปจึงเรียกไม่ได้จนกว่าจะแก้ค่านี้
  - plugin แปลงลิงก์ DOI ไปหาฉบับ open access (`oa_doi_rewrite`) ปิดอยู่
  - `suspended_times` เป็นค่าเดียวกับ upstream

## วิธีวัด

- เปิด SearXNG ชั่วคราว 2 ตัวจาก image เดียวกับ stack (`searxng/searxng` 2026.9.20)
  - ตัวหนึ่งใช้ settings ของ lit-storm
  - อีกตัวใช้ settings ของ fork โดยเพิ่ม `json` เข้าไป
- fork ไม่ได้แก้โค้ด engine ผลจึงเป็นพฤติกรรมของ fork บน engine รุ่นเดียวกัน ถ้ารัน fork จริงจะได้ engine รุ่น พ.ย. 2025 ซึ่งเก่ากว่า
- คำค้น 6 ข้อ อังกฤษ 3 ไทย 3 ส่งผ่าน 4 โหมด
- สคริปต์อยู่ที่ `server/tests/compare_searxng.py` ผลดิบอยู่ใน [2026-10-05-searxng-vs-ldr-academic.json](2026-10-05-searxng-vs-ldr-academic.json)

| โหมด | เวลาต่อคำค้น | ผลใน 5 อันดับแรก |
|---|---|---|
| ของเรา: SearXNG (ค้นเว็บ) | 1.0–2.0 วินาที | เว็บล้วน คำค้นไทยได้หน้าไทยครบ 5/5 |
| ของเรา: SearXNG LDR-academic | 1.6–2.9 วินาที | วิชาการ 5/5 ทุกคำค้น คำค้นไทยได้งานวิจัยไทยภาษาไทย (TCI-ThaiJO, จุฬาฯ, มฟล.) |
| fork: ค้นปกติ | **6.0 วินาทีทุกคำค้น** | ปนกันแบบเดาไม่ได้ เช่น "RAG evaluation" ได้หน้าดิกชันนารีและ wiki ส่วน "PM2.5" ได้วิชาการล้วน คำค้น "รถยนต์ไฟฟ้าในประเทศไทย" ได้หน้า GeeksforGeeks เรื่อง backend มา 3 ใน 5 |
| fork: หมวด academic | 2.0–3.2 วินาที | วิชาการ 5/5 แต่คำค้นไทยได้งานไทยฉบับชื่ออังกฤษ |

## สิ่งที่ fork มีแต่เราไม่ได้เปิด

| engine | ผลที่วัดได้ | สรุป |
|---|---|---|
| BASE | timeout ทุกครั้ง (ก่อนหน้านี้ตอบ "Access denied" กับ IP ที่ยังไม่ได้รับอนุญาต) | ไม่ได้เสียอะไร |
| Wolfram\|Alpha | timeout ทุกครั้ง | ไม่ได้เสียอะไร และไม่ใช่แหล่งอ้างอิงสำหรับรายงาน |
| Library of Congress | upstream ถอดโค้ด engine ออกแล้ว (`loc.py` ไม่มี) | ไม่มีให้ใช้แล้ว |
| Mojeek | ภาษาอังกฤษได้ 10 ผลจาก index ของตัวเอง ภาษาไทยได้ 0 ผล | เป็นตัวสำรองค้นเว็บอังกฤษได้ เปิดเพิ่มได้ถ้าต้องการ |
| encyclosearch, wikibooks, wikisource, wikiversity | ผลไม่ตรงหัวข้อ เช่น handwiki หรือหน้าคอร์สออนไลน์ | ปิดไว้ดีกว่า |

ส่วน Europe PMC เรามีแต่ fork ไม่มี ให้ผลเฉลี่ย 10 ต่อคำค้น

## ที่พังเหมือนกันทั้งสองแบบ

- **Semantic Scholar:** ตอบ `parsing error` เกือบทุกคำค้น เพราะ engine เรียก API ภายในของเว็บ (`www.semanticscholar.org/api/1/search`) ซึ่งตอนนี้ส่งหน้า HTML สำหรับกันบอตกลับมา (202) ส่วน API ทางการ (`api.semanticscholar.org/graph/v1`) ตอบ 429 เมื่อไม่มี key ถ้าจะใช้ต้องทำ Search Provider ของตัวเองที่เรียก API ทางการพร้อม key ฟรี
- **Google, Brave และ DuckDuckGo:** ถูกพักจาก access denied, too many requests และ CAPTCHA ตามลำดับ ผลค้นเว็บจริงมาจาก Google CSE, Bing และ Yahoo

## สรุป

- **ไม่ได้ตกหล่นแหล่งข้อมูลวิชาการ:** engine วิชาการที่ยังใช้งานได้ของ fork มีในโหมด "SearXNG LDR-academic" ของเราครบ บวก Europe PMC
- **ของเราดีกว่าในสองเรื่อง:**
  - ภาษา: ค้นแบบ `auto` ทำให้คำค้นไทยได้งานวิจัยภาษาไทย ส่วน fork บังคับ en-US
  - ความเร็ว: ค้นปกติของ fork รอ engine ที่ timeout ทุกครั้งจนใช้ 6 วินาที
- **ความต่างเรื่องการปนผล:** fork ปนผลเว็บกับวิชาการในคำค้นเดียว ถ้าต้องการผลปนกันแบบนั้น ให้เลือกทั้ง "SearXNG" และ "SearXNG LDR-academic" ในแหล่งค้นคว้าเพิ่มเติมของ Run ซึ่งระบบจะสลับผลจากสองแหล่งให้เท่ากัน (MultiRM) แทนการให้ SearXNG จัดอันดับปนกันเอง ตอนนี้ทำได้เฉพาะ Run แบบ STORM (`max_sources` 3) ส่วน Co-STORM, Deep Research และ Agent Research ใช้ได้ทีละแหล่ง
- **ที่ทำเพิ่มได้:**
  - Search Provider Semantic Scholar ผ่าน API ทางการ
  - เปิด Mojeek เป็นตัวสำรองค้นเว็บภาษาอังกฤษ
