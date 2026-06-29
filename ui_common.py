"""
ui_common.py — Streamlit 共用啟動邏輯(金鑰注入 + 密碼)
=====================================================

persona_dashboard.py(Build 工具)與 pages/(Persona Library)共用,避免重複。
"""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Load .env BEFORE any check_password()/ensure_openai_key() so APP_PASSWORD and
# OPENAI_API_KEY from shared/.env are visible at startup (persona_core also loads
# these later, but the password gate runs first).
_HERE = Path(__file__).resolve().parent
load_dotenv(_HERE / ".env")
load_dotenv(_HERE.parent.parent / "shared" / ".env")


def secret(key, default=None):
    """先讀 Streamlit secrets(雲端),再讀環境變數(本地 .env)。"""
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


def ensure_openai_key() -> None:
    """把 OPENAI_API_KEY 從 secrets / 環境注入 os.environ,供 persona_core 用。"""
    k = secret("OPENAI_API_KEY")
    if k:
        os.environ["OPENAI_API_KEY"] = str(k).strip()


def check_password() -> bool:
    """若有設 APP_PASSWORD 就要求輸入;沒設則直接放行。"""
    app_pw = secret("APP_PASSWORD")
    if not app_pw:
        return True
    if st.session_state.get("auth_ok"):
        return True
    st.title("Persona Generation Interface")
    pw = st.text_input("Enter access password", type="password")
    if pw:
        if pw == str(app_pw):
            st.session_state.auth_ok = True
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()
