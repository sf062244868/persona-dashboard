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
# 主區:左 = persona+chat,右 = 原文+CCD
#   先畫右欄(原文 text area),左欄的「建立」按鈕才能讀到當前全文。
# ===========================================================================
left, right = st.columns([3, 2], gap="large")

# --- 右欄:原文 + CCD 歸類檔 ----------------------------------------------
with right:
    st.subheader("文章原文 (post)")
    # 左欄會用到的選擇結果先在這裡準備:用 session 暫存目前選到的 post
    cur_post = st.session_state.get("_cur_post")
    if cur_post is None:
        cur_post = core.POSTS[16]  # 預設 #17 Habit Change(有全文)
    # 原文 text area:key 綁 post id,換 post 自動換內容/記住各自貼上的全文
    post_text = st.text_area(
        "Reddit 全文(找不到時請貼上)",
        value=core.load_post_text(cur_post["id"]),
        key=f"posttext_{cur_post['id']}",
        height=260,
        label_visibility="collapsed",
    )
    st.caption(f"#{cur_post['id']} · {cur_post['title']}")
    st.caption(f"🔗 {cur_post['url']}")

    st.subheader("CCD 歸類檔 (8 段)")
    if st.session_state.persona_ready and st.session_state.basis == "CCD":
        st.caption(f"📄 {st.session_state.ccd_path}")
        st.text(st.session_state.ccd)
    elif st.session_state.basis == "Post":
        st.info("Direct 模式不經過 CCD,因此沒有 CCD 歸類檔。")
    else:
        st.caption("建立 persona(CCD 模式)後,這裡會顯示 8 段 CCD 歸類檔。")

# --- 左欄:選 post + 建立 persona + 對話 ----------------------------------
with left:
    st.subheader("Persona + Chatbox")

    clusters = core.load_clusters()
    cc, pc = st.columns(2)
    with cc:
        cluster_name = st.selectbox("Cluster(分群篩選)", list(clusters.keys()),
                                    index=list(clusters.keys()).index(cur_post["category"]))
    with pc:
        posts_in = clusters[cluster_name]
        ids = [p["id"] for p in posts_in]
        default_idx = ids.index(cur_post["id"]) if cur_post["id"] in ids else 0
        chosen = st.selectbox("Post", posts_in, index=default_idx,
                              format_func=lambda p: f"{'⚠️ ' if p['flagged'] else ''}#{p['id']} · {p['title']}")

    # 換 post → 更新右欄原文 + 讓 persona 過期
    if chosen["id"] != cur_post["id"]:
        st.session_state["_cur_post"] = chosen
        invalidate_persona()
        st.rerun()

    st.caption(f"摘要:{chosen['summary']}")
    if chosen["flagged"]:
        st.error("此 post 標記為危機內容(含自殺意念),依規則排除於 persona 使用。")

    # 模式或 post 變了 → persona 過期
    sig = (chosen["id"], mode)
    if st.session_state.persona_ready and st.session_state.persona_sig != sig:
        invalidate_persona()

    build = st.button("建立 / 重建 Persona", type="primary", disabled=chosen["flagged"])
    if build:
        if not post_text.strip():
            st.warning("請先在右側提供 post 全文。")
        else:
            with st.spinner("建立 CCD…" if mode == core.MODE_CCD else "建立 persona…"):
                res = core.build_persona(mode, post_text)
            st.session_state.persona_ready = True
            st.session_state.persona_sig = sig
            st.session_state.basis = res["basis"]
            st.session_state.ccd = res["ccd"]
            st.session_state.ccd_path = res["ccd_path"]
            st.session_state.messages = [{"role": "system", "content": res["system"]}]
            st.session_state.chat_history = []
            st.rerun()

    # persona 狀態列
    if st.session_state.persona_ready:
        st.success(f"Persona 已就緒 · 模式:{mode} · 生成依據:{st.session_state.basis}")
    else:
        st.info("選好 post 與模式後,按「建立 / 重建 Persona」。")

    # 對話區
    st.markdown("**對話測試**")
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
