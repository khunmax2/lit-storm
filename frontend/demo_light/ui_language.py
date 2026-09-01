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
    "nav.articles": {"English": "My Articles", "ไทย": "บทความของฉัน"},
    "nav.create": {"English": "Create New Article", "ไทย": "สร้างบทความใหม่"},
    # A short label under the wordmark, as in the reference. The sentence it
    # replaced described the product; at rail width it wrapped to two lines
    # and read as a paragraph someone forgot to move.
    "brand.role": {
        "English": "Research Assistant",
        "ไทย": "ผู้ช่วยงานวิจัย",
    },
    "brand.tagline": {
        "English": "Researches a topic from many perspectives, then writes a cited article.",
        "ไทย": "ค้นคว้าหัวข้อจากหลายมุมมอง แล้วเรียบเรียงเป็นบทความพร้อมแหล่งอ้างอิง",
    },
    "lang.label": {"English": "Interface language", "ไทย": "ภาษาของระบบ"},
    "nav.sources": {"English": "Search sources", "ไทย": "แหล่งค้นคว้า"},
    "nav.roundtable": {"English": "Round table", "ไทย": "โต๊ะกลม"},
    # -- search sources ---------------------------------------------------
    "search.title": {"English": "Search sources", "ไทย": "แหล่งค้นคว้า"},
    "search.using": {"English": "researching with {name}", "ไทย": "กำลังใช้ {name}"},
    "search.one_at_a_time": {
        "English": "STORM researches with one source at a time. Pick the one "
        "it should use; the rest keep their keys for later.",
        "ไทย": "STORM ใช้แหล่งค้นคว้าได้ทีละหนึ่งแหล่ง เลือกแหล่งที่จะใช้ "
        "ส่วนแหล่งอื่นจะเก็บคีย์ไว้ให้",
    },
    "search.free": {"English": "no key", "ไทย": "ไม่ต้องใช้คีย์"},
    "search.paid": {"English": "needs a key", "ไทย": "ต้องมีคีย์"},
    "search.in_use": {"English": "in use", "ไทย": "ใช้อยู่"},
    "search.unavailable": {"English": "unavailable", "ไทย": "ใช้ไม่ได้"},
    "search.key_saved": {
        "English": "API key — saved, ending {last4}. Type a new one to replace it.",
        "ไทย": "API key — บันทึกแล้ว ลงท้าย {last4} · พิมพ์ค่าใหม่เพื่อแทนที่",
    },
    "search.key_needed": {"English": "API key", "ไทย": "API key"},
    "search.no_key_needed": {
        "English": "Public search, no account needed.",
        "ไทย": "ค้นหาสาธารณะ ไม่ต้องสมัครบัญชี",
    },
    "search.get_key": {"English": "Where to get one", "ไทย": "ขอคีย์ได้ที่นี่"},
    "search.test": {"English": "Test", "ไทย": "ทดสอบ"},
    "search.testing": {"English": "Searching…", "ไทย": "กำลังค้นหา…"},
    "search.use": {"English": "Use this", "ไทย": "ใช้แหล่งนี้"},
    "search.forget_key": {"English": "Forget this key", "ไทย": "ลบคีย์นี้"},
    "search.test_ok": {
        "English": "Working — {n} results, from {hosts}.",
        "ไทย": "ใช้งานได้ — ได้ผล {n} รายการ จาก {hosts}",
    },
    "search.test_failed": {
        "English": "The search did not go through.",
        "ไทย": "ค้นหาไม่สำเร็จ",
    },
    "search.no_results": {
        "English": "The search went through but came back empty.",
        "ไทย": "เชื่อมต่อได้ แต่ไม่มีผลลัพธ์กลับมา",
    },
    "arxiv_note": {
        "English": "Paper abstracts straight from arxiv.org — no key, no "
        "account. Strong on computing, physics and maths; thin on history, "
        "law and the humanities. One search every three seconds, as arXiv "
        "asks, so a run takes longer.",
        "ไทย": "บทคัดย่องานวิจัยจาก arxiv.org โดยตรง ไม่ต้องมีคีย์หรือบัญชี · "
        "แข็งด้านคอมพิวเตอร์ ฟิสิกส์ คณิตศาสตร์ · บางด้านประวัติศาสตร์ "
        "กฎหมาย สังคมศาสตร์ · ค้นได้ 3 วินาทีต่อครั้งตามที่ arXiv ขอ "
        "การรันจึงใช้เวลานานขึ้น",
    },
    "search.needs_endpoint": {
        "English": "Marked internal-only in the library, and needs a private "
        "Stanford endpoint that is not published.",
        "ไทย": "ไลบรารีระบุว่าใช้ภายในเท่านั้น และต้องมี endpoint ของ Stanford "
        "ซึ่งไม่ได้เปิดสาธารณะ",
    },
    "search.needs_collection": {
        "English": "Searches your own documents, which have to be embedded "
        "into a vector store first — a setup of its own, not a key.",
        "ไทย": "ค้นจากเอกสารของคุณเอง ซึ่งต้องนำเข้าฐานข้อมูลเวกเตอร์ก่อน "
        "เป็นการติดตั้งอีกชุด ไม่ใช่แค่ใส่คีย์",
    },
    "search.failed_config": {
        "English": "The search source is not configured, so no run was started.",
        "ไทย": "ยังตั้งค่าแหล่งค้นคว้าไม่ครบ จึงยังไม่ได้เริ่มค้นคว้า",
    },
    # -- creating an article --------------------------------------------
    "create.eyebrow": {"English": "Powered by STORM", "ไทย": "ขับเคลื่อนด้วย STORM"},
    "create.title": {
        "English": "What do you want to learn in depth?",
        "ไทย": "อยากรู้เรื่องอะไรแบบเจาะลึก?",
    },
    "create.subtitle": {
        "English": "STORM researches your topic from several perspectives, "
        "gathers sources from the web, then writes a cited, "
        "Wikipedia-style article.",
        "ไทย": "STORM จะค้นคว้าหัวข้อของคุณจากหลายมุมมอง "
        "รวบรวมแหล่งข้อมูลจากเว็บ "
        "แล้วเขียนเป็นบทความสไตล์วิกิพีเดียพร้อมอ้างอิง",
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
        "ไทย": "กรุณาใส่หัวข้อก่อน",
    },
    "create.try_example": {"English": "Try an example", "ไทย": "ลองหัวข้อตัวอย่าง"},
    "create.in_progress": {"English": "research in progress", "ไทย": "กำลังค้นคว้า"},
    "create.step1": {
        "English": "Step 1 of 2 · brain**STORM**ing — researching the topic "
        "(about 2 minutes).",
        "ไทย": "ขั้นที่ 1 จาก 2 · brain**STORM**ing — กำลังค้นคว้าหัวข้อ "
        "(ประมาณ 2 นาที)",
    },
    "create.step1_done": {
        "English": "Step 1 of 2 · research complete",
        "ไทย": "ขั้นที่ 1 จาก 2 · ค้นคว้าเสร็จแล้ว",
    },
    "create.step2": {
        "English": "Step 2 of 2 · writing and polishing the article (about 2 minutes).",
        "ไทย": "ขั้นที่ 2 จาก 2 · กำลังเขียนและขัดเกลาบทความ (ประมาณ 2 นาที)",
    },
    "create.step2_writing": {
        "English": "Connecting the sources I found into a cited article…",
        "ไทย": "กำลังเรียบเรียงแหล่งข้อมูลที่พบให้เป็นบทความพร้อมอ้างอิง…",
    },
    "create.step2_done": {
        "English": "Step 2 of 2 · article ready",
        "ไทย": "ขั้นที่ 2 จาก 2 · บทความพร้อมแล้ว",
    },
    "create.failed_label": {
        "English": "Run stopped",
        "ไทย": "การค้นคว้าหยุดกลางคัน",
    },
    "create.failed_quota": {
        "English": "The model provider turned the request away — usually a rate "
        "limit or an empty balance. Check the API key's quota, then try again.",
        "ไทย": "ผู้ให้บริการโมเดลปฏิเสธคำขอ ส่วนใหญ่เกิดจากโควตาเต็มหรือเครดิตหมด "
        "ตรวจสอบโควตาของ API key แล้วลองใหม่",
    },
    "create.failed_generic": {
        "English": "Something went wrong partway through. Nothing was saved.",
        "ไทย": "เกิดข้อผิดพลาดระหว่างทาง ยังไม่มีอะไรถูกบันทึก",
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
        "ไทย": "งานค้นคว้าและบทความที่คุณสร้างจะผูกกับบัญชีของคุณ",
    },
    "auth.tab_signin": {"English": "Sign in", "ไทย": "เข้าสู่ระบบ"},
    "auth.tab_signup": {"English": "Create account", "ไทย": "สมัครสมาชิก"},
    "auth.email": {"English": "Email", "ไทย": "อีเมล"},
    "auth.password": {"English": "Password", "ไทย": "รหัสผ่าน"},
    "auth.name": {"English": "Display name", "ไทย": "ชื่อที่ใช้แสดง"},
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
        "ไทย": "สร้างบัญชีแล้ว กรุณาเปิดอีเมลเพื่อยืนยัน แล้วจึงเข้าสู่ระบบ",
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
    "auth.role_admin": {"English": "Admin", "ไทย": "ผู้ดูแล"},
    "auth.quota": {
        "English": "{used} of {limit} runs this month",
        "ไทย": "ใช้ไป {used} จาก {limit} ครั้งในเดือนนี้",
    },
    "auth.quota_spent": {
        "English": "You have used this month's {limit} research runs. An admin "
        "can raise your limit.",
        "ไทย": "คุณใช้สิทธิ์ค้นคว้าครบ {limit} ครั้งของเดือนนี้แล้ว "
        "ผู้ดูแลสามารถเพิ่มโควตาให้ได้",
    },
    "auth.no_profile": {
        "English": "Your account has no profile row yet. Run the schema in "
        "docs/supabase-schema.sql.",
        "ไทย": "บัญชีนี้ยังไม่มีข้อมูลโปรไฟล์ กรุณารันสคีมาใน "
        "docs/supabase-schema.sql",
    },
    # -- admin ------------------------------------------------------------
    "nav.admin": {"English": "Members", "ไทย": "สมาชิก"},
    "admin.title": {"English": "Members", "ไทย": "จัดการสมาชิก"},
    "admin.count": {"English": "{n} accounts", "ไทย": "{n} บัญชี"},
    "admin.col_name": {"English": "Name", "ไทย": "ชื่อ"},
    "admin.col_email": {"English": "Email", "ไทย": "อีเมล"},
    "admin.col_role": {"English": "Role", "ไทย": "สิทธิ์"},
    "admin.col_limit": {"English": "Runs / month", "ไทย": "โควตา/เดือน"},
    "admin.col_used": {"English": "Used", "ไทย": "ใช้ไป"},
    "admin.col_active": {"English": "Active", "ไทย": "ใช้งานอยู่"},
    "admin.col_joined": {"English": "Joined", "ไทย": "สมัครเมื่อ"},
    "admin.help_limit": {
        "English": "Research runs allowed each calendar month. 0 stops new runs "
        "without closing the account.",
        "ไทย": "จำนวนครั้งที่ค้นคว้าได้ต่อเดือน ตั้ง 0 เพื่อหยุดการรันใหม่ "
        "โดยไม่ต้องปิดบัญชี",
    },
    "admin.save": {"English": "Save changes", "ไทย": "บันทึกการแก้ไข"},
    "admin.saved": {"English": "Saved {n} change(s).", "ไทย": "บันทึกแล้ว {n} รายการ"},
    "admin.no_changes": {"English": "Nothing to save.", "ไทย": "ไม่มีการแก้ไข"},
    "admin.last_admin": {
        "English": "You are the only admin — keep at least one, or nobody can "
        "manage members.",
        "ไทย": "คุณเป็นผู้ดูแลคนเดียว ต้องเหลือผู้ดูแลอย่างน้อยหนึ่งคน "
        "ไม่งั้นจะไม่มีใครจัดการสมาชิกได้",
    },
    "admin.runs_label": {"English": "Recent runs", "ไทย": "การค้นคว้าล่าสุด"},
    "admin.runs_empty": {"English": "No runs yet.", "ไทย": "ยังไม่มีการค้นคว้า"},
    "admin.col_topic": {"English": "Topic", "ไทย": "หัวข้อ"},
    "admin.col_status": {"English": "Status", "ไทย": "สถานะ"},
    "admin.col_when": {"English": "Started", "ไทย": "เริ่มเมื่อ"},
    "admin.col_who": {"English": "By", "ไทย": "โดย"},
    "admin.denied": {
        "English": "Members only. Ask an admin if you need access.",
        "ไทย": "เฉพาะผู้ดูแลเท่านั้น หากต้องการสิทธิ์กรุณาติดต่อผู้ดูแล",
    },
    # -- landing / home --------------------------------------------------
    "nav.home": {"English": "Home", "ไทย": "หน้าแรก"},
    "home.hero_note": {
        "English": "Every claim carries a citation you can open and check.",
        "ไทย": "ทุกข้อความมีแหล่งอ้างอิงที่กดเปิดตรวจสอบได้",
    },
    "home.engine_label": {
        "English": "How should the research happen?",
        "ไทย": "อยากให้ค้นคว้าแบบไหน",
    },
    # The engines' own names, in both languages: a proper noun does not
    # translate, and the line under the switch is where the difference between
    # them is actually explained.
    "home.engine_storm": {"English": "STORM", "ไทย": "STORM"},
    "home.engine_costorm": {"English": "Co-STORM", "ไทย": "Co-STORM"},
    "home.engine_storm_note": {
        "English": "STORM researches on its own and hands back a cited "
        "article. About 2–5 minutes, nothing to do but wait.",
        "ไทย": "STORM ค้นคว้าเองจนจบ แล้วส่งบทความพร้อมอ้างอิงกลับมา "
        "ใช้เวลาราว 2–5 นาที ระหว่างนั้นไม่ต้องทำอะไร",
    },
    "home.engine_costorm_note": {
        "English": "Co-STORM lets a panel argue it out while you watch, "
        "interrupt, and steer. Slower, and the direction is yours.",
        "ไทย": "Co-STORM เปิดวงให้ผู้เชี่ยวชาญถกกันให้ดู "
        "คุณแทรกและกำหนดทิศทางได้ตลอด ช้ากว่า แต่คุมเองได้",
    },
    "home.how_label": {"English": "How it works", "ไทย": "ทำงานอย่างไร"},
    "home.step1_title": {
        "English": "It finds the angles you would not have asked about",
        "ไทย": "หามุมที่คุณอาจนึกไม่ถึง",
    },
    "home.step1_body": {
        "English": "STORM reads around the topic first, then assembles a panel of "
        "editors — a historian, an economist, a practitioner — who each "
        "interview the subject from their own angle.",
        "ไทย": "STORM อ่านเรื่องรอบ ๆ หัวข้อก่อน แล้วตั้งคณะผู้เขียนหลายมุม "
        "เช่น นักประวัติศาสตร์ นักเศรษฐศาสตร์ คนทำงานจริง "
        "ให้แต่ละคนสัมภาษณ์หัวข้อจากมุมของตัวเอง",
    },
    "home.step2_title": {
        "English": "Every question becomes a real search",
        "ไทย": "ทุกคำถามถูกแปลงเป็นการค้นจริง",
    },
    "home.step2_body": {
        "English": "Each question is turned into search queries, the pages are read, "
        "and the source behind every answer is kept.",
        "ไทย": "แต่ละคำถามถูกแปลงเป็นคำค้น ระบบเปิดอ่านหน้าเว็บจริง "
        "และเก็บแหล่งที่มาของทุกคำตอบไว้",
    },
    "home.step3_title": {
        "English": "You get an article, not a summary",
        "ไทย": "ได้บทความ ไม่ใช่บทสรุป",
    },
    "home.step3_body": {
        "English": "The findings are organised into an outline and written up section "
        "by section, with inline citations and a reference list.",
        "ไทย": "ข้อมูลที่ได้ถูกจัดเป็นโครงเรื่อง แล้วเขียนทีละหัวข้อ "
        "พร้อมอ้างอิงในเนื้อความและรายการแหล่งข้อมูลท้ายบทความ",
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
        "ไทย": "กรองตามหัวข้อ…",
    },
    "articles.empty_title": {"English": "No articles yet", "ไทย": "ยังไม่มีบทความ"},
    "articles.empty_body": {
        "English": "Head to “{create}”, give STORM a topic, "
        "and it will research and write one for you.",
        "ไทย": "ไปที่ “{create}” แล้วใส่หัวข้อที่สนใจ "
        "STORM จะค้นคว้าและเขียนบทความให้คุณ",
    },
    "articles.start_first": {
        "English": "Start your first research",
        "ไทย": "เริ่มค้นคว้าเรื่องแรก",
    },
    "articles.no_match_title": {"English": "No match", "ไทย": "ไม่พบบทความ"},
    "articles.no_match_body": {
        "English": "Nothing here matches “{query}”.",
        "ไทย": "ไม่มีบทความที่ตรงกับ “{query}”",
    },
    "articles.page": {"English": "Page (1–{total})", "ไทย": "หน้า (1–{total})"},
    "articles.read": {"English": "Read article", "ไทย": "อ่านบทความ"},
    "articles.inspect": {"English": "Inspect", "ไทย": "ดูรายละเอียด"},
    "articles.incomplete": {"English": "incomplete run", "ไทย": "ทำงานไม่สำเร็จ"},
    "articles.incomplete_body": {
        "English": "This topic has no finished article — the run stopped early.",
        "ไทย": "หัวข้อนี้ยังไม่มีบทความที่เสร็จสมบูรณ์ — การทำงานหยุดกลางคัน",
    },
    # -- reading an article ----------------------------------------------
    "article.download": {
        "English": "Download as Markdown",
        "ไทย": "ดาวน์โหลดเป็น Markdown",
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
        "ไทย": "ดูวิธีที่ STORM ค้นคว้า — ระบบจะสัมภาษณ์หัวข้อนี้จากหลายมุมมองก่อนลงมือเขียน",
    },
    # -- research progress -----------------------------------------------
    "status.perspectives_start": {
        "English": "Start identifying different perspectives for researching the topic.",
        "ไทย": "เริ่มมองหามุมมองต่าง ๆ สำหรับการค้นคว้าหัวข้อนี้",
    },
    "status.perspectives_end": {
        "English": "Finish identifying perspectives. Will now start gathering "
        "information from the following perspectives:\n- {perspectives}",
        "ไทย": "ได้มุมมองครบแล้ว กำลังเริ่มเก็บข้อมูลจากมุมมองต่อไปนี้:\n- {perspectives}",
    },
    "status.browsing_start": {
        "English": "Start browsing the Internet.",
        "ไทย": "เริ่มค้นหาข้อมูลจากอินเทอร์เน็ต",
    },
    "status.browsed": {
        "English": "Finish browsing {link}.",
        "ไทย": "อ่านข้อมูลจาก {link} แล้ว",
    },
    "status.browsing_end": {
        "English": "Finish collecting information.",
        "ไทย": "เก็บข้อมูลครบแล้ว",
    },
    "status.organizing_start": {
        "English": "Start organizing information into a hierarchical outline.",
        "ไทย": "เริ่มจัดข้อมูลให้เป็นโครงร่างตามลำดับหัวข้อ",
    },
    "status.outline_internal": {
        "English": "Finish leveraging the internal knowledge of the large language model.",
        "ไทย": "ใช้ความรู้เดิมของโมเดลภาษาร่างโครงเรื่องเสร็จแล้ว",
    },
    "status.outline_collected": {
        "English": "Finish leveraging the collected information.",
        "ไทย": "นำข้อมูลที่เก็บมาปรับโครงเรื่องเสร็จแล้ว",
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
        "ไทย": "ร่วมวงค้นคว้าไปด้วยกัน",
    },
    "table.subtitle": {
        "English": "A panel of experts discusses your topic while you watch. "
        "Ask a question, push back, or steer them somewhere else at "
        "any point — then have them write the report.",
        "ไทย": "ผู้เชี่ยวชาญหลายคนจะตั้งวงคุยหัวข้อของคุณให้ดูสด ๆ "
        "คุณแทรกเข้าไปถาม แย้ง หรือเปลี่ยนทิศทางได้ตลอด "
        "แล้วค่อยให้สรุปออกมาเป็นรายงาน",
    },
    "table.topic_placeholder": {
        "English": "e.g. Should Thailand build a land bridge?",
        "ไทย": "เช่น ไทยควรสร้างแลนด์บริดจ์หรือไม่?",
    },
    "table.submit": {"English": "Open the discussion", "ไทย": "เปิดวงสนทนา"},
    "table.caption": {
        "English": "Getting the room up to speed takes roughly 2–4 minutes. "
        "After that every turn is a minute or so, and nothing happens "
        "until you ask for it.",
        "ไทย": "ช่วงตั้งวงใช้เวลาประมาณ 2–4 นาที "
        "จากนั้นแต่ละตาใช้เวลาราวหนึ่งนาที "
        "และจะไม่มีอะไรเดินต่อจนกว่าคุณจะสั่ง",
    },
    "table.step1_title": {"English": "They read up", "ไทย": "เตรียมตัว"},
    "table.step1_body": {
        "English": "A panel is picked for the topic and interviews itself, "
        "searching the web, until everyone shares the same background.",
        "ไทย": "ระบบเลือกผู้เชี่ยวชาญให้เข้ากับหัวข้อ "
        "แล้วให้สัมภาษณ์กันเองพร้อมค้นเว็บ จนทุกคนมีพื้นเรื่องตรงกัน",
    },
    "table.step2_title": {"English": "You join in", "ไทย": "คุณร่วมวง"},
    "table.step2_body": {
        "English": "Let the table run a turn at a time, or say something "
        "yourself. A moderator steps in when the experts circle.",
        "ไทย": "จะปล่อยให้คุยกันเองทีละตา หรือพิมพ์แทรกเองก็ได้ "
        "มีผู้ดำเนินรายการคอยเปลี่ยนประเด็นเมื่อวงเริ่มวนที่เดิม",
    },
    "table.step3_title": {"English": "It gets written up", "ไทย": "สรุปเป็นรายงาน"},
    "table.step3_body": {
        "English": "Everything said is filed into a mind map as it goes. The "
        "report is written from that map, and lands in your library.",
        "ไทย": "ทุกอย่างที่คุยถูกจัดลงแผนผังความคิดไปเรื่อย ๆ "
        "รายงานเขียนจากแผนผังนั้น และไปเก็บไว้ในคลังบทความของคุณ",
    },
    "table.in_progress": {"English": "round table open", "ไทย": "วงกำลังเปิดอยู่"},
    "table.warm_label": {
        "English": "Getting the room up to speed (about 3 minutes).",
        "ไทย": "กำลังตั้งวงและปูพื้นเรื่อง (ประมาณ 3 นาที)",
    },
    "table.warm_done": {"English": "The table is ready.", "ไทย": "วงพร้อมแล้ว"},
    "table.warm_step1": {
        "English": "Inviting experts and letting them interview each other.",
        "ไทย": "กำลังเชิญผู้เชี่ยวชาญ และให้สัมภาษณ์กันเอง",
    },
    "table.warm_step2": {
        "English": "Organising what they found.",
        "ไทย": "กำลังจัดระเบียบข้อมูลที่ได้มา",
    },
    "table.warm_step3": {
        "English": "Filing it into the mind map.",
        "ไทย": "กำลังบันทึกลงแผนผังความคิด",
    },
    "table.warm_step4": {
        "English": "Writing the opening of the discussion.",
        "ไทย": "กำลังเรียบเรียงบทเปิดวง",
    },
    "table.thinking": {"English": "The table is thinking…", "ไทย": "วงกำลังคิด…"},
    "table.thinking_done": {"English": "Your turn.", "ไทย": "ถึงตาคุณแล้ว"},
    "table.planning": {
        "English": "Deciding who speaks next.",
        "ไทย": "กำลังเลือกว่าใครจะพูดต่อ",
    },
    "table.searching": {
        "English": "Searching for something to back it up.",
        "ไทย": "กำลังค้นหาหลักฐานมาสนับสนุน",
    },
    "table.polishing": {
        "English": "Putting it into words.",
        "ไทย": "กำลังเรียบเรียงคำพูด",
    },
    "table.filing": {
        "English": "Filing what was said into the mind map.",
        "ไทย": "กำลังบันทึกสิ่งที่พูดลงแผนผังความคิด",
    },
    "table.reorganising": {
        "English": "Tidying up the mind map.",
        "ไทย": "กำลังจัดระเบียบแผนผังความคิดใหม่",
    },
    "table.step_browsed": {
        "English": "Read {n} sources so far…",
        "ไทย": "อ่านมาแล้ว {n} แหล่ง…",
    },
    "table.deciding": {
        "English": "The speaker is deciding what to say.",
        "ไทย": "ผู้พูดกำลังตัดสินใจว่าจะพูดอะไร",
    },
    "table.decided": {
        "English": "Decided what to say.",
        "ไทย": "ตัดสินใจแล้วว่าจะพูดอะไร",
    },
    "table.drafted": {
        "English": "Drafted a reply from what was found.",
        "ไทย": "ร่างคำตอบจากข้อมูลที่หามาได้แล้ว",
    },
    "table.updating_experts": {
        "English": "Working out who else should be at the table.",
        "ไทย": "กำลังพิจารณาว่าควรเชิญใครเข้าวงเพิ่ม",
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
        "ไทย": "อยากได้ไปทำอะไร",
    },
    "table.purpose_report": {
        "English": "Write a report",
        "ไทย": "เขียนรายงานหรือบทความ",
    },
    "table.purpose_report_note": {
        "English": "Cited material you will write up yourself",
        "ไทย": "อยากได้เนื้อหาที่อ้างอิงได้ไปเรียบเรียงต่อ",
    },
    "table.purpose_decide": {"English": "Make a decision", "ไทย": "ใช้ตัดสินใจ"},
    "table.purpose_decide_note": {
        "English": "The case for and against, and what the risks are",
        "ไทย": "อยากรู้ข้อดีข้อเสียและความเสี่ยง",
    },
    "table.purpose_learn": {
        "English": "Understand the basics",
        "ไทย": "ทำความเข้าใจพื้นฐาน",
    },
    "table.purpose_learn_note": {
        "English": "New to this and after the shape of it",
        "ไทย": "เพิ่งเริ่มสนใจ อยากได้ภาพรวมก่อน",
    },
    "table.purpose_teach": {
        "English": "Teach or present it",
        "ไทย": "เตรียมสอนหรือนำเสนอ",
    },
    "table.purpose_teach_note": {
        "English": "Points you can explain to somebody else",
        "ไทย": "อยากได้ประเด็นที่อธิบายคนอื่นได้",
    },
    "table.purpose_none": {"English": "Rather not say", "ไทย": "ยังไม่แน่ใจ"},
    "table.purpose_none_note": {
        "English": "Let the panel choose its own direction",
        "ไทย": "ปล่อยให้วงเลือกทิศทางเอง",
    },
    "table.purpose_own": {"English": "Or say it yourself", "ไทย": "หรือพิมพ์เอง"},
    "table.purpose_own_placeholder": {
        "English": "e.g. I have to brief a committee on this next week",
        "ไทย": "เช่น ต้องไปบรีฟคณะกรรมการสัปดาห์หน้า",
    },
    "table.purpose_said": {
        "English": "Before we start — what I want out of this is to {purpose}.",
        "ไทย": "ก่อนเริ่ม — สิ่งที่ผมอยากได้จากวงนี้คือ{purpose}",
    },
    # -- questions the table could be asked next --------------------------
    "table.suggest": {"English": "Suggest questions", "ไทย": "ขอคำแนะนำคำถาม"},
    "table.suggesting": {
        "English": "Working out what would be worth asking…",
        "ไทย": "กำลังคิดว่าน่าจะถามอะไรดี…",
    },
    "table.suggested": {
        "English": "Some things you could ask.",
        "ไทย": "นี่คือคำถามที่น่าจะถามต่อ",
    },
    "table.suggestions_label": {
        "English": "Ask one of these, or write your own below",
        "ไทย": "เลือกถามข้อใดข้อหนึ่ง หรือพิมพ์เองด้านล่าง",
    },
    "table.say_placeholder": {
        "English": "Ask the table something…",
        "ไทย": "ถามวงสนทนา…",
    },
    "table.next_turn": {"English": "Let them continue", "ไทย": "ให้คุยต่อ"},
    "table.write_report": {"English": "Write the report", "ไทย": "เขียนรายงาน"},
    "table.writing_label": {
        "English": "Writing the report from the mind map (about a minute).",
        "ไทย": "กำลังเขียนรายงานจากแผนผังความคิด (ประมาณหนึ่งนาที)",
    },
    "table.writing_done": {"English": "The report is ready.", "ไทย": "รายงานพร้อมแล้ว"},
    "table.new": {"English": "New discussion", "ไทย": "เริ่มวงใหม่"},
    "table.new_confirm": {
        "English": "Starting a new discussion closes this one. Its report, if "
        "you wrote one, stays in your library.",
        "ไทย": "การเริ่มวงใหม่จะปิดวงนี้ "
        "รายงานที่เขียนไว้แล้วจะยังอยู่ในคลังบทความ",
    },
    "table.mind_map": {"English": "Mind map", "ไทย": "แผนผังความคิด"},
    "table.mind_map_empty": {
        "English": "Nothing filed yet.",
        "ไทย": "ยังไม่มีอะไรถูกบันทึก",
    },
    "table.you": {"English": "You", "ไทย": "คุณ"},
    "table.turns": {"English": "{n} turns", "ไทย": "{n} ตา"},
    "table.report_ready": {
        "English": "The report is in your library.",
        "ไทย": "รายงานถูกเก็บไว้ในคลังบทความแล้ว",
    },
    "table.failed_turn": {
        "English": "That turn did not go through. The discussion is still "
        "open — try again, or say something yourself.",
        "ไทย": "ตานี้ไม่สำเร็จ วงยังเปิดอยู่ "
        "ลองใหม่อีกครั้ง หรือพิมพ์แทรกเองก็ได้",
    },
    "table.failed_empty_report": {
        "English": "The report came back empty, so nothing was saved. The "
        "discussion is untouched — try again.",
        "ไทย": "รายงานที่ได้กลับมาว่างเปล่า จึงยังไม่ได้บันทึกอะไร "
        "วงสนทนายังอยู่ครบ ลองใหม่อีกครั้งได้",
    },
    "table.failed_embedding": {
        "English": "Co-STORM sorts every source it finds by similarity, which "
        "needs an embedding model the current settings do not provide.",
        "ไทย": "Co-STORM ต้องจัดกลุ่มแหล่งข้อมูลด้วยความคล้ายกัน "
        "ซึ่งต้องใช้โมเดล embedding ที่การตั้งค่าปัจจุบันยังไม่มี",
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
