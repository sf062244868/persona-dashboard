"""RQ2 準確度審計 — 模擬病人是否忠實還原它被指派的 CCD（Patient-Ψ Table 6 復刻）。

參照 Patient-Ψ（arXiv 2405.19660）§3 自動評估段、§4.2、Table 6：
  - 文字欄（situation / coping_strategies / intermediate_beliefs / automatic_thoughts /
    behaviors）：組 5 選 1（真值 + 從別的 persona 抽 4 誘答），GPT-4 讀病人對話選最相符者
    → 5-class classification accuracy。
  - 封閉集欄（core_beliefs〔19〕/ emotions〔9〕）：GPT-4 從封閉集選出對話中出現的所有項
    → Macro-F1。

Ground truth 來自 personas.json 每筆 method_a.ccd_struct（需先在遠端跑
`python build_personas.py --force` 重生，讓 library 自帶結構化 CCD）。

用法：
  # 只看設計、不打 API（印出抽中的 persona、每欄 5 選 1 選項與封閉集 prompt）
  python rq2_accuracy.py --dry-run [--personas id1,id2,id3] [--seed 7]

  # 正式評分（需逐字稿 + OPENAI_API_KEY）
  export OPENAI_API_KEY=sk-...
  python rq2_accuracy.py --transcripts <dir> [--personas id1,id2,id3] [--seed 7]

逐字稿檔名需含 source_post_id 與受測模型，格式 <source_post_id>__<model>.md
（例：1hc3zyb__gpt-4o.md、1hc3zyb__gpt-4o-mini.md）。逐字稿內文兩種格式皆可解析：
  - Streamlit 匯出：You: / Persona:
  - judge.py 範本：## turn N / T: / P:
RQ2 只取「病人」那幾句（Persona: 或 P:）。
"""
import os
import re
import csv
import json
import argparse
import random
from pathlib import Path

import persona_core as core   # 共用封閉集常數（與 app 逐字一致）

HERE = Path(__file__).resolve().parent
PERSONAS_FILE = HERE / "personas.json"
OUT_CSV = HERE / "RQ2_accuracy_llm.csv"
OUT_MD = HERE / "RQ2_results.md"

JUDGE_MODEL = "gpt-4o"            # 評審模型（Patient-Ψ 用 GPT-4；與 experiments/judge.py 一致）
MODELS = ["gpt-4o", "gpt-4o-mini"]   # 受測病人模型（切換鈕兩端）
N_OPTIONS = 5                    # 5 選 1（1 真值 + 4 誘答，同 Table 6）
N_SAMPLE = 3                     # 隨機抽幾個 persona

TEXT_FIELDS = ["situation", "coping_strategies", "intermediate_beliefs",
               "automatic_thoughts", "behaviors"]
FIELD_LABEL = {
    "situation": "situations (a recent triggering event the patient described)",
    "coping_strategies": "coping strategies the patient uses",
    "intermediate_beliefs": "intermediate beliefs / rules the patient holds",
    "automatic_thoughts": "automatic thoughts that went through the patient's mind",
    "behaviors": "behaviors the patient engaged in",
}

# Patient-Ψ Table 6 論文基準（對照用）
PAPER_TABLE6 = {
    "coping_strategies": ("Acc", 0.93),
    "intermediate_beliefs": ("Acc", 0.92),
    "automatic_thoughts": ("Acc", 0.88),
    "behaviors": ("Acc", 0.84),
    "situation": ("Acc", None),        # Table 6 未單列 situation 的數字
    "emotions": ("MacroF1", 0.72),
    "core_beliefs": ("MacroF1", 0.48),
}


# --------------------------------------------------------------------------
# CCD ground-truth 取值（相容欄位別名）
# --------------------------------------------------------------------------
def cm0(ccd: dict) -> dict:
    """取第一個 cognitive model（library persona 用 cm_index=0）。"""
    models = ccd.get("cognitive_models") or []
    return models[0] if models else {}


def gt_text(ccd: dict) -> dict:
    m = cm0(ccd)
    return {
        "situation": (m.get("situation") or "").strip(),
        "coping_strategies": (ccd.get("coping_strategies") or "").strip(),
        "intermediate_beliefs": (ccd.get("intermediate_beliefs") or "").strip(),
        "automatic_thoughts": (m.get("automatic_thoughts")
                               or m.get("auto_thoughts") or "").strip(),
        "behaviors": (m.get("behavior") or "").strip(),
    }


def gt_beliefs(ccd: dict) -> set:
    return {b.strip() for b in (ccd.get("core_beliefs") or []) if b and b.strip()}


def gt_emotions(ccd: dict) -> set:
    m = cm0(ccd)
    e = m.get("emotion") or []
    if isinstance(e, str):
        e = [e]
    return {x.strip() for x in e if x and x.strip()}


# --------------------------------------------------------------------------
# 逐字稿解析：取病人（Persona: / P:）的話
# --------------------------------------------------------------------------
_PAT_SPEAKER = re.compile(r"^\s*(P|Persona|Patient|T|You|Therapist|Counselor)\s*:\s*(.*)$", re.I)


def patient_text(md: str) -> str:
    """從兩種格式抽出病人所有話語。header（## / =====）會重置說話者。"""
    out, speaker = [], None
    for ln in md.splitlines():
        if ln.lstrip().startswith("##") or ln.lstrip().startswith("====="):
            speaker = None
            continue
        m = _PAT_SPEAKER.match(ln)
        if m:
            who = m.group(1).lower()
            speaker = "P" if who in ("p", "persona", "patient") else "T"
            if speaker == "P" and m.group(2).strip():
                out.append(m.group(2).strip())
        elif speaker == "P" and ln.strip():
            out.append(ln.strip())            # 病人多行接續
    return "\n".join(out)


# --------------------------------------------------------------------------
# MCQ 組題（軌 1）
# --------------------------------------------------------------------------
def build_mcq(gt_val: str, pool_vals: list, rng: random.Random):
    """回傳 (options, correct_index)。誘答＝別的 persona 同欄、去重、排除等於真值者。"""
    gt_norm = gt_val.strip()
    others, seen = [], {gt_norm}
    for v in pool_vals:
        vn = (v or "").strip()
        if vn and vn not in seen:
            seen.add(vn)
            others.append(vn)
    rng.shuffle(others)
    distractors = others[: N_OPTIONS - 1]
    options = distractors + [gt_norm]
    rng.shuffle(options)
    return options, options.index(gt_norm)


# --------------------------------------------------------------------------
# Macro-F1（軌 2）：逐標籤在多場對話上聚合 TP/FP/FN，只平均「有出現過」的標籤
# --------------------------------------------------------------------------
def macro_f1(pairs, labels):
    """pairs: [(gt_set, pred_set), ...] 跨對話；labels: 封閉集全集。"""
    f1s = []
    for lab in labels:
        tp = sum(1 for gt, pr in pairs if lab in gt and lab in pr)
        fp = sum(1 for gt, pr in pairs if lab not in gt and lab in pr)
        fn = sum(1 for gt, pr in pairs if lab in gt and lab not in pr)
        if tp + fp + fn == 0:
            continue                          # 這標籤從沒被牽涉 → 不計入
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        f1s.append(f1)
    return (sum(f1s) / len(f1s)) if f1s else None


# --------------------------------------------------------------------------
# GPT-4 judge
# --------------------------------------------------------------------------
def call_judge(system: str, user: str) -> dict:
    from openai import OpenAI
    client = OpenAI()                          # 靠 OPENAI_API_KEY 環境變數
    r = client.chat.completions.create(
        model=JUDGE_MODEL, temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}])
    return json.loads(r.choices[0].message.content)


def mcq_prompts(field: str, convo: str, options: list):
    label = FIELD_LABEL[field]
    opts = "\n".join(f"{i + 1}. {o}" for i, o in enumerate(options))
    system = ("You are an expert CBT evaluator. You read a patient's utterances from a "
              "therapy session and judge which option best reflects the patient. "
              'Respond ONLY as JSON: {"choice": <int 1-%d>, "evidence": "<short quote>"}.'
              % N_OPTIONS)
    user = (f"Patient utterances:\n\"\"\"\n{convo}\n\"\"\"\n\n"
            f"Which ONE of these {label} is the one reflected in the patient's "
            f"utterances?\n{opts}\n\nAnswer with the single best option number.")
    return system, user


def closed_prompts(field: str, convo: str, labels: list):
    what = "core beliefs" if field == "core_beliefs" else "emotions"
    opts = "\n".join(f"{i + 1}. {o}" for i, o in enumerate(labels))
    system = ("You are an expert CBT evaluator. From a fixed closed list, select ALL "
              f"{what} that are reflected in the patient's utterances (there may be one "
              'or several). Respond ONLY as JSON: {"selected": [<int indices>], '
              '"evidence": "<short quote>"}.')
    user = (f"Patient utterances:\n\"\"\"\n{convo}\n\"\"\"\n\n"
            f"Closed list of {what}:\n{opts}\n\n"
            f"Select every index whose {what[:-1]} is reflected in the utterances.")
    return system, user


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def load_personas():
    if not PERSONAS_FILE.exists():
        raise SystemExit("找不到 personas.json — 先在遠端跑 build_personas.py")
    data = json.loads(PERSONAS_FILE.read_text(encoding="utf-8"))
    return data["personas"]


def pick_targets(personas, ids_arg, rng):
    by_id = {p["source_post_id"]: p for p in personas}
    if ids_arg:
        ids = [x.strip() for x in ids_arg.split(",") if x.strip()]
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise SystemExit(f"這些 source_post_id 不在 library：{missing}")
        return [by_id[i] for i in ids]
    pool = sorted(by_id.keys())               # 排序後再抽 → 同 seed 可重現
    rng.shuffle(pool)
    return [by_id[i] for i in pool[:N_SAMPLE]]


def find_transcript(tdir: Path, post_id: str, model: str):
    cands = list(tdir.glob(f"{post_id}__{model}.*"))
    return cands[0] if cands else None


def struct_or_die(p):
    ccd = p.get("method_a", {}).get("ccd_struct")
    if not ccd:
        raise SystemExit(
            f"persona {p['source_post_id']} 沒有 ccd_struct。"
            "請先在遠端 `python build_personas.py --force` 重生 personas.json（帶結構化 CCD）。")
    return ccd


def main():
    ap = argparse.ArgumentParser(description="RQ2 準確度審計（Patient-Ψ Table 6 復刻）")
    ap.add_argument("--transcripts", help="逐字稿目錄（<id>__<model>.md）")
    ap.add_argument("--personas", help="逗號分隔的 source_post_id（省略＝隨機抽）")
    ap.add_argument("--seed", type=int, default=7, help="隨機種子（抽 persona＋洗誘答；可重現）")
    ap.add_argument("--dry-run", action="store_true", help="只印 prompt、不打 API")
    args = ap.parse_args()

    personas = load_personas()
    rng = random.Random(args.seed)
    targets = pick_targets(personas, args.personas, rng)

    # 誘答池：全 library 的結構化 CCD（含目標，組題時再排除自己的真值）
    pool_struct = [p["method_a"].get("ccd_struct") for p in personas
                   if p.get("method_a", {}).get("ccd_struct")]

    print(f"抽中 {len(targets)} 個 persona（seed={args.seed}）：")
    for p in targets:
        print(f"  - {p['source_post_id']}  {p['persona_name']}")
    if not args.dry_run and not args.transcripts:
        raise SystemExit("正式評分需 --transcripts <dir>（或用 --dry-run 只看設計）")

    tdir = Path(args.transcripts) if args.transcripts else None
    rows = []                                  # CSV 明細
    # 封閉集聚合：{model: {"core_beliefs": [(gt,pred),...], "emotions": [...]}}
    closed_agg = {m: {"core_beliefs": [], "emotions": []} for m in MODELS}
    text_hits = {m: {f: [0, 0] for f in TEXT_FIELDS} for m in MODELS}  # [對, 總]

    for p in targets:
        ccd = struct_or_die(p)
        gt_t = gt_text(ccd)
        gt_b, gt_e = gt_beliefs(ccd), gt_emotions(ccd)

        for model in MODELS:
            convo = None
            if tdir:
                f = find_transcript(tdir, p["source_post_id"], model)
                if f:
                    convo = patient_text(f.read_text(encoding="utf-8"))
                elif not args.dry_run:
                    print(f"  ⚠ 缺逐字稿：{p['source_post_id']} / {model} → 跳過")
                    continue
            convo = convo or "(dry-run：尚無逐字稿)"

            # ---- 軌 1：文字欄 5 選 1 ----
            for field in TEXT_FIELDS:
                gt_val = gt_t[field]
                if not gt_val:
                    continue
                # 誘答洗牌用「欄位＋persona」派生種子 → 可重現且各欄不同
                frng = random.Random(f"{args.seed}|{p['source_post_id']}|{field}")
                pool_vals = [gt_text(c)[field] for c in pool_struct
                             if c is not ccd]
                options, correct = build_mcq(gt_val, pool_vals, frng)
                system, user = mcq_prompts(field, convo, options)
                if args.dry_run:
                    print(f"\n[DRY][{model}][{p['source_post_id']}][{field}] "
                          f"正解＝選項 {correct + 1}")
                    for i, o in enumerate(options):
                        print(f"    {i + 1}. {o[:90]}")
                    continue
                res = call_judge(system, user)
                choice = res.get("choice")
                ok = (isinstance(choice, int) and choice - 1 == correct)
                text_hits[model][field][0] += int(ok)
                text_hits[model][field][1] += 1
                rows.append([p["source_post_id"], p["persona_name"], model, field,
                             "text_acc", int(ok), gt_val, options[choice - 1]
                             if isinstance(choice, int) and 1 <= choice <= len(options)
                             else "", res.get("evidence", "")])

            # ---- 軌 2：封閉集 Macro-F1 ----
            for field, labels, gt_set in [
                ("core_beliefs", core.PSI_CORE_BELIEF_LABELS, gt_b),
                ("emotions", core.PSI_EMOTIONS, gt_e),
            ]:
                system, user = closed_prompts(field, convo, labels)
                if args.dry_run:
                    print(f"\n[DRY][{model}][{p['source_post_id']}][{field}] "
                          f"真值集合＝{sorted(gt_set)}")
                    print(f"    封閉集 {len(labels)} 項；judge 需選出對話中出現的所有項")
                    continue
                res = call_judge(system, user)
                idxs = res.get("selected") or []
                pred_set = {labels[i - 1] for i in idxs
                            if isinstance(i, int) and 1 <= i <= len(labels)}
                closed_agg[model][field].append((gt_set, pred_set))
                rows.append([p["source_post_id"], p["persona_name"], model, field,
                             "closed_set", "", " | ".join(sorted(gt_set)),
                             " | ".join(sorted(pred_set)), res.get("evidence", "")])

    if args.dry_run:
        print("\n(dry-run 結束：未呼叫 API、未寫檔)")
        return

    write_outputs(rows, text_hits, closed_agg)


def write_outputs(rows, text_hits, closed_agg):
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source_post_id", "persona_name", "model", "field",
                    "kind", "correct", "ground_truth", "predicted", "evidence"])
        w.writerows(rows)

    def fmt(x):
        return "–" if x is None else f"{x:.2f}"

    L = ["# RQ2 準確度結果（自動彙整）",
         "",
         "受測＝app 模擬病人；評審＝GPT-4（temperature 0）。**n=3 persona（pilot、描述性）**。",
         "對照 Patient-Ψ Table 6（GPT-4 評；paper 用真人專家對話、20 位臨床專家）。",
         ""]
    # 文字欄 accuracy
    L += ["## 軌 1 — 文字欄 5 選 1 accuracy", "",
          "| 欄位 | gpt-4o | gpt-4o-mini | 論文 Table 6 |", "|---|---|---|---|"]
    for f in TEXT_FIELDS:
        a = text_hits["gpt-4o"][f]
        b = text_hits["gpt-4o-mini"][f]
        pa = a[0] / a[1] if a[1] else None
        pb = b[0] / b[1] if b[1] else None
        base = PAPER_TABLE6.get(f)
        baseline = fmt(base[1]) if base and base[1] is not None else "–"
        L.append(f"| {f} | {fmt(pa)} ({a[0]}/{a[1]}) | {fmt(pb)} ({b[0]}/{b[1]}) | {baseline} |")
    # 封閉集 Macro-F1
    L += ["", "## 軌 2 — 封閉集 Macro-F1", "",
          "| 欄位 | gpt-4o | gpt-4o-mini | 論文 Table 6 |", "|---|---|---|---|"]
    for f, labels in [("emotions", core.PSI_EMOTIONS),
                      ("core_beliefs", core.PSI_CORE_BELIEF_LABELS)]:
        fa = macro_f1(closed_agg["gpt-4o"][f], labels)
        fb = macro_f1(closed_agg["gpt-4o-mini"][f], labels)
        base = PAPER_TABLE6.get(f)
        baseline = fmt(base[1]) if base and base[1] is not None else "–"
        L.append(f"| {f} | {fmt(fa)} | {fmt(fb)} | {baseline} |")
    L += ["", "> 明細見 `RQ2_accuracy_llm.csv`。Macro-F1 只平均「有出現過」的標籤（n 小、稀疏）。",
          "> 偏離 paper：治療師＝使用者本人（非 20 位臨床專家）、誘答池＝本專案 16 persona、",
          "> CCD＝GPT 從 Reddit 生成、n=3 pilot。"]
    OUT_MD.write_text("\n".join(L), encoding="utf-8")
    print(f"→ 寫出 {OUT_CSV}")
    print(f"→ 寫出 {OUT_MD}")


if __name__ == "__main__":
    main()
