# Persona Generation Interface

A Streamlit app that turns a Reddit post into a conversational persona and lets you chat
with it. Built on Patient-Ψ (Wang et al., EMNLP 2024), reproduced at the prompt level with
`gpt-4o`. No model training.

## Quickstart

Requires Python 3.11.

```bash
pip install -r requirements.txt
streamlit run persona_dashboard.py
```

Supply `OPENAI_API_KEY` one of two ways:

- A `.env` file in this directory containing `OPENAI_API_KEY=sk-...`
- `.streamlit/secrets.toml`, copied from `.streamlit/secrets.toml.example`

`APP_PASSWORD` is optional. When set, the app asks for a password before opening.

Never commit `.env` or `.streamlit/secrets.toml`. Both are gitignored.

## Using the app

**1. Provide a post.** Paste any post or self-description, or pick one of the 16 bundled
samples to fill the box.

**2. Choose a mode.**

| Mode | Path |
| --- | --- |
| A | post → Cognitive Conceptualization Diagram (CCD) → persona |
| B | post → persona |

**3. Choose a conversational style and chat model.** Six Patient-Ψ styles are available:
`plain`, `upset`, `verbose`, `reserved`, `tangent`, `pleasing`. The style is baked into the
system prompt at build time. The model choice, `gpt-4o` or `gpt-4o-mini`, applies to each
reply.

**4. Select Build**, then chat.

Available while chatting:

- **CCD profile** — the nine CCD cells, in mode A
- **Final system prompt sent to the model** — the fully assembled prompt
- **Source post used**
- **Edit prompts** — override any of the three prompts, with a reset button
- **Save / Load** — store a built persona and reload it later
- **Export** — download the transcript
- Token count and cost per call

## More

- [docs/code-map.md](docs/code-map.md) — where the prompts live, and why some names repeat
- [docs/pipeline.md](docs/pipeline.md) — what each mode calls
- [docs/DEPLOY.md](docs/DEPLOY.md) — deployment
