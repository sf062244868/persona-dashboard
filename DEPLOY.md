# 上線部署指南(Streamlit Community Cloud)

把 `persona_dashboard.py` 推上線,之後用網址就能開,不必開本地終端機。
推薦用 **Streamlit Community Cloud**(免費、最適合 Streamlit)。

---

## 0. 上線前一定要做(安全)

1. **把外洩的 OpenAI key 換掉**:目前 `.env` 那把曾以明文出現,請到
   <https://platform.openai.com/api-keys> 撤銷舊的、產生新的。
2. **設用量上限**:OpenAI 後台 Billing → Usage limits 設一個月上限,避免被打爆。
3. **密鑰絕不進 git**:本資料夾 `.gitignore` 已排除 `.env` 與 `.streamlit/secrets.toml`。
4. 程式已加 **密碼門檻**(`APP_PASSWORD`),上線後網頁需輸入密碼才能用。

---

## 1. 準備檔案(已幫你建好)

```
2026.06.24/
├── persona_dashboard.py        ← 主程式(部署入口)
├── persona_core.py             ← 後端
├── requirements.txt            ← 相依套件
├── .gitignore                  ← 排除密鑰
├── posts/17.txt                ← #17 全文(讓雲端也讀得到)
└── .streamlit/
    └── secrets.toml.example    ← secrets 範本(真的那份不上傳)
```

---

## 2. 推到 GitHub(需要 GitHub 帳號)

> 把 repo 根目錄設成這個 `2026.06.24` 資料夾最單純(主程式、requirements 都在根)。

```bash
cd "/home/ray/ray/filex and i/Build_Persona_Pipeline_AND_Chat_unzipped/2026.06.24"

# 第一次用 gh 要先登入(會開瀏覽器授權)
gh auth login

git init
git add .
git commit -m "Persona generation dashboard"

# 建一個 private repo 並推上去(名字可自訂)
gh repo create persona-dashboard --private --source=. --push
```

確認 GitHub 上 **看不到** `.env` / `secrets.toml`(被 .gitignore 擋掉了)。

---

## 3. 在 Streamlit Cloud 部署

1. 開 <https://share.streamlit.io> → 用 GitHub 登入。
2. **Create app** → 選剛剛的 repo、branch `main`、Main file path 填 `persona_dashboard.py`。
3. 點 **Advanced settings → Secrets**,貼上(用你自己的值):
   ```toml
   OPENAI_API_KEY = "sk-proj-你的新金鑰"
   APP_PASSWORD = "你設的密碼"
   ```
4. **Deploy**。等 1–3 分鐘,會得到一個網址,如
   `https://你的帳號-persona-dashboard.streamlit.app`。

---

## 4. 限制誰能看(建議)

App 設定 → **Settings → Sharing** → 把 "Who can view" 改成只允許特定 email,
或就靠步驟 3 的 `APP_PASSWORD` 把關。

---

## 更新流程

之後改完程式,只要:
```bash
git add . && git commit -m "update" && git push
```
Streamlit Cloud 會自動重新部署。

---

## 替代方案

- **Hugging Face Spaces**(也免費、可設 private、用 Secrets 放金鑰):新建 Space 選
  Streamlit SDK,把同樣這些檔案 push 上去,Secrets 設 `OPENAI_API_KEY` / `APP_PASSWORD`。
- 兩者程式碼完全一樣,差別只在部署平台與 secrets 介面。
