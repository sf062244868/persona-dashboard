# clusters/

Extension point for post clustering. Not wired into the app.

`persona_core.load_clusters()` groups `POST_CATALOG` by its eight hand-assigned categories
(Relationship, Family, Loneliness, Addiction, Career, Milestone, Habit Change, Sleep).

To plug in real clustering, put the results here and rewrite `load_clusters()` to return
the same shape:

```python
{
  "cluster_0": [{"id": int, "category": str, "title": str,
                 "summary": str, "url": str, "flagged": bool}],
  "cluster_1": [...],
}
```
