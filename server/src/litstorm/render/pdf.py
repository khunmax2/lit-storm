"""report.json as PDF, printed from the HTML export by Chromium.

Chromium breaks Thai lines at word boundaries (ICU), which is why it is used
rather than a CSS-to-PDF library (docs/adr/0005). The page names Thai fonts
first; the machine that prints must have one installed — the Worker image
installs Noto Sans Thai.

LITSTORM_PDF_BROWSER_CHANNEL picks an installed browser instead of
Playwright's own Chromium (for example "msedge" on a Windows laptop).
"""

import os

from litstorm.render import html as html_render


def render(report, path, with_evidence=False):
    from playwright.sync_api import sync_playwright

    page_html = html_render.render(report, with_evidence=with_evidence, expanded=True)
    channel = os.environ.get("LITSTORM_PDF_BROWSER_CHANNEL") or None
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=channel)
        try:
            page = browser.new_page()
            # Nothing on the page needs the network; refuse it outright.
            page.route("**/*", lambda route: route.abort())
            page.set_content(page_html, wait_until="load")
            page.emulate_media(media="print")
            page.pdf(
                path=path,
                format="A4",
                print_background=True,
                margin={"top": "18mm", "bottom": "18mm", "left": "16mm", "right": "16mm"},
            )
        finally:
            browser.close()
    return path
