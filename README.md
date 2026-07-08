# Persona Generation Interface

從 Reddit 貼文出發，用 **CBT 認知概念圖（CCD, Cognitive Conceptualization Diagram）**把一位真實敘事者轉成一個可對話的 **模擬病人 persona**，並提供 Streamlit 介面直接與其聊天。方法源頭是 **Patient‑Ψ（EMNLP 2024）**，這裡以 `gpt-4o` 在 prompt / 架構層重現，不做模型訓練。

> 線上部署：Streamlit Community Cloud（GitHub repo `sf062244868/persona-dashboard`，主程式 `persona_dashboard.py`，push 到 `main` 即自動重新部署）。

---

## 這個 app 做什麼

一個單頁、三個分頁的介面：

| 分頁 | 功能 |
|---|---|
| 🛠 **Build** | 貼一篇 post → Method A（先生成 CCD 再變 persona）或 Method B（直接生成 persona）→ 與該 persona 聊天 |
| 📚 **Persona Library** | 16 個預先烘好的 persona（`personas.json`）→ 下拉選擇 → 聊天（作者端先產、雲端只讀） |
| 🔎 **Cluster Search** | 呼叫 Felix 的 ClusterSearch API 挑 post → 走既有 CCD 推論 → 顯示 |

聊天支援 **Patient‑Ψ 六種對話風格**（plain / upset / verbose / reserved / tangent / pleasing）與取樣參數（temperature / penalty），用來做 persona 的人性化。

---

## 專案結構

```
persona-dashboard/                  ← repo root（＝ Streamlit 主程式所在，勿搬）
├── persona_dashboard.py            主程式 / Streamlit UI（三分頁）
├── persona_core.py                 後端：prompts、CCD 生成、對話、Patient‑Ψ 重現、六風格
├── persona_store.py                讀 / 追加 personas.json（作者端寫、雲端只讀）
├── ui_common.py                    共用啟動：金鑰注入 + 密碼門
├── cluster_api.py                  Felix ClusterSearch API 客戶端
├── build_personas.py               作者端 CLI：批次烘 persona 進 personas.json
│
├── personas.json                   Persona Library 資料（16 個 persona + _meta）
├── selected_posts.json             選用的來源 post
├── posts/                          post 全文（posts/{id}.txt）
├── clusters/                       分群結果接口（placeholder）
├── patients_ccd/                   Method A 生成的 CCD 存檔（執行時產生，已 gitignore）
│
├── tests/                          pytest（test_persona_core.py）
├── scripts/                        輔助腳本（ab_test.py）
├── felix_files/Phase2/             ClusterSearch 研究：notebook + 分群 assets
│
├── docs/                           文件
│   ├── DEPLOY.md                   部署 / 更新流程（Streamlit Cloud）
│   ├── pipeline.md                 兩條 pipeline 的設計說明
│   ├── ab_test_transcript.md       Method A vs B 對話實測逐字稿
│   ├── chatbot_pipeline_slide.html pipeline 簡報
│   └── archive/                    過期的自動執行報告（歷史存查）
│
├── requirements.txt                部署相依（streamlit / openai / python-dotenv）
├── requirements-dev.txt            開發相依（+ pytest）
├── .streamlit/                     config.toml（主題）+ secrets.toml.example
└── .devcontainer/                  VS Code / Codespaces 設定
```

**為什麼 runtime 檔案都在 root：**主程式用裸 import（`import persona_core`），且 `personas.json` / `selected_posts.json` 以「同資料夾相對路徑」讀取，Streamlit Cloud 的 Main file path 也鎖在 root 的 `persona_dashboard.py`。這幾個 `.py` 與資料檔綁在一起、留在 root，搬動會同時弄壞 import、資料路徑與線上部署。

---

## 快速啟動（本地）

```bash
# 需 Python 3.11
pip install -r requirements.txt

# 提供金鑰（擇一）：
#   a) 於本資料夾或上層 shared/ 放 .env，內含 OPENAI_API_KEY
#   b) 複製 .streamlit/secrets.toml.example → .streamlit/secrets.toml 填入

streamlit run persona_dashboard.py
```

- 需 `OPENAI_API_KEY`（對話 / CCD 生成用 `gpt-4o`）。
- `APP_PASSWORD`：**有設**才要求輸入密碼；本地未設則直接放行。
- 🔎 Cluster Search 另需 ClusterSearch API（預設 `http://localhost:8000`）；不用該分頁可略。

---

## Secrets / 金鑰（重要）

- **絕不進 git**：`.gitignore` 已排除 `.env` 與 `.streamlit/secrets.toml`。
- **本地**：`OPENAI_API_KEY` / `APP_PASSWORD` 放 `.env` 或 `.streamlit/secrets.toml`。
- **雲端**：在 Streamlit Cloud → Settings → Secrets 貼 TOML（範本見 `.streamlit/secrets.toml.example`）：

  ```toml
  OPENAI_API_KEY = "sk-proj-你的金鑰"
  APP_PASSWORD   = "你設的密碼"
  ```

金鑰讀取順序（`ui_common.secret()`）：先 Streamlit secrets（雲端）→ 再環境變數 / `.env`（本地）。

---

## 部署與更新

完整步驟見 **[`docs/DEPLOY.md`](docs/DEPLOY.md)**。更新只要：

```bash
git add -A && git commit -m "..." && git push   # push 到 main → Streamlit Cloud 自動重新部署
```

---

## 測試

```bash
pip install -r requirements-dev.txt
pytest tests/
```

---

## 架構重點

- **CCD → persona → chat**：`persona_core.py` 內含 Patient‑Ψ 的封閉集（emotions / core beliefs）、CCD 生成 prompt、persona system prompt 與 `chat_once()`。
- **兩條 build pipeline**：Method A（post → CCD → persona）與 Method B（post → persona 直出），設計說明見 `docs/pipeline.md`。
- **Persona Library 的「接縫」**：作者端（本機、有 API）用 `build_personas.py` 把 persona 產進 `personas.json` 並 commit/push；雲端只讀，省 API 成本、加速載入。
