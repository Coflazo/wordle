"""TDK adapter for Turkish meanings.

Preferred path: `sozluk.gov.tr/gts?ara=<word>` (the underlying JSON endpoint
that tdk-all-api and tdk-cli both wrap). We call it directly so we don't need
a Node subprocess. If that fails we shell out to the `tdk` CLI if present.
"""

from __future__ import annotations

import asyncio
import shutil
from typing import Dict, List

import httpx

GTS_URL = "https://sozluk.gov.tr/gts"
UA = "OflazWordle/0.1 (contact: cagan04oflazoglu@gmail.com)"
TIMEOUT = httpx.Timeout(10.0)


async def lookup(word: str) -> Dict:
    data = await _fetch_gts(word)
    if data is None:
        cli_payload = await _try_cli(word)
        if cli_payload is not None:
            return cli_payload
        return _empty(word)

    return _normalize(word, data)


async def _fetch_gts(word: str):
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT, headers={"User-Agent": UA}
        ) as client:
            resp = await client.get(GTS_URL, params={"ara": word})
        if resp.status_code != 200:
            return None
        data = resp.json()
        if isinstance(data, dict) and data.get("error"):
            return None
        if not isinstance(data, list) or not data:
            return None
        return data
    except Exception:
        return None


def _normalize(word: str, data: List[dict]) -> Dict:
    entries: List[dict] = []
    compounds: List[str] = []
    proverbs: List[str] = []

    for lemma in data:
        # anlamlarListe has the meanings
        for meaning in lemma.get("anlamlarListe", []) or []:
            pos = None
            ozelliklerListe = meaning.get("ozelliklerListe") or []
            for prop in ozelliklerListe:
                if prop.get("tur") == "3" and prop.get("tam_adi"):
                    pos = prop["tam_adi"]
                    break
            example = None
            ornekler = meaning.get("orneklerListe") or []
            if ornekler and ornekler[0].get("ornek"):
                example = ornekler[0]["ornek"]
            entries.append(
                {
                    "part_of_speech": pos,
                    "definition": meaning.get("anlam"),
                    "example": example,
                    "synonyms": [],
                    "antonyms": [],
                }
            )
        # birlesikler = compound words; atasozu = proverbs
        for cw in (lemma.get("birlesikler") or "").split(","):
            cw = cw.strip()
            if cw:
                compounds.append(cw)
        for prov in lemma.get("atasozu", []) or []:
            if isinstance(prov, dict) and prov.get("madde"):
                proverbs.append(prov["madde"])

    return {
        "word": word,
        "phonetic": None,
        "audio_url": None,
        "entries": entries or [],
        "extras": {
            "compounds": compounds[:8],
            "proverbs": proverbs[:8],
        },
        "source": "tdk-all-api",
        "source_label": "TDK",
    }


async def _try_cli(word: str) -> Dict | None:
    cli = shutil.which("tdk")
    if cli is None:
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            cli,
            "search",
            word,
            "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=8.0)
        if proc.returncode != 0 or not stdout:
            return None
        import json

        parsed = json.loads(stdout.decode("utf-8", errors="ignore"))
        if isinstance(parsed, list):
            return _normalize(word, parsed)
    except Exception:
        return None
    return None


def _empty(word: str) -> Dict:
    return {
        "word": word,
        "phonetic": None,
        "audio_url": None,
        "entries": [],
        "extras": {"error": "TDK'da bulunamadı"},
        "source": "tdk-all-api",
        "source_label": "TDK",
    }
