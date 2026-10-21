"""Headless smoke test: every Streamlit page renders without an exception,
and the directory search/filter actually narrows results."""
import pytest

from src import config

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

needs_data = pytest.mark.skipif(not config.FACULTY_JSON.exists(), reason="run the pipeline first")
APP = str(config.ROOT / "app.py")
PAGES = ["Overview", "Directory", "Faculty profile", "Department analytics",
         "Research & text analytics", "Faculty discovery", "Data & methodology"]


@needs_data
@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, at.exception


@needs_data
def test_directory_search_filters():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.sidebar.radio[0].set_value("Directory").run()
    before = [m.value for m in at.markdown if "profiles match" in m.value][0]
    at.text_input(key="dir_q").set_value("Kumar").run()
    after = [m.value for m in at.markdown if "profiles match" in m.value][0]
    assert before.startswith("**609**") or "of" in before
    assert after != before and not at.exception


@needs_data
def test_discovery_returns_results():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.sidebar.radio[0].set_value("Faculty discovery").run()
    at.text_input(key="disc_q").set_value("graph theory").run()
    assert not at.exception
    assert any("Matched terms" in m.value for m in at.markdown)
