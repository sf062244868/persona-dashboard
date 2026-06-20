"""
ab_test.py — 同一篇 post 跑 Method A(經 CCD)vs Method B(直接)的批次對照。
正式化自先前散在 /tmp 的版本,重用 persona_core。

用法:
  python scripts/ab_test.py --post posts/17.txt
  python scripts/ab_test.py --post posts/17.txt --turns "你最近好嗎?" "今天怎麼了?" --out result.md

需求:.env 內含 OPENAI_API_KEY。
"""

import sys
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # 讓 `import persona_core` 找得到
import persona_core as core  # noqa: E402

DEFAULT_TURNS = [
    "hey, how have you been this week?",
    "did you keep up with the routine you set?",
    "ah that sucks. what goes through your head on a day you slip up?",
    "do you think you'll get back on track?",
]


def run_chat(system: str, turns):
    messages = [{"role": "system", "content": system}]
    out = []
    for u in turns:
        messages.append({"role": "user", "content": u})
        reply, info = core.chat_once(messages)
        messages.append({"role": "assistant", "content": reply})
        out.append((u, reply, info.get("latency", 0.0)))
    return out


def main():
    ap = argparse.ArgumentParser(description="A/B 對照:同一篇 post 跑 Method A vs B")
    ap.add_argument("--post", required=True, help="post 全文檔路徑")
    ap.add_argument("--turns", nargs="*", default=DEFAULT_TURNS, help="使用者訊息(空白分隔多句)")
    ap.add_argument("--out", default=None, help="輸出 markdown 路徑(預設只印到 stdout)")
    args = ap.parse_args()

    post = Path(args.post).read_text(encoding="utf-8").strip()
    print(f"post: {args.post} ({len(post)} chars)\n")

    print("建立 Method A(CCD)…")
    a = core.build_persona(core.MODE_CCD, post)
    print(f"  CCD 建立耗時 {a['build_secs']:.1f}s\n建立 Method B(直接)…")
    b = core.build_persona(core.MODE_DIRECT, post)

    print("跑 A 對話…")
    ta = run_chat(a["system"], args.turns)
    print("跑 B 對話…")
    tb = run_chat(b["system"], args.turns)

    lines = ["# A/B 對話對照\n",
             f"- post:`{args.post}`",
             f"- Method A CCD 建立:{a['build_secs']:.1f}s\n",
             "| # | User | A · 經 CCD (⏱) | B · 直接 (⏱) |",
             "|---|------|----------------|--------------|"]
    for i, ((u, ra, la), (_, rb, lb)) in enumerate(zip(ta, tb), 1):
        ra1 = ra.replace("\n", " ").replace("|", "\\|")
        rb1 = rb.replace("\n", " ").replace("|", "\\|")
        u1 = u.replace("|", "\\|")
        lines.append(f"| {i} | {u1} | {ra1} (⏱{la:.1f}s) | {rb1} (⏱{lb:.1f}s) |")
    md = "\n".join(lines)

    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"\n已寫出:{args.out}")
    else:
        print("\n" + md)


if __name__ == "__main__":
    main()
