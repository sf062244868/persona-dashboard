# BUILD_CCD_PROMPT — Beck-aligned Stage-1 版（含出處附註）

> Stage 1 = post → 自由文字 CCD（**無封閉集**）。封閉集 label 由 Stage 2 獨立呼叫外掛。
> 對齊目標:Beck Institute *CBT Worksheet Packet* (2020),Traditional CCD 章節:
> **p.3 = Instructions|p.4 = Diagram Questions|p.5 = Diagram Example (Abe)|p.6 = Blank Worksheet**
> (頁碼為 packet 印刷頁碼,與目錄一致:「Traditional Cognitive Conceptualization Diagram…3」)

---

## 一、Prompt 全文

> 佔位符:`{name}` 填顯示名;`{patient_text}` 填 post 原文。
> 舊版的 `{helpless}{unlovable}{worthless}{emotions}` 佔位符**已移除**(Stage 1 不含封閉集)。

```
You are completing a Beck Institute (Traditional) Cognitive Conceptualization Diagram (CCD)
for the person who wrote the TEXT below, following the CBT Worksheet Packet (J. Beck, 2020),
Traditional CCD section. A CCD is a set of working hypotheses that organizes what the person
actually wrote; it is NOT a diagnosis. Do not assume depression or any disorder. If the TEXT
itself states a diagnosis or clinical fact, record it faithfully — but never add one.

GROUNDING RULES
1. The diagram must be based on specific information the person provides. Work ONLY from
   the TEXT.
2. Every CCD box is one of two kinds:
   - "stated": the box restates something the person wrote. Its "evidence" list must contain
     EXACT substrings copied verbatim from the TEXT (they will be checked by string match).
   - "inferred": a hypothesis of yours. Append " ?" to the box text — the worksheet requires
     hypotheses to be marked (e.g., with a question mark) and treated as tentative until the
     client confirms them. This person cannot confirm them, so keep every hypothesis modest
     and close to the TEXT, and still list the exact quotes that motivated it in "evidence".
3. If a box cannot be grounded at all, set its text to "insufficient information" and leave
   "evidence" empty. An honest empty box is correct; a filled ungrounded box is an error.
4. The person's self-evaluations (e.g., "I'm a burden") are BELIEF material, not biographical
   fact: they belong in the belief boxes (core belief / intermediate beliefs / meaning), never
   in life history.

ORDER OF WORK — bottom-up, as the worksheet instructs ("start midway down the page")
First identify the problematic situation(s), then the automatic thoughts, then what each
thought meant to the person; ascertaining the meaning of the automatic thoughts across the
situations should lead to your hypothesis about the core belief. Only then complete the top
boxes. Generate the JSON keys strictly in the order given below — it enforces this order
of work.

SITUATION COUNT
Choose situations in which the person displays a pattern of unhelpful behavior or in which
their automatic thoughts show common themes; if there is more than one theme, include a
situation that reflects it. One situation box per theme the TEXT actually grounds — a
single-theme post yields ONE box. Never invent situations to fill a quota.

OUTPUT
Return a SINGLE JSON object (no markdown fences). Every CCD box is an object:
  {"text": string, "grounding": "stated" | "inferred", "evidence": [exact quotes from TEXT]}
For an empty box use {"text": "insufficient information", "grounding": null, "evidence": []}.

Keys, in this exact generation order:

- "name": string. Use the NAME provided below verbatim if given; otherwise a plausible first
  name grounded in the TEXT. Never use "Alex".

- "themes": array of short strings — the distinct problematic theme(s) the TEXT grounds.

- "cognitive_models": array, ONE object per theme, each with:
    - "situation": box. "What was the problematic situation?" One specific moment or event
      from the TEXT, not a general ongoing state.
    - "automatic_thoughts": box. "What went through the person's mind?" The surface words in
      that moment. This is NOT the core belief; if the TEXT records no in-the-moment thought,
      write "insufficient information" rather than promoting a conclusion into this box.
    - "meaning_of_automatic_thought": box. "What did the automatic thought mean to them?"
      The bridge from that surface thought toward a belief about the self. Usually "inferred".
    - "emotion": box. "What emotion was associated with the automatic thought?" The feeling
      word(s) the person used or clearly implied, as free text — there is no fixed list.
    - "behavior": box. "What did the person do then?"

- "core_belief": box. "What is the person's most central dysfunctional belief about
  themself?" State it in the person's own framing, derived FROM the meanings above. This is
  almost always "inferred" (with " ?").

- "intermediate_beliefs": box. "Which assumptions, rules and attitudes help them cope with
  the core belief?" Current episode only. Include a shift in these beliefs (e.g., during a
  low period) ONLY if the TEXT itself describes one.

- "coping_strategies": box. "Which patterns of behavior do they use to cope with the
  belief(s)?"

- "life_history": box. "Which experiences contributed to the development and maintenance of
  the core belief(s)?" plus the precipitant(s) of the current difficulty. Biographical facts
  and events only. A single post often supports only the precipitants — that is acceptable.

NAME: {name}
TEXT:
{patient_text}
```

---

## 二、逐條出處附註(prompt 敘述 ↔ worksheet 位置)

> 引文皆出自 `WorksheetPacket2020Web1.pdf`。p.3 的引文取自 Instructions 的三段內文;p.4 取自 Diagram Questions 頁的格子標籤與引導問句;p.5 取自 Abe 範例的格內內容。

| # | Prompt 裡的敘述 | 依據(worksheet 原文) | 位置 |
|---|---|---|---|
| 1 | "a set of working hypotheses … it is NOT a diagnosis" | "This diagram is designed to help **you** conceptualize clients"(治療師視角的假設工具,不是給個案的結論);假設須「regard … as tentative」 | p.3 第 2、4 段 |
| 2 | "Do not assume depression or any disorder" | 表格本體**沒有**任何憂鬱專屬欄位;Abe 範例中 "During Depression:" 只是 intermediate-beliefs 格**內的 case 內容**,不是 schema 欄位 | p.4、p.6(整頁格線);p.5(intermediate 格) |
| 3 | Grounding Rule 1:"based on specific information the person provides" | "The diagram is **based on specific information that clients provide**." | p.3 第 2 段 |
| 4 | Grounding Rule 2:"inferred" 要加 " ?" | "when you make **hypotheses**, you should **indicate so (with a question mark, for example)**" | p.3 第 2 段 |
| 5 | "treated as tentative until the client confirms them. This person cannot confirm them…" | "regard your hypotheses as **tentative until directly confirmed by the client**"(pipeline 無 client 可確認 → 推論永久 tentative,是我們對此句的忠實延伸) | p.3 第 2 段 |
| 6 | ORDER OF WORK:由下往上,"start midway down the page" | "Generally, it is best to **start midway down the page**, recording problematic situations…" | p.3 第 3 段 |
| 7 | "ascertaining the meaning … should lead to your hypothesis about the core belief" | "**Ascertaining the meaning** of clients' automatic thoughts across representative situations **should lead to hypotheses about their core beliefs**." | p.3 第 3 段 |
| 8 | SITUATION COUNT:選有共同主題/不良行為模式的情境;一主題一格 | "Choose situations in which clients display a pattern of unhelpful behavior or the clients' automatic thoughts show **common themes**. **If there is more than one theme, make sure you include a situation that reflects it.**" | p.3 第 3 段 |
| 9 | 允許 >3 或 <3(數量跟主題走,不設額度) | 「三格常不夠」的原因是「particularly when clients have **several core beliefs**」→ 數量由主題/信念數決定,不是固定 3 | p.3 第 3 段(括號句) |
| 10 | 九格結構與順序(history → core → intermediate → coping → situation → AT → meaning → emotion → behavior) | 空白表與提問頁的格線本體:RELEVANT LIFE HISTORY and PRECIPITANTS / CORE BELIEF(S) / INTERMEDIATE BELIEFS: ASSUMPTIONS/ATTITUDES/RULES / COPING STRATEGIES / SITUATION / AUTOMATIC THOUGHT(S) / MEANING OF A.T. / EMOTION / BEHAVIOR | p.4、p.6 |
| 11 | "(during current episode)" 的語意 → 我們的 belief/coping 欄說明皆限定 current episode | 三個上層格的標籤都掛 "**(during current episode)**" 字樣(不是 during depression) | p.4、p.6 |
| 12 | situation 欄說明:"What was the problematic situation?" | 同字句(提問頁 SITUATION 格的引導問句) | p.4 |
| 13 | AT 欄說明:"What went through the person's mind?" | "What went through the **client's** mind?"(client→person 為本專案去病理化改寫,下同) | p.4 |
| 14 | meaning 欄說明:"What did the automatic thought mean to them?" | 同字句(MEANING OF A.T. 格引導問句) | p.4 |
| 15 | emotion 欄說明:"What emotion was associated with the automatic thought?" | 同字句(EMOTION 格引導問句) | p.4 |
| 16 | behavior 欄說明:"What did the person do then?" | "What did the **client** do then?" | p.4 |
| 17 | core belief 欄說明:"most central dysfunctional belief about themself" | "What are the client's **most central dysfunctional beliefs about themself**?" | p.4 |
| 18 | intermediate 欄說明:"assumptions, rules and attitudes help them cope with the core belief" | "Which assumptions, rules and beliefs **help them cope with the core belief**?" | p.4 |
| 19 | coping 欄說明:"patterns of behavior … to cope with the belief(s)" | "Which patterns of dysfunctional behaviors do they use to **cope with the belief(s)**?" | p.4 |
| 20 | life history 欄說明:"experiences contributed to the development and maintenance…" + precipitants | "Which experiences contributed to the **development and maintenance** of the core belief(s)?";格名本身含 "**and PRECIPITANTS**" | p.4 |
| 21 | "AT 不是 core belief;沒有當下念頭就寫 insufficient" | Abe 範例的分層示範:AT 是情境性的("What if I run out of money?"),meaning 才收斂到 "I'm a failure."(= core belief)——兩格內容**明顯不同層** | p.5(Situation #1 欄) |
| 22 | emotion 為自由文字、無固定清單 | Abe 範例 emotion 格 = "Anxious" / "Sad" / "Sad":單字自由填寫;全 packet 無情緒選單 | p.5 |
| 23 | core belief 用第一人稱、本人框架 | Abe 範例:"**I'm** incompetent/a failure."(第一人稱句式) | p.5 |
| 24 | "Include a shift … ONLY if the TEXT itself describes one"(取代舊的必填憂鬱欄) | "During Depression: (1) If I avoid challenges…" 出現在 Abe 的 intermediate 格**內文**——證明它是 instance 內容,可有可無 | p.5 |
| 25 | intermediate 格可含多條規則 | Abe 範例 intermediate 格列了多條 assumptions(非單一句) | p.5 |
| 26 | "If the TEXT itself states a diagnosis … record it faithfully" | 表頭本有 "Name: Date: **Diagnosis:**" 一列——worksheet 是臨床文件;我們的立場是「單篇貼文無法建立診斷,故不填」而非「假裝該欄不存在」 | p.4、p.5、p.6 表頭 |

### 不是出自 worksheet 的部分(工程添加,demo 時要分開講)

| 添加 | 目的 |
|---|---|
| `{"text", "grounding", "evidence"}` 的 box 物件格式、`stated/inferred` 二值、evidence 需為**原文精確子字串** | 可稽核性:讓「CCD vs origin post」能用字串比對算 grounding rate(回應老師回饋),worksheet 只要求「?」標記,未要求引文 |
| `"insufficient information"` 空值出口 | 對抗 LLM 的必填完形壓力;worksheet 的紙本格子本來就允許留白,JSON 需要顯式等價物 |
| `"themes"` key 與「JSON key 順序 = 產生順序」 | 把 p.3 的 bottom-up 工作順序**強制編碼**進生成過程(JSON 依 key 順序生成) |
| Grounding Rule 4(自我評價歸信念格) | Reddit 自述視角 ↔ worksheet 治療師視角的落差處理;worksheet 未處理此問題 |
| name grounding、禁用 "Alex" | 修 Daniel/Max bug;與 worksheet 無關 |
| 移除封閉集(兩段式) | 防 label 措辭污染 verbatim(已實證的照唸 bug);Patient-Ψ 的設計,非 Beck 的 |

---

## 三、下游接線注意(改動點)

1. **box 形狀變了**:欄位從 string / dual-field object 變成 `{text, grounding, evidence}`。既有的向後相容 accessor(`_core_belief_text` 等)要加第三種形:`.get("text")`。
2. **emotion 變 box**(自由文字,無 `label`)——Stage 2 labeler 產出的 label 建議存**旁路檔或平行 key**(如 `labels.json` 或 CCD 頂層 `"annotations"`),不要回寫進 box,維持 Stage 1 產物純淨。
3. **`generate_ccd_psi` 的 format 參數**:舊佔位符 `{helpless}{unlovable}{worthless}{emotions}` 已移除,填模板時只剩 `{name}{patient_text}`。
4. **grounding rate 腳本**(deterministic):對每個 box,`all(q in post_text for q in evidence)` → 統計 stated 格的通過率、inferred 格的 " ?" 標記率、insufficient 佔比。零 API。
5. `cm_to_text` 渲染順序**維持九格由上而下**(p.4/p.6 的版面順序)——bottom-up 只是生成順序,呈現仍照 worksheet 版面。
6. 記得每份 CCD 存 `prompt_version`(建議 `"beck-aligned-v1"`)+ `model` + `post_id`。

## 四、文字層小勘誤(引用 PDF 時避免踩雷)

p.3 的 PDF 文字層有兩處萃取瑕疵:`insufÏcient`(連字元 ligature,實為 *insufficient*)、`hebavior`(實為 *behavior*)。若你要在投影片直接引原文,注意這兩處以免被當成你打錯字。
