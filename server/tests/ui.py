"""The web app's screens, as steps the browser scripts share.

Every selector the scripts use lives here, so a change to the screens is
fixed in one place. Written against the Thai interface (the scripts open
the browser with locale th-TH and the accounts they make default to Thai).

Not a test module: pytest collects only test_*.py.
"""

import re

from playwright.sync_api import expect

FINAL_BADGE = re.compile("เสร็จแล้ว|ล้มเหลว|ถูกขัดจังหวะ|ยกเลิกแล้ว")


# --- signing in -------------------------------------------------------------------


def setup(page, base, code, name, email, password):
    """The first-run page: the installer's code and the first Administrator."""
    page.goto(base)
    page.wait_for_url(re.compile(r"/setup"))
    page.locator("#code").fill(code)
    page.locator("#name").fill(name)
    page.locator("#email").fill(email)
    page.locator("#password").fill(password)
    page.get_by_role("button", name="สร้างผู้ดูแลระบบ").click()
    page.wait_for_url(re.compile(r"/settings/"))


def login(page, base, email, password):
    page.goto(f"{base}/login")
    page.locator("#email").fill(email)
    page.locator("#password").fill(password)
    page.get_by_role("button", name="เข้าสู่ระบบ").click()
    page.wait_for_url(re.compile(r"/$"))


def csrf(page):
    return next(c["value"] for c in page.context.cookies() if c["name"] == "litstorm_csrf")


# --- research ---------------------------------------------------------------------------


def start_research(page, topic):
    """Type a topic in the composer on the page that is open and start it.
    From the home page the topic is filed in no Project; from a Project's
    page, in that Project."""
    page.get_by_placeholder(re.compile("พิมพ์หัวข้อ")).fill(topic)
    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r"/sessions/"))
    return page.url.rstrip("/").split("/")[-1]


def new_project(page, base, name):
    """Make a Project from the Projects page; ends on the Project's page."""
    page.goto(f"{base}/projects")
    page.get_by_role("button", name="โปรเจกต์ใหม่").first.click()
    dialog = page.get_by_role("dialog")
    dialog.locator("#project-name").fill(name)
    dialog.get_by_role("button", name="สร้าง").click()
    page.wait_for_url(re.compile(r"/projects/[0-9a-f-]+$"))
    return page.url.rstrip("/").split("/")[-1]


def delete_project(page, base, project_id):
    page.goto(f"{base}/projects/{project_id}")
    page.get_by_role("button", name="เพิ่มเติม").first.click()
    page.get_by_role("menuitem", name="ลบโปรเจกต์").click()
    page.get_by_role("alertdialog").get_by_role("button", name="ใช่").click()
    page.wait_for_url(re.compile(r"/projects$"))


def run_badge(page):
    """The latest Run's status on a topic's page, once it is final."""
    return page.locator("main").get_by_text(FINAL_BADGE).first


def cancel_latest(page):
    page.get_by_role("button", name="ยกเลิก").first.click()
    page.get_by_role("alertdialog").get_by_role("button", name="ใช่").click()


def open_report(page):
    """From a topic's page, the latest report."""
    page.get_by_role("link", name="อ่านรายงาน").first.click()
    page.wait_for_url(re.compile(r"/runs/"))
    expect(page.locator("article h1")).to_be_visible()


def open_citation(page):
    """Click the first citation; returns the panel beside the report."""
    page.locator("button.cite").first.click()
    panel = page.get_by_role("dialog")
    expect(panel).to_be_visible()
    return panel


def trash_row(page, base, title):
    page.goto(f"{base}/trash")
    return page.locator("tbody tr", has_text=title)


# --- settings --------------------------------------------------------------------------


def _switch(dialog, label):
    """A switch row in a settings dialog, by its label."""
    return dialog.locator("label", has_text=label).get_by_role("switch")


def add_model(page, base, label, model, reasoning="", talk="", write="", default=False):
    """Add a model for a provider whose key is already stored (OpenRouter)."""
    page.goto(f"{base}/settings/models")
    page.get_by_role("button", name="เพิ่มโมเดล").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("radio", name=re.compile("OpenRouter")).click()
    dialog.locator("#m-model").fill(model)
    dialog.locator("#m-label").fill(label)
    if reasoning or talk or write:
        dialog.get_by_role("button", name=re.compile("ตั้งค่าขั้นสูง")).click()
        dialog.locator("#m-reasoning").fill(reasoning)
        dialog.locator("#m-talk").fill(talk)
        dialog.locator("#m-write").fill(write)
    if default:
        _switch(dialog, "ค่าเริ่มต้น").click()
    dialog.get_by_role("button", name="บันทึก").click()
    expect(dialog).to_have_count(0)
    expect(page.get_by_text(model)).to_be_visible()


def add_search(page, base, kind="arXiv", default=True):
    page.goto(f"{base}/settings/search")
    page.get_by_role("button", name="เพิ่มบริการค้นหา").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("radio", name=re.compile(kind)).click()
    if default:
        _switch(dialog, "ค่าเริ่มต้น").click()
    dialog.get_by_role("button", name="บันทึก").click()
    expect(dialog).to_have_count(0)


def new_user(page, base, email, name):
    """Returns the one-time link the dialog shows."""
    page.goto(f"{base}/settings/users")
    page.get_by_role("button", name="ผู้ใช้ใหม่").click()
    dialog = page.get_by_role("dialog")
    dialog.locator("#u-email").fill(email)
    dialog.locator("#u-name").fill(name)
    dialog.get_by_role("button", name="สร้าง").click()
    link = dialog.locator("input[readonly]")
    expect(link).to_have_value(re.compile(r"/set-password#"))
    value = link.input_value()
    dialog.get_by_role("button", name="เสร็จ").click()
    return value


def test_button_toast(page):
    """Click a table's first test button; returns the toast it raises, which
    says how long the call took whether it passed or not."""
    page.get_by_role("button", name="ทดสอบ").first.click()
    toast = page.locator("[data-sonner-toast]").first
    expect(toast).to_contain_text(re.compile(r"[\d.]+s"), timeout=60_000)
    return toast
