"""persona_core 的最小測試(不打網路)。執行:pytest tests/"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import persona_core as core  # noqa: E402


def test_load_clusters_has_8_categories():
    clusters = core.load_clusters()
    assert len(clusters) == 8
    assert "Habit Change" in clusters
    # 每篇 post 都有必要欄位
    for posts in clusters.values():
        for p in posts:
            assert {"id", "category", "title", "summary", "url", "flagged"} <= set(p)


def test_load_post_text_known_and_unknown():
    assert len(core.load_post_text(17)) > 0     # #17 全文存在 posts/17.txt
    assert core.load_post_text(999999) == ""    # 不存在 → 空字串


def test_build_persona_direct_no_api():
    r = core.build_persona(core.MODE_DIRECT, "I feel stuck and tired.")
    assert r["basis"] == "Post"
    assert r["ccd"] is None
    assert r["build_secs"] == 0.0
    assert "I feel stuck and tired." in r["system"]


def test_build_persona_ccd_monkeypatched(monkeypatch):
    def fake_generate_ccd(post_text):
        info = {"latency": 1.23, "cached": True,
                "prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
        return "FAKE-CCD-BODY", "/tmp/fake_ccd.txt", info

    monkeypatch.setattr(core, "generate_ccd", fake_generate_ccd)
    r = core.build_persona(core.MODE_CCD, "some post text")
    assert r["basis"] == "CCD"
    assert "FAKE-CCD-BODY" in r["system"]
    assert r["ccd_path"] == "/tmp/fake_ccd.txt"
    assert r["build_secs"] == 1.23


def test_ccd_cache_returns_same(monkeypatch):
    """同一篇 post 第二次走快取(cached=True、不再呼叫底層 client)。"""
    calls = {"n": 0}

    class _Msg:
        content = "CCD-FROM-API"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]
        usage = type("U", (), {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})()

    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    calls["n"] += 1
                    return _Resp()

    monkeypatch.setattr(core, "get_client", lambda: _Client())
    core._ccd_cache.clear()
    text = "unique-post-for-cache-test"
    ccd1, _, info1 = core.generate_ccd(text)
    ccd2, _, info2 = core.generate_ccd(text)
    assert ccd1 == ccd2 == "CCD-FROM-API"
    assert calls["n"] == 1            # 第二次沒再打 API
    assert info1["cached"] is False and info2["cached"] is True
