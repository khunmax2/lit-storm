"""The language of the interface itself, separate from the article's language.

Every string the app draws goes through `t()`. The strings live here as one
dict keyed by a stable id, with the languages side by side, so a missing
translation is visible at a glance rather than hiding in another file.

The article's language is a different choice — see `article_language` — but
picking a UI language sets the default for it, because someone reading a Thai
interface almost always wants a Thai article too.
"""

from urllib.parse import unquote

import streamlit as st
import auth

# Display name -> itself. Language names are written in their own language,
# which is what a picker should show to someone who cannot read the current one.
LANGUAGES = ("English", "ไทย")

DEFAULT = "English"

# Not prefixed with "page", so it survives `clear_other_page_session_state`.
STATE_KEY = "ui_lang"

# Session state dies with the websocket, so on its own it makes the choice
# last exactly until the reader presses refresh — and a Thai page coming back
# in English is the one moment the picker is hardest to find. The crumb below
# outlives the session the same way the sign-in one does.
COOKIE_NAME = "storm_lang"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365
_PENDING_WRITE = "ui_lang_changed"

_STRINGS = {
    # -- chrome ---------------------------------------------------------
    "nav.label": {"English": "Navigation", "ไทย": "เมนู"},
    "nav.main_group": {"English": "Main menu", "ไทย": "เมนูหลัก"},
    "nav.manage_group": {"English": "Management", "ไทย": "การจัดการ"},
    "nav.articles": {"English": "My Articles", "ไทย": "บทความของฉัน"},
    "nav.create": {"English": "Create New Article", "ไทย": "สร้างบทความใหม่"},
    # A short label under the wordmark, as in the reference. The sentence it
    # replaced described the product; at rail width it wrapped to two lines
    # and read as a paragraph someone forgot to move.
    "brand.role": {
        "English": "Research Assistant",
        "ไทย": "ผู้ช่วยค้นคว้า",
    },
    "brand.tagline": {
        "English": "Researches a topic from many perspectives, then writes a cited article.",
        "ไทย": "ค้นคว้าหัวข้อจากหลายมุมมอง แล้วเรียบเรียงเป็นบทความพร้อมแหล่งอ้างอิง",
    },
    "lang.label": {"English": "Interface language", "ไทย": "ภาษาของระบบ"},
    "nav.sources": {"English": "Search sources", "ไทย": "แหล่งค้นคว้า"},
    "nav.roundtable": {"English": "Round table", "ไทย": "สนทนาเพื่อค้นคว้า"},
    "nav.models": {"English": "Models", "ไทย": "โมเดล"},
    # -- search sources ---------------------------------------------------
    "search.title": {"English": "Search sources", "ไทย": "แหล่งค้นคว้า"},
    "search.using": {"English": "researching with {name}", "ไทย": "แหล่งค้นคว้าที่ใช้: {name}"},
    "search.one_at_a_time": {
        "English": "STORM researches with one source at a time. Pick the one "
        "it should use; the rest keep their keys for later.",
        "ไทย": "STORM ใช้แหล่งค้นคว้าได้ครั้งละหนึ่งแหล่ง เลือกแหล่งที่ต้องการใช้ "
        "โดยระบบจะเก็บ API key ของแหล่งอื่นไว้สำหรับใช้งานครั้งต่อไป",
    },
    "search.free": {"English": "no key", "ไทย": "ไม่ต้องใช้ API key"},
    "search.paid": {"English": "needs a key", "ไทย": "ต้องใช้ API key"},
    "search.in_use": {"English": "in use", "ไทย": "กำลังใช้งาน"},
    "search.unavailable": {"English": "unavailable", "ไทย": "ไม่พร้อมใช้งาน"},
    "search.key_saved": {
        "English": "API key — saved, ending {last4}. Type a new one to replace it.",
        "ไทย": "บันทึก API key แล้ว (ลงท้ายด้วย {last4}) กรอกคีย์ใหม่หากต้องการเปลี่ยน",
    },
    "search.key_needed": {"English": "API key", "ไทย": "API key"},
    "search.no_key_needed": {
        "English": "Public search, no account needed.",
        "ไทย": "ค้นหาข้อมูลสาธารณะได้โดยไม่ต้องสมัครบัญชี",
    },
    "search.get_key": {"English": "Where to get one", "ไทย": "รับ API key"},
    "search.test": {"English": "Test", "ไทย": "ทดสอบ"},
    "search.testing": {"English": "Searching…", "ไทย": "กำลังค้นหา…"},
    "search.use": {"English": "Use this", "ไทย": "ใช้แหล่งนี้"},
    "search.forget_key": {"English": "Forget this key", "ไทย": "ลบ API key"},
    "search.test_ok": {
        "English": "Working — {n} results, from {hosts}.",
        "ไทย": "ใช้งานได้ พบผลลัพธ์ {n} รายการจาก {hosts}",
    },
    "search.test_failed": {
        "English": "The search did not go through.",
        "ไทย": "ค้นหาไม่สำเร็จ",
    },
    "search.no_results": {
        "English": "The search went through but came back empty.",
        "ไทย": "ค้นหาสำเร็จ แต่ไม่พบผลลัพธ์",
    },
    "arxiv_note": {
        "English": "Paper abstracts straight from arxiv.org — no key, no "
        "account. Strong on computing, physics and maths; thin on history, "
        "law and the humanities. One search every three seconds, as arXiv "
        "asks, so a run takes longer.",
        "ไทย": "ค้นหาบทคัดย่องานวิจัยจาก arxiv.org โดยตรง ไม่ต้องใช้ API key หรือสมัครบัญชี "
        "มีข้อมูลครอบคลุมด้านคอมพิวเตอร์ ฟิสิกส์ และคณิตศาสตร์ "
        "แต่มีข้อมูลด้านประวัติศาสตร์ กฎหมาย และมนุษยศาสตร์ค่อนข้างน้อย "
        "ระบบเว้นระยะการค้นหาอย่างน้อย 3 วินาทีต่อครั้งตามข้อกำหนดของ arXiv "
        "จึงอาจใช้เวลาค้นคว้านานขึ้น",
    },
    "searxng_note": {
        "English": "A metasearch engine you host yourself, querying Google, "
        "Bing, arXiv, PubMed and dozens more at once — no key, no rate limit "
        "but your own. The instance must allow JSON output: 'json' under "
        "search.formats in its settings.yml. Public instances almost never do.",
        "ไทย": "เครื่องมือค้นหารวมที่คุณโฮสต์เอง ค้นจาก Google, Bing, arXiv, PubMed "
        "และอีกหลายสิบแหล่งพร้อมกัน ไม่ต้องใช้ API key และไม่ถูกจำกัดอัตราจากใครนอกจากตัวเอง "
        "instance ต้องเปิดผลลัพธ์แบบ JSON ไว้ ('json' ใต้ search.formats ใน settings.yml) "
        "ซึ่ง instance สาธารณะแทบไม่มีที่เปิด",
    },
    "search.url_saved": {"English": "Instance address", "ไทย": "ที่อยู่ instance"},
    "search.url_needed": {"English": "Instance address", "ไทย": "ที่อยู่ instance"},
    "search.host_one": {"English": "How to host one", "ไทย": "วิธีติดตั้ง instance"},
    "search.forget_url": {"English": "Forget this address", "ไทย": "ลบที่อยู่นี้"},
    "search.needs_endpoint": {
        "English": "Marked internal-only in the library, and needs a private "
        "Stanford endpoint that is not published.",
        "ไทย": "แหล่งค้นคว้านี้รองรับการใช้งานภายในเท่านั้น และต้องเชื่อมต่อผ่าน endpoint "
        "ของ Stanford ที่ไม่ได้เปิดให้ใช้งานสาธารณะ",
    },
    "search.needs_collection": {
        "English": "Searches your own documents, which have to be embedded "
        "into a vector store first — a setup of its own, not a key.",
        "ไทย": "ค้นหาข้อมูลจากเอกสารของคุณเอง "
        "โดยต้องแปลงเอกสารเป็นเวกเตอร์และจัดเก็บในฐานข้อมูลเวกเตอร์ก่อน "
        "จึงต้องตั้งค่าเพิ่มเติมนอกเหนือจาก API key",
    },
    "search.failed_config": {
        "English": "The search source is not configured, so no run was started.",
        "ไทย": "ยังตั้งค่าแหล่งค้นคว้าไม่ครบ จึงยังไม่ได้เริ่มค้นคว้า",
    },
    # -- model settings ---------------------------------------------------
    "models.title": {"English": "Models", "ไทย": "โมเดล"},
    "models.using": {"English": "calling {name}", "ไทย": "ผู้ให้บริการที่ใช้: {name}"},
    "models.intro": {
        "English": "Saved here, these take effect on the next run — no file "
        "to edit and no restart. A deployment that sets them in the "
        "environment keeps working until something is saved over it.",
        "ไทย": "ค่าที่บันทึกที่นี่มีผลกับการค้นคว้าครั้งถัดไปทันที ไม่ต้องแก้ไฟล์หรือรีสตาร์ต "
        "หากการติดตั้งใดตั้งค่าไว้ในสภาพแวดล้อมอยู่แล้ว ระบบจะใช้ค่านั้นต่อไปจนกว่าจะมีการบันทึกทับ",
    },
    "models.default_provider": {"English": "Default provider", "ไทย": "ผู้ให้บริการหลัก"},
    "models.default_what": {
        "English": "Both roles use this unless one of them names another.",
        "ไทย": "ทั้งสองหน้าที่จะใช้ผู้ให้บริการนี้ เว้นแต่จะระบุผู้ให้บริการเฉพาะของตนเอง",
    },
    "models.role_fast": {"English": "Fast model", "ไทย": "โมเดลเร็ว"},
    "models.role_fast_what": {
        "English": "Asks the questions and plays the interviews.",
        "ไทย": "ใช้ตั้งคำถามและจำลองบทสนทนา",
    },
    "models.role_strong": {"English": "Strong model", "ไทย": "โมเดลหลัก"},
    "models.role_strong_what": {
        "English": "Writes the outline, the article and the polish.",
        "ไทย": "ใช้สร้างโครงร่าง เขียนบทความ และปรับภาษา",
    },
    "models.encoder": {"English": "Embeddings", "ไทย": "โมเดล embedding"},
    "models.encoder_what": {
        "English": "Co-STORM sorts every source it finds by similarity, so it "
        "needs these. STORM does not.",
        "ไทย": "Co-STORM จัดทุกแหล่งข้อมูลที่พบด้วยความคล้าย จึงต้องใช้ส่วนนี้ ส่วน STORM ไม่ต้องใช้",
    },
    "models.encoder_unavailable": {
        "English": "{name} sells chat completions but no embeddings, so "
        "Co-STORM cannot run on it. Pick a service for embeddings here.",
        "ไทย": "{name} ขายเฉพาะ chat completions ไม่มี embeddings ทำให้ Co-STORM ทำงานไม่ได้ "
        "ให้เลือกบริการสำหรับ embeddings ที่นี่",
    },
    "models.provider": {"English": "Provider", "ไทย": "ผู้ให้บริการ"},
    "models.inherit": {
        "English": "Same as the default",
        "ไทย": "ใช้ตามผู้ให้บริการหลัก",
    },
    "models.model_name": {"English": "Model name", "ไทย": "ชื่อโมเดล"},
    "models.model_default": {
        "English": "Leave empty to use {name}.",
        "ไทย": "เว้นว่างไว้เพื่อใช้ {name}",
    },
    "models.model_no_default": {
        "English": "This provider ships no default, so a name is required.",
        "ไทย": "ผู้ให้บริการนี้ไม่มีชื่อโมเดลเริ่มต้น จึงต้องระบุเอง",
    },
    "models.model_required": {"English": "required", "ไทย": "ต้องระบุ"},
    "models.api_base": {"English": "API base URL", "ไทย": "API base URL"},
    "models.key_saved": {
        "English": "{name} — saved, ending {last4}",
        "ไทย": "{name} — บันทึกแล้ว ลงท้าย {last4}",
    },
    "models.key_needed": {"English": "{name}", "ไทย": "{name}"},
    "models.from_server": {
        "English": "Set on the server, not here — it cannot be removed from "
        "this page, and saving a key here would take its place.",
        "ไทย": "ค่านี้ตั้งไว้ที่เซิร์ฟเวอร์ ไม่ได้ตั้งจากหน้านี้ จึงลบจากหน้านี้ไม่ได้ "
        "การบันทึกคีย์ที่นี่จะถูกใช้แทนค่าดังกล่าว",
    },
    "models.forget_key": {"English": "Forget this key", "ไทย": "ลบคีย์นี้"},
    "models.test": {"English": "Test", "ไทย": "ทดสอบ"},
    "models.testing": {"English": "Calling the model…", "ไทย": "กำลังเรียกโมเดล…"},
    "models.save": {"English": "Save", "ไทย": "บันทึก"},
    "models.test_ok": {
        "English": "{model} answered in {seconds}s: “{reply}”",
        "ไทย": "{model} ตอบกลับใน {seconds} วินาที: “{reply}”",
    },
    "models.encoder_ok": {
        "English": "Embeddings answered in {seconds}s, {dimensions} dimensions.",
        "ไทย": "embeddings ตอบกลับใน {seconds} วินาที ขนาด {dimensions} มิติ",
    },
    "models.test_failed": {
        "English": "The model could not be reached.",
        "ไทย": "เรียกโมเดลไม่สำเร็จ",
    },
    "models.empty_reply": {
        "English": "The model replied with nothing. It is reachable, but it is "
        "not answering — often a token budget spent on reasoning before any "
        "text is written.",
        "ไทย": "โมเดลตอบกลับมาเป็นค่าว่าง แปลว่าติดต่อได้แต่ไม่ตอบ "
        "สาเหตุที่พบบ่อยคือโควตา token ถูกใช้ไปกับการคิดจนหมดก่อนจะเขียนข้อความออกมา",
    },
    "models.slow": {
        "English": "That took {seconds}s for one word. A healthy model answers "
        "this in one to eight. A full run makes thousands of calls, so check "
        "the model name before using it.",
        "ไทย": "ใช้เวลา {seconds} วินาทีสำหรับคำเดียว ซึ่งโมเดลปกติจะตอบใน 1–8 วินาที "
        "การค้นคว้าหนึ่งครั้งเรียกโมเดลหลายพันครั้ง จึงควรตรวจสอบชื่อโมเดลก่อนใช้งาน",
    },
    "models.where_saved": {
        "English": "Keys are written to a file on this server, readable by its "
        "owner only, and never to the database — anything a member's session "
        "can read is something that member can take.",
        "ไทย": "คีย์ถูกบันทึกเป็นไฟล์บนเซิร์ฟเวอร์นี้ อ่านได้เฉพาะเจ้าของไฟล์ และไม่ถูกเก็บลงฐานข้อมูล "
        "เพราะสิ่งที่เซสชันของสมาชิกอ่านได้ ย่อมเป็นสิ่งที่สมาชิกคนนั้นนำออกไปได้",
    },
    # -- creating an article --------------------------------------------
    "create.eyebrow": {"English": "Powered by STORM", "ไทย": "ขับเคลื่อนด้วย STORM"},
    "create.title": {
        "English": "What do you want to learn in depth?",
        "ไทย": "ค้นคว้าหัวข้อที่คุณสนใจ",
    },
    "create.subtitle": {
        "English": "STORM researches your topic from several perspectives, "
        "gathers sources from the web, then writes a cited, "
        "Wikipedia-style article.",
        "ไทย": "STORM จะค้นคว้าหัวข้อของคุณจากหลายมุมมอง รวบรวมข้อมูลจากเว็บไซต์ "
        "แล้วเรียบเรียงเป็นบทความในรูปแบบวิกิพีเดียพร้อมแหล่งอ้างอิง",
    },
    "create.topic": {"English": "Topic", "ไทย": "หัวข้อ"},
    "create.topic_placeholder": {
        "English": "e.g. The history of Thai silk",
        "ไทย": "เช่น ประวัติศาสตร์ผ้าไหมไทย",
    },
    "create.article_language": {"English": "Article language", "ไทย": "ภาษาของบทความ"},
    "create.submit": {"English": "Start research", "ไทย": "เริ่มค้นคว้า"},
    "create.caption": {
        "English": "A full run takes roughly 2–5 minutes. Sources are searched in "
        "whichever language fits the topic; only the article is written "
        "in the language you pick.",
        "ไทย": "ทั้งกระบวนการใช้เวลาประมาณ 2–5 นาที "
        "ระบบจะค้นหาแหล่งข้อมูลด้วยภาษาที่เหมาะกับหัวข้อ "
        "ส่วนบทความจะเขียนด้วยภาษาที่คุณเลือก",
    },
    "create.needs_topic": {
        "English": "Please enter a topic first.",
        "ไทย": "กรุณาระบุหัวข้อที่ต้องการค้นคว้า",
    },
    "create.try_example": {"English": "Try an example", "ไทย": "ลองหัวข้อตัวอย่าง"},
    "create.in_progress": {"English": "research in progress", "ไทย": "กำลังค้นคว้า"},
    "create.step1": {
        "English": "Step 1 of 2 · brain**STORM**ing — researching the topic "
        "(about 2 minutes).",
        "ไทย": "ขั้นที่ 1 จาก 2 · กำลังค้นคว้าหัวข้อ (ประมาณ 2 นาที)",
    },
    "create.step1_done": {
        "English": "Step 1 of 2 · research complete",
        "ไทย": "ขั้นที่ 1 จาก 2 · ค้นคว้าเสร็จสิ้น",
    },
    "create.step2": {
        "English": "Step 2 of 2 · writing and polishing the article (about 2 minutes).",
        "ไทย": "ขั้นที่ 2 จาก 2 · กำลังเขียนและขัดเกลาบทความ (ประมาณ 2 นาที)",
    },
    "create.step2_writing": {
        "English": "Connecting the sources I found into a cited article…",
        "ไทย": "กำลังเรียบเรียงข้อมูลที่ค้นพบเป็นบทความพร้อมแหล่งอ้างอิง…",
    },
    "create.step2_done": {
        "English": "Step 2 of 2 · article ready",
        "ไทย": "ขั้นที่ 2 จาก 2 · สร้างบทความเสร็จสิ้น",
    },
    "create.failed_label": {
        "English": "Run stopped",
        "ไทย": "การค้นคว้าไม่สำเร็จ",
    },
    "create.failed_quota": {
        "English": "The model provider turned the request away — usually a rate "
        "limit or an empty balance. Check the API key's quota, then try again.",
        "ไทย": "ผู้ให้บริการโมเดลปฏิเสธคำขอ "
        "ซึ่งอาจเกิดจากการใช้เกินขีดจำกัดหรือเครดิตไม่เพียงพอ "
        "กรุณาตรวจสอบโควตาและเครดิตของ API key แล้วลองอีกครั้ง",
    },
    "create.failed_generic": {
        "English": "Something went wrong partway through. Nothing was saved.",
        "ไทย": "เกิดข้อผิดพลาดระหว่างการค้นคว้า ระบบยังไม่ได้บันทึกผลลัพธ์",
    },
    "create.failed_model": {
        "English": "The language model is not configured, so no run was started.",
        "ไทย": "ยังตั้งค่าโมเดลภาษาไม่ครบ จึงยังไม่ได้เริ่มค้นคว้า",
    },
    "create.failed_detail": {"English": "Technical detail", "ไทย": "รายละเอียดทางเทคนิค"},
    "create.retry": {"English": "Start over", "ไทย": "เริ่มใหม่"},
    "create.read_article": {"English": "Read the article", "ไทย": "อ่านบทความ"},
    # -- accounts ---------------------------------------------------------
    "auth.title": {"English": "Sign in to STORM", "ไทย": "เข้าสู่ระบบ STORM"},
    "auth.subtitle": {
        "English": "Your research and the articles you generate stay with your "
        "account.",
        "ไทย": "ระบบจะเก็บงานค้นคว้าและบทความที่คุณสร้างไว้ในบัญชีของคุณ",
    },
    "auth.tab_signin": {"English": "Sign in", "ไทย": "เข้าสู่ระบบ"},
    "auth.tab_signup": {"English": "Create account", "ไทย": "สมัครสมาชิก"},
    "auth.email": {"English": "Email", "ไทย": "อีเมล"},
    "auth.password": {"English": "Password", "ไทย": "รหัสผ่าน"},
    "auth.name": {"English": "Display name", "ไทย": "ชื่อที่แสดง"},
    "auth.do_signin": {"English": "Sign in", "ไทย": "เข้าสู่ระบบ"},
    "auth.do_signup": {"English": "Create account", "ไทย": "สมัครสมาชิก"},
    "auth.signout": {"English": "Sign out", "ไทย": "ออกจากระบบ"},
    "auth.needs_fields": {
        "English": "Enter an email and a password.",
        "ไทย": "กรุณากรอกอีเมลและรหัสผ่าน",
    },
    "auth.password_short": {
        "English": "Use at least 8 characters.",
        "ไทย": "รหัสผ่านต้องยาวอย่างน้อย 8 ตัวอักษร",
    },
    "auth.check_email": {
        "English": "Account created. Check your email for the confirmation "
        "link, then sign in.",
        "ไทย": "สร้างบัญชีเรียบร้อยแล้ว กรุณาคลิกลิงก์ยืนยันในอีเมลก่อนเข้าสู่ระบบ",
    },
    "auth.failed": {
        "English": "That did not work. Check the address and password.",
        "ไทย": "เข้าสู่ระบบไม่สำเร็จ ตรวจสอบอีเมลและรหัสผ่านอีกครั้ง",
    },
    "auth.not_configured": {
        "English": "Sign-in is not set up: add SUPABASE_URL and "
        "SUPABASE_ANON_KEY to .streamlit/secrets.toml.",
        "ไทย": "ยังไม่ได้ตั้งค่าระบบสมาชิก — เพิ่ม SUPABASE_URL และ "
        "SUPABASE_ANON_KEY ใน .streamlit/secrets.toml",
    },
    "auth.role_member": {"English": "Member", "ไทย": "สมาชิก"},
    "auth.role_admin": {"English": "Admin", "ไทย": "ผู้ดูแลระบบ"},
    "auth.quota": {
        "English": "{used} of {limit} runs this month",
        "ไทย": "ค้นคว้าไปแล้ว {used} จาก {limit} ครั้งในเดือนนี้",
    },
    "auth.quota_spent": {
        "English": "You have used this month's {limit} research runs. An admin "
        "can raise your limit.",
        "ไทย": "คุณใช้โควตาค้นคว้าครบ {limit} ครั้งในเดือนนี้แล้ว หากต้องการเพิ่มโควตา "
        "กรุณาติดต่อผู้ดูแลระบบ",
    },
    "auth.no_profile": {
        "English": "Your account has no profile row yet. Run the schema in "
        "docs/supabase-schema.sql.",
        "ไทย": "บัญชีนี้ยังไม่มีข้อมูลโปรไฟล์ กรุณาให้ผู้ดูแลระบบเรียกใช้คำสั่ง SQL ใน "
        "docs/supabase-schema.sql",
    },
    # -- admin ------------------------------------------------------------
    "nav.admin": {"English": "Members", "ไทย": "สมาชิก"},
    "admin.title": {"English": "Members", "ไทย": "จัดการสมาชิก"},
    "admin.count": {"English": "{n} accounts", "ไทย": "{n} บัญชี"},
    "admin.col_name": {"English": "Name", "ไทย": "ชื่อ"},
    "admin.col_email": {"English": "Email", "ไทย": "อีเมล"},
    "admin.col_role": {"English": "Role", "ไทย": "บทบาท"},
    "admin.col_limit": {"English": "Runs / month", "ไทย": "โควตาค้นคว้าต่อเดือน"},
    "admin.col_used": {"English": "Used", "ไทย": "จำนวนครั้งที่ใช้"},
    "admin.col_active": {"English": "Account status", "ไทย": "สถานะบัญชี"},
    "admin.col_joined": {"English": "Joined", "ไทย": "สมัครเมื่อ"},
    "admin.help_limit": {
        "English": "Research runs allowed each calendar month. 0 stops new runs "
        "without closing the account.",
        "ไทย": "จำนวนครั้งที่อนุญาตให้ค้นคว้าในแต่ละเดือนปฏิทิน กำหนดเป็น 0 "
        "เพื่อระงับการค้นคว้าครั้งใหม่โดยไม่ต้องปิดบัญชี",
    },
    "admin.save": {"English": "Save changes", "ไทย": "บันทึกการแก้ไข"},
    "admin.saved": {"English": "Saved {n} change(s).", "ไทย": "บันทึกแล้ว {n} รายการ"},
    "admin.no_changes": {"English": "Nothing to save.", "ไทย": "ไม่มีการแก้ไข"},
    "admin.last_admin": {
        "English": "There is currently one admin account. You can still manage members. "
        "Keep at least one admin account active so someone can manage members.",
        "ไทย": "ขณะนี้มีบัญชีผู้ดูแลระบบ 1 บัญชี คุณยังจัดการสมาชิกได้ตามปกติ "
        "โปรดคงบัญชีผู้ดูแลระบบที่ใช้งานได้ไว้อย่างน้อย 1 บัญชี "
        "เพื่อให้มีผู้จัดการสมาชิกได้ต่อไป",
    },
    "admin.runs_label": {"English": "Recent runs", "ไทย": "การค้นคว้าล่าสุด"},
    "admin.runs_empty": {"English": "No runs yet.", "ไทย": "ยังไม่มีการค้นคว้า"},
    "admin.col_topic": {"English": "Topic", "ไทย": "หัวข้อ"},
    "admin.col_status": {"English": "Status", "ไทย": "สถานะ"},
    "admin.col_when": {"English": "Started", "ไทย": "เริ่มเมื่อ"},
    "admin.col_who": {"English": "By", "ไทย": "โดย"},
    "admin.denied": {
        "English": "Members only. Ask an admin if you need access.",
        "ไทย": "หน้านี้สำหรับผู้ดูแลระบบเท่านั้น หากต้องการสิทธิ์เข้าถึง กรุณาติดต่อผู้ดูแลระบบ",
    },
    'auth.suspended': {'English': 'Your account is suspended. Contact an admin to restore access.',
 'ไทย': 'บัญชีนี้ถูกระงับการใช้งาน กรุณาติดต่อผู้ดูแลระบบเพื่อเปิดใช้งานอีกครั้ง'},
    'admin.you': {'English': 'Your signed-in account', 'ไทย': 'บัญชีที่คุณกำลังใช้งาน'},
    'admin.active': {'English': 'Active', 'ไทย': 'ใช้งานได้'},
    'admin.suspended': {'English': 'Suspended', 'ไทย': 'ระงับการใช้งาน'},
    'admin.self_protected': {'English': 'You cannot change your own role, suspend or delete your own account.',
 'ไทย': 'คุณไม่สามารถลดสิทธิ์ ระงับการใช้งาน หรือลบบัญชีที่กำลังใช้งานอยู่ได้'},
    'admin.usage': {'English': 'This month: {used} / {limit} research runs', 'ไทย': 'การค้นคว้าเดือนนี้: {used} / {limit} ครั้ง'},
    'admin.member_meta': {'English': 'Account date: {date} · Origin: {source}', 'ไทย': 'วันที่สร้างบัญชี: {date} · ที่มา: {source}'},
    'admin.created_by': {'English': 'By: {name}', 'ไทย': 'ดำเนินการโดย: {name}'},
    'admin.source_legacy_unknown': {'English': 'Origin not recorded', 'ไทย': 'ไม่มีข้อมูลที่มา'},
    'admin.source_first_sign_in': {'English': 'Profile created at first sign-in; registration origin unknown',
 'ไทย': 'สร้างโปรไฟล์เมื่อเข้าสู่ระบบครั้งแรก ไม่ทราบช่องทางสมัครบัญชี'},
    'admin.source_self_signup': {'English': 'Self-registration', 'ไทย': 'สมัครด้วยตนเอง'},
    'admin.source_admin_create': {'English': 'Created by an admin', 'ไทย': 'ผู้ดูแลระบบสร้างให้'},
    'admin.pending': {'English': '{n} account(s) have unsaved changes', 'ไทย': 'มีการแก้ไข {n} บัญชีที่ยังไม่ได้บันทึก'},
    'admin.reset': {'English': 'Discard changes', 'ไทย': 'ยกเลิกการแก้ไข'},
    'admin.save_failed': {'English': 'Changes were not saved. Another admin may have updated these accounts. Discard changes to load '
            'current values, then try again. If this persists, check the database setup.',
 'ไทย': 'บันทึกไม่สำเร็จ อาจมีผู้ดูแลคนอื่นแก้ไขข้อมูลแล้ว กดยกเลิกการแก้ไขเพื่อโหลดค่าล่าสุด แล้วลองใหม่ '
        'หากยังบันทึกไม่ได้ ให้ตรวจสอบการตั้งค่าฐานข้อมูล'},
    'admin.add_member': {'English': 'Add member', 'ไทย': 'เพิ่มสมาชิก'},
    'admin.create_help': {'English': 'Enter the same details as registration. New accounts start as members and can sign in '
            'immediately with this password. No welcome or confirmation email is sent.',
 'ไทย': 'กรอกข้อมูลเช่นเดียวกับการสมัครสมาชิก บัญชีใหม่จะมีสิทธิ์สมาชิกและใช้รหัสผ่านนี้เข้าสู่ระบบได้ทันที '
        'ระบบไม่ส่งอีเมลต้อนรับหรืออีเมลยืนยัน'},
    'admin.create_setup': {'English': 'Account creation requires the Supabase server key and the updated database schema. This form is '
            'unavailable in the local demo.',
 'ไทย': 'การเพิ่มสมาชิกต้องตั้งค่าคีย์ Supabase ฝั่งเซิร์ฟเวอร์และอัปเดตฐานข้อมูลก่อน '
        'ฟอร์มนี้ไม่เปิดใช้งานในโหมดสาธิต'},
    'admin.email_verified': {'English': 'I have verified that this email belongs to the member.',
 'ไทย': 'ฉันตรวจสอบแล้วว่าอีเมลนี้เป็นของสมาชิกที่จะเพิ่ม'},
    'admin.verify_email_first': {'English': 'Verify the member’s email and select the confirmation before creating the account.',
 'ไทย': 'โปรดตรวจสอบอีเมลของสมาชิกและเลือกช่องยืนยันก่อนสร้างบัญชี'},
    'admin.create_not_ready': {'English': 'Account creation is unavailable. Check the database migration and your current admin '
            'permissions.',
 'ไทย': 'ยังไม่สามารถเพิ่มสมาชิกได้ กรุณาตรวจสอบการอัปเดตฐานข้อมูลและสิทธิ์ผู้ดูแลระบบของบัญชีนี้'},
    'admin.created': {'English': 'Member created. Your admin session is unchanged.',
 'ไทย': 'เพิ่มสมาชิกแล้ว คุณยังเข้าสู่ระบบด้วยบัญชีผู้ดูแลเดิม'},
    'admin.error_invalid_email': {'English': 'Enter a valid email address.', 'ไทย': 'กรุณากรอกอีเมลให้ถูกต้อง'},
    'admin.error_password_short': {'English': 'Use a password with at least 8 characters.', 'ไทย': 'กรุณาใช้รหัสผ่านอย่างน้อย 8 ตัวอักษร'},
    'admin.error_name_long': {'English': 'Names must be at most 200 characters.', 'ไทย': 'ชื่อยาวได้ไม่เกิน 200 ตัวอักษร'},
    'admin.error_self_protected': {'English': 'You cannot demote or suspend your own account.',
 'ไทย': 'คุณไม่สามารถลดสิทธิ์หรือระงับบัญชีที่กำลังใช้งานอยู่ได้'},
    'admin.error_denied': {'English': 'An active admin account is required.', 'ไทย': 'ต้องใช้บัญชีผู้ดูแลระบบที่ยังใช้งานได้'},
    'admin.error_dev_readonly': {'English': 'Demo accounts cannot be changed. No real account was created or updated.',
 'ไทย': 'บัญชีสาธิตแก้ไขไม่ได้ ระบบไม่ได้สร้างหรือแก้ไขบัญชีจริง'},
    'admin.error_setup_required': {'English': 'Configure the server key before adding members.',
 'ไทย': 'กรุณาตั้งค่าคีย์ฝั่งเซิร์ฟเวอร์ก่อนเพิ่มสมาชิก'},
    'admin.error_create_failed': {'English': 'Account creation failed. Check whether this email is already registered or the password meets '
            'the project requirements.',
 'ไทย': 'เพิ่มสมาชิกไม่สำเร็จ โปรดตรวจสอบว่าอีเมลนี้มีบัญชีอยู่แล้วหรือไม่ '
        'และรหัสผ่านตรงตามข้อกำหนดของระบบหรือไม่'},
    'admin.error_rollback_failed': {'English': 'Account creation did not complete and automatic cleanup failed. Check this email in Supabase '
            'Auth and reconcile the account before retrying.',
 'ไทย': 'สร้างบัญชีไม่ครบและย้อนกลับอัตโนมัติไม่สำเร็จ กรุณาตรวจสอบอีเมลนี้ใน Supabase Auth '
        'และแก้ไขบัญชีที่ค้างก่อนลองใหม่'},
    'admin.error_audit_failed': {'English': 'Account creation failed and its failure log could not be saved. Check the database connection '
            'before retrying.',
 'ไทย': 'เพิ่มสมาชิกไม่สำเร็จ และบันทึกประวัติข้อผิดพลาดไม่ได้ กรุณาตรวจสอบการเชื่อมต่อฐานข้อมูลก่อนลองใหม่'},
    'admin.error_invalid_fields': {'English': 'Unsupported member field.', 'ไทย': 'มีช่องข้อมูลที่ระบบไม่รองรับ'},
    'admin.error_invalid_role': {'English': 'Choose an available role.', 'ไทย': 'กรุณาเลือกบทบาทที่ระบบมีให้'},
    'admin.error_invalid_status': {'English': 'Choose an available account status.', 'ไทย': 'กรุณาเลือกสถานะบัญชีที่ระบบมีให้'},
    'admin.error_invalid_limit': {'English': 'Enter a valid nonnegative monthly limit.',
 'ไทย': 'กรุณาระบุโควตารายเดือนเป็นจำนวนเต็มตั้งแต่ 0 ขึ้นไป'},
    'admin.error_missing_member': {'English': 'This member no longer exists. Reload the page.', 'ไทย': 'ไม่พบบัญชีนี้แล้ว กรุณาโหลดหน้าใหม่'},
    'admin.total': {'English': 'All accounts', 'ไทย': 'บัญชีทั้งหมด'},
    'admin.active_admins': {'English': 'Active admins', 'ไทย': 'ผู้ดูแลระบบที่ใช้งานได้'},
    'admin.manage': {'English': 'Manage accounts', 'ไทย': 'จัดการบัญชี'},
    'admin.audit': {'English': 'Member history', 'ไทย': 'ประวัติการจัดการสมาชิก'},
    'admin.edit_help': {'English': 'Choose a role, status or monthly quota, then save. Your own role and status are protected.',
 'ไทย': 'เลือกบทบาท สถานะ หรือโควตารายเดือน แล้วบันทึก บทบาทและสถานะของบัญชีที่คุณกำลังใช้งานจะถูกล็อกไว้'},
    'admin.audit_setup': {'English': 'Member history is unavailable. Apply the updated database schema to start recording it.',
 'ไทย': 'ยังแสดงประวัติการจัดการสมาชิกไม่ได้ กรุณาอัปเดตฐานข้อมูลเพื่อเริ่มเก็บประวัติ'},
    'admin.audit_empty': {'English': 'No member history recorded yet.', 'ไทย': 'ยังไม่มีประวัติการจัดการสมาชิก'},
    'admin.audit_help': {'English': 'Latest 50 events. Account origins and successful edits are recorded without passwords.',
 'ไทย': 'ประวัติล่าสุด 50 รายการ แสดงที่มาของบัญชีและการแก้ไขที่บันทึกแล้ว โดยไม่เก็บรหัสผ่าน'},
    'admin.event_account_created': {'English': 'Account created', 'ไทย': 'สร้างบัญชี'},
    'admin.event_profile_created': {'English': 'First sign-in profile created', 'ไทย': 'สร้างโปรไฟล์เมื่อเข้าสู่ระบบครั้งแรก'},
    'admin.event_profile_updated': {'English': 'Account updated', 'ไทย': 'แก้ไขบัญชี'},
    'admin.event_account_creation_failed': {'English': 'Account creation failed', 'ไทย': 'สร้างบัญชีไม่สำเร็จ'},
    'admin.event_target': {'English': 'Account: {name}', 'ไทย': 'บัญชี: {name}'},
    'admin.event_outcome': {'English': 'Result: {outcome}', 'ไทย': 'ผลการดำเนินการ: {outcome}'},
    'admin.outcome_success': {'English': 'Success', 'ไทย': 'สำเร็จ'},
    'admin.outcome_failed': {'English': 'Failed', 'ไทย': 'ไม่สำเร็จ'},
    'admin.system': {'English': 'System / self-registration', 'ไทย': 'ระบบ / การสมัครด้วยตนเอง'},
    'admin.before': {'English': 'Before', 'ไทย': 'ก่อนแก้ไข'},
    'admin.after': {'English': 'After', 'ไทย': 'หลังแก้ไข'},
    'admin.details': {'English': 'Details', 'ไทย': 'รายละเอียด'},
    'admin.run_running': {'English': 'In progress', 'ไทย': 'กำลังค้นคว้า'},
    'admin.run_done': {'English': 'Completed', 'ไทย': 'สำเร็จ'},
    'admin.run_failed': {'English': 'Failed', 'ไทย': 'ไม่สำเร็จ'},
    'admin.account_date': {'English': 'Account created', 'ไทย': 'สร้างบัญชีเมื่อ'},
    'admin.profile_date': {'English': 'Profile added', 'ไทย': 'เพิ่มโปรไฟล์เมื่อ'},
    'admin.field': {'English': 'Field', 'ไทย': 'ข้อมูล'},
    'admin.reason_auth_rejected': {'English': 'The authentication provider rejected account creation.',
 'ไทย': 'ระบบยืนยันตัวตนไม่อนุญาตให้สร้างบัญชี'},
    'admin.reason_profile_registration_failed': {'English': 'The profile and audit registration did not complete.',
 'ไทย': 'บันทึกโปรไฟล์และประวัติการสร้างบัญชีไม่สำเร็จ'},
    'admin.reason_rollback_failed': {'English': 'Automatic cleanup failed; the account needs manual reconciliation.',
 'ไทย': 'ย้อนกลับอัตโนมัติไม่สำเร็จ ต้องตรวจสอบและแก้ไขบัญชีที่ค้าง'},
    'admin.subtitle': {'English': 'Manage member access, account status and research quotas',
 'ไทย': 'ดูแลสิทธิ์ สถานะ และโควตาของสมาชิก'},
    'admin.total_caption': {'English': 'Accounts in the system', 'ไทย': 'บัญชีทั้งหมดในระบบ'},
    'admin.active_caption': {'English': '{pct}% of all accounts', 'ไทย': 'คิดเป็น {pct}% ของทั้งหมด'},
    'admin.suspended_caption': {'English': '{pct}% of all accounts', 'ไทย': 'คิดเป็น {pct}% ของทั้งหมด'},
    'admin.stat_total': {'English': 'All members', 'ไทย': 'สมาชิกทั้งหมด'},
    'admin.stat_active': {'English': 'Active', 'ไทย': 'ใช้งานอยู่'},
    'admin.stat_suspended': {'English': 'Suspended', 'ไทย': 'ระงับการใช้งาน'},
    'admin.member_tab': {'English': 'Members', 'ไทย': 'สมาชิก'},
    'admin.member': {'English': 'Member', 'ไทย': 'สมาชิก'},
    'admin.used_this_month': {'English': 'Used this month', 'ไทย': 'การใช้งานเดือนนี้'},
    'admin.monthly_limit': {'English': 'Monthly quota', 'ไทย': 'โควตา/เดือน'},
    'admin.actions': {'English': 'Actions', 'ไทย': 'จัดการ'},
    'admin.search': {'English': 'Search members', 'ไทย': 'ค้นหาสมาชิก'},
    'admin.search_placeholder': {'English': 'Search by name or email', 'ไทย': 'ค้นหาชื่อหรืออีเมล'},
    'admin.role_filter': {'English': 'Filter by role', 'ไทย': 'กรองตามบทบาท'},
    'admin.status_filter': {'English': 'Filter by status', 'ไทย': 'กรองตามสถานะ'},
    'admin.all_roles': {'English': 'All roles', 'ไทย': 'ทุกบทบาท'},
    'admin.all_statuses': {'English': 'All statuses', 'ไทย': 'ทุกสถานะ'},
    'admin.no_results': {'English': 'No members match these filters.', 'ไทย': 'ไม่พบสมาชิกที่ตรงกับเงื่อนไขการค้นหา'},
    'admin.times': {'English': 'runs', 'ไทย': 'ครั้ง'},
    'admin.over_quota': {'English': '{n} run(s) over quota', 'ไทย': 'เกินโควตา {n} ครั้ง'},
    'admin.edit_member': {'English': 'Edit member', 'ไทย': 'แก้ไขสมาชิก'},
    'admin.edit_then_save': {'English': 'Save pending changes below the list.', 'ไทย': 'บันทึกการแก้ไขที่ด้านล่างรายการ'},
    'admin.showing': {'English': 'Showing {start}–{end} of {total} members', 'ไทย': 'แสดง {start}–{end} จาก {total} รายการ'},
    # -- landing / home --------------------------------------------------
    "nav.home": {"English": "Home", "ไทย": "หน้าแรก"},
    "home.hero_note": {
        "English": "Every claim carries a citation you can open and check.",
        "ไทย": "ตรวจสอบแหล่งที่มาของข้อมูลได้จากรายการอ้างอิงในบทความ",
    },
    "home.engine_label": {
        "English": "How should the research happen?",
        "ไทย": "รูปแบบการค้นคว้า",
    },
    # The engines' own names, in both languages: a proper noun does not
    # translate, and the line under the switch is where the difference between
    # them is actually explained.
    "home.engine_storm": {"English": "STORM", "ไทย": "STORM"},
    "home.engine_costorm": {"English": "Co-STORM", "ไทย": "Co-STORM"},
    "home.engine_storm_note": {
        "English": "STORM researches on its own and hands back a cited "
        "article. About 2–5 minutes, nothing to do but wait.",
        "ไทย": "STORM ค้นคว้าและสร้างบทความพร้อมแหล่งอ้างอิงโดยอัตโนมัติ ใช้เวลาประมาณ 2–5 นาที",
    },
    "home.engine_costorm_note": {
        "English": "Co-STORM lets a panel argue it out while you watch, "
        "interrupt, and steer. Slower, and the direction is yours.",
        "ไทย": "Co-STORM ค้นคว้าผ่านการสนทนาระหว่างผู้เชี่ยวชาญ AI "
        "คุณสามารถถามคำถามและกำหนดทิศทางการสนทนาได้ ใช้เวลามากกว่า STORM",
    },
    "home.how_label": {"English": "How it works", "ไทย": "ขั้นตอนการทำงาน"},
    "home.step1_title": {
        "English": "It finds the angles you would not have asked about",
        "ไทย": "สำรวจหัวข้อจากหลายมุมมอง",
    },
    "home.step1_body": {
        "English": "STORM reads around the topic first, then assembles a panel of "
        "editors — a historian, an economist, a practitioner — who each "
        "interview the subject from their own angle.",
        "ไทย": "STORM ศึกษาข้อมูลเบื้องต้น แล้วกำหนดบทบาทให้ AI "
        "ค้นคว้าผ่านการถามตอบจากหลายมุมมอง เช่น ประวัติศาสตร์ เศรษฐศาสตร์ "
        "และการใช้งานจริง",
    },
    "home.step2_title": {
        "English": "Every question becomes a real search",
        "ไทย": "ค้นหาข้อมูลเพื่อตอบคำถาม",
    },
    "home.step2_body": {
        "English": "Each question is turned into search queries, the pages are read, "
        "and the source behind every answer is kept.",
        "ไทย": "ระบบนำคำถามมาสร้างคำค้น อ่านข้อมูลจากเว็บไซต์ "
        "และเก็บแหล่งที่มาของข้อมูลที่ใช้ตอบคำถาม",
    },
    "home.step3_title": {
        "English": "You get an article, not a summary",
        "ไทย": "เรียบเรียงเป็นบทความพร้อมแหล่งอ้างอิง",
    },
    "home.step3_body": {
        "English": "The findings are organised into an outline and written up section "
        "by section, with inline citations and a reference list.",
        "ไทย": "ระบบจัดข้อมูลเป็นโครงร่าง แล้วเขียนบทความทีละหัวข้อ "
        "พร้อมรายการอ้างอิงในเนื้อหาและแหล่งข้อมูลท้ายบทความ",
    },
    "home.recent_label": {"English": "Made with STORM", "ไทย": "ตัวอย่างผลงาน"},
    "home.recent_all": {"English": "See all articles", "ไทย": "ดูบทความทั้งหมด"},
    # -- the library -----------------------------------------------------
    # `{s}` is the English plural suffix; Thai simply ignores it.
    "articles.count": {"English": "{n} article{s}", "ไทย": "{n} บทความ"},
    "articles.sources": {"English": "{n} sources", "ไทย": "{n} แหล่งอ้างอิง"},
    "articles.search": {"English": "Search articles", "ไทย": "ค้นหาบทความ"},
    "articles.search_placeholder": {
        "English": "Filter by topic…",
        "ไทย": "ค้นหาตามหัวข้อ…",
    },
    "articles.empty_title": {"English": "No articles yet", "ไทย": "ยังไม่มีบทความ"},
    "articles.empty_body": {
        "English": "Head to “{create}”, give STORM a topic, "
        "and it will research and write one for you.",
        "ไทย": "ไปที่ “{create}” แล้วระบุหัวข้อที่สนใจ STORM จะค้นคว้าและสร้างบทความให้คุณ",
    },
    "articles.start_first": {
        "English": "Start your first research",
        "ไทย": "เริ่มค้นคว้าหัวข้อแรก",
    },
    "articles.no_match_title": {"English": "No match", "ไทย": "ไม่พบบทความ"},
    "articles.no_match_body": {
        "English": "Nothing here matches “{query}”.",
        "ไทย": "ไม่มีบทความที่ตรงกับ “{query}”",
    },
    "articles.page": {"English": "Page (1–{total})", "ไทย": "หน้า (1–{total})"},
    "articles.read": {"English": "Read article", "ไทย": "อ่านบทความ"},
    "articles.inspect": {"English": "Inspect", "ไทย": "ดูรายละเอียด"},
    "articles.actions": {"English": "Actions", "ไทย": "จัดการ"},
    "articles.delete": {"English": "Delete report", "ไทย": "ลบรายงาน"},
    "articles.delete_note": {
        "English": "Deleted reports can be restored from Deleted reports.",
        "ไทย": "กู้คืนได้จากรายการรายงานที่ลบ",
    },
    "articles.deleted": {
        "English": "Moved “{name}” to Deleted reports.",
        "ไทย": "ย้าย “{name}” ไปยังรายการรายงานที่ลบแล้ว",
    },
    "articles.trash": {
        "English": "Deleted reports ({n})", "ไทย": "รายงานที่ลบ ({n})",
    },
    "articles.trash_note": {
        "English": "Restore a report to your library. Deleting a report does not refund research quota.",
        "ไทย": "กู้คืนรายงานกลับไปยังคลังได้ การลบรายงานไม่คืนโควตาค้นคว้าที่ใช้ไปแล้ว",
    },
    "articles.restore": {"English": "Restore", "ไทย": "กู้คืน"},
    "articles.restored": {
        "English": "Restored “{name}”.", "ไทย": "กู้คืน “{name}” แล้ว",
    },
    "articles.restore_conflict": {
        "English": "A report with this name already exists. Move it to Deleted reports before restoring this version.",
        "ไทย": "มีรายงานชื่อนี้อยู่ในคลังแล้ว หากต้องการกู้คืนฉบับนี้ ให้ย้ายรายงานที่มีอยู่ไปยังรายการรายงานที่ลบก่อน",
    },
    "articles.action_failed": {
        "English": "The report could not be moved. Refresh the page and try again.",
        "ไทย": "ไม่สามารถย้ายรายงานได้ กรุณารีเฟรชหน้าแล้วลองอีกครั้ง",
    },
    "articles.back": {"English": "Back to my articles", "ไทย": "กลับไปยังบทความของฉัน"},
    "articles.saved_details_note": {
        "English": "These are the research materials saved before the run stopped.",
        "ไทย": "ข้อมูลด้านล่างคือผลการค้นคว้าที่บันทึกไว้ก่อนการสร้างบทความหยุดลง",
    },
    "articles.saved_outline": {"English": "Research outline", "ไทย": "โครงร่างจากการค้นคว้า"},
    "articles.initial_outline": {"English": "Initial outline", "ไทย": "โครงร่างเบื้องต้น"},
    "articles.saved_interviews": {"English": "Research questions and answers", "ไทย": "บันทึกการถามตอบระหว่างค้นคว้า"},
    "articles.saved_sources": {"English": "Collected sources", "ไทย": "ข้อมูลจากแหล่งค้นคว้า"},
    "articles.no_saved_details": {
        "English": "This run stopped before any research materials were saved.",
        "ไทย": "งานนี้หยุดลงก่อนที่จะมีการบันทึกข้อมูลการค้นคว้า",
    },
    "articles.saved_details_unreadable": {
        "English": "This saved research file is incomplete or could not be read.",
        "ไทย": "ข้อมูลส่วนนี้ไม่สมบูรณ์หรือไม่สามารถอ่านได้",
    },
    "create.invalid_topic": {
        "English": "Please use a topic that does not begin with a dot or contain a backslash.",
        "ไทย": "กรุณาระบุหัวข้อที่ไม่ขึ้นต้นด้วยจุดและไม่มีเครื่องหมายแบ็กสแลช (\\)",
    },
    "articles.incomplete": {"English": "incomplete run", "ไทย": "สร้างบทความไม่สำเร็จ"},
    "articles.incomplete_body": {
        "English": "This topic has no finished article — the run stopped early.",
        "ไทย": "การสร้างบทความหยุดลงก่อนเสร็จสิ้น หัวข้อนี้จึงยังไม่มีบทความฉบับสมบูรณ์",
    },
    # -- reading an article ----------------------------------------------
    "article.download": {
        "English": "Download as Markdown",
        "ไทย": "ดาวน์โหลดเป็น Markdown",
    },
    # The interactive export. "Report" rather than "HTML" because what the
    # button hands over is the whole run — article, evidence and interviews —
    # not a change of file format.
    "article.download_report": {
        "English": "Download interactive report",
        "ไทย": "ดาวน์โหลดรายงานแบบโต้ตอบ",
    },
    # Short forms for the pair of buttons under the article title, where the
    # body column is half the page: at that width "Download interactive
    # report" broke mid-word. The icon and the tooltip carry the verb.
    "article.download_report_short": {
        "English": "Interactive report",
        "ไทย": "รายงานแบบโต้ตอบ",
    },
    "article.download_short": {"English": "Markdown", "ไทย": "Markdown"},
    "article.report_help": {
        "English": "One HTML file with the article, every source behind it and "
        "the interviews that produced it. Opens in any browser, no internet needed.",
        "ไทย": "ไฟล์ HTML ที่รวมบทความ แหล่งอ้างอิง "
        "และบันทึกการถามตอบระหว่างค้นคว้าไว้ในไฟล์เดียว "
        "เปิดอ่านในเว็บเบราว์เซอร์ได้โดยไม่ต้องเชื่อมต่ออินเทอร์เน็ต",
    },
    "article.toc": {"English": "Table of contents", "ไทย": "สารบัญ"},
    "article.view_all_references": {
        "English": "View all references",
        "ไทย": "ดูแหล่งอ้างอิงทั้งหมด",
    },
    "article.references": {"English": "References", "ไทย": "แหล่งอ้างอิง"},
    "article.no_references": {
        "English": "No references available.",
        "ไทย": "ไม่มีแหล่งอ้างอิง",
    },
    "article.jump_reference": {
        "English": "Jump to a reference",
        "ไทย": "เลือกดูแหล่งอ้างอิง",
    },
    "article.highlights": {"English": "Highlights", "ไทย": "ข้อความสำคัญจากแหล่งข้อมูล"},
    "article.conversation": {
        "English": "See how STORM researched this — the agent interviews the topic "
        "from several perspectives before writing",
        "ไทย": "ดูบันทึกการถามตอบที่ STORM ใช้ค้นคว้าหัวข้อนี้จากหลายมุมมองก่อนเขียนบทความ",
    },
    # -- research progress -----------------------------------------------
    "status.perspectives_start": {
        "English": "Start identifying different perspectives for researching the topic.",
        "ไทย": "กำลังกำหนดมุมมองสำหรับการค้นคว้าหัวข้อนี้",
    },
    "status.perspectives_end": {
        "English": "Finish identifying perspectives. Will now start gathering "
        "information from the following perspectives:\n- {perspectives}",
        "ไทย": "กำหนดมุมมองแล้ว กำลังรวบรวมข้อมูลจากมุมมองต่อไปนี้:\n- {perspectives}",
    },
    "status.browsing_start": {
        "English": "Start browsing the Internet.",
        "ไทย": "กำลังค้นหาข้อมูลจากอินเทอร์เน็ต",
    },
    "status.browsed": {
        "English": "Finish browsing {link}.",
        "ไทย": "อ่านข้อมูลจาก {link} แล้ว",
    },
    "status.browsing_end": {
        "English": "Finish collecting information.",
        "ไทย": "รวบรวมข้อมูลเสร็จสิ้น",
    },
    "status.organizing_start": {
        "English": "Start organizing information into a hierarchical outline.",
        "ไทย": "กำลังจัดข้อมูลเป็นโครงร่างบทความ",
    },
    "status.outline_internal": {
        "English": "Finish leveraging the internal knowledge of the large language model.",
        "ไทย": "สร้างโครงร่างเบื้องต้นจากความรู้ของโมเดลภาษาแล้ว",
    },
    "status.outline_collected": {
        "English": "Finish leveraging the collected information.",
        "ไทย": "ปรับโครงร่างตามข้อมูลที่รวบรวมได้แล้ว",
    },
    # -- fixed replies the engine writes itself ---------------------------
    # These two are hard-coded in `knowledge_curation.py`, so no prompt can
    # translate them; they are swapped out on the way to the screen instead.
    "expert.cannot_answer": {
        "English": "Sorry, I cannot answer this question. Please ask another question.",
        "ไทย": "ขออภัย ไม่สามารถตอบคำถามนี้ได้ กรุณาถามคำถามอื่น",
    },
    "expert.no_information": {
        "English": "Sorry, I cannot find information for this question. "
        "Please ask another question.",
        "ไทย": "ขออภัย ไม่พบข้อมูลสำหรับคำถามนี้ กรุณาถามคำถามอื่น",
    },
    # -- the round table (Co-STORM) ---------------------------------------
    "table.title": {
        "English": "Sit in on the research",
        "ไทย": "ค้นคว้าผ่านการสนทนา",
    },
    "table.subtitle": {
        "English": "A panel of experts discusses your topic while you watch. "
        "Ask a question, push back, or steer them somewhere else at "
        "any point — then have them write the report.",
        "ไทย": "ผู้เชี่ยวชาญ AI จะแลกเปลี่ยนข้อมูลและมุมมองเกี่ยวกับหัวข้อของคุณ "
        "คุณสามารถถามคำถาม เสนอมุมมองเพิ่มเติม หรือปรับทิศทางการสนทนาได้ "
        "จากนั้นให้ระบบสรุปผลเป็นรายงาน",
    },
    "table.topic_placeholder": {
        "English": "e.g. Should Thailand build a land bridge?",
        "ไทย": "เช่น ไทยควรสร้างแลนด์บริดจ์หรือไม่?",
    },
    "table.submit": {"English": "Open the discussion", "ไทย": "เริ่มการสนทนา"},
    "table.caption": {
        "English": "Getting the room up to speed takes roughly 2–4 minutes. "
        "After that every turn is a minute or so, and nothing happens "
        "until you ask for it.",
        "ไทย": "การเตรียมการสนทนาใช้เวลาประมาณ 2–4 นาที จากนั้นแต่ละรอบใช้เวลาประมาณ 1 นาที "
        "ระบบจะเริ่มรอบถัดไปเมื่อคุณกดดำเนินการต่อหรือส่งข้อความ",
    },
    "table.step1_title": {"English": "They read up", "ไทย": "เตรียมข้อมูลและผู้เชี่ยวชาญ AI"},
    "table.step1_body": {
        "English": "A panel is picked for the topic and interviews itself, "
        "searching the web, until everyone shares the same background.",
        "ไทย": "ระบบกำหนดบทบาทผู้เชี่ยวชาญ AI ให้เหมาะกับหัวข้อ "
        "แล้วให้ถามตอบและค้นหาข้อมูลจากเว็บไซต์ "
        "เพื่อรวบรวมข้อมูลพื้นฐานสำหรับการสนทนา",
    },
    "table.step2_title": {"English": "You join in", "ไทย": "ร่วมแลกเปลี่ยนความคิดเห็น"},
    "table.step2_body": {
        "English": "Let the table run a turn at a time, or say something "
        "yourself. A moderator steps in when the experts circle.",
        "ไทย": "คุณสามารถให้ผู้เชี่ยวชาญ AI สนทนาต่อทีละรอบ หรือส่งคำถามและความคิดเห็นได้ "
        "โดยมี AI ผู้ดำเนินการสนทนาช่วยปรับประเด็นเมื่อเนื้อหาเริ่มซ้ำ",
    },
    "table.step3_title": {"English": "It gets written up", "ไทย": "สรุปเป็นรายงาน"},
    "table.step3_body": {
        "English": "Everything said is filed into a mind map as it goes. The "
        "report is written from that map, and lands in your library.",
        "ไทย": "ระบบจัดข้อมูลจากการสนทนาไว้ในแผนผังความคิด เมื่อคุณเลือกสร้างรายงาน "
        "ระบบจะเรียบเรียงข้อมูลจากแผนผังและบันทึกรายงานไว้ใน “บทความของฉัน”",
    },
    "table.in_progress": {"English": "round table open", "ไทย": "กำลังดำเนินการสนทนา"},
    "table.warm_label": {
        "English": "Getting the room up to speed (about 3 minutes).",
        "ไทย": "กำลังเตรียมข้อมูลสำหรับการสนทนา (ประมาณ 3 นาที)",
    },
    "table.warm_done": {"English": "The table is ready.", "ไทย": "พร้อมเริ่มการสนทนา"},
    "table.warm_step1": {
        "English": "Inviting experts and letting them interview each other.",
        "ไทย": "กำลังกำหนดบทบาทผู้เชี่ยวชาญ AI และรวบรวมข้อมูลผ่านการถามตอบ",
    },
    "table.warm_step2": {
        "English": "Organising what they found.",
        "ไทย": "กำลังจัดระเบียบข้อมูลที่รวบรวมได้",
    },
    "table.warm_step3": {
        "English": "Filing it into the mind map.",
        "ไทย": "กำลังบันทึกข้อมูลลงแผนผังความคิด",
    },
    "table.warm_step4": {
        "English": "Writing the opening of the discussion.",
        "ไทย": "กำลังเรียบเรียงประเด็นเริ่มต้นการสนทนา",
    },
    "table.thinking": {"English": "The table is thinking…", "ไทย": "กำลังประมวลผลการสนทนา…"},
    "table.thinking_done": {"English": "Your turn.", "ไทย": "พร้อมรับคำถามหรือดำเนินการต่อ"},
    "table.planning": {
        "English": "Deciding who speaks next.",
        "ไทย": "กำลังเลือกผู้เชี่ยวชาญ AI สำหรับรอบถัดไป",
    },
    "table.searching": {
        "English": "Searching for something to back it up.",
        "ไทย": "กำลังค้นหาข้อมูลสนับสนุนคำตอบ",
    },
    "table.polishing": {
        "English": "Putting it into words.",
        "ไทย": "กำลังปรับถ้อยคำของคำตอบ",
    },
    "table.filing": {
        "English": "Filing what was said into the mind map.",
        "ไทย": "กำลังบันทึกข้อมูลจากการสนทนาลงแผนผังความคิด",
    },
    "table.reorganising": {
        "English": "Tidying up the mind map.",
        "ไทย": "กำลังจัดระเบียบแผนผังความคิดใหม่",
    },
    "table.step_browsed": {
        "English": "Read {n} sources so far…",
        "ไทย": "อ่านข้อมูลแล้ว {n} แหล่ง…",
    },
    "table.deciding": {
        "English": "The speaker is deciding what to say.",
        "ไทย": "ผู้เชี่ยวชาญ AI กำลังเลือกประเด็นที่จะตอบ",
    },
    "table.decided": {
        "English": "Decided what to say.",
        "ไทย": "เลือกประเด็นที่จะตอบแล้ว",
    },
    "table.drafted": {
        "English": "Drafted a reply from what was found.",
        "ไทย": "ร่างคำตอบจากข้อมูลที่ค้นพบแล้ว",
    },
    "table.updating_experts": {
        "English": "Working out who else should be at the table.",
        "ไทย": "กำลังพิจารณาเพิ่มบทบาทผู้เชี่ยวชาญ AI ให้เหมาะกับประเด็น",
    },
    "table.filed": {
        "English": "Filed into the mind map.",
        "ไทย": "บันทึกลงแผนผังความคิดแล้ว",
    },
    "table.writing_sections": {
        "English": "Writing the report, one section at a time.",
        "ไทย": "กำลังเขียนรายงานทีละหัวข้อ",
    },
    # -- what the reader wants the discussion for -------------------------
    "table.purpose_label": {
        "English": "What do you want this for?",
        "ไทย": "วัตถุประสงค์ของรายงาน",
    },
    "table.purpose_report": {
        "English": "Write a report",
        "ไทย": "จัดทำรายงานหรือบทความ",
    },
    "table.purpose_report_note": {
        "English": "Cited material you will write up yourself",
        "ไทย": "รวบรวมข้อมูลพร้อมแหล่งอ้างอิงสำหรับนำไปเรียบเรียงต่อ",
    },
    "table.purpose_decide": {"English": "Make a decision", "ไทย": "ประกอบการตัดสินใจ"},
    "table.purpose_decide_note": {
        "English": "The case for and against, and what the risks are",
        "ไทย": "เปรียบเทียบข้อดี ข้อเสีย และความเสี่ยง",
    },
    "table.purpose_learn": {
        "English": "Understand the basics",
        "ไทย": "ทำความเข้าใจพื้นฐาน",
    },
    "table.purpose_learn_note": {
        "English": "New to this and after the shape of it",
        "ไทย": "ศึกษาภาพรวมและประเด็นสำคัญของหัวข้อ",
    },
    "table.purpose_teach": {
        "English": "Teach or present it",
        "ไทย": "เตรียมการสอนหรือการนำเสนอ",
    },
    "table.purpose_teach_note": {
        "English": "Points you can explain to somebody else",
        "ไทย": "รวบรวมประเด็นและคำอธิบายสำหรับถ่ายทอดให้ผู้อื่น",
    },
    "table.purpose_none": {"English": "Rather not say", "ไทย": "ยังไม่แน่ใจ"},
    "table.purpose_none_note": {
        "English": "Let the panel choose its own direction",
        "ไทย": "ให้ระบบกำหนดแนวทางการค้นคว้า",
    },
    "table.purpose_own": {"English": "Or say it yourself", "ไทย": "หรือระบุวัตถุประสงค์ด้วยตนเอง (ไม่บังคับ)"},
    "table.purpose_own_placeholder": {
        "English": "e.g. I have to brief a committee on this next week",
        "ไทย": "เช่น เตรียมข้อมูลเพื่อนำเสนอต่อคณะกรรมการในสัปดาห์หน้า",
    },
    "table.purpose_said": {
        "English": "Before we start — what I want out of this is to {purpose}.",
        "ไทย": "วัตถุประสงค์ของการค้นคว้าครั้งนี้: {purpose}",
    },
    # -- questions the table could be asked next --------------------------
    "table.suggest": {"English": "Suggest questions", "ไทย": "แนะนำคำถาม"},
    "table.suggesting": {
        "English": "Working out what would be worth asking…",
        "ไทย": "กำลังสร้างคำถามแนะนำ…",
    },
    "table.suggested": {
        "English": "Some things you could ask.",
        "ไทย": "คำถามแนะนำสำหรับการสนทนาต่อ",
    },
    "table.suggestions_label": {
        "English": "Ask one of these, or write your own below",
        "ไทย": "เลือกคำถามด้านล่าง หรือพิมพ์คำถามของคุณเอง",
    },
    "table.say_placeholder": {
        "English": "Ask the table something…",
        "ไทย": "พิมพ์คำถามหรือความคิดเห็น…",
    },
    "table.next_turn": {"English": "Let them continue", "ไทย": "ดำเนินการสนทนาต่อ"},
    "table.write_report": {"English": "Write the report", "ไทย": "สร้างรายงาน"},
    "table.writing_label": {
        "English": "Writing the report from the mind map (about a minute).",
        "ไทย": "กำลังเขียนรายงานจากแผนผังความคิด (ประมาณหนึ่งนาที)",
    },
    "table.writing_done": {"English": "The report is ready.", "ไทย": "สร้างรายงานเสร็จสิ้น"},
    "table.new": {"English": "New discussion", "ไทย": "เริ่มการสนทนาใหม่"},
    "table.new_confirm": {
        "English": "Starting a new discussion closes this one. Its report, if "
        "you wrote one, stays in your library.",
        "ไทย": "การเริ่มการสนทนาใหม่จะปิดการสนทนาปัจจุบัน รายงานที่สร้างไว้แล้วจะยังอยู่ใน "
        "“บทความของฉัน”",
    },
    "table.mind_map": {"English": "Mind map", "ไทย": "แผนผังความคิด"},
    "table.mind_map_empty": {
        "English": "Nothing filed yet.",
        "ไทย": "ยังไม่มีข้อมูลในแผนผังความคิด",
    },
    "table.you": {"English": "You", "ไทย": "คุณ"},
    "table.turns": {"English": "{n} turns", "ไทย": "{n} รอบการสนทนา"},
    "table.report_ready": {
        "English": "The report is in your library.",
        "ไทย": "บันทึกรายงานไว้ใน “บทความของฉัน” แล้ว",
    },
    "table.failed_turn": {
        "English": "That turn did not go through. The discussion is still "
        "open — try again, or say something yourself.",
        "ไทย": "เกิดข้อผิดพลาดในรอบการสนทนานี้ คุณสามารถลองอีกครั้ง "
        "หรือส่งคำถามและความคิดเห็นเพื่อสนทนาต่อได้",
    },
    "table.failed_empty_report": {
        "English": "The report came back empty, so nothing was saved. The "
        "discussion is untouched — try again.",
        "ไทย": "ระบบไม่สามารถสร้างเนื้อหารายงานได้ จึงยังไม่ได้บันทึกรายงาน "
        "ข้อมูลการสนทนายังอยู่ คุณสามารถลองสร้างรายงานอีกครั้งได้",
    },
    "table.failed_embedding": {
        "English": "Co-STORM sorts every source it finds by similarity, which "
        "needs an embedding model the current settings do not provide.",
        "ไทย": "Co-STORM ต้องใช้โมเดล embedding เพื่อจัดกลุ่มแหล่งข้อมูลตามความคล้ายคลึง "
        "แต่ยังไม่ได้ตั้งค่าโมเดลนี้",
    },
    "article.view_label": {"English": "How to read this", "ไทย": "รูปแบบการแสดงผล"},
    "article.view_article": {"English": "Article", "ไทย": "บทความ"},
    "article.view_report": {"English": "Report", "ไทย": "รายงาน"},
    "article.view_failed": {
        "English": "The report could not be built for this run.",
        "ไทย": "ไม่สามารถแสดงผลการค้นคว้าครั้งนี้ในรูปแบบรายงานได้",
    },
    # -- dates and lengths -------------------------------------------------
    "date.today": {"English": "{time} today", "ไทย": "{time} วันนี้"},
    "date.yesterday": {"English": "yesterday", "ไทย": "เมื่อวาน"},
    "date.days_ago": {"English": "{n}d ago", "ไทย": "{n} วันก่อน"},
    "date.this_year": {"English": "{month} {day}", "ไทย": "{day} {month}"},
    "date.other_year": {
        "English": "{month} {day}, {year}",
        "ไทย": "{day} {month} {year}",
    },
    "length.words": {"English": "{n:,} words", "ไทย": "{n:,} คำ"},
    "length.chars": {"English": "{n:,} chars", "ไทย": "{n:,} ตัวอักษร"},
}

# Abbreviated month names, indexed 1–12. `%b` only knows the C locale, which
# the app cannot rely on being installed.
_MONTHS = {
    "English": (
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ),
    "ไทย": (
        "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
        "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
    ),
}


def current():
    """The interface language in use. Always one of `LANGUAGES`."""
    language = st.session_state.get(STATE_KEY, DEFAULT)
    return language if language in LANGUAGES else DEFAULT


def _remembered():
    """The language the browser is carrying, if it is still one we have.

    Read from the request's own cookies rather than through the component:
    the component returns None on the first render of a page load, which is
    precisely the moment a refreshed page needs the answer.

    Unquoted on the way in, because a language named in its own script is
    percent-encoded on the way out — "ไทย" comes back as "%E0%B9%84...", which
    matches nothing in `LANGUAGES`.
    """
    try:
        value = (st.context.cookies or {}).get(COOKIE_NAME)
    except Exception:  # noqa: BLE001 - no request behind this run
        return None
    if not value:
        return None
    value = unquote(value)
    return value if value in LANGUAGES else None


def _picked():
    """The radio's on_change: note that a person moved it.

    Only a note. Writing the cookie draws a component, and a callback is not
    allowed to draw — so the write happens on the rerun that follows.
    """
    st.session_state[_PENDING_WRITE] = True


def _remember():
    """Write the picker's value to the browser, if a person just changed it.

    Guarded on an actual change rather than run unconditionally. Writing on
    every run looks harmless until the read fails for some other reason: the
    picker falls back to English, and then this would helpfully save English
    over the choice the reader had made — which is exactly how the first
    version of this erased a Thai cookie on every refresh.
    """
    if not st.session_state.pop(_PENDING_WRITE, False):
        return
    try:
        auth.remember_preference(
            COOKIE_NAME,
            current(),
            key="storm_lang_cookie_set",
            max_age=COOKIE_MAX_AGE,
        )
    except Exception:  # noqa: BLE001 - a preference is not worth a stack trace
        pass


def t(key, **kwargs):
    """The string for `key` in the current interface language.

    Unknown keys raise rather than falling back silently: a typo should show
    up the first time the line is drawn, not ship as English in a Thai page.
    """
    try:
        translations = _STRINGS[key]
    except KeyError:
        raise KeyError(f"No interface string named {key!r}") from None
    text = translations.get(current()) or translations[DEFAULT]
    return text.format(**kwargs) if kwargs else text


def localize_engine_reply(text):
    """Translate a reply STORM produced without going through a prompt.

    The transcript is otherwise written by the model, which the prompts steer
    into the chosen language. Its two hard-coded fallbacks cannot be steered,
    so they are matched here — exactly, to avoid touching real answers.
    """
    for key in ("expert.cannot_answer", "expert.no_information"):
        if text.strip() == _STRINGS[key][DEFAULT]:
            return t(key)
    return text


def month(number):
    """Abbreviated name of month `number` (1–12) in the current language."""
    return _MONTHS.get(current(), _MONTHS[DEFAULT])[number - 1]


# The two-letter tag shown on the trigger, so the button says which language
# is active without opening it.
_SHORT = {"English": "EN", "ไทย": "TH"}


def selector():
    """The language picker, pinned beside Streamlit's own menu.

    A globe is the one control people look for in a top corner when a page is
    in the wrong language, and it belongs next to the other app-wide setting
    (the theme) rather than buried in the sidebar with the navigation.
    """
    # Seeded before the radio is drawn: Streamlit refuses an assignment to a
    # widget's key once that widget exists, so restoring the remembered choice
    # has to happen on the way in rather than after.
    if STATE_KEY not in st.session_state:
        st.session_state[STATE_KEY] = _remembered() or DEFAULT

    with st.popover(
        _SHORT.get(current(), current()),
        icon=":material/language:",
        help=t("lang.label"),
        key="lang_selector",
    ):
        st.radio(
            t("lang.label"),
            LANGUAGES,
            key=STATE_KEY,
            on_change=_picked,
            label_visibility="collapsed",
        )

    _remember()
