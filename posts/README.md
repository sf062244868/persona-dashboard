# posts/ — 接口 placeholder

`persona_core.py` 的 `load_post_text(post_id)` 會先找這裡的 `{id}.txt`。
把某篇 post 的全文存成對應檔名，介面選到該 post 時就會自動帶入全文。

範例：
```
posts/17.txt   ← #17 Habit Change（上次的 ★ 來源 post）
posts/12.txt   ← #12 Addiction
```

- 檔名用 `Merged_Post_List.md` 的 post 編號（1–20）。
- 找不到檔案時，介面會留空讓使用者自己貼上。
- #17 的全文上次已存在上層 `selected_post_habitchange.txt`，程式已自動映射，不必重複放。
