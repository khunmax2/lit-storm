# คู่มือแก้ปัญหา STORM (Troubleshooting)

รวมปัญหาที่เจอจริงระหว่างตั้งค่าและใช้งาน fork นี้ พร้อมสาเหตุและวิธีแก้

ขั้นตอนติดตั้งและรันอยู่ที่ [frontend/demo_light/README.md](../frontend/demo_light/README.md)
เอกสารนี้เน้นเฉพาะ "เจออาการนี้ ทำยังไง"

## สภาพแวดล้อมที่ยืนยันว่าใช้ได้

| | เวอร์ชัน |
|---|---|
| Python | 3.14.3 (venv ไม่ใช่ conda) |
| streamlit | 1.60.0 |
| ddgs | 9.14.4 |
| dspy-ai | 2.4.9 |
| litellm | 1.80.0 |
| numpy | 2.5.1 |

README หลักของ upstream แนะนำ `conda` + Python 3.11 — ใช้ได้เหมือนกัน แต่
fork นี้พัฒนาและทดสอบบน venv + 3.14

---

# ปัญหาที่ยังเจอได้

## 1. `ModuleNotFoundError: No module named 'knowledge_storm'`

**สาเหตุ** ซอร์สโค้ดหลักยังไม่ถูกลงทะเบียนใน environment — ติดตั้งแค่
`requirements.txt` ไม่พอ

**วิธีแก้**

```bash
.venv/bin/pip install -e .
```

## 2. `streamlit: command not found` หรือรันแล้วได้เวอร์ชันผิด

**สาเหตุ** venv ยังไม่ได้ activate คำสั่ง `streamlit` เปล่า ๆ จะไปหาใน PATH
ของระบบซึ่งมักไม่มีอะไรเลย

**วิธีแก้** เรียกผ่าน path ของ venv

```bash
cd frontend/demo_light
../../.venv/bin/streamlit run storm.py
```

หรือ `source .venv/bin/activate` ก่อน

## 3. `StreamlitSecretNotFoundError` / `KeyError: 'GOOGLE_API_KEY'`

**สาเหตุ** มีสองแบบ

1. วางไฟล์ผิดที่ — ต้องอยู่ที่ `frontend/demo_light/.streamlit/secrets.toml`
2. **ลืมเครื่องหมายคำพูด** — `GOOGLE_API_KEY=xxx` ไม่ใช่ TOML ที่ถูกต้อง
   ตัว parser จะอ่านไม่ผ่านแล้วรายงานว่า "หา key ไม่เจอ" แทนที่จะบอกว่า
   ไวยากรณ์ผิด ทำให้หลงทางได้ง่าย

**วิธีแก้**

```toml
GOOGLE_API_KEY = "your-key-here"
```

## 4. แก้โค้ดแล้วไม่มีอะไรเปลี่ยน / error เดิมโผล่ซ้ำ ๆ

**อาการที่หลอกที่สุดในโปรเจกต์นี้** — แก้ `demo_util.py` ไปแล้วแต่ traceback
ยังชี้ไปที่โค้ดเวอร์ชันเก่า

**สาเหตุ** `STORMWikiRunner` ถูก cache ไว้ใน `st.session_state["runner"]`
Streamlit rerun สคริปต์ใหม่ทุกครั้งก็จริง แต่ไม่ได้สร้าง runner ใหม่
ตัวเก่าที่ถือ config เดิม (รวมถึง API key เดิม) จึงถูกใช้ต่อไปเรื่อย ๆ

**วิธีแก้** ต้อง**รีสตาร์ท streamlit** ไม่ใช่แค่รีเฟรชหน้าเว็บ

```bash
pkill -f "streamlit run"
```

เรื่องนี้ใช้กับการเปลี่ยน API key ด้วย

## 5. `NotFound: 404 models/gemini-... is not found`

**สาเหตุ** ชื่อโมเดลแบบปักหมุด (`gemini-1.5-flash`, `gemini-2.0-flash`,
`gemini-2.5-flash`) ถูก Google ปิดรับ key ที่สร้างใหม่ — ข้อความจริงคือ
*"no longer available to new users"*

จุดที่หลอกคือ `genai.list_models()` **ยังลิสต์ชื่อพวกนี้อยู่** ทั้งที่เรียกจริง
ไม่ได้ ห้ามใช้ผลจาก list_models เป็นข้อสรุป — ต้องลองเรียกจริง

**วิธีแก้** ใช้ alias `-latest` ซึ่งชี้ไปรุ่นล่าสุดที่ key นั้นเข้าถึงได้

```python
fast_lm   = LitellmModel(model="gemini/gemini-flash-lite-latest", ...)
strong_lm = LitellmModel(model="gemini/gemini-flash-latest", ...)
```

ทดสอบว่า key ใช้โมเดลไหนได้บ้าง

```bash
.venv/bin/python -c "
import tomllib
s=tomllib.load(open('frontend/demo_light/.streamlit/secrets.toml','rb'))
from knowledge_storm.lm import LitellmModel
for m in ['gemini/gemini-flash-latest','gemini/gemini-flash-lite-latest']:
    try: print('OK  ', m, LitellmModel(model=m, api_key=s['GOOGLE_API_KEY'], max_tokens=20)(prompt='hi'))
    except Exception as e: print('FAIL', m, str(e).splitlines()[0][:100])
"
```

## 6. `RateLimitError` จากทุกโมเดล

**อ่านข้อความในนั้นก่อนแก้โค้ด** เพราะมีสองสาเหตุที่ต่างกันคนละเรื่อง

**ก. โควตาฟรีเต็ม** — `quotaId: GenerateRequestsPerMinutePerProjectPerModel-FreeTier`,
`quotaValue: 15` แปลว่าชนเพดาน 15 คำขอ/นาที/โมเดล ซึ่ง STORM ทะลุได้ง่ายมาก
เพราะค้นหลายมุมมองพร้อมกัน

ลดการขนานลงใน `set_storm_runner()`

```python
max_conv_turn=2, max_perspective=2, max_thread_num=1
```

**ข. เครดิตหมด** — *"Your prepayment credits are depleted"* อันนี้ไม่ใช่บั๊ก
และแก้ด้วยโค้ดไม่ได้ ต้องไปเติมเงินที่ AI Studio

## 7. ค้นข้อมูลไม่เจอ / บทความว่างเปล่า ทั้งที่ไม่มี error

**สาเหตุ** แพ็กเกจ `duckduckgo_search` เปลี่ยนชื่อเป็น `ddgs` แล้ว ตัวเก่ายัง
import ได้ ยังคืน HTTP 200 แต่ **คืนผลลัพธ์ศูนย์รายการทุก backend** — STORM
เลยดูเหมือนทำงานปกติแต่ไม่ได้ค้นอะไรเลย

**วิธีแก้** fork นี้แก้ให้แล้ว (ดูข้อ B ด้านล่าง) ถ้าเจอในสภาพแวดล้อมอื่น

```bash
.venv/bin/pip install ddgs
```

ตรวจว่าค้นได้จริง

```bash
.venv/bin/python -c "
from knowledge_storm.rm import DuckDuckGoSearchRM
r = DuckDuckGoSearchRM(k=3).forward('quantum computing')
print('results:', len(r))
"
```

ได้ `0` = ยังพัง, ได้ `3` = ปกติ

---

# ปัญหาที่ fork นี้แก้ถาวรแล้ว

ไม่ต้องแก้ซ้ำ แต่บันทึกไว้เผื่อไป merge กับ upstream แล้วหายไป

**A. `RuntimeError: ScriptRunContext not initialized`**
STORM ยิง callback แจ้งความคืบหน้าจาก worker thread ซึ่งไม่มี script context
ของ Streamlit ตั้งแต่ Streamlit 1.5x เป็นต้นมา การเขียน UI จาก thread แบบนี้
เปลี่ยนจากแค่เตือนเป็น **raise** ทำให้รันไม่จบสักครั้ง
แก้โดยผูก context กลับเข้า thread ใน `demo_util.py`

**B. `duckduckgo_search` → `ddgs`**
รวมถึง `backend="api"` ที่เลิกใช้แล้ว และ giveup handler ของ `dsp` ที่อ่าน
`err.message` (แอตทริบิวต์ที่มีแต่ใน SDK ของ Mistral) ทำให้ตอนโดน rate limit
เด้ง `AttributeError` ออกมาแทนสาเหตุจริง

**C. ลิงก์สารบัญ (TOC) กดแล้วไม่ไปไหน**
หัวข้อที่ไม่มีอักษรละตินเลย (ไทย จีน อาหรับ) ได้ anchor ว่างเปล่าชนกันหมด
และ Streamlit รุ่นใหม่ตั้ง id หัวข้อเป็น hash ทำให้ slug ไม่มีวันตรง —
พังกับภาษาอังกฤษด้วย ไม่ใช่แค่ไทย

**D. `streamlit==1.31.1` ติดตั้งคู่กับ NumPy 2 ไม่ได้**
ปลดพินเป็น `streamlit>=1.46` ใน `requirements.txt` แล้ว

---

# ปัญหาที่หมดอายุแล้ว

**Pillow คอมไพล์ไม่ผ่าน (`RequiredDependencyException: jpeg`)**
เคยต้อง `brew install libjpeg` แล้วตั้ง `LDFLAGS`/`CPPFLAGS` เพราะตอนนั้น
Pillow ยังไม่มี wheel สำเร็จรูปสำหรับ Python 3.14 จึงต้องคอมไพล์จาก source
**ตอนนี้มี wheel แล้ว** (ตรวจสอบเมื่อ 2026-08-27 พบ `pillow-12.3.0-cp314`)
ติดตั้งได้ตรง ๆ ไม่ต้องพึ่ง Homebrew

**Protobuf `TypeError: Metaclasses with custom tp_new are not supported`**
เกิดจาก protobuf เวอร์ชันเก่าที่ `streamlit==1.31.1` ลากมา บน Python 3.14
หมดปัญหาไปพร้อมกับข้อ D
