# รายงานแบบ HTML โต้ตอบได้ (interactive HTML report) สำหรับ lit-storm — งานค้นคว้า

วันที่ค้นคว้า: 2026-10-01 · ขอบเขต: research only ไม่มีการแก้โค้ด

**วิธีอ่านระดับความเชื่อมั่นในเอกสารนี้**

- ไม่มีป้าย = อ่านจากแหล่งต้นทางโดยตรง (เอกสารทางการ, README/ซอร์สบน GitHub, MDN/W3C, npm registry) ในวันที่ค้นคว้า
- **[snippet]** = แหล่งต้นทางบล็อกการดึงหน้าโดยตรง (HTTP 403 / Cloudflare challenge) จึงเห็นข้อความของหน้าทางการนั้นผ่านผลค้นหาเท่านั้น ถือว่า "ยืนยันได้บางส่วน"
- **[unverified]** = พบแต่ในแหล่งรอง ยังไม่ยืนยันจากต้นทาง
- **[อนุมาน]** = ข้อสรุปของผู้เขียนเอง ไม่ใช่สิ่งที่แหล่งใดเขียนไว้
- ขนาดไฟล์ไลบรารีวัดเองจากไฟล์ใน npm (ดึงผ่าน jsDelivr) ในวันที่ค้นคว้า ไม่ได้อ้างตัวเลขจากเว็บของไลบรารี

---

## 1. สรุปสั้น (TL;DR)

1. **อย่าให้ LLM เขียน HTML/JS เอง** ให้ LLM ส่งออกเป็น **JSON "visual blocks"** ตาม schema ที่แคบ แล้วให้ renderer ที่เราเขียนเองแปลงเป็นกราฟหรือแผนภาพ แนวนี้ตรงกับทิศทางของ A2UI (Google) และ json-render (Vercel) ที่ตั้งหลักไว้ว่า "declarative data, not code" และใช้ catalog ที่ฝั่ง client เชื่อถือ [33][32] ส่วนการให้ LLM เขียนโค้ดแล้วรันจริงต้องใช้ sandbox ที่แข็งแรงอย่างที่ Claude Artifacts, ChatGPT Canvas และ E2B ทำ [2][16][35]
2. **ตัวเลขทุกตัวในกราฟต้องมีที่มา** block ที่มีตัวเลขต้องแนบ `source` (id ใน `report.sources`) และ `quote` ที่คัดมาตรงตัวจาก evidence แล้ว validator ที่ไม่ใช้ LLM ตรวจว่า quote อยู่ใน evidence จริงและตัวเลขอยู่ใน quote ถ้าไม่ผ่านก็ตัดทิ้ง ห้ามเติมเอง แนวคิดนี้เหมือน `cited_text` ของ Claude Citations API ที่รับประกันว่าชี้กลับไปที่เอกสารได้จริง [64] และสอดคล้องกับ ADR 0005 ของ lit-storm ที่ห้ามสร้างหลักฐานที่ Engine ไม่ได้บันทึกไว้
3. **ภาพที่ไม่ต้องใช้ LLM ให้สร้างจากข้อมูลที่มีอยู่แล้ว (ค่าใช้จ่าย 0)** ได้แก่ mind map จากโครง `sections`, source network (section ↔ แหล่งที่อ้าง) จาก citation `[n]` และตารางแหล่งอ้างอิงที่เรียงและกรองได้ ส่วน LLM ใช้เฉพาะ key-stat cards, กราฟตัวเลข, timeline, ตารางเปรียบเทียบ และแผนภาพ flow
4. **เลือกไลบรารีกราฟเดียวคือ Apache ECharts** (Apache-2.0) option เป็น JSON, มี SVG renderer, render ฝั่ง server เป็น SVG string ได้, มี locale ไทย (`langTH`), มี ARIA และ decal pattern และ Evidence.dev ก็ใช้ ECharts อยู่เบื้องหลัง [42][43][44][39] ส่วนแผนภาพใช้ **Mermaid** แต่ **pre-render เป็น SVG ฝั่ง server** เพราะ `mermaid.min.js` ใหญ่ 5.4 MB [41]
5. **ใช้แนวทาง "static-first"** render กราฟทุกตัวเป็น **inline SVG** ใน headless Chromium ที่ lit-storm มีอยู่แล้วสำหรับ PDF (Playwright) โดยปิด network ไว้ ผลคือไฟล์ HTML เปิดออฟไลน์ได้, พิมพ์หรือทำ PDF ได้คมชัด และทำงานได้แม้ปิด JavaScript ส่วน JS แบบ inline ขนาดเล็กใส่เพิ่มเฉพาะงานโต้ตอบ เช่น แท็บ, เรียงหรือกรองตาราง, popover ของ citation, สลับโหมดมืด/สว่าง ถ้าต้องการ tooltip บนกราฟจริงค่อยฝัง ECharts runtime เป็นตัวเลือก (~1.1 MB raw / ~360 KB gzip)
6. **ความปลอดภัยมีหลายชั้น** ชั้นแรก LLM ไม่ได้ส่ง markup ใดๆ (escape ทุก string) ชั้นที่สองใส่ `<meta http-equiv="Content-Security-Policy">` ในไฟล์ (`default-src 'none'` และอนุญาต script ด้วย hash) ชั้นที่สาม เมื่อแสดงในเว็บแอปให้ใช้ `<iframe sandbox="allow-scripts">` **ห้ามใส่** `allow-same-origin` [55][56] และส่ง header `Content-Security-Policy: sandbox allow-scripts` เมื่อเสิร์ฟไฟล์จาก API [57]
7. **ในไปป์ไลน์ ให้เป็นขั้นแยกหลัง `report.json`** เก็บผลเป็นไฟล์ใหม่ `visuals.json` ข้าง `report.json` เพื่อให้ `report.json` ยังเขียนครั้งเดียวไม่แก้ตาม ADR 0005 และสร้าง **เมื่อผู้ใช้กดขอครั้งแรก (on-demand) แล้ว cache ไว้** Run ที่ไม่มีใครขอจึงไม่เสียเงินเพิ่ม
8. **ค่าใช้จ่าย** คือเรียกโมเดลเร็ว 1 ครั้ง (บวก repair สูงสุด 1 ครั้ง) input ราว 8–15k token, output 2–4k token ประเมินจาก benchmark ของ lit-storm เองได้ประมาณ **$0.005–0.01 ต่อรายงาน** หรือราว 25–50% ของค่า Run ระดับมาตรฐาน (ดู §8.6) **[อนุมาน]**
9. **ภาษาไทย** SVG `<text>` ไม่ตัดบรรทัดเอง จึงต้องตัดคำ label ฝั่ง server ก่อน (เช่นใช้ ICU/PyThaiNLP หรือ `Intl.Segmenter` ใน Chromium ตอน pre-render [60]) และฝังฟอนต์ไทย subset เป็น data URI ได้ (Noto Sans Thai subset ไทยน้ำหนักละ ~9 KB [67])
10. **UX ที่ควรลอกมา** ได้แก่ citation hover card (Quarto/MyST [37][40]), ตาราง "ดูข้อมูลของกราฟ" ใต้กราฟทุกตัว (ช่วย accessibility และตรวจสอบได้), mind map ย่อขยายได้ (NotebookLM [13]), แท็บและส่วนพับได้, print stylesheet, ไฟล์เดียวที่เปิดออฟไลน์ได้ (Quarto `embed-resources` [37])

---

## 2. Frontier products

### 2.1 Anthropic Claude — Artifacts, custom visuals, AI-powered apps

**สิ่งที่ผลิต**
- ศูนย์ช่วยเหลือระบุว่า artifacts ใช้สร้าง "documents, code snippets, single-page websites, images, diagrams and flowcharts, dashboards" และเครื่องมือโต้ตอบขนาดเล็ก เก็บข้อมูลถาวรได้ 20 MB ต่อ artifact (เฉพาะข้อความ) และ artifact เป็น private จนกว่าจะแชร์ [1][5]
- **Custom visuals** คือ diagram/chart แบบ HTML ที่ Claude สร้าง inline ในแชต มีปุ่มและ slider ให้โต้ตอบได้ แต่ "ephemeral by default" คือไม่ถูกบันทึกแยก ดาวน์โหลดเป็น SVG/HTML หรือแปลงเป็น artifact ได้ [3]
- **AI-powered apps**: artifact เรียก Claude ได้เอง โดยการใช้งานคิดกับโควตาของผู้ชม ไม่ใช่ของผู้สร้าง ตอนเปิดตัวยังเรียก API ภายนอกไม่ได้และไม่มี persistent storage [4] (ภายหลังหน้า help ระบุว่ามี storage และ connector แล้ว [1])

**เทคนิคที่น่าสนใจ (มีเอกสารยืนยัน)** — จากเอกสาร Claude Code artifacts [2]
- viewer โหลด artifact จาก origin แยกที่ถูก sandbox คือ `*.claudeusercontent.com`
- ไฟล์ถูกห่อด้วย HTML shell และเสิร์ฟภายใต้ **CSP เข้มงวด** ที่อนุญาต script จาก CDN 5 แห่ง (cdnjs, unpkg, jsDelivr `/npm/`, Tailwind, jQuery) และฟอนต์จาก Google Fonts เท่านั้น ส่วนรูปภาพภายนอก, stylesheet/ฟอนต์อื่น และ `fetch`/XHR/WebSocket ถูกบล็อก ยกเว้นไป origin ของตัวเองกับ Google Fonts
- หน้าเริ่มดาวน์โหลดไฟล์เองไม่ได้ (บล็อกแม้แต่ลิงก์ `data:`/`blob:`) ต้องประกาศ capability "downloads" ก่อน
- เป็นหน้าเดียวที่ไม่มี backend และ relative link ใช้ไม่ได้ ขนาดหลัง render ต้องไม่เกิน 16 MiB
- เอกสารแนะนำให้ใช้ SVG หรือ HTML/CSS แทนภาพ raster ฝังในหน้า และให้ "summarize large datasets rather than inline them in full"
- แชร์สาธารณะแล้วผู้ชมที่ไม่ได้ล็อกอินจะเห็นป้าย "Content is user-generated and unverified."

**ข้อจำกัด**
- รายชื่อไลบรารีที่ติดตั้งมาให้ใน React artifact ของ claude.ai (เช่น Recharts, d3) **ไม่มีในเอกสารทางการที่พบ** มีแต่ในแหล่งรอง **[unverified]**
- วิธีตั้งค่า iframe `sandbox` token ของ claude.ai **not documented** เอกสารบอกเพียงว่าใช้ origin แยกและ CSP

**สิ่งที่ lit-storm ควรเอามาใช้**: แยก origin หรือใช้ opaque origin, CSP ที่บล็อก network ขาออก, ห้ามเริ่มดาวน์โหลดเอง และหลัก "ข้อมูลน้อยแต่สรุปดี" ดีกว่าฝังข้อมูลดิบทั้งหมด

### 2.2 Google Gemini — Deep Research + Canvas, visual reports

**สิ่งที่ผลิต**
- **Canvas** (มี.ค. 2025) สร้างและพรีวิว "HTML/React code and other web app prototypes" ได้ [6]
- เมนู **Create** ใน Canvas แปลงเนื้อหาเป็น web page, infographic, quiz, Audio Overview และ slides [9]
- release notes วันที่ 2025-05-20 ระบุว่าแปลง Deep Research reports เป็น "interactive displays, quizzes, infographics, and audio summaries" ได้ [8] และ Workspace Updates ยืนยันว่าสร้าง quiz จากรายงาน Deep Research ใน Canvas ได้ [10]
- **Visual reports** (2025-12-15, เฉพาะ Google AI Ultra): Deep Research สร้าง "custom images, charts and interactive simulations" รวมถึง diagram และ schematic ได้ [11] หน้า help ระบุว่าเมื่อใช้แหล่งข้อมูลจาก Google Workspace จะไม่มี visuals [12]
- ส่งออกรายงานไป Google Docs หรือแชร์เป็นลิงก์ได้ ส่วนลิงก์ Canvas ที่แชร์เปิดได้เฉพาะบน gemini.google.com [9][12]

**เทคนิคที่น่าสนใจ**: แยก "รายงานข้อความ" ออกจาก "สิ่งที่สร้างต่อจากรายงาน" (web page/infographic/quiz/audio) ผู้ใช้ต้องกดขอเอง ซึ่งตรงกับแนว on-demand ที่เสนอใน §8

**ข้อจำกัด / not documented**
- ไม่มีเอกสารว่า Gemini เลือก visual อย่างไร และ visual ผูกกับ citation อย่างไร [11]
- sandbox ของ Canvas preview **not documented** [9]
- ข้อความที่ว่า infographic ถูกสร้างเป็น "single HTML file" พบในแหล่งรองเท่านั้น **[unverified]**

### 2.3 Google NotebookLM — Mind Maps, Video/Audio Overviews

- **Mind Maps** สรุปแหล่งข้อมูลที่อัปโหลดเป็น "branching diagram" มีฟังก์ชันซูม/เลื่อน, พับ/กางกิ่ง, **เลือก node เพื่อถามต่อในแชต** และดาวน์โหลดได้ [13]
- **Studio** มี 4 ชนิดผลลัพธ์ ได้แก่ Audio Overviews, Video Overviews, Mind Maps และ Reports ส่วน Video Overviews เป็น "narrated slides" ที่ดึง "images, diagrams, quotes and numbers from your documents" มาใช้ [14]
- สิ่งที่ควรลอก: mind map ที่ **พับ/กางกิ่งได้** และเชื่อม node กับเนื้อหา ซึ่งใน lit-storm ทำได้ด้วยการกระโดดไปยัง section นั้น โดยไม่ต้องใช้ LLM **[อนุมาน]**

### 2.4 OpenAI ChatGPT — deep research, Canvas, data analysis charts

> help.openai.com และ openai.com ตอบ 403 (Cloudflare) ต่อการดึงโดยตรง ข้อความในส่วนนี้จึงมาจากผลค้นหาที่ index หน้าทางการเหล่านั้น **[snippet]**

- **Deep research**: รายงานเปิดใน "fullscreen report view" ดาวน์โหลดได้เป็น Markdown, Word, PDF [15] ตอนเปิดตัวประกาศว่า "in the next few weeks" จะเพิ่ม "embedded images, data visualizations, and other analytic outputs" [18] สถานะปัจจุบันของการมีกราฟในรายงาน deep research ยืนยันไม่ได้ **[unverified]**
- **Canvas**: React/HTML "rendered in a sandbox environment" มีปุ่ม Preview และ "code previews ... use a sandboxed environment" ถ้าต้องใช้ทรัพยากรภายนอก ChatGPT "may ask for permission before connecting" [16]
- **Data analysis**: กราฟ interactive รองรับ bar, line, pie, scatter ส่วนชนิดอื่น "may be returned as static images" และสลับระหว่าง static กับ interactive ได้ [17]
- สิ่งที่ควรลอก: **กราฟ interactive มีชนิดจำกัดชุดเล็ก ชนิดอื่น fallback เป็นภาพนิ่ง** ตรงกับแนวที่เสนอว่า block type ควรมีแค่ bar/line/pie/scatter
- sandbox ของ Canvas (origin, CSP) **not documented** ในส่วนที่เห็นได้

### 2.5 Perplexity — Labs, Pages

> perplexity.ai ตอบ 403 เช่นกัน **[snippet]**

- **Labs** (2025-05-30) "writes and executes code" เพื่อทำ chart, spreadsheet และ "simple interactive web apps" ในแท็บ **App** ส่วนไฟล์ทั้งหมด (chart, CSV, code) อยู่ในแท็บ **Assets** [19]
- **Pages**: หน้า help ระบุว่า "Create page" ถูก "temporarily retired" [20]
- สิ่งที่ควรลอก: รวม "สินทรัพย์ที่สร้าง" ไว้ที่เดียวให้ดาวน์โหลดได้ (ของ lit-storm คือเมนู export)

### 2.6 Manus, Genspark, Kimi, Microsoft Copilot Researcher

- **Manus**: จากไฟล์ข้อมูลสร้าง slide deck, interactive dashboard (ลิงก์ถาวร), report (PDF) และ webpage ได้ มี chart ได้สูงสุด 5 ชนิดต่อการวิเคราะห์หนึ่งครั้ง และรับเฉพาะ static dataset [21] เอกสารไม่บอกว่ารันโค้ดใน sandbox หรือไม่ (**not documented**)
- **Kimi Agent "OK Computer"** (2025-09-26): สร้างเว็บไซต์, interactive app, รายงาน, PPT และ data visualization แล้ว deploy โค้ดเป็น "shareable link" [22]
- **Genspark Sparkpages**: เป็นหน้าที่สร้างตาม query และมี "built-in AI copilot" [23] **[snippet]** รายละเอียดเรื่องกราฟและ citation **not documented** ในแหล่งที่เข้าถึงได้
- **Microsoft 365 Copilot Researcher**: รายงานมี "Visuals, charts, and graphs", "Organized sections" และ "Cited sources" [24] กลไกการสร้างกราฟ **not documented**
- **Grok**: ไม่พบเอกสารทางการเรื่องรายงาน HTML interactive จึงไม่ครอบคลุม

### 2.7 ข้อสังเกตรวมจาก frontier products **[อนุมาน]**

- ผลิตภัณฑ์ที่ **ให้โมเดลเขียนโค้ดเอง** (Claude, ChatGPT Canvas, Perplexity Labs, Manus, Kimi) ล้วนต้องมีโครงสร้าง sandbox/hosting ขนาดใหญ่ และไม่มีรายใดเปิดเผยวิธีผูก "ตัวเลขในกราฟ" กับ citation
- ในส่วนที่เข้าถึงได้ **ไม่มีผลิตภัณฑ์ใดบอกว่าตัวเลขในกราฟตรวจกับแหล่งอย่างไร** นี่คือช่องว่างที่ lit-storm ซึ่งมี evidence snippet อยู่แล้วทำได้ดีกว่า

---

## 3. Open source projects

### 3.1 STORM / Co-STORM (stanford-oval/storm) — MIT
- ผลลัพธ์เป็น **ข้อความล้วน** ได้แก่ `storm_gen_article_polished.txt`, `url_to_info.json` และ log ของบทสนทนาจำลอง ส่วน Co-STORM มี **mind map** แบบ "hierarchical concept structure" ด้วย UI ตัวอย่างเป็น Streamlit (demo light) [25]
- lit-storm เก็บ mind map ของ Co-STORM ไว้ใน state อยู่แล้ว (`server/src/litstorm/engines/costorm/engine.py` คีย์ `mind_map`) นำไปใช้เป็น mind map ของรายงาน Co-STORM ได้ทันที

### 3.2 GPT Researcher — Apache-2.0
- ส่งออก PDF, Docx, Markdown มีตัวเลือกสร้างภาพ inline ด้วย Gemini (`IMAGE_GENERATION_ENABLED`) และ "smart image scraping" [26]
- ในรายงานไม่มีกราฟข้อมูล ภาพที่ได้เป็นภาพประกอบ ไม่ใช่ข้อมูลที่ตรวจได้

### 3.3 Open deep-research ตัวอื่น
- **langchain-ai/open_deep_research** (MIT) และ **dzhng/deep-research** (MIT) ส่งออกเป็น markdown report (`report.md`/`answer.md`) ไม่มีกราฟ [27][28]
- **HF smolagents open_deep_research** เป็น agent ที่วัดผลด้วย GAIA ไม่ได้เน้นรายงานภาพ [31]
- **nickscamara/open-deep-research** เป็นแชตบนฐาน Vercel AI chatbot [30]
- **u14app/deep-research** (MIT) มี "one-click generation of knowledge graph" [29] ดูจากซอร์สแล้ว prompt ให้ LLM **คืนเฉพาะโค้ด Mermaid** แบบ `graph TD/LR` กำหนดให้ node id เป็นอักษรอังกฤษ, label อยู่ในเครื่องหมายคำพูดทุกตัว และ "double-check that all content complies with Mermaid syntax" [29a] ฝั่ง client เรียก `mermaid.parse(code, {suppressErrors: true})` ก่อน render ถ้า parse ไม่ผ่านก็ไม่ render [29b]
  - บทเรียน: การให้ LLM เขียน DSL ตรงๆ ต้องมีทั้ง prompt ที่เข้มงวดและ parse-check แนวที่เสนอใน §8 ปลอดภัยกว่า คือให้ LLM ส่ง nodes/edges เป็น JSON แล้ว **เราสร้างโค้ด Mermaid เอง** **[อนุมาน]**

### 3.4 Generative UI และโคลน Artifacts
- **A2UI** (Google, Apache-2.0, v0.9.x): "A2UI is a declarative data format, not executable code." ใช้ catalog ของ component ที่ client เชื่อถือ และ "flat list of components with ID references" เพื่อให้ LLM สร้างทีละส่วนได้ [33]
- **json-render** (Vercel Labs, Apache-2.0): catalog กำหนดด้วย Zod ทำให้ "AI can only use components in your catalog" และ stream/render ทีละส่วนได้ [32]
- **OpenUI** (W&B, Apache-2.0): ให้ LLM เขียน HTML แล้ว render สด [34]
- **E2B Fragments** (Apache-2.0): โคลน Artifacts ที่รันโค้ดใน E2B sandbox [35]
- **Microsoft LIDA** (MIT): pipeline ประกอบด้วย summarize → goals → generate viz code → VizOps (repair/evaluate/explain) พร้อมคำเตือนว่า "LIDA generates and executes code. Ensure that you run LIDA in a secure environment." [36]
- บทเรียน: เครื่องมือตระกูล "เขียนโค้ด" ต้องมี sandbox รันโค้ด ซึ่ง lit-storm ไม่มีและไม่ควรเพิ่ม ส่วนตระกูล "spec + catalog" เหมาะกับ lit-storm กว่า **[อนุมาน]**

### 3.5 เครื่องมือเอกสารโต้ตอบแบบ static
- **Quarto**: `embed-resources` ให้ไฟล์ HTML ที่ "needs no external files and no net access" (ใช้ `data:` URI) มี floating TOC ที่ไฮไลต์ตาม scroll, tabset (`panel-tabset`) และ **hover popup ของ citation/footnote/cross-ref** [37]
- **Observable Framework**: data loader "generate static snapshots of data during build" รวมถึง "server-side render a chart" ข้อดีคือหน้าเร็วและผู้ชมไม่ต้องเข้าถึงแหล่งข้อมูล [38] ตรงกับแนวคิด pre-render ของเรา
- **Evidence.dev** (MIT): chart เป็น component ใน markdown ที่ชี้ไปที่ query และในซอร์สสร้างบน **ECharts** (`core/src/user-components/common/echarts-options-attributes.ts`) [39] แปลว่า "ผู้เขียนระบุชนิดกราฟ + ฟิลด์ แล้ว component เป็นคนสร้าง option" ซึ่งเป็น pattern เดียวกับที่เสนอ
- **MyST**: อ้างอิง heading แล้วเห็นเนื้อหาถัดไปแบบ preview และซ้อนอ้างอิงต่อกันได้ [40]
- Streamlit / Datasette เป็น app ที่ต้องมี server ไม่เหมาะกับไฟล์เดียวออฟไลน์ จึงไม่ได้ลงรายละเอียด **[อนุมาน]**

---

## 4. เปรียบเทียบไลบรารีกราฟและแผนภาพ

ขนาดวัดจากไฟล์ minified ใน npm ตามเวอร์ชันล่าสุดวันที่ 2026-10-01 (raw / gzip -9) license มาจาก npm registry [41]

| ไลบรารี (เวอร์ชัน) | License | ขนาด raw / gz | spec หรือ code (LLM ส่ง JSON ได้?) | SVG / canvas | ฝังไฟล์เดียวไม่ใช้ CDN | print/PDF | accessibility | หมายเหตุ |
|---|---|---|---|---|---|---|---|---|
| **Apache ECharts** 6.1.0 | Apache-2.0 | 1,095 / 359 KB (full) · 488 / 164 KB (`echarts.simple`) | **JSON option** ได้ (ยกเว้น formatter ที่เป็น function) | ทั้งสองแบบ SVG คมเมื่อซูม, canvas เหมาะข้อมูล >1k จุด [43] | ได้ และ **SSR เป็น SVG string ได้โดยไม่มี dependency** มี client runtime เบาๆ ~4 KB สำหรับ legend/highlight แต่ไม่มี tooltip [42] | SVG คม | aria สร้างคำบรรยายจากข้อมูลอัตโนมัติ (ปิดเป็นค่าเริ่มต้น) และ decal สำหรับตาบอดสี [44] | มี `i18n/langTH.js` [41] ใช้ใน Evidence [39] |
| **Chart.js** 4.5.1 | MIT | 203 / 68 KB | config เป็น JSON ได้บางส่วน callback เป็น function | canvas เท่านั้น | ได้ | เป็นภาพ bitmap **[อนุมาน]** | canvas "will not be accessible to screen readers" ต้องใส่ `role="img"`/`aria-label`/fallback เอง [51] | render ฝั่ง server ต้องใช้ node-canvas |
| **Vega-Lite** 6.4.3 + Vega 6.4.0 + vega-embed 7.3.0 | BSD-3-Clause | 244+508+58 = 810 / 272 KB | **JSON spec ล้วน** (grammar of graphics) เหมาะให้ LLM ส่งที่สุด | SVG/canvas | ได้ และ headless ใน Node ได้ (`view.toSVG()`, `vg2svg`) [45] | SVG คม | mark มี `aria`/`description` (SVG เท่านั้น) [46] | **ไม่ผ่าน CSP มาตรฐาน** เพราะใช้ `Function` constructor ต้องเปลี่ยนไปใช้ expression interpreter ที่ CSP-compliant [45] |
| **Plotly.js** 4.1.1 (dist-min) | MIT | 4,702 / 1,433 KB | **JSON figure** (data+layout) | SVG (+WebGL บาง trace) | ได้แต่ใหญ่มาก | ส่งออก png/svg/jpeg/webp ได้จาก modebar [53] | — | ใหญ่เกินสำหรับไฟล์ export **[อนุมาน]** |
| **Observable Plot** 0.6.17 (+ d3) | ISC | 204 / 67 KB + d3 273 / 90 KB | เป็นโค้ด JS (option object แต่ mark เป็น function call) | SVG | ได้ และ SSR ได้ผ่าน `document` option (virtual DOM) [52b] | SVG คม | `ariaLabel`/`ariaDescription` ระดับ plot และ mark [52] | |
| **D3** 7.9.0 | ISC | 273 / 90 KB | **code เท่านั้น** | SVG/canvas | ได้ | — | ต้องทำเองทั้งหมด | ไม่เหมาะให้ LLM สร้าง |
| **Mermaid** 12.0.0 | MIT | **5,444 / 1,558 KB** | **DSL ข้อความ** มี `mermaid.parse()` สำหรับ validate [47] | SVG | ได้แต่ใหญ่มาก จึงควร pre-render ด้วย mermaid-cli (Puppeteer) หรือ Chromium ของเรา [50] | SVG | `accTitle`/`accDescr` → `<title>`/`<desc>` + `aria-roledescription` [48] | `securityLevel` ค่าเริ่มต้น `strict` (encode HTML, ปิด click) [47] markdown string ตัดบรรทัดอัตโนมัติ [49] |
| **markmap** (view 0.18.12) | MIT | view 48 / 11 KB (+ d3) · lib 661 / 167 KB | tree JSON หรือ markdown | SVG | ได้ | — | — | mind map จาก markdown [54] ไม่ต้องใช้ `markmap-lib` ถ้าสร้าง tree จาก sections เอง |
| **Cytoscape.js** 3.34.3 | MIT | 425 / 133 KB | JSON elements | canvas | ได้ | bitmap **[อนุมาน]** | — | graph ขนาดใหญ่ |
| **vis-network** 10.1.2 | Apache-2.0 OR MIT | 636 / 150 KB | JSON nodes/edges | canvas | ได้ | — | — | |
| **Leaflet** 1.9.4 | BSD-2-Clause | 144 / 41 KB | code + GeoJSON | SVG/canvas | ตัวไลบรารีได้ แต่ **tile แผนที่ต้องดึงจาก server ภายนอก** ซึ่งขัดนโยบายไม่ยิง third-party **[อนุมาน]** | — | — | ถ้าจำเป็นใช้ GeoJSON outline ที่ฝังในไฟล์แทน |
| **KaTeX** 0.18.10 | MIT | JS 266 / 74 KB + CSS 24 KB (+ฟอนต์) | TeX string | HTML | ได้ | ดี | — | รายงานส่วนใหญ่ไม่ต้องใช้ ข้ามได้ |

**ภาษาไทย**
- SVG `<text>` และ canvas ไม่ตัดบรรทัดตามคำ **[อนุมาน จากพฤติกรรม SVG/canvas ทั่วไป]**
- ภาษาไทยไม่มีช่องว่างระหว่างคำ การตัดคำจึงต้องใช้ตัวตัดคำ เช่น `Intl.Segmenter` ที่ MDN ยกไทยเป็นตัวอย่างและเป็น Baseline 2024 [60]
- Mermaid ใช้ HTML label และตัดบรรทัดอัตโนมัติ [49] เมื่อ pre-render ใน Chromium จึงได้การตัดบรรทัดแบบ ICU ของเบราว์เซอร์ ซึ่งเป็นเหตุผลเดียวกับที่ ADR 0005 เลือก Chromium ทำ PDF **[อนุมาน, ควรทดสอบ]**
- ECharts SSR ใน Node วัดความกว้างข้อความโดยไม่มีเบราว์เซอร์ ความแม่นกับอักษรไทย (สระบน/ล่าง) **ยังไม่ได้ตรวจ** จึงควร pre-render ใน Chromium แทน Node **[อนุมาน]**
- ฟอนต์: `@fontsource/noto-sans-thai` subset ไทย woff2 มีขนาด ~9 KB ต่อน้ำหนัก [67] ฝังเป็น data URI ได้ ทำให้ไฟล์แสดงผลเหมือนกันทุกเครื่อง ขณะที่ HTML export ปัจจุบันพึ่งฟอนต์ระบบ

**คำตัดสิน**
- **ECharts** ใช้เป็นเครื่องยนต์กราฟตัวเดียว (bar/line/pie/scatter และ tree/graph สำหรับ mind map หรือ network ถ้าต้องการ)
- **Mermaid** ใช้สำหรับแผนภาพ flow/ลำดับขั้น โดย pre-render เท่านั้น
- ส่วนที่เหลือทำเป็น **HTML/CSS ล้วน** ได้แก่ timeline, ตารางเปรียบเทียบ, key-stat cards, glossary
- Vega-Lite เป็นตัวเลือกที่ดีรองลงมา (spec เป็น JSON ล้วน) แต่ติดปัญหา CSP และขนาดรวมใหญ่กว่า
- ข้อสำคัญ: เนื่องจาก LLM ส่ง **schema ของเราเอง** ไม่ใช่ option ของไลบรารี การเปลี่ยนไลบรารีภายหลังจึงแก้แค่ renderer

---

## 5. สถาปัตยกรรมการสร้าง (generation architecture)

### 5.1 ทางเลือก

| ทางเลือก | ตัวอย่าง | ข้อดี | ข้อเสียสำหรับ lit-storm |
|---|---|---|---|
| A. LLM เขียน HTML/JS อิสระทั้งหน้า | Claude Artifacts, ChatGPT Canvas, OpenUI, Kimi, Manus [2][16][34][22][21] | ยืดหยุ่นสูงสุด หน้าตาหลากหลาย | ต้อง sandbox แข็งแรง, ใช้ token มาก ("more token-intensive" [2]), ตรวจตัวเลขไม่ได้, รูปแบบไม่คงที่, เสี่ยง script/ลิงก์แปลกปลอม, แปลภาษาหรือพิมพ์ได้ไม่สม่ำเสมอ |
| B. LLM เขียนโค้ดวิเคราะห์ + รันใน sandbox แล้วได้ภาพ | ChatGPT data analysis, Perplexity Labs, LIDA, E2B [17][19][36][35] | คำนวณจริงจาก dataset | lit-storm ไม่มี dataset มีแต่ข้อความและ snippet และต้องมี code sandbox เพิ่ม |
| C. LLM ส่ง **spec ของไลบรารี** (Vega-Lite JSON / ECharts option / Mermaid DSL) | u14app knowledge graph (Mermaid) [29a] | ถูก, LLM รู้จัก spec ดี | spec กว้างเกิน (ECharts option มีเป็นพันคีย์), มีช่อง inject เช่น `formatter`, `href` หรือ Mermaid `click`, ต้องตรวจ syntax |
| D. **LLM ส่ง JSON ตาม schema แคบของเรา → renderer ของเราแปลงเป็น spec ไลบรารี** | A2UI, json-render, Evidence [33][32][39] | ตรวจได้ทุกฟิลด์, แนบ citation ต่อจุดข้อมูลได้, ปลอดภัยโดยโครงสร้าง, เปลี่ยนไลบรารีได้, token น้อย | ชนิดภาพจำกัดตาม catalog |
| E. ไม่ใช้ LLM (deterministic) | — | ฟรีและถูกต้องแน่นอน | ทำได้เฉพาะภาพเชิงโครงสร้าง (mind map, source network, ตารางแหล่ง) |

**ข้อเสนอ: D + E** (ดู §8)

### 5.2 Validation / repair loop
- ใช้ structured output เมื่อ provider รองรับ LiteLLM รับ `response_format: {type: "json_schema", ...}` และมี `supports_response_schema()` ถ้าโมเดลไม่รองรับ ให้ตั้ง `litellm.enable_json_schema_validation=True` เพื่อ validate ฝั่ง client [66] (Claude ก็มี structured outputs ที่ compile schema เป็น grammar [65] **[snippet]**)
- ขั้นต่อจาก JSON Schema ต้องมี **validator เชิงความหมาย** ที่ไม่ใช้ LLM (§5.3)
- ถ้ามี error ให้ส่ง "รายการ error" กลับไป repair **ไม่เกิน 1 ครั้ง** แนวเดียวกับ VizOps "repair" ของ LIDA [36] ถ้ายังไม่ผ่านก็ **ตัด block นั้นทิ้ง** ไม่ต้องหยุดทั้งรายงาน
- Mermaid: เราเป็นคนสร้าง source จาก nodes/edges จึงไม่ควรมี syntax error แต่ยังเรียก `mermaid.parse()` ตอน pre-render เป็น guard ได้ [47]

### 5.3 กันตัวเลขมโน (anti-hallucination) **[ข้อเสนอของผู้เขียน]**

1. **ข้อมูลเข้าต้องมาจากรายงานเท่านั้น** ป้อน LLM ด้วย "fact sheet" ที่ดึงแบบ deterministic ได้แก่ ประโยคใน `lead`/`body` ที่มีตัวเลข (รวมเลขไทย ๐–๙, %, หน่วย) พร้อม `[n]`, และ evidence snippet ของแหล่งที่ถูกอ้างซึ่งมีตัวเลข ไม่ต้องให้ LLM ค้นเว็บเพิ่ม
2. **จุดข้อมูลทุกจุดต้องมี `cite: {source, quote}`** และ validator ตรวจว่า
   - `source` มีอยู่ใน `report.sources`
   - `quote` (normalize ช่องว่าง/เลขไทย/จุลภาค) เป็น substring ของ `evidence[]` ของแหล่งนั้น หรือของประโยคในรายงานที่อ้าง `[source]`
   - ค่าตัวเลข `y` (หรือ `value`) ปรากฏใน `quote` โดยยอมให้ต่างกันตามรูปแบบ เช่น 12.5 ↔ ๑๒.๕ ↔ 12,5
   - หน่วยของทุก series ใน chart เดียวกันตรงกัน และ `as_of`/ปีไม่ขัดกัน
3. **Engine ที่ไม่มี evidence** (report schema อนุญาต evidence ว่าง) ให้ยอมรับได้เฉพาะตัวเลขที่อยู่ในประโยคของรายงานที่มี `[n]` กำกับ และแสดงป้าย "อ้างจากข้อความรายงาน ไม่ใช่ข้อความต้นฉบับ" ตามหลักของ `render/html.py` ที่บอกผู้อ่านตรงๆ ว่าไม่มีหลักฐาน
4. **renderer บังคับรูปแบบที่ไม่หลอกตา**: bar เริ่มที่ 0, ห้ามแกนคู่, pie ต้องรวมได้ ~100% (ไม่อย่างนั้นเปลี่ยนเป็น bar), เรียงเวลาเอง, และแสดง "ที่มา: [n]" ใต้กราฟทุกตัว
5. **ถ้าจุดข้อมูลถูกตัดจนเหลือน้อยกว่าเกณฑ์** (เช่น < 2 จุด หรือถูกตัด > 50%) ให้ตัดทั้ง block ห้ามให้ LLM "เติม" ข้อมูล

---

## 6. ความปลอดภัย / sandboxing — checklist

| # | ข้อ | ที่มา |
|---|---|---|
| 1 | LLM **ไม่ส่ง HTML/JS/CSS/URL ใดๆ** ทุกฟิลด์เป็นข้อความหรือตัวเลข renderer escape ทุก string (แนวเดียวกับที่ `render/html.py` และ `report.tsx` ใช้ markdown-it `html: false` อยู่แล้ว) | markdown-it: ปิด HTML แล้ว "Output will be safe without sanitizer" และบล็อก `javascript:`/`vbscript:`/`file:`/`data:` (ยกเว้นรูปบางชนิด) [63] |
| 2 | ลิงก์ที่ออกไปนอกหน้าต้องมาจาก `report.sources[].url` ที่ตรวจ `^https?://` แล้วเท่านั้น (ตามที่ `render/html.py` ทำ) ใส่ `rel="noopener noreferrer"` | [อนุมาน] |
| 3 | ในไฟล์ export ใส่ `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; font-src data:; style-src 'unsafe-inline'; script-src 'sha256-…'">` ไม่มี `connect-src` ทำให้ fetch/XHR/WebSocket ถูกบล็อกทั้งหมด script ที่รันได้คือ script ของเราที่คำนวณ hash ตอน render | CSP รองรับ hash สำหรับ inline script และมี `connect-src` [56] |
| 4 | ข้อจำกัดของ meta CSP: `sandbox`, `frame-ancestors`, `report-uri` ใช้ใน `<meta>` ไม่ได้ ต้องส่งเป็น HTTP header | [56][57] |
| 5 | เมื่อเสิร์ฟไฟล์ interactive จาก API ให้เพิ่ม header `Content-Security-Policy: sandbox allow-scripts` (บวก CSP ข้อ 3) ต่อให้ผู้ใช้เปิด URL ตรงบน origin ของ lit-storm ก็จะรันใน opaque origin | CSP `sandbox` "applies restrictions ... enforcing a same-origin policy" [57] |
| 6 | พรีวิวในเว็บแอปใช้ `<iframe sandbox="allow-scripts">` **ห้าม** เติม `allow-same-origin` (ถ้า same-origin + allow-scripts ตัวหน้าลบ sandbox เองได้) และไม่ให้ `allow-top-navigation`/`allow-popups` ถ้าลิงก์แหล่งต้องเปิดแท็บใหม่ ให้พิจารณา `allow-popups allow-popups-to-escape-sandbox` เป็นการเฉพาะ | MDN iframe [55] |
| 7 | ถ้าใช้ `srcdoc` เอกสาร srcdoc **รับ CSP ของหน้าแม่** ด้วย ถ้าวันหนึ่ง SPA มี CSP ต้องไม่บล็อก inline script ของ iframe หรือเลือกใช้ `src` ชี้ไปที่ endpoint ที่มี header ของตัวเองแทน | CSP spec (ข้อความเรื่อง iframe srcdoc) [58] · MDN srcdoc [55] |
| 8 | session cookie ของ lit-storm เป็น `HttpOnly; SameSite=Lax` และมี CSRF cookie แบบ double-submit (`server/src/litstorm/api/auth.py`) iframe ที่ไม่มี `allow-same-origin` อ่าน CSRF cookie ไม่ได้ และคำขอ `fetch` ข้าม site จะไม่แนบ cookie Lax | MDN SameSite=Lax: ไม่ส่งกับ `fetch()` ข้าม site หรือ "navigations inside `<iframe>`" [59] · การที่ opaque origin นับเป็น cross-site เป็น **[อนุมาน]** |
| 9 | pre-render ใน Chromium ให้ปิด network ทั้งหมด (`page.route("**/*", abort)`) ตามที่ `render/pdf.py` ทำอยู่ และโหลดไลบรารีจากไฟล์ vendored ใน image ไม่โหลดจาก CDN | ตามนโยบาย lit-storm (ไม่ยิง third-party) |
| 10 | Mermaid ให้ใช้ `securityLevel: 'strict'` (ค่าเริ่มต้น) และไม่สร้าง `click` directive | [47] |
| 11 | ถ้าใช้ Vega ต้องเปลี่ยน expression interpreter ให้ CSP-compliant (ไม่แนะนำ ใช้ ECharts แทน) | [45] |
| 12 | ไฟล์ export ห้ามมี key หรือข้อมูลภายในใดๆ (ตามที่ design doc กำหนดว่าห้ามเก็บ key ในไฟล์ export) | `docs/web-app-design.md` |
| 13 | ตัวอย่างอ้างอิงในอุตสาหกรรม: Claude แยก origin (`*.claudeusercontent.com`) + CSP เข้ม + บล็อกการเริ่มดาวน์โหลดเอง [2] ส่วน ChatGPT ใช้ "sandboxed environment" และขออนุญาตก่อนเชื่อมต่อภายนอก [16] **[snippet]** | |

---

## 7. Citations และ UX patterns ที่ควรลอก

### 7.1 Citation / provenance
- **Citation ต่อจุดข้อมูล** แนบ `cite` ทุกค่า แล้วแสดงใน tooltip หรือในตาราง "ข้อมูลของกราฟ" เป็น `[n]` ที่กดไปรายการแหล่งได้ **[ข้อเสนอ]** แนวคิดมาจาก `cited_text` ของ Claude Citations ที่ชี้กลับไปที่ข้อความต้นฉบับได้เสมอ [64]
- **Hover card ของ citation** แบบ Quarto/MyST ที่แสดงเนื้อหาอ้างอิงเมื่อ hover [37][40] ทำด้วย Popover API ได้โดยไม่ต้องใช้ JS (`popover`/`popovertarget`, Baseline 2025) [61] แสดงชื่อแหล่ง, domain และ evidence ท่อนแรก ซึ่งตรงกับแผงด้านข้างของ `report.tsx`
- **"ที่มา" ใต้กราฟทุกตัว** แบบ caption ของ figure พร้อมป้ายเมื่อข้อมูลมาจากหลายแหล่ง ("ตัวเลขจาก 3 แหล่ง ปีต่างกัน")
- **ตารางแหล่งอ้างอิงแบบเรียงและกรองได้** (domain, จำนวนครั้งที่อ้าง, มี/ไม่มี evidence)
- **Source network**: bipartite graph ระหว่าง section กับ source สร้างจาก `[n]` ได้เลย (ไม่ใช้ LLM) ถ้าจะให้ดูง่ายในไฟล์เดียว อาจทำเป็น matrix/heatmap แทน graph **[อนุมาน]**

### 7.2 UX patterns

| Pattern | แหล่งแรงบันดาลใจ | วิธีทำในไฟล์เดียว |
|---|---|---|
| TOC ลอยที่ไฮไลต์ตาม scroll | Quarto floating TOC [37] | `IntersectionObserver` + CSS sticky (JS สั้นๆ) |
| แท็บ (เช่น กราฟ / ตารางข้อมูล) | Quarto `panel-tabset` [37] | ปุ่ม + `role="tablist"` (WAI-ARIA tabs) |
| ส่วนพับได้ | Quarto/`<details>` | `<details>` ต้องเปิดทั้งหมดก่อนพิมพ์ (ข้อสังเกตเดิมใน `render/html.py`: Chromium ไม่พิมพ์เนื้อหาใน `<details>` ที่ปิด) |
| Mind map ย่อ/ขยายกิ่ง, คลิกแล้วไป section | NotebookLM [13], markmap [54], Co-STORM [25] | ECharts `tree` pre-render หรือ `<details>` ซ้อนเป็นทางสำรองที่พิมพ์ได้ |
| Timeline | Kimi/Manus-style reports [22][21] | `<ol>` + CSS เส้นเวลา (ไม่ต้องใช้ไลบรารี) |
| ตารางเปรียบเทียบ เรียงหรือกรองได้ | ChatGPT/Perplexity-style dashboards | `<table>` + ปุ่มใน `<th>` + `aria-sort` ตาม APG [62] |
| Key-stat cards | Researcher/Manus dashboards [24][21] | `<dl>` grid พร้อม `[n]` |
| Glossary hover card | Quarto hover refs [37] | Popover API [61] |
| สลับโหมดมืด/สว่าง | Claude artifacts (theming) [2] | CSS variables + `prefers-color-scheme` + ปุ่มสลับ (กราฟ pre-render ต้องใช้สีผ่าน CSS variable หรือ render 2 ชุด) **[อนุมาน]** |
| Responsive | — | SVG `viewBox` + `width:100%` |
| Print stylesheet / PDF | lit-storm ปัจจุบัน | SVG พิมพ์คม, ซ่อนปุ่มโต้ตอบ, เปิด `<details>` ทั้งหมด, `break-inside: avoid` ที่ figure |
| ไฟล์เดียวดาวน์โหลดได้ | Quarto `embed-resources` [37] | ฝังทุกอย่าง (CSS, JS, ฟอนต์ subset, SVG) |
| ตารางข้อมูลแทนกราฟ (a11y) | Chart.js fallback content [51], ECharts aria [44] | `<table>` ใต้กราฟทุกตัว + `role="img"` + `aria-label` |

---

## 8. ข้อเสนอสำหรับ lit-storm

### 8.1 ภาพรวม

```
report.json (เดิม ไม่แก้)
   │
   ├─► [E] deterministic: mind map (sections), source network ([n]), ตารางแหล่ง  ── ฟรี
   │
   └─► fact sheet (ดึงประโยค/evidence ที่มีตัวเลข) ─► [D] LLM เร็ว 1 ครั้ง ─► JSON blocks
                                                            │
                                            validator (schema + cite + ตัวเลข + หน่วย)
                                                            │  (repair ≤ 1 ครั้ง / ตัดทิ้ง)
                                                            ▼
                                                   visuals.json (ข้าง report.json)
                                                            │
                     renderer (Python) + Chromium pre-render (network ปิด, libs vendored)
                                                            ▼
                                  interactive.html ไฟล์เดียว (inline SVG + JS เล็ก + CSP)
                                    ├─ ดาวน์โหลด (export format ใหม่ "html-interactive")
                                    └─ พรีวิวในหน้า Report ผ่าน iframe sandbox
```

### 8.2 สิ่งที่ LLM ส่งออก — schema ร่างของ `visuals.json`

```jsonc
{
  "schema": 1,
  "report": "sha256 ของ report.json ตอนสร้าง",      // ผูกกับรายงานฉบับนั้น
  "model": "provider/model", "created_at": "ISO-8601",
  "blocks": [
    { "id": "v1", "type": "stat_cards",
      "anchor": { "section": "s2" },                   // ใส่ท้าย section ใด (หรือ "lead")
      "title": "ตัวเลขสำคัญ",
      "items": [
        { "label": "สัดส่วนผู้ใช้", "value": 42.5, "unit": "%", "as_of": "2024",
          "cite": [{ "source": 3, "quote": "ร้อยละ 42.5 ของผู้ตอบ..." }] }
      ] },

    { "id": "v2", "type": "chart", "chart": "bar",     // bar | line | pie | scatter
      "anchor": { "section": "s3" },
      "title": "…", "x": { "label": "ปี", "kind": "category" },   // category | time | value
      "y": { "label": "มูลค่า", "unit": "ล้านบาท" },
      "series": [
        { "name": "…", "points": [
          { "x": "2022", "y": 120, "cite": { "source": 5, "quote": "…120 ล้านบาท…" } }
        ] }
      ],
      "note": "ข้อควรระวังในการอ่าน (ถ้ามี)" },

    { "id": "v3", "type": "timeline", "anchor": { "section": "s1" },
      "events": [
        { "date": "2019-05", "precision": "month", "label": "…", "detail": "…",
          "cite": [{ "source": 2, "quote": "…" }] }
      ] },

    { "id": "v4", "type": "comparison", "anchor": { "section": "s4" },
      "columns": [{ "key": "cost", "label": "ต้นทุน", "kind": "text" }],   // text | number | yes_no
      "rows": [
        { "label": "ทางเลือก A",
          "cells": { "cost": { "value": "สูง", "cite": [{ "source": 7, "quote": "…" }] } } }
      ] },

    { "id": "v5", "type": "diagram", "kind": "flow",   // flow | hierarchy | cycle
      "direction": "LR", "anchor": { "section": "s2" },
      "nodes": [{ "id": "n1", "label": "…" }],
      "edges": [{ "from": "n1", "to": "n2", "label": "…" }],
      "cite": [{ "source": 4, "quote": "…" }] },

    { "id": "v6", "type": "glossary",
      "terms": [{ "term": "…", "definition": "…", "cite": [{ "source": 1, "quote": "…" }] }] }
  ]
}
```

**กติกาที่ validator บังคับ**
- ขอบเขตขนาด: blocks ≤ 6, series ≤ 4, points ≤ 30, nodes ≤ 15, rows ≤ 12, ข้อความ ≤ 120 ตัวอักษร
- `id` ของ node ต้องตรง `^[a-z][a-z0-9_]{0,15}$`
- `anchor.section` ต้องมีจริงใน `report.sections`
- `cite` ตรวจตาม §5.3
- ภาษาของ label ต้องตรง `report.language` (ตรวจสัดส่วนอักษรไทยแบบคร่าวๆ)

**ภาพที่ไม่อยู่ใน schema** ได้แก่ mind map, source network และตารางแหล่ง renderer สร้างเองจาก `report.json` สำหรับ Co-STORM ใช้ `mind_map` ของ Discussion ได้ถ้ามี

### 8.3 Renderer: `report.json` + `visuals.json` → HTML ไฟล์เดียว
1. **คอมไพล์ block เป็น spec ไลบรารี** (Python ล้วน)
   - `chart` → ECharts option (SVG renderer, locale TH, aria on, ไม่มี function)
   - `diagram` → Mermaid source ที่เราสร้างเอง (label ครอบด้วย `"…"` และ escape อักขระพิเศษ)
   - `timeline`/`comparison`/`stat_cards`/`glossary` → HTML template ธรรมดา (Jinja หรือ f-string แบบเดียวกับ `render/html.py`)
2. **Pre-render เป็น SVG** ใน Chromium ที่ใช้ทำ PDF อยู่แล้ว
   - เปิดหน้าว่าง, บล็อก network, inject `echarts.min.js`/`mermaid.min.js` จากไฟล์ vendored
   - render แล้วดึง `outerHTML` ของ `<svg>` ครั้งเดียวสำหรับทุก block
   - ตัดบรรทัด label ไทยด้วย `Intl.Segmenter('th', {granularity:'word'})` ก่อน render [60]
3. **ประกอบหน้า**: ต่อยอด `render/html.py` (สารบัญ, citation, evidence) แล้วแทรก figure ตาม `anchor`
   - figure แต่ละอันประกอบด้วย `<svg role="img" aria-label>`, caption "ที่มา [n]" และแท็บ "ตารางข้อมูล" ที่ citation ต่อแถว
4. **JS inline ของเราเอง** (เป้าหมาย < 15 KB)
   - TOC scrollspy, แท็บ, เรียงและกรองตาราง, popover ของ citation/glossary (Popover API และ fallback), ปุ่มสลับธีม, ปุ่มพิมพ์
   - คำนวณ sha256 ใส่ใน meta CSP
5. **ตัวเลือก "กราฟโต้ตอบเต็ม"**: ฝัง `echarts.min.js` (~1.1 MB) แล้ว hydrate จาก option เดิมเพื่อให้มี tooltip/zoom ขนาดไฟล์ยังต่ำกว่าเพดาน 16 MiB ของ Claude artifacts มาก [2] (ใช้เป็นหลักอ้างอิงคร่าวๆ)
6. **ฟอนต์**: ฝัง Noto Sans Thai subset ไทย + ละติน 400/700 เป็น data URI (~40 KB รวม) **[อนุมาน จากขนาด subset ไทย ~9 KB/น้ำหนัก [67]]**
7. **PDF**: พิมพ์จากหน้าเดียวกัน (โหมด static) กราฟเป็นเวกเตอร์เพราะเป็น SVG

### 8.4 ตำแหน่งในไปป์ไลน์
- **ขั้นใหม่หลังรายงานเสร็จ** ไม่แทรกใน Engine ทำให้ใช้ได้กับทุก Engine (STORM, Co-STORM, agent, Deep Research) เพราะทุก Engine ส่งออก `report.json` รูปเดียวกัน (ADR 0005)
- **สร้างตอนผู้ใช้กดขอครั้งแรก** (ปุ่ม "สร้างรายงานแบบโต้ตอบ" หรือ export `html-interactive`) แล้ว cache เป็น `visuals.json` ข้าง `report.json` รอบถัดไปไม่เรียก LLM อีก
  - ทางเลือก: ผู้ดูแลเปิด "สร้างอัตโนมัติท้าย Run" ได้ ใช้งบของ Run นั้น
- **โมเดล**: ใช้ "โมเดลเร็ว" ตาม ADR 0006 ถ้าไม่ได้ตั้ง ให้ใช้โมเดลหลักของ Run นั้น
- **การนับค่าใช้จ่าย/โควตา**: บันทึกลง cost ของ Run เดิมตามโมเดล ถ้าเป็น on-demand ให้มี daily cap แบบ `refine.py` (เรียกจาก API ไม่ต้องผ่าน Worker) ส่วน pre-render ต้องใช้ Chromium ซึ่ง API ใช้ทำ PDF export อยู่แล้ว (`api/research.py`)
- ไฟล์ HTML เดิมและ Markdown/PDF ยังเหมือนเดิม "interactive" เป็น format เพิ่ม ไม่ได้แทนของเดิม

### 8.5 ในเว็บแอป
- หน้า Report เพิ่มแท็บหรือปุ่ม "มุมมองภาพ" ที่โหลด `interactive.html` ใน `<iframe sandbox="allow-scripts" src="…/export?format=html-interactive&inline=1">` และส่ง header `Content-Security-Policy: sandbox allow-scripts; default-src 'none'; …` จาก API
- ระยะต่อไป (ไม่บังคับ): render block เดียวกันใน React โดยตรงเพื่อให้กด citation แล้วเปิดแผงแหล่งเดิมของ `report.tsx` ได้ ส่วน JSON ยังใช้ชุดเดียวกัน

### 8.6 ประมาณค่าใช้จ่ายต่อรายงาน **[อนุมาน]**
- จาก `docs/benchmarks/2026-09-30-baseline.md` (Gemini 3.1 Flash Lite) แก้สมการจาก 3 Run ได้อัตราประมาณ **$0.25/1M token ขาเข้า และ $1.5/1M token ขาออก**
- **การเรียกหลัก 1 ครั้ง**: fact sheet 8–15k token เข้า, JSON 2–4k token ออก ≈ **$0.005–0.008**
- **repair (ถ้ามี) 1 ครั้ง**: ≈ +$0.002–0.004 (ส่งเฉพาะ block ที่ผิดพร้อม error)
- **รวม ≈ $0.005–0.012 ต่อรายงาน** เทียบกับ Run ระดับมาตรฐานที่ $0.017–0.025 ถ้าสร้างอัตโนมัติทุก Run ค่าใช้จ่ายจะเพิ่มราว 25–50% จึงแนะนำ on-demand
- ส่วน deterministic (mind map, network) และ pre-render **ไม่ใช้ LLM** แต่ใช้ CPU/เวลา Chromium ราว 1–3 วินาทีต่อรายงาน **[อนุมาน ต้องวัด]**

### 8.7 ความเสี่ยง
| ความเสี่ยง | การลดความเสี่ยง |
|---|---|
| ตัวเลขผิดหรือมโน | validator §5.3, ตัด block ที่ไม่ผ่าน, แสดง "ที่มา" ทุกกราฟ |
| เอาตัวเลขที่เทียบกันไม่ได้มาใส่กราฟเดียวกัน (ต่างปี ต่างนิยาม ต่างแหล่ง) | บังคับ unit เดียว, `as_of`, ป้ายเตือนเมื่อหลายแหล่ง, ใช้ตารางแทนกราฟถ้าไม่แน่ใจ |
| รายงานส่วนใหญ่ไม่มีตัวเลขพอทำกราฟ | ยอมให้ได้ 0 block แล้วยังมี mind map/timeline/ตารางเปรียบเทียบ ไม่บังคับให้ต้องมีกราฟ |
| label ไทยล้น/ตัดคำผิดใน SVG | ตัดคำด้วย `Intl.Segmenter` ใน Chromium, จำกัดความยาว label, ทดสอบด้วยรายงานไทยจริง |
| ไฟล์ใหญ่ | โหมด static เป็นค่าเริ่มต้น ECharts เต็มเป็นตัวเลือก ไม่ฝัง Mermaid runtime |
| อัปเดตไลบรารีแล้ว SVG เปลี่ยน | pin เวอร์ชันและ vendor ใน image, snapshot test ของ SVG |
| ปัญหา license ของไฟล์ที่แจกจ่าย | Apache-2.0 (ECharts) และ MIT (Mermaid) ต้องคงข้อความ license/notice ไว้ ใส่ comment license ไว้ในไฟล์เมื่อฝัง runtime **[อนุมาน, ควรให้ผู้ดูแลตรวจ]** |
| XSS ผ่าน label | LLM ส่งได้เฉพาะ string, escape ทุกจุด, CSP + sandbox, Mermaid `strict` |
| โมเดลบางตัวไม่รองรับ JSON schema | LiteLLM client-side validation [66] + parser แบบ `refine.py` + repair 1 ครั้ง |

### 8.8 คำถามเปิดสำหรับเจ้าของ
1. สร้างภาพแบบ **on-demand** (แนะนำ) หรือ **อัตโนมัติท้ายทุก Run**? ถ้า on-demand จะนับเข้าโควตาหรือใช้ daily cap แบบ refine?
2. โหมดเริ่มต้นเป็น **static SVG** (ไฟล์เล็ก พิมพ์ดี ไม่มี tooltip) หรือ **ECharts เต็ม** (tooltip/zoom +~1.1 MB)?
3. อยากให้ "HTML interactive" **แทน** HTML export เดิม หรือเป็น format ที่ 4?
4. Engine ที่ evidence ว่าง (agent) ควร**ไม่ทำกราฟตัวเลขเลย** หรือยอมใช้ตัวเลขจากประโยคที่มี `[n]` พร้อมป้ายเตือน?
5. ต้องการ mind map แบบ interactive (ต้องฝัง JS) หรือแบบ `<details>` ซ้อนที่พิมพ์ได้ก็พอ?
6. ยอมรับการฝังฟอนต์ไทย subset ในไฟล์ (~40 KB) เพื่อให้หน้าตาเหมือนกันทุกเครื่องหรือไม่?
7. ต้องการให้ผู้ใช้**แก้หรือลบ block** ก่อน export (เช่น ตัดกราฟที่ไม่ชอบ) หรือไม่?
8. ภาพที่สร้างควรแสดงในหน้า Report ของเว็บแอปด้วย (ต้องทำ iframe/React) หรือมีเฉพาะในไฟล์ export ในรุ่นแรก?

**คำตอบของเจ้าของ (2026-10-01): ตามข้อแนะนำทุกข้อ**
1. สร้างเมื่อผู้ใช้กดขอ แล้ว cache เป็น `visuals.json` ไม่หักโควตา Run แต่มี daily cap แบบ `refine.py`
2. ค่าเริ่มต้นเป็น static SVG ส่วน ECharts เต็ม (tooltip/zoom) เป็นตัวเลือกตอนดาวน์โหลด
3. เป็น format ที่ 4 ไม่แทน HTML export เดิม ซึ่งยังเป็นไฟล์ไม่มี script
4. Engine ที่ evidence ว่างไม่ทำกราฟตัวเลขเลย เหลือ timeline, mind map และตารางเปรียบเทียบ
5. รุ่นแรก mind map เป็น `<details>` ซ้อนที่พิมพ์ได้
6. ฝังฟอนต์ในไฟล์ ซึ่ง HTML/PDF export ทำแล้ว (Geist, IBM Plex Sans Thai, Noto Serif Thai, Instrument Serif ราว 150 KB)
7. รุ่นแรกผู้ใช้ซ่อนหรือลบ block ได้ แต่ยังแก้ข้อมูลไม่ได้
8. แสดงในหน้า Report ของเว็บแอปตั้งแต่รุ่นแรก ผ่านปุ่ม "มุมมองภาพ" ที่เปิด `<iframe sandbox="allow-scripts">`

---

## 9. แหล่งอ้างอิง

เข้าถึงทั้งหมดวันที่ 2026-10-01 ยกเว้นที่ระบุไว้ **[snippet]** = หน้าทางการบล็อกการดึงโดยตรง เห็นผ่านผลค้นหา

1. Claude Help Center — What are artifacts and how do I use them? https://support.claude.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them
2. Claude Code Docs — Share session output as artifacts (Page constraints, Allowlist the viewer domain). https://code.claude.com/docs/en/artifacts
3. Claude Help Center — Custom visuals in chat and Cowork. https://support.claude.com/en/articles/13979539-custom-visuals-in-chat-and-cowork
4. Claude blog — Build and share AI-powered apps with Claude. https://claude.com/blog/claude-powered-artifacts (redirect จาก anthropic.com/news/claude-powered-artifacts)
5. Claude Help Center — Share artifacts. https://support.claude.com/en/articles/9547008-publish-and-share-artifacts
6. Google blog — New Gemini features: Canvas and Audio Overview (2025-03-18). https://blog.google/products/gemini/gemini-collaboration-features/
7. Google blog — Gemini App: 7 updates from Google I/O 2025 (2025-05-20). https://blog.google/products-and-platforms/products/gemini/gemini-app-updates-io-2025/
8. Gemini Apps release notes (entry 2025.05.20). https://gemini.google/release-notes/
9. Gemini Apps Help — Create docs, apps & more with Canvas. https://support.google.com/gemini/answer/16047321?hl=en&co=GENIE.Platform%3DDesktop
10. Google Workspace Updates — Quizzes through Canvas (2025-05). https://workspaceupdates.googleblog.com/2025/05/gemini-canvas-quizzes.html
11. Google blog — Integrated visual reports from Gemini Deep Research (2025-12-15). https://blog.google/products/gemini/visual-reports/
12. Gemini Apps Help — Use Deep Research in Gemini Apps. https://support.google.com/gemini/answer/15719111?hl=en&co=GENIE.Platform%3DDesktop
13. Gemini Notebook (NotebookLM) Help — Use Mind Maps. https://support.google.com/notebooklm/answer/16212283?hl=en
14. Google blog — What's new in NotebookLM: Video Overviews and an upgraded Studio (2025-07-29). https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-video-overviews-studio-upgrades/
15. OpenAI Help — Deep research in ChatGPT. https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt **[snippet]**
16. OpenAI Help — What is the canvas feature in ChatGPT. https://help.openai.com/en/articles/9930697-what-is-the-canvas-feature-in-chatgpt-and-how-do-i-use-it **[snippet]**
17. OpenAI Help — Data analysis with ChatGPT. https://help.openai.com/en/articles/8437071-data-analysis-with-chatgpt **[snippet]**
18. OpenAI — Introducing deep research. https://openai.com/index/introducing-deep-research/ **[snippet]**
19. Perplexity blog — Introducing Perplexity Labs (2025-05-30). https://www.perplexity.ai/hub/blog/introducing-perplexity-labs **[snippet]**
20. Perplexity Help Center — Perplexity Pages. https://www.perplexity.ai/help-center/en/articles/10352968-perplexity-pages **[snippet]**
21. Manus Documentation — Data Analysis & Visualization. https://manus.im/docs/features/data-visualization
22. Kimi Help Center — What Is Kimi Agent? https://www.kimi.com/en/help/agent/agent-overview
23. Genspark blog — Introduction to Sparkpage. https://www.genspark.ai/blog/sparkpage-intro **[snippet]**
24. Microsoft Learn — What is Researcher Agent in Microsoft Copilot? (updated 2026-08-18). https://learn.microsoft.com/en-us/microsoft-365/copilot/researcher-agent
25. stanford-oval/storm (README). https://github.com/stanford-oval/storm
26. assafelovic/gpt-researcher (README). https://github.com/assafelovic/gpt-researcher
27. langchain-ai/open_deep_research. https://github.com/langchain-ai/open_deep_research
28. dzhng/deep-research. https://github.com/dzhng/deep-research
29. u14app/deep-research (README). https://github.com/u14app/deep-research
    - 29a. `src/constants/prompts.ts` (knowledgeGraphPrompt, outputGuidelinesPrompt). https://github.com/u14app/deep-research/blob/main/src/constants/prompts.ts
    - 29b. `src/components/MagicDown/Mermaid.tsx` (`mermaid.parse(..., {suppressErrors: true})`). https://github.com/u14app/deep-research/blob/main/src/components/MagicDown/Mermaid.tsx
30. nickscamara/open-deep-research. https://github.com/nickscamara/open-deep-research
31. huggingface/smolagents — examples/open_deep_research. https://github.com/huggingface/smolagents/tree/main/examples/open_deep_research
32. vercel-labs/json-render. https://github.com/vercel-labs/json-render
33. google/A2UI. https://github.com/google/A2UI
34. wandb/openui. https://github.com/wandb/openui
35. e2b-dev/fragments. https://github.com/e2b-dev/fragments
36. microsoft/lida. https://github.com/microsoft/lida
37. Quarto — HTML Basics (embed-resources, TOC, tabsets, hover citations). https://quarto.org/docs/output-formats/html-basics.html
38. Observable Framework — Data loaders (ซอร์สเอกสารบน GitHub). https://github.com/observablehq/framework/blob/main/docs/data-loaders.md
39. evidence-dev/evidence (MIT) และ `core/src/user-components/common/echarts-options-attributes.ts`. https://github.com/evidence-dev/evidence · https://docs.evidence.dev/core-concepts/components/
40. MyST — Cross-references. https://mystmd.org/guide/cross-references
41. npm registry (เวอร์ชันและ license) https://registry.npmjs.org/ และไฟล์ที่วัดขนาดจาก jsDelivr https://cdn.jsdelivr.net/npm/ ได้แก่ echarts@6.1.0 (`dist/echarts.min.js`, `echarts.simple.min.js`, `i18n/langTH.js`), chart.js@4.5.1, vega@6.4.0, vega-lite@6.4.3, vega-embed@7.3.0, plotly.js-dist-min@4.1.1, @observablehq/plot@0.6.17, d3@7.9.0, mermaid@12.0.0, markmap-view/markmap-lib@0.18.12, cytoscape@3.34.3, vis-network@10.1.2, leaflet@1.9.4, katex@0.18.10
42. Apache ECharts Handbook — Server-side rendering. https://echarts.apache.org/handbook/en/how-to/cross-platform/server/
43. Apache ECharts Handbook — Canvas vs. SVG. https://echarts.apache.org/handbook/en/best-practices/canvas-vs-svg/
44. Apache ECharts Handbook — Accessibility (aria, decal). https://echarts.apache.org/handbook/en/best-practices/aria/
45. Vega — Usage (headless, `toSVG`, `vg2svg`, CSP). https://vega.github.io/vega/usage/
46. Vega-Lite — Mark (`aria`, `description`). https://vega.github.io/vega-lite/docs/mark.html
47. Mermaid — Usage (`securityLevel`, `mermaid.parse`). https://mermaid.js.org/config/usage.html
48. Mermaid — Accessibility (`accTitle`, `accDescr`). https://mermaid.js.org/config/accessibility.html
49. Mermaid — Flowchart (Markdown strings, auto wrap). https://mermaid.js.org/syntax/flowchart.html
50. mermaid-js/mermaid-cli. https://github.com/mermaid-js/mermaid-cli
51. Chart.js — Accessibility. https://www.chartjs.org/docs/latest/general/accessibility.html
52. Observable Plot — Accessibility (ซอร์สเอกสาร). https://github.com/observablehq/plot/blob/main/docs/features/accessibility.md
    - 52b. Observable Plot — Plots (`document` option สำหรับ SSR). https://github.com/observablehq/plot/blob/main/docs/features/plots.md
53. Plotly.js — Configuration options. https://plotly.com/javascript/configuration-options/
54. markmap (README). https://github.com/markmap/markmap
55. MDN — `<iframe>` (sandbox, srcdoc, csp). https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe
56. MDN — Content-Security-Policy header. https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy
57. MDN — CSP `sandbox` directive. https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/sandbox
58. W3C — Content Security Policy (ข้อความเรื่อง iframe srcdoc รับ policy ของหน้าแม่; ฉบับ draft เดิม ส่วน CSP Level 3 ปัจจุบันใช้กลไก policy container ของ HTML). https://w3c.github.io/webappsec/specs/content-security-policy/
59. MDN — Set-Cookie (SameSite=Lax). https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie
60. MDN — Intl.Segmenter. https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/Segmenter
61. MDN — Popover API. https://developer.mozilla.org/en-US/docs/Web/API/Popover_API
62. W3C WAI-ARIA APG — Sortable Table Example. https://www.w3.org/WAI/ARIA/apg/patterns/table/examples/sortable-table/
63. markdown-it — Safety. https://github.com/markdown-it/markdown-it/blob/master/docs/safety.md
64. Claude Platform Docs — Citations (`cited_text`, "guaranteed to contain valid pointers"). https://platform.claude.com/docs/en/build-with-claude/citations
65. Claude Platform Docs — Structured outputs. https://platform.claude.com/docs/en/build-with-claude/structured-outputs **[snippet: เห็นผ่านผลค้นหา ไม่ได้เปิดหน้าเต็ม]**
66. LiteLLM — Structured Outputs (JSON Mode). https://docs.litellm.ai/docs/completion/json_mode
67. @fontsource/noto-sans-thai@5.3.0 — file listing (thai-400/700-normal.woff2 ≈ 9.1 KB). https://data.jsdelivr.com/v1/packages/npm/@fontsource/noto-sans-thai@5.3.0?structure=flat

**ไฟล์ใน repo ที่ใช้เป็นบริบท**: `server/src/litstorm/report.py`, `server/src/litstorm/render/html.py`, `server/src/litstorm/render/pdf.py`, `server/src/litstorm/api/research.py` (export), `server/src/litstorm/api/auth.py` (cookie), `server/src/litstorm/refine.py`, `server/src/litstorm/engines/costorm/engine.py` (mind map), `web/src/pages/report.tsx`, `web/nginx.conf`, `docs/adr/0005-report-json-file.md`, `docs/adr/0006-fast-and-main-model.md`, `docs/benchmarks/2026-09-30-baseline.md`, `docs/web-app-design.md`
