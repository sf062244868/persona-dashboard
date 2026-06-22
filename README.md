# 2026.06.24 — Persona Generation Interface

下週開發任務：把兩種 persona 製作方式放進同一個 Streamlit 介面。
現有檔案（上層的 `app.py` / `chat_persona.py` / `single_ccd.py`）都沒有改動，新東西都放這個資料夾。

## 內容

| 檔案 | 說明 |
|---|---|
| `persona_dashboard.py` | 兩方法 Streamlit 介面（A·B 並排、計時、token、匯出、prompt 展示） |
| `persona_core.py` | 共用後端（prompts、post 資料、cluster 接口、CCD 生成、對話），無 UI 依賴 |
| `pipeline.md` | 兩條 pipeline 的設計與討論文件 |
| `clusters/` | 接口 placeholder：之後放分群/研究方法結果 |
| `posts/` | 接口 placeholder：之後放 20 篇 post 全文（`{id}.txt`） |
| `patients_ccd/` | Method A 生成的 CCD 存檔處（自動建立） |

## 執行

```bash
cd "2026.06.24"
streamlit run persona_dashboard.py
```

需求：`.env` 內含 `OPENAI_API_KEY`（會自動讀本資料夾或上一層的 `.env`）。
依賴：`streamlit`（1.58）、`openai`（2.42）、`python-dotenv`。

## 之後要接的部分

- `load_clusters()` — 目前用 8 個人工 category 當分群，換成你們之前的研究方法時改這裡。
- `load_post_text(post_id)` — 目前找 `posts/{id}.txt`，把全文補進去就會自動帶入。

兩個函式維持回傳格式即可，UI 不用動。
