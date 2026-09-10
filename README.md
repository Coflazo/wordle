# Oflaz Wordle

Local-first multilingual Wordle for English, Turkish, and German. Word lengths 5–10 (attempts scale with length). Three pages: Welcome, Game, Profile. Every session runs on your laptop — no login, no cloud, no analytics.

The learning loop: **play word → fail or solve → open the meaning → the word enters your profile → mastery improves over time**.

## Stack

- **Backend:** Python 3.11 + FastAPI + SQLAlchemy + SQLite
- **Frontend:** vanilla HTML + CSS + JS (no build step)
- **Design system:** Google Stitch (see `design/stitch-refs.json`)
- **Word banks:** cleaned from six upstream repos (see §Sources)

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.build_wordbanks           # ~30 s — builds the six JSON word banks
uvicorn app.main:app --reload               # http://localhost:8000
```

Open `http://localhost:8000/` in your browser. On first run the SQLite DB is auto-created.

## Sources

| Language | Repo | Role |
| --- | --- | --- |
| Turkish | [halituzan/tdk-all-api](https://github.com/halituzan/tdk-all-api) | Meaning lookup (via Node subprocess) |
| Turkish | [utkusen/turkce-wordlist](https://github.com/utkusen/turkce-wordlist) | `corpus.txt` for word bank (**not** `wordlist.txt`) |
| Turkish | [agmmnn/tdk-cli](https://github.com/agmmnn/tdk-cli) | Local TDK CLI fallback |
| English | [dwyl/english-words](https://github.com/dwyl/english-words) | `words_alpha.txt` for word bank |
| English | [meetDeveloper/freeDictionaryAPI](https://github.com/meetDeveloper/freeDictionaryAPI) | Meaning lookup (dictionaryapi.dev) |
| German | [Jonny-exe/German-Words-Library](https://github.com/Jonny-exe/German-Words-Library) | Word bank |
| German | OpenThesaurus | Synonym/context lookup |

## Attempts by length

| Length | Attempts |
| ---: | ---: |
| 5 | 6 |
| 6 | 7 |
| 7 | 7 |
| 8 | 8 |
| 9 | 8 |
| 10 | 9 |

Chill difficulty adds +1 attempt.

## Layout

See `design/architecture.md` for the full folder tree and API reference.

## License

MIT for the app code. Upstream word sources retain their own licenses.
