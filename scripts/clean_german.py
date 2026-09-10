"""German bank.

Two problems in the previous build, both traceable to one mislabelled file.
`app/data/raw/german/derewo-common.txt` is not DeReWo; it is an OpenSubtitles
frequency list. Using it directly as the target source meant:

  - 6,034 targets (20.1%) were also valid English words — "about", "above",
    "suits", "flats" — because subtitle corpora are full of untranslated lines.
  - Personal and place names rode along: giuseppe, claudio, milan, gannicus.

The fix is an intersection rather than a new download: a word only becomes a
target if the actual German dictionary (enz/german-wordlist) also contains it.
That list is 685k entries and keeps capitalization, which also solves the third
problem — every German noun in the old bank was lowercased, so "Apfel" shipped
as "apfel". Fold form drives matching, the capitalized form is kept for display.
"""

from __future__ import annotations

from scripts._common import (
    RAW,
    Entry,
    apply_target_policy,
    normalize,
    read_lines,
    read_ranked,
    report,
)

MAX_FREQ_TARGETS = 30_000

FALLBACK_DE = """
Apfel Birne Kirsche Erdbeere Banane Zitrone Melone Weintraube
Hund Katze Pferd Schaf Ziege Ente Huhn
Mutter Vater Bruder Schwester Tante Onkel Cousine Großmutter
Wasser Milch Brot Käse Butter Zucker Pfeffer Essig
Haus Wohnung Zimmer Küche Badezimmer Garten Garage Fenster
Straße Platz Brücke Bahnhof Flughafen Hafen Kirche Schule
Buch Zeitung Stift Heft Tafel Kreide Lineal Rucksack
Sonne Stern Himmel Wolke Regen Schnee Sturm
Berg Fluss Meer Strand Insel Wüste Wald Wiese
Montag Dienstag Mittwoch Donnerstag Freitag Samstag Sonntag Woche Monat
Januar Februar April August September Oktober November Dezember
Arbeit Firma Kunde Kollege Gehalt Urlaub Projekt
Geschichte Physik Chemie Biologie Musik Kunst Sport Informatik
Student Lehrer Krankenschwester Ingenieur Architekt Anwalt Richter Polizist
Computer Tastatur Bildschirm Drucker Programm Internet Browser
Regierung Parlament Kanzler Minister Gesetz Freiheit Demokratie Recht
Wirtschaft Markt Preis Kosten Gewinn Verlust Zinsen Bank Steuer
Familie Freund Freundin Nachbar Fremder Partner Kamerad
Freude Angst Trauer Hoffnung Liebe Stolz Scham Überraschung
Früher Später Gestern Heute Morgen Niemals Immer Manchmal Selten
Schnell Langsam Leise Schwer Leicht Warm Kalt
Blau Grün Gelb Schwarz Grau Braun Violett
Singen Tanzen Laufen Springen Schlafen Träumen Denken Glauben Lieben
Verstehen Erklären Sprechen Hören Lesen Schreiben Zeichnen Malen Bauen
Essen Trinken Kochen Backen Waschen Putzen Kaufen Verkaufen
Kraft Stärke Schwäche Zweifel Vertrauen Respekt
Energie Strom Spannung Widerstand Frequenz Molekül Gewebe
Gemälde Skulptur Zeichnung Fotografie Design Muster Stil
Stimme Stille Klang Melodie Rhythmus Harmonie
Reise Hotel Gepäck Koffer
Fahrrad Motorrad Flugzeug Schiff Straßenbahn
Restaurant Kellner Speisekarte Teller Gabel Messer Löffel Glas
Handschuhe Mantel Hemd Hose Schuhe Stiefel Kleid Krawatte
Geschäft Laden Kaufhaus Supermarkt Bäckerei Metzgerei Apotheke Kiosk
Vertrag Urteil Zeuge Verteidigung Anklage Gerichtssaal
Krankenhaus Operation Medikament Impfung Untersuchung Rezept Diagnose Therapie
Buchhaltung Bilanz Statistik Budget Haushalt Planung Strategie
Entwickler Software Hardware Algorithmus Datenbank Netzwerk Server
Künstler Musiker Schauspieler Tänzer Regisseur Autor Dichter Kritiker Publikum
""".split()


def build() -> tuple[dict[str, Entry], dict[str, int]]:
    entries: dict[str, Entry] = {}

    # Fold form -> the dictionary's own capitalization. German nouns are
    # capitalized, so this is the difference between "Apfel" and "apfel".
    display_of: dict[str, str] = {}

    def put(folded: str, source: str) -> Entry:
        entry = entries.get(folded)
        if entry is None:
            entry = Entry(fold=folded, display=folded)
            entries[folded] = entry
        entry.sources.add(source)
        return entry

    dictionary: set[str] = set()
    for raw in read_lines(RAW / "german" / "german-wordlist.txt"):
        folded = normalize(raw, "de")
        if folded is None:
            continue
        dictionary.add(folded)
        put(folded, "dictionary")
        # Prefer the capitalized spelling when the list carries both.
        if raw[:1].isupper() or folded not in display_of:
            display_of.setdefault(folded, raw)
            if raw[:1].isupper():
                display_of[folded] = raw

    # Frequency order decides which dictionary words become targets.
    promoted = 0
    for raw, rank in read_ranked(RAW / "german" / "derewo-common.txt"):
        folded = normalize(raw, "de")
        if folded is None:
            continue
        entry = put(folded, "frequency")
        entry.rank = rank if entry.rank is None else min(entry.rank, rank)
        # The intersection is the whole fix: subtitle-only strings stay in the
        # allowed list but never become answers.
        if folded in dictionary and promoted < MAX_FREQ_TARGETS:
            entry.is_target = True
            promoted += 1

    for offset, raw in enumerate(FALLBACK_DE):
        folded = normalize(raw, "de")
        if folded is None:
            continue
        entry = put(folded, "curated")
        entry.is_target = True
        if entry.rank is None:
            entry.rank = 1_000 + offset
        display_of.setdefault(folded, raw)
        if raw[:1].isupper():
            display_of[folded] = raw

    not_in_dictionary = sum(
        1 for e in entries.values() if "frequency" in e.sources and e.fold not in dictionary
    )

    blocked = apply_target_policy(entries)
    blocked["subtitle_only"] = not_in_dictionary

    for entry in entries.values():
        entry.display = display_of.get(entry.fold, entry.fold)

    return entries, blocked


def main() -> int:
    entries, blocked = build()
    report("de", entries, blocked)
    return 0


if __name__ == "__main__":
    main()
