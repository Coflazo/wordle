# Oflaz Wordle

Guess words from 5 to 10 letters in **English, Turkish or German**, then learn what they mean.
Everything runs on your own machine. No account, no cloud, no analytics.

<p align="center">
  <img src="docs/playthrough.gif" alt="A game of Oflaz Wordle: guessing CRANE, asking the solver for a hint, then solving TREAT" width="680">
</p>

## Install

One line. Pick your system.

**macOS / Linux**

```bash
curl -fsSL https://raw.githubusercontent.com/Coflazo/wordle/main/install.sh | bash
```

**Windows** (PowerShell)

```powershell
irm https://raw.githubusercontent.com/Coflazo/wordle/main/install.ps1 | iex
```

The installer fetches the repo, installs Python and a C++ compiler if you do not
have them, builds everything, and opens the game.

## Start

```bash
python run.py
```

That is the whole thing. It builds anything missing, starts the server, and opens
your browser at `http://localhost:8000`. Press Ctrl+C to stop.

## How to play

Guess the hidden word. After each guess every letter is coloured:

| Tile | Meaning |
| --- | --- |
| **Green** | Right letter, right place |
| **Yellow** | The word has this letter, somewhere else |
| **Grey** | Not in the word at all |

Type with your keyboard or tap the one on screen, then press Enter. Repeated
letters are counted properly: if the answer is SPEED and you guess ERASE, only
one E can be credited, and the E already in the right place claims it.

Run out of guesses and the word is revealed. Either way you can open the meaning
panel to see what it meant, and that word goes into your profile. Solve it a few
times and read its meaning, and it counts as mastered.

**Difficulty** changes which words you get, not just how many guesses:

- **Chill** — everyday words, one extra guess
- **Classic** — common and mid-frequency words
- **Scholar** — rarer words, no extra guess

**Hint** shows which words still fit and which guess would narrow it down most,
measured in bits of information.

**Today's puzzle** is the same word for everyone, in whichever language you pick,
changing at your local midnight. Solve it and you can copy a spoiler-free grid to
paste at a friend:

```
Oflaz Wordle #252 EN 3/6

⬛🟨⬛⬛🟩
⬛⬛🟨🟩🟩
🟩🟩🟩🟩🟩
```

The app keeps working without a connection. Finished games, your stats and the
meanings you have already looked up stay available; new guesses need the local
server, which is on your own machine anyway.

## How it works

A Python web server for the pages and your history, and a C++ core for the parts
that need to be fast.

```
frontend/     plain HTML, CSS and JS. No build step, no framework.
              Works offline through a service worker.
app/          FastAPI + SQLite. Games, profiles, stats, dictionary lookups.
native/       C++20, built as the Python module wordle_core.
solverd/      C++ solver daemon. Optional; hints work without it.
scripts/      builds the word banks from public word lists.
```

The C++ core handles four things Python was bad at:

- **Text.** Lowercasing is not the same in every language. `İSTANBUL` has eight
  letters, but Python's `lower()` turns it into nine characters, and `KIZIL`
  becomes `kizil`, which is not a word. One piece of C++ does the folding for
  both the game and the word-bank builder, so a word is never stored in one form
  and looked up in another.
- **Word banks.** The three languages hold about 590,000 words. They are packed
  into a binary file that is memory-mapped, so startup costs one system call
  instead of parsing 8 MB of JSON into 74 MB of Python objects.
- **Scoring.** Words are packed into five bits per letter, and a guess is scored
  in about 12 nanoseconds.
- **Hints.** Working out which guess narrows the answer most means scoring every
  candidate against every possible guess. In Turkish that is 29 million
  combinations for a single turn, spread across a thread pool.

Word difficulty comes from how common a word is, blended with how many turns the
C++ solver needs to reach it under optimal play, which is what makes the
difficulty setting real. A word can be common and still hard: "mummy" repeats
letters and shares a rhyme family, so it survives longer than its frequency
suggests.

Your games, your vocabulary and your stats live in `oflaz_wordle.db` next to the
code. Delete that file and you start over.

## Requirements

- **Python 3.11 or newer**
- **A C++20 compiler** — Apple command line tools, GCC, Clang, or MSVC on Windows
- About **200 MB** of disk, mostly the word lists
- A connection the first time, to download the word lists

The installer sets up anything missing. macOS and Linux reach the solver daemon
over a Unix socket; Windows uses a loopback port with a shared token instead,
because Python on Windows cannot open the first kind. Either way the daemon is
optional: if it is not running, hints are computed inside the web server.

## Development

```bash
python run.py --reload          # restart on file changes
python -m pytest tests -q       # 151 tests
python -m scripts.build_wordbanks --difficulty   # rebuild banks, run the solver sweep
cd solverd && make              # build the solver daemon
```

Useful environment variables: `WORDLE_DEBUG=1` opens the bank diagnostics
endpoint, `WORDLE_DB_URL` points at a different database, `WORDLE_CORS_ORIGINS`
allows a frontend on another origin.

## Word sources

| Language | Source | Used for |
| --- | --- | --- |
| English | [dwyl/english-words](https://github.com/dwyl/english-words) | Accepted guesses |
| English | [first20hours/google-10000-english](https://github.com/first20hours/google-10000-english) | Which words are answers |
| English | [dictionaryapi.dev](https://dictionaryapi.dev) | Meanings |
| All three | [Wiktionary](https://en.wiktionary.org) | Meanings, when the source above has none |
| Turkish | [CanNuhlar/Turkce-Kelime-Listesi](https://github.com/CanNuhlar/Turkce-Kelime-Listesi) | Word bank |
| Turkish | [TDK Sözlük](https://sozluk.gov.tr) | Meanings |
| German | [enz/german-wordlist](https://github.com/enz/german-wordlist) | Word bank |
| German | [OpenThesaurus](https://www.openthesaurus.de) | Synonyms |

Answers are filtered: no slurs, no proper nouns, no verb infinitives, and nothing
that is only in the list because a film subtitle used it. Rude but real words
stay playable as guesses; they are simply never the answer.

## Licence

MIT for the code. Each word source keeps its own licence.
