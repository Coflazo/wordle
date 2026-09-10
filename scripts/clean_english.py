"""English bank: dwyl/english-words for coverage, google-10k for target choice.

Targets are the intersection of the two, so answers are words a player has
plausibly met, while the allowed list stays wide enough that legitimate guesses
are not rejected.
"""

from __future__ import annotations

from scripts._common import (
    MAX_LEN,
    MIN_LEN,
    RAW,
    Entry,
    allowed_as_target,
    apply_target_policy,
    normalize,
    read_lines,
    read_ranked,
    report,
)

# The frequency list stops around 10k words, so the longer buckets thin out.
# Below this many targets at a given length, top up from the wide list.
MIN_TARGETS_PER_LENGTH = 400

FALLBACK_EN = """
about above actual adjust advance airport almost always amount animal answer
appear around arrive artist aspect attack author autumn average awesome
badge balance banner basket battle beauty become before behind believe below
better between beyond bottle bottom branch breath bridge bright broken budget
button camera cancel candle canvas carbon careful carpet castle casual center
change charge cheese chance choice circle client climate clever closet cloud
coffee column combine comfort common compare complex concert confirm connect
consider content contrast control convert copper corner cotton country couple
courage create credit crisis crowd crystal culture curious current custom
damage danger debate decade decide declare defend define degree deliver demand
depend deposit desert design desire detail develop device diamond differ
digital dinner direct discuss display distance divide doctor domain double
dragon dream driver during eager early earth easier eastern effect effort
either elbow electric elegant element eleven emerge empty enable energy engine
enough enter entire equal error escape estate ethics event every exact example
exceed except exchange excite expand expect expert explain export express
extend fabric factor family famous fashion father favor feature federal fellow
figure filter finger finish fiscal flavor flight floor flower follow forest
forget formal format fortune forward found fresh friend fruit function future
garden gather gender gentle gesture giant global golden govern grade grand
grant grass great green ground group growth guard guess guest guide habit
handle happen harbor health heart heavy height hidden holiday honest honor
horizon hotel human humble hunger husband ideal image impact import improve
income indeed index indoor infant inform inner input inside instant intend
invest invite island issue joint journey judge junior justice keeper kitchen
knight knowledge label labor ladder language large laser later laugh launch
layer leader league learn leave legal legend length lesson letter level liberty
library license light limit linear liquid listen little living local locate
logic lonely longer loyal luggage lumber lunch luxury machine magic magnet
major manage manner marble margin marine market master match material matter
mature meadow measure medal media medium member memory mental mentor merchant
merit message metal meter method middle might minor minute mirror mission
mixture mobile modern modest moment money monitor month moral morning mother
motion motor mount movie muscle museum music mutual narrow nation native
nature nearly needle neighbor neither nerve network neutral never night noble
normal north notice novel number object oblige observe obtain occur ocean
offer office often olive online open opera option orange orbit order organ
origin other outdoor output outside oxygen packet palace panel paper parade
parent partner passage patient pattern pause payment peace pencil people
pepper perfect period permit person phase phone photo phrase physical piano
picture piece pilot pioneer place planet plant plastic plate player please
plenty pocket poetry point police policy polish popular portion position
possible poster potato powder power praise precise prefer premium prepare
present preserve pretty prevent price pride primary prince print prison
private prize problem process produce profit program project promise proper
propose protect proud proven public publish purple purpose puzzle quality
quarter question quick quiet quote radio raise random range rapid rather
reach reader ready realize reason recall receive recent record reduce refer
reflect reform refuse regard region regular reject relate relax release
relief remain remark remember remind remote remove render repair repeat
replace reply report request require rescue research reserve resist resolve
resort resource respect respond restore result retain return reveal reverse
review reward rhythm rider right river robust rocket romance rotate rough
round router royal rubber rugby rural sacred saddle safety salad salary
sample sandwich satisfy sauce savings scale scatter scene schedule scheme
scholar school science scope score screen script search season second secret
section secure select senior sense sentence series serious service settle
seven severe shadow shape share sharp shelf shelter shield shift shine short
should shoulder shower signal silent silver similar simple single sister
situation sketch skill slice slight small smart smile smooth social socket
soften solar soldier solid solution someone sorry sound source south space
spare speak special speech speed spend sphere spirit splash spoke sport
spread spring square stable staff stage stand start state station status
steady steam steel stick still stock stone store storm story straight strange
stream street stress strike string strong struggle student studio study
stupid style subject submit subtle succeed sudden suffer sugar suggest
summer summit sunny super supply support suppose surface surprise survey
survive sweet switch symbol system table talent target teach teacher
technique telephone television temper temple tender tennis tension terminal
terrible territory theatre theory therapy thermal thick thing think third
thirty though thought thread threat throat through thumb thunder ticket
tight timber timer tissue title today together toilet token tomato tomorrow
tongue tonight total touch tough tourist toward tower track trade traffic
train transfer travel treat trend trial tribe trick trouble truck truly
trust truth tunnel turkey twelve twenty typical unable uncle under
understand uniform union unique unite universe unless until update upgrade
upper upset urban urgent usage useful usual valley value vapor variety
various vector vendor venture verbal verify version vessel veteran victim
victory video village violin virtual virtue vision visit visual vital voice
volume voyage waiting wallet wander warmth warning washing watch water weapon
weather weekend weight welcome welfare western whether which while whisper
white whole widely willing window winter wisdom within without witness woman
wonder wooden worker world worry worth would wound write writer wrong yellow
yesterday yield young youth
""".split()


def build() -> tuple[dict[str, Entry], dict[str, int]]:
    entries: dict[str, Entry] = {}

    def put(folded: str, source: str) -> Entry:
        entry = entries.get(folded)
        if entry is None:
            entry = Entry(fold=folded, display=folded)
            entries[folded] = entry
        entry.sources.add(source)
        return entry

    # Wide coverage list -> the allowed pool.
    for raw in read_lines(RAW / "english" / "words_alpha.txt"):
        folded = normalize(raw, "en")
        if folded is not None:
            put(folded, "words_alpha")

    # Frequency list -> targets, carrying rank for the tier split.
    ranked = read_ranked(RAW / "english" / "google-10000-english-usa.txt")
    for raw, rank in ranked:
        folded = normalize(raw, "en")
        if folded is None:
            continue
        entry = put(folded, "google10k")
        entry.is_target = True
        entry.rank = rank if entry.rank is None else min(entry.rank, rank)

    # Curated everyday words, so the game is playable even without downloads.
    for offset, raw in enumerate(FALLBACK_EN):
        folded = normalize(raw, "en")
        if folded is None:
            continue
        entry = put(folded, "curated")
        entry.is_target = True
        if entry.rank is None:
            entry.rank = 2000 + offset

    blocked = apply_target_policy(entries)

    # Longer words fall off the end of a 10k frequency list. Top those buckets
    # up by word length, shortest first, which correlates far better with
    # familiarity than the alphabetical order the previous build used (it
    # produced targets like "aahed" and "aalii").
    by_len: dict[int, int] = {}
    for entry in entries.values():
        if entry.is_target:
            by_len[len(entry.fold)] = by_len.get(len(entry.fold), 0) + 1

    for length in range(MIN_LEN, MAX_LEN + 1):
        have = by_len.get(length, 0)
        if have >= MIN_TARGETS_PER_LENGTH:
            continue
        pool = sorted(
            (e for e in entries.values() if not e.is_target and len(e.fold) == length),
            key=lambda e: e.fold,
        )
        for entry in pool[: MIN_TARGETS_PER_LENGTH - have]:
            if not allowed_as_target(entry.fold):
                continue
            entry.is_target = True
            entry.rank = 50_000  # no frequency evidence; lands in the rare tier

    return entries, blocked


def main() -> int:
    entries, blocked = build()
    report("en", entries, blocked)
    return 0


if __name__ == "__main__":
    main()
