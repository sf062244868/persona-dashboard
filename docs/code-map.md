# Code map

Where things live, and why some names look like duplicates of each other.

Line numbers refer to the current `main`.

## Layout

```
persona_dashboard.py    Streamlit UI, and the entry point
persona_core.py         Prompts, CCD generation, persona assembly, chat
ui_common.py            Key injection and password gate

posts/                  16 sample posts, listed in index.json
patients_ccd/           CCDs written at runtime (gitignored)
docs/                   this file, DEPLOY.md
```

These three modules stay at the repository root. `persona_dashboard.py` imports
`persona_core` as a bare module and resolves `posts/` relative to its own directory, and
Streamlit Cloud pins the main file path to the root. Moving them breaks imports and the
deployment together.

`ui_common` is imported before `persona_core` on purpose: it copies `OPENAI_API_KEY` out
of `st.secrets` into `os.environ`, which is the only way the key reaches `persona_core` on
Streamlit Cloud (there is no `.env` there), and it runs the password gate before the
backend loads.

## The prompts

Four prompt texts reach the model. Three are named constants you can edit in the UI; the
fourth is inlined in a function call and is not exposed anywhere.

| # | What it does | Constant | `persona_core.py` | Editable in UI |
| --- | --- | --- | --- | --- |
| ① | post → CCD JSON | `BUILD_CCD_PROMPT_PSI` | **133–154** | yes |
| ② | roleplay, mode A (from CCD) | `PSI_PERSONA_SYSTEM_TEMPLATE` | **223–247** | yes |
| ③ | roleplay, mode B (from post) | `PERSONA_FROM_POST_PROMPT` | **48–70** | yes |
| ④ | JSON-format instruction for ① | *(none — inline literal)* | **188** | **no** |

④ is the system message `"You reconstruct Beck cognitive conceptualization diagrams and
reply with a single JSON object."`, hardcoded inside the `chat.completions.create` call in
`generate_ccd_psi()`. It is sent on every mode-A build alongside ①. Anyone auditing the
prompts should read it too — it will not appear in the UI or in a search for `PROMPT`.

Two more blocks are prompt *fragments* rather than whole prompts:

| Constant | `persona_core.py` | Injected into | Used in |
| --- | --- | --- | --- |
| `PSI_PATIENT_TYPES` | 210 | `{style_content}` of ② | mode A only |
| `CONVERSATION_STYLES` | 82 | `{style_block}` of ③ | mode B only |

### Finding them in the running app

The three editable prompts are under the **🧩 Edit prompts** expander
(`persona_dashboard.py:404`). It sits at the very bottom of the page, below the chat
transcript — scroll all the way down. Fields are at lines 409, 413 and 415; the reset
button restores the constants above via `reset_prompts()` (`persona_dashboard.py:204`).

Three nearby expanders show what was actually sent: **CCD profile** (`:395`), **Final
system prompt sent to the model** (`:399`), **Source post used** (`:401`).

## Why the names look duplicated

Each prompt carries a different name in each of the three layers. This is the main reason
they are hard to find by searching.

| UI label | `persona_core.py` constant | `session_state` key |
| --- | --- | --- |
| ① Build CCD (A) | `BUILD_CCD_PROMPT_PSI` | `build_ccd_prompt_edit` |
| ② Roleplay from CCD (A) | `PSI_PERSONA_SYSTEM_TEMPLATE` | `persona_from_ccd_prompt_edit` |
| ③ Roleplay from post (B) | `PERSONA_FROM_POST_PROMPT` | `persona_from_post_prompt_edit` |

Only ③ keeps a recognisable name across all three layers. ②'s `PSI_` prefix hides that it
is ③'s sibling — the session key calls it `persona_from_ccd`, which is the clearer name.

Other collisions worth knowing about:

- **Two style dictionaries with identical keys.** `CONVERSATION_STYLES` (`:82`) and
  `PSI_PATIENT_TYPES` (`:210`) both have `plain / upset / verbose / reserved / tangent /
  pleasing`. The dropdown is built from the first (`persona_dashboard.py:156`), but in mode
  A the text that reaches the model comes from the second. So the menu is *labelled* by one
  dict and *honoured* by the other, depending on mode.
- **The `_PSI` suffix means nothing now.** It distinguished these from a non-Ψ twin that no
  longer exists. There is no `BUILD_CCD_PROMPT` and no `generate_ccd()`.
- **Four vocabularies for the A/B choice**: `VIEW_A`/`VIEW_B` (display) → `"A"`/`"B"` →
  `MODE_CCD`/`MODE_DIRECT` → `basis="CCD"`/`"Post"` (returned by `build_persona`, then never
  read).
- **"CCD" names three things**: `cm` (the dict, inside `persona_core`), `ccd_struct` (same
  dict, returned by `build_persona`), and `run["ccd"]` (the 9-cell text from `cm_to_text`).

## Data flow

Mode A, post → reply:

```
persona_dashboard.render_build()          dashboard:316   collects post + mode + style
  └ core.build_persona(MODE_CCD, ...)     core:419
      ├ generate_ccd_psi()                core:166        API call #1 — prompts ① + ④
      │   └ _ccd_psi_prompt()             core:157        substitutes {patient_text}
      ├ cm_to_text()                      core:337        dict → the 9 cells the UI shows
      └ psi_persona_system()              core:362        fills ② from the CCD + PSI_PATIENT_TYPES
  └ core.chat_once(...)                   core:454        API call #2, once per turn
```

Mode B skips `generate_ccd_psi` and `psi_persona_system`; `build_persona` formats ③
directly with `{post_text}` and `{style_block}`.

Sample posts do **not** go through `persona_core`. `load_sample_posts()`
(`persona_dashboard.py:185`) reads `posts/index.json` itself, and the picker reads
`posts/<id>.txt`.

## The CCD format

Prompt ① is stamped `beck-pure-string-v4` and is called with `model=gpt-4o`,
`response_format={"type": "json_object"}`, `max_tokens=1500`. It returns five fields, all
plain strings:

```
life_history
core_belief
intermediate_beliefs
coping_strategies
cognitive_models        1–3 objects, each with situation, automatic_thoughts,
                        meaning_of_automatic_thought, emotion, behavior
```

Two conventions the prompt enforces: fields the post does not support are filled with
`insufficient information`, and uncertain inferences end with `?`.

The format carries no closed-set labels, no `{"text", "grounding", "evidence"}` boxes, and
no name field — personas are identified by `post_id`. `cm_to_text()` (`core:337`) flattens
the five fields into the nine cells shown under **CCD profile**.

## Backward compatibility

`persona_core` has seen three CCD shapes: the current plain strings, an intermediate
dual-field form (`{verbatim, label}`), and a `{text, grounding, evidence}` box form. The
accessors that absorb all three — `_is_box()`, `_box_display()`, `_box_text()`,
`_core_belief_text()`, `_emotion_text()` — are still live, so a CCD cached under an older
format still renders.

What the closed-set era left behind has been removed: the 19 core-belief labels, the 9
emotion categories, and `grounding_report()`, which audited evidence boxes the current
prompt does not emit and so scored 0/0 on everything generated today. The closed-set lists
now live in `experiments/test_3posts.py`, the only thing that still checks against them.
