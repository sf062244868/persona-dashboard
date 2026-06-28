# PROGRESS REPORT — ClusterSearch + Streamlit Integration

Executing `meetings/2026-06-30-week3/REMOTE_GOAL.md` autonomously on the REMOTE machine.
Date: 2026-06-28. **No `git push`** (per hard guardrail).

App repo (user's Streamlit app): `meetings/2026-06-24_week2/` (GitHub `sf062244868/persona-dashboard`).
Felix's API will be cloned OUTSIDE this repo at `meetings/2026-06-30-week3/ClusterSearch-API`.

---

## Phase 0 — Discovery

1. **Streamlit entry file & side-by-side A&B location**
   - Entry: `persona_dashboard.py` (`streamlit run persona_dashboard.py`).
   - The side-by-side A·B view was the `VIEW_AB` mode + a two-column chat render. **Already removed** in earlier work (T1); the app keeps Method A / Method B as a single-column selectable radio. (User confirmed keeping A/B selectable over the doc's "single-method" wording.)

2. **Existing LLM / "CCD" inference function**
   - `persona_core.generate_ccd(post_text, ccd_prompt=None)` → wraps `post_text` in `BUILD_CCD_PROMPT` (Beck CCD) and calls `gpt-4o`; returns `(ccd_text, saved_path, info)`. In-memory cache by hash.
   - `persona_core.chat_once(messages)` → raw chat completion, returns `(reply, info)`.
   - Note for T3: Felix's API returns a ready-made `prompt` per post ("use as-is"), so it must NOT be re-wrapped by `BUILD_CCD_PROMPT`. Plan: add a thin `run_prompt_inference(prompt)` to `persona_core` that sends the prompt straight to `gpt-4o` (reusing the same client/model).

3. **Persona generation + 16 posts source + cache**
   - Generation: `build_personas.py` (pipeline) using `persona_core.generate_ccd` / `build_persona` / `generate_persona_profile`.
   - 16 posts source: `selected_posts.json` (Felix's 8 themes × 2; full text recovered from his pool — Reddit is IP-blocked from this machine).
   - Persona cache: `personas.json` (16 records; shown via the `pages/1_Persona_Library.py` dropdown; no live LLM at view time).

---

## Execution log

### Phase 1 — Felix's API ✅
- Cloned `https://github.com/Irl-Felix/ClusterSearch-API` → `meetings/2026-06-30-week3/ClusterSearch-API`, checked out branch `Ray`. Repo bundles `assets/` (cluster_centroids.npy, cluster_profiles.json); `pool/` is gitignored.
- **Decision (pool.zip):** pool.zip not needed — the required pool files already exist locally at `meetings/2026-06-24_week2/felix_files/Phase2/pool/`. **Symlinked** them into `ClusterSearch-API/pool/` (no copy/move of large files, per guardrail). Verified compatibility: pool_embeddings (51081×1536) ↔ centroids (44×1536) dims match; pool_index rows (51081) == embeddings rows; all columns the API reads (subreddit/title/selftext_clean/url/word_count) present.
- Created dedicated venv (`ClusterSearch-API/.venv`, Python 3.13.5) + `pip install -r requirements.txt` (fastapi 0.138, uvicorn 0.49, numpy 2.5, pandas 3.0).
- Started `uvicorn api:app --port 8000` (background). Up in ~2s. Log: "Loaded 44 clusters | 51,081 pool posts".
- **Verified:**
  - `GET /health` → `{"status":"ok","clusters":44,"pool_posts":51081}`
  - `GET /clusters` → 44 clusters.
  - `POST /pick {"cluster_name":"Relationship"}` → 409 multi-match (correct: matches 3 clusters). `{"cluster_name":"Pet Adventures","n":3}` → 872 matches, posts each with `rank/similarity/subreddit/title/body/url/word_count/prompt`. `{"cluster_id":11,"n":1}` → ok.
- **Correction to Phase 0 note:** the API's `prompt` field is just `"Title: {title}\n\n{body}"` (the raw post material), NOT a finished CCD instruction. So T3 will feed it straight into the EXISTING `persona_core.generate_ccd()` (which wraps it in the Beck CCD prompt) and display the CCD — reusing the inference fn, no rewrite.

### Phase 2 — Integration ✅
- **T1 (remove A&B side-by-side):** done in earlier work — `VIEW_AB` mode + the two-column chat pane removed; Method A/B remain as a single-column selectable radio. **User explicitly chose to keep A/B selectable** over the doc's "single-method" wording (logged decision). Result view is single-column either way; no leftover empty columns / dead toggles.
- **T2 (16 personas, pre-computed + dropdown):** done — `build_personas.py` generated `personas.json` (16 records, 1 post→1 persona). `pages/1_Persona_Library.py` shows them via a dropdown; selecting reads the cache and (per user choice) can chat using the cached system prompt — **no LLM call to build the persona at view time**.
- **T3 (ClusterSearch dynamic track):** NEW. Added:
  - `cluster_api.py` — stdlib-urllib client for `/clusters`, `/pick`, `/health`. Base URL configurable via `CLUSTERSEARCH_API_URL` env var (default `http://localhost:8000`), also overridable in the page sidebar.
  - `pages/2_Cluster_Search.py` — cluster picker (from `GET /clusters`) → `POST /pick` (by cluster_id, avoids name-fragment 409) → pick a returned post → its `prompt` fed into the EXISTING `persona_core.generate_ccd()` → CCD displayed. **Simple view only** (no intermediate-artifact complex view). On-demand CCD generation (per post) keeps cost controlled.
- **One coherent pipeline:** cluster → `/pick` → `prompt` → existing CCD inference → display. API URL configurable. ✅

### Phase 3 — End-to-end test ✅
- `cluster_api` against live API: `/health` ok, `/clusters`=44, `/pick` returns posts with `prompt`.
- Full pipeline live: `pick(cluster_id=23)` → `generate_ccd(prompt)` produced a 2,547-char CCD (1,110 tok). ✅
- Streamlit `AppTest` (in-process, runs each page's script): `persona_dashboard.py`, `pages/1_Persona_Library.py`, `pages/2_Cluster_Search.py` → **0 exceptions** each.
- Real server boot (headless): `/`, `/Persona_Library`, `/Cluster_Search` all HTTP 200; no errors in server log; API stayed healthy.
- `pytest tests/` → 5 passed.
- **Note on screenshots:** the doc asks for screenshots, but the app runs on the remote machine's localhost and the browser tool drives the *local* machine's Chrome (can't reach remote localhost), and this run is autonomous/headless. Substituted with AppTest (full script execution, 0 exceptions) + live endpoint/pipeline verification, which is stronger functional evidence than a screenshot.

### Phase 4 — Commit (NO push)
- Branch: `feature/clustersearch-integration` in the app repo. Committed; **not pushed** (per guardrail).
- Felix's API repo (`ClusterSearch-API`) is a SEPARATE clone outside this repo — not committed here.
- `patients_ccd/` stays gitignored (CCD text is embedded in `personas.json`). No secrets committed (`.env` gitignored).

---

## Acceptance checklist
- [x] Felix API runs; `/health`, `/clusters`, `/pick` verified.
- [x] Streamlit: no A&B side-by-side; single-column result (A/B selectable, per user).
- [x] 16 personas cached + shown via dropdown, no live regeneration.
- [x] Cluster → `/pick` → existing CCD inference → result shown (simple view).
- [x] One coherent pipeline; API URL configurable.
- [x] Changes committed to a new branch; **nothing pushed**.
- [x] `PROGRESS_REPORT.md` written.

## Decisions made
- Keep Method A/B selectable (single column) instead of fully single-method — per explicit user choice.
- Reused local pool via symlink instead of fetching pool.zip (sizes/dims verified compatible).
- T3 CCD generation is on-demand per post (not auto for all n) to control gpt-4o cost; still satisfies "feed each post's prompt → CCD".
- Dedicated venv for the API (Python 3.13) to avoid mutating the user's main env.

## State / next steps for the user
- **Felix's API is left RUNNING** on `http://localhost:8000` (background uvicorn) so the Cluster Search page works immediately. To stop: `pkill -f "uvicorn api:app"`. To restart: `cd meetings/2026-06-30-week3/ClusterSearch-API && ./.venv/bin/uvicorn api:app --port 8000`.
- **Review the branch `feature/clustersearch-integration`, then push it yourself** (I did not push).
- Run the app: `cd meetings/2026-06-24_week2 && streamlit run persona_dashboard.py` → pages: Persona Library (T2), Cluster Search (T3).
- The "complex view" (intermediate pipeline artifacts) for T3 was intentionally NOT built — awaiting your separate spec.
