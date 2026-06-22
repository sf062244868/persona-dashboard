# Persona Pipeline — 兩種製作方式（2026.06.24）

> 2026.06.18 實驗會議的延伸：把「兩種 persona 製作方式」放進同一個 Streamlit 介面對照。
> 延續上次的 CCD pipeline，不換方法；用上次的分群結果當選 post 的篩選機制。

## Method A — Post-CCD-Chatbox（延續上次）

```
Post Selection  →  CCD Processing  →  Persona Construction  →  Chatbox Interaction
```

- **CCD Processing**：`generate_ccd(post_text)` → GPT-4o 產出 8 段 CCD（Persons 2008）。
- **Persona Construction**：`PERSONA_SYSTEM_PROMPT.format(ccd_text=...)` 當 system prompt。
- **生成依據**：CCD 全文。

## Method B — Direct Post-Chatbox（本次新增的對照組）

```
Post Selection  →  Persona Construction  →  Chatbox Interaction
```

- **Persona Construction**：`PERSONA_DIRECT_PROMPT.format(post_text=...)`，跳過 CCD。
- **生成依據**：原始 post 全文。
- 語氣/規則沿用 Method A 的 persona prompt（第一人稱、簡短口語、不暴露 roleplay）。

## 實驗問題

中間那層 CCD 結構化，是否讓 persona 在長對話中**更一致、更貼近原人物**？
還是直接餵 post 就夠了？→ 介面讓人一眼看懂兩條流程，並能對同一篇 post 現場 A/B 測試。

## 之後要接的部分（先留接口）

| 接口 | 現況（placeholder） | 之後接上 |
|---|---|---|
| `load_clusters()` | Merged_Post_List.md 的 8 個人工 category | 你們之前的研究方法（embedding / 分群結果） |
| `load_post_text(post_id)` | `posts/{id}.txt` 或上層既有全文 | 20 篇 post 全文 |

只要維持回傳格式，`persona_dashboard.py` 的 UI 不用改。

## 安全規則（沿用上次）

`Merged_Post_List.md` 第 5 篇標 ⚠️（含自殺意念）→ 介面標記並停用「生成 Persona」按鈕，排除於 persona 使用。
