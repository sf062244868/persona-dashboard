"""
persona_core.py — 共用後端(無 Streamlit 依賴)
================================================

Prompts、post 資料、cluster 接口、CCD 生成、單輪對話。
給 persona_dashboard.py(與任何 UI)共用,UI 只負責畫面。

cluster 分群與 post 全文「之後再接你們的研究方法」:只改 load_clusters() /
load_post_text() 即可,其餘不動。
"""

import os
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

CCD_PROMPT = """You are a clinical psychologist trained in Cognitive Behavioral Therapy, using the Beck Institute's traditional Cognitive Conceptualization Diagram (CCD) (Beck, 2020).

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

PERSONA_SYSTEM_PROMPT = """You are roleplaying as the person described in the CCD below.

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
- Do not ask questions back. Just respond and let the other person lead.

CCD:
{ccd_text}
"""

PERSONA_DIRECT_PROMPT = """You are roleplaying as the person who wrote the post below.

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
- Do not ask questions back. Just respond and let the other person lead.

POST:
{post_text}
"""


# ---------------------------------------------------------------------------
# Post 資料 + cluster / 全文接口
# ---------------------------------------------------------------------------

# 來自 Merged_Post_List.md 的 8 個人工 category 與 20 篇 post。
# ⚠️ flagged=True 的 post(含危機內容)沿用上次規則,排除於 persona 使用。
POSTS = [
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
KNOWN_FULL_TEXT = {
    17: SHARED / "selected_post_habitchange.txt",
}


def get_post(post_id: int) -> dict:
    return next((p for p in POSTS if p["id"] == post_id), None)


def load_clusters() -> dict:
    """回傳 {cluster_name: [post, ...]}。Placeholder:用 8 個人工 category。
    換成你們之前的研究方法時只改這裡,維持回傳格式即可。"""
    clusters: dict = {}
    for post in POSTS:
        clusters.setdefault(post["category"], []).append(post)
    return clusters


def load_post_text(post_id: int) -> str:
    """回傳某篇 post 全文,找不到回空字串。先找 posts/{id}.txt,再找已知上層全文。"""
    local = POSTS_DIR / f"{post_id}.txt"
    if local.exists():
        return local.read_text(encoding="utf-8")
    known = KNOWN_FULL_TEXT.get(post_id)
    if known and known.exists():
        return known.read_text(encoding="utf-8")
    return ""


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

# 以 post 內容 hash 為 key 的 CCD 記憶體快取:同一篇 post 重建不重打 API。
_ccd_cache: dict = {}


def _usage(response):
    u = getattr(response, "usage", None)
    return {
        "prompt_tokens": getattr(u, "prompt_tokens", None),
        "completion_tokens": getattr(u, "completion_tokens", None),
        "total_tokens": getattr(u, "total_tokens", None),
    }


def generate_ccd(post_text: str, ccd_prompt: str = None):
    """回傳 (ccd_text, saved_path, info)。同一篇 post + 同一份 prompt 走快取。

    ccd_prompt: 自訂的 CCD 建構 prompt(含 {patient_text});None 則用預設 CCD_PROMPT。
    快取 key 同時看 prompt,所以「只改 prompt」也會重新生成(解掉舊版無法重抽的問題)。

    info = {latency, cached, prompt_tokens, completion_tokens, total_tokens}
    """
    ccd_prompt = ccd_prompt or CCD_PROMPT
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
    CCD_DIR.mkdir(exist_ok=True)
    existing = [f for f in os.listdir(CCD_DIR) if f.startswith("single_") and f.endswith("_ccd.txt")]
    out_path = CCD_DIR / f"single_{len(existing) + 1:03d}_ccd.txt"
    out_path.write_text(ccd, encoding="utf-8")
    _ccd_cache[key] = (ccd, str(out_path))
    info = {"latency": latency, "cached": False, **_usage(response)}
    return ccd, str(out_path), info


def build_persona(mode: str, post_text: str, ccd_prompt: str = None, persona_prompt: str = None):
    """依模式建立 persona 的 system prompt。

    ccd_prompt     - 自訂 CCD 建構 prompt(僅 CCD 模式用;None 用預設)
    persona_prompt - 自訂 roleplay prompt(None 用該模式的預設範本)

    回傳 dict:
      system     - persona 的 system prompt
      basis      - "CCD" 或 "Post"(生成依據標籤)
      ccd        - CCD 全文(僅 CCD 模式,否則 None)
      ccd_path   - CCD 存檔路徑(僅 CCD 模式,否則 None)
      build_secs - 建立耗時(秒;CCD 模式才有實質數值,Direct 近 0)
      info       - 生成的 token / cached 資訊(CCD 模式才有)
    """
    if mode == MODE_CCD:
        ccd, path, info = generate_ccd(post_text, ccd_prompt)
        tmpl = persona_prompt or PERSONA_SYSTEM_PROMPT
        return {"system": tmpl.format(ccd_text=ccd.strip()),
                "basis": "CCD", "ccd": ccd, "ccd_path": path,
                "build_secs": info["latency"], "info": info}
    tmpl = persona_prompt or PERSONA_DIRECT_PROMPT
    return {"system": tmpl.format(post_text=post_text.strip()),
            "basis": "Post", "ccd": None, "ccd_path": None,
            "build_secs": 0.0, "info": None}


def persona_system_from_ccd(ccd_text: str, persona_prompt: str = None) -> str:
    """用(可能手改過的)CCD 內文組出 persona 的 system prompt,不打 API。

    給「手動編輯 CCD 後重建 persona」用:persona_prompt None 則用預設範本。
    """
    tmpl = persona_prompt or PERSONA_SYSTEM_PROMPT
    return tmpl.format(ccd_text=ccd_text.strip())


def chat_once(messages: list):
    """messages 已含 system prompt 與歷史,回傳 (reply, info)。

    info = {latency, prompt_tokens, completion_tokens, total_tokens}
    """
    t0 = time.perf_counter()
    response = get_client().chat.completions.create(model=MODEL, messages=messages)
    latency = time.perf_counter() - t0
    reply = response.choices[0].message.content
    return reply, {"latency": latency, **_usage(response)}
