"""persona_core 的最小測試(不打網路)。執行:pytest tests/"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import persona_core as core  # noqa: E402


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
    def fake_generate_ccd_psi(post_text, ccd_prompt=None, name=None):
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


# 新版 beck-aligned Stage-1 CCD:每格是 {text,grounding,evidence} box、無封閉集。
NEW_BOX_CM = {
    "name": "Max",
    "themes": ["loneliness"],
    "cognitive_models": [{
        "situation": {"text": "Saw old friends hanging out without me online",
                      "grounding": "stated",
                      "evidence": ["friends hanging out without me"]},
        "automatic_thoughts": {"text": "I wasn't invited; I'm not part of that anymore",
                               "grounding": "stated", "evidence": ["wasn't invited"]},
        "meaning_of_automatic_thought": {"text": "It means no one wants me around ?",
                                         "grounding": "inferred", "evidence": []},
        "emotion": {"text": "lonely, left out", "grounding": "stated",
                    "evidence": ["lonely"]},
        "behavior": {"text": "Stayed on the couch, reached out to no one",
                     "grounding": "stated", "evidence": ["reached out to no one"]},
    }],
    "core_belief": {"text": "I'm meant to be alone ?", "grounding": "inferred", "evidence": []},
    "intermediate_beliefs": {"text": "If I share my struggles I'll be a burden ?",
                             "grounding": "inferred", "evidence": []},
    "coping_strategies": {"text": "Withdraws further; distracts with TV",
                          "grounding": "stated", "evidence": ["friends hanging out without me"]},
    # 這格故意放一條「不在 post 裡」的 evidence,用來驗 grounding_report 的 fail 分支。
    "life_history": {"text": "Friends drifted after university",
                     "grounding": "stated", "evidence": ["moved abroad as a kid"]},
    "prompt_version": "beck-aligned-v1",
}

POST_TEXT_FOR_NEW_BOX = ("I'm mostly by myself. I saw old friends hanging out without me "
                         "online and I wasn't invited. I felt lonely and reached out to no one.")


def test_new_box_shape_renders_and_feeds_persona(monkeypatch):
    """新 box 形:CCD 文字與 persona system 都不可漏出 str(dict);核心信念要進得去。"""
    def fake_generate_ccd_psi(post_text, ccd_prompt=None, name=None):
        return NEW_BOX_CM, {"latency": 0.0, "cached": True}

    monkeypatch.setattr(core, "generate_ccd_psi", fake_generate_ccd_psi)
    monkeypatch.setattr(core, "_save_ccd_json", lambda cm: "/tmp/fake_ccd.json")
    r = core.build_persona(core.MODE_CCD, POST_TEXT_FOR_NEW_BOX, name="Max")

    ccd_text, system = r["ccd"], r["system"]
    # 沒有 dict 字面漏出來
    assert "'text':" not in ccd_text and "{'text'" not in system
    # 核心信念的「本人原話」有進 CCD 文字與 persona
    assert "I'm meant to be alone" in ccd_text
    assert "I'm meant to be alone" in system
    # grounding 標記有出現在給人看的文字
    assert "[stated]" in ccd_text and "[inferred]" in ccd_text
    # 情境/行為的 box text(非 dict)有攤平進 persona
    assert "reached out to no one" in system


def test_build_persona_ccd_situation_index(monkeypatch):
    """cm_index 選第幾個 cognitive model,忠於官方 Abe 1-1/1-2/1-3 的一場一情境。"""
    def fake_generate_ccd_psi(post_text, ccd_prompt=None, name=None):
        return FAKE_CM, {"latency": 0.0, "cached": True}

    monkeypatch.setattr(core, "generate_ccd_psi", fake_generate_ccd_psi)
    monkeypatch.setattr(core, "_save_ccd_json", lambda cm: "/tmp/fake_ccd.json")
    r = core.build_persona(core.MODE_CCD, "some post text", cm_index=1)
    assert "SITU-TWO" in r["system"] and "SITU-ONE" not in r["system"]


def test_ccd_psi_cache_returns_same(monkeypatch):
    """同一篇 post 第二次走 generate_ccd_psi 快取(cached=True、不再呼叫底層 client)。"""
    calls = {"n": 0}

    class _Msg:
        content = '{"name": "X", "cognitive_models": []}'

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
    core._ccd_psi_cache.clear()
    text = "unique-post-for-cache-test"
    cm1, info1 = core.generate_ccd_psi(text)
    cm2, info2 = core.generate_ccd_psi(text)
    assert cm1 == cm2
    assert calls["n"] == 1            # 第二次沒再打 API
    assert info1["cached"] is False and info2["cached"] is True


def test_chat_once_switches_model_and_drops_penalties(monkeypatch):
    """gpt-4o/mini 切換:chat_once 把選定 model 傳進 client、回報在 info、且不再帶 penalty。"""
    captured = {}

    class _Msg:
        content = "hi there"

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
                    captured.update(kw)
                    return _Resp()

    monkeypatch.setattr(core, "get_client", lambda: _Client())
    reply, info = core.chat_once([{"role": "user", "content": "hi"}], model="gpt-4o-mini")
    assert captured["model"] == "gpt-4o-mini"          # 真的把 mini 傳給 API
    assert "presence_penalty" not in captured          # penalty 已移除
    assert "frequency_penalty" not in captured
    assert info["model"] == "gpt-4o-mini"              # UI 可顯示本則用哪個 model
