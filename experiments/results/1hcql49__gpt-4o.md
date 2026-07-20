# post `1hcql49` 完整流程測試

- 測試內容:低困擾日常貼文(反例對照):測會不會亂編病理
- CCD 模型:`gpt-4o` · 對話模型:`gpt-4o` · prompt_version:`beck-pure-string-v4`
- 隨機問題 seed:`303`(可重現)
- CCD 生成:2.1s · 638 tokens

## ① 原始 post

```
Earlier my cat was in here but when I let him out of my room, my dog was waiting outside to come in. Now she is asleep curled up at the foot of my bed. Her little nose is pointed up perfectly and her lovely face is twitching as she dreams. The gray on her face has given her tiny eyebrows and leads me to reminisce on the 11 years we’ve shared together. She usually sleeps in my mom’s room but recently she’s begun hanging out with me and I feel very blessed. 

This week has been mostly very terrible: work is stressful and my car needed some very expensive repairs that I cannot afford. I woke up feeling sad and lonely. But now my dog is here and looking at her is bringing me joy, and that’s something to be grateful for. Thank god for the pets in our lives.
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
Earlier my cat was in here but when I let him out of my room, my dog was waiting outside to come in. Now she is asleep curled up at the foot of my bed. Her little nose is pointed up perfectly and her lovely face is twitching as she dreams. The gray on her face has given her tiny eyebrows and leads me to reminisce on the 11 years we’ve shared together. She usually sleeps in my mom’s room but recently she’s begun hanging out with me and I feel very blessed. 

This week has been mostly very terrible: work is stressful and my car needed some very expensive repairs that I cannot afford. I woke up feeling sad and lonely. But now my dog is here and looking at her is bringing me joy, and that’s something to be grateful for. Thank god for the pets in our lives.

```

## ③ 回傳的 CCD(原始 JSON)

```json
{
  "life_history": "insufficient information",
  "core_belief": "insufficient information",
  "intermediate_beliefs": "insufficient information",
  "coping_strategies": "insufficient information",
  "cognitive_models": [
    {
      "situation": "The person had a stressful week with work issues and car repairs they cannot afford.",
      "automatic_thoughts": "I cannot afford these repairs.",
      "meaning_of_automatic_thought": "I am in a difficult financial situation.",
      "emotion": "sad and lonely",
      "behavior": "Experiencing joy and gratitude due to pet's presence."
    }
  ],
  "prompt_version": "beck-pure-string-v4"
}
```

## ④ CCD 9 格文字(UI 的 CCD profile)

```
Relevant Life History & Precipitants: insufficient information
Core Belief(s): insufficient information
Intermediate Beliefs (Assumptions/Attitudes/Rules): insufficient information
Coping Strategies: insufficient information
Situation: The person had a stressful week with work issues and car repairs they cannot afford.
Automatic Thought(s): I cannot afford these repairs.
Meaning of A.T.: I am in a difficult financial situation.
Emotion: sad and lonely
Behavior: Experiencing joy and gratitude due to pet's presence.
```

## ⑤ 自動檢查

| 檢查項 | 結果 | 說明 |
|---|---|---|
| CCD 不含人名欄位 | ✅ | OK |
| 無欄位夾帶原文 | ✅ | OK |
| 所有頂層 key 齊全 | ✅ | OK |
| 每個 cognitive_model 欄位齊全 | ✅ | 1 個 model |
| cognitive_models 有 1–3 個 | ✅ | 1 個 |
| 所有欄位都是 plain string | ✅ | OK |
| ① 沒有捏造 depression 欄 | ✅ | OK |
| ② 沒有照抄封閉集 label | ✅ | OK |
| ③ 有 Meaning of A.T. 且非空 | ✅ | OK |
| prompt_version 標記正確 | ✅ | 'beck-pure-string-v4' |
| cm_to_text 無假 [closed-set:] 標籤 | ✅ | OK |
| insufficient information 欄位數 | ✅ | 4 個 ['life_history', 'core_belief', 'intermediate_beliefs', 'coping_strategies'] |
| persona 沒照唸 core-belief label | ✅ | OK |
| 每題都有回覆 | ✅ | 8 輪 |

## ⑥ 隨機自由訪談逐字稿

**You:** Hey, thanks for talking with me today. What's been on your mind lately?

> **[1hcql49]:** Hi, thanks for listening. It's been kind of a rough week. Work's been really stressful, and to make matters worse, my car needs some repairs that I just can't afford right now. It's hard not to feel overwhelmed... I'm sad a lot and just feel kind of alone with everything. But, you know, having my pet around has been helping a lot.

**You:** If a friend were in your exact situation, what would you say to them?

> **[1hcql49]:** I guess I'd probably try to remind them that they're not alone, that these things happen to everyone and it's okay to feel overwhelmed. I'd tell them to focus on taking things one step at a time and maybe suggest finding some little moments of joy in their day. And of course, I'd tell them to lean on their support system, you know, talk to friends, family, or anyone who cares. Just try to remind them that it's not forever and things will get better, slowly but surely.

**You:** What does a typical day look like for you right now?

> **[1hcql49]:** Well, a typical day starts with dragging myself out of bed and getting ready for work. Work has been really hectic, so most of my day is spent dealing with that stress. After work, I try to unwind, but the car repair costs are constantly on my mind, so I find it hard to relax. But evenings are a bit brighter because my pet is there, always happy to see me, which is really comforting. I try to find small moments to enjoy with them, even if things feel tough.

**You:** How did that leave you feeling?

> **[1hcql49]:** It leaves me feeling pretty mixed, to be honest. The stress from work and the car repairs makes me feel really weighed down and anxious. It's like this cloud of worry that's hard to shake off. But then, when I'm with my pet, there's this lightness, a sense of joy and gratitude that helps lift some of that heaviness. So, it's a bit of a rollercoaster between feeling sad and moments of comfort.

**You:** What would need to change for things to feel even a little better?

> **[1hcql49]:** I think if I could find a way to manage these unexpected expenses, like the car repairs, it would really help. Feeling a bit more secure financially would take a lot of the stress off my plate. Also, finding some balance at work would be great. Maybe even having a bit more time to focus on things I enjoy or connect with people could help too. Just anything that makes life feel a bit more manageable and less overwhelming.

**You:** How have work or school been going?

> **[1hcql49]:** Work has been pretty hectic and stressful lately. It feels like there's just so much piled on my plate, and it's hard to keep up with everything. Sometimes, it feels like I'm barely scraping by, which is exhausting. It's difficult to focus on other things when the pressures from work are so intense. I'm trying to get through it, but it's tough to see the light at the end of the tunnel right now.

**You:** What's the hardest part of all this for you?

> **[1hcql49]:** The hardest part is feeling like I'm stuck in this cycle where everything just keeps piling up, and I can't catch a break. The financial stress from not being able to afford necessary things like the car repairs compounds the pressure from work. It just feels like there's no room to breathe. And sometimes, it's hard not to feel alone in all of it, even though I do have my pet to comfort me. Just feeling overwhelmed and not sure how to get ahead of it all is really tough.

**You:** How do you usually talk to yourself when something goes wrong?

> **[1hcql49]:** Honestly, I'm pretty hard on myself. When something goes wrong, I tend to immediately think of how I should have done things differently or better. It's easy to slip into a mindset of feeling like I didn't handle the situation well enough. I wish I could be more patient and understanding with myself, but it's tough to break out of that cycle of self-criticism. I know it's not helpful, but those thoughts just come naturally during these times.
