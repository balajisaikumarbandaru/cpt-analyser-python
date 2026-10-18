import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


def test_app_runs_on_demo_data():
    at = AppTest.from_file("../app/streamlit_app.py", default_timeout=90).run()
    assert not at.exception
    sounding = next(s for s in at.selectbox if s.label == "Sounding")
    sounding.select("DEMO-01 D1 @5 m").run()
    assert not at.exception and at.json
