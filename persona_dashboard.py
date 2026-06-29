"""
persona_dashboard.py — Persona Generation Interface (single page, 3 tabs)
========================================================================

One coherent UI with a top tab bar — every capability is visible at a glance:

  🛠 Build           paste a post -> Method A (CCD) or B (direct) -> persona -> chat
  📚 Persona Library 16 pre-computed personas (personas.json) -> dropdown -> chat (cached)
  🔎 Cluster Search  Felix's ClusterSearch API -> /pick -> existing CCD inference -> display

Backend lives in persona_core.py (LLM/CCD) and cluster_api.py (Felix's API).
Run:   streamlit run persona_dashboard.py
Needs: OPENAI_API_KEY (.env locally / Streamlit secrets on cloud).
       Cluster Search also needs the ClusterSearch API (default http://localhost:8000).
"""

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Persona Generation Interface", layout="wide")

from ui_common import ensure_openai_key, check_password  # noqa: E402

ensure_openai_key()
check_password()

import persona_core as core   # noqa: E402
import cluster_api            # noqa: E402

HERE = Path(__file__).resolve().parent
PERSONAS_FILE = HERE / "personas.json"
SELECTED_FILE = HERE / "selected_posts.json"

# Two build methods (single-column result; A·B side-by-side removed).
VIEW_A = "Method A (Post-CCD)"
VIEW_B = "Method B (Direct)"
VIEW_KEY = {VIEW_A: "A", VIEW_B: "B"}
KEY_MODE = {"A": core.MODE_CCD, "B": core.MODE_DIRECT}
KEY_LABEL = {"A": "Method A · via CCD", "B": "Method B · direct post"}


# ===========================================================================
# Styling — refined teal theme (aligned with the slide palette)
# ===========================================================================
st.markdown("""
<style>
  /* headings */
  section.main h1 { letter-spacing:.2px; }
  section.main h2, section.main h3 { color:#0f766e; }

  /* top tab bar — make it a clear segmented control */
  div[data-baseweb="tab-list"]{ gap:6px; border-bottom:2px solid #e7edf1; }
  button[data-baseweb="tab"]{
    background:#f4f6f8; border-radius:10px 10px 0 0; padding:8px 18px;
    font-weight:600; color:#5b6b7a;
  }
  button[data-baseweb="tab"][aria-selected="true"]{
    background:#0f766e; color:#fff;
  }
  div[data-baseweb="tab-highlight"]{ background:transparent; }

  /* primary buttons */
  .stButton button[kind="primary"]{ background:#0f766e; border-color:#0f766e; }
  .stButton button[kind="primary"]:hover{ background:#0c5e57; border-color:#0c5e57; }

  /* pipeline diagram cards */
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
  .pp-node .call{font-size:9px;color:#0f766e;font-family:ui-monospace,Menlo,Consolas,monospace;line-height:1.2;margin-top:2px;}
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
      <div class="pp-node post"><b>Post</b><small>raw post</small><small class="call">load_post_text()</small></div><div class="pp-arrow">→</div>
      <div class="pp-node ccd"><b>CCD</b><small>Beck format</small><small class="call">gpt-4o<br>generate_ccd()</small></div><div class="pp-arrow">→</div>
      <div class="pp-node persona"><b>Persona</b><small>from CCD</small><small class="call">build_persona()</small></div><div class="pp-arrow">→</div>
      <div class="pp-node chat"><b>Chatbox</b><small>chat</small><small class="call">gpt-4o<br>chat_once()</small></div>
    </div>
    <span class="pp-cap">Turn the post into a Beck-format CCD, then build the persona from the CCD.</span>
  </div>
  <div class="pp-panel b">
    <div class="pp-title b"><span class="tag">B</span>Direct Post-Chatbox</div>
    <div class="pp-flow">
      <div class="pp-node post"><b>Post</b><small>raw post</small><small class="call">load_post_text()</small></div><div class="pp-arrow">→</div>
      <div class="pp-node persona"><b>Persona</b><small>from post</small><small class="call">build_persona()</small></div><div class="pp-arrow">→</div>
      <div class="pp-node chat"><b>Chatbox</b><small>chat</small><small class="call">gpt-4o<br>chat_once()</small></div>
    </div>
    <span class="pp-cap">Skip the CCD; build the persona directly from the raw post.</span>
  </div>
</div>
"""


# ===========================================================================
# shared helpers
# ===========================================================================
PRICE_IN, PRICE_OUT = 2.50, 10.00


def _cost(prompt_tokens, completion_tokens) -> float:
    return ((prompt_tokens or 0) * PRICE_IN + (completion_tokens or 0) * PRICE_OUT) / 1_000_000


def _meta_chips(info: dict) -> list:
    bits = []
    if info.get("latency"):
        bits.append(f"⏱ {info['latency']:.1f}s")
    if info.get("total_tokens"):
        bits.append(f"🔢 {info['total_tokens']} tok")
        bits.append(f"~${_cost(info.get('prompt_tokens'), info.get('completion_tokens')):.4f}")
    return bits


@st.cache_data
def load_personas() -> list:
    if not PERSONAS_FILE.exists():
        return []
    return json.loads(PERSONAS_FILE.read_text(encoding="utf-8")).get("personas", [])


@st.cache_data
def load_source_posts() -> dict:
    if not SELECTED_FILE.exists():
        return {}
    data = json.loads(SELECTED_FILE.read_text(encoding="utf-8"))
    return {p["post_id"]: p for p in data.get("posts", [])}


# ===========================================================================
# session state (Build tab)
# ===========================================================================
_defaults = {
    "runs": {},               # {'A'|'B': run}
    "built_post": "",
    "built_view": None,
    "saved": [],
    "build_counter": 0,
    "build_ccd_prompt_edit": core.BUILD_CCD_PROMPT,
    "persona_from_ccd_prompt_edit": core.PERSONA_FROM_CCD_PROMPT,
    "persona_from_post_prompt_edit": core.PERSONA_FROM_POST_PROMPT,
}
for k, v in _defaults.items():
    st.session_state.setdefault(k, v)


def has_persona() -> bool:
    return bool(st.session_state.runs)


def load_sample():
    st.session_state.post_input = core.load_post_text(17)


def reset_prompts():
    st.session_state.build_ccd_prompt_edit = core.BUILD_CCD_PROMPT
    st.session_state.persona_from_ccd_prompt_edit = core.PERSONA_FROM_CCD_PROMPT
    st.session_state.persona_from_post_prompt_edit = core.PERSONA_FROM_POST_PROMPT


def clear_chat():
    for run in st.session_state.runs.values():
        run["messages"] = [run["messages"][0]] if run["messages"] else []
        run["chat_history"] = []


def save_persona():
    name = (st.session_state.get("save_name") or "").strip()
    if not name:
        excerpt = (st.session_state.built_post or "").strip().replace("\n", " ")[:20]
        name = f"{st.session_state.built_view} · {excerpt}…"
    snap = {kk: {**run, "messages": list(run["messages"]), "chat_history": list(run["chat_history"])}
            for kk, run in st.session_state.runs.items()}
    st.session_state.saved.append({
        "label": name, "view": st.session_state.built_view,
        "built_post": st.session_state.built_post, "runs": snap,
    })
    st.session_state.save_name = ""


def load_saved_persona():
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
             f"View: {st.session_state.built_view}", "",
             "===== Source post =====", st.session_state.built_post or "(none)", ""]
    for kk, run in st.session_state.runs.items():
        hdr = f"build {run['build_secs']:.1f}s"
        binfo = run.get("build_info")
        if binfo and binfo.get("total_tokens"):
            hdr += f", {binfo['total_tokens']} tok"
        lines.append(f"===== {KEY_LABEL[kk]} ({hdr}) =====")
        if run.get("ccd"):
            lines += ["[CCD profile]", run["ccd"], ""]
        lines.append("[Chat]")
        for role, text, info in run["chat_history"]:
            who = "You" if role == "you" else "Persona"
            lines.append(f"{who}: {text}")
        lines.append("")
    return "\n".join(lines)


def render_transcript(run):
    for role, text, info in run["chat_history"]:
        with st.chat_message("user" if role == "you" else "assistant"):
            st.write(text)
            if role != "you" and info:
                bits = _meta_chips(info)
                if bits:
                    st.caption(" · ".join(bits))


# ===========================================================================
# TAB 1 — Build
# ===========================================================================
def render_build():
    st.caption("Paste any post → pick a method → build a chattable persona. "
               "(A·B side-by-side was removed; A/B are selectable, single-column.)")

    cL, cR = st.columns([5, 4])
    with cL:
        view = st.radio("Mode", [VIEW_A, VIEW_B], key="view_radio", horizontal=True,
                        help="A: build a CCD first, then the persona. B: build directly from the post.")
        st.text_area("Post", key="post_input", height=150,
                      placeholder="Paste any post / self-description here…")
        b1, b2, _ = st.columns([1, 1, 3])
        with b1:
            st.button("📄 Sample", on_click=load_sample, use_container_width=True)
        with b2:
            build = st.button("✨ Build", type="primary", use_container_width=True)
    with cR:
        with st.expander("Method pipeline (A / B) — what each step calls", expanded=not has_persona()):
            st.markdown(PIPELINE_HTML, unsafe_allow_html=True)

    # mode changed -> stale persona
    if has_persona() and st.session_state.built_view != view:
        st.session_state.runs = {}

    if build:
        post_text = st.session_state.get("post_input", "")
        if not post_text.strip():
            st.warning("Paste a post first, or click \"Sample\".")
        else:
            kk = VIEW_KEY[view]
            mode = KEY_MODE[kk]
            try:
                with st.spinner(f"Building {KEY_LABEL[kk]}…"):
                    res = core.build_persona(
                        mode, post_text,
                        ccd_prompt=st.session_state.build_ccd_prompt_edit,
                        persona_prompt=(st.session_state.persona_from_ccd_prompt_edit
                                        if mode == core.MODE_CCD
                                        else st.session_state.persona_from_post_prompt_edit),
                    )
                st.session_state.runs = {kk: {
                    "mode": mode, "system": res["system"], "basis": res["basis"],
                    "ccd": res["ccd"], "ccd_path": res["ccd_path"], "build_secs": res["build_secs"],
                    "build_info": res["info"],
                    "messages": [{"role": "system", "content": res["system"]}],
                    "chat_history": [],
                }}
                st.session_state.built_post = post_text
                st.session_state.built_view = view
                st.session_state.build_counter += 1
                st.rerun()
            except Exception as e:
                st.error(f"Failed to build {KEY_LABEL[kk]}: {type(e).__name__}: {e}")

    # status + persona actions
    if has_persona():
        kk, run = next(iter(st.session_state.runs.items()))
        s = f"Ready · {KEY_LABEL[kk]} · build {run['build_secs']:.1f}s"
        info = run.get("build_info")
        if info and info.get("total_tokens"):
            s += f" · {info['total_tokens']} tok"
        elif info and info.get("cached"):
            s += " · CCD cached"
        st.success(s)
        a1, a2, a3, a4 = st.columns([2, 1, 1, 2])
        with a1:
            st.text_input("Save name", key="save_name", placeholder="Name this persona (blank = auto)",
                          label_visibility="collapsed")
        with a2:
            st.button("💾 Save", on_click=save_persona, use_container_width=True)
        with a3:
            st.button("🧹 Clear", on_click=clear_chat, use_container_width=True)
        with a4:
            st.download_button("⬇️ Export", data=build_export_text(),
                               file_name=f"persona_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                               mime="text/plain", use_container_width=True)
        if st.session_state.saved:
            labels = [s["label"] for s in st.session_state.saved]
            lc1, lc2 = st.columns([4, 1])
            with lc1:
                st.selectbox("Saved personas", range(len(labels)),
                             format_func=lambda i: f"{labels[i]} ({st.session_state.saved[i]['view']})",
                             key="load_idx", label_visibility="collapsed")
            with lc2:
                st.button("📂 Load", on_click=load_saved_persona, use_container_width=True)
    else:
        st.info("Paste a post, pick a mode, then **Build**.")

    # chat
    st.markdown("##### Chat test")
    if has_persona():
        kk, run = next(iter(st.session_state.runs.items()))
        render_transcript(run)
    user_input = st.chat_input("Say something…" if has_persona() else "Build a persona first",
                               disabled=not has_persona(), key="build_chat")
    if user_input and has_persona():
        kk, run = next(iter(st.session_state.runs.items()))
        run["messages"].append({"role": "user", "content": user_input})
        try:
            reply, info = core.chat_once(run["messages"])
        except Exception as e:
            reply, info = f"(Error: {type(e).__name__}: {e})", None
        run["messages"].append({"role": "assistant", "content": reply})
        run["chat_history"].append(("you", user_input, None))
        run["chat_history"].append(("persona", reply, info))
        st.rerun()

    # outputs
    if has_persona():
        kk, run = next(iter(st.session_state.runs.items()))
        if run.get("ccd"):
            with st.expander("CCD profile (Beck CCD) — editable"):
                if run.get("ccd_path"):
                    st.caption(f"📄 {run['ccd_path']}")
                edited = st.text_area("CCD (editable)", value=run["ccd"], height=320,
                                      key=f"ccd_edit_{st.session_state.build_counter}",
                                      label_visibility="collapsed")
                if st.button("✅ Apply edited CCD → rebuild persona"):
                    run["ccd"] = edited
                    run["system"] = core.persona_system_from_ccd(
                        edited, st.session_state.persona_from_ccd_prompt_edit)
                    run["messages"] = [{"role": "system", "content": run["system"]}]
                    run["chat_history"] = []
                    st.success("Persona rebuilt from the edited CCD. Chat was reset.")
                    st.rerun()
        with st.expander("Final system prompt sent to the model"):
            st.code(run["system"], language="text")
        with st.expander("Source post used"):
            st.text(st.session_state.built_post)

    with st.expander("🧩 Edit prompts"):
        st.caption("The real templates sent to the model. Edit, then **Build** to apply. Keep each `{curly}` placeholder.")
        st.button("↩️ Reset to default", on_click=reset_prompts)
        st.text_area("① Build CCD (A) — `{patient_text}`", key="build_ccd_prompt_edit", height=140)
        st.text_area("② Roleplay from CCD (A) — `{ccd_text}`", key="persona_from_ccd_prompt_edit", height=140)
        st.text_area("③ Roleplay from post (B) — `{post_text}`", key="persona_from_post_prompt_edit", height=140)


# ===========================================================================
# TAB 2 — Persona Library
# ===========================================================================
def render_library():
    personas = load_personas()
    source_posts = load_source_posts()
    st.caption("16 pre-computed personas from Felix's selected posts (8 themes × 2). "
               "Selecting one never re-calls the LLM; only chat does.")

    if not personas:
        st.warning("`personas.json` not found. Run `python build_personas.py` first.")
        return

    cL, cR = st.columns([3, 2])
    with cL:
        idx = st.selectbox(
            "Persona", range(len(personas)),
            format_func=lambda i: f"{i + 1:>2}. {personas[i]['persona_name']} — "
                                  f"{personas[i]['cluster']} · {personas[i]['subreddit']}",
            key="lib_idx")
    with cR:
        method = st.radio("Roleplay basis", ["A", "B"], horizontal=True,
                          format_func=lambda m: "A · via CCD" if m == "A" else "B · direct post",
                          key="lib_method",
                          help="Which cached system prompt drives the chat.")

    p = personas[idx]
    system_prompt = p["method_a"]["persona_system"] if method == "A" else p["method_b"]["persona_system"]

    st.markdown(f"### {p['persona_name']}")
    st.caption(f"{p['cluster_group']} → **{p['cluster']}** · {p['subreddit']} · "
               f"[source post]({p['source_url']})")
    st.info(p["persona_content"])

    chat_key = f"lib_chat_{p['source_post_id']}_{method}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = {"messages": [{"role": "system", "content": system_prompt}],
                                      "history": []}
    thread = st.session_state[chat_key]

    st.markdown("##### Chat with this persona")
    for role, text in thread["history"]:
        with st.chat_message("user" if role == "you" else "assistant"):
            st.write(text)
    if st.button("🧹 Reset chat", key="lib_reset"):
        st.session_state[chat_key] = {"messages": [{"role": "system", "content": system_prompt}],
                                      "history": []}
        st.rerun()
    user_input = st.chat_input("Say something to this persona…", key="lib_chat_input")
    if user_input:
        thread["messages"].append({"role": "user", "content": user_input})
        try:
            reply, _info = core.chat_once(thread["messages"])
        except Exception as e:
            reply = f"(Error: {type(e).__name__}: {e})"
        thread["messages"].append({"role": "assistant", "content": reply})
        thread["history"].append(("you", user_input))
        thread["history"].append(("persona", reply))
        st.rerun()

    with st.expander("Source post"):
        src = source_posts.get(p["source_post_id"])
        st.markdown(f"**{p['title']}**")
        st.text(src["content"] if src else "(source post text not found)")
    if p["method_a"].get("ccd"):
        with st.expander("CCD profile (Method A · Beck CCD)"):
            st.text(p["method_a"]["ccd"])
    with st.expander("System prompt in use (cached)"):
        st.code(system_prompt, language="text")


# ===========================================================================
# TAB 3 — Cluster Search
# ===========================================================================
def render_cluster():
    st.caption("Pick a cluster → fetch representative posts from Felix's ClusterSearch API → "
               "run a post's prompt through the existing CCD inference → display the CCD.")

    api_url = st.text_input("ClusterSearch API base URL", value=cluster_api.base_url(),
                            help="Default CLUSTERSEARCH_API_URL or http://localhost:8000.",
                            key="cs_api_url")
    try:
        h = cluster_api.health(api_url)
        st.success(f"API ok · {h['clusters']} clusters · {h['pool_posts']:,} posts")
        api_ok = True
    except Exception as e:
        st.error(f"API unreachable ({type(e).__name__}). On the cloud, point this at a public URL — "
                 f"localhost is the remote machine only. Start it: `uvicorn api:app --port 8000`.")
        st.caption(str(e))
        api_ok = False

    clusters = []
    if api_ok:
        try:
            clusters = cluster_api.get_clusters(api_url)
        except Exception as e:
            st.error(f"Could not load clusters: {e}")

    if clusters:
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            ci = st.selectbox("Cluster", range(len(clusters)),
                              format_func=lambda i: f"#{clusters[i]['id']} {clusters[i]['name']} "
                                                    f"({clusters[i]['n_posts']} posts)",
                              key="cs_cluster_i")
        with c2:
            n = st.slider("n posts", 1, 20, 5, key="cs_n")
        with c3:
            st.write("")
            st.write("")
            if st.button("🔎 Pick", type="primary", use_container_width=True):
                try:
                    with st.spinner("Calling /pick…"):
                        st.session_state.cs_pick = cluster_api.pick(
                            cluster_id=clusters[ci]["id"], n=n, override=api_url)
                    st.session_state.pop("cs_ccd", None)
                except Exception as e:
                    st.error(f"/pick failed: {e}")

    pick = st.session_state.get("cs_pick")
    if not pick:
        st.info("Pick a cluster and click **Pick** to fetch posts.")
        return

    c = pick["cluster"]
    st.markdown(f"### Cluster: {c['name']}")
    st.caption(f"keywords: {', '.join(c['keywords'])} · {c['n_matches']} posts above threshold "
               f"{c['sim_threshold']} · showing top {len(pick['posts'])}")

    posts = pick["posts"]
    sel = st.selectbox("Post", range(len(posts)),
                       format_func=lambda i: f"#{posts[i]['rank']} · sim {posts[i]['similarity']:.3f} · "
                                             f"r/{posts[i]['subreddit']} · {posts[i]['title'][:55]}",
                       key="cs_post_i")
    post = posts[sel]
    st.markdown(f"**{post['title']}**  ·  [source]({post['url']})  ·  {post['word_count']} words")
    with st.expander("Post body", expanded=True):
        st.write(post["body"])

    st.markdown("Feeds this post's `prompt` into `persona_core.generate_ccd()`.")
    if st.button("🧠 Generate CCD for this post", type="primary", key="cs_gen"):
        try:
            with st.spinner("Running CCD inference (gpt-4o)…"):
                ccd, _path, info = core.generate_ccd(post["prompt"])
            st.session_state.setdefault("cs_ccd", {})[post["url"]] = {"ccd": ccd, "info": info}
        except Exception as e:
            st.error(f"CCD inference failed: {type(e).__name__}: {e}")

    cached = st.session_state.get("cs_ccd", {}).get(post["url"])
    if cached:
        info = cached["info"]
        if info and info.get("total_tokens"):
            st.caption(f"⏱ {info.get('latency', 0):.1f}s · 🔢 {info['total_tokens']} tok")
        elif info and info.get("cached"):
            st.caption("served from CCD cache (no API call)")
        st.text(cached["ccd"])


# ===========================================================================
# LAYOUT — title + top tabs
# ===========================================================================
st.title("Persona Generation Interface")

tab_build, tab_lib, tab_cluster = st.tabs(["🛠 Build", "📚 Persona Library", "🔎 Cluster Search"])
with tab_build:
    render_build()
with tab_lib:
    render_library()
with tab_cluster:
    render_cluster()
