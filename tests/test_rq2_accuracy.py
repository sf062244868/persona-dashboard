"""rq2_accuracy 的離線測試(不打網路)。執行: pytest tests/test_rq2_accuracy.py"""
import sys
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rq2_accuracy as rq2  # noqa: E402


FAKE_CCD = {
    "name": "Testy",
    "core_belief_category": "unlovable",
    "core_beliefs": ["I am unlovable.", "I am bound to be alone."],
    "intermediate_beliefs": "If I open up, I get hurt.",
    "coping_strategies": "Avoids intimacy.",
    "cognitive_models": [
        {"situation": "Partner didn't text back.",
         "automatic_thoughts": "They're leaving me.",
         "emotion": ["anxious, worried, fearful, scared, tense", "hurt"],
         "behavior": "Checks phone repeatedly."},
        {"situation": "second situation", "automatic_thoughts": "x",
         "emotion": ["guilty"], "behavior": "y"},
    ],
}


def test_gt_text_uses_first_cognitive_model_and_aliases():
    gt = rq2.gt_text(FAKE_CCD)
    assert gt["situation"] == "Partner didn't text back."      # 用 cm[0]
    assert gt["automatic_thoughts"] == "They're leaving me."
    assert gt["behaviors"] == "Checks phone repeatedly."
    assert gt["coping_strategies"] == "Avoids intimacy."
    # auto_thoughts 別名也要吃
    alt = dict(FAKE_CCD)
    alt["cognitive_models"] = [{"situation": "s", "auto_thoughts": "ALIASED",
                                "emotion": ["hurt"], "behavior": "b"}]
    assert rq2.gt_text(alt)["automatic_thoughts"] == "ALIASED"


def test_gt_closed_sets():
    assert rq2.gt_beliefs(FAKE_CCD) == {"I am unlovable.", "I am bound to be alone."}
    # emotion 取 cm[0] 的整段 label（不拆字）
    assert rq2.gt_emotions(FAKE_CCD) == {
        "anxious, worried, fearful, scared, tense", "hurt"}


def test_gt_beliefs_canonicalizes_missing_period():
    """CCD 生成常漏句點；gt_beliefs 要對齊封閉集官方寫法(含句點)才能算對 F1。"""
    ccd = {"core_beliefs": ["I am bound to be rejected", "i am unlovable"],
           "cognitive_models": [{"situation": "s", "automatic_thoughts": "a",
                                 "emotion": [], "behavior": "b"}]}
    got = rq2.gt_beliefs(ccd)
    assert "I am bound to be rejected." in got      # 補回句點、對上封閉集
    assert "I am unlovable." in got                 # 大小寫也對齊
    # 對齊後就在 19 標籤全集內
    assert got <= set(rq2.PSI_CORE_BELIEF_LABELS_)


def test_patient_text_streamlit_format():
    md = ("===== Persona (A) =====\n[Chat]\n"
          "You: Hi, how was your week?\n"
          "Persona: Not great. I kept checking my phone.\n"
          "It made me anxious.\n"
          "You: Tell me more.\n"
          "Persona: I felt like they were leaving me.\n")
    txt = rq2.patient_text(md)
    assert "checking my phone" in txt
    assert "It made me anxious." in txt            # 病人多行接續
    assert "they were leaving me" in txt
    assert "how was your week" not in txt          # 治療師的話不算


def test_patient_text_turn_format():
    md = ("## turn 1\nT: Hello.\nP: I feel stuck.\n\n"
          "## turn 2\nT: Why?\nP: Because nothing works.\n")
    txt = rq2.patient_text(md)
    assert "I feel stuck." in txt and "Because nothing works." in txt
    assert "Hello." not in txt and "Why?" not in txt


def test_build_mcq_shape_and_correct_index():
    rng = random.Random(0)
    gt = "the true situation"
    pool = ["d1", "d2", "d3", "d4", "d5", "d6", gt]   # 含與真值相同者要被排除
    options, correct = rq2.build_mcq(gt, pool, rng)
    assert len(options) == rq2.N_OPTIONS               # 恰 5 選項
    assert options[correct] == gt                      # 正解索引指向真值
    assert len(set(options)) == rq2.N_OPTIONS          # 無重複
    assert options.count(gt) == 1                      # 真值只出現一次


def test_build_mcq_reproducible_with_same_seed():
    a = rq2.build_mcq("g", ["a", "b", "c", "d", "e"], random.Random(42))
    b = rq2.build_mcq("g", ["a", "b", "c", "d", "e"], random.Random(42))
    assert a == b                                      # 同 seed → 可重現


def test_find_transcript_by_library_name_and_model(tmp_path):
    """檔名用 library 名字也找得到；gpt-4o 不可誤配到 gpt-4o-mini。"""
    (tmp_path / "Jake__gpt-4o.md").write_text("x", encoding="utf-8")
    (tmp_path / "Jake__gpt-4o-mini.md").write_text("x", encoding="utf-8")
    (tmp_path / "_TEMPLATE__example.md").write_text("x", encoding="utf-8")
    persona = {"source_post_id": "1h8zpqh", "persona_name": "Jake (25M)"}
    assert rq2.find_transcript(tmp_path, persona, "gpt-4o").name == "Jake__gpt-4o.md"
    assert rq2.find_transcript(tmp_path, persona, "gpt-4o-mini").name == "Jake__gpt-4o-mini.md"
    # 也能用 source_post_id 命名
    (tmp_path / "1htp0xw__gpt-4o.md").write_text("x", encoding="utf-8")
    pid_persona = {"source_post_id": "1htp0xw", "persona_name": "Max (Lonely)"}
    assert rq2.find_transcript(tmp_path, pid_persona, "gpt-4o").name == "1htp0xw__gpt-4o.md"
    # 缺檔回 None、_ 開頭範本被略過
    assert rq2.find_transcript(tmp_path, {"source_post_id": "zzz",
                                          "persona_name": "Nobody"}, "gpt-4o") is None


def test_macro_f1_known_case():
    labels = ["a", "b", "c"]
    # 一場對話：真值{a,b} 預測{a,c}
    #   a: TP=1 → F1=1 ; b: FN=1 → F1=0 ; c: FP=1 → F1=0 ; 平均=1/3
    pairs = [({"a", "b"}, {"a", "c"})]
    got = rq2.macro_f1(pairs, labels)
    assert abs(got - (1.0 / 3.0)) < 1e-9


def test_macro_f1_perfect_and_skips_absent_labels():
    labels = ["a", "b", "c", "d"]      # d 從沒出現 → 應跳過、不拉低分母
    pairs = [({"a"}, {"a"}), ({"b"}, {"b"})]
    assert rq2.macro_f1(pairs, labels) == 1.0


# 新版 Beck-aligned Stage-1 CCD:每格是 {text,grounding,evidence} box、無封閉集 label。
NEW_BOX_CCD = {
    "name": "Max",
    "cognitive_models": [{
        "situation": {"text": "Mostly by myself", "grounding": "stated", "evidence": []},
        "automatic_thoughts": {"text": "I can't connect", "grounding": "stated", "evidence": []},
        "emotion": {"text": "lonely", "grounding": "stated", "evidence": []},
        "behavior": {"text": "Withdrew further", "grounding": "stated", "evidence": []},
    }],
    "core_belief": {"text": "Something about me can't connect ?", "grounding": "inferred", "evidence": []},
    "intermediate_beliefs": {"text": "Sharing = being a burden ?", "grounding": "inferred", "evidence": []},
    "coping_strategies": {"text": "Improves alone", "grounding": "stated", "evidence": []},
    "life_history": {"text": "90% alone since university", "grounding": "stated", "evidence": []},
    "prompt_version": "beck-aligned-v1",
}


def test_gt_text_box_shape_no_crash():
    """新版 box 形不可讓 gt_text 對 dict 呼叫 .strip() 而崩潰;要攤出 box 的 text。"""
    t = rq2.gt_text(NEW_BOX_CCD)
    assert t["situation"] == "Mostly by myself"
    assert t["automatic_thoughts"] == "I can't connect"
    assert t["behaviors"] == "Withdrew further"
    assert t["coping_strategies"] == "Improves alone"


def test_closed_set_returns_none_for_new_box():
    """新版 box 無封閉集 label → gt_beliefs/gt_emotions 回 None(F1 track 會被跳過)。"""
    assert rq2.gt_beliefs(NEW_BOX_CCD) is None
    assert rq2.gt_emotions(NEW_BOX_CCD) is None


def test_closed_set_still_works_for_old_flat():
    """舊 flat 形維持原行為:回傳對齊封閉集的集合。"""
    assert rq2.gt_beliefs(FAKE_CCD) == {"I am unlovable.", "I am bound to be alone."}
    assert rq2.gt_emotions(FAKE_CCD) is not None and len(rq2.gt_emotions(FAKE_CCD)) >= 1
