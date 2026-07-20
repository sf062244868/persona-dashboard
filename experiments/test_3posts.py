"""
test_3posts.py — 3 篇 post 的完整 pipeline 測試(post → CCD → persona → 隨機訪談)
================================================================================
走的是和 Streamlit UI 完全同一份後端:
    build_persona(MODE_CCD) → generate_ccd_psi(gpt-4o) → psi_persona_system → chat_once

每篇會輸出一份 markdown,含:
  ① 原 post
  ② 實際送給 gpt-4o 的 CCD 建構 prompt 全文
  ③ 回傳的 CCD 原始 JSON
  ④ cm_to_text 的 9 格文字(UI 的「CCD profile」看到的東西)
  ⑤ 自動檢查(schema 合規 + 5 個舊失敗模式有沒有復發)
  ⑥ 隨機自由訪談逐字稿

跑法:
    .venv/bin/python experiments/test_3posts.py            # 實跑(需 OPENAI_API_KEY)
    .venv/bin/python experiments/test_3posts.py --dry-run  # 空跑,不打 API,驗流程用

隨機問題用固定 seed(每篇不同),所以「隨機」但可重跑重現。
"""
import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

import persona_core as pc  # noqa: E402

OUT_DIR = HERE / "results"
CHAT_MODEL = "gpt-4o"
N_QUESTIONS = 8

# 三篇測試 post。persona 不取名——一律用 post_id 當識別。
TARGETS = [
    {"post_id": "1htp0xw", "seed": 101, "note": "舊版 Max,可與舊 prompt 逐字稿對照"},
    {"post_id": "1iercl7", "seed": 202, "note": "典型自責,core belief 應清楚"},
    {"post_id": "1hcql49", "seed": 303, "note": "低困擾日常貼文(反例對照):測會不會亂編病理"},
]

# --- 隨機自由問題池 -------------------------------------------------------------
# 刻意寫成自然口語、不是 Beck 逐格走查。池子裡混了幾題天然的邊界題
# (家庭史 / 工作 / 憂鬱),隨機抽到時就順便驗「會不會憑空捏造」。
OPENERS = [
    "Hey, thanks for talking with me today. What's been on your mind lately?",
    "Hi — how have things been going for you recently?",
    "Thanks for sitting down with me. Where would you like to start?",
    "Can you tell me a bit about what's been going on for you?",
]

QUESTION_POOL = [
    "Can you tell me about a moment recently that really stuck with you?",
    "What was going through your head right then?",
    "How did that leave you feeling?",
    "What did you end up doing about it?",
    "Has this been going on for a while, or is it fairly new?",
    "Who do you usually talk to when things get heavy?",
    "What does a typical day look like for you right now?",
    "If a friend were in your exact situation, what would you say to them?",
    "What would need to change for things to feel even a little better?",
    "Is there something you wish people understood about you?",
    "What do you do when you need to get your mind off things?",
    "Tell me about your family growing up.",
    "How have work or school been going?",
    "Do you think you might be depressed?",
    "What's something that went okay recently, even a small thing?",
    "When you picture six months from now, what do you see?",
    "Is there anything you've been putting off or avoiding?",
    "What's the hardest part of all this for you?",
    "How do you usually talk to yourself when something goes wrong?",
    "What helps, when anything helps?",
]


def pick_questions(seed: int, n: int = N_QUESTIONS) -> list:
    """固定 seed 的隨機抽題:第 1 題一定是開場白,其餘從題池隨機抽不重複。"""
    rng = random.Random(seed)
    return [rng.choice(OPENERS)] + rng.sample(QUESTION_POOL, n - 1)


# --- 自動檢查 -------------------------------------------------------------------
TOP_KEYS = ["life_history", "core_belief", "intermediate_beliefs",
            "coping_strategies", "cognitive_models"]
CM_KEYS = ["situation", "automatic_thoughts", "meaning_of_automatic_thought",
           "emotion", "behavior"]


def check_ccd(cm: dict, post_text: str = "") -> dict:
    """schema 合規 + 5 個舊失敗模式。回傳 {檢查項: (pass, 說明)}。"""
    models = cm.get("cognitive_models") or []
    flat = []           # 所有欄位值,用來驗型別與 label 洩漏
    for k in TOP_KEYS:
        if k != "cognitive_models":
            flat.append((k, cm.get(k)))
    for i, m in enumerate(models):
        for k in CM_KEYS:
            flat.append((f"cognitive_models[{i}].{k}", (m or {}).get(k)))

    non_str = [k for k, v in flat if not isinstance(v, str)]
    missing_top = [k for k in TOP_KEYS if k not in cm]
    missing_cm = [f"[{i}].{k}" for i, m in enumerate(models)
                  for k in CM_KEYS if k not in (m or {})]

    # 封閉集 label 洩漏:CCD 欄位不該逐字等於 19 個 core-belief / 9 個 emotion 標籤
    leaked = [f"{k}={v!r}" for k, v in flat if isinstance(v, str)
              and (v.strip().rstrip("?").strip() in pc.PSI_CORE_BELIEF_LABELS
                   or v.strip() in pc.PSI_EMOTIONS)]

    insufficient = [k for k, v in flat if isinstance(v, str)
                    and v.strip().lower().startswith("insufficient")]

    rendered = pc.cm_to_text(cm)

    # name 健全性:上一版只驗「非空且非 Alex/Daniel」,結果 1239 字的整篇 post
    # 和字面 "NAME" 都矇混過關,腳本才會誤報「全部通過」。這裡改成正面描述人名該長怎樣。
    # 新規格:CCD 只有 5 個內容欄位,不該出現 name。
    # persona 的識別改用 post_id,所以這裡驗的是「沒有名字」而不是「名字合法」。
    has_name = "name" in cm
    # 原文夾帶偵測仍保留:任何欄位若整段吞進 post,roleplay prompt 就會被污染。
    leak_fields = []
    if post_text:
        probe = post_text.strip()[:40]
        for k, v in flat:
            if isinstance(v, str) and probe in v:
                leak_fields.append(k)

    return {
        "CCD 不含人名欄位": (not has_name, f"意外出現 name={cm.get('name')!r}" if has_name else "OK"),
        "無欄位夾帶原文": (not leak_fields, f"夾帶:{leak_fields}" if leak_fields else "OK"),
        "所有頂層 key 齊全": (not missing_top, f"缺:{missing_top}" if missing_top else "OK"),
        "每個 cognitive_model 欄位齊全": (not missing_cm, f"缺:{missing_cm}" if missing_cm else f"{len(models)} 個 model"),
        "cognitive_models 有 1–3 個": (1 <= len(models) <= 3, f"{len(models)} 個"),
        "所有欄位都是 plain string": (not non_str, f"非字串:{non_str}" if non_str else "OK"),
        "① 沒有捏造 depression 欄": ("intermediate_beliefs_during_depression" not in cm, "OK"),
        "② 沒有照抄封閉集 label": (not leaked, f"洩漏:{leaked}" if leaked else "OK"),
        "③ 有 Meaning of A.T. 且非空": (
            all((m or {}).get("meaning_of_automatic_thought", "").strip() for m in models),
            "OK" if models else "無 model"),
        "prompt_version 標記正確": (
            cm.get("prompt_version") == "beck-pure-string-v4", f"{cm.get('prompt_version')!r}"),
        "cm_to_text 無假 [closed-set:] 標籤": ("[closed-set:" not in rendered, "OK"),
        "insufficient information 欄位數": (True, f"{len(insufficient)} 個 {insufficient}"),
    }


def check_transcript(pairs: list) -> dict:
    """逐字稿層級:persona 有沒有照唸封閉集 label。"""
    joined = " ".join(a for _, a in pairs).lower()
    parroted = [lab for lab in pc.PSI_CORE_BELIEF_LABELS
                if lab.lower().rstrip(".") in joined]
    return {
        "persona 沒照唸 core-belief label": (
            not parroted, f"照唸:{parroted}" if parroted else "OK"),
        "每題都有回覆": (all(a.strip() for _, a in pairs), f"{len(pairs)} 輪"),
    }


# --- dry-run 假 client(不打 API)-----------------------------------------------
def install_fake_client():
    """把 get_client 換成假的,回傳符合新 schema 的字串型 CCD 與罐頭對話。"""
    fake_ccd = {
        "life_history": "insufficient information",
        "core_belief": "I am not worth including ?",
        "intermediate_beliefs": "If I reach out and get no reply, it means I'm not wanted.",
        "coping_strategies": "Withdraws and stops initiating contact.",
        "cognitive_models": [{
            "situation": "Saw friends posting from a gathering he wasn't invited to.",
            "automatic_thoughts": "They didn't even think of me.",
            "meaning_of_automatic_thought": "I don't matter to people ?",
            "emotion": "lonely, hurt",
            "behavior": "Put the phone down and stayed in bed.",
        }],
    }

    class _Usage:
        prompt_tokens, completion_tokens, total_tokens = 900, 300, 1200

    def _resp(content):
        msg = type("M", (), {"content": content})()
        choice = type("C", (), {"message": msg, "finish_reason": "stop"})()
        return type("R", (), {"choices": [choice], "usage": _Usage()})()

    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    is_ccd = kw.get("response_format", {}).get("type") == "json_object"
                    if is_ccd:
                        return _resp(json.dumps(fake_ccd, ensure_ascii=False))
                    return _resp("(dry-run) I guess I've just been keeping to myself a lot lately.")

    pc.get_client = lambda: _Client()


# --- 主流程 ---------------------------------------------------------------------
def run_one(target: dict, dry: bool) -> dict:
    post_id, seed = target["post_id"], target["seed"]
    post = (REPO / "posts" / f"{post_id}.txt").read_text(encoding="utf-8").strip()

    print(f"\n{'=' * 78}\n[{post_id}] {target['note']}\n{'=' * 78}")

    prompt_sent = pc._ccd_psi_prompt(post)
    build = pc.build_persona(pc.MODE_CCD, post)
    cm = build["ccd_struct"]
    system = build["system"]
    info = build.get("info") or {}
    print(f"CCD 生成完畢 · {info.get('latency', 0):.1f}s · {info.get('total_tokens')} tok")
    print(pc.cm_to_text(cm))

    ccd_checks = check_ccd(cm, post)
    print("\n-- CCD 自動檢查 --")
    for k, (ok, detail) in ccd_checks.items():
        print(f"  [{'✓' if ok else '✗'}] {k}  ({detail})")

    questions = pick_questions(seed)
    messages = [{"role": "system", "content": system}]
    pairs = []
    print(f"\n-- 隨機訪談(seed={seed},{len(questions)} 題)--")
    for q in questions:
        messages.append({"role": "user", "content": q})
        reply, _ = pc.chat_once(messages, model=CHAT_MODEL)
        messages.append({"role": "assistant", "content": reply})
        pairs.append((q, reply))
        print(f"\nYou: {q}\n[{post_id}]: {reply}")

    tr_checks = check_transcript(pairs)
    print("\n-- 逐字稿檢查 --")
    for k, (ok, detail) in tr_checks.items():
        print(f"  [{'✓' if ok else '✗'}] {k}  ({detail})")

    return {"post_id": post_id, "post": post, "prompt_sent": prompt_sent, "cm": cm,
            "system": system, "info": info, "seed": seed, "note": target["note"],
            "pairs": pairs, "ccd_checks": ccd_checks, "tr_checks": tr_checks,
            "dry": dry}


def write_md(r: dict) -> Path:
    cm = r["cm"]
    tag = "DRY-RUN(未打 API)" if r["dry"] else CHAT_MODEL
    L = [
        f"# post `{r['post_id']}` 完整流程測試",
        "",
        f"- 測試內容:{r['note']}",
        f"- CCD 模型:`gpt-4o` · 對話模型:`{tag}` · prompt_version:"
        f"`{cm.get('prompt_version')}`",
        f"- 隨機問題 seed:`{r['seed']}`(可重現)",
        f"- CCD 生成:{r['info'].get('latency', 0):.1f}s · "
        f"{r['info'].get('total_tokens')} tokens",
        "",
        "## ① 原始 post", "", "```", r["post"], "```", "",
        "## ② 送給 gpt-4o 的 CCD 建構 prompt(全文)", "", "```", r["prompt_sent"], "```", "",
        "## ③ 回傳的 CCD(原始 JSON)", "",
        "```json", json.dumps(cm, ensure_ascii=False, indent=2), "```", "",
        "## ④ CCD 9 格文字(UI 的 CCD profile)", "", "```", pc.cm_to_text(cm), "```", "",
        "## ⑤ 自動檢查", "",
        "| 檢查項 | 結果 | 說明 |", "|---|---|---|",
    ]
    for k, (ok, detail) in {**r["ccd_checks"], **r["tr_checks"]}.items():
        L.append(f"| {k} | {'✅' if ok else '❌'} | {detail} |")
    L += ["", "## ⑥ 隨機自由訪談逐字稿", ""]
    for q, a in r["pairs"]:
        L += [f"**You:** {q}", "", f"> **[{r['post_id']}]:** {a}", ""]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{r['post_id']}__{'dryrun' if r['dry'] else CHAT_MODEL}.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="不打 API,用假 client 驗流程")
    args = ap.parse_args()

    if args.dry_run:
        install_fake_client()
        print("*** DRY-RUN:不會打任何 API ***")
    elif not __import__("os").environ.get("OPENAI_API_KEY"):
        raise SystemExit(
            "找不到 OPENAI_API_KEY。請在 repo 根目錄建 .env(內容 OPENAI_API_KEY=sk-...),"
            "或用 --dry-run 空跑。")

    results = [run_one(t, args.dry_run) for t in TARGETS]

    print(f"\n{'=' * 78}\n總結\n{'=' * 78}")
    rows = []
    for r in results:
        allchecks = {**r["ccd_checks"], **r["tr_checks"]}
        # 「insufficient 欄位數」是統計不是通過條件,不計入分母
        scored = {k: v for k, v in allchecks.items() if not k.startswith("insufficient")}
        n_ok = sum(1 for ok, _ in scored.values() if ok)
        out = write_md(r)
        rows.append((r["post_id"], r["post_id"], n_ok, len(scored), out))
        print(f"  {r['post_id']:10} 檢查 {n_ok}/{len(scored)} 通過  → {out.relative_to(REPO)}")

    failed = [(p, n) for p, n, ok, tot, _ in rows if ok < tot]
    print(f"\n{'全部檢查通過 ✅' if not failed else '有檢查未通過 ❌ → ' + str(failed)}")


if __name__ == "__main__":
    main()
