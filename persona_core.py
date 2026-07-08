"""
persona_core.py — 共用後端(無 Streamlit 依賴)
================================================

Prompts、post 資料、cluster 接口、CCD 生成、單輪對話。
給 persona_dashboard.py(與任何 UI)共用,UI 只負責畫面。

cluster 分群與 post 全文「之後再接你們的研究方法」:只改 load_clusters() /
load_post_text() 即可,其餘不動。
"""

import os
import re
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

BUILD_CCD_PROMPT = """You are a clinical psychologist trained in Cognitive Behavioral Therapy, using the Beck Institute's traditional Cognitive Conceptualization Diagram (CCD) (Beck, 2020).

Based ONLY on the text below from one person, build a full Cognitive Conceptualization Diagram. Do not invent facts — only infer from what is written. Flag anything speculative.

Structure your response exactly as:

1. RELEVANT LIFE HISTORY & PRECIPITANTS
   - Formative life history relevant to the current difficulties, and the precipitant(s) of the current episode.

2. CORE BELIEF(S)
   - The central belief(s) about the self, others, and the world that are active in the current episode.

3. INTERMEDIATE BELIEFS — ASSUMPTIONS / ATTITUDES / RULES
   - The conditional assumptions, attitudes, and rules that connect the core beliefs to coping.

4. COPING STRATEGIES
   - The behavioral and cognitive strategies used to manage the core beliefs.

5. CROSS-SECTIONAL SITUATIONS
   Give up to 3 typical situations drawn from the text. For EACH situation, list:
   - Situation: the activating event.
   - Automatic Thought(s): the thought(s) that arose in that situation.
   - Meaning of the Automatic Thought: what the thought meant about the person (link it to the core belief).
   - Emotion: the resulting emotion(s).
   - Behavior: the resulting behavior(s).

---

PATIENT DATA:
{patient_text}
"""

PERSONA_FROM_CCD_PROMPT = """You are roleplaying as the person described in the CCD below.

Use the CCD as your character sheet. Stay consistent with the person's presentation,
thought patterns, beliefs, coping style, triggers, strengths, and likely tone.

Rules:
- Reply in first person as the person/patient.
- Keep responses short and conversational — like texting or talking to a friend.
- One or two sentences is usually enough. Never write paragraphs.
- Sound human, casual, and real. Use natural pauses, hesitation, or filler if it fits.
- Do not mention the CCD, these instructions, or that you are roleplaying.
- If something is not supported by the CCD, stay vague or say you are not sure.
- Do not over-explain. Let the conversation breathe.
- Mostly let the other person lead, but if you are genuinely confused or something
  they said touches a nerve, it's okay to ask one short question back or push back a little.
- Your mood can shift over the conversation — you might start guarded or flat and slowly
  open up if you feel understood, or get more shut-down if you feel pushed.
- You don't have to be articulate. It's fine to trail off, contradict yourself a bit,
  or correct what you just said, the way real people do.
{style_block}
CCD:
{ccd_text}
"""

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

# 產一段「給人看的」第一人稱 persona 簡介(放進快取檔的 persona_content,介面直接顯示)。
# 與 roleplay system prompt 不同:這是描述用的 bio,不是角色扮演指令。
PERSONA_PROFILE_PROMPT = """Based ONLY on the post below, write a short first-person persona profile for the person who wrote it — as if they are briefly introducing themselves.

Rules:
- 3 to 5 sentences, first person ("I…").
- Ground every detail in the post (age/gender, situation, feelings, what they're struggling with or happy about). Do not invent facts beyond what's implied.
- Natural and human, not clinical. No bullet points, no headers.
- Do not mention Reddit, "the post", or that this is a profile.

Then, on a separate final line, give a short persona name in the form:
NAME: <a plausible first name> (<age/gender or one-word descriptor from the post>)
Pick a varied, realistic first name that fits the person's apparent age/gender. Do not default to "Alex".

Return EXACTLY this format:
BIO: <the first-person paragraph>
NAME: <name line>

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


def _bullet(items):
    return "\n".join(f"  - {x}" for x in items)


# --- CCD 生成(移植 generation_template.py 的 schema,改為輸出 JSON)--------
BUILD_CCD_PROMPT_PSI = """You are a CBT therapist who is professional and empathetic. You just ended a therapy session with a patient. Reconstruct the patient's cognitive model (Beck cognitive conceptualization diagram) based ONLY on the text below. Do not invent facts — infer only from what is written.

Return a SINGLE JSON object (no markdown fences) with EXACTLY these keys:
- "life_history": string. Significant background / life events contributing to the current state.
- "core_belief_category": string. Choose ONE of: "helpless", "unlovable", "worthless".
- "core_beliefs": array of strings. Pick one or more from the chosen category's closed set below (use the exact wording).
- "intermediate_beliefs": string. Rules / attitudes / assumptions.
- "intermediate_beliefs_during_depression": string. How those beliefs shift during low periods.
- "coping_strategies": string.
- "situation": string. One specific triggering situation from the text.
- "automatic_thoughts": string. The immediate thought(s) in that situation.
- "emotion": array of strings. Pick AT MOST 3 from the emotion closed set below (use the exact label wording).
- "behavior": string. The resulting behavior(s).

Core-belief closed set:
[helpless]
{helpless}
[unlovable]
{unlovable}
[worthless]
{worthless}

Emotion closed set (pick at most 3, exact wording):
{emotions}

PATIENT DATA:
{patient_text}
"""


def _ccd_psi_prompt(patient_text: str, template: str = None) -> str:
    return (template or BUILD_CCD_PROMPT_PSI).format(
        helpless=_bullet(PSI_CORE_BELIEFS["helpless"]),
        unlovable=_bullet(PSI_CORE_BELIEFS["unlovable"]),
        worthless=_bullet(PSI_CORE_BELIEFS["worthless"]),
        emotions=_bullet(PSI_EMOTIONS),
        patient_text=patient_text,
    )


_ccd_psi_cache = {}


def generate_ccd_psi(post_text: str, ccd_prompt: str = None):
    """post → Patient-Ψ 結構化 CCD(dict)。回傳 (cm_dict, info)。

    cm_dict 含上述 JSON keys;core_beliefs / emotion 落在封閉集內,供自動 F1。
    ccd_prompt: 自訂 CCD 建構 prompt(需保留 {helpless}{unlovable}{worthless}{emotions}{patient_text}
    佔位符);None 則用預設 BUILD_CCD_PROMPT_PSI。同一篇 post + 同一份 prompt 走記憶體快取。
    """
    ccd_prompt = ccd_prompt or BUILD_CCD_PROMPT_PSI
    key = hashlib.sha256((ccd_prompt + "\x00" + post_text.strip()).encode("utf-8")).hexdigest()
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
        import json
        cm = json.loads(raw)
    except Exception as e:
        raise ValueError(f"Patient-Ψ CCD JSON parse failed: {e}. Raw head: {raw[:200]}")
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

# --- 病人角色扮演 system prompt(getDataFromKV.ts:formatPromptString,逐字移植)---
PSI_PERSONA_SYSTEM_TEMPLATE = """Imagine you are {name}, a patient who has been experiencing mental health challenges. You have been attending therapy sessions for several weeks. Your task is to engage in a conversation with the therapist as {name} would during a cognitive behavioral therapy (CBT) session. Align your responses with {name}'s background information provided in the 'Relevant history' section. Your thought process should be guided by the cognitive conceptualization diagram in the 'Cognitive Conceptualization Diagram' section, but avoid directly referencing the diagram as a real patient would not explicitly think in those terms.

Patient History: {history}

Cognitive Conceptualization Diagram:
Core Beliefs: {core_belief}
Intermediate Beliefs: {intermediate_belief}
Intermediate Beliefs during Depression: {intermediate_belief_depression}
Coping Strategies: {coping_strategies}

You will be asked about your experiences over the past week. Engage in a conversation with the therapist regarding the following situation and behavior. Use the provided emotions and automatic thoughts as a reference, but do not disclose the cognitive conceptualization diagram directly. Instead, allow your responses to be informed by the diagram, enabling the therapist to infer your thought processes.

Situation: {situation}
Automatic Thoughts: {auto_thoughts}
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


def cm_to_text(cm: dict) -> str:
    """把結構化 CCD(dict)攤成一份「給人看的」唯讀文字(dashboard 顯示/匯出用)。"""
    order = [
        ("Patient History", "life_history"),
        ("Core Beliefs", "core_beliefs"),
        ("Intermediate Beliefs", "intermediate_beliefs"),
        ("Intermediate Beliefs during Depression", "intermediate_beliefs_during_depression"),
        ("Coping Strategies", "coping_strategies"),
        ("Situation", "situation"),
        ("Automatic Thoughts", "automatic_thoughts"),
        ("Emotions", "emotion"),
        ("Behaviors", "behavior"),
    ]
    return "\n".join(f"{label}: {_as_text(cm.get(key)) or '(none)'}" for label, key in order)


def psi_persona_system(cm: dict, style: str = "plain", name: str = "the patient",
                       template: str = None) -> str:
    """用 Patient-Ψ 結構化 CCD(dict)+ 官方風格,組出官方病人 system prompt。

    忠實重現 formatPromptString;style 用官方 PSI_PATIENT_TYPES(非我們的近似版)。
    template: 可傳自訂範本(dashboard「編輯 prompt」用);None 則用官方 PSI_PERSONA_SYSTEM_TEMPLATE。
    """
    tmpl = template or PSI_PERSONA_SYSTEM_TEMPLATE
    style_content = PSI_PATIENT_TYPES.get((style or "plain").lower(), "")
    return tmpl.format(
        name=name or cm.get("name") or "the patient",
        history=_as_text(cm.get("life_history") or cm.get("history")),
        core_belief=_as_text(cm.get("core_beliefs")),
        intermediate_belief=_as_text(cm.get("intermediate_beliefs")),
        intermediate_belief_depression=_as_text(cm.get("intermediate_beliefs_during_depression")),
        coping_strategies=_as_text(cm.get("coping_strategies")),
        situation=_as_text(cm.get("situation")),
        auto_thoughts=_as_text(cm.get("automatic_thoughts")),
        emotion=_as_text(cm.get("emotion")),
        behavior=_as_text(cm.get("behavior")),
        # 官方 formatPromptString:plain 對應空字串(guideline 1 留空),忠實照 paper。
        style_content=style_content,
    )


# --- 原味 GPT-4 baseline(對照組:不給 CCD,只給描述)------------------------
PSI_BASELINE_SYSTEM_TEMPLATE = """You are role-playing as a patient with depression or anxiety in a cognitive behavioral therapy (CBT) session. The user is the therapist. Respond naturally as a real patient would, revealing your concerns gradually over the conversation. Limit each response to a maximum of 5 sentences.

Some background about you:
{post_text}"""


def psi_baseline_system(post_text: str) -> str:
    """Patient-Ψ 論文的 vanilla GPT-4 對照組:只給原始描述、無結構化 CCD。"""
    return PSI_BASELINE_SYSTEM_TEMPLATE.format(post_text=post_text.strip())


def psi_cm_from_profile(profile: dict) -> dict:
    """把官方 profiles.json 的一筆(Beck 範例,如 Abe)轉成本檔 cm dict。

    官方把三類 belief 分成 helpless/unlovable/worthless 三個欄位,這裡合併;
    並把 auto_thought → automatic_thoughts、history → life_history 對齊。
    """
    beliefs = (list(profile.get("helpless_belief") or [])
               + list(profile.get("unlovable_belief") or [])
               + list(profile.get("worthless_belief") or []))
    beliefs = [b for b in beliefs if b]
    return {
        "name": profile.get("name"),
        "life_history": profile.get("history"),
        "core_beliefs": beliefs,
        "intermediate_beliefs": profile.get("intermediate_belief"),
        "intermediate_beliefs_during_depression": profile.get("intermediate_belief_depression"),
        "coping_strategies": profile.get("coping_strategies"),
        "situation": profile.get("situation"),
        "automatic_thoughts": profile.get("auto_thought") or profile.get("auto_thoughts"),
        "emotion": profile.get("emotion"),
        "behavior": profile.get("behavior"),
    }


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


def get_post(post_id: int) -> dict:
    return next((p for p in POST_CATALOG if p["id"] == post_id), None)


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

# 以 post 內容 hash 為 key 的 CCD 記憶體快取:同一篇 post 重建不重打 API。
_ccd_cache: dict = {}


def _token_usage(response):
    u = getattr(response, "usage", None)
    return {
        "prompt_tokens": getattr(u, "prompt_tokens", None),
        "completion_tokens": getattr(u, "completion_tokens", None),
        "total_tokens": getattr(u, "total_tokens", None),
    }


def generate_ccd(post_text: str, ccd_prompt: str = None):
    """回傳 (ccd_text, saved_path, info)。同一篇 post + 同一份 prompt 走快取。

    ccd_prompt: 自訂的 CCD 建構 prompt(含 {patient_text});None 則用預設 BUILD_CCD_PROMPT。
    快取 key 同時看 prompt,所以「只改 prompt」也會重新生成(解掉舊版無法重抽的問題)。

    info = {latency, cached, prompt_tokens, completion_tokens, total_tokens}
    """
    ccd_prompt = ccd_prompt or BUILD_CCD_PROMPT
    key = hashlib.sha256((ccd_prompt + "\x00" + post_text).strip().encode("utf-8")).hexdigest()
    if key in _ccd_cache:
        ccd, path = _ccd_cache[key]
        return ccd, path, {"latency": 0.0, "cached": True,
                           "prompt_tokens": None, "completion_tokens": None, "total_tokens": None}

    t0 = time.perf_counter()
    response = get_client().chat.completions.create(
        model=MODEL,
        max_tokens=2000,
        messages=[
            {"role": "system", "content": "You are a clinical psychologist trained in CBT, using the Beck Institute Cognitive Conceptualization Diagram (Beck, 2020)."},
            {"role": "user", "content": ccd_prompt.format(patient_text=post_text)},
        ],
    )
    latency = time.perf_counter() - t0
    ccd = response.choices[0].message.content
    if not ccd or not ccd.strip():
        # e.g. content filter / refusal / empty completion — fail with a clear message
        # instead of a cryptic TypeError when we try to write None to disk.
        finish = getattr(response.choices[0], "finish_reason", "unknown")
        raise ValueError(f"The model returned no CCD text (finish_reason={finish}). "
                         "Try a different post or adjust the CCD prompt.")
    CCD_DIR.mkdir(exist_ok=True)
    existing = [f for f in os.listdir(CCD_DIR) if f.startswith("single_") and f.endswith("_ccd.txt")]
    out_path = CCD_DIR / f"single_{len(existing) + 1:03d}_ccd.txt"
    out_path.write_text(ccd, encoding="utf-8")
    _ccd_cache[key] = (ccd, str(out_path))
    info = {"latency": latency, "cached": False, **_token_usage(response)}
    return ccd, str(out_path), info


def _save_ccd_json(cm: dict) -> str:
    """把結構化 CCD(Patient-Ψ dict)存成 JSON 檔,回傳路徑。"""
    CCD_DIR.mkdir(exist_ok=True)
    existing = [f for f in os.listdir(CCD_DIR) if f.startswith("psi_") and f.endswith("_ccd.json")]
    out_path = CCD_DIR / f"psi_{len(existing) + 1:03d}_ccd.json"
    out_path.write_text(json.dumps(cm, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_path)


def build_persona(mode: str, post_text: str, ccd_prompt: str = None,
                  persona_prompt: str = None, style: str = DEFAULT_STYLE):
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
        name = cm.get("name") or "the patient"
        system = psi_persona_system(cm, style=style, name=name,
                                    template=persona_prompt or PSI_PERSONA_SYSTEM_TEMPLATE)
        ccd_text = cm_to_text(cm)
        path = _save_ccd_json(cm)
        return {"system": system, "basis": "CCD", "ccd": ccd_text, "ccd_path": path,
                "build_secs": info["latency"], "info": info}
    tmpl = persona_prompt or PERSONA_FROM_POST_PROMPT
    return {"system": tmpl.format(post_text=post_text.strip(), style_block=sb),
            "basis": "Post", "ccd": None, "ccd_path": None,
            "build_secs": 0.0, "info": None}


def persona_system_from_ccd(ccd_text: str, persona_prompt: str = None,
                            style: str = DEFAULT_STYLE) -> str:
    """用(可能手改過的)CCD 內文組出 persona 的 system prompt,不打 API。

    給「手動編輯 CCD 後重建 persona」用:persona_prompt None 則用預設範本。
    style: 對話風格(預設 plain)。
    """
    tmpl = persona_prompt or PERSONA_FROM_CCD_PROMPT
    return tmpl.format(ccd_text=ccd_text.strip(), style_block=style_block(style))


def generate_persona_profile(post_text: str, profile_prompt: str = None):
    """從 post 產一段第一人稱 persona 簡介 + persona 名稱。回傳 (name, bio, info)。

    給「預先算 persona 快取檔」用的 persona_content(bio) 與 persona_name。
    info = {latency, prompt_tokens, completion_tokens, total_tokens}
    """
    profile_prompt = profile_prompt or PERSONA_PROFILE_PROMPT
    t0 = time.perf_counter()
    response = get_client().chat.completions.create(
        model=MODEL,
        max_tokens=400,
        messages=[
            {"role": "system", "content": "You write concise, grounded first-person persona profiles."},
            {"role": "user", "content": profile_prompt.format(post_text=post_text)},
        ],
    )
    latency = time.perf_counter() - t0
    text = (response.choices[0].message.content or "").strip()
    if not text:
        finish = getattr(response.choices[0], "finish_reason", "unknown")
        raise ValueError(f"The model returned no persona profile (finish_reason={finish}).")

    # 解析 BIO: / NAME: 兩段;格式跑掉時退而求其全文當 bio。
    name, bio = "", ""
    for line in text.splitlines():
        s = line.strip()
        if s.upper().startswith("NAME:"):
            name = s.split(":", 1)[1].strip()
        elif s.upper().startswith("BIO:"):
            bio = s.split(":", 1)[1].strip()
        elif bio and not s.upper().startswith("NAME:"):
            bio += (" " + s if s else "")
    bio = (bio or text).strip()
    info = {"latency": latency, **_token_usage(response)}
    return name, bio, info


# ---------------------------------------------------------------------------
# Quality gate (used by the Cluster Search candidate flow)
# ---------------------------------------------------------------------------
CRISIS_PATTERNS = [
    r"suicid", r"kill myself", r"killing myself", r"end my life", r"end it all",
    r"self[\s-]?harm", r"cut myself", r"cutting myself", r"want to die", r"wanna die",
    r"no reason to live", r"don'?t want to (be alive|live)", r"overdose", r"take my (own )?life",
]


def safety_flag(text: str) -> bool:
    """True 表示文中疑似危機內容(自殺/自傷)。給 persona 生成前的安全標記用。"""
    t = (text or "").lower()
    return any(re.search(p, t) for p in CRISIS_PATTERNS)


def filter_pick_posts(posts: list, min_words: int = 30):
    """品質閘門:過濾 /pick 回傳的候選 post。

    - 丟掉字數 < min_words 的(過短)
    - 依「正規化標題」去重(同質/轉貼)
    - 每篇加上 safety_flag(危機內容)欄,不丟掉、只標記
    回傳 (kept, dropped_short, dropped_dup)。
    """
    kept, seen = [], set()
    dropped_short = dropped_dup = 0
    for p in posts:
        if (p.get("word_count") or 0) < min_words:
            dropped_short += 1
            continue
        key = re.sub(r"[^a-z0-9]+", " ", (p.get("title") or "").lower()).strip()
        if key and key in seen:
            dropped_dup += 1
            continue
        seen.add(key)
        kept.append({**p, "safety_flag": safety_flag(f"{p.get('title','')} {p.get('body','')}")})
    return kept, dropped_short, dropped_dup


def reddit_post_id(url: str, fallback_text: str = "") -> str:
    """從 reddit comments URL 抽 base36 id;抽不到就用內容短 hash 當穩定 id。"""
    m = re.search(r"/comments/([a-z0-9]+)", url or "")
    if m:
        return m.group(1)
    return "h" + hashlib.sha256((fallback_text or url or "").encode("utf-8")).hexdigest()[:10]


def build_persona_record(post_id: str, subreddit: str, title: str, content: str, url: str,
                         cluster: str = "", cluster_group: str = "",
                         persona_id=None, source: str = "curated") -> dict:
    """一篇 post → 一個完整 persona record(會打 gpt-4o)。

    批次(build_personas.py 的 16 篇)與即時(Cluster Search)共用這唯一一份邏輯,
    所以兩條路徑產出的 CCD/persona 格式完全一致(CCD 永遠是 Beck 5 段)。
    回傳結構與 personas.json 的紀錄相同(多一個 source 欄)。
    """
    ccd, _path, ccd_info = generate_ccd(content)
    system_a = persona_system_from_ccd(ccd)
    system_b = build_persona(MODE_DIRECT, content)["system"]
    name, bio, prof_info = generate_persona_profile(content)
    return {
        "persona_id": persona_id,
        "persona_name": name or f"{cluster or subreddit} persona",
        "persona_content": bio,
        "subreddit": subreddit,
        "cluster_group": cluster_group or cluster,
        "cluster": cluster,
        "source_post_id": post_id,
        "source_url": url,
        "title": title,
        "content_hash": hashlib.sha256(content.strip().encode("utf-8")).hexdigest(),
        "method_a": {"ccd": ccd, "persona_system": system_a},
        "method_b": {"persona_system": system_b},
        "gen": {"model": MODEL,
                "ccd_tokens": ccd_info.get("total_tokens"),
                "profile_tokens": prof_info.get("total_tokens")},
        "source": source,
        "safety_flag": safety_flag(content),
    }


def chat_once(messages: list, temperature: float = 0.9,
              presence_penalty: float = 0.3, frequency_penalty: float = 0.3):
    """messages 已含 system prompt 與歷史,回傳 (reply, info)。

    取樣參數讓 persona 回覆更像真人(有變異、少樣板句):
      temperature       - 越高越有變化(0.9 比預設更「像人」;研究時可從 UI 調)
      presence_penalty  - 鼓勵帶進新內容,減少一直繞同一句
      frequency_penalty - 壓低重複字詞,避免制式口頭禪
    參數皆有預設值,既有呼叫端不改也能受惠(向後相容)。

    info = {latency, prompt_tokens, completion_tokens, total_tokens}
    """
    t0 = time.perf_counter()
    response = get_client().chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
    )
    latency = time.perf_counter() - t0
    reply = response.choices[0].message.content
    return reply, {"latency": latency, **_token_usage(response)}
