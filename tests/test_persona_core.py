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


FAKE_CM = {
    "name": "Testy",
    "life_history": "some background",
    "core_belief_category": "unlovable",
    "core_beliefs": ["I am unlovable."],
    "intermediate_beliefs": "some rule",
    "intermediate_beliefs_during_depression": "N/A",
    "coping_strategies": "avoidance",
    "cognitive_models": [
        {"situation": "SITU-ONE", "automatic_thoughts": "AT1",
         "emotion": ["sad, down, lonely, unhappy"], "behavior": "B1"},
        {"situation": "SITU-TWO", "automatic_thoughts": "AT2",
         "emotion": ["hurt"], "behavior": "B2"},
        {"situation": "SITU-THREE", "automatic_thoughts": "AT3",
         "emotion": ["guilty"], "behavior": "B3"},
    ],
}


def test_build_persona_ccd_monkeypatched(monkeypatch):
    def fake_generate_ccd_psi(post_text, ccd_prompt=None):
        info = {"latency": 1.23, "cached": True,
                "prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
        return FAKE_CM, info

    monkeypatch.setattr(core, "generate_ccd_psi", fake_generate_ccd_psi)
    monkeypatch.setattr(core, "_save_ccd_json", lambda cm: "/tmp/fake_ccd.json")
    r = core.build_persona(core.MODE_CCD, "some post text")
    assert r["basis"] == "CCD"
    assert "Imagine you are Testy" in r["system"]      # 用真名,不是 "the patient"
    assert "SITU-ONE" in r["system"]                   # 預設用第 1 個 cognitive model
    assert r["build_secs"] == 1.23
    # cm_to_text 應把 ≥3 個情境全列出
    assert "SITU-TWO" in r["ccd"] and "SITU-THREE" in r["ccd"]


def test_build_persona_ccd_situation_index(monkeypatch):
    """cm_index 選第幾個 cognitive model,忠於官方 Abe 1-1/1-2/1-3 的一場一情境。"""
    def fake_generate_ccd_psi(post_text, ccd_prompt=None):
        return FAKE_CM, {"latency": 0.0, "cached": True}

    monkeypatch.setattr(core, "generate_ccd_psi", fake_generate_ccd_psi)
    monkeypatch.setattr(core, "_save_ccd_json", lambda cm: "/tmp/fake_ccd.json")
    r = core.build_persona(core.MODE_CCD, "some post text", cm_index=1)
    assert "SITU-TWO" in r["system"] and "SITU-ONE" not in r["system"]


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
