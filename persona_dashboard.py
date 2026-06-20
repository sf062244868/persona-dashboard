"""
persona_dashboard.py — Persona Generation Interface
===================================================

Top-down layout + slide styling, with A·B side-by-side comparison,
per-reply timing, and chat export.

  Top     Two method pipelines (cards, collapse after build) + tutorial + mode (A / B / A·B)
  Middle  Paste post / load sample -> Build -> Save / Load / Clear / Export / view source
  Bottom  Chat test (two columns in side-by-side mode) + CCD profile

Backend lives in persona_core.py. To plug in your own clustering / post source later,
only change load_clusters() / load_post_text() there.

Run:    streamlit run persona_dashboard.py
Needs:  OPENAI_API_KEY in .env (local) or Streamlit secrets (cloud)
"""

import os
from datetime import datetime

import streamlit as st

st.set_page_config(page_title="Persona Generation Interface", layout="wide")


def _secret(key, default=None):
    """Read Streamlit secrets first (cloud), then environment variables (local .env)."""
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
    pw = st.text_input("Enter access password", type="password")
    if pw:
        if pw == str(app_pw):
            st.session_state.auth_ok = True
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()


_check_password()

import persona_core as core  # noqa: E402

# Three view modes -> run keys to build ('A' = Method A/CCD, 'B' = Method B/Direct)
VIEW_A = "Method A (Post-CCD)"
VIEW_B = "Method B (Direct)"
VIEW_AB = "A·B Side-by-side"
VIEW_KEYS = {VIEW_A: ["A"], VIEW_B: ["B"], VIEW_AB: ["A", "B"]}
KEY_MODE = {"A": core.MODE_CCD, "B": core.MODE_DIRECT}
KEY_LABEL = {"A": "Method A · via CCD", "B": "Method B · direct post"}


# ===========================================================================
# Styling (matches the slide palette)
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
      <div class="pp-node post"><b>Post</b><small>raw post</small></div><div class="pp-arrow">→</div>
      <div class="pp-node ccd"><b>CCD</b><small>8-section</small></div><div class="pp-arrow">→</div>
      <div class="pp-node persona"><b>Persona</b><small>from CCD</small></div><div class="pp-arrow">→</div>
      <div class="pp-node chat"><b>Chatbox</b><small>chat</small></div>
    </div>
    <span class="pp-cap">Turn the post into an 8-section CCD, then build the persona from the CCD.</span>
  </div>
  <div class="pp-panel b">
    <div class="pp-title b"><span class="tag">B</span>Direct Post-Chatbox</div>
    <div class="pp-flow">
      <div class="pp-node post"><b>Post</b><small>raw post</small></div><div class="pp-arrow">→</div>
      <div class="pp-node persona"><b>Persona</b><small>from post</small></div><div class="pp-arrow">→</div>
      <div class="pp-node chat"><b>Chatbox</b><small>chat</small></div>
    </div>
    <span class="pp-cap">Skip the CCD; build the persona directly from the raw post.</span>
  </div>
</div>
"""


# ===========================================================================
# session state
# ===========================================================================
_defaults = {
    "runs": {},            # {'A': run, 'B': run}; run = mode/system/basis/ccd/ccd_path/build_secs/messages/chat_history
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
             f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
             f"View: {st.session_state.built_view}",
             "",
             "===== Source post =====",
             st.session_state.built_post or "(none)",
             ""]
    for kk, run in st.session_state.runs.items():
        lines.append(f"===== {KEY_LABEL[kk]} (build {run['build_secs']:.1f}s) =====")
        if run.get("ccd"):
            lines += ["[CCD profile]", run["ccd"], ""]
        lines.append("[Chat]")
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
# Top: title + pipeline + tutorial + mode
# ===========================================================================
st.title("Persona Generation Interface")

with st.expander("Method Pipeline (A / B flow)", expanded=not has_persona()):
    st.markdown(PIPELINE_HTML, unsafe_allow_html=True)

with st.expander("📖 How to use (read this first)", expanded=not has_persona()):
    st.markdown("""
**What this tool does**: turns a post / self-description into a *chattable persona*, and lets you compare two ways of generating it.

**Steps**
1. Pick a **mode**: **Method A** (turn it into an 8-section CCD first) / **Method B** (build directly from the raw text) / **A·B Side-by-side** (build both and compare).
2. **Paste a post**, or click **"Load sample post"**.
3. Click **"Build / Rebuild Persona"**.
4. Chat with the persona in **Chat test** below; each reply shows its **⏱ response time**. In side-by-side mode, the same message goes to both A and B.
5. Want to keep it → **"💾 Save"**; want a record → **"⬇️ Export chat (.txt)"**.
""")

view = st.radio(
    "Mode",
    [VIEW_A, VIEW_B, VIEW_AB],
    horizontal=True,
    key="view_radio",
    help="A: build a CCD first, then the persona. B: build directly from the post. A·B: build both and compare.",
)

st.divider()

# ===========================================================================
# Middle: paste post -> build -> save / load / clear / export
# ===========================================================================
st.subheader("Paste a post")
post_text = st.text_area(
    "Paste a post",
    key="post_input",
    height=180,
    placeholder="Paste any post / self-description here…",
    label_visibility="collapsed",
)

b1, b2 = st.columns([1, 1])
with b1:
    st.button("📄 Load sample post", on_click=load_sample, use_container_width=True)
with b2:
    build = st.button("✨ Build / Rebuild Persona", type="primary", use_container_width=True)

# Mode changed -> current persona is stale
if has_persona() and st.session_state.built_view != view:
    st.session_state.runs = {}

if build:
    if not post_text.strip():
        st.warning("Paste a post first, or click \"Load sample post\".")
    else:
        runs = {}
        ok = True
        for kk in VIEW_KEYS[view]:
            mode = KEY_MODE[kk]
            try:
                with st.spinner(f"Building {KEY_LABEL[kk]}…"):
                    res = core.build_persona(mode, post_text)
            except Exception as e:
                st.error(f"Failed to build {KEY_LABEL[kk]}: {type(e).__name__} — please try again.")
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
    st.success(f"Persona ready · {st.session_state.built_view} · build time: {secs}")
else:
    st.info("Paste a post, pick a mode, then click \"Build / Rebuild Persona\".")

# --- toolbar: save / clear / export / view source ------------------------
if has_persona():
    t1, t2, t3 = st.columns([2, 1, 1])
    with t1:
        st.text_input("Save name", key="save_name",
                      placeholder="Name this persona (leave blank to auto-name)",
                      label_visibility="collapsed")
    with t2:
        st.button("💾 Save", on_click=save_persona, use_container_width=True)
    with t3:
        st.button("🧹 Clear chat", on_click=clear_chat, use_container_width=True)

    st.download_button(
        "⬇️ Export chat (.txt)",
        data=build_export_text(),
        file_name=f"persona_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain",
        use_container_width=True,
    )
    with st.expander("Source post used"):
        st.text(st.session_state.built_post)

if st.session_state.saved:
    labels = [s["label"] for s in st.session_state.saved]
    l1, l2 = st.columns([3, 1])
    with l1:
        st.selectbox("Saved personas", range(len(labels)),
                     format_func=lambda i: f"{labels[i]}  ({st.session_state.saved[i]['view']})",
                     key="load_idx", label_visibility="collapsed")
    with l2:
        st.button("📂 Load", on_click=load_persona, use_container_width=True)
    st.caption(f"{len(labels)} saved (this session only; a refresh clears them).")

st.divider()

# ===========================================================================
# Bottom: chat test (two columns in side-by-side mode) + CCD
# ===========================================================================
st.subheader("Chat test")
runs = st.session_state.runs
keys = list(runs.keys())

if not has_persona():
    st.info("Build a persona first.")
elif len(keys) == 2:
    c = st.columns(2)
    for col, kk in zip(c, keys):
        with col:
            st.markdown(f"**{KEY_LABEL[kk]}**")
            render_transcript(runs[kk])
else:
    render_transcript(runs[keys[0]])

user_input = st.chat_input(
    "Say something (side-by-side sends to both A and B)…" if has_persona() else "Build a persona first",
    disabled=not has_persona(),
)
if user_input:
    for kk, run in runs.items():
        run["messages"].append({"role": "user", "content": user_input})
        try:
            reply, info = core.chat_once(run["messages"])
            lat = info["latency"]
        except Exception as e:
            reply, lat = f"(Error: {type(e).__name__}, please try again)", None
        run["messages"].append({"role": "assistant", "content": reply})
        run["chat_history"].append(("you", user_input, None))
        run["chat_history"].append(("persona", reply, lat))
    st.rerun()

# --- CCD profile -----------------------------------------------------------
if has_persona():
    st.divider()
    st.subheader("CCD profile (8 sections)")
    a_run = runs.get("A")
    if a_run and a_run.get("ccd"):
        if a_run.get("ccd_path"):
            st.caption(f"📄 {a_run['ccd_path']}")
        st.text(a_run["ccd"])
    else:
        st.info("The current view has no Method A (CCD), so there's no CCD profile.")
