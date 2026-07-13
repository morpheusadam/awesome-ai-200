# Contributing to Awesome AI 200

Thanks for your interest! This list is **data-driven and auto-generated**. You
never edit the `README*.md` files by hand — they are rebuilt from
[`data/repos.json`](data/repos.json) every week by
[`scripts/update.py`](scripts/update.py), so manual edits get overwritten.

## What lives where

| File | Purpose |
|------|---------|
| `data/repos.json` | The single source of truth — every repo, its stars, and its description in 6 languages. |
| `scripts/update.py` | Refreshes live stars, computes the trending list, discovers rising repos, and regenerates every `README`. |
| `README*.md` | Generated output, one per language. **Do not edit.** |

## Ways to help

- **Add / suggest a repo** — add an entry to `data/repos.json` (at minimum
  `name`, `url`, and a `desc.en`) and run the script; stars and translations
  can be filled in automatically or by a translator.
- **Improve a translation** — fix any `desc.<lang>` value in `data/repos.json`.
  The six languages are `en`, `zh`, `es`, `hi`, `ar`, `fa`.
- **Add a language** — extend `LANGS` and the `T` strings table in
  `scripts/update.py`, then add the matching `desc.<code>` values.
- **Tune trending / discovery** — the constants at the top of `update.py`
  (`DISCOVER_*`, `TRENDING_COUNT`) control how rising repos are found.

## Running it locally

```bash
# Python 3.10+. A token avoids rate limits.
GITHUB_TOKEN=<your_token> python scripts/update.py

# Render only, without hitting the network:
AAI_SKIP_FETCH=1 python scripts/update.py
```

Review the regenerated `README*.md` before opening a pull request.

## Ground rules

- Keep it **open source** and **AI / agent focused**.
- The star ranking is the arbiter — no manual reordering.
- One logical change per pull request.
