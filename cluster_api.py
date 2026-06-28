"""
cluster_api.py — thin client for Felix's ClusterSearch-API (FastAPI)
===================================================================

Talks to the Resonance/ClusterSearch API:
    GET  /clusters  -> [{id, name, n_posts}]
    POST /pick      -> {cluster:{...}, posts:[{rank, similarity, subreddit,
                        title, body, url, word_count, prompt}]}
    GET  /health    -> {status, clusters, pool_posts}

Base URL is configurable via the CLUSTERSEARCH_API_URL env var (or passed in);
defaults to http://localhost:8000. Uses stdlib urllib only (no extra deps).
"""

import os
import json
import urllib.request
import urllib.error

DEFAULT_BASE_URL = "http://localhost:8000"


def base_url(override: str = None) -> str:
    url = override or os.environ.get("CLUSTERSEARCH_API_URL") or DEFAULT_BASE_URL
    return url.rstrip("/")


def _get(path: str, override: str = None, timeout: int = 30):
    req = urllib.request.Request(base_url(override) + path, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(path: str, payload: dict, override: str = None, timeout: int = 120):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base_url(override) + path, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # surface the API's {"detail": "..."} message (e.g. 409 multi-match) cleanly
        body = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(body).get("detail", body)
        except Exception:
            detail = body
        raise RuntimeError(f"API {e.code}: {detail}") from None


def health(override: str = None) -> dict:
    return _get("/health", override)


def get_clusters(override: str = None) -> list:
    return _get("/clusters", override)


def pick(cluster_id: int = None, cluster_name: str = None, n: int = 5, override: str = None) -> dict:
    payload = {"n": n}
    if cluster_id is not None:
        payload["cluster_id"] = cluster_id
    if cluster_name is not None:
        payload["cluster_name"] = cluster_name
    return _post("/pick", payload, override)
