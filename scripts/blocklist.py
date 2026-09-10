"""Content policy for the word banks.

Two tiers, because they need different treatment:

`SLURS` — hate speech and ethnic/sexual slurs. Removed from targets *and* from
the allowed list, so the word is not playable in any form.

`NOT_AS_ANSWER` — vulgar, sexual, violent, or politically charged words that are
legitimate dictionary entries. Removed from targets only. A player who types one
still gets a valid guess; the game just never picks it as the answer.

The distinction matters: stripping every rude word from the allowed list would
reject real words a player typed on purpose, which reads as a broken dictionary.
Serving one as the answer is a different thing entirely — the game chose it.

Everything here is compared against the folded (locale-lowercased) form, so
"Nigger", "NIGGER" and "nigger" are all caught by one entry.
"""

from __future__ import annotations

# Slurs and hate terms. Removed everywhere, in every language, regardless of
# which bank the string turned up in — these lists cross-contaminate through the
# subtitle and web-scraped sources.
SLURS: frozenset[str] = frozenset(
    """
    nigger niggers nigga niggas negro negroes coon coons
    faggot faggots fagot fagots dyke dykes tranny trannies shemale
    chink chinks gook gooks spic spics wetback wetbacks
    kike kikes yid yids
    raghead ragheads towelhead sandnigger
    retard retards retarded spastic mongoloid
    paki pakis wop wops dago dagos kraut krauts
    gypsy gypsies zigeuner
    untermensch judensau negerin neger
    """.split()
)

# Legitimate words that should never be the answer.
NOT_AS_ANSWER: frozenset[str] = frozenset(
    """
    bitch bitches bastard bastards whore whores slut sluts
    pussy pussies cunt cunts dick dicks cock cocks prick pricks
    penis penises vagina vaginas testicle testicles scrotum
    semen sperm ejaculate orgasm masturbate masturbation
    fucker fucking fucked shitty shithead asshole assholes
    rape rapist rapists incest bestiality pedophile paedophile
    suicide suicidal genocide holocaust lynching
    hitler stalin mussolini nazism nazis fascist fascists
    heroin cocaine methamphetamine

    scheisse scheiße scheissen ficken fickt gefickt arschloch
    fotze fotzen wichser wichsen schlampe schlampen nutte nutten
    hurensohn huren hure titten schwanz muschi arsch
    schwuchtel spasti behindert selbstmord voelkermord völkermord
    vergewaltigung vergewaltigen zuhaelter zuhälter

    orospu orospular pezevenk piclik piçlik kahpe kahpeler
    gavat sikmek sikis sikiş amcik amcık yarrak tasak taşak
    gotveren götveren ibne ibneler pust puşt oruspu
    tecavuz tecavüz intihar soykirim soykırım
    """.split()
)

# Brands, places, and given names that survive a lowercase dictionary filter.
# These are dictionary-legal strings but make for bad Wordle answers: a player
# cannot reason about them, they are not in the language's vocabulary, and they
# are the single most common complaint about scraped word banks.
PROPER_NOUNS: frozenset[str] = frozenset(
    """
    aaron abbey abbie abbott aberdeen abigail abilene abner abraham adam adams
    adobe africa alabama alaska albert alberta alexander alfred algeria alice
    allan amanda amazon america american andrea andrew andy angela anna anne
    anthony antonio apple arabia argentina arizona arkansas arthur asia athens
    atlanta atlantic auburn august augusta austin australia austria
    baker baltimore bangkok baptist barbara barcelona barnes barry basel
    beijing belfast belgium bengal benjamin berlin bernard beverly bolivia
    bombay boston boulder bradford bradley brasil brazil brendan brian bristol
    britain british brooklyn bruce brussels bryan bucharest budapest buffalo
    calgary california cambridge cameron canada canadian carlos carmen carol
    carolina carter catherine celtic charles charlie charlotte chelsea chester
    chicago chile china chinese chris christian christina christopher cincinnati
    claire clark claudia claudio cleveland clifford clinton colombia colorado
    columbia columbus congo connecticut cooper copenhagen cornell cornwall
    cuba curtis cyprus czech
    dakota dallas daniel danish darwin david dawson delaware delhi denmark
    dennis denver derek detroit diana diego dominic donald donna dorothy douglas
    dresden dublin duncan durham dutch dylan
    ecuador edinburgh edward egypt eileen eleanor elizabeth ellen emily emma
    england english eric estonia ethan ethiopia eugene europe european evans
    everest
    fabian ferguson finland fisher fletcher florence florida ford foster france
    frances francis francisco frank franklin fraser french
    gabriel gambia gannicus garcia gareth gemma geneva george georgia gerald
    german germany gilbert giovanni giuseppe glasgow gloria gordon graham grant
    greece greek greene gregory
    hamburg hamilton hannah hanover harold harper harris harrison harvard harvey
    hawaii hayden heather hebrew hector helen henderson henry herbert hindu
    holland hollywood honda hongkong horace houston howard hudson hughes hungary
    hunter huntington
    iceland idaho illinois india indian indiana indonesia iowa iran iraq ireland
    irish isaac isabel islam islamic israel istanbul italian italy
    jackson jacob jamaica james janet japan japanese jasmine jason jefferson
    jeffrey jenkins jennifer jeremy jerome jersey jerusalem jessica jesus jewish
    johnson jonathan jordan joseph joshua juliet julius justin
    kansas karachi katherine kathleen keith kelly kennedy kenneth kentucky kenya
    kevin kimberly kingston kirsten korea korean kuwait
    lambert lancaster lawrence lebanon leeds leonard leslie liberia libya lincoln
    lisbon lithuania liverpool logan london louis louise louisiana lucas lucia
    lucy luther luxembourg lyons
    madison madrid maine malawi malaysia malcolm manchester manila marcus
    margaret maria marilyn marion marshall martin maryland mason massachusetts
    matthew maurice maxwell melbourne melissa memphis mexican mexico miami
    michael michelle michigan milan miller milwaukee minnesota mississippi
    missouri mitchell mohammed monaco mongolia monica montana montreal morgan
    morocco morris moscow muhammad mumbai munich murphy murray muslim myanmar
    nairobi namibia nancy naples nathan nebraska nelson nepal netherlands nevada
    newark newcastle newman newton nicholas nichols nicole nigeria nissan norman
    norway norwegian nottingham
    oakland ohio oklahoma oliver olivia omaha ontario oregon orlando osaka
    ottawa oxford
    pacific pakistan palmer panama paris parker patricia patrick patterson paula
    pearson pennsylvania perkins persian perth peru peters peterson philadelphia
    philip philippines phoenix pittsburgh poland polish porter portland portugal
    potter powell prague preston pretoria princeton prussia
    quebec quinn
    rachel raleigh ralph ramirez randall raymond reagan rebecca reynolds
    richard richardson richmond riley roberts robertson robinson rochester
    rodriguez roger roland roman romania rome ronald roosevelt rosemary russell
    russia russian rwanda ryan
    sacramento salvador samantha samuel sandra santiago sarah saudi savannah
    schmidt scotland scott scottish seattle senegal seoul serbia sergio seville
    shanghai shannon sharon sheffield shelby sheridan sherman siberia sicily
    sierra simmons simpson singapore slovakia slovenia smith solomon somalia
    sophia spain spanish spencer stanford stanley stephanie stephen sterling
    steven stewart stockholm stuart sudan sullivan sussex sweden swedish swiss
    switzerland sydney syria
    taiwan tanzania tasmania taylor tehran tennessee texas thailand theodore
    thomas thompson thornton tibet timothy tokyo toledo tommy toronto toyota
    trinidad tucker tunisia turkey turkish turner
    uganda ukraine ulster uruguay utah
    valencia vancouver vaughan venezuela venice vermont vernon veronica victor
    victoria vienna vietnam viking vincent virginia
    wagner wales walker wallace walter warner warren washington watson wayne
    webster wellington wesley wheeler whitney wilkinson william williams willis
    wilson winchester windsor winnipeg wisconsin wolfgang wright wyoming
    yahoo yale yemen yorkshire young
    zambia zealand zimbabwe zurich

    almanya amerika anadolu ankara antalya avrupa aziziye balkanlar bursa
    cumhuriyet diyarbakir diyarbakır erzurum eskisehir eskişehir fransa
    gaziantep hollanda ingiltere isvicre isviçre italya izmir kayseri konya
    malatya marmara mersin rusya samsun trabzon turkiye türkiye yunanistan

    baden bayern berliner deutschland frankfurt hessen koeln köln muenchen
    münchen oesterreich österreich preussen preußen sachsen schweiz stuttgart
    thueringen thüringen
    """.split()
)


def block_reason(folded: str) -> str | None:
    """Return 'slur', 'not_as_answer', 'proper_noun', or None."""
    if folded in SLURS:
        return "slur"
    if folded in NOT_AS_ANSWER:
        return "not_as_answer"
    if folded in PROPER_NOUNS:
        return "proper_noun"
    return None


def allowed_in_bank(folded: str) -> bool:
    """False only for words that must not exist in the game at all."""
    return folded not in SLURS


def allowed_as_target(folded: str) -> bool:
    """False for anything that must never be served as the answer."""
    return block_reason(folded) is None
