# VERIFICATION REPORT — Persona Pipeline (autonomous run, 2026-06-29)

Executed `AUTONOMOUS_GOAL.md` on the REMOTE machine while the coordinator was away
(remote kept running). This report is the **monitorable record**: every stage, the exact
command/function/file:line that runs it, and what role that code plays — so each step can
be checked for soundness.

App repo: `meetings/2026-06-24_week2/` (GitHub `sf062244868/persona-dashboard`, `main` = `6823936`).
Felix API: `meetings/2026-06-30-week3/ClusterSearch-API` (branch `Ray`).

---

## 0. TL;DR status
- ✅ Felix API up; `/health`,`/clusters`,`/pick` verified.
- ✅ pytest 5/5; Streamlit AppTest 0 exceptions.
- ✅ Quality gate (min-words + dedup + crisis-flag) implemented + verified.
- ✅ Unified pipeline: one `build_persona_record()` feeds both the 16-seed batch and live Cluster Search; cache (`personas.json`) is the seam.
- ✅ Public demo live via cloudflared (all 3 tabs work, incl. Cluster Search).
- ✅ Pushed to `main` (`6823936`); coordinator's parallel ngrok fix (`2bea023`) integrated by rebase.
- ⏳ Streamlit **Cloud** redeploy is still the coordinator's manual step (the tunnel demo below bypasses it).

---

## 1. 🔗 Public demo URL (remote stays on)
**App (all three tabs): https://creek-effect-affects-regions.trycloudflare.com**

- Verified: `GET /` → HTTP 200, `/_stcore/health` → `ok` through the tunnel.
- Why everything works here (unlike Streamlit Cloud): the Streamlit **server runs on the remote**, same machine as the Felix API and the OpenAI key (`shared/.env`). All LLM calls and all `/pick` calls happen **server-side on the remote**, so:
  - 🛠 Build → works (server has the key)
  - 📚 Persona Library → works (reads `personas.json`)
  - 🔎 Cluster Search → **works** (server calls `localhost:8000` internally — no public API needed)
- ⚠️ **Security/cost:** this URL is public and unauthenticated; using it spends the real OpenAI key. The trycloudflare subdomain is random/obscure and the tunnel is ephemeral. **Take it down when not demoing:** `pkill -f "cloudflared tunnel"`.
- Processes kept alive on the remote: `uvicorn api:app`(:8000), `streamlit run persona_dashboard.py`(:8501), `cloudflared tunnel`.
- Coordinator's parallel track (commit `2bea023`): exposing the **API** via **ngrok** so the *Streamlit Cloud* app can reach it (`CLUSTERSEARCH_API_URL` = ngrok URL). That is a different path to the same end; `cluster_api.py` now sends `ngrok-skip-browser-warning` + a non-browser UA so ngrok returns clean JSON.

---

## 2. 🗺 Complete end-to-end flow

```
══════════ AUTHORING (remote: has Felix API + OpenAI key + spends $) ══════════

 post source (3 interchangeable "heads")
 ┌─ 🛠 Build: paste text ─┬─ 📚 16 seed posts ─┬─ 🔎 Cluster Search ───────────┐
 │                        │ selected_posts.json│  GET /clusters → POST /pick    │
 │                        │                    │  (Felix ClusterSearch API)     │
 └────────────────────────┴──────────┬─────────┴───────────────┬───────────────┘
                                      │                         │
                                      │             ┌───────────▼───────────────┐
                                      │             │ QUALITY GATE               │
                                      │             │ filter_pick_posts():       │
                                      │             │  • drop < 30 words         │
                                      │             │  • dedup by title          │
                                      │             │  • safety_flag() ⚠️crisis  │
                                      │             └───────────┬───────────────┘
                                      └─────────────┬───────────┘
                                                    ▼  one normalized post
                          ★ build_persona_record()  (persona_core.py:420 — THE single path)
                            1) generate_ccd()        → Beck 5-section CCD   (gpt-4o)
                            2) persona_system_from_ccd() / build_persona(B)  → roleplay system prompt
                            3) generate_persona_profile() → persona_name + first-person bio (gpt-4o)
                            (+ safety_flag on the source content)
                                                    │  full persona record
                                                    ▼
                          〔💾 Save to Library〕→ persona_store.append_persona()
                                                    │ dedup by source_post_id, write
                                                    ▼
══════════════════ personas.json  (THE SEAM — authoring writes, serving reads) ═══════
                    16 curated seeds  +  cluster-search additions
                                                    │  commit + push
                                                    ▼
══════════ SERVING (anywhere incl. cloud / tunnel: reads file, NO Felix API) ══════════
   📚 Persona Library: dropdown → bio + CCD(5 cards) + chat
   chat → chat_once() → gpt-4o   (persona identity already baked into the system prompt)
```

---

## 3. 🔬 Per-step narrative (command · file:line · role)

### Source → post
| Step | Code (file:line) | Role |
|---|---|---|
| Felix API: list topics | `cluster_api.get_clusters()` `cluster_api.py:66` → `GET /clusters` | returns the 44 clusters `{id,name,n_posts}` for the picker |
| Felix API: fetch posts | `cluster_api.pick(cluster_id,n)` `cluster_api.py:70` → `POST /pick` | server-side cosine-similarity retrieval; returns top-N posts each with a ready `prompt` (Title+body) |
| HTTP hygiene | `_COMMON_HEADERS` `cluster_api.py:27` | `ngrok-skip-browser-warning` + non-browser UA so an ngrok tunnel returns JSON, not its interstitial (harmless locally) |
| 16 seed posts | `selected_posts.json` | the boss's 16 posts (full text recovered from Felix's pool) — input to the offline batch |

### Quality gate (Cluster Search only)
| Step | Code | Role |
|---|---|---|
| Filter candidates | `filter_pick_posts(posts, min_words=30)` `persona_core.py:389` | drops too-short (<30 words) + duplicate-title posts; attaches `safety_flag` to each kept post |
| Crisis detection | `safety_flag(text)` `persona_core.py:383` | regex keyword check (suicide / self-harm / "want to die" …) → UI shows ⚠️ + a caution before generating; never hard-blocks |
| UI wiring | `render_cluster()` `persona_dashboard.py:497` | applies the gate, reports "dropped N short + M dup", marks ⚠️ in the list |

### ★ post → CCD → persona  (the core; one shared function)
| # | Step | Code (file:line) | Model/Prompt | Role |
|---|---|---|---|---|
| 0 | Entry point | `build_persona_record(post)` `persona_core.py:420` | — | the SINGLE path used by both the 16-batch and live Cluster Search; returns the full persona record (same schema everywhere) |
| 1 | Build CCD | `generate_ccd(content)` `persona_core.py:260` | `gpt-4o` (`MODEL` `:38`) + `BUILD_CCD_PROMPT` `:51` | turns the raw post into a **Beck 5-section Cognitive Conceptualization Diagram** (Life History / Core Beliefs / Intermediate Beliefs / Coping / Cross-sectional Situations). Hash-cached so the same post isn't re-billed |
| 2a | Persona from CCD (Method A) | `persona_system_from_ccd(ccd)` `persona_core.py:327` | `PERSONA_FROM_CCD_PROMPT` `:83` (no API call) | fills the CCD into a roleplay **system prompt** — the persona's "identity" for chat |
| 2b | Persona from post (Method B) | `build_persona(MODE_DIRECT, content)` `persona_core.py:301` | `PERSONA_FROM_POST_PROMPT` `:102` (no API call) | alternative roleplay system prompt built straight from the post (no CCD) |
| 3 | Profile (display text) | `generate_persona_profile(content)` `persona_core.py:336` | `gpt-4o` + `PERSONA_PROFILE_PROMPT` `:123` | produces `persona_name` + a first-person **bio** (the text shown in the UI) |
| 4 | Safety tag | `safety_flag(content)` `persona_core.py:383` | — | record carries a crisis-content flag |
| — | Batch reuse | `build_one()` `build_personas.py:49` → calls `build_persona_record(...)`; `ensure_unique_names()` `:66` | — | the 16 seeds are produced by this same path, then names de-duplicated in one extra gpt-4o call |

### Cache (the seam) → serving
| Step | Code (file:line) | Role |
|---|---|---|
| Append to cache | `persona_store.append_persona(record)` `persona_store.py:23` | writes the record into `personas.json`, deduped by `source_post_id`; 16 are `source="curated"`, new ones `source="cluster-search"` |
| Read cache | `persona_store.read_personas()` `persona_store.py:17` / dashboard `load_personas()` (cached) | serving reads the file only — **no Felix API, no re-generation** |
| Display persona | `render_persona_panel()` `persona_dashboard.py:422` | one shared panel for Library + Cluster Search: bio, source badge (🌱 seed / 🔎 added), chat |
| CCD as cards | `render_ccd_sections(ccd)` `persona_dashboard.py:406` | splits the CCD into the 5 Beck sections as collapsible cards |
| Chat | `chat_once(messages)` `persona_core.py:454` | `gpt-4o` reply using the cached system prompt + history — the only serving-time LLM call; **uses no Felix API** |
| Top-level UI | `st.tabs([...])` `persona_dashboard.py:622` | single page, three tabs: Build / Persona Library / Cluster Search |

---

## 4. ✅ Verification commands + results (this run)
- `curl /health` → `{"status":"ok","clusters":44,"pool_posts":51081}`
- `curl /clusters` → 44 clusters · `POST /pick {cluster_id:..}` → posts with `prompt` field
- `pytest tests/` → **5 passed**
- `AppTest(persona_dashboard.py)` → **0 exceptions**; 3 tabs; widgets present
- `safety_flag()` → 4/4 correct (crisis vs benign)
- `filter_pick_posts()` on a 4-post fixture → dropped 1 short + 1 dup, kept 2, flagged the crisis post
- Live cycle earlier (cluster #17): `/pick` → `build_persona_record` → record schema identical to the 16 → `append_persona` (16→17) → read back (no API) → `chat_once` reply in-character → reverted to 16
- Rebased `2bea023` (coordinator's ngrok fix) → re-ran pytest/AppTest (still green) → pushed `6823936`
- Public URL `GET /` → 200; `/_stcore/health` → ok through cloudflared

---

## 5. Manual step still on the coordinator
- The **Streamlit Cloud** app (the `*.streamlit.app` URL) updates only when *that* app rebuilds from `main`. Source/branch/file were confirmed correct (`sf062244868/persona-dashboard` / `main` / `persona_dashboard.py`); `main` is at `6823936`. If it still shows old code: hard-refresh, then **Reboot** in Manage app, or delete+redeploy. Re-add `OPENAI_API_KEY` in Secrets.
- The **cloudflared demo URL above bypasses all of that** — it serves the latest directly from the remote.

## 6. How to take the demo down / restart
```
pkill -f "cloudflared tunnel"        # kill the public URL
pkill -f "streamlit run persona_dashboard"   # stop the app
pkill -f "uvicorn api:app"           # stop Felix API
# restart API:  cd .../ClusterSearch-API && ./.venv/bin/uvicorn api:app --port 8000
# restart app:  cd .../2026-06-24_week2 && /home/ray/ray/.venv/bin/streamlit run persona_dashboard.py --server.port 8501
# re-tunnel:    /home/ray/ray/cloudflared tunnel --url http://localhost:8501
```
