# Persona Pipeline — 兩種製作方式

> 原始版本 2026.06.24;2026.07.20 依 `beck-pure-string-v4` 改版重寫。
> 舊版描述的 `generate_ccd()` / `PERSONA_SYSTEM_PROMPT` / `PERSONA_DIRECT_PROMPT`
> 已不存在於 `persona_core.py`,勿再參照。

## 研究問題

中間那層 CCD 結構化,是否讓 persona 更一致、更貼近原人物?還是直接餵 post 就夠了?
Streamlit 介面讓同一篇 post 現場 A/B 對照。

## Method A — Post → CCD → Persona

```
post 原文 → generate_ccd_psi() → cm dict → psi_persona_system() → chat_once()
```

| 階段 | 實作 | prompt |
|---|---|---|
| CCD 生成 | `generate_ccd_psi()` | `BUILD_CCD_PROMPT_PSI` |
| Persona 組裝 | `psi_persona_system()` | `PSI_PERSONA_SYSTEM_TEMPLATE` |

API 參數:`model=gpt-4o`、`response_format={"type":"json_object"}`、`max_tokens=1500`。

CCD 為 5 個欄位、**全部 plain string**:

```
life_history / core_belief / intermediate_beliefs / coping_strategies / cognitive_models
```

`cognitive_models` 為 1–3 個,每個含
`situation` / `automatic_thoughts` / `meaning_of_automatic_thought` / `emotion` / `behavior`。
`cm_to_text()` 把它攤成 UI 顯示的 9 格文字。

**設計決定(已鎖定)**:無封閉集 label、無 `{"text","grounding","evidence"}` box、
無人名欄位。persona 識別一律用 `post_id`。不支援的欄位填 `insufficient information`。
不確定的推論在字串尾標 `?`。

## Method B — Post → Persona(對照組)

```
post 原文 → build_persona(MODE_DIRECT) → chat_once()
```

prompt:`PERSONA_FROM_POST_PROMPT`,跳過 CCD,直接餵原文。

兩條路徑的差異就是「有沒有經過 CCD 結構化」—— 所以任何讓原文從 CCD 欄位偷渡進
Method A 的 bug(例:2026.07 修掉的整篇 post 被塞進 `name` 欄位)都會讓對照失效。

## 已知限制

- `PSI_PERSONA_SYSTEM_TEMPLATE` 內建「病人/治療會談」框架,並要求
  "gradually reveal deeper concerns and core issues"。低困擾的 post 即使 CCD 四格
  都是 `insufficient information`,persona 仍會自行補出核心信念。詳見
  `2026.07.21` 週報第三節。
- persona 會編造 post 未涵蓋的生活細節(家庭、工作)。**此為接受的行為**,
  目標是「人設」而非逐字還原。

## 安全規則

`safety_flag()` / `CRISIS_PATTERNS` 已隨 Cluster Search 一併移除(2026.07.20),
目前 pipeline 無自動危機內容標記。若要恢復需重新設計。
