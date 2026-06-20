"""
Persona Generation Interface — 2026.06.24
=========================================

兩種 persona 製作方式放在同一個 Streamlit 介面，方便對照：

  Method A  Post-CCD-Chatbox  : Post -> CCD -> Persona -> Chatbox
  Method B  Direct Post-Chatbox: Post ->        Persona -> Chatbox

延續上次的 CCD pipeline（沿用 app.py 的 CCD_PROMPT / PERSONA_SYSTEM_PROMPT 與
generate_ccd 邏輯），新增「不經過 CCD、直接用 post 全文建 persona」的對照組。

注意：cluster 分群與 post 全文來源「之後再接」——本檔以 load_clusters() /
load_post_text() 兩個函式當接口，預設用 Merged_Post_List.md 的 8 個人工 category
與本機 posts/ 資料夾。要換成你們之前的研究方法時，只改這兩個函式即可。

執行：  streamlit run persona_interface.py
需求：  上層或本資料夾的 .env 內含 OPENAI_API_KEY
"""

import os
from pathlib import Path

import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

# .env 可能放在這個資料夾或上一層（沿用既有專案的 .env）
HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
load_dotenv(HERE.parent / ".env")
client = OpenAI()

CCD_DIR = HERE / "patients_ccd"
POSTS_DIR = HERE / "posts"


# ---------------------------------------------------------------------------
# Prompts（A/B 共用語氣，只差在「依據」是 CCD 還是 post 全文）
# ---------------------------------------------------------------------------

CCD_PROMPT = """You are a clinical psychologist trained in Cognitive Behavioral Therapy and Cognitive Case Conceptualization (Persons, 2008 model).

Based ONLY on the comments below from one person, build a full CCD. Do not invent facts — only infer from what is written. Flag anything speculative.

Structure your response exactly as:

1. PRESENTING PROBLEMS
2. AUTOMATIC THOUGHTS
3. CORE BELIEFS (about self, others, the world)
4. INTERMEDIATE BELIEFS
5. COPING BEHAVIORS
6. TRIGGERS
7. ORIGINS HYPOTHESIS
8. STRENGTHS & RESOURCES

---

PATIENT DATA:
{patient_text}
"""

# Method A：persona 以 CCD 為角色設定
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

# Method B：persona 直接以原始 post 為角色設定（跳過 CCD）
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
# 資料接口（cluster + post 全文）—— 之後接上你們的研究方法時，只改這兩個函式
# ---------------------------------------------------------------------------

# Placeholder：來自 Merged_Post_List.md 的 8 個人工 category 與 20 篇 post。
# ⚠️ flagged=True 的 post（含危機內容）沿用上次規則，排除於 persona 使用。
POSTS = [
    # Relationship
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
    # Family
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
    # Loneliness
    {"id": 9, "category": "Loneliness", "title": "I feel like literally no one knows me truly",
     "summary": "An 18F masks her true self socially, feels permanently alone and like an outcast even when 'popular'; recent depression/anxiety diagnosis dismissed by parents.",
     "url": "https://www.reddit.com/r/intj/comments/9rrd92/i_feel_like_literally_no_one_knows_me_truly_not", "flagged": False},
    {"id": 10, "category": "Loneliness", "title": "Today I found out my crush had her wedding",
     "summary": "He confessed feelings years after meeting her through volunteering, learned she was taken; today saw her wedding photos and grieves alone on his couch.",
     "url": "https://www.reddit.com/r/ForeverAlone/comments/prnu08/today_i_found_out_my_crush_had_her_wedding/", "flagged": False},
    # Addiction
    {"id": 11, "category": "Addiction", "title": "Anyone else drink to shut off their brain",
     "summary": "Functioning at work but calls himself 'a ticking time-bomb', keeps using to cope with idle free time; a ruminator and mental drifter.",
     "url": "https://www.reddit.com/r/stopdrinking/comments/1dox2u6/anyone_else_drink_to_shut_off_their_brain", "flagged": False},
    {"id": 12, "category": "Addiction", "title": "I was too confident and relapsed",
     "summary": "Quit pot and wine, relapsed when a dating partner offered to smoke; within a month using every two days with all old problems back. Recommitting to quitting.",
     "url": "https://www.reddit.com/r/leaves/comments/rp31tc/i_was_too_confident_and_relapsed_my_issues_came/", "flagged": False},
    # Career
    {"id": 13, "category": "Career", "title": "Feeling like a fraud",
     "summary": "A ~20yr senior procrastinates then completes work in bursts; unconventional ideas earn high reviews yet he feels like a fraud vs steadier colleagues.",
     "url": "https://www.reddit.com/r/auscorp/comments/1iow049/feeling_like_a_fraud", "flagged": False},
    {"id": 14, "category": "Career", "title": "Told I speak 'too direct' and 'like a machine gun'",
     "summary": "A non-native English speaker in a UK corporate role, told he's 'too direct' after a meeting; realized he's paid ~10k less than peers, asks how to respond.",
     "url": "https://www.reddit.com/r/careerguidance/comments/1kneck7/told_i_speak_too_direct_and_like_a_machine_gun/", "flagged": False},
    # Milestone
    {"id": 15, "category": "Milestone", "title": "Going from being ahead to feeling behind in life",
     "summary": "Ahead in grade school, slacked in college, a year unemployed; now in an online master's + internship feeling ~3 years delayed vs friends. Asks how to change the mindset.",
     "url": "https://www.reddit.com/r/findapath/comments/1ttgogd/going_from_being_ahead_to_feeling_behind_in_life", "flagged": False},
    {"id": 16, "category": "Milestone", "title": "You awaken at age 22…",
     "summary": "On the day he should have graduated, he reflects on being academically suspended due to then-undiagnosed ADHD; friends' graduation photos bring him to tears.",
     "url": "https://www.reddit.com/r/findapath/comments/1korjdl/you_awaken_at_age_22/", "flagged": False},
    # Habit Change
    {"id": 17, "category": "Habit Change", "title": "Does anyone feel like getting disciplined / 'relapsed'",
     "summary": "★ Last week's source post. Set small goals (~7 weeks ago) that worked until he stopped tracking; today stayed in bed and felt like a failure. Asks how others self-talk through a relapse.",
     "url": "https://www.reddit.com/r/getdisciplined/comments/dshviu/needadvice_does_anyone_feel_like_getting", "flagged": False},
    {"id": 18, "category": "Habit Change", "title": "Relapsed",
     "summary": "Doing well across no-fap, gym, study, work until he broke a 26-day streak; traces it to a domino effect from sleeping late. Asks if a small loss can cascade.",
     "url": "https://www.reddit.com/r/getdisciplined/comments/1kd7bi9/relapsed/", "flagged": False},
    # Sleep
    {"id": 19, "category": "Sleep", "title": "Anyone else feel exhausted but their mind won't switch off",
     "summary": "His mind woke the moment he tried to sleep; what changed was realizing the pressure around sleep was the problem and he stopped forcing it. A recovery narrative.",
     "url": "https://www.reddit.com/r/insomnia/comments/1sjdmpd/anyone_else_feel_exhausted_but_their_mind_wont/", "flagged": False},
    {"id": 20, "category": "Sleep", "title": "Slept absolutely zero hours last night again and I feel normal",
     "summary": "In bed at 11pm, awake until 6am for ~zero sleep yet felt oddly normal at work; a severe sleep-deprivation pattern that began with anxiety; meds haven't worked.",
     "url": "https://www.reddit.com/r/insomnia/comments/1kq3rmk/slept_absolutely_zero_hours_last_night_again_and/", "flagged": False},
]

# id 17 的全文上次已存在上層資料夾，先映射過去；其餘等之後補進 posts/
KNOWN_FULL_TEXT = {
    17: HERE.parent / "selected_post_habitchange.txt",
}


def load_clusters() -> dict:
    """回傳 {cluster_name: [post, ...]}。

    Placeholder：目前用 Merged_Post_List.md 的 8 個人工 category。
    要換成你們之前的研究方法（embedding / 分群結果）時，改這個函式即可，
    只要維持回傳格式不變，上層 UI 不必動。
    """
    clusters: dict = {}
    for post in POSTS:
        clusters.setdefault(post["category"], []).append(post)
    return clusters


def load_post_text(post_id: int) -> str:
    """回傳某篇 post 的全文，找不到就回空字串（讓使用者自行貼上）。

    Placeholder：先找 posts/{id}.txt，再找已知的上層全文檔。
    之後把 20 篇全文補進 posts/ 即可自動帶入。
    """
    local = POSTS_DIR / f"{post_id}.txt"
    if local.exists():
        return local.read_text(encoding="utf-8")
    known = KNOWN_FULL_TEXT.get(post_id)
    if known and known.exists():
        return known.read_text(encoding="utf-8")
    return ""


# ---------------------------------------------------------------------------
# LLM 步驟
# ---------------------------------------------------------------------------

def generate_ccd(post_text: str):
    """Method A 的 CCD 步驟。回傳 (ccd_text, saved_path)，沿用 app.py 的存檔邏輯。"""
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=2000,
        messages=[
            {"role": "system", "content": "You are a clinical psychologist trained in CBT and Cognitive Case Conceptualization."},
            {"role": "user", "content": CCD_PROMPT.format(patient_text=post_text)},
        ],
    )
    ccd = response.choices[0].message.content

    CCD_DIR.mkdir(exist_ok=True)
    existing = [f for f in os.listdir(CCD_DIR) if f.startswith("single_") and f.endswith("_ccd.txt")]
    next_num = len(existing) + 1
    out_path = CCD_DIR / f"single_{next_num:03d}_ccd.txt"
    out_path.write_text(ccd, encoding="utf-8")
    return ccd, str(out_path)


def persona_reply(user_input: str) -> str:
    """共用聊天步驟：依 st.session_state.messages（已含 system prompt）續對話。"""
    st.session_state.messages.append({"role": "user", "content": user_input})
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=st.session_state.messages,
    )
    reply = response.choices[0].message.content
    st.session_state.messages.append({"role": "assistant", "content": reply})
    return reply


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def reset_persona():
    """換方法 / 換 post / 重新生成時，清掉 persona 與對話。"""
    st.session_state.persona_ready = False
    st.session_state.basis_label = None   # "CCD" or "Post"
    st.session_state.basis_text = None
    st.session_state.messages = []
    st.session_state.chat_history = []


for key, default in {
    "persona_ready": False,
    "basis_label": None,
    "basis_text": None,
    "messages": [],
    "chat_history": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ===========================================================================
# UI
# ===========================================================================

st.set_page_config(page_title="Persona Generation Interface", layout="wide")
st.title("Persona Generation Interface")

# --- Section 1：方法說明與 Pipeline ---------------------------------------
st.header("1 · 方法說明與 Pipeline")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Method A — Post-CCD-Chatbox**")
    st.graphviz_chart("""
    digraph A {
        rankdir=LR; node [shape=box, style=rounded, fontsize=11];
        "Post\\nSelection" -> "CCD\\nProcessing" -> "Persona\\nConstruction" -> "Chatbox\\nInteraction";
    }
    """)
    st.caption("延續上次：先用 CCD 把 post 結構化，再用 CCD 當角色設定。")
with c2:
    st.markdown("**Method B — Direct Post-Chatbox**")
    st.graphviz_chart("""
    digraph B {
        rankdir=LR; node [shape=box, style=rounded, fontsize=11];
        "Post\\nSelection" -> "Persona\\nConstruction" -> "Chatbox\\nInteraction";
    }
    """)
    st.caption("對照組：不經過 CCD，直接用 post 全文當角色設定。")

st.divider()

# --- Section 2：選擇 Persona 製作方式 -------------------------------------
st.header("2 · 選擇 Persona 製作方式")
method = st.radio(
    "Persona 製作方式",
    ["Post-CCD-Chatbox", "Direct Post-Chatbox"],
    horizontal=True,
    label_visibility="collapsed",
    on_change=reset_persona,
)

st.divider()

# --- Section 3：輸入 / 選擇 Post -------------------------------------------
st.header("3 · 輸入 / 選擇 Post")
clusters = load_clusters()
sel1, sel2 = st.columns(2)
with sel1:
    cluster_name = st.selectbox("Cluster（分群篩選）", list(clusters.keys()))
with sel2:
    posts_in_cluster = clusters[cluster_name]
    def _post_label(p):
        return f"{'⚠️ ' if p['flagged'] else ''}#{p['id']} · {p['title']}"
    chosen = st.selectbox("Post", posts_in_cluster, format_func=_post_label)

st.caption(f"Summary：{chosen['summary']}")
st.caption(f"URL：{chosen['url']}")
if chosen["flagged"]:
    st.error("此 post 已被標記為危機內容（含自殺意念），依上次規則排除於 persona 使用。")

prefill = load_post_text(chosen["id"])
post_text = st.text_area(
    "Post 全文（找不到全文時請貼上；cluster 與全文來源之後接你們的研究方法）",
    value=prefill,
    height=220,
    placeholder="貼上這篇 post 的完整內容…",
)

st.divider()

# --- Section 4：生成 Persona ----------------------------------------------
st.header("4 · 生成 Persona")
disabled = chosen["flagged"]
if st.button("生成 Persona", type="primary", disabled=disabled):
    if not post_text.strip():
        st.warning("請先提供 post 全文。")
    else:
        reset_persona()
        if method == "Post-CCD-Chatbox":
            with st.spinner("產生 CCD 中…"):
                ccd, saved = generate_ccd(post_text)
            st.session_state.messages = [
                {"role": "system", "content": PERSONA_SYSTEM_PROMPT.format(ccd_text=ccd.strip())}
            ]
            st.session_state.basis_label = "CCD"
            st.session_state.basis_text = ccd
            st.success(f"CCD 已存：{saved}")
        else:  # Direct Post-Chatbox
            st.session_state.messages = [
                {"role": "system", "content": PERSONA_DIRECT_PROMPT.format(post_text=post_text.strip())}
            ]
            st.session_state.basis_label = "Post"
            st.session_state.basis_text = post_text
        st.session_state.persona_ready = True

if st.session_state.persona_ready:
    label = st.session_state.basis_label
    st.markdown(f"**生成依據：{label}**" + ("（Method A：CCD）" if label == "CCD" else "（Method B：原始 post）"))
    with st.expander(f"檢視{label}", expanded=(label == "CCD")):
        st.text(st.session_state.basis_text)

st.divider()

# --- Section 5：Chatbox 測試 ----------------------------------------------
st.header("5 · Chatbox 測試")
if not st.session_state.persona_ready:
    st.info("先在上面生成 persona。")
else:
    for role, msg in st.session_state.chat_history:
        with st.chat_message("user" if role == "you" else "assistant"):
            st.write(msg)

    user_input = st.chat_input("跟這個 persona 說點什麼…")
    if user_input:
        with st.chat_message("user"):
            st.write(user_input)
        reply = persona_reply(user_input)
        with st.chat_message("assistant"):
            st.write(reply)
        st.session_state.chat_history.append(("you", user_input))
        st.session_state.chat_history.append(("persona", reply))
