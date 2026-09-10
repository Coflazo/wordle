"""Turkish bank.

Three filters that the previous build did not have, each fixing a measured
problem in the shipped targets:

1. Infinitives. 4,295 targets (10%) ended in -mek/-mak. "abanmak" is a
   dictionary entry but nobody guesses a verb in its citation form.
2. Potential-mood nominals. 440 targets ended in -abilme/-ebilme
   ("abanabilme", "acikabilme") — grammatical, unguessable.
3. De-diacriticized twins. 198 pairs like aksam/aksam and bakir/bakir sat in
   targets together. The ASCII form comes from a transliterated corpus, not from
   Turkish orthography, so it is demoted to allowed-only: a player who types it
   is accepted, but the game never asks for it.

There is no Turkish frequency corpus in the sources, so tiers come from a
documented heuristic (curated core, source agreement, derivational depth,
length) rather than counts. That is stated rather than hidden.
"""

from __future__ import annotations

import wordle_core as wc

from scripts._common import (
    RAW,
    Entry,
    apply_target_policy,
    normalize,
    read_lines,
    report,
)

INFINITIVE_SUFFIXES = ("mek", "mak")
POTENTIAL_SUFFIXES = ("abilme", "ebilme", "yabilme", "yebilme")

# Derivational suffixes, deepest first. Each one a word carries makes it less
# likely to be everyday vocabulary.
DERIVATIONAL = (
    "sizlik", "lilik", "cilik", "cilik", "lastirma", "lestirme",
    "sizlık", "lılık", "cılık", "çılık", "laştırma", "leştirme",
    "lik", "lık", "luk", "lük",
    "ci", "cı", "cu", "cü", "çi", "çı", "çu", "çü",
    "siz", "sız", "suz", "süz",
    "li", "lı", "lu", "lü",
    "ici", "ıcı", "ucu", "ücü",
    "ış", "iş", "uş", "üş",
)

FALLBACK_TR = """
kalem masa kitap şeker ekmek tebeşir balık yolcu havlu gemi
elma armut erik kiraz hediye paket süpürge teyze yıldız güneş
gökyüzü sokak şehir köylü müzik radyo televizyon bilgisayar telefon
araba otobüs tramvay metro bisiklet kaptan asker
profesör öğretmen öğrenci mimar doktor hemşire polis hakim avukat
hesap matematik tarih coğrafya fizik kimya biyoloji edebiyat felsefe
ekonomi şirket borsa döviz enflasyon gelir gider fatura
peynir zeytin tereyağı yumurta salatalık domates biber sarımsak soğan
portakal limon çilek karpuz kavun mandalina greyfurt incir
kalemtıraş defter silgi cetvel kağıt mürekkep kalemlik çanta sıra
pencere kapı perde koltuk yatak yastık battaniye halı
sabah akşam gece gündüz hafta günler saat dakika saniye
kaleci forvet futbol basketbol voleybol yüzücü boksör hakem stadyum
atkı bere eldiven palto çizme gömlek pantolon kravat şapka
resim müze tiyatro opera sinema konser festival sergi galeri
roman hikaye şiir masal destan efsane atasözü deyim
yağmur fırtına rüzgar bulut sıcaklık soğukluk nemli
sağlık ilaç hastane poliklinik reçete tansiyon
arkadaş kardeş anne baba dayı hala amca dede nine
ağabey abla kuzen yeğen gelin damat kayınpeder kayınvalide enişte
duygu sevinç üzüntü mutluluk hüzün özlem umut korku şaşkınlık
başarı emek sabır güven cesaret dürüstlük adalet dostluk sadakat
ışık gölge renk kırmızı mavi yeşil sarı siyah beyaz
denizci balıkçı tayfa tekne yelken liman sahil kıyı
orman vadi göl nehir ırmak şelale dere
kelebek karınca örümcek sinek fare tavşan koyun keçi
kaplan aslan zürafa ceylan kartal şahin güvercin serçe
kompozisyon dilbilgisi imla yazım cümle paragraf özne yüklem tümleç
elektrik manyetik atomik moleküler kimyasal biyolojik fiziksel
işletme muhasebe yönetim planlama strateji pazarlama satış reklam marka
ekonomik finansal yatırım tasarruf kredi borç varlık kaynak değer
araştırma gözlem deney hipotez teori sonuç analiz sentez yorum
sanayi teknoloji yazılım donanım robotik otomasyon makine cihaz alet
tarım hasat tohum gübre sulama çiftlik harman
belediye valilik kaymakam milletvekili başbakan bakan müdür memur
demokrasi özgürlük eşitlik kardeşlik hukuk kanun tüzük
toplum kültür gelenek görenek norm kural ahlak erdem
sanat estetik zevk güzellik yaratıcılık ilham tuval fırça enstrüman
antrenör kondisyon turnuva şampiyon madalya kupa forma
eğitim öğretim müfredat program sınav karne diploma
üniversite fakülte bölüm rektör dekan doçent asistan laboratuvar amfi
kütüphane kitaplık raf katalog özet makale dergi
internet tarayıcı sunucu istemci protokol güvenlik şifre parola kullanıcı
""".split()


def _is_infinitive(word: str) -> bool:
    return len(word) > 5 and word.endswith(INFINITIVE_SUFFIXES)


def _is_potential(word: str) -> bool:
    return any(word.endswith(s) for s in POTENTIAL_SUFFIXES)


def _derivational_depth(word: str) -> int:
    """How many stacked derivational suffixes the word appears to carry."""
    depth = 0
    stem = word
    changed = True
    while changed and len(stem) > 4:
        changed = False
        for suffix in DERIVATIONAL:
            if stem.endswith(suffix) and len(stem) - len(suffix) >= 3:
                stem = stem[: -len(suffix)]
                depth += 1
                changed = True
                break
    return depth


def build() -> tuple[dict[str, Entry], dict[str, int]]:
    entries: dict[str, Entry] = {}

    def put(folded: str, source: str) -> Entry:
        entry = entries.get(folded)
        if entry is None:
            entry = Entry(fold=folded, display=folded)
            entries[folded] = entry
        entry.sources.add(source)
        return entry

    sources = {
        "primary": RAW / "turkish" / "turkce-kelime-listesi.txt",
        "secondary": RAW / "turkish" / "mertemin-words.txt",
        "corpus": RAW / "turkish" / "corpus.txt",
    }
    for name, path in sources.items():
        for raw in read_lines(path):
            folded = normalize(raw, "tr")
            if folded is None:
                continue
            entry = put(folded, name)
            # The utkusen corpus is transliterated ASCII, so it may widen the
            # allowed list but must never introduce a target on its own.
            if name != "corpus":
                entry.is_target = True

    for raw in FALLBACK_TR:
        folded = normalize(raw, "tr")
        if folded is None:
            continue
        entry = put(folded, "curated")
        entry.is_target = True

    blocked = apply_target_policy(entries)

    def demote(entry: Entry, reason: str) -> None:
        entry.is_target = False
        blocked[reason] = blocked.get(reason, 0) + 1

    for entry in entries.values():
        if not entry.is_target or "curated" in entry.sources:
            continue
        if _is_infinitive(entry.fold):
            demote(entry, "infinitive")
        elif _is_potential(entry.fold):
            demote(entry, "potential_mood")

    # Demote ASCII twins of a properly spelled target: "aksam" when "akşam" is
    # also a target. Only pure-ASCII words can be twins, so the check is cheap.
    diacritic_targets = {
        e.fold for e in entries.values() if e.is_target and wc.deaccent(e.fold) != e.fold
    }
    ascii_shadows = {wc.deaccent(w) for w in diacritic_targets}
    for entry in entries.values():
        if not entry.is_target or "curated" in entry.sources:
            continue
        if wc.deaccent(entry.fold) == entry.fold and entry.fold in ascii_shadows:
            demote(entry, "ascii_twin")

    # Heuristic ordering, most-everyday first. Documented in the module
    # docstring: there is no Turkish frequency corpus among the sources.
    curated_order = {w: i for i, w in enumerate(FALLBACK_TR)}
    targets = [e for e in entries.values() if e.is_target]
    targets.sort(
        key=lambda e: (
            curated_order.get(e.fold, 10_000),
            0 if {"primary", "secondary"} <= e.sources else 1,
            _derivational_depth(e.fold),
            len(e.fold),
            e.fold,
        )
    )
    for rank, entry in enumerate(targets):
        entry.rank = rank

    return entries, blocked


def main() -> int:
    entries, blocked = build()
    report("tr", entries, blocked)
    return 0


if __name__ == "__main__":
    main()
