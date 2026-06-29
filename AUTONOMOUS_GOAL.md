# Autonomous Goal — Finalize, Quality-Gate, Public Demo & Deep Verification

Claude Code runs this autonomously on the REMOTE machine while the coordinator is away.
The remote machine STAYS ON (coordinator only disconnects their local). Execute fully,
verify everything, and leave a deeply detailed report. Log progress to
`VERIFICATION_REPORT.md` as you go.

## Guardrail overrides (confirmed by coordinator this session)
- **Pushing to `main` IS wanted** (supersedes the old "do not push / branch only" rule).
- Keep secrets out of any committed file (`.env`, keys). `.gitignore` already excludes them.
- Do NOT delete/move large data (pool stays symlinked). Do NOT batch-generate new personas
  (coordinator did NOT ask to grow the library — keep the curated 16 unless a test adds one,
  which must be reverted).

## Scope (what to accomplish)

### A. Full re-run + full verification + push
- Ensure Felix API is running (`uvicorn api:app --port 8000`); verify `/health`,`/clusters`,`/pick`.
- Run `pytest tests/` and a Streamlit `AppTest` on `persona_dashboard.py` → 0 exceptions.
- Confirm the 16 personas load and read-back (Library) needs no API.
- Commit + push to `main`. Verify `origin/main` HEAD matches local.

### B. Quality gate (apply in the Cluster Search candidate flow)
Add `quality.py` (or functions in `persona_core`) and wire into the Cluster Search post list:
1. **Min word count** — drop `/pick` posts below a threshold (default 30 words); show how many dropped.
2. **Dedup** — drop near-duplicate titles (normalized) within the returned list.
3. **Crisis-content flag** — `safety_flag(text)` keyword check (suicide / self-harm / "kill myself" / "end it" …). Flagged posts show a ⚠️ caution in the UI and `build_persona_record` attaches a `safety_flag` field. Do NOT hard-block (research may want them) — flag clearly.
Verify with unit-style checks (AppTest + direct function tests). Commit + push.

### C. Public demo via tunnel (remote stays on)
- Keep Streamlit on `:8501` and Felix API on `:8000`.
- Use `cloudflared` quick tunnels to expose BOTH as public HTTPS URLs.
- Point the app's Cluster Search at the API's public URL (set `CLUSTERSEARCH_API_URL`).
- Write the two public URLs into `VERIFICATION_REPORT.md` so the coordinator can click them.
- If `cloudflared` is unavailable, log it and fall back (document the local URLs + how to tunnel).

### D. Deep verification report (`VERIFICATION_REPORT.md`)
The coordinator wants to monitor that EVERY step is sound. Include:
1. A **complete end-to-end flow diagram** covering the whole system (sources → pipeline → cache → UI → chat), with the API and tunnel paths.
2. A **per-step narrative**: for each stage, state the exact **command/function**, the **file:line**, the **prompt/model** used, and **what role that code plays**. Especially detail **post → CCD → persona**:
   - `generate_ccd()` (which prompt = Beck 5-section, which model, caching),
   - `persona_system_from_ccd()` / `build_persona()` (how the system prompt is formed),
   - `generate_persona_profile()` (name + first-person bio),
   - `build_persona_record()` (the single shared path),
   - `persona_store.append_persona()` (cache seam),
   - `chat_once()` (serving-time chat).
3. Every verification command run + its result (tests, AppTest, endpoint checks).
4. The public demo URLs + how to use each tab.
5. The one manual step still on the coordinator (Streamlit Cloud redeploy, if they still want the Cloud app) + that the tunnel demo bypasses it.

## Acceptance checklist
- [ ] API up; `/health`,`/clusters`,`/pick` verified.
- [ ] pytest + AppTest = 0 failures/exceptions.
- [ ] Quality gate (min-words + dedup + crisis-flag) implemented, wired, verified.
- [ ] App + API exposed via public tunnels; URLs in the report; Cluster Search works through the public API.
- [ ] Everything committed + pushed to `main`; `origin/main` HEAD verified.
- [ ] `VERIFICATION_REPORT.md` has the full flow diagram + per-step narrative + commands/results + URLs.
- [ ] Any test-added persona reverted (library stays at 16).
