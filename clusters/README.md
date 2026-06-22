# clusters/ — 接口 placeholder

`persona_core.py` 的 `load_clusters()` 目前直接用 `Merged_Post_List.md` 的
8 個人工 category 當分群（Relationship · Family · Loneliness · Addiction · Career ·
Milestone · Habit Change · Sleep）。

之後接上「你們之前的研究方法」（embedding / 分群結果）時：

1. 把分群結果放進這個資料夾。
2. 改寫 `load_clusters()`，讓它回傳同樣的格式：

```python
{
  "cluster_0": [ {"id": int, "category": str, "title": str,
                  "summary": str, "url": str, "flagged": bool}, ... ],
  "cluster_1": [ ... ],
}
```

只要回傳格式不變，Section 3 的 UI 不用動。
