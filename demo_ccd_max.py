"""
demo_ccd_max.py — advisor demo: Max (Loneliness) 的 post → 新版 Beck CCD → chat
=================================================================================
針對回饋「Build CCD (A) 沒對齊 worksheet；請比對 CCD 與原 post;demo Max post & CCD
& chat + 修過的 prompt」而做。跑法:

    export OPENAI_API_KEY=sk-...
    python demo_ccd_max.py

會依序印出:
  [1] 原 post(拿來和 CCD 對照)
  [2] 修過的 CCD 建構 prompt 全文(BUILD_CCD_PROMPT_PSI)
  [3] 生成的結構化 CCD(Stage-1 box JSON + 給人看的 9-格文字)
  [3b] 對齊檢查 + [3c] grounding 稽核(本版為純字串輸出,無 evidence box → 顯示 N/A)
  [4] 幾題訪談對話,確認 persona 講話自然、貼原 post(用本人原話,不照唸封閉集)

⚠️ Max 全文請貼到 posts/1htp0xw.txt(posts_16.json 只存了截斷的摘要)。沒有該檔時
   會退回用截斷摘要,並印出警告——那樣 CCD 只能反映摘要,無法完整對照原 post。
"""

import os
import json
from pathlib import Path

import persona_core as pc

HERE = Path(__file__).resolve().parent
POST_ID = "1htp0xw"          # r/selfimprovement: How to get by with no friends and support system?
DISPLAY_NAME = POST_ID          # persona 不取名,顯示一律用 post_id

# posts_16.json 內的截斷摘要(content_complete=False)。僅作 fallback。
MAX_POST_STUB = (
    "How to get by with no friends and support system?\n\n"
    "I'm mostly by myself. Doesn't get invites to hangouts. Old high school and close "
    "friends from university have drifted..."
)


def load_max_post() -> str:
    f = HERE / "posts" / f"{POST_ID}.txt"
    if f.exists() and f.read_text(encoding="utf-8").strip():
        return f.read_text(encoding="utf-8").strip()
    print("⚠️  posts/%s.txt 不存在或為空 → 用截斷摘要 demo(請貼上 Reddit 全文以完整對照)。\n"
          % POST_ID)
    return MAX_POST_STUB


def hr(title: str):
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("請先 export OPENAI_API_KEY=sk-... 再跑(需要打 gpt-4o)。")

    post = load_max_post()

    hr("[1] 原 POST(對照用)")
    print(post)

    hr("[2] 修過的 CCD 建構 PROMPT(實際送給 gpt-4o 的全文)")
    print(pc._ccd_psi_prompt(post))

    hr("[3] 生成的 CCD")
    cm, info = pc.generate_ccd_psi(post)
    print("— 結構化 JSON —")
    print(json.dumps(cm, ensure_ascii=False, indent=2))
    print("\n— 給人看的 9-格(對齊 Beck worksheet 欄位順序)—")
    print(pc.cm_to_text(cm))

    # 幾個對照檢查點(對應 CCD_prompt_problem_summary 的問題)
    # 註:box 形(text+grounding)的斷言已移除——純字串版本刻意不產 evidence box,
    #     留著只會印出誤導的 ✗。
    hr("[3b] 對齊檢查(對照問題清單)")
    checks = {
        "CCD 不含人名(識別用 post_id)": "name" not in cm,
        "no fabricated depression field": "intermediate_beliefs_during_depression" not in cm,
        "has Meaning of A.T. field": all(
            "meaning_of_automatic_thought" in m for m in pc._cognitive_models(cm)),
        "core_belief present": bool(str(cm.get("core_belief") or "").strip()),
        "prompt_version stamped": cm.get("prompt_version") == "beck-pure-string-v4",
    }
    for k, v in checks.items():
        print(f"  [{'✓' if v else '✗'}] {k}")

    # grounding 稽核對本版不適用:純字串輸出沒有 evidence box,跑了只會印 0/0。
    # grounding_report 本身保留(舊 box 形快取 CCD 仍可用)。
    hr("[3c] Grounding 稽核(CCD vs origin post)")
    print("  Grounding/evidence audit: N/A — this CCD prompt version emits "
          "plain-string fields (no evidence boxes).")

    hr("[4] CHAT(persona 回話;確認貼原 post、講話自然)")
    build = pc.build_persona(pc.MODE_CCD, post)
    system = build["system"]
    questions = [
        "Hi, thanks for coming in today. To start, can you tell me about a specific moment "
        "this past week that was hard for you? What happened?",
        "In that moment, what went through your mind? What were you saying to yourself?",
        "And how did that make you feel emotionally? Can you name the feelings?",
        "When you felt that way, what did you do? How did you react or respond?",
    ]
    history = [{"role": "system", "content": system}]
    for q in questions:
        history.append({"role": "user", "content": q})
        reply, _ = pc.chat_once(history, model="gpt-4o")
        history.append({"role": "assistant", "content": reply})
        print(f"\nYou: {q}\nMax: {reply}")


if __name__ == "__main__":
    main()
