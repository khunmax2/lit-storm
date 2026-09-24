// Screen language, Thai and English (docs/web-app-design.md). The report
// language is chosen per Run and is not this.
import { createContext, useContext, useState, type ReactNode } from "react";

export type Lang = "th" | "en";

const en = {
  app: "lit-storm",
  signIn: "Sign in",
  signOut: "Sign out",
  email: "Email",
  password: "Password",
  name: "Name",
  save: "Save",
  cancel: "Cancel",
  create: "Create",
  loading: "Loading…",
  back: "Back",
  copy: "Copy",
  copied: "Copied",
  close: "Close",
  edit: "Edit",
  yes: "Yes",
  no: "No",

  "setup.title": "Set up lit-storm",
  "setup.lead": "Create the first Administrator. You need the setup code the installer put in the Docker secret.",
  "setup.code": "Setup code",
  "setup.submit": "Create Administrator",
  "setup.noCode": "No setup code is configured. Add LITSTORM_BOOTSTRAP_CODE_FILE to the api service and restart it.",

  "login.title": "Sign in to lit-storm",
  "login.failed": "That email and password do not match an account.",

  "pw.title": "Choose your password",
  "pw.lead": "For {email}. At least 10 characters.",
  "pw.invalid": "This link has expired or was already used. Ask an Administrator for a new one.",
  "pw.submit": "Set password",
  "pw.weak": "Use at least 10 characters.",

  "nav.projects": "Projects",
  "nav.admin": "Administration",

  "projects.title": "Projects",
  "projects.new": "New project",
  "projects.namePlaceholder": "e.g. Thesis literature review",
  "projects.empty": "No projects yet. Create one to start researching.",

  "project.sessions": "Research topics",
  "project.newSession": "Research a new topic",
  "project.empty": "No research yet in this project.",

  "run.topic": "Topic",
  "run.topicPlaceholder": "What should be researched?",
  "run.language": "Report language",
  "run.model": "Model",
  "run.search": "Search provider",
  "run.start": "Start research",
  "run.again": "Research again",
  "run.againLead": "Adjust the topic or settings. The new Run keeps earlier reports.",
  "run.history": "Runs",
  "run.cancel": "Cancel",
  "run.cancelConfirm": "Stop this Run? Work already done is kept.",
  "run.open": "Read report",
  "run.sources": "{n} sources",
  "run.refunded": "Quota refunded",
  "run.closeSafe": "You can close this page — the research keeps going.",
  "run.browsed": "Read {n} sources",
  "run.perspectives": "Perspectives",
  "run.noOptions": "An Administrator needs to add a model and a search provider first.",

  "lang.th": "Thai",
  "lang.en": "English",

  "status.queued": "Waiting",
  "status.needs_selection": "Needs a new model or provider",
  "status.running": "Researching",
  "status.cancelling": "Stopping",
  "status.succeeded": "Done",
  "status.failed": "Failed",
  "status.cancelled": "Cancelled",
  "status.interrupted": "Interrupted",

  "stage.research": "Researching sources",
  "stage.outline": "Planning the outline",
  "stage.article": "Writing",
  "stage.polish": "Polishing",
  "stage.normalize": "Preparing the report",

  "reason.retries_exhausted": "A service kept failing after retrying.",
  "reason.bad_configuration": "The model or search settings do not work. An Administrator needs to check them.",
  "reason.interrupted": "The worker stopped while this was running.",
  "reason.timed_out": "It ran past the time limit.",
  "reason.empty_report": "The research found nothing to write about.",
  "reason.refused": "The model declined this topic.",
  "reason.engine_error": "Something went wrong inside the research engine.",

  "report.contents": "Contents",
  "report.sources": "Sources",
  "report.export": "Export",
  "report.withEvidence": "Attach evidence",
  "report.evidence": "Evidence",
  "report.excerpt": "Excerpts the system actually used — not the full original.",
  "report.noEvidence": "No evidence was recorded for this source.",
  "report.openSource": "Open the original",

  "admin.users": "Users",
  "admin.models": "Models",
  "admin.search": "Search providers",
  "admin.limits": "Limits",
  "admin.newUser": "New user",
  "admin.role": "Role",
  "admin.role.user": "User",
  "admin.role.admin": "Administrator",
  "admin.active": "Active",
  "admin.hasPassword": "Password set",
  "admin.link": "Set-password link",
  "admin.linkLead": "Send this link to {email}. It works once and expires in 24 hours.",
  "admin.newLink": "New link",
  "admin.resetConfirm": "Reset this password? The user is signed out and must set a new password from the link.",
  "admin.keys": "API keys",
  "admin.keyHint": "Stored key {hint}",
  "admin.noKey": "No key",
  "admin.apiKey": "API key",
  "admin.apiBase": "Base URL",
  "admin.label": "Label",
  "admin.provider": "Provider",
  "admin.modelId": "Model id",
  "admin.reasoning": "Reasoning",
  "admin.reasoningHelp": "Empty, off, effort:minimal, effort:low, budget:800",
  "admin.maxTokens": "Reply budget (talk / write)",
  "admin.enabled": "Offered",
  "admin.default": "Default",
  "admin.addModel": "Add model",
  "admin.addSearch": "Add search provider",
  "admin.kind": "Kind",
  "admin.endpoint": "Endpoint",
  "admin.engines": "SearXNG engines",
  "admin.limit.total": "Runs at once, whole system",
  "admin.limit.perUser": "Runs at once, per user",
  "admin.limit.queued": "Waiting Runs, per user",
  "admin.limit.quota": "Runs per month, per user",
  "admin.limit.deadline": "Longest a Run may take (minutes)",
  "admin.saved": "Saved",

  "error.generic": "Something went wrong. Try again.",
  "error.email_taken": "That email already has an account.",
  "error.no_default_configured": "No default model or search provider is set up yet.",
  "error.choice_not_available": "That model or provider is no longer offered.",
  "error.weak_password": "Use at least 10 characters.",
  "error.bootstrap_code_wrong": "That setup code is not right.",
  "error.setup_done": "Setup has already been done.",
  "error.cannot_demote_self": "You cannot remove your own administrator access.",
};

type Key = keyof typeof en;

const th: Record<Key, string> = {
  app: "lit-storm",
  signIn: "เข้าสู่ระบบ",
  signOut: "ออกจากระบบ",
  email: "อีเมล",
  password: "รหัสผ่าน",
  name: "ชื่อ",
  save: "บันทึก",
  cancel: "ยกเลิก",
  create: "สร้าง",
  loading: "กำลังโหลด…",
  back: "กลับ",
  copy: "คัดลอก",
  copied: "คัดลอกแล้ว",
  close: "ปิด",
  edit: "แก้ไข",
  yes: "ใช่",
  no: "ไม่",

  "setup.title": "ตั้งค่า lit-storm",
  "setup.lead": "สร้างผู้ดูแลระบบคนแรก ต้องใช้รหัสตั้งต้นที่ผู้ติดตั้งกำหนดไว้ใน Docker secret",
  "setup.code": "รหัสตั้งต้น",
  "setup.submit": "สร้างผู้ดูแลระบบ",
  "setup.noCode": "ยังไม่ได้กำหนดรหัสตั้งต้น ให้เพิ่ม LITSTORM_BOOTSTRAP_CODE_FILE ให้ service api แล้ว restart",

  "login.title": "เข้าสู่ระบบ lit-storm",
  "login.failed": "อีเมลหรือรหัสผ่านไม่ถูกต้อง",

  "pw.title": "ตั้งรหัสผ่าน",
  "pw.lead": "สำหรับ {email} อย่างน้อย 10 ตัวอักษร",
  "pw.invalid": "ลิงก์นี้หมดอายุหรือถูกใช้ไปแล้ว ขอลิงก์ใหม่จากผู้ดูแลระบบ",
  "pw.submit": "ตั้งรหัสผ่าน",
  "pw.weak": "ใช้อย่างน้อย 10 ตัวอักษร",

  "nav.projects": "โปรเจกต์",
  "nav.admin": "ดูแลระบบ",

  "projects.title": "โปรเจกต์",
  "projects.new": "โปรเจกต์ใหม่",
  "projects.namePlaceholder": "เช่น ทบทวนวรรณกรรมวิทยานิพนธ์",
  "projects.empty": "ยังไม่มีโปรเจกต์ สร้างโปรเจกต์เพื่อเริ่มทำวิจัย",

  "project.sessions": "หัวข้อวิจัย",
  "project.newSession": "วิจัยหัวข้อใหม่",
  "project.empty": "ยังไม่มีงานวิจัยในโปรเจกต์นี้",

  "run.topic": "หัวข้อ",
  "run.topicPlaceholder": "ต้องการค้นคว้าเรื่องอะไร",
  "run.language": "ภาษารายงาน",
  "run.model": "โมเดล",
  "run.search": "บริการค้นหา",
  "run.start": "เริ่มค้นคว้า",
  "run.again": "ค้นคว้าอีกครั้ง",
  "run.againLead": "ปรับหัวข้อหรือค่าที่ใช้ได้ รายงานจากรอบก่อนยังเก็บไว้",
  "run.history": "รอบการค้นคว้า",
  "run.cancel": "ยกเลิก",
  "run.cancelConfirm": "หยุดรอบนี้ไหม ผลที่ทำเสร็จแล้วจะยังเก็บไว้",
  "run.open": "อ่านรายงาน",
  "run.sources": "{n} แหล่งอ้างอิง",
  "run.refunded": "คืนโควตาแล้ว",
  "run.closeSafe": "ปิดหน้านี้ได้ การค้นคว้ายังทำต่อ",
  "run.browsed": "อ่านแล้ว {n} แหล่ง",
  "run.perspectives": "มุมมอง",
  "run.noOptions": "ผู้ดูแลระบบต้องเพิ่มโมเดลและบริการค้นหาก่อน",

  "lang.th": "ไทย",
  "lang.en": "อังกฤษ",

  "status.queued": "รอคิว",
  "status.needs_selection": "ต้องเลือกโมเดลหรือบริการใหม่",
  "status.running": "กำลังค้นคว้า",
  "status.cancelling": "กำลังหยุด",
  "status.succeeded": "เสร็จแล้ว",
  "status.failed": "ล้มเหลว",
  "status.cancelled": "ยกเลิกแล้ว",
  "status.interrupted": "ถูกขัดจังหวะ",

  "stage.research": "ค้นคว้าแหล่งข้อมูล",
  "stage.outline": "วางโครงร่าง",
  "stage.article": "เขียนรายงาน",
  "stage.polish": "ขัดเกลา",
  "stage.normalize": "จัดเตรียมรายงาน",

  "reason.retries_exhausted": "บริการภายนอกล้มเหลวซ้ำหลังลองใหม่แล้ว",
  "reason.bad_configuration": "การตั้งค่าโมเดลหรือบริการค้นหาใช้งานไม่ได้ ผู้ดูแลระบบต้องตรวจสอบ",
  "reason.interrupted": "ระบบประมวลผลหยุดทำงานระหว่างรอบนี้",
  "reason.timed_out": "ใช้เวลาเกินกำหนด",
  "reason.empty_report": "ค้นคว้าแล้วไม่พบเนื้อหาที่จะเขียนรายงาน",
  "reason.refused": "โมเดลปฏิเสธหัวข้อนี้",
  "reason.engine_error": "เกิดข้อผิดพลาดภายในระบบค้นคว้า",

  "report.contents": "สารบัญ",
  "report.sources": "แหล่งอ้างอิง",
  "report.export": "ดาวน์โหลด",
  "report.withEvidence": "แนบหลักฐาน",
  "report.evidence": "ข้อความหลักฐาน",
  "report.excerpt": "ข้อความบางส่วนที่ระบบใช้จริง ไม่ใช่ต้นฉบับเต็ม",
  "report.noEvidence": "ระบบไม่ได้บันทึกข้อความหลักฐานของแหล่งนี้",
  "report.openSource": "เปิดเว็บไซต์ต้นทาง",

  "admin.users": "ผู้ใช้",
  "admin.models": "โมเดล",
  "admin.search": "บริการค้นหา",
  "admin.limits": "ขีดจำกัด",
  "admin.newUser": "ผู้ใช้ใหม่",
  "admin.role": "บทบาท",
  "admin.role.user": "ผู้ใช้",
  "admin.role.admin": "ผู้ดูแลระบบ",
  "admin.active": "ใช้งานได้",
  "admin.hasPassword": "ตั้งรหัสผ่านแล้ว",
  "admin.link": "ลิงก์ตั้งรหัสผ่าน",
  "admin.linkLead": "ส่งลิงก์นี้ให้ {email} ใช้ได้ครั้งเดียวและหมดอายุใน 24 ชั่วโมง",
  "admin.newLink": "ออกลิงก์ใหม่",
  "admin.resetConfirm": "รีเซ็ตรหัสผ่านไหม ผู้ใช้จะถูกออกจากระบบและต้องตั้งรหัสใหม่จากลิงก์",
  "admin.keys": "API key",
  "admin.keyHint": "key ที่บันทึกไว้ {hint}",
  "admin.noKey": "ยังไม่มี key",
  "admin.apiKey": "API key",
  "admin.apiBase": "Base URL",
  "admin.label": "ชื่อที่แสดง",
  "admin.provider": "ผู้ให้บริการ",
  "admin.modelId": "รหัสโมเดล",
  "admin.reasoning": "การคิด (reasoning)",
  "admin.reasoningHelp": "เว้นว่าง, off, effort:minimal, effort:low, budget:800",
  "admin.maxTokens": "งบคำตอบ (สนทนา / เขียน)",
  "admin.enabled": "เปิดให้เลือก",
  "admin.default": "ค่าเริ่มต้น",
  "admin.addModel": "เพิ่มโมเดล",
  "admin.addSearch": "เพิ่มบริการค้นหา",
  "admin.kind": "ชนิด",
  "admin.endpoint": "Endpoint",
  "admin.engines": "engine ของ SearXNG",
  "admin.limit.total": "Run พร้อมกันทั้งระบบ",
  "admin.limit.perUser": "Run พร้อมกันต่อผู้ใช้",
  "admin.limit.queued": "Run ที่รอคิวต่อผู้ใช้",
  "admin.limit.quota": "Run ต่อเดือนต่อผู้ใช้",
  "admin.limit.deadline": "เวลาสูงสุดต่อ Run (นาที)",
  "admin.saved": "บันทึกแล้ว",

  "error.generic": "เกิดข้อผิดพลาด ลองอีกครั้ง",
  "error.email_taken": "อีเมลนี้มีบัญชีอยู่แล้ว",
  "error.no_default_configured": "ยังไม่ได้ตั้งโมเดลหรือบริการค้นหาเริ่มต้น",
  "error.choice_not_available": "โมเดลหรือบริการนี้ไม่เปิดให้เลือกแล้ว",
  "error.weak_password": "ใช้อย่างน้อย 10 ตัวอักษร",
  "error.bootstrap_code_wrong": "รหัสตั้งต้นไม่ถูกต้อง",
  "error.setup_done": "ตั้งค่าครั้งแรกไปแล้ว",
  "error.cannot_demote_self": "ถอดสิทธิ์ผู้ดูแลของตัวเองไม่ได้",
};

const dictionaries: Record<Lang, Record<Key, string>> = { en, th };

type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (key: Key, vars?: Record<string, string | number>) => string };

const I18n = createContext<Ctx | null>(null);

function initial(): Lang {
  try {
    const saved = localStorage.getItem("litstorm.lang");
    if (saved === "th" || saved === "en") return saved;
  } catch {
    /* storage may be blocked */
  }
  return navigator.language.startsWith("th") ? "th" : "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initial);
  const setLang = (l: Lang) => {
    setLangState(l);
    document.documentElement.lang = l;
    try {
      localStorage.setItem("litstorm.lang", l);
    } catch {
      /* ignore */
    }
  };
  const t = (key: Key, vars?: Record<string, string | number>) => {
    let text = dictionaries[lang][key] ?? key;
    for (const [k, v] of Object.entries(vars ?? {})) text = text.replace(`{${k}}`, String(v));
    return text;
  };
  return <I18n.Provider value={{ lang, setLang, t }}>{children}</I18n.Provider>;
}

export function useT() {
  const ctx = useContext(I18n);
  if (!ctx) throw new Error("I18nProvider missing");
  return ctx;
}

// For codes that come back from the API ("error.email_taken", "status.running").
export function has(key: string): key is Key {
  return key in en;
}
