"""
persona_dashboard.py — Persona Generation Interface(二欄 dashboard 版)
=====================================================================

版面(老闆/Ray 選定):
  最上方   兩種方法的 pipeline + 模式切換橫幅(CCD / Direct)
  左欄     PERSONA + CHATBOX:選 post → 建立 persona → 與 persona 對話
  右欄     上 = 文章原文(post);下 = 生成的 CCD 歸類檔(8 段,僅 CCD 模式)

後端在 persona_core.py(prompts / posts / generate_ccd / 對話)。
cluster 分群與 post 全文之後接你們的研究方法 → 只改 persona_core 的
load_clusters() / load_post_text()。

執行:  streamlit run persona_dashboard.py
需求:  .env 內含 OPENAI_API_KEY
"""

import os
import streamlit as st

st.set_page_config(page_title="Persona Generation Interface", layout="wide")


def _secret(key, default=None):
    """先讀 Streamlit secrets(雲端),再讀環境變數(本地 .env)。"""
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


# 雲端密鑰注入:把 secrets 的 OPENAI_API_KEY 放進環境,讓 persona_core 取用。
_key = _secret("OPENAI_API_KEY")
if _key:
    os.environ["OPENAI_API_KEY"] = str(_key).strip()


def _check_password() -> bool:
    """上線保護:設了 APP_PASSWORD 才啟用密碼門檻;本地沒設則直接放行。"""
    app_pw = _secret("APP_PASSWORD")
    if not app_pw:
        return True
    if st.session_state.get("auth_ok"):
        return True
    st.title("Persona Generation Interface")
    pw = st.text_input("請輸入存取密碼", type="password")
    if pw:
        if pw == str(app_pw):
            st.session_state.auth_ok = True
            st.rerun()
        else:
            st.error("密碼錯誤。")
    st.stop()


_check_password()

import persona_core as core  # noqa: E402  (在密鑰注入之後才匯入)

# --- session state ---------------------------------------------------------
_defaults = {
    "persona_ready": False,
    "persona_sig": None,      # (post_id, mode) at build time — 偵測過期
    "basis": None,            # "CCD" / "Post"
    "ccd": None,
    "ccd_path": None,
    "messages": [],           # 含 system prompt 的完整對話
    "chat_history": [],       # [(role, text)] 顯示用
}
for k, v in _defaults.items():
    st.session_state.setdefault(k, v)


def invalidate_persona():
    st.session_state.persona_ready = False
    st.session_state.persona_sig = None
    st.session_state.basis = None
    st.session_state.ccd = None
    st.session_state.ccd_path = None
    st.session_state.messages = []
    st.session_state.chat_history = []


# ===========================================================================
# 最上方:pipeline + 模式切換
# ===========================================================================
st.title("Persona Generation Interface")

pa, pb = st.columns(2)
with pa:
    st.markdown("**Method A — Post-CCD-Chatbox**")
    st.graphviz_chart("""
    digraph A { rankdir=LR; node [shape=box style=rounded fontsize=11];
      "Post" -> "CCD" -> "Persona" -> "Chatbox"; }
    """, use_container_width=True)
with pb:
    st.markdown("**Method B — Direct Post-Chatbox**")
    st.graphviz_chart("""
    digraph B { rankdir=LR; node [shape=box style=rounded fontsize=11];
      "Post" -> "Persona" -> "Chatbox"; }
    """, use_container_width=True)

mode = st.radio(
    "模式切換",
    [core.MODE_CCD, core.MODE_DIRECT],
    horizontal=True,
    help="Post-CCD-Chatbox:先產生 CCD 再建 persona。Direct Post-Chatbox:直接用 post 建 persona。",
)

st.divider()

# ===========================================================================
# 順流式:貼上文章 → 建立 Persona →(下方)左 對話、右 CCD
# ===========================================================================

# --- 貼上文章(整列寬)----------------------------------------------------
st.subheader("貼上文章 (post)")
post_text = st.text_area(
    "貼上文章",
    key="post_input",
    height=200,
    placeholder="從任何地方把一段貼文 / 自述貼進來…",
    label_visibility="collapsed",
)

# 模式變了 → persona 過期,提示重建
if st.session_state.persona_ready and st.session_state.get("built_mode") != mode:
    invalidate_persona()

if st.button("建立 / 重建 Persona", type="primary"):
    if not post_text.strip():
        st.warning("請先貼上文章。")
    else:
        with st.spinner("建立 CCD…" if mode == core.MODE_CCD else "建立 persona…"):
            res = core.build_persona(mode, post_text)
        st.session_state.persona_ready = True
        st.session_state.built_mode = mode
        st.session_state.basis = res["basis"]
        st.session_state.ccd = res["ccd"]
        st.session_state.ccd_path = res["ccd_path"]
        st.session_state.messages = [{"role": "system", "content": res["system"]}]
        st.session_state.chat_history = []
        st.rerun()

if st.session_state.persona_ready:
    st.success(f"Persona 已就緒 · 模式:{mode} · 生成依據:{st.session_state.basis}")
else:
    st.info("貼上文章、選好模式後,按「建立 / 重建 Persona」。")

st.divider()

# --- 下方:左 對話 / 右 CCD ------------------------------------------------
left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader("對話測試")
    for role, msg in st.session_state.chat_history:
        with st.chat_message("user" if role == "you" else "assistant"):
            st.write(msg)

    user_input = st.chat_input(
        "跟這個 persona 說點什麼…" if st.session_state.persona_ready else "請先建立 persona",
        disabled=not st.session_state.persona_ready,
    )
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        reply = core.chat_once(st.session_state.messages)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.chat_history.append(("you", user_input))
        st.session_state.chat_history.append(("persona", reply))
        st.rerun()

with right:
    st.subheader("CCD 歸類檔 (8 段)")
    if st.session_state.persona_ready and st.session_state.basis == "CCD":
        st.caption(f"📄 {st.session_state.ccd_path}")
        st.text(st.session_state.ccd)
    elif st.session_state.basis == "Post":
        st.info("Direct 模式不經過 CCD,因此沒有 CCD 歸類檔。")
    else:
        st.caption("建立 persona(CCD 模式)後,這裡會顯示 8 段 CCD 歸類檔。")
