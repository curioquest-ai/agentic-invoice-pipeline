# 01-form — Data entry form + invoice renderer
```bash
uvicorn app:app --port 8000
```
`GET /` = the form the bot fills · `GET /invoice/{id}` = the printable invoice.
The server renders input **verbatim, never validates** — it stands in for every
legacy ERP entry screen, and those don't fix your typos either. Chaos lives in
the data, not the renderer.

**Gotcha** — Forms without stable id/name attributes force bots into brittle
XPath guessing. Accessibility and automatability are the same property. (Every
input here has a stable `id`; that's why `bot.py` is 15 lines of fills, not 80
lines of selectors.)
