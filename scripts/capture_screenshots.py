"""Capture real screenshots of the running Streamlit app (for report/slides).

    streamlit run app.py --server.port 8501 --server.headless true   # terminal 1
    python scripts/capture_screenshots.py --url http://localhost:8501  # terminal 2

Each page is selected through the sidebar exactly as a user would click it.
Images are written to outputs/screenshots/.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "screenshots"

PAGES = [
    ("Overview", "01_overview", None),
    ("Directory", "02_directory", None),
    ("Faculty profile", "03_profile", None),
    ("Department analytics", "04_departments", None),
    ("Research & text analytics", "05_text_analytics", None),
    ("Faculty discovery", "06_discovery", "machine learning for healthcare"),
    ("Data & methodology", "07_methodology", None),
]


def wait_idle(page, extra: float = 2.5) -> None:
    """Wait until Streamlit stops showing its 'running' indicator."""
    for _ in range(120):
        if page.locator('[data-testid="stStatusWidget"]').count() == 0:
            break
        time.sleep(0.5)
    time.sleep(extra)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8501")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": args.width, "height": args.height}, device_scale_factor=1.5)
        page.goto(args.url, wait_until="networkidle")
        wait_idle(page, 5)
        for label, fname, query in PAGES:
            page.locator('[data-testid="stSidebar"] label').filter(has_text=label).first.click()
            wait_idle(page)
            if query:
                box = page.get_by_label("Research interest")
                box.fill(query)
                box.press("Enter")
                wait_idle(page)
            page.screenshot(path=str(OUT / f"{fname}.png"))
            print("saved", fname)
        # an extra view: directory filtered to one school
        page.locator('[data-testid="stSidebar"] label').filter(has_text="Department analytics").first.click()
        wait_idle(page)
        page.get_by_role("tab", name="Data completeness").click()
        wait_idle(page, 2)
        page.screenshot(path=str(OUT / "08_completeness.png"))
        page.locator('[data-testid="stSidebar"] label').filter(has_text="Research & text analytics").first.click()
        wait_idle(page)
        page.get_by_role("tab", name="Co-occurrence network").click()
        wait_idle(page, 3)
        page.screenshot(path=str(OUT / "09_network.png"))
        page.get_by_role("tab", name="Topics (NMF)").click()
        wait_idle(page, 3)
        page.screenshot(path=str(OUT / "10_topics.png"))
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
