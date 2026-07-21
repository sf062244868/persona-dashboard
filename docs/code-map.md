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
docs/                   this file, pipeline.md, DEPLOY.md
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
| ① | post → CCD JSON | `BUILD_CCD_PROMPT_PSI` | **172–193** | yes |
| ② | roleplay, mode A (from CCD) | `PSI_PERSONA_SYSTEM_TEMPLATE` | **267–291** | yes |
| ③ | roleplay, mode B (from post) | `PERSONA_FROM_POST_PROMPT` | **48–70** | yes |
| ④ | JSON-format instruction for ① | *(none — inline literal)* | **229** | **no** |

④ is the system message `"You reconstruct Beck cognitive conceptualization diagrams and
reply with a single JSON object."`, hardcoded inside the `chat.completions.create` call in
`generate_ccd_psi()`. It is sent on every mode-A build alongside ①. Anyone auditing the
prompts should read it too — it will not appear in the UI or in a search for `PROMPT`.

Two more blocks are prompt *fragments* rather than whole prompts:

| Constant | `persona_core.py` | Injected into | Used in |
| --- | --- | --- | --- |
| `PSI_PATIENT_TYPES` | 252 | `{style_content}` of ② | mode A only |
| `CONVERSATION_STYLES` | 83 | `{style_block}` of ③ | mode B only |

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

- **Two style dictionaries with identical keys.** `CONVERSATION_STYLES` (`:83`) and
  `PSI_PATIENT_TYPES` (`:252`) both have `plain / upset / verbose / reserved / tangent /
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
- **`style_temp_controls()`** (`persona_dashboard.py:161`) no longer controls temperature.
  It returns `(style, model)`.

## Data flow

Mode A, post → reply:

```
persona_dashboard.render_build()          dashboard:316   collects post + mode + style
  └ core.build_persona(MODE_CCD, ...)     core:567
      ├ generate_ccd_psi()                core:207        API call #1 — prompts ① + ④
      │   └ _ccd_psi_prompt()             core:196        substitutes {patient_text}
      ├ cm_to_text()                      core:407        dict → the 9 cells the UI shows
      └ psi_persona_system()              core:510        fills ② from the CCD + PSI_PATIENT_TYPES
  └ core.chat_once(...)                   core:606        API call #2, once per turn
```

Mode B skips `generate_ccd_psi` and `psi_persona_system`; `build_persona` formats ③
directly with `{post_text}` and `{style_block}`.

Sample posts do **not** go through `persona_core`. `load_sample_posts()`
(`persona_dashboard.py:185`) reads `posts/index.json` itself, and the picker reads
`posts/<id>.txt`.

## Legacy code kept on purpose

- `grounding_report()` (`core:458`) audits `{text, grounding, evidence}` boxes. The current
  CCD format has no such boxes, so it reports 0/0 on anything generated today. It is kept
  only so previously cached CCDs remain auditable.
- The closed-set machinery — `PSI_CORE_BELIEFS` (`:127`), `PSI_CORE_BELIEF_LABELS` (`:143`),
  `PSI_EMOTIONS` (`:146`), `_core_belief_labels()` (`:321`), `_emotion_labels()` (`:337`),
  `_dual_line()` (`:363`) — belongs to an earlier CCD format that used closed-set labels.
  The current format is plain strings throughout, so these are only reachable through
  backward-compatibility branches.
