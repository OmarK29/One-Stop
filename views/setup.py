"""Setup (desktop only): connect the Google Sheet, get the phone secrets, quit."""
from __future__ import annotations

import json
import os
import signal
import threading

import streamlit as st

import store


def page(connected: bool, error: str | None = None) -> None:
    st.subheader("Setup")
    if error:
        st.error(error)
    cfg = store.load_local_config()
    key = store.load_local_key()

    if connected and key and cfg.get("sheet_url"):
        st.success(f"Connected to [your sheet]({cfg['sheet_url']}).", icon=":material/check_circle:")
        _phone_setup(cfg["sheet_url"], key)
        with st.expander("Connect a different sheet or key"):
            _connect_form(key)
        _quit()
        return

    st.markdown("**1.** Make a new, empty Google Sheet (any name, e.g. *One Stop*).")
    _connect_form(key)
    _quit()


def _connect_form(existing_key: dict | None) -> None:
    crm_key = None
    if store.CRM_KEY_FILE.exists():
        try:
            crm_key = json.loads(store.CRM_KEY_FILE.read_text())
        except (OSError, ValueError):
            crm_key = None
    key = existing_key or crm_key
    if key:
        st.markdown(f"**2.** In the sheet, click **Share** and add this address as an **Editor**:")
        st.code(key.get("client_email", ""), language=None)
        source = "your CRM" if key is crm_key and not existing_key else "your saved key"
        st.caption(f"Using the Google key from {source}. Upload a different one below if you want.")
    else:
        st.markdown("**2.** Upload your Google service-account key (the `.json` file). The address inside it "
                    "then needs to be added to the sheet as an **Editor**.")
    upload = st.file_uploader("Service-account key (.json)", type=["json"], key="key_upload")
    url = st.text_input("**3.** Paste the sheet's link", value=store.load_local_config().get("sheet_url", ""),
                        placeholder="https://docs.google.com/spreadsheets/d/…")
    if st.button("Connect", type="primary", icon=":material/link:"):
        try:
            info = json.loads(upload.getvalue()) if upload else key
            if not info:
                raise store.SetupError("Upload your service-account key first.")
            store.check_key(info)
            ss = store.open_spreadsheet(info, url)
            created = store.Store(ss).ensure_tabs()
            store.save_local_config(url.strip(), info)
            st.cache_resource.clear()
            st.toast("Connected" + (f". Created {', '.join(created)}" if created else ""), icon="✅")
            st.rerun()
        except (store.SetupError, ValueError) as e:
            st.error(str(e))


def _phone_setup(sheet_url: str, key: dict) -> None:
    with st.expander("Put it on your phone", expanded=False):
        st.markdown(
            "1. Push this folder to a **private** GitHub repo.\n"
            "2. Go to **share.streamlit.io** → **Create app** → pick the repo, branch `main`, file `app.py`.\n"
            "3. Open **Advanced settings → Secrets**, paste the block below, then **Deploy**.\n"
            "4. On the app, click **Share** and invite your Gmail. Only invited people can open it.\n"
            "5. On your phone, open the link in Safari → Share → **Add to Home Screen**.")
        st.code(store.secrets_toml(sheet_url, key), language="toml")
        st.caption("This block works like a password to your sheet. Paste it only into Streamlit's Secrets box.")


def _quit() -> None:
    st.divider()
    if st.button("Quit One Stop", icon=":material/power_settings_new:", type="tertiary"):
        st.info("One Stop has stopped. You can close this tab.")
        threading.Timer(0.5, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
