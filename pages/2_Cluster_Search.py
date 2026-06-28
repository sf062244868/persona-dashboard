"""
pages/2_Cluster_Search.py — ClusterSearch pipeline (Task 3 / REMOTE_GOAL T3)
===========================================================================

One coherent dynamic pipeline:
    cluster (GET /clusters) -> POST /pick -> each post's `prompt`
    -> EXISTING CCD inference (persona_core.generate_ccd) -> display CCD

Simple view only (no intermediate-artifact "complex view" yet).
API base URL is configurable (CLUSTERSEARCH_API_URL env var; default
http://localhost:8000) and can be overridden in the sidebar.
"""

import streamlit as st

st.set_page_config(page_title="Cluster Search", layout="wide")

from ui_common import ensure_openai_key, check_password  # noqa: E402

ensure_openai_key()
check_password()

import persona_core as core      # noqa: E402  (existing CCD inference)
import cluster_api               # noqa: E402  (Felix's API client)

st.title("🔎 Cluster Search → CCD")
st.caption("Pick a cluster → fetch representative posts from Felix's ClusterSearch API → "
           "run each post's prompt through the existing CCD inference → display the CCD.")


# ---------------------------------------------------------------------------
# Sidebar — API config + cluster picker
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("ClusterSearch API")
    api_url = st.text_input("API base URL", value=cluster_api.base_url(),
                            help="Configurable; defaults to CLUSTERSEARCH_API_URL or http://localhost:8000")

    # health check
    try:
        h = cluster_api.health(api_url)
        st.success(f"API ok · {h['clusters']} clusters · {h['pool_posts']:,} posts")
        api_ok = True
    except Exception as e:
        st.error(f"API unreachable: {type(e).__name__}")
        st.caption(f"{e}")
        st.caption("Start it: `uvicorn api:app --port 8000` in ClusterSearch-API.")
        api_ok = False

    clusters = []
    if api_ok:
        try:
            clusters = cluster_api.get_clusters(api_url)
        except Exception as e:
            st.error(f"Could not load clusters: {e}")

    if clusters:
        ci = st.selectbox(
            "Cluster", range(len(clusters)),
            format_func=lambda i: f"#{clusters[i]['id']} {clusters[i]['name']} "
                                  f"({clusters[i]['n_posts']} posts)",
            key="cs_cluster_i",
        )
        n = st.slider("How many posts (n)", 1, 20, 5, key="cs_n")
        if st.button("🔎 Pick posts", type="primary", use_container_width=True):
            try:
                with st.spinner("Calling /pick…"):
                    st.session_state.cs_pick = cluster_api.pick(
                        cluster_id=clusters[ci]["id"], n=n, override=api_url)
                st.session_state.pop("cs_ccd", None)
            except Exception as e:
                st.error(f"/pick failed: {e}")


# ---------------------------------------------------------------------------
# Main — picked posts + on-demand CCD
# ---------------------------------------------------------------------------
pick = st.session_state.get("cs_pick")
if not pick:
    st.info("← Pick a cluster and click **Pick posts** to start.")
    st.stop()

c = pick["cluster"]
st.subheader(f"Cluster: {c['name']}")
st.caption(f"keywords: {', '.join(c['keywords'])} · {c['n_matches']} posts above threshold "
           f"{c['sim_threshold']} · showing top {len(pick['posts'])}")

posts = pick["posts"]
labels = [f"#{p['rank']} · sim {p['similarity']:.3f} · r/{p['subreddit']} · {p['title'][:60]}"
          for p in posts]
sel = st.selectbox("Post", range(len(posts)), format_func=lambda i: labels[i], key="cs_post_i")
post = posts[sel]

st.markdown(f"**{post['title']}**  ·  [source]({post['url']})  ·  {post['word_count']} words")
with st.expander("Post body", expanded=True):
    st.write(post["body"])

# Pipeline step: feed the API's ready-made `prompt` into the existing CCD inference.
st.markdown("**CCD inference** — feeds this post's `prompt` into `persona_core.generate_ccd()`.")
if st.button("🧠 Generate CCD for this post", type="primary"):
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
