"""Wiktionary adapter.

Exists because a single upstream is a single point of failure, and the one this
project started with proved it: dictionaryapi.dev stopped answering entirely and
every English lookup came back empty. Wiktionary covers all three languages, so
it backs up each of them.

The REST endpoint returns definitions as HTML fragments, so they are stripped to
text here rather than being handed to the client, which renders with textContent.
"""

from __future__ import annotations

import html
import logging
from html.parser import HTMLParser
from typing import Dict, List
from urllib.parse import quote

import httpx

from app import config

log = logging.getLogger("wordle.dictionary.wiktionary")

# en.wiktionary only. The definition endpoint is a REST extension that the
# German and Turkish Wiktionaries do not enable — both answer 501 — while the
# English one carries entries for every language, keyed by language code.
HOST = "en.wiktionary.org"
TIMEOUT = httpx.Timeout(config.DICTIONARY_TIMEOUT, connect=4.0)
USER_AGENT = "OflazWordle/1.0 (local vocabulary game; contact: cagan04oflazoglu@gmail.com)"

MAX_ENTRIES = 6
MAX_DEFINITION_CHARS = 400


class _TextOnly(HTMLParser):
    """Collapse an HTML fragment to plain text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        # Wiktionary embeds colour swatches and other decorations inside
        # examples; their text is markup noise, not part of the sentence.
        if tag in {"style", "script"} or dict(attrs).get("class", "").startswith("color-panel"):
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return " ".join("".join(self.parts).split())


def strip_html(fragment: str | None) -> str:
    if not fragment:
        return ""
    parser = _TextOnly()
    parser.feed(html.unescape(fragment))
    parser.close()
    return parser.text()


async def lookup(word: str, language: str, display: str | None = None) -> Dict:
    """Look the word up, trying its display spelling first.

    Wiktionary headwords are case-sensitive, and German nouns are capitalized:
    "Apfel" has a German entry, "apfel" has none. The bank already knows the
    display form, so try that before the folded one.
    """
    forms = []
    for form in (display, word):
        if form and form not in forms:
            forms.append(form)

    unreachable = False
    for form in forms:
        payload = await _fetch(form, language)
        if payload["entries"]:
            payload["word"] = word
            return payload
        unreachable = unreachable or payload["extras"].get("error") == "source_unreachable"
    return _empty(word, unreachable=unreachable)


async def _fetch(word: str, language: str) -> Dict:
    url = f"https://{HOST}/api/rest_v1/page/definition/{quote(word, safe='')}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        log.info("wiktionary unreachable for %r: %s", word, exc)
        return _empty(word, unreachable=True)

    if response.status_code == 404:
        return _empty(word)
    if response.status_code != 200:
        return _empty(word, unreachable=True)
    try:
        data = response.json()
    except ValueError:
        return _empty(word, unreachable=True)
    if not isinstance(data, dict):
        return _empty(word)

    # Prefer the section written in the word's own language.
    blocks = data.get(language) or data.get("en") or []
    entries: List[Dict] = []
    for block in blocks:
        part_of_speech = block.get("partOfSpeech")
        for item in block.get("definitions") or []:
            definition = strip_html(item.get("definition"))
            if not definition:
                continue  # Wiktionary emits empty headings between senses
            example = ""
            for sample in (item.get("parsedExamples") or item.get("examples") or []):
                example = strip_html(sample.get("example") if isinstance(sample, dict) else sample)
                if example:
                    break
            entries.append({
                "part_of_speech": part_of_speech,
                "definition": definition[:MAX_DEFINITION_CHARS],
                "example": example[:MAX_DEFINITION_CHARS] or None,
                "synonyms": [],
                "antonyms": [],
            })
            if len(entries) >= MAX_ENTRIES:
                break
        if len(entries) >= MAX_ENTRIES:
            break

    return {
        "word": word,
        "phonetic": None,
        "audio_url": None,
        "entries": entries,
        "extras": {} if entries else {"error": "not_found"},
        "source": "wiktionary",
        "source_label": "Wiktionary",
    }


def _empty(word: str, unreachable: bool = False) -> Dict:
    return {
        "word": word,
        "phonetic": None,
        "audio_url": None,
        "entries": [],
        "extras": {"error": "source_unreachable" if unreachable else "not_found"},
        "source": "wiktionary",
        "source_label": "Wiktionary",
    }
