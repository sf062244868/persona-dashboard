# post `1iercl7` 完整流程測試

- 測試內容:典型自責,core belief 應清楚
- CCD 模型:`gpt-4o` · 對話模型:`gpt-4o` · prompt_version:`beck-pure-string-v4`
- 隨機問題 seed:`202`(可重現)
- CCD 生成:5.1s · 957 tokens

## ① 原始 post

```
Every time I receive constructive critism-or just hear something that I can improve on, even if it's not directed towards me-i hurt. I feel like it makes me less than. I feel embarrassed and judged. So I get defensive, I either lash out or stay silently fuming. I feel like I can't see anyone else with these problems I have so I feel like I'm the worst. I also feel hurt when my behavior IS mirrored back to me. 

It makes me obsessive over my defects that I want to change in a day. But I can't change in a day but at the same time people leave when I'm like this and if I'm not interacting with people how can I show improved behavior?

I like to think I'm kind and have a good heart but I don't come off that way, I might not even be that way. My personality is just too strong-if I knew how to tone down some things I would be alright. For example-im mean to the ones I love as a joke but maybe I should cut back. Also I talk to much about myself but I feel like if I don't then no one would ask. Because they won't. They don't care what I experience and that hurts too. 

I'm just hurt and I can't tell anyone irl because most of them don't care, because I can't keep a relationship going on my end. 

How to get past this hurt?
```

## ② 送給 gpt-4o 的 CCD 建構 prompt(全文)

```
From the TEXT below, identify the writer's automatic thoughts, emotions, behaviors, and the beliefs behind them, using only what the TEXT states. Treat every entry as a working hypothesis; mark uncertain ones with "?".

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
Every time I receive constructive critism-or just hear something that I can improve on, even if it's not directed towards me-i hurt. I feel like it makes me less than. I feel embarrassed and judged. So I get defensive, I either lash out or stay silently fuming. I feel like I can't see anyone else with these problems I have so I feel like I'm the worst. I also feel hurt when my behavior IS mirrored back to me. 

It makes me obsessive over my defects that I want to change in a day. But I can't change in a day but at the same time people leave when I'm like this and if I'm not interacting with people how can I show improved behavior?

I like to think I'm kind and have a good heart but I don't come off that way, I might not even be that way. My personality is just too strong-if I knew how to tone down some things I would be alright. For example-im mean to the ones I love as a joke but maybe I should cut back. Also I talk to much about myself but I feel like if I don't then no one would ask. Because they won't. They don't care what I experience and that hurts too. 

I'm just hurt and I can't tell anyone irl because most of them don't care, because I can't keep a relationship going on my end. 

How to get past this hurt?

```

## ③ 回傳的 CCD(原始 JSON)

```json
{
  "life_history": "Feeling not cared for and having difficulties maintaining relationships.",
  "core_belief": "I am less than others and my personality flaws drive people away.",
  "intermediate_beliefs": "I need to change quickly or people will leave me; if I don't talk about myself, no one will care.",
  "coping_strategies": "Becoming defensive and obsessive over perceived defects; lashing out or withdrawing when criticized.",
  "cognitive_models": [
    {
      "situation": "Receiving constructive criticism or hearing about potential improvements.",
      "automatic_thoughts": "This criticism makes me less than others.",
      "meaning_of_automatic_thought": "Being criticized implies I'm worse than others.",
      "emotion": "Hurt and embarrassed",
      "behavior": "Getting defensive, lashing out, or staying silent."
    },
    {
      "situation": "Behavior mirrored back by others.",
      "automatic_thoughts": "I need to change my defects quickly to be accepted.",
      "meaning_of_automatic_thought": "People will leave me if I don't change immediately.",
      "emotion": "Hurt and obsessive",
      "behavior": "Obsessing over defects and struggling to interact positively."
    },
    {
      "situation": "Interacting with others where personality is perceived as too strong.",
      "automatic_thoughts": "I might not be kind or have a good heart.",
      "meaning_of_automatic_thought": "Strong personality makes it hard to connect and be perceived as kind.",
      "emotion": "Hurt",
      "behavior": "Joking meanly with loved ones, talking excessively about self."
    }
  ],
  "prompt_version": "beck-pure-string-v4"
}
```

## ④ CCD 9 格文字(UI 的 CCD profile)

```
Relevant Life History & Precipitants: Feeling not cared for and having difficulties maintaining relationships.
Core Belief(s): I am less than others and my personality flaws drive people away.
Intermediate Beliefs (Assumptions/Attitudes/Rules): I need to change quickly or people will leave me; if I don't talk about myself, no one will care.
Coping Strategies: Becoming defensive and obsessive over perceived defects; lashing out or withdrawing when criticized.
Situation #1: Receiving constructive criticism or hearing about potential improvements.
Automatic Thought(s) #1: This criticism makes me less than others.
Meaning of A.T. #1: Being criticized implies I'm worse than others.
Emotion #1: Hurt and embarrassed
Behavior #1: Getting defensive, lashing out, or staying silent.
Situation #2: Behavior mirrored back by others.
Automatic Thought(s) #2: I need to change my defects quickly to be accepted.
Meaning of A.T. #2: People will leave me if I don't change immediately.
Emotion #2: Hurt and obsessive
Behavior #2: Obsessing over defects and struggling to interact positively.
Situation #3: Interacting with others where personality is perceived as too strong.
Automatic Thought(s) #3: I might not be kind or have a good heart.
Meaning of A.T. #3: Strong personality makes it hard to connect and be perceived as kind.
Emotion #3: Hurt
Behavior #3: Joking meanly with loved ones, talking excessively about self.
```

## ⑤ 自動檢查

| 檢查項 | 結果 | 說明 |
|---|---|---|
| CCD 不含人名欄位 | ✅ | OK |
| 無欄位夾帶原文 | ✅ | OK |
| 所有頂層 key 齊全 | ✅ | OK |
| 每個 cognitive_model 欄位齊全 | ✅ | 3 個 model |
| cognitive_models 有 1–3 個 | ✅ | 3 個 |
| 所有欄位都是 plain string | ✅ | OK |
| ① 沒有捏造 depression 欄 | ✅ | OK |
| ② 沒有照抄封閉集 label | ✅ | OK |
| ③ 有 Meaning of A.T. 且非空 | ✅ | OK |
| prompt_version 標記正確 | ✅ | 'beck-pure-string-v4' |
| cm_to_text 無假 [closed-set:] 標籤 | ✅ | OK |
| insufficient information 欄位數 | ✅ | 0 個 [] |
| persona 沒照唸 core-belief label | ✅ | OK |
| 每題都有回覆 | ✅ | 8 輪 |

## ⑥ 隨機自由訪談逐字稿

**You:** Can you tell me a bit about what's been going on for you?

> **[1iercl7]:** Lately, I've been feeling really on edge, especially when I get any kind of feedback. It's just...you know, when someone points out something I might need to improve, it feels like they're saying I'm just not good enough. I guess it makes me feel really...exposed, and then I either get defensive or just shut down completely. It's hard to shake off that feeling of being less than everyone else, and I worry it pushes people away. It's just been exhausting trying to figure out how to keep people from leaving.

**You:** When you picture six months from now, what do you see?

> **[1iercl7]:** I wish I could say I see something hopeful, but honestly, it seems a bit intimidating to think that far ahead. I have this fear that if I don't sort out these issues, people I care about will drift away. It feels like I need to change overnight or risk being left alone. Maybe I'll be in the same position—struggling to maintain the relationships that matter. But I really hope I'll find a way to manage these thoughts better by then.

**You:** Do you think you might be depressed?

> **[1iercl7]:** I haven't really thought of it that way, I guess. I do find myself feeling low and overwhelmed, especially after any kind of criticism... it just sticks with me. Sometimes, I get this feeling that nothing I do is quite right, and that can be pretty draining. But I'm not sure if that means I'm depressed, or if it's just a rough patch. It's hard to separate emotions sometimes, you know?

**You:** What does a typical day look like for you right now?

> **[1iercl7]:** Lately, a typical day starts with me waking up already anxious about what might happen. I spend a lot of time overthinking conversations, worried I'll say or do something wrong. If something critical comes up during the day, I catch myself dwelling on it and feeling inadequate. I often find myself shutting down or being extra cautious around others, trying not to reveal too much. By the end of the day, I'm usually exhausted from all the mental effort it takes to just get by.

**You:** What's the hardest part of all this for you?

> **[1iercl7]:** The hardest part is definitely the constant feeling that I'm not good enough. It’s like no matter what I do, there’s always something to point out or fix, and it feels so personal when it happens. Afterward, I find myself obsessing over my flaws and worrying that people might just get fed up with me. It leads to this cycle of either lashing out or withdrawing, neither of which really help. It's tough to break out of that pattern and just feel okay with who I am.

**You:** How have work or school been going?

> **[1iercl7]:** Work has been really challenging lately. I'm always on edge there, half expecting some critique or feedback at any moment. When it does come, even if it's meant to be helpful, it's hard not to take it as a sign that I'm not measuring up. I try to keep it together, but I either end up snapping at someone or retreating into myself for the rest of the day. It’s become a place where I feel I have to constantly prove my worth, and that’s pretty stressful.

**You:** Can you tell me about a moment recently that really stuck with you?

> **[1iercl7]:** There was this meeting at work not too long ago where my manager suggested a different approach to a project I’d been working on. Even though I knew they were just trying to help, I felt this immediate sense of embarrassment, like everyone in the room could see I hadn't done a good enough job. I remember fighting back defensive comments, stopping myself just in time, but after that, I couldn't shake how small it made me feel. It really stuck with me, and I’ve been replaying it over and over, worrying about what everyone must think of me now. It’s these moments that just linger, making it hard to move on.

**You:** Is there anything you've been putting off or avoiding?

> **[1iercl7]:** Yeah, I've been avoiding having any deep conversations with friends or family. It feels like if I'm too open or honest, they'll see all my flaws and start to drift away. So instead, I've been sticking to surface-level interactions, too afraid to dive deeper and risk any sort of criticism. I know avoiding these conversations isn't helping, but it just seems easier than facing potential disappointment or conflict. It’s been this constant worry in the back of my mind.
