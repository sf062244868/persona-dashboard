# post `1htp0xw` 完整流程測試

- 測試內容:舊版 Max,可與舊 prompt 逐字稿對照
- CCD 模型:`gpt-4o` · 對話模型:`gpt-4o` · prompt_version:`beck-pure-string-v4`
- 隨機問題 seed:`101`(可重現)
- CCD 生成:6.3s · 941 tokens

## ① 原始 post

```
I'm mostly by myself. Doesn't get invites to hangouts. Old high school and close friends from university have drifted away and they have their own circles, too. I do go out by myself but meeting new people isn't in the list. Too introverted to join in on conversations. Communication and talking isn't really my strong point and I want to work on this honestly.

If I look back, I have been 90% alone for most of my adult life after university. Even with people whom I thought as friends make me feel lonely. Turns out I am just around them for proximity, convenience, and transactional connections. 

Too scared to go to a therapist to talk about my internal struggles. No one really checks in on me. Been fighting silent battles alone due to that. And I don't want to talk to people about it since everyone got their own problems too. Wouldn't that seem whine-y?

My work has been greatly affected by this. Colleagues are colleagues after all. You can't really open up to them about anything. I feel like that would be a big mistake. I struggle getting things done and I have been silently screaming for help but tried to improve any way I could by myself.

Idk how to cope anymore.
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
I'm mostly by myself. Doesn't get invites to hangouts. Old high school and close friends from university have drifted away and they have their own circles, too. I do go out by myself but meeting new people isn't in the list. Too introverted to join in on conversations. Communication and talking isn't really my strong point and I want to work on this honestly.

If I look back, I have been 90% alone for most of my adult life after university. Even with people whom I thought as friends make me feel lonely. Turns out I am just around them for proximity, convenience, and transactional connections. 

Too scared to go to a therapist to talk about my internal struggles. No one really checks in on me. Been fighting silent battles alone due to that. And I don't want to talk to people about it since everyone got their own problems too. Wouldn't that seem whine-y?

My work has been greatly affected by this. Colleagues are colleagues after all. You can't really open up to them about anything. I feel like that would be a big mistake. I struggle getting things done and I have been silently screaming for help but tried to improve any way I could by myself.

Idk how to cope anymore.

```

## ③ 回傳的 CCD(原始 JSON)

```json
{
  "life_history": "Old high school and close friends from university have drifted away, has been 90% alone for most of adult life after university.",
  "core_belief": "I am alone.",
  "intermediate_beliefs": "It's risky to open up to others because they have their own problems and doing so might seem whiny.",
  "coping_strategies": "Avoids opening up to others about internal struggles, avoids seeing a therapist, and tries to improve by self without seeking external help.",
  "cognitive_models": [
    {
      "situation": "Being mostly by myself without invites to hangouts.",
      "automatic_thoughts": "No one really checks in on me.",
      "meaning_of_automatic_thought": "I am unimportant to others.",
      "emotion": "Loneliness",
      "behavior": "Goes out by self but avoids meeting new people."
    },
    {
      "situation": "Struggles in work due to inability to open up to colleagues.",
      "automatic_thoughts": "Opening up to colleagues would be a big mistake.",
      "meaning_of_automatic_thought": "If I open up, I could be judged or seen as inadequate.",
      "emotion": "Fear",
      "behavior": "Struggles to get things done and silently screams for help without seeking assistance."
    },
    {
      "situation": "Doesn't talk to people about struggles.",
      "automatic_thoughts": "Everyone has their own problems.",
      "meaning_of_automatic_thought": "My problems are not worth burdening others with.",
      "emotion": "Embarrassment?",
      "behavior": "Avoids talking to others about personal struggles."
    }
  ],
  "prompt_version": "beck-pure-string-v4"
}
```

## ④ CCD 9 格文字(UI 的 CCD profile)

```
Relevant Life History & Precipitants: Old high school and close friends from university have drifted away, has been 90% alone for most of adult life after university.
Core Belief(s): I am alone.
Intermediate Beliefs (Assumptions/Attitudes/Rules): It's risky to open up to others because they have their own problems and doing so might seem whiny.
Coping Strategies: Avoids opening up to others about internal struggles, avoids seeing a therapist, and tries to improve by self without seeking external help.
Situation #1: Being mostly by myself without invites to hangouts.
Automatic Thought(s) #1: No one really checks in on me.
Meaning of A.T. #1: I am unimportant to others.
Emotion #1: Loneliness
Behavior #1: Goes out by self but avoids meeting new people.
Situation #2: Struggles in work due to inability to open up to colleagues.
Automatic Thought(s) #2: Opening up to colleagues would be a big mistake.
Meaning of A.T. #2: If I open up, I could be judged or seen as inadequate.
Emotion #2: Fear
Behavior #2: Struggles to get things done and silently screams for help without seeking assistance.
Situation #3: Doesn't talk to people about struggles.
Automatic Thought(s) #3: Everyone has their own problems.
Meaning of A.T. #3: My problems are not worth burdening others with.
Emotion #3: Embarrassment?
Behavior #3: Avoids talking to others about personal struggles.
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

**You:** Hi — how have things been going for you recently?

> **[1htp0xw]:** Hi. Well, things have been... somewhat the same, I guess. I've spent most of my time alone, as usual. I haven't really been in touch with friends from high school or university much. It's just been a bit quiet, you know?

**You:** What's the hardest part of all this for you?

> **[1htp0xw]:** The hardest part is probably the loneliness. It just feels like no one really checks in on me. I sometimes wonder if I'm important to anyone at all. It's tough to shake that feeling, even when I'm keeping busy on my own. It's like I'm just out here trying to figure things out alone.

**You:** Tell me about your family growing up.

> **[1htp0xw]:** Growing up, my family was... well, we were close, I think. My parents worked a lot, so I learned to be pretty independent early on. They supported me but weren't always around to talk about what was going on with me. I guess I've always kind of gotten used to just handling things on my own. They were good parents, but emotions weren't something we really discussed.

**You:** What's something that went okay recently, even a small thing?

> **[1htp0xw]:** I guess something that went okay was... I did go out for a walk the other day. It was nice to get some fresh air and move around a bit. I managed to clear my head, at least for a little while. I saw some people around, but I didn't really feel like approaching any of them. Still, it was something positive, I suppose.

**You:** What was going through your head right then?

> **[1htp0xw]:** While I was walking, I was mostly thinking about how it felt good to be outside and not cooped up at home. But I also couldn't shake the thought that I was doing this alone, again. It just made me think about how no one had really reached out to join me or anything. I felt like it wouldn't make much difference to anyone else if I was out there or not. That thought lingered a bit, even as I tried to focus on enjoying the moment.

**You:** What does a typical day look like for you right now?

> **[1htp0xw]:** A typical day for me usually involves waking up, having breakfast, and then getting on with whatever tasks I need to do. I might work on some projects or chores, things that keep me occupied. I try to go out for a walk or run errands, just to get out of the house. In the evenings, I might read or watch something to relax. It's pretty routine and quiet without many other people involved.

**You:** Is there something you wish people understood about you?

> **[1htp0xw]:** I wish people understood that, even though I might seem okay on my own, I do feel lonely and disconnected. It's not that I don't want to be included or that I'm avoiding everyone on purpose. It's just hard for me to reach out or open up since I'm not sure how they'll respond. I guess it would mean a lot if someone would take the initiative to check in or invite me to hang out. It’s just tough to push past those walls by myself.

**You:** What did you end up doing about it?

> **[1htp0xw]:** Honestly, I haven't really done much about it. I tend to keep to myself, thinking it might be better not to bother others with my issues. I've tried to focus on improving things on my own, hoping that I'll find some way to make it better. There’s a part of me that wishes I could open up more, but it's hard when I'm not sure how it'll be received. So, I've just continued managing things as best as I can by myself.
