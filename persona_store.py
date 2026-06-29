"""
persona_store.py — read/append the shared persona cache (personas.json)
=======================================================================

personas.json 是「接縫」:作者端(本機, 有 API)往裡 append,服務端(雲端)只讀。
16 篇精選是 source="curated" 的種子;Cluster Search 存的是 source="cluster-search"。
依 source_post_id 去重,不重複加。
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PERSONAS_FILE = HERE / "personas.json"


def read_personas() -> dict:
    if not PERSONAS_FILE.exists():
        return {"_meta": {}, "personas": []}
    return json.loads(PERSONAS_FILE.read_text(encoding="utf-8"))


def append_persona(record: dict):
    """加入一筆 persona;source_post_id 已存在則不重複加。回傳 (added: bool, msg)。"""
    data = read_personas()
    personas = data.get("personas", [])
    if any(p.get("source_post_id") == record.get("source_post_id") for p in personas):
        return False, "這篇已經在 Library 裡了（同一個 source_post_id）。"
    record = dict(record)
    record["persona_id"] = max((p.get("persona_id") or 0 for p in personas), default=0) + 1
    record.setdefault("source", "cluster-search")
    personas.append(record)
    data["personas"] = personas
    PERSONAS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True, f"已存入 Library（persona #{record['persona_id']}）。記得 commit + push 才會上雲端。"
