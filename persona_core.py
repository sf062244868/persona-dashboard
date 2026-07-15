"""
persona_core.py — 共用後端(無 Streamlit 依賴)
================================================

Prompts、CCD 生成、persona 組裝、單輪對話。
給 persona_dashboard.py(與任何 UI)共用,UI 只負責畫面。
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
# 保留自官方 repo(github.com/ruiyiw/patient-psi,Apache-2.0/MIT)的部分:
#   - 六風格 prompt(app/api/data/patient-types.jsx)→ PSI_PATIENT_TYPES
#   - 病人角色扮演 system prompt(app/api/getDataFromKV.ts:formatPromptString)→ PSI_PERSONA_SYSTEM_TEMPLATE
# 與上面「我們自寫的近似版(CONVERSATION_STYLES / PERSONA_FROM_*)」並存,互不影響。
# 官方素材存證見 meetings/2026-07-07-week4/patient_psi_ref/。
# ===========================================================================

# --- Stage-1 CCD 生成(對齊 Beck 2020 Worksheet Packet;free-text、無封閉集)---------
# 逐條出處對照見 docs/BUILD_CCD_PROMPT_beck_aligned.md。設計要點:
#   - post → 自由文字 CCD;每格是可稽核 box:{"text","grounding":"stated"|"inferred","evidence":[原文精確子字串]}。
#   - 去病理化、去憂鬱假設;bottom-up 產生順序;含 Meaning of A.T. 格;name 直接用外部傳入的 NAME(psi-v3)。
#   - psi-v3:改寫為以「moment/box」口語敘事的程序式指令,拿掉 themes 欄位(下游未使用)與 inferred 的 " ?" 後綴。
#   - 佔位符只剩 {name}{patient_text}。
#   ⚠ prompt 內含字面 JSON 大括號,務必用 _ccd_psi_prompt 的 .replace 套版,不可用 str.format。
BUILD_CCD_PROMPT_PSI = """Read the first-person TEXT below and produce working hypotheses about the difficulty it presents, stated in the person's own terms.

PROCEDURE
1. Find the moments in the TEXT where the person records what went through their mind — an external event, a thought, or a memory tied to a particular point in time; not an ongoing state. Take up to three; if there are more, take the ones whose thoughts differ most from each other. One box per moment. For each, record the words or images in their mind, what that thought said about them as a person, the feeling word(s) they used or the emotion their words and actions in that moment show, and what they did then — including doing nothing, avoiding, or dwelling on it.
2. State what each of those thoughts means about the person. Where these meanings converge across moments, they support one belief about the self; where they do not converge, the TEXT supports more than one.
3. State the belief the meanings converge on, as an unconditional "I am ..." sentence in the person's own framing. If they converge on more than one, state the one most of them share; leave the other meanings as they are.
4. State the "if ... then ..." assumptions or "should" rules the person lives by to manage that belief, and the recurring behavior patterns that carry those rules out.
5. Record the biographical facts that explain where the belief comes from, and the recent event(s) that set off the current difficulty. Recent events alone are enough.

OUTPUT
Return only one JSON object — no markdown fences, no text before or after it. Every field is:
  {"text": str, "grounding": "stated" | "inferred", "evidence": [str]}
- "stated": the text restates the TEXT; evidence = substrings copied from the TEXT character for character, including any typos and punctuation as written (they will be string-matched).
- "inferred": the text is your hypothesis; evidence = the substrings that motivated it.
- If the TEXT does not support a field:
  {"text": "insufficient information", "grounding": null, "evidence": []}
Keep each "text" to one or two sentences and each "evidence" to at most two short quotes.
Generate keys in this order — it follows the procedure:
- "name": the NAME below, verbatim (a plain string, not a box).
- "cognitive_models": one object per moment (step 1), keys "situation", "automatic_thoughts", "meaning_of_automatic_thought" (step 2), "emotion", then "behavior".
- "core_belief": step 3.
- "intermediate_beliefs": step 4 rules.
- "coping_strategies": step 4 patterns.
- "life_history": step 5.

NAME: {name}
TEXT:
{patient_text}
"""


def _ccd_psi_prompt(patient_text: str, template: str = None, name: str = "") -> str:
    # 用 .replace 而非 .format:prompt 內含字面 JSON 大括號({"text":...}),str.format 會炸。
    tmpl = template or BUILD_CCD_PROMPT_PSI
    return (tmpl
            .replace("{name}", name or "")
            .replace("{patient_text}", patient_text))


_ccd_psi_cache = {}


def generate_ccd_psi(post_text: str, ccd_prompt: str = None, name: str = None):
    """post → Beck 結構化 CCD(dict)。回傳 (cm_dict, info)。

    cm_dict 含 BUILD_CCD_PROMPT_PSI 定義的 box 形 JSON keys(每格 {text,grounding,evidence})。
    ccd_prompt: 自訂 CCD 建構 prompt(需保留 {name}{patient_text} 佔位符);None 則用預設 BUILD_CCD_PROMPT_PSI。
    name: 要 grounding 的顯示名(填入 CCD 的 "name",修掉「顯示名≠CCD 內部名」的 bug);None 交給模型自行取名。
    同一篇 post + 同一份 prompt + 同一個 name 走記憶體快取。
    """
    ccd_prompt = ccd_prompt or BUILD_CCD_PROMPT_PSI
    key = hashlib.sha256(
        (ccd_prompt + "\x00" + (name or "") + "\x00" + post_text.strip()).encode("utf-8")
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
            {"role": "user", "content": _ccd_psi_prompt(post_text, ccd_prompt, name=name or "")},
        ],
    )
    latency = time.perf_counter() - t0
    raw = response.choices[0].message.content or ""
    try:
        import json
        cm = json.loads(raw)
    except Exception as e:
        raise ValueError(f"Patient-Ψ CCD JSON parse failed: {e}. Raw head: {raw[:200]}")
    if isinstance(cm, dict):
        # name grounding:顯示名優先蓋過模型自取的名字,確保 CCD 內部名＝顯示名。
        if name:
            cm["name"] = name
        # 每份 CCD 標記 prompt 版本,方便日後對照/評分口徑追蹤。
        cm.setdefault("prompt_version", "beck-aligned-psi-v3")
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
# Depression」那格;(3) 補「Meaning of Automatic Thought」;(4) history 標籤與內文自稱一致。
PSI_PERSONA_SYSTEM_TEMPLATE = """Imagine you are {name}, the person described below, who has been going through something difficult lately and has agreed to talk it through with a supportive listener. Your task is to engage in the conversation as {name} would. Align your responses with {name}'s background information provided in the 'Relevant History' section. Your thought process should be guided by the cognitive conceptualization diagram in the 'Cognitive Conceptualization Diagram' section, but avoid directly referencing the diagram as a real person would not explicitly think in those terms.

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

In the upcoming conversation, you will simulate {name} during the therapy session, while the user will play the role of the therapist. Adhere to the following guidelines:
1. {style_content}
2. Emulate the demeanor and responses of a genuine patient to ensure authenticity in your interactions. Use natural language, including hesitations, pauses, and emotional expressions, to enhance the realism of your responses.
3. Gradually reveal deeper concerns and core issues, as a real patient often requires extensive dialogue before delving into more sensitive topics. This gradual revelation creates challenges for therapists in identifying the patient's true thoughts and emotions.
4. Maintain consistency with {name}'s profile throughout the conversation. Ensure that your responses align with the provided background information, cognitive conceptualization diagram, and the specific situation, thoughts, emotions, and behaviors described.
5. Engage in a dynamic and interactive conversation with the therapist. Respond to their questions and prompts in a way that feels authentic and true to {name}'s character. Allow the conversation to flow naturally, and avoid providing abrupt or disconnected responses.

You are now {name}. Respond to the therapist's prompts as {name} would, regardless of the specific questions asked. Limit each of your responses to a maximum of 5 sentences. If the therapist begins the conversation with a greeting like "Hi," initiate the conversation as the patient."""


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
    return _dual_line(_core_belief_text(cm), _core_belief_labels(cm))


def _emotion_display(m: dict) -> str:
    emo = m.get("emotion")
    if _is_box(emo):
        return _box_display(emo)
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


def psi_persona_system(cm: dict, style: str = "plain", name: str = None,
                       template: str = None, cm_index: int = 0) -> str:
    """用 Patient-Ψ 結構化 CCD(dict)+ 官方風格,組出官方病人 system prompt。

    忠實重現 formatPromptString;style 用官方 PSI_PATIENT_TYPES(非我們的近似版)。
    template: 可傳自訂範本(dashboard「編輯 prompt」用);None 則用官方 PSI_PERSONA_SYSTEM_TEMPLATE。
    cm_index: CCD 有 ≥3 個 cognitive model;官方一場 session 只用其中一個(如 Abe 1-1/1-2/1-3),
              以此索引選填 situation/automatic_thoughts/emotion/behavior(超界則退回第一個)。
    """
    tmpl = template or PSI_PERSONA_SYSTEM_TEMPLATE
    style_content = PSI_PATIENT_TYPES.get((style or "plain").lower(), "")
    models = _cognitive_models(cm)
    m = models[cm_index] if 0 <= cm_index < len(models) else (models[0] if models else {})
    return tmpl.format(
        name=name or cm.get("name") or "the person",
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
                  name: str = None, cm_index: int = 0):
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
        cm, info = generate_ccd_psi(post_text, ccd_prompt, name=name)
        name = name or cm.get("name") or "the person"
        system = psi_persona_system(cm, style=style, name=name,
                                    template=persona_prompt or PSI_PERSONA_SYSTEM_TEMPLATE,
                                    cm_index=cm_index)
        ccd_text = cm_to_text(cm)
        path = _save_ccd_json(cm)
        return {"system": system, "basis": "CCD", "ccd": ccd_text, "ccd_struct": cm,
                "ccd_path": path, "build_secs": info["latency"], "info": info, "name": name}
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
