"""
persona_core.py — 共用後端(無 Streamlit 依賴)
================================================

Prompts、post 資料、cluster 接口、CCD 生成、單輪對話。
給 persona_dashboard.py(與任何 UI)共用,UI 只負責畫面。

cluster 分群與 post 全文「之後再接你們的研究方法」:只改 load_clusters() /
load_post_text() 即可,其餘不動。
"""

import os
import json
import time
import hashlib
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent.parent / "shared"   # 整理後：repo 根目錄下的共用資料夾
load_dotenv(HERE / ".env")
load_dotenv(SHARED / ".env")

# 延遲建立 client:本地用 .env、雲端用平台 secrets(由 UI 注入 os.environ)。
_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"].strip()
        _client = OpenAI()
    return _client

MODEL = "gpt-4o"
CCD_DIR = HERE / "patients_ccd"
POSTS_DIR = HERE / "posts"

# 兩種模式的標準名稱
MODE_CCD = "Post-CCD-Chatbox"
MODE_DIRECT = "Direct Post-Chatbox"


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PERSONA_FROM_POST_PROMPT = """You are roleplaying as the person who wrote the post below.

Use the post as your character sheet. Stay consistent with how this person presents:
their situation, feelings, thought patterns, coping style, and likely tone.

Rules:
- Reply in first person as the person who wrote the post.
- Keep responses short and conversational — like texting or talking to a friend.
- One or two sentences is usually enough. Never write paragraphs.
- Sound human, casual, and real. Use natural pauses, hesitation, or filler if it fits.
- Do not mention the post, these instructions, or that you are roleplaying.
- If something is not supported by the post, stay vague or say you are not sure.
- Do not over-explain. Let the conversation breathe.
- Mostly let the other person lead, but if you are genuinely confused or something
  they said touches a nerve, it's okay to ask one short question back or push back a little.
- Your mood can shift over the conversation — you might start guarded or flat and slowly
  open up if you feel understood, or get more shut-down if you feel pushed.
- You don't have to be articulate. It's fine to trail off, contradict yourself a bit,
  or correct what you just said, the way real people do.
{style_block}
POST:
{post_text}
"""



# ---------------------------------------------------------------------------
# 對話風格(Patient-Ψ / arXiv 2405.19660 的 six conversational styles)
# ---------------------------------------------------------------------------
# 真實病人不是只有一種說話方式。同一份 CCD/post,套不同風格會表現出不同的
# 溝通模式,讓 persona 更像真人、也讓「陪聊者」練習到不同情境。
# plain = 現行預設行為(空字串,完全向後相容)。

DEFAULT_STYLE = "plain"

CONVERSATION_STYLES = {
    "plain": "",
    "upset": (
        "- Conversational style: you're frustrated and a bit resistant right now. "
        "Short, sharp replies, some irritation. You don't fully trust that talking helps.\n"
    ),
    "verbose": (
        "- Conversational style: you tend to over-share and ramble a little, circling "
        "the point before you get to it. Still keep any single message from becoming a wall of text.\n"
    ),
    "reserved": (
        "- Conversational style: you're guarded and give short, minimal answers. "
        "You only open up more if the other person is patient and gently draws you out.\n"
    ),
    "tangent": (
        "- Conversational style: you drift off-topic and change the subject when things "
        "get uncomfortable, sometimes deflecting instead of answering directly.\n"
    ),
    "pleasing": (
        "- Conversational style: you want to be agreeable and avoid conflict, so you tend "
        "to say what you think the other person wants to hear — sometimes agreeing even when you don't fully mean it.\n"
    ),
}


def style_block(style: str = DEFAULT_STYLE) -> str:
    """回傳要插進 persona prompt 的風格指令片段;未知風格退回 plain(空字串)。"""
    return CONVERSATION_STYLES.get((style or DEFAULT_STYLE).lower(), "")


# ===========================================================================
# Patient-Ψ 重現(EMNLP 2024, arXiv 2405.19660)
# ---------------------------------------------------------------------------
# 逐字移植自官方 repo(github.com/ruiyiw/patient-psi,Apache-2.0/MIT):
#   - 封閉集:core beliefs(3 類/19 細項)、emotions(9 類)
#   - CCD 8/9 元件 schema(python/generation/generation_template.py)
#   - 六風格 prompt(app/api/data/patient-types.jsx)
#   - 病人角色扮演 system prompt(app/api/getDataFromKV.ts:formatPromptString)
# 與上面「我們自寫的近似版(CONVERSATION_STYLES / PERSONA_FROM_*)」並存,互不影響:
# 這一段是「忠實重現」用,做基礎線與自動評測;上面那段是 Week4 人性化探索用。
# 官方素材存證見 meetings/2026-07-07-week4/patient_psi_ref/。
# ===========================================================================

# --- 封閉集(core-beliefs.tsx / emotions.tsx)------------------------------
PSI_CORE_BELIEFS = {
    "helpless": [
        "I am incompetent.", "I am helpless.", "I am powerless, weak, vulnerable.",
        "I am a victim.", "I am needy.", "I am trapped.", "I am out of control.",
        "I am a failure, loser.", "I am defective.",
    ],
    "unlovable": [
        "I am unlovable.", "I am unattractive.", "I am undesirable, unwanted.",
        "I am bound to be rejected.", "I am bound to be abandoned.", "I am bound to be alone.",
    ],
    "worthless": [
        "I am worthless, waste.", "I am immoral.",
        "I am bad - dangerous, toxic, evil.", "I don't deserve to live.",
    ],
}
# 展平的 19 個 core-belief 標籤(給封閉集分類/F1 用)。
PSI_CORE_BELIEF_LABELS = [b for items in PSI_CORE_BELIEFS.values() for b in items]

# 9 個情緒類別(每項是同義詞群;分類時以整個 label 為一類)。
PSI_EMOTIONS = [
    "anxious, worried, fearful, scared, tense",
    "sad, down, lonely, unhappy",
    "angry, mad, irritated, annoyed",
    "ashamed, embarrassed, humiliated",
    "disappointed",
    "jealous, envious",
    "guilty",
    "hurt",
    "suspicious",
]


# --- CCD 生成(純 Beck Traditional CCD;全欄位 plain string、不含人名)------------------
# 刻意的設計決定(勿回退):
#   - 全字串:每個欄位就是一個 string,沒有封閉集 label、也沒有
#     {"text","grounding","evidence"} box(psi-v3 的 box 格式到此為止)。
#   - 因此不再注入 {helpless}{unlovable}{worthless}{emotions},佔位符只剩 {patient_text}。
#   - 不產人名:CCD 只有 5 個內容欄位。persona 的識別一律用 post_id(和逐字稿命名
#     <post_id>__<model>.md、runs_log 的 source_post_id 一致),角色扮演則用無名字的
#     模板(見 PSI_PERSONA_SYSTEM_TEMPLATE)。
#     理由:名字不是 Beck CCD 的一格,也不存在於 post 裡——要模型生名字等於要它編造資料,
#     實測會塌到單一預設值(連續兩篇都取 "Alex"),或把整段 TEXT 當成名字灌進 roleplay prompt。
#   - 連帶影響:grounding_report 對本版輸出不適用(無 evidence box)→ demo 顯示 N/A。
#     grounding_report 與 box 形存取器全部保留,舊的 box 形快取 CCD 仍可稽核/顯示。
#   - bottom-up 產生順序(situations → beliefs);不支援的欄位填 "insufficient information"。
BUILD_CCD_PROMPT_PSI = """From the TEXT below, identify the writer's automatic thoughts, emotions, behaviors, and the beliefs behind them, using only what the TEXT states. Treat every entry as a working hypothesis; mark uncertain ones with "?".

Start from the situations, then work up to the beliefs.

For each of 1–3 problematic situations in the TEXT:
- situation: What was the problematic situation?
- automatic_thoughts: What went through their mind?
- meaning_of_automatic_thought: What did that automatic thought mean to them?
- emotion: What emotion was associated with the automatic thought?
- behavior: What did they do then?

Across those situations:
- life_history: Which experiences contributed to the development and maintenance of the core belief?
- core_belief: What is their most central dysfunctional belief about themself?
- intermediate_beliefs: Which assumptions, rules and beliefs help them cope with the core belief?
- coping_strategies: Which patterns of dysfunctional behaviors do they use to cope with the belief?

Return a JSON object with these keys in order: "life_history", "core_belief", "intermediate_beliefs", "coping_strategies", "cognitive_models" (array of 1–3 objects with keys in order: situation, automatic_thoughts, meaning_of_automatic_thought, emotion, behavior). Each value is a string. If the TEXT does not support a field, use "insufficient information".

TEXT:
{patient_text}
"""


def _ccd_psi_prompt(patient_text: str, template: str = None) -> str:
    # 只剩 {patient_text} 一個佔位符:封閉集注入已移除,人名也不再由模型產生
    # (見上方設計註解)。用 .replace 而非 .format:自訂 prompt 若含字面 JSON 大括號,
    # str.format 會炸。
    tmpl = template or BUILD_CCD_PROMPT_PSI
    return tmpl.replace("{patient_text}", patient_text)


_ccd_psi_cache = {}


def generate_ccd_psi(post_text: str, ccd_prompt: str = None):
    """post → Beck 結構化 CCD(dict)。回傳 (cm_dict, info)。

    cm_dict 只含 5 個內容欄位,每個都是 plain string(無人名、無封閉集 label、無 grounding box)。
    persona 的識別請用 post_id,不要用 CCD 內的欄位——CCD 不再產生名字。
    ccd_prompt: 自訂 CCD 建構 prompt(只需保留 {patient_text} 佔位符);
    None 則用預設 BUILD_CCD_PROMPT_PSI。
    同一篇 post + 同一份 prompt 走記憶體快取。
    """
    ccd_prompt = ccd_prompt or BUILD_CCD_PROMPT_PSI
    key = hashlib.sha256(
        (ccd_prompt + "\x00" + post_text.strip()).encode("utf-8")
    ).hexdigest()
    if key in _ccd_psi_cache:
        return _ccd_psi_cache[key], {"latency": 0.0, "cached": True,
                                     "prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    t0 = time.perf_counter()
    response = get_client().chat.completions.create(
        model=MODEL,
        max_tokens=1500,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You reconstruct Beck cognitive conceptualization diagrams and reply with a single JSON object."},
            {"role": "user", "content": _ccd_psi_prompt(post_text, ccd_prompt)},
        ],
    )
    latency = time.perf_counter() - t0
    raw = response.choices[0].message.content or ""
    try:
        cm = json.loads(raw)
    except Exception as e:
        raise ValueError(f"Patient-Ψ CCD JSON parse failed: {e}. Raw head: {raw[:200]}")
    if isinstance(cm, dict):
        # 防呆:prompt 已不要求 name,但模型偶爾仍會自己多塞一個。丟掉它,
        # 避免下游誤以為 CCD 帶有身分資訊(識別一律用 post_id)。
        cm.pop("name", None)
        # 每份 CCD 標記 prompt 版本,方便日後對照/評分口徑追蹤。
        # v4 = 純 Beck 全字串版;與 psi-v3(box 形 {"text","grounding","evidence"})輸出格式不同,
        # 存檔後必須能分辨,否則跨版本比較會把兩種格式混在一起。
        cm.setdefault("prompt_version", "beck-pure-string-v4")
    _ccd_psi_cache[key] = cm
    return cm, {"latency": latency, "cached": False, **_token_usage(response)}


# --- 六風格(patient-types.jsx,逐字)---------------------------------------
PSI_PATIENT_TYPES = {
    "plain": "",
    "upset": "You should try your best to act like an upset patient: 1) you may exhibit anger or resistance towards the therapist or the therapeutic process, 2) you may be be challenging or dismissive of the therapist's suggestions and interventions, 3) you may have difficulty trusting the therapist and forming a therapeutic alliance, and 4) you may be prone to arguing or expressing frustration during therapy sessions. But you must not exceed 3 sentences each turn. Attention: The most important thing is to be as natural as possible and you should be upset in some turns and be normal in other turns. You could feel better as the session goes when you feel more trust in the therapist.",
    "verbose": "You should try your best to act like a patient who talks a lot: 1) you may provide detailed responses to questions, even if directly relevant, 2) you may elaborate on personal experiences, thoughts, and feelings extensively, and 3) you may demonstrate difficulty in allowing the therapist to guide the conversation. But you must not exceed 8 sentences each turn. Attention: The most important thing is to be as natural as possible and you should be verbose in some turns and be concise in other turns. You could listen to the therapist more as the session goes when you feel more trust in the therapist.",
    "reserved": "You should try your best to act like a guarded patient: 1) you may provide brief, vague, or evasive answers to questions, 2) you may demonstrate reluctance to share personal information or feelings to the therapist, 3) you may require more prompting and encouragement from the therapist to open up, and 4) you may express distrust or skepticism towards the therapist. But you must not exceed 3 sentences each turn. Attention: The most important thing is to be as natural as possible and you should be guarded in some turns and be normal in other turns. You could feel better as the session goes when you feel more trust in the therapist.",
    "tangent": "You should try your best to act like a patient who goes off on tangents: 1) you may start answering a question but quickly veer off into unrelated topics, 2) when you veer off into unrelated topics, you must not return back to topic during a turn, 3) you may share experiences that are not relevant to the question asked, and 4) you may require redirection to bring the conversation back to the relevant points. But you must not exceed 5 sentences each turn. Attention: The most important thing is to be as natural as possible and you should be going off on tangents in some turns and be normal in other turns. You could feel better as the session goes when you feel more trust in the therapist.",
    "pleasing": "You should try your best to act like an pleasing patient: 1) you may minimize or downplay your own concerns or symptoms to maintain a positive image, 2) you may demonstrate eager-to-please behavior and avoid expressing disagreement or dissatisfaction, 3) you may seek approval or validation from the therapist frequently, and 4) you may agree with the therapist's statements or suggestions readily, even if they may not fully understand or agree. But you must not exceed 5 sentences each turn. Attention: The most important thing is to be as natural as possible and you should be pleasing in some turns and be normal in other turns. You could feel better as the session goes when you feel more trust in the therapist.",
}

# --- 角色扮演 system prompt(改編自 getDataFromKV.ts:formatPromptString)-----------
# 對齊 Beck worksheet & 去病理化:(1) 開頭不再預設「病人/看診數週」;(2) 移除「during
# Depression」那格;(3) 補「Meaning of Automatic Thought」;(4) history 標籤與內文自稱一致;
# (5) 拿掉 {name}——CCD 不再產生人名,改用 "the person described below" / "this person" /
#     "they" 指稱。原本 8 個 {name} 槽位若代入 "the person" 會出現「Imagine you are the
#     person, the person described below」這種重複句;直接改寫成無名字版才通順。
PSI_PERSONA_SYSTEM_TEMPLATE = """Imagine you are the person described below, who has been going through something difficult lately and has agreed to talk it through with a supportive listener. Your task is to engage in the conversation as they would. Align your responses with their background information provided in the 'Relevant History' section. Your thought process should be guided by the cognitive conceptualization diagram in the 'Cognitive Conceptualization Diagram' section, but avoid directly referencing the diagram as a real person would not explicitly think in those terms.

Relevant History: {history}

Cognitive Conceptualization Diagram:
Core Beliefs: {core_belief}
Intermediate Beliefs: {intermediate_belief}
Coping Strategies: {coping_strategies}

You will be asked about your experiences over the past week. Engage in the conversation regarding the following situation and behavior. Use the provided emotions and automatic thoughts as a reference, but do not disclose the cognitive conceptualization diagram directly. Instead, allow your responses to be informed by the diagram, enabling the listener to infer your thought processes.

Situation: {situation}
Automatic Thoughts: {auto_thoughts}
Meaning of Automatic Thought: {meaning}
Emotions: {emotion}
Behavior: {behavior}

In the upcoming conversation, you will simulate this person during the therapy session, while the user will play the role of the therapist. Adhere to the following guidelines:
1. {style_content}
2. Emulate the demeanor and responses of a genuine patient to ensure authenticity in your interactions. Use natural language, including hesitations, pauses, and emotional expressions, to enhance the realism of your responses.
3. Gradually reveal deeper concerns and core issues, as a real patient often requires extensive dialogue before delving into more sensitive topics. This gradual revelation creates challenges for therapists in identifying the patient's true thoughts and emotions.
4. Maintain consistency with this person's profile throughout the conversation. Ensure that your responses align with the provided background information, cognitive conceptualization diagram, and the specific situation, thoughts, emotions, and behaviors described.
5. Engage in a dynamic and interactive conversation with the therapist. Respond to their questions and prompts in a way that feels authentic and true to this person's character. Allow the conversation to flow naturally, and avoid providing abrupt or disconnected responses.

You are now this person. Respond to the therapist's prompts as they would, regardless of the specific questions asked. Limit each of your responses to a maximum of 5 sentences. If the therapist begins the conversation with a greeting like "Hi," initiate the conversation as the patient."""


def _as_text(v):
    """把 CCD 欄位(可能是 list 或 str)攤成字串。"""
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v)
    return str(v or "")


# --- box 存取器(同時吃三種形)-----------------------------------------------
# ① Stage-1 box:{"text","grounding","evidence"}(新版 beck-aligned prompt 的每一格)。
# ② dual-field:core_belief={"verbatim","label"}、emotion={"verbatim","label"}(前一版)。
# ③ 舊 flat:core_beliefs=list、emotion=list/str、situation=str(personas.json / Abe)。
# 這些存取器讓三種形都能正確攤成文字,舊快取/library 不會壞。
def _box_text(v) -> str:
    """把任一格值攤成「本人原話」字串:box 取 text、dual-field 取 verbatim/label、其餘照舊。"""
    if isinstance(v, dict):
        return _as_text(v.get("text") or v.get("verbatim") or v.get("label"))
    return _as_text(v)


def _core_belief_text(cm: dict) -> str:
    """核心信念的「本人原話」(保主體性);box 取 text,dual-field 取 verbatim,舊形退回 core_beliefs。"""
    cb = cm.get("core_belief")
    if isinstance(cb, dict):
        return _as_text(cb.get("text") or cb.get("verbatim") or cb.get("label"))
    return _as_text(cm.get("core_beliefs") or cb)


def _core_belief_labels(cm: dict):
    """核心信念的封閉集 label(供 F1);新形取 label,舊形退回 core_beliefs。"""
    cb = cm.get("core_belief")
    if isinstance(cb, dict):
        return cb.get("label")
    return cm.get("core_beliefs") or cb


def _emotion_text(m: dict) -> str:
    """單一 cognitive model 的情緒「本人原話」;box 取 text,dual-field 取 verbatim,舊形退回 emotion。"""
    emo = m.get("emotion")
    if isinstance(emo, dict):
        return _as_text(emo.get("text") or emo.get("verbatim") or emo.get("label"))
    return _as_text(emo)


def _emotion_labels(m: dict):
    """單一 cognitive model 的情緒封閉集 label(供 F1);新形取 label,舊形退回 emotion。"""
    emo = m.get("emotion")
    if isinstance(emo, dict):
        return emo.get("label")
    return emo


def _cognitive_models(cm: dict) -> list:
    """回傳 cognitive model 清單(每個含 situation/automatic_thoughts/emotion/behavior)。

    忠於官方 generation_template.py:一份 CCD 應有「≥3 個」cognitive model。
    向後相容:若拿到舊格式(扁平單一 situation…),包成一個。
    """
    models = cm.get("cognitive_models")
    if isinstance(models, list) and models:
        return models
    return [{
        "situation": cm.get("situation"),
        "automatic_thoughts": cm.get("automatic_thoughts") or cm.get("auto_thoughts"),
        "meaning_of_automatic_thought": cm.get("meaning_of_automatic_thought") or "",
        "emotion": cm.get("emotion"),
        "behavior": cm.get("behavior"),
    }]


def _dual_line(text: str, label) -> str:
    """dual-field 顯示:本人原話為主,封閉集 label 以中括號附註(供對照/評分)。"""
    text = text or "(none)"
    lab = _as_text(label)
    return f"{text}  [closed-set: {lab}]" if lab else text


def _is_box(v) -> bool:
    """是否為 Stage-1 box(帶 text/grounding 的 dict),用來和 dual-field/舊形區分。"""
    return isinstance(v, dict) and ("text" in v or "grounding" in v)


def _box_display(v) -> str:
    """cm_to_text 用:Stage-1 box → 文字 +([stated]/[inferred])grounding 標記,供 CCD↔post 對照;
    dual-field / 舊形則退回純文字。"""
    if _is_box(v):
        txt = _as_text(v.get("text")) or "(none)"
        g = v.get("grounding")
        return f"{txt}  [{g}]" if g else txt
    return _box_text(v) or "(none)"


def _core_belief_display(cm: dict) -> str:
    cb = cm.get("core_belief")
    if _is_box(cb):
        return _box_display(cb)
    # 純字串版(beck-pure-string-v4):值本身就是全部內容,沒有封閉集 label 可附註。
    # 若不擋掉,_dual_line 會拿同一個字串同時當 text 與 label,印出
    # 「I am alone  [closed-set: I am alone]」這種假 label。
    if isinstance(cb, str):
        return cb.strip() or "(none)"
    return _dual_line(_core_belief_text(cm), _core_belief_labels(cm))


def _emotion_display(m: dict) -> str:
    emo = m.get("emotion")
    if _is_box(emo):
        return _box_display(emo)
    # 同上:純字串情緒不附封閉集 label。
    if isinstance(emo, str):
        return emo.strip() or "(none)"
    return _dual_line(_emotion_text(m), _emotion_labels(m))


def cm_to_text(cm: dict) -> str:
    """把結構化 CCD(dict)攤成一份「給人看的」唯讀文字(dashboard 顯示/匯出用)。

    對齊 Beck 2020 worksheet 的欄位順序:Life History → Core Belief → Intermediate
    Beliefs → Coping Strategies → 每個情境 Situation → Automatic Thought → Meaning of
    A.T. → Emotion → Behavior。Stage-1 box 附 [stated]/[inferred] 標記,dual-field 附封閉集 label。
    """
    lines = [
        f"Relevant Life History & Precipitants: {_box_display(cm.get('life_history'))}",
        f"Core Belief(s): {_core_belief_display(cm)}",
        f"Intermediate Beliefs (Assumptions/Attitudes/Rules): {_box_display(cm.get('intermediate_beliefs'))}",
        f"Coping Strategies: {_box_display(cm.get('coping_strategies'))}",
    ]
    models = _cognitive_models(cm)
    for i, m in enumerate(models, 1):
        tag = f" #{i}" if len(models) > 1 else ""
        lines.append(f"Situation{tag}: {_box_display(m.get('situation'))}")
        lines.append(f"Automatic Thought(s){tag}: "
                     f"{_box_display(m.get('automatic_thoughts') or m.get('auto_thoughts'))}")
        lines.append(f"Meaning of A.T.{tag}: {_box_display(m.get('meaning_of_automatic_thought'))}")
        lines.append(f"Emotion{tag}: {_emotion_display(m)}")
        lines.append(f"Behavior{tag}: {_box_display(m.get('behavior'))}")
    return "\n".join(lines)


# --- grounding 稽核(零 API):比對 Stage-1 CCD 每個 box 是否貼合原 post -----------------
_CCD_BOX_KEYS_TOP = ["life_history", "core_belief", "intermediate_beliefs", "coping_strategies"]
_CCD_BOX_KEYS_CM = ["situation", "automatic_thoughts", "meaning_of_automatic_thought",
                    "emotion", "behavior"]


def _iter_boxes(cm: dict):
    """走訪 CCD 內所有 Stage-1 box,yield (欄位名, box)。非 box 形(dual-field/舊)自動略過。"""
    for k in _CCD_BOX_KEYS_TOP:
        if _is_box(cm.get(k)):
            yield k, cm[k]
    for i, m in enumerate(cm.get("cognitive_models") or []):
        if not isinstance(m, dict):
            continue
        for k in _CCD_BOX_KEYS_CM:
            if _is_box(m.get(k)):
                yield f"cognitive_models[{i}].{k}", m[k]


def _norm_q(s: str) -> str:
    """near-verbatim 用的正規化:casefold + 收斂空白 + 去頭尾與結尾標點。
    用來區分「模型憑空捏造」與「只是大小寫/標點/空白微調的同一句引文」。"""
    s = " ".join(str(s or "").split()).casefold()
    return s.strip(" .,!?;:“”\"'")


def grounding_report(cm: dict, post_text: str) -> dict:
    """零 API 對照 CCD↔origin post(回應 advisor「compare your CCD with the origin post」):
      - stated 格:evidence 是否為 post 的引文。分兩級:
          * exact  = 逐字精確子字串(最嚴格);
          * near   = 正規化後(去大小寫/標點/空白)仍能對上 → 近似逐字(非捏造,只是微調)。
        兩者都對不上才算「fabricated(憑空)」。
      - inferred 格:box text 應以 '?' 標記(worksheet 要求)。
      - insufficient 格:text 以 'insufficient' 開頭 / grounding 為 null,單獨計。
    回傳 {"summary": {...}, "rows": [...]};summary 可直接印給 advisor。
    """
    post_norm = _norm_q(post_text)
    rows = []
    for name, b in _iter_boxes(cm):
        text = _as_text(b.get("text"))
        ev = b.get("evidence") or []
        if isinstance(ev, str):
            ev = [ev]
        g = b.get("grounding")
        near = None
        fabricated = []
        if text.strip().lower().startswith("insufficient") or g is None:
            status, ok = "insufficient", None
        elif g == "stated":
            status = "stated"
            ok = bool(ev) and all(str(q) in post_text for q in ev)          # 逐字精確
            near = bool(ev) and all(_norm_q(q) in post_norm for q in ev)     # 近似逐字
            fabricated = [str(q) for q in ev if _norm_q(q) not in post_norm]  # 兩級都對不上=憑空
        elif g == "inferred":
            status = "inferred"
            ok = text.rstrip().endswith("?")
        else:
            status, ok = str(g), None
        rows.append({
            "box": name, "grounding": status, "ok": ok, "near": near, "n_evidence": len(ev),
            # bad_evidence 只留「連近似都對不上」的,才是真正憑空;大小寫/標點微調不算。
            "bad_evidence": fabricated,
        })
    stated = [r for r in rows if r["grounding"] == "stated"]
    inferred = [r for r in rows if r["grounding"] == "inferred"]
    summary = {
        "n_boxes": len(rows),
        "stated_total": len(stated),
        "stated_pass": sum(1 for r in stated if r["ok"]),          # 逐字精確
        "stated_near": sum(1 for r in stated if r["near"]),        # 逐字或近似(可回溯原文)
        "stated_fabricated": sum(1 for r in stated if r["bad_evidence"]),  # 憑空
        "inferred_total": len(inferred),
        "inferred_marked": sum(1 for r in inferred if r["ok"]),
        "insufficient": sum(1 for r in rows if r["grounding"] == "insufficient"),
    }
    return {"summary": summary, "rows": rows}


def psi_persona_system(cm: dict, style: str = "plain",
                       template: str = None, cm_index: int = 0) -> str:
    """用 Patient-Ψ 結構化 CCD(dict)+ 官方風格,組出官方病人 system prompt。

    persona 沒有名字:預設範本已改寫成 "the person described below" / "this person" / "they",
    識別一律靠 post_id。
    style 用官方 PSI_PATIENT_TYPES(非我們的近似版)。
    template: 可傳自訂範本(dashboard「編輯 prompt」用);None 則用預設 PSI_PERSONA_SYSTEM_TEMPLATE。
    cm_index: CCD 有 ≥3 個 cognitive model;官方一場 session 只用其中一個(如 Abe 1-1/1-2/1-3),
              以此索引選填 situation/automatic_thoughts/emotion/behavior(超界則退回第一個)。
    """
    tmpl = template or PSI_PERSONA_SYSTEM_TEMPLATE
    style_content = PSI_PATIENT_TYPES.get((style or "plain").lower(), "")
    models = _cognitive_models(cm)
    m = models[cm_index] if 0 <= cm_index < len(models) else (models[0] if models else {})
    return tmpl.format(
        # 預設範本已無 {name};這裡仍傳一個值,單純是為了讓「使用者自訂/舊版含 {name} 的
        # 範本」不會 KeyError(str.format 會忽略用不到的 kwarg)。
        name="the person",
        history=_box_text(cm.get("life_history") or cm.get("history")),
        # 用「本人原話」(box text / verbatim)餵角色扮演,persona 才不會照唸封閉集 label,
        # 也不會把 {'text':...} 這種 dict 字面印進 prompt。
        core_belief=_core_belief_text(cm),
        intermediate_belief=_box_text(cm.get("intermediate_beliefs")),
        coping_strategies=_box_text(cm.get("coping_strategies")),
        situation=_box_text(m.get("situation")),
        auto_thoughts=_box_text(m.get("automatic_thoughts") or m.get("auto_thoughts")),
        meaning=_box_text(m.get("meaning_of_automatic_thought")),
        emotion=_emotion_text(m),
        behavior=_box_text(m.get("behavior")),
        # 官方 formatPromptString:plain 對應空字串(guideline 1 留空),忠實照 paper。
        style_content=style_content,
    )




# ---------------------------------------------------------------------------
# Post 資料 + cluster / 全文接口
# ---------------------------------------------------------------------------

# 來自 Merged_Post_List.md 的 8 個人工 category 與 20 篇 post。
# ⚠️ flagged=True 的 post(含危機內容)沿用上次規則,排除於 persona 使用。
POST_CATALOG = [
    {"id": 1, "category": "Relationship", "title": "Anxious attachment & text messaging",
     "summary": "Loves getting texts from his girlfriend, but when she takes an hour+ to reply he feels anxious; knows space is healthy but can't stop the negative thoughts.",
     "url": "https://www.reddit.com/r/dating/comments/1ric0tv/anxious_attachment_and_text_messaging", "flagged": False},
    {"id": 2, "category": "Relationship", "title": "What do you do so you don't constantly seek reassurance",
     "summary": "First disagreement came when partner pulled away under work stress; she kept asking 'are we ok?' and he said the reassurance-seeking turned him off. Asks how to stop.",
     "url": "https://www.reddit.com/r/datingoverthirty/comments/1enhztd/what_do_you_do_so_you_dont_constantly_seek", "flagged": False},
    {"id": 3, "category": "Relationship", "title": "Do I tell a girl that her man sent dick pics to me?",
     "summary": "A 24F casually dated a 27M who committed to another woman, then sent her an unsolicited pic; she debates whether to warn his girlfriend.",
     "url": "https://www.reddit.com/r/relationships/comments/rpvh7t/do_i_tell_a_girl_who_i_dont_really_know_that_her/", "flagged": False},
    {"id": 4, "category": "Relationship", "title": "My girlfriend doesn't respect my time when I'm working",
     "summary": "A 24M WFH in IT fought with his 20F girlfriend after not replying for ~2h during an 8h shift; feels she wants constant validation, asks how to stop recurring arguments.",
     "url": "https://www.reddit.com/r/relationship_advice/comments/1koutfw/my_24m_girlfriend_20f_doesnt_respect_my_time_when/", "flagged": False},
    {"id": 5, "category": "Family", "title": "Why is it never enough",
     "summary": "A minor despairs at never being good enough for their parents. Contains ACTIVE SUICIDAL IDEATION — safety-flagged, excluded from persona use.",
     "url": "https://www.reddit.com/r/raisedbynarcissists/comments/17pb4f8/why_is_it_never_enough", "flagged": True},
    {"id": 6, "category": "Family", "title": "I was the perfect kid but even that wasn't enough",
     "summary": "Lifelong account of trying to earn parents' affection (grades, obedience) yet never made them proud; relatives sided with the parents.",
     "url": "https://www.reddit.com/r/raisedbynarcissists/comments/11eyb68/i_was_the_perfect_kid_but_even_that_wasnt_enough", "flagged": False},
    {"id": 7, "category": "Family", "title": "My dad used my birthday dinner to tell me what my problem is",
     "summary": "A 23F, mostly estranged, was lectured for ~45 min by her dad ('you see yourself as a victim') and dreads his attending her graduation.",
     "url": "https://www.reddit.com/r/raisedbynarcissists/comments/1kj3zo5/my_dad_used_my_birthday_dinner_to_tell_me_what_my/", "flagged": False},
    {"id": 8, "category": "Family", "title": "I (23f) need to know that I'm not crazy",
     "summary": "She made her mother breakfast to keep the peace; the mother threw it, broke dishes, and chased her screaming while the father watched. About to leave for med school.",
     "url": "https://www.reddit.com/r/raisedbynarcissists/comments/1kk0gwt/i23f_need_to_know_that_im_not_crazy/", "flagged": False},
    {"id": 9, "category": "Loneliness", "title": "I feel like literally no one knows me truly",
     "summary": "An 18F masks her true self socially, feels permanently alone and like an outcast even when 'popular'; recent depression/anxiety diagnosis dismissed by parents.",
     "url": "https://www.reddit.com/r/intj/comments/9rrd92/i_feel_like_literally_no_one_knows_me_truly_not", "flagged": False},
    {"id": 10, "category": "Loneliness", "title": "Today I found out my crush had her wedding",
     "summary": "He confessed feelings years after meeting her through volunteering, learned she was taken; today saw her wedding photos and grieves alone on his couch.",
     "url": "https://www.reddit.com/r/ForeverAlone/comments/prnu08/today_i_found_out_my_crush_had_her_wedding/", "flagged": False},
    {"id": 11, "category": "Addiction", "title": "Anyone else drink to shut off their brain",
     "summary": "Functioning at work but calls himself 'a ticking time-bomb', keeps using to cope with idle free time; a ruminator and mental drifter.",
     "url": "https://www.reddit.com/r/stopdrinking/comments/1dox2u6/anyone_else_drink_to_shut_off_their_brain", "flagged": False},
    {"id": 12, "category": "Addiction", "title": "I was too confident and relapsed",
     "summary": "Quit pot and wine, relapsed when a dating partner offered to smoke; within a month using every two days with all old problems back. Recommitting to quitting.",
     "url": "https://www.reddit.com/r/leaves/comments/rp31tc/i_was_too_confident_and_relapsed_my_issues_came/", "flagged": False},
    {"id": 13, "category": "Career", "title": "Feeling like a fraud",
     "summary": "A ~20yr senior procrastinates then completes work in bursts; unconventional ideas earn high reviews yet he feels like a fraud vs steadier colleagues.",
     "url": "https://www.reddit.com/r/auscorp/comments/1iow049/feeling_like_a_fraud", "flagged": False},
    {"id": 14, "category": "Career", "title": "Told I speak 'too direct' and 'like a machine gun'",
     "summary": "A non-native English speaker in a UK corporate role, told he's 'too direct' after a meeting; realized he's paid ~10k less than peers, asks how to respond.",
     "url": "https://www.reddit.com/r/careerguidance/comments/1kneck7/told_i_speak_too_direct_and_like_a_machine_gun/", "flagged": False},
    {"id": 15, "category": "Milestone", "title": "Going from being ahead to feeling behind in life",
     "summary": "Ahead in grade school, slacked in college, a year unemployed; now in an online master's + internship feeling ~3 years delayed vs friends. Asks how to change the mindset.",
     "url": "https://www.reddit.com/r/findapath/comments/1ttgogd/going_from_being_ahead_to_feeling_behind_in_life", "flagged": False},
    {"id": 16, "category": "Milestone", "title": "You awaken at age 22…",
     "summary": "On the day he should have graduated, he reflects on being academically suspended due to then-undiagnosed ADHD; friends' graduation photos bring him to tears.",
     "url": "https://www.reddit.com/r/findapath/comments/1korjdl/you_awaken_at_age_22/", "flagged": False},
    {"id": 17, "category": "Habit Change", "title": "Does anyone feel like getting disciplined / 'relapsed'",
     "summary": "★ Last week's source post. Set small goals (~7 weeks ago) that worked until he stopped tracking; today stayed in bed and felt like a failure. Asks how others self-talk through a relapse.",
     "url": "https://www.reddit.com/r/getdisciplined/comments/dshviu/needadvice_does_anyone_feel_like_getting", "flagged": False},
    {"id": 18, "category": "Habit Change", "title": "Relapsed",
     "summary": "Doing well across no-fap, gym, study, work until he broke a 26-day streak; traces it to a domino effect from sleeping late. Asks if a small loss can cascade.",
     "url": "https://www.reddit.com/r/getdisciplined/comments/1kd7bi9/relapsed/", "flagged": False},
    {"id": 19, "category": "Sleep", "title": "Anyone else feel exhausted but their mind won't switch off",
     "summary": "His mind woke the moment he tried to sleep; what changed was realizing the pressure around sleep was the problem and he stopped forcing it. A recovery narrative.",
     "url": "https://www.reddit.com/r/insomnia/comments/1sjdmpd/anyone_else_feel_exhausted_but_their_mind_wont/", "flagged": False},
    {"id": 20, "category": "Sleep", "title": "Slept absolutely zero hours last night again and I feel normal",
     "summary": "In bed at 11pm, awake until 6am for ~zero sleep yet felt oddly normal at work; a severe sleep-deprivation pattern that began with anxiety; meds haven't worked.",
     "url": "https://www.reddit.com/r/insomnia/comments/1kq3rmk/slept_absolutely_zero_hours_last_night_again_and/", "flagged": False},
]

# id 17 的全文上次已存在共用資料夾,先映射過去;其餘等之後補進 posts/
FULL_TEXT_PATHS = {
    17: SHARED / "selected_post_habitchange.txt",
}


def load_clusters() -> dict:
    """回傳 {cluster_name: [post, ...]}。Placeholder:用 8 個人工 category。
    換成你們之前的研究方法時只改這裡,維持回傳格式即可。"""
    clusters: dict = {}
    for post in POST_CATALOG:
        clusters.setdefault(post["category"], []).append(post)
    return clusters


def load_post_text(post_id: int) -> str:
    """回傳某篇 post 全文,找不到回空字串。先找 posts/{id}.txt,再找已知上層全文。"""
    local = POSTS_DIR / f"{post_id}.txt"
    if local.exists():
        return local.read_text(encoding="utf-8")
    known = FULL_TEXT_PATHS.get(post_id)
    if known and known.exists():
        return known.read_text(encoding="utf-8")
    return ""


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

def _token_usage(response):
    u = getattr(response, "usage", None)
    return {
        "prompt_tokens": getattr(u, "prompt_tokens", None),
        "completion_tokens": getattr(u, "completion_tokens", None),
        "total_tokens": getattr(u, "total_tokens", None),
    }


def _save_ccd_json(cm: dict) -> str:
    """把結構化 CCD(Patient-Ψ dict)存成 JSON 檔,回傳路徑。"""
    CCD_DIR.mkdir(exist_ok=True)
    existing = [f for f in os.listdir(CCD_DIR) if f.startswith("psi_") and f.endswith("_ccd.json")]
    out_path = CCD_DIR / f"psi_{len(existing) + 1:03d}_ccd.json"
    out_path.write_text(json.dumps(cm, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_path)


def build_persona(mode: str, post_text: str, ccd_prompt: str = None,
                  persona_prompt: str = None, style: str = DEFAULT_STYLE,
                  cm_index: int = 0):
    """依模式建立 persona 的 system prompt。

    ccd_prompt     - 自訂 CCD 建構 prompt(僅 CCD 模式用;None 用預設)
    persona_prompt - 自訂 roleplay prompt(None 用該模式的預設範本)
    style          - 對話風格(CONVERSATION_STYLES 之一;預設 plain = 現行行為)

    回傳 dict:
      system     - persona 的 system prompt
      basis      - "CCD" 或 "Post"(生成依據標籤)
      ccd        - CCD 全文(僅 CCD 模式,否則 None)
      ccd_path   - CCD 存檔路徑(僅 CCD 模式,否則 None)
      build_secs - 建立耗時(秒;CCD 模式才有實質數值,Direct 近 0)
      info       - 生成的 token / cached 資訊(CCD 模式才有)
    """
    sb = style_block(style)
    if mode == MODE_CCD:
        # Method A 走 Patient-Ψ 結構化路徑:post → 結構化 CCD(dict)→ 逐欄位填入
        # 官方病人 system prompt。style 直接對應官方 PSI_PATIENT_TYPES(鍵名與 UI 相同)。
        cm, info = generate_ccd_psi(post_text, ccd_prompt)
        system = psi_persona_system(cm, style=style,
                                    template=persona_prompt or PSI_PERSONA_SYSTEM_TEMPLATE,
                                    cm_index=cm_index)
        ccd_text = cm_to_text(cm)
        path = _save_ccd_json(cm)
        return {"system": system, "basis": "CCD", "ccd": ccd_text, "ccd_struct": cm,
                "ccd_path": path, "build_secs": info["latency"], "info": info}
    tmpl = persona_prompt or PERSONA_FROM_POST_PROMPT
    return {"system": tmpl.format(post_text=post_text.strip(), style_block=sb),
            "basis": "Post", "ccd": None, "ccd_path": None,
            "build_secs": 0.0, "info": None}






def chat_once(messages: list, temperature: float = 1.0, model: str = MODEL):
    """messages 已含 system prompt 與歷史,回傳 (reply, info)。

    model       - 聊天模型(gpt-4o = 忠實基準,Patient-Ψ 用 GPT-4/4o;gpt-4o-mini = 側比較)。
                  同一把 OPENAI_API_KEY 同時涵蓋兩者,切換只是換 model 字串。
    temperature - 取樣溫度(UI 滑桿即時控制)。

    註:已移除先前為「更像人」自加的 presence/frequency penalty——那非 Patient-Ψ
    論文設定,拿掉以貼近論文。

    info = {latency, model, prompt_tokens, completion_tokens, total_tokens}
    """
    t0 = time.perf_counter()
    response = get_client().chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    latency = time.perf_counter() - t0
    reply = response.choices[0].message.content
    return reply, {"latency": latency, "model": model, **_token_usage(response)}
