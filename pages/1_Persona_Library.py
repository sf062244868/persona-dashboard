"""
pages/1_Persona_Library.py — Persona Library (Task 3, simple version)
====================================================================

讀預先算好的 personas.json(由 build_personas.py 產生),讓使用者從下拉選單挑一個
persona → 顯示它的簡介 / 來源 post / CCD / system prompt,並可用「快取好的」system
prompt 直接聊天。**view 時不重算 persona**,只有聊天回覆才打 LLM。
"""

import json
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Persona Library", layout="wide")

from ui_common import ensure_openai_key, check_password  # noqa: E402

ensure_openai_key()
check_password()

import persona_core as core  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
PERSONAS_FILE = HERE / "personas.json"
SELECTED_FILE = HERE / "selected_posts.json"


@st.cache_data
def load_personas():
    if not PERSONAS_FILE.exists():
        return []
    return json.loads(PERSONAS_FILE.read_text(encoding="utf-8")).get("personas", [])


@st.cache_data
def load_source_posts():
    if not SELECTED_FILE.exists():
        return {}
    data = json.loads(SELECTED_FILE.read_text(encoding="utf-8"))
    return {p["post_id"]: p for p in data.get("posts", [])}


personas = load_personas()
source_posts = load_source_posts()

st.title("📚 Persona Library")
st.caption("Pre-computed personas from Felix's 16 selected posts (8 cluster themes × 2). "
           "Built once by `build_personas.py` — selecting one never re-calls the LLM; only chat does.")

if not personas:
    st.warning("`personas.json` not found. Run `python build_personas.py` first.")
    st.stop()


# ---------------------------------------------------------------------------
# Sidebar — pick a persona + method
# ---------------------------------------------------------------------------
def _label(p):
    return f"{p['persona_name']} — {p['cluster']} · {p['subreddit']}"


with st.sidebar:
    st.header("Pick a persona")
    idx = st.selectbox(
        "Persona", range(len(personas)),
        format_func=lambda i: f"{i + 1:>2}. {_label(personas[i])}",
        key="lib_idx",
    )
    method = st.radio(
        "Roleplay basis", ["A", "B"],
        format_func=lambda m: "Method A · via CCD" if m == "A" else "Method B · direct post",
        key="lib_method",
        help="Which cached system prompt drives the chat. A = built from the Beck CCD; B = built from the raw post.",
    )

p = personas[idx]
system_prompt = p["method_a"]["persona_system"] if method == "A" else p["method_b"]["persona_system"]

# ---------------------------------------------------------------------------
# Main — persona profile + chat
# ---------------------------------------------------------------------------
st.subheader(f"{p['persona_name']}")
st.caption(f"{p['cluster_group']} → **{p['cluster']}** · {p['subreddit']} · "
           f"[source post]({p['source_url']})")

st.markdown("**Persona profile**")
st.info(p["persona_content"])

# chat thread is per (persona, method) so switching keeps each thread separate
chat_key = f"lib_chat_{p['source_post_id']}_{method}"
if chat_key not in st.session_state:
    st.session_state[chat_key] = {"messages": [{"role": "system", "content": system_prompt}],
                                  "history": []}
thread = st.session_state[chat_key]

st.markdown("**Chat with this persona**")
for role, text in thread["history"]:
    with st.chat_message("user" if role == "you" else "assistant"):
        st.write(text)

col_a, col_b = st.columns([1, 5])
with col_a:
    if st.button("🧹 Reset chat", use_container_width=True):
        st.session_state[chat_key] = {"messages": [{"role": "system", "content": system_prompt}],
                                      "history": []}
        st.rerun()

user_input = st.chat_input("Say something to this persona…")
if user_input:
    thread["messages"].append({"role": "user", "content": user_input})
    try:
        reply, info = core.chat_once(thread["messages"])
    except Exception as e:
        reply, info = f"(Error: {type(e).__name__}: {e})", None
    thread["messages"].append({"role": "assistant", "content": reply})
    thread["history"].append(("you", user_input))
    thread["history"].append(("persona", reply))
    st.rerun()

# ---------------------------------------------------------------------------
# Details — source post / CCD / system prompt (read-only)
# ---------------------------------------------------------------------------
with st.expander("Source post"):
    src = source_posts.get(p["source_post_id"])
    st.markdown(f"**{p['title']}**")
    st.text(src["content"] if src else "(source post text not found)")

if p["method_a"].get("ccd"):
    with st.expander("CCD profile (Method A · Beck CCD)"):
        st.text(p["method_a"]["ccd"])

with st.expander("System prompt in use (cached)"):
    st.caption("This exact text is the persona's system message for every reply above — "
               "no LLM call was needed to build it.")
    st.code(system_prompt, language="text")
