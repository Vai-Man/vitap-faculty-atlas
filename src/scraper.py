"""Collection stage: capture the official VIT-AP faculty directory.

How the site works (verified 17 Oct 2026)
-----------------------------------------
``https://vitap.ac.in/allfaculty`` is a Next.js (React) page. The HTML that
the server returns contains only navigation chrome; the faculty cards are
rendered in the browser after the page's own JavaScript downloads records
from a Strapi CMS (``cms.vitap.ac.in/api/faculty-profiles``, 100 per page)
and merges a small list of records that is bundled into the page script
(the SBST school). A plain Requests + BeautifulSoup fetch therefore sees no
faculty at all, so this module uses Playwright to render the page.

Two capture paths are combined:

1. **Rendered page state** (primary). After rendering, the list the page is
   displaying is read from the React component state. This contains the API
   records *and* the bundled SBST records, i.e. exactly what a visitor sees.
2. **Network responses** (cross-check). Every CMS response the page itself
   receives is recorded, so the API-sourced count can be compared with (1).

We never call the CMS directly and never handle any access token: we only
observe what the public page loads. Personal phone numbers (``Contact_No``)
are dropped at capture time.

The browser snapshot workflow used to build the shipped dataset is the same
JavaScript (``REACT_STATE_JS``) executed in a desktop browser; see
``docs/methodology.md``.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from . import config

log = logging.getLogger(__name__)

# JavaScript executed inside the rendered directory page. It walks up the
# React fibre tree from the first faculty link and returns the largest array
# of faculty objects held in component state (the page's full list).
REACT_STATE_JS = r"""
() => {
  const links = [...document.querySelectorAll('a[href*="/faculty/"]')];
  if (!links.length) return null;
  const el = links[0];
  const key = Object.keys(el).find(k => k.startsWith('__reactFiber'));
  if (!key) return null;
  let f = el[key], best = null;
  while (f) {
    let h = f.memoizedState, n = 0;
    while (h && n < 60) {
      const v = h.memoizedState;
      if (Array.isArray(v) && v.length > 50 && v[0] && typeof v[0] === 'object'
          && ('Employee_Id' in v[0])) {
        if (!best || v.length > best.length) best = v;
      }
      h = h.next; n++;
    }
    f = f.return;
  }
  if (!best) return null;
  return best.map(o => {
    const c = Object.assign({}, o);
    delete c.Contact_No;                      // privacy: no phone numbers
    const p = o.Photo && o.Photo.data;
    c.Photo = p ? (p.attributes ? p.attributes.url : (p.url || null)) : null;
    return c;
  });
}
"""

FIRST_PAGE_LINKS_JS = r"""
() => [...document.querySelectorAll('a[href*="/faculty/"]')].map(a => a.getAttribute('href'))
"""


# ---------------------------------------------------------------- HTTP helpers
def fetch_with_retry(
    url: str,
    *,
    session: requests.Session | None = None,
    retries: int = 3,
    backoff: float = 2.0,
    timeout: float = 20.0,
    method: str = "GET",
    sleep: Callable[[float], None] = time.sleep,
) -> requests.Response | None:
    """GET/HEAD ``url`` with exponential back-off.

    Returns the response, or ``None`` if every attempt failed (network error
    or HTTP status >= 500). 4xx responses are returned immediately because
    retrying will not change them. Failures are logged, never raised, so a
    single bad URL cannot stop the pipeline.
    """
    sess = session or requests.Session()
    headers = {"User-Agent": config.USER_AGENT}
    for attempt in range(1, retries + 1):
        try:
            resp = sess.request(method, url, headers=headers, timeout=timeout,
                                allow_redirects=True)
            if resp.status_code < 500:
                return resp
            log.warning("HTTP %s for %s (attempt %d/%d)", resp.status_code, url,
                        attempt, retries)
        except requests.RequestException as exc:
            log.warning("Request failed for %s (attempt %d/%d): %s", url, attempt,
                        retries, exc)
        if attempt < retries:
            sleep(backoff ** attempt)
    log.error("Giving up on %s after %d attempts", url, retries)
    return None


def robots_allows(url: str, robots_url: str = config.ROBOTS_URL,
                  robots_text: str | None = None) -> bool:
    """Return True if robots.txt permits a generic crawler to fetch ``url``.

    ``robots_text`` can be supplied (tests, offline use). If robots.txt
    cannot be fetched we log it and return True, which is the standard
    interpretation of an unreachable robots file.
    """
    rp = urllib.robotparser.RobotFileParser()
    if robots_text is None:
        resp = fetch_with_retry(robots_url, retries=2)
        if resp is None or resp.status_code != 200:
            log.warning("robots.txt unavailable; proceeding cautiously")
            return True
        robots_text = resp.text
    rp.parse(robots_text.splitlines())
    return rp.can_fetch("*", url)


# ---------------------------------------------------------------- capture
def capture_directory(headless: bool = True, timeout_s: int = 90) -> dict[str, Any]:
    """Render the official directory with Playwright and return a snapshot.

    Raises ``RuntimeError`` if the page cannot be rendered or no records are
    found, so the caller can fall back to an existing snapshot.
    """
    if not robots_allows(config.DIRECTORY_URL):
        raise RuntimeError("robots.txt disallows the faculty directory")

    from playwright.sync_api import sync_playwright  # local import: optional dep

    api_pages: list[dict[str, Any]] = []
    failures: list[str] = []

    def on_response(resp):  # noqa: ANN001 - Playwright type
        if config.CMS_ENDPOINT_PATTERN in resp.url:
            try:
                body = resp.json()
                data = body.get("data") if isinstance(body, dict) else None
                api_pages.append({
                    "url": resp.url,
                    "status": resp.status,
                    "records": len(data) if isinstance(data, list) else 0,
                    "meta": body.get("meta") if isinstance(body, dict) else None,
                })
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{resp.url}: {exc}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=config.USER_AGENT)
        page.on("response", on_response)
        log.info("Opening %s", config.DIRECTORY_URL)
        page.goto(config.DIRECTORY_URL, wait_until="domcontentloaded",
                  timeout=timeout_s * 1000)
        records = None
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            records = page.evaluate(REACT_STATE_JS)
            if records:
                # wait until the list stops growing (all CMS pages merged)
                time.sleep(3)
                again = page.evaluate(REACT_STATE_JS)
                if again and len(again) == len(records):
                    break
                records = again
            time.sleep(1)
        links = page.evaluate(FIRST_PAGE_LINKS_JS)
        browser.close()

    if not records:
        raise RuntimeError("No faculty records found in rendered page")

    api_total = sum(pg["records"] for pg in api_pages)
    log.info("Captured %d records (%d from %d CMS responses)", len(records),
             api_total, len(api_pages))
    return build_snapshot(records, links, method="playwright", api_pages=api_pages,
                          failures=failures)


def build_snapshot(records: list[dict], first_page_links: list[str] | None = None,
                   *, method: str, api_pages: list[dict] | None = None,
                   failures: list[str] | None = None) -> dict[str, Any]:
    """Wrap captured records with provenance metadata."""
    return {
        "source_page": config.DIRECTORY_URL,
        "api_endpoint": "https://" + config.CMS_ENDPOINT_PATTERN
                        + "?populate=*&sort=Employee_Id:ASC&pagination[page]=N&pagination[pageSize]=100",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "capture_method": method,
        "first_page_links": first_page_links or [],
        "api_pages": api_pages or [],
        "capture_failures": failures or [],
        "record_count": len(records),
        "records": records,
    }


def save_snapshot(snapshot: dict[str, Any], path: Path = config.RAW_SNAPSHOT) -> Path:
    """Write a raw snapshot (unchanged records + metadata) to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Saved raw snapshot -> %s", path)
    return path


def load_snapshot(path: Path = config.RAW_SNAPSHOT) -> dict[str, Any]:
    """Load a raw snapshot and check its basic shape."""
    snap = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(snap, dict) or not isinstance(snap.get("records"), list):
        raise ValueError(f"{path} is not a valid faculty snapshot")
    for rec in snap["records"]:
        rec.pop("Contact_No", None)  # enforce privacy rule on any snapshot
    return snap
