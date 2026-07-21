# Pipeline

Both modes end in the same chat loop. The only difference is whether the post passes
through a Cognitive Conceptualization Diagram (CCD) first.

## Mode A: post → CCD → persona

```
post text → generate_ccd_psi() → cm dict → psi_persona_system() → chat_once()
```

| Stage | Function | Prompt |
| --- | --- | --- |
| Generate CCD | `generate_ccd_psi()` | `BUILD_CCD_PROMPT_PSI` |
| Assemble persona | `psi_persona_system()` | `PSI_PERSONA_SYSTEM_TEMPLATE` |

API parameters: `model=gpt-4o`, `response_format={"type": "json_object"}`,
`max_tokens=1500`.

The CCD has five fields, all plain strings:

```
life_history
core_belief
intermediate_beliefs
coping_strategies
cognitive_models        1–3 objects, each with situation, automatic_thoughts,
                        meaning_of_automatic_thought, emotion, behavior
```

Fields the post does not support are filled with `insufficient information`. Uncertain
inferences end with `?`. `cm_to_text()` flattens the structure into the nine cells the UI
shows under **CCD profile**.

The prompt is stamped `beck-pure-string-v4`. There are no closed-set labels, no
`{"text", "grounding", "evidence"}` boxes, and no name field; personas are identified by
`post_id`.

## Mode B: post → persona

```
post text → build_persona(MODE_DIRECT) → chat_once()
```

Uses `PERSONA_FROM_POST_PROMPT`. No CCD; the persona reads the post directly.

## Conversation styles

`PSI_PATIENT_TYPES` holds the six Patient-Ψ styles (`plain`, `upset`, `verbose`,
`reserved`, `tangent`, `pleasing`), transcribed from the reference implementation. The
selected style is inserted into the system prompt when the persona is built, not per reply.
