"""One Stop: track physical, mental and spiritual habits in a Google Sheet,
and get walked to the one thing worth doing next."""
from __future__ import annotations

import hmac
import json
from pathlib import Path

import streamlit as st

import logic
import store
from views import edit, guide, progress, setup, today
from views.common import Ctx

CSS = """
<style>
.stButton button { min-height: 2.9rem; }
.stButton button[kind="tertiary"] { min-height: 0; }
[data-testid="stMetricValue"] { font-size: 1.5rem; }
.hero-xp { font-size: 3.4rem; font-weight: 700; line-height: 1.1; margin: .2rem 0 .4rem; }
.hero-xp span { font-size: 1.2rem; font-weight: 500; opacity: .65; }
[data-testid="stExpander"] summary p { font-weight: 600; }
[data-testid="stHeaderActionElements"] { display: none; }
[data-testid="stMainBlockContainer"] { padding-top: 3.2rem; padding-bottom: 3rem; }
.stat-line { font-size: 1.05rem; margin: -.4rem 0 .8rem; }
.stat-line b { font-size: 1.25rem; }
</style>
"""


def _secrets() -> dict:
    try:
        return dict(st.secrets)
    except Exception:  # no secrets file: running on the desktop
        return {}


@st.cache_resource(show_spinner="Opening your sheet…")
def _store(key_json: str, sheet_url: str) -> store.Store:
    s = store.Store(store.open_spreadsheet(json.loads(key_json), sheet_url))
    s.ensure_tabs()
    return s


def _password_gate(secrets: dict) -> None:
    """Optional extra lock for the hosted app: set app_password in Secrets."""
    pw = str(secrets.get("app_password", "") or "")
    if not pw or st.session_state.get("authed"):
        return
    entered = st.text_input("Password", type="password")
    if entered and hmac.compare_digest(entered, pw):
        st.session_state.authed = True
        st.rerun()
    if entered:
        st.error("That's not it.")
    st.stop()


def main() -> None:
    st.set_page_config(page_title="One Stop", page_icon=str(Path(__file__).parent / "assets" / "icon.png"), layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)
    secrets = _secrets()
    cloud = "gcp_service_account" in secrets
    _password_gate(secrets)

    if cloud:
        key_info, sheet_url = dict(secrets["gcp_service_account"]), str(secrets.get("sheet_url", ""))
    else:
        key_info, sheet_url = store.load_local_key(), store.load_local_config().get("sheet_url", "")

    error = None
    s = None
    if key_info and sheet_url:
        try:
            s = _store(json.dumps(key_info, sort_keys=True), sheet_url)
        except store.SetupError as e:
            error = str(e)

    if s is None:
        if cloud:
            st.error(error or "Add sheet_url to the app's Secrets.")
            st.stop()
        nav = st.navigation([st.Page(lambda: setup.page(False, error), title="Setup", icon=":material/settings:",
                                     url_path="setup", default=True)], position="hidden")
        nav.run()
        return

    settings = s.settings()
    ctx = Ctx(store=s, clock=logic.Clock.from_settings(settings), settings=settings, cloud=cloud)
    pages = [
        st.Page(lambda: guide.page(ctx), title="Guide me", icon=":material/explore:", url_path="guide", default=True),
        st.Page(lambda: today.page(ctx), title="Today", icon=":material/checklist:", url_path="today"),
        st.Page(lambda: progress.page(ctx), title="Progress", icon=":material/insights:", url_path="progress"),
        st.Page(lambda: edit.page(ctx), title="Edit", icon=":material/edit_note:", url_path="edit"),
    ]
    if not cloud:
        pages.append(st.Page(lambda: setup.page(True), title="Setup", icon=":material/settings:", url_path="setup"))
    st.navigation(pages, position="top").run()


if __name__ == "__main__":
    main()
