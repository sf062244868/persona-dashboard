"""
build_personas.py — Persona generation pipeline (run ONCE, cached)
==================================================================

讀 selected_posts.json(Felix 選的 16 篇 + 全文)→ 每篇產一個 persona →
寫 personas.json(預先算好、commit 進 repo;Streamlit 只讀這個檔,view 時不打 LLM)。

每篇 post 產出(1 post -> 1 persona):
  - persona_name        第一人稱簡介裡的人物名
  - persona_content     第一人稱 persona 簡介(介面直接顯示的描述文字)
  - method_a            Method A:Beck CCD(gpt-4o)+ 由 CCD 組的 roleplay system prompt
  - method_b            Method B:直接由 post 組的 roleplay system prompt(不打 API)

可重跑:同一篇 post(content_hash 相同)且已存在於 personas.json → 直接沿用,不重打 API。

用法:
    cd meetings/2026-06-24_week2
    python build_personas.py            # 缺的才產
    python build_personas.py --force    # 全部重產
"""

import sys
import json
import hashlib
from pathlib import Path

import persona_core as core

HERE = Path(__file__).resolve().parent
SELECTED = HERE / "selected_posts.json"
OUT = HERE / "personas.json"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def load_existing() -> dict:
    """回傳 {source_post_id: persona_record},給快取沿用。"""
    if not OUT.exists():
        return {}
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return {p["source_post_id"]: p for p in data.get("personas", [])}
    except Exception:
        return {}


def build_one(post: dict, idx: int) -> dict:
    """一篇 post → 一個完整 persona record(會打 API)。"""
    text = post["content"]

    # Method A: post → CCD → persona system prompt
    ccd, ccd_path, ccd_info = core.generate_ccd(text)
    system_a = core.persona_system_from_ccd(ccd)

    # Method B: post → persona system prompt(template fill,不打 API)
    res_b = core.build_persona(core.MODE_DIRECT, text)
    system_b = res_b["system"]

    # 第一人稱 persona 簡介 + 名稱(打 API)
    name, bio, prof_info = core.generate_persona_profile(text)

    return {
        "persona_id": idx,
        "persona_name": name or f"{post['cluster']} persona {idx}",
        "persona_content": bio,
        "subreddit": post["subreddit"],
        "cluster_group": post["cluster_group"],
        "cluster": post["cluster"],
        "source_post_id": post["post_id"],
        "source_url": post["url"],
        "title": post["title"],
        "content_hash": content_hash(text),
        "method_a": {"ccd": ccd, "persona_system": system_a},
        "method_b": {"persona_system": system_b},
        "gen": {
            "model": core.MODEL,
            "ccd_tokens": ccd_info.get("total_tokens"),
            "profile_tokens": prof_info.get("total_tokens"),
        },
    }


def _first_name(name: str) -> str:
    return name.split("(")[0].strip().split()[0].lower() if name.strip() else ""


def ensure_unique_names(personas: list) -> None:
    """persona_name 跨 16 筆要彼此不同(下拉選單才好認)。撞名才打一次 API 重配。

    單篇生成各自獨立,常會都叫 "Alex";偵測到撞名時用「一次呼叫」一口氣產 16 個
    不重複、貼合年齡性別的名字。沒撞名(例如重跑時沿用)就不打 API。
    """
    firsts = [_first_name(p["persona_name"]) for p in personas]
    if len(set(firsts)) == len(firsts):
        return  # 已全唯一

    lines = [f"{p['persona_id']}. cluster={p['cluster']} | title={p['title']} | "
             f"bio: {p['persona_content'][:140]}" for p in personas]
    prompt = (
        f"Below are {len(personas)} distinct people, each writing about their own situation. "
        "Assign each one a SHORT persona name in the form "
        "`<a realistic first name> (<age/gender or one-word descriptor grounded in their text>)`.\n"
        "Rules:\n"
        "- All first names MUST be different from each other. Use varied, realistic first names.\n"
        "- Do NOT use the name 'Alex'.\n"
        "- Match the name to the person's apparent age/gender when stated (e.g. 27F -> a woman's name).\n"
        f"- Return EXACTLY {len(personas)} lines, format: `<n>. <Name> (<descriptor>)`, no extra text.\n\n"
        + "\n".join(lines)
    )
    resp = core.get_client().chat.completions.create(
        model=core.MODEL, max_tokens=500,
        messages=[{"role": "system", "content": "You assign concise, varied, grounded persona names."},
                  {"role": "user", "content": prompt}],
    )
    import re
    names = {}
    for ln in (resp.choices[0].message.content or "").splitlines():
        m = re.match(r"\s*(\d+)\.\s*(.+)", ln.strip())
        if m:
            names[int(m.group(1))] = m.group(2).strip()
    by_id = {p["persona_id"]: p for p in personas}
    for pid, nm in names.items():
        if pid in by_id:
            by_id[pid]["persona_name"] = nm
    print(f"  🔤 重配 persona 名字以避免撞名({len(names)} 個)")


def main():
    force = "--force" in sys.argv
    if not SELECTED.exists():
        sys.exit(f"找不到 {SELECTED.name};請先產生 selected_posts.json。")

    sel = json.loads(SELECTED.read_text(encoding="utf-8"))
    posts = sel["posts"]
    existing = {} if force else load_existing()

    personas, reused, built = [], 0, 0
    for i, post in enumerate(posts, start=1):
        pid = post["post_id"]
        cached = existing.get(pid)
        if cached and cached.get("content_hash") == content_hash(post["content"]):
            cached["persona_id"] = i  # 重新編號保持與 selected 順序一致
            personas.append(cached)
            reused += 1
            print(f"  [{i:>2}/{len(posts)}] ♻️  沿用  {pid}  {post['cluster']}")
            continue
        print(f"  [{i:>2}/{len(posts)}] ⚙️  產生  {pid}  {post['cluster']} …", flush=True)
        personas.append(build_one(post, i))
        built += 1

    ensure_unique_names(personas)

    out = {
        "_meta": {
            "description": "16 pre-computed personas (1 per source post, 8 cluster themes x 2). "
                           "Streamlit reads this file and never calls the LLM at view time.",
            "source_posts": SELECTED.name,
            "method_a": "post -> Beck CCD (gpt-4o) -> roleplay persona system prompt",
            "method_b": "post -> roleplay persona system prompt (direct, no API)",
            "persona_content": "first-person persona profile (for display)",
            "model": core.MODEL,
        },
        "personas": personas,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 寫出 {OUT.name} · {len(personas)} personas（新產 {built} · 沿用 {reused}）")


if __name__ == "__main__":
    main()
