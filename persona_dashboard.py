"""
persona_dashboard.py — Persona Generation Interface
===================================================

順流式版面 + 投影片風格,並支援 A·B 並排對照、回覆計時、對話匯出。

  頂部   兩種方法 pipeline(卡片,建完收合)+ 使用教學 + 模式(A / B / A·B 並排)
  中段   貼上文章 / 載入範例 → 建立 → 暫存 / 載入 / 清空 / 匯出 / 看原文
  下方   對話測試(並排模式時兩欄)+ CCD 歸類檔

後端在 persona_core.py。cluster/全文之後接你們的研究方法只改 persona_core。

執行:  streamlit run persona_dashboard.py
需求:  .env(本地)或 Streamlit secrets(雲端)內含 OPENAI_API_KEY
"""

import os
from datetime import datetime

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


_key = _secret("OPENAI_API_KEY")
if _key:
    os.environ["OPENAI_API_KEY"] = str(_key).strip()


def _check_password() -> bool:
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

import persona_core as core  # noqa: E402

# 三種檢視模式 → 要建立的 run keys('A'=Method A/CCD,'B'=Method B/Direct)
VIEW_A = "Method A(Post-CCD)"
VIEW_B = "Method B(Direct)"
VIEW_AB = "A·B 並排對照"
VIEW_KEYS = {VIEW_A: ["A"], VIEW_B: ["B"], VIEW_AB: ["A", "B"]}
KEY_MODE = {"A": core.MODE_CCD, "B": core.MODE_DIRECT}
KEY_LABEL = {"A": "Method A · 經 CCD", "B": "Method B · 直接 post"}


# ===========================================================================
# 樣式(對齊投影片配色)
# ===========================================================================
st.markdown("""
<style>
  section.main h2, section.main h3 { color:#0f766e; }
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
    "runs": {},            # {'A': run, 'B': run};run = mode/system/basis/ccd/ccd_path/build_secs/messages/chat_history
    "built_post": "",
    "built_view": None,
    "saved": [],
}
for k, v in _defaults.items():
    st.session_state.setdefault(k, v)


def has_persona() -> bool:
    return bool(st.session_state.runs)


# --- callbacks -------------------------------------------------------------
def load_sample():
    st.session_state.post_input = core.load_post_text(17)


def clear_chat():
    for run in st.session_state.runs.values():
        run["messages"] = [run["messages"][0]] if run["messages"] else []
        run["chat_history"] = []


def save_persona():
    name = (st.session_state.get("save_name") or "").strip()
    if not name:
        excerpt = (st.session_state.built_post or "").strip().replace("\n", " ")[:20]
        name = f"{st.session_state.built_view} · {excerpt}…"
    # 深拷貝 runs(messages / chat_history 是 list)
    snap_runs = {}
    for kk, run in st.session_state.runs.items():
        snap_runs[kk] = {**run, "messages": list(run["messages"]), "chat_history": list(run["chat_history"])}
    st.session_state.saved.append({
        "label": name,
        "view": st.session_state.built_view,
        "built_post": st.session_state.built_post,
        "runs": snap_runs,
    })
    st.session_state.save_name = ""


def load_persona():
    i = st.session_state.get("load_idx", 0)
    if i is None or i >= len(st.session_state.saved):
        return
    s = st.session_state.saved[i]
    st.session_state.view_radio = s["view"]
    st.session_state.built_view = s["view"]
    st.session_state.built_post = s["built_post"]
    st.session_state.runs = {kk: {**run, "messages": list(run["messages"]),
                                  "chat_history": list(run["chat_history"])}
                             for kk, run in s["runs"].items()}


def build_export_text() -> str:
    lines = ["Persona Chat Export",
             f"時間:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
             f"檢視模式:{st.session_state.built_view}",
             "",
             "===== 原文 (post) =====",
             st.session_state.built_post or "(無)",
             ""]
    for kk, run in st.session_state.runs.items():
        lines.append(f"===== {KEY_LABEL[kk]}(建立 {run['build_secs']:.1f}s) =====")
        if run.get("ccd"):
            lines += ["[CCD 歸類檔]", run["ccd"], ""]
        lines.append("[對話]")
        for role, text, lat in run["chat_history"]:
            who = "You" if role == "you" else "Persona"
            tag = f" (⏱ {lat:.1f}s)" if lat else ""
            lines.append(f"{who}{tag}: {text}")
        lines.append("")
    return "\n".join(lines)


def render_transcript(run):
    for role, text, lat in run["chat_history"]:
        with st.chat_message("user" if role == "you" else "assistant"):
            st.write(text)
            if role != "you" and lat:
                st.caption(f"⏱ {lat:.1f}s")


# ===========================================================================
# 頂部:標題 + pipeline + 教學 + 模式
# ===========================================================================
st.title("Persona Generation Interface")

with st.expander("方法 Pipeline(A / B 流程)", expanded=not has_persona()):
    st.markdown(PIPELINE_HTML, unsafe_allow_html=True)

with st.expander("📖 使用教學(第一次先看這裡)", expanded=not has_persona()):
    st.markdown("""
**這個工具在做什麼**:把一段自述 / 貼文變成「可對話的 persona」,並比較兩種生成方式的差別。

**操作步驟**
1. 選 **模式**:**Method A**(先轉成 8 段 CCD 再建)/ **Method B**(直接用原文建)/ **A·B 並排對照**(同時建兩個、左右對照)。
2. **貼上文章**,或按 **「載入範例貼文」**。
3. 按 **「建立 / 重建 Persona」**。
4. 在下方 **對話測試** 跟 persona 聊天;每則回覆會顯示 **⏱ 花費時間**。並排模式下,同一句話會同時送給 A 和 B。
5. 想保留 → **「💾 暫存」**;想存證據 → **「⬇️ 匯出對話 (.txt)」**。
""")

view = st.radio(
    "模式",
    [VIEW_A, VIEW_B, VIEW_AB],
    horizontal=True,
    key="view_radio",
    help="A:先產 CCD 再建。B:直接用 post。A·B:同時建兩個並排對照。",
)

st.divider()

# ===========================================================================
# 中段:貼上文章 → 建立 → 暫存 / 載入 / 清空 / 匯出
# ===========================================================================
st.subheader("貼上文章 (post)")
post_text = st.text_area(
    "貼上文章",
    key="post_input",
    height=180,
    placeholder="從任何地方把一段貼文 / 自述貼進來…",
    label_visibility="collapsed",
)

b1, b2 = st.columns([1, 1])
with b1:
    st.button("📄 載入範例貼文", on_click=load_sample, use_container_width=True)
with b2:
    build = st.button("✨ 建立 / 重建 Persona", type="primary", use_container_width=True)

# 模式變了 → 目前 persona 過期
if has_persona() and st.session_state.built_view != view:
    st.session_state.runs = {}

if build:
    if not post_text.strip():
        st.warning("請先貼上文章,或按「載入範例貼文」。")
    else:
        runs = {}
        ok = True
        for kk in VIEW_KEYS[view]:
            mode = KEY_MODE[kk]
            try:
                with st.spinner(f"建立 {KEY_LABEL[kk]}…"):
                    res = core.build_persona(mode, post_text)
            except Exception as e:
                st.error(f"建立 {KEY_LABEL[kk]} 失敗:{type(e).__name__} — 請稍後再試。")
                ok = False
                break
            runs[kk] = {
                "mode": mode, "system": res["system"], "basis": res["basis"],
                "ccd": res["ccd"], "ccd_path": res["ccd_path"], "build_secs": res["build_secs"],
                "messages": [{"role": "system", "content": res["system"]}],
                "chat_history": [],
            }
        if ok:
            st.session_state.runs = runs
            st.session_state.built_post = post_text
            st.session_state.built_view = view
            st.rerun()

if has_persona():
    secs = " · ".join(f"{KEY_LABEL[kk]} {run['build_secs']:.1f}s" for kk, run in st.session_state.runs.items())
    st.success(f"Persona 已就緒 · {st.session_state.built_view} · 建立耗時:{secs}")
else:
    st.info("貼上文章、選好模式後,按「建立 / 重建 Persona」。")

# --- 工具列:暫存 / 清空 / 匯出 / 看原文 ----------------------------------
if has_persona():
    t1, t2, t3 = st.columns([2, 1, 1])
    with t1:
        st.text_input("暫存名稱", key="save_name",
                      placeholder="幫這個 persona 取名(可留空自動命名)",
                      label_visibility="collapsed")
    with t2:
        st.button("💾 暫存", on_click=save_persona, use_container_width=True)
    with t3:
        st.button("🧹 清空對話", on_click=clear_chat, use_container_width=True)

    st.download_button(
        "⬇️ 匯出對話 (.txt)",
        data=build_export_text(),
        file_name=f"persona_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain",
        use_container_width=True,
    )
    with st.expander("建立依據的原文 (post)"):
        st.text(st.session_state.built_post)

if st.session_state.saved:
    labels = [s["label"] for s in st.session_state.saved]
    l1, l2 = st.columns([3, 1])
    with l1:
        st.selectbox("已暫存的 Persona", range(len(labels)),
                     format_func=lambda i: f"{labels[i]}  ({st.session_state.saved[i]['view']})",
                     key="load_idx", label_visibility="collapsed")
    with l2:
        st.button("📂 載入", on_click=load_persona, use_container_width=True)
    st.caption(f"已暫存 {len(labels)} 個(本次連線有效,重新整理會清空)。")

st.divider()

# ===========================================================================
# 下方:對話測試(並排模式兩欄)+ CCD
# ===========================================================================
st.subheader("對話測試")
runs = st.session_state.runs
keys = list(runs.keys())

if not has_persona():
    st.info("先建立 persona。")
elif len(keys) == 2:
    c = st.columns(2)
    for col, kk in zip(c, keys):
        with col:
            st.markdown(f"**{KEY_LABEL[kk]}**")
            render_transcript(runs[kk])
else:
    render_transcript(runs[keys[0]])

user_input = st.chat_input(
    "說點什麼(並排模式會同時送給 A 和 B)…" if has_persona() else "請先建立 persona",
    disabled=not has_persona(),
)
if user_input:
    for kk, run in runs.items():
        run["messages"].append({"role": "user", "content": user_input})
        try:
            reply, info = core.chat_once(run["messages"])
            lat = info["latency"]
        except Exception as e:
            reply, lat = f"(發生錯誤:{type(e).__name__},請稍後再試)", None
        run["messages"].append({"role": "assistant", "content": reply})
        run["chat_history"].append(("you", user_input, None))
        run["chat_history"].append(("persona", reply, lat))
    st.rerun()

# --- CCD 歸類檔 ------------------------------------------------------------
if has_persona():
    st.divider()
    st.subheader("CCD 歸類檔 (8 段)")
    a_run = runs.get("A")
    if a_run and a_run.get("ccd"):
        if a_run.get("ccd_path"):
            st.caption(f"📄 {a_run['ccd_path']}")
        st.text(a_run["ccd"])
    else:
        st.info("目前檢視不含 Method A(CCD),因此沒有 CCD 歸類檔。")
