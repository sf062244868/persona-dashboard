# posts/

Sample posts for the app's post picker.

Each post is one `<post_id>.txt` file holding the full text, where `post_id` is the Reddit
submission ID. `index.json` lists the 16 posts the picker offers:

```json
{
  "posts": [
    {"id": "1hc3zyb", "title": "...", "subreddit": "r/relationship_advice"}
  ]
}
```

To add a post, write `<post_id>.txt` and add a matching entry to `index.json`.
