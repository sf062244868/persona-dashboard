# Deployment

The app runs on Streamlit Community Cloud from the `sf062244868/persona-dashboard`
repository, with `persona_dashboard.py` as the main file.

## Update a running deployment

```bash
git push origin main
```

Streamlit Cloud rebuilds automatically. Deployments read `main`, so anything unpushed is
not live.

Streamlit caches loaded data with `@st.cache_data`. A push does not clear that cache. If
the app still serves old data after a successful rebuild, open the app dashboard and choose
**Manage → Reboot app**.

## Deploy a new instance

1. Sign in to [share.streamlit.io](https://share.streamlit.io) with GitHub.
2. Choose **Create app**, select the repository, branch `main`, and set the main file path
   to `persona_dashboard.py`.
3. Under **Advanced settings → Secrets**, add:

   ```toml
   OPENAI_API_KEY = "sk-proj-..."
   APP_PASSWORD   = "..."
   ```

4. Choose **Deploy**. The first build takes one to three minutes.

`.streamlit/secrets.toml.example` is the template. The real `secrets.toml` is gitignored and
must never be committed.

## Access control

`APP_PASSWORD` gates the app whenever it is set. To restrict access further, use
**Settings → Sharing** and limit "Who can view" to specific email addresses.

Set a monthly spending cap under OpenAI **Billing → Usage limits**. The app calls `gpt-4o`
on every build and every chat turn, and a public URL is a public spend.

## Alternative host

Hugging Face Spaces works with the same code: create a Space with the Streamlit SDK, push
the repository, and set `OPENAI_API_KEY` and `APP_PASSWORD` under the Space's Secrets. Only
the deployment platform and the secrets UI differ.
