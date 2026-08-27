"""The language of the interface itself, separate from the article's language.

Every string the app draws goes through `t()`. The strings live here as one
dict keyed by a stable id, with the languages side by side, so a missing
translation is visible at a glance rather than hiding in another file.

The article's language is a different choice — see `article_language` — but
picking a UI language sets the default for it, because someone reading a Thai
interface almost always wants a Thai article too.
"""

import streamlit as st

# Display name -> itself. Language names are written in their own language,
# which is what a picker should show to someone who cannot read the current one.
LANGUAGES = ("English", "ไทย")

DEFAULT = "English"

# Not prefixed with "page", so it survives `clear_other_page_session_state`.
STATE_KEY = "ui_lang"

_STRINGS = {
    # -- chrome ---------------------------------------------------------
    "nav.label": {"English": "Navigation", "ไทย": "เมนู"},
    "nav.articles": {"English": "My Articles", "ไทย": "บทความของฉัน"},
    "nav.create": {"English": "Create New Article", "ไทย": "สร้างบทความใหม่"},
    "brand.tagline": {
        "English": "Researches a topic from many perspectives, then writes a cited article.",
        "ไทย": "ค้นคว้าหัวข้อจากหลายมุมมอง แล้วเรียบเรียงเป็นบทความพร้อมแหล่งอ้างอิง",
    },
    "lang.label": {"English": "Interface language", "ไทย": "ภาษาของระบบ"},
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
    "articles.back": {
        "English": "← Back to all articles",
        "ไทย": "← กลับไปหน้ารวมบทความ",
    },
    # -- reading an article ----------------------------------------------
    "article.download": {
        "English": "Download as Markdown",
        "ไทย": "ดาวน์โหลดเป็น Markdown",
    },
    "article.toc": {"English": "Table of contents", "ไทย": "สารบัญ"},
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
            label_visibility="collapsed",
        )
