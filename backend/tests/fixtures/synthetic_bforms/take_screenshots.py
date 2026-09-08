"""Batch-render every synthetic B-form HTML fixture to PNG via Playwright."""
from pathlib import Path
from playwright.sync_api import sync_playwright


FIXTURES = Path(r"C:\Users\KHADIJAH\Desktop\casefill-ai-v2\backend\tests\fixtures\synthetic_bforms")


def main() -> None:
    htmls = sorted(FIXTURES.glob("test_*.html"))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        for html in htmls:
            page.goto(html.as_uri(), wait_until="networkidle")
            out = FIXTURES / f"{html.stem}.png"
            page.screenshot(path=str(out), full_page=True)
            print(f"wrote {out.name}")
        browser.close()


if __name__ == "__main__":
    main()
