"""report.json as PDF, printed from the HTML export by Chromium.

Chromium breaks Thai lines at word boundaries (ICU), which is why it is used
rather than a CSS-to-PDF library (docs/adr/0005). The page names Thai fonts
first; the machine that prints must have one installed — the Worker image
installs Noto Sans Thai.

LITSTORM_PDF_BROWSER_CHANNEL picks an installed browser instead of
Playwright's own Chromium (for example "msedge" on a Windows laptop).
"""

import html
import os

from litstorm.render import html as html_render

# Every page but none of the text: the report's title and where the reader is.
# Chromium draws it outside the page's own styles, so the fonts are named here.
_FOOTER = (
    '<div style="width:100%;padding:0 16mm;display:flex;justify-content:space-between;gap:8mm;'
    "font-size:7.5px;color:#8a8f98;font-family:'Noto Sans Thai','Noto Sans',sans-serif;\">"
    '<span style="overflow:hidden;white-space:nowrap;text-overflow:ellipsis">{title}</span>'
    '<span style="white-space:nowrap"><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
)


def render(report, path, with_evidence=False, engine_label="", finished_at=None):
    from playwright.sync_api import sync_playwright

    page_html = html_render.render(
        report, with_evidence=with_evidence, expanded=True, engine_label=engine_label, finished_at=finished_at
    )
    channel = os.environ.get("LITSTORM_PDF_BROWSER_CHANNEL") or None
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=channel)
        try:
            page = browser.new_page()
            # Nothing on the page needs the network; refuse it outright.
            page.route("**/*", lambda route: route.abort())
            page.set_content(page_html, wait_until="load")
            # The faces travel as data: URLs and load only once text asks for
            # them, after "load": printing sooner prints the fallback faces.
            page.evaluate("document.fonts.ready.then(() => document.fonts.size)")
            page.emulate_media(media="print")
            page.pdf(
                path=path,
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template="<span></span>",
                footer_template=_FOOTER.format(title=html.escape(report["title"])),
                margin={"top": "18mm", "bottom": "20mm", "left": "16mm", "right": "16mm"},
            )
        finally:
            browser.close()
    return path
