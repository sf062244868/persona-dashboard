"""
persona_dashboard.py — Persona Generation Interface
===================================================

順流式版面 + 投影片風格(對齊 chatbot_pipeline_slide.html):
  頂部   兩種方法的 pipeline(卡片式)+ 使用教學 + 模式切換
  中段   貼上文章 / 載入範例 → 建立 Persona → 暫存 / 載入
  下方   左 = 對話測試,右 = CCD 歸類檔

後端在 persona_core.py。cluster/全文之後接你們的研究方法只改 persona_core。

執行:  streamlit run persona_dashboard.py
需求:  .env(本地)或 Streamlit secrets(雲端)內含 OPENAI_API_KEY
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


# ===========================================================================
# 樣式(對齊投影片配色)
# ===========================================================================
st.markdown("""
<style>
  section.main h2, section.main h3 { color:#0f766e; }
  /* pipeline 卡片 */
  .pp-wrap{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:2px 0 6px;}
  .pp-panel{border:1px solid #d7dee5;border-radius:10px;padding:12px 14px;background:#fff;}
  .pp-panel.a{border-color:#7fc9bf;background:#f3fbf9;}
  .pp-panel.b{border-color:#9bb4ea;background:#f5f8ff;}
  .pp-title{font-size:14px;font-weight:700;margin:0 0 8px;color:#1f2933;}
  .pp-title .tag{font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;margin-right:6px;color:#fff;}
  .pp-title.a .tag{background:#0f766e;} .pp-title.b .tag{background:#1d4ed8;}
  .pp-flow{display:flex;align-items:stretch;gap:4px;}
  .pp-node{flex:1 1 0;min-width:0;border-radius:9px;padding:8px 6px;text-align:center;border:1.5px solid;
           display:flex;flex-direction:column;justify-content:center;gap:2px;}
  .pp-node b{font-size:12px;color:#1f2933;} .pp-node small{font-size:10px;color:#5b6b7a;line-height:1.2;}
  .pp-node.post{background:#fdebcf;border-color:#e9b873;}
  .pp-node.ccd{background:#d6f0ec;border-color:#7fc9bf;}
  .pp-node.persona{background:#eef3ff;border-color:#9bb4ea;}
  .pp-node.chat{background:#e6ebf1;border-color:#aab7c4;}
  .pp-arrow{display:flex;align-items:center;justify-content:center;font-size:16px;color:#90a0ad;font-weight:700;min-width:14px;}
  .pp-cap{font-size:11px;color:#5b6b7a;margin-top:6px;display:block;}
</style>
""", unsafe_allow_html=True)

PIPELINE_HTML = """
<div class="pp-wrap">
  <div class="pp-panel a">
    <div class="pp-title a"><span class="tag">A</span>Post-CCD-Chatbox</div>
    <div class="pp-flow">
      <div class="pp-node post"><b>Post</b><small>原始貼文</small></div><div class="pp-arrow">→</div>
      <div class="pp-node ccd"><b>CCD</b><small>8 段概念化</small></div><div class="pp-arrow">→</div>
      <div class="pp-node persona"><b>Persona</b><small>以 CCD 建</small></div><div class="pp-arrow">→</div>
      <div class="pp-node chat"><b>Chatbox</b><small>對話</small></div>
    </div>
    <span class="pp-cap">先把貼文轉成 8 段 CCD,再以 CCD 建立 persona。</span>
  </div>
  <div class="pp-panel b">
    <div class="pp-title b"><span class="tag">B</span>Direct Post-Chatbox</div>
    <div class="pp-flow">
      <div class="pp-node post"><b>Post</b><small>原始貼文</small></div><div class="pp-arrow">→</div>
      <div class="pp-node persona"><b>Persona</b><small>直接用 post</small></div><div class="pp-arrow">→</div>
      <div class="pp-node chat"><b>Chatbox</b><small>對話</small></div>
    </div>
    <span class="pp-cap">跳過 CCD,直接以原始 post 建立 persona。</span>
  </div>
</div>
"""


# ===========================================================================
# session state
# ===========================================================================
_defaults = {
    "persona_ready": False,
    "built_mode": None,
    "built_post": "",
    "basis": None,
    "ccd": None,
    "ccd_path": None,
    "messages": [],
    "chat_history": [],
    "saved": [],          # 暫存的 persona 清單
}
for k, v in _defaults.items():
    st.session_state.setdefault(k, v)


def invalidate_persona():
    st.session_state.persona_ready = False
    st.session_state.built_mode = None
    st.session_state.basis = None
    st.session_state.ccd = None
    st.session_state.ccd_path = None
    st.session_state.messages = []
    st.session_state.chat_history = []


# --- callbacks(在 rerun 前執行,可安全寫 widget 的 session_state)----------
def load_sample():
    st.session_state.post_input = core.load_post_text(17)


def save_persona():
    name = (st.session_state.get("save_name") or "").strip()
    if not name:
        excerpt = (st.session_state.built_post or "").strip().replace("\n", " ")[:20]
        name = f"{st.session_state.basis} · {excerpt}…"
    st.session_state.saved.append({
        "label": name,
        "mode": st.session_state.built_mode,
        "basis": st.session_state.basis,
        "ccd": st.session_state.ccd,
        "ccd_path": st.session_state.ccd_path,
        "built_post": st.session_state.built_post,
        "messages": list(st.session_state.messages),
        "chat_history": list(st.session_state.chat_history),
    })
    st.session_state.save_name = ""


def load_persona():
    i = st.session_state.get("load_idx", 0)
    if i is None or i >= len(st.session_state.saved):
        return
    s = st.session_state.saved[i]
    st.session_state.mode_radio = s["mode"]      # 同步模式,避免被「模式變了」判定清掉
    st.session_state.built_mode = s["mode"]
    st.session_state.built_post = s.get("built_post", "")
    st.session_state.persona_ready = True
    st.session_state.basis = s["basis"]
    st.session_state.ccd = s["ccd"]
    st.session_state.ccd_path = s["ccd_path"]
    st.session_state.messages = list(s["messages"])
    st.session_state.chat_history = list(s["chat_history"])


# ===========================================================================
# 頂部:標題 + pipeline + 教學 + 模式
# ===========================================================================
st.title("Persona Generation Interface")
st.markdown(PIPELINE_HTML, unsafe_allow_html=True)

with st.expander("📖 使用教學(第一次先看這裡)", expanded=not st.session_state.persona_ready):
    st.markdown("""
**這個工具在做什麼**:把一段自述 / 貼文變成「可對話的 persona」,並比較兩種生成方式的差別。

**操作步驟**
1. 選 **模式**:**A = Post-CCD-Chatbox**(先轉成 8 段 CCD 再建 persona)/ **B = Direct Post-Chatbox**(直接用原文建)。
2. **貼上文章**,或按 **「載入範例貼文」** 帶入一篇示範貼文。
3. 按 **「建立 / 重建 Persona」**。
4. 在下方 **對話測試** 跟 persona 聊天;A 模式可在右側看到 **8 段 CCD 歸類檔**。
5. 想保留目前這個 persona → 按 **「💾 暫存此 Persona」**,之後可在「已暫存」清單 **載回**(本次連線有效)。
""")

mode = st.radio(
    "模式切換",
    [core.MODE_CCD, core.MODE_DIRECT],
    horizontal=True,
    key="mode_radio",
    help="A:先產生 CCD 再建 persona。B:直接用 post 建 persona。",
)

st.divider()

# ===========================================================================
# 中段:貼上文章 → 建立 → 暫存 / 載入
# ===========================================================================
st.subheader("貼上文章 (post)")
post_text = st.text_area(
    "貼上文章",
    key="post_input",
    height=190,
    placeholder="從任何地方把一段貼文 / 自述貼進來…",
    label_visibility="collapsed",
)

b1, b2 = st.columns([1, 1])
with b1:
    st.button("📄 載入範例貼文", on_click=load_sample, use_container_width=True)
with b2:
    build = st.button("✨ 建立 / 重建 Persona", type="primary", use_container_width=True)

# 模式變了 → 目前 persona 過期,提示重建
if st.session_state.persona_ready and st.session_state.built_mode != mode:
    invalidate_persona()

if build:
    if not post_text.strip():
        st.warning("請先貼上文章,或按「載入範例貼文」。")
    else:
        with st.spinner("建立 CCD…" if mode == core.MODE_CCD else "建立 persona…"):
            res = core.build_persona(mode, post_text)
        st.session_state.persona_ready = True
        st.session_state.built_mode = mode
        st.session_state.built_post = post_text
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

# --- Persona 暫存 / 載入 ---------------------------------------------------
if st.session_state.persona_ready:
    s1, s2 = st.columns([3, 1])
    with s1:
        st.text_input("暫存名稱", key="save_name",
                      placeholder="幫這個 persona 取個名字(可留空自動命名)",
                      label_visibility="collapsed")
    with s2:
        st.button("💾 暫存此 Persona", on_click=save_persona, use_container_width=True)

if st.session_state.saved:
    labels = [s["label"] for s in st.session_state.saved]
    l1, l2 = st.columns([3, 1])
    with l1:
        st.selectbox("已暫存的 Persona", range(len(labels)),
                     format_func=lambda i: f"{labels[i]}  ({st.session_state.saved[i]['mode']})",
                     key="load_idx", label_visibility="collapsed")
    with l2:
        st.button("📂 載入", on_click=load_persona, use_container_width=True)
    st.caption(f"已暫存 {len(labels)} 個 persona(本次連線有效,重新整理會清空)。")

st.divider()

# ===========================================================================
# 下方:左 對話 / 右 CCD
# ===========================================================================
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
        if st.session_state.ccd_path:
            st.caption(f"📄 {st.session_state.ccd_path}")
        st.text(st.session_state.ccd)
    elif st.session_state.basis == "Post":
        st.info("Direct 模式不經過 CCD,因此沒有 CCD 歸類檔。")
    else:
        st.caption("建立 persona(A 模式)後,這裡會顯示 8 段 CCD 歸類檔。")
