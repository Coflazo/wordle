/* Interface translation.
 *
 * Selecting Turkish previously changed the word bank and the keyboard layout
 * and nothing else — the player got Turkish words wrapped in an English
 * interface, and <html lang> stayed "en" so a screen reader read Turkish
 * definitions with an English voice.
 *
 * Keys are dotted paths. `t('game.attemptsLeft')` returns the string for the
 * active locale, falling back to English if a key is missing so a gap shows up
 * as English text rather than a blank or a raw key.
 */

const EN = {
  app: {
    name: 'Oflaz Wordle',
    tagline: 'Guess words from 5 to 10 letters in English, Turkish, or German — then learn what they mean.',
  },
  nav: {
    profile: 'Profile',
    newGame: 'New game',
    viewProfile: 'View profile',
    backToStart: 'Back to start',
    skipToGame: 'Skip to the game board',
    skipToContent: 'Skip to content',
  },
  setup: {
    language: 'Language',
    difficulty: 'Difficulty',
    wordLength: 'Word length',
    mix: 'Mix',
    mixHint: 'A random length each game',
    start: 'Start game',
    starting: 'Starting…',
    customize: 'Customize your character',
    character: 'Character',
    defaultName: 'Oflaz',
    defaultDesc: 'The house character. Calm, green badge.',
    customName: 'Make your own',
    customDesc: 'Pick a name, hair, accessory and colours.',
    name: 'Name',
    namePlaceholder: 'e.g. Çağan',
    hair: 'Hair',
    accessory: 'Accessory',
    shirt: 'Shirt colour',
    aura: 'Aura colour',
    preview: 'Preview',
    theme: 'Theme',
  },
  difficulty: {
    chill: 'Chill',
    chillHint: 'Everyday words, one extra guess',
    classic: 'Classic',
    classicHint: 'Common and mid-frequency words',
    scholar: 'Scholar',
    scholarHint: 'Rarer words, no extra guess',
  },
  theme: {
    system: 'Match system',
    dark: 'Dark',
    light: 'Light',
    contrast: 'High contrast',
    colorblind: 'Colourblind friendly',
  },
  hair: {
    short_black: 'Short black', short_brown: 'Short brown', long_blond: 'Long blond',
    curly_red: 'Curly red', buzz: 'Buzz cut', none: 'None',
  },
  accessory: {
    badge: 'Badge', glasses: 'Glasses', crown: 'Crown',
    headphones: 'Headphones', scarf: 'Scarf', calculator: 'Calculator', book: 'Book',
  },
  game: {
    length: 'Length',
    attemptsLeft: 'Guesses left',
    difficultyLabel: 'Difficulty',
    meaning: 'Meaning',
    meaningOfGuess: 'Meaning of your guess',
    meaningOfAnswer: 'Meaning of the answer',
    openMeaning: 'Show meaning',
    hint: 'Hint',
    getHint: 'Get a hint',
    hintsUsed: 'Hints used',
    giveUp: 'Give up',
    enter: 'Enter',
    backspace: 'Backspace',
    loading: 'Loading…',
    boardLabel: 'Guess grid, {rows} rows of {cols} letters',
    rowLabel: 'Guess {row}',
    emptyRow: 'Row {row}, empty',
    tileEmpty: 'empty',
    typedRow: 'Row {row}: {letters}',
    won: 'Solved it.',
    lost: 'Out of guesses.',
    answerWas: 'The word was',
    seeMeaning: 'See what it means',
    playAgain: 'Play again',
    guessResult: 'Guess {row}, {word}: {detail}',
    markCorrect: '{letter} correct',
    markPresent: '{letter} in the word, wrong place',
    markAbsent: '{letter} not in the word',
    meaningIntro: 'Play a guess, then open the meaning panel to see what the word means.',
    noDefinition: 'No definition found for this word.',
    compounds: 'Compound forms',
    proverbs: 'Proverbs and idioms',
    similar: 'Similar words',
    synonyms: 'Synonyms',
    source: 'Source',
    hintIntro: 'Best next guesses by how much they narrow the answer.',
    hintCandidates: { one: 'Only {count} word still fits', other: '{count} words still fit' },
    hintSolved: 'One word is left — that is the answer.',
    hintBits: '{bits} bits',
    hintCouldBeAnswer: 'could be the answer',
  },
  profile: {
    title: 'Profile',
    since: 'Playing since {date}',
    prefers: 'Prefers {language}',
    all: 'All',
    gamesPlayed: 'Games played',
    winRate: 'Win rate',
    currentStreak: 'Current streak',
    currentStreakSub: 'wins in a row',
    bestStreak: 'Best streak',
    avgAttempts: 'Average guesses',
    avgAttemptsSub: 'per win',
    wordsMastered: 'Words mastered',
    wordsMasteredSub: 'solved repeatedly, meaning read',
    fastestSolve: 'Fastest solve',
    longestWord: 'Longest word solved',
    distribution: 'Guesses needed, by word length',
    languageSplit: 'By language',
    vocabulary: 'Vocabulary',
    mastered: 'Mastered',
    known: 'Known',
    struggling: 'Still tricky',
    recentGames: 'Recent games',
    experiments: 'Experiments',
    experimentsIntro: 'Variations being tried out on this device. The bar shows the 95% confidence interval — a wide bar means too few games to tell yet.',
    noGames: 'No finished games yet. Play one and this fills in.',
    noEntries: 'Nothing here yet.',
    colWord: 'Word',
    colMastery: 'Mastery',
    colFails: 'Misses',
    colLanguage: 'Language',
    games: { one: '{count} game', other: '{count} games' },
    deltaUp: 'up {value} on the previous 7',
    deltaDown: 'down {value} on the previous 7',
    deltaFlat: 'level with the previous 7',
    deltaUnknown: 'needs 14 games to compare',
    resigned: 'gave up',
    hintedGame: 'used {count} hints',
  },
  errors: {
    generic: 'Something went wrong. Please try again.',
    offline: 'Cannot reach the game server. Is it still running?',
    timeout: 'The server took too long to answer.',
    not_a_word: '“{word}” is not in the {language} word list.',
    not_a_word_suggest: '“{word}” is not in the list. Did you mean {suggestions}?',
    wrong_length: 'Needs {expected} letters, you typed {got}.',
    game_not_found: 'That game has expired. Starting a new one.',
    game_finished: 'That game is already over.',
    profile_not_found: 'That profile no longer exists.',
    no_words_for_length: 'No {length}-letter words available for this language.',
    unsupported_language: 'That language is not supported.',
    bank_unavailable: 'Word banks are missing. Run the build step and restart.',
    solver_unavailable: 'Hints are unavailable right now.',
    rate_limited: 'Slow down a moment.',
    internal_error: 'The server hit an unexpected error.',
    startFailed: 'Could not start the game.',
    meaningFailed: 'Could not load the meaning.',
    dashboardFailed: 'Could not load your stats.',
    retry: 'Try again',
  },
  languages: { en: 'English', tr: 'Turkish', de: 'German' },
};

const TR = {
  app: {
    name: 'Oflaz Wordle',
    tagline: 'İngilizce, Türkçe veya Almanca 5–10 harfli kelimeleri tahmin edin, sonra anlamlarını öğrenin.',
  },
  nav: {
    profile: 'Profil',
    newGame: 'Yeni oyun',
    viewProfile: 'Profili gör',
    backToStart: 'Başa dön',
    skipToGame: 'Oyun tahtasına geç',
    skipToContent: 'İçeriğe geç',
  },
  setup: {
    language: 'Dil',
    difficulty: 'Zorluk',
    wordLength: 'Kelime uzunluğu',
    mix: 'Karışık',
    mixHint: 'Her oyunda rastgele uzunluk',
    start: 'Oyunu başlat',
    starting: 'Başlatılıyor…',
    customize: 'Karakterini özelleştir',
    character: 'Karakter',
    defaultName: 'Oflaz',
    defaultDesc: 'Evin karakteri. Sakin, yeşil rozetli.',
    customName: 'Kendin yap',
    customDesc: 'Ad, saç, aksesuar ve renk seç.',
    name: 'Ad',
    namePlaceholder: 'örn. Çağan',
    hair: 'Saç',
    accessory: 'Aksesuar',
    shirt: 'Tişört rengi',
    aura: 'Aura rengi',
    preview: 'Önizleme',
    theme: 'Tema',
  },
  difficulty: {
    chill: 'Rahat',
    chillHint: 'Günlük kelimeler, bir hak fazla',
    classic: 'Klasik',
    classicHint: 'Yaygın ve orta sıklıkta kelimeler',
    scholar: 'Uzman',
    scholarHint: 'Daha nadir kelimeler, ek hak yok',
  },
  theme: {
    system: 'Sistemle aynı',
    dark: 'Koyu',
    light: 'Açık',
    contrast: 'Yüksek kontrast',
    colorblind: 'Renk körlüğüne uygun',
  },
  hair: {
    short_black: 'Kısa siyah', short_brown: 'Kısa kahverengi', long_blond: 'Uzun sarı',
    curly_red: 'Kıvırcık kızıl', buzz: 'Asker tıraşı', none: 'Yok',
  },
  accessory: {
    badge: 'Rozet', glasses: 'Gözlük', crown: 'Taç',
    headphones: 'Kulaklık', scarf: 'Atkı', calculator: 'Hesap makinesi', book: 'Kitap',
  },
  game: {
    length: 'Uzunluk',
    attemptsLeft: 'Kalan hak',
    difficultyLabel: 'Zorluk',
    meaning: 'Anlam',
    meaningOfGuess: 'Tahmininin anlamı',
    meaningOfAnswer: 'Cevabın anlamı',
    openMeaning: 'Anlamı göster',
    hint: 'İpucu',
    getHint: 'İpucu al',
    hintsUsed: 'Kullanılan ipucu',
    giveUp: 'Pes et',
    enter: 'Gir',
    backspace: 'Geri sil',
    loading: 'Yükleniyor…',
    boardLabel: 'Tahmin tablosu, {cols} harflik {rows} satır',
    rowLabel: '{row}. tahmin',
    emptyRow: '{row}. satır, boş',
    tileEmpty: 'boş',
    typedRow: '{row}. satır: {letters}',
    won: 'Bildin.',
    lost: 'Hakkın bitti.',
    answerWas: 'Kelime şuydu',
    seeMeaning: 'Anlamına bak',
    playAgain: 'Tekrar oyna',
    guessResult: '{row}. tahmin, {word}: {detail}',
    markCorrect: '{letter} doğru',
    markPresent: '{letter} kelimede var, yeri yanlış',
    markAbsent: '{letter} kelimede yok',
    meaningIntro: 'Bir tahmin yap, sonra anlam panelini açarak kelimenin ne demek olduğunu gör.',
    noDefinition: 'Bu kelime için tanım bulunamadı.',
    compounds: 'Birleşik biçimler',
    proverbs: 'Atasözleri ve deyimler',
    similar: 'Benzer kelimeler',
    synonyms: 'Eş anlamlılar',
    source: 'Kaynak',
    hintIntro: 'Cevabı en çok daraltan tahminler.',
    hintCandidates: { one: 'Sadece {count} kelime uyuyor', other: '{count} kelime hâlâ uyuyor' },
    hintSolved: 'Tek kelime kaldı, cevap o.',
    hintBits: '{bits} bit',
    hintCouldBeAnswer: 'cevap olabilir',
  },
  profile: {
    title: 'Profil',
    since: '{date} tarihinden beri oynuyor',
    prefers: 'Tercihi: {language}',
    all: 'Hepsi',
    gamesPlayed: 'Oynanan oyun',
    winRate: 'Kazanma oranı',
    currentStreak: 'Güncel seri',
    currentStreakSub: 'üst üste galibiyet',
    bestStreak: 'En iyi seri',
    avgAttempts: 'Ortalama tahmin',
    avgAttemptsSub: 'galibiyet başına',
    wordsMastered: 'Pekişen kelime',
    wordsMasteredSub: 'defalarca bilindi, anlamı okundu',
    fastestSolve: 'En hızlı çözüm',
    longestWord: 'En uzun bilinen kelime',
    distribution: 'Kelime uzunluğuna göre gereken tahmin',
    languageSplit: 'Dile göre',
    vocabulary: 'Kelime dağarcığı',
    mastered: 'Pekişen',
    known: 'Bilinen',
    struggling: 'Hâlâ zor',
    recentGames: 'Son oyunlar',
    experiments: 'Denemeler',
    experimentsIntro: 'Bu cihazda denenen varyasyonlar. Çubuk %95 güven aralığını gösterir; geniş çubuk henüz karar vermek için yeterli oyun olmadığı anlamına gelir.',
    noGames: 'Henüz biten oyun yok. Bir tane oyna, burası dolsun.',
    noEntries: 'Burada henüz bir şey yok.',
    colWord: 'Kelime',
    colMastery: 'Pekişme',
    colFails: 'Kaçırma',
    colLanguage: 'Dil',
    games: { one: '{count} oyun', other: '{count} oyun' },
    deltaUp: 'önceki 7 oyuna göre {value} arttı',
    deltaDown: 'önceki 7 oyuna göre {value} azaldı',
    deltaFlat: 'önceki 7 oyunla aynı',
    deltaUnknown: 'karşılaştırma için 14 oyun gerekli',
    resigned: 'pes edildi',
    hintedGame: '{count} ipucu kullanıldı',
  },
  errors: {
    generic: 'Bir şeyler ters gitti. Lütfen tekrar deneyin.',
    offline: 'Oyun sunucusuna ulaşılamıyor. Hâlâ çalışıyor mu?',
    timeout: 'Sunucu çok geç yanıt verdi.',
    not_a_word: '“{word}” {language} kelime listesinde yok.',
    not_a_word_suggest: '“{word}” listede yok. {suggestions} demek mi istediniz?',
    wrong_length: '{expected} harf gerekiyor, siz {got} harf yazdınız.',
    game_not_found: 'Bu oyunun süresi doldu. Yenisi başlatılıyor.',
    game_finished: 'Bu oyun zaten bitti.',
    profile_not_found: 'Bu profil artık yok.',
    no_words_for_length: 'Bu dil için {length} harfli kelime yok.',
    unsupported_language: 'Bu dil desteklenmiyor.',
    bank_unavailable: 'Kelime bankaları eksik. Derleme adımını çalıştırıp yeniden başlatın.',
    solver_unavailable: 'İpuçları şu anda kullanılamıyor.',
    rate_limited: 'Biraz yavaşlayın.',
    internal_error: 'Sunucuda beklenmedik bir hata oluştu.',
    startFailed: 'Oyun başlatılamadı.',
    meaningFailed: 'Anlam yüklenemedi.',
    dashboardFailed: 'İstatistikleriniz yüklenemedi.',
    retry: 'Tekrar dene',
  },
  languages: { en: 'İngilizce', tr: 'Türkçe', de: 'Almanca' },
};

const DE = {
  app: {
    name: 'Oflaz Wordle',
    tagline: 'Errate Wörter mit 5 bis 10 Buchstaben auf Englisch, Türkisch oder Deutsch — und lerne, was sie bedeuten.',
  },
  nav: {
    profile: 'Profil',
    newGame: 'Neues Spiel',
    viewProfile: 'Profil ansehen',
    backToStart: 'Zurück zum Start',
    skipToGame: 'Zum Spielfeld springen',
    skipToContent: 'Zum Inhalt springen',
  },
  setup: {
    language: 'Sprache',
    difficulty: 'Schwierigkeit',
    wordLength: 'Wortlänge',
    mix: 'Gemischt',
    mixHint: 'Jedes Spiel eine zufällige Länge',
    start: 'Spiel starten',
    starting: 'Wird gestartet…',
    customize: 'Figur anpassen',
    character: 'Figur',
    defaultName: 'Oflaz',
    defaultDesc: 'Die Hausfigur. Ruhig, grünes Abzeichen.',
    customName: 'Selbst gestalten',
    customDesc: 'Name, Haare, Accessoire und Farben wählen.',
    name: 'Name',
    namePlaceholder: 'z. B. Çağan',
    hair: 'Haare',
    accessory: 'Accessoire',
    shirt: 'Shirtfarbe',
    aura: 'Aurafarbe',
    preview: 'Vorschau',
    theme: 'Design',
  },
  difficulty: {
    chill: 'Entspannt',
    chillHint: 'Alltagswörter, ein Versuch mehr',
    classic: 'Klassisch',
    classicHint: 'Häufige und mittelhäufige Wörter',
    scholar: 'Kenner',
    scholarHint: 'Seltenere Wörter, kein Extraversuch',
  },
  theme: {
    system: 'Wie das System',
    dark: 'Dunkel',
    light: 'Hell',
    contrast: 'Hoher Kontrast',
    colorblind: 'Farbenblind-freundlich',
  },
  hair: {
    short_black: 'Kurz schwarz', short_brown: 'Kurz braun', long_blond: 'Lang blond',
    curly_red: 'Lockig rot', buzz: 'Kurzhaarschnitt', none: 'Keine',
  },
  accessory: {
    badge: 'Abzeichen', glasses: 'Brille', crown: 'Krone',
    headphones: 'Kopfhörer', scarf: 'Schal', calculator: 'Taschenrechner', book: 'Buch',
  },
  game: {
    length: 'Länge',
    attemptsLeft: 'Versuche übrig',
    difficultyLabel: 'Schwierigkeit',
    meaning: 'Bedeutung',
    meaningOfGuess: 'Bedeutung deines Versuchs',
    meaningOfAnswer: 'Bedeutung der Lösung',
    openMeaning: 'Bedeutung zeigen',
    hint: 'Tipp',
    getHint: 'Tipp holen',
    hintsUsed: 'Tipps benutzt',
    giveUp: 'Aufgeben',
    enter: 'Eingabe',
    backspace: 'Löschen',
    loading: 'Wird geladen…',
    boardLabel: 'Rateraster, {rows} Reihen mit {cols} Buchstaben',
    rowLabel: 'Versuch {row}',
    emptyRow: 'Reihe {row}, leer',
    tileEmpty: 'leer',
    typedRow: 'Reihe {row}: {letters}',
    won: 'Gelöst.',
    lost: 'Keine Versuche mehr.',
    answerWas: 'Das Wort war',
    seeMeaning: 'Bedeutung ansehen',
    playAgain: 'Nochmal spielen',
    guessResult: 'Versuch {row}, {word}: {detail}',
    markCorrect: '{letter} richtig',
    markPresent: '{letter} im Wort, falsche Stelle',
    markAbsent: '{letter} nicht im Wort',
    meaningIntro: 'Rate ein Wort und öffne dann die Bedeutungsleiste.',
    noDefinition: 'Für dieses Wort wurde keine Bedeutung gefunden.',
    compounds: 'Zusammensetzungen',
    proverbs: 'Redewendungen',
    similar: 'Ähnliche Wörter',
    synonyms: 'Synonyme',
    source: 'Quelle',
    hintIntro: 'Die Versuche, die die Lösung am stärksten eingrenzen.',
    hintCandidates: { one: 'Nur noch {count} Wort passt', other: '{count} Wörter passen noch' },
    hintSolved: 'Nur ein Wort bleibt übrig — das ist die Lösung.',
    hintBits: '{bits} Bit',
    hintCouldBeAnswer: 'könnte die Lösung sein',
  },
  profile: {
    title: 'Profil',
    since: 'Spielt seit {date}',
    prefers: 'Bevorzugt {language}',
    all: 'Alle',
    gamesPlayed: 'Gespielte Spiele',
    winRate: 'Gewinnquote',
    currentStreak: 'Aktuelle Serie',
    currentStreakSub: 'Siege in Folge',
    bestStreak: 'Beste Serie',
    avgAttempts: 'Versuche im Schnitt',
    avgAttemptsSub: 'pro Sieg',
    wordsMastered: 'Beherrschte Wörter',
    wordsMasteredSub: 'mehrfach gelöst, Bedeutung gelesen',
    fastestSolve: 'Schnellste Lösung',
    longestWord: 'Längstes gelöstes Wort',
    distribution: 'Benötigte Versuche nach Wortlänge',
    languageSplit: 'Nach Sprache',
    vocabulary: 'Wortschatz',
    mastered: 'Beherrscht',
    known: 'Bekannt',
    struggling: 'Noch schwierig',
    recentGames: 'Letzte Spiele',
    experiments: 'Tests',
    experimentsIntro: 'Varianten, die auf diesem Gerät ausprobiert werden. Der Balken zeigt das 95%-Konfidenzintervall — ein breiter Balken heißt, es sind noch zu wenige Spiele.',
    noGames: 'Noch keine beendeten Spiele. Spiel eins, dann füllt sich das hier.',
    noEntries: 'Hier ist noch nichts.',
    colWord: 'Wort',
    colMastery: 'Können',
    colFails: 'Fehlversuche',
    colLanguage: 'Sprache',
    games: { one: '{count} Spiel', other: '{count} Spiele' },
    deltaUp: '{value} besser als die vorigen 7',
    deltaDown: '{value} schlechter als die vorigen 7',
    deltaFlat: 'gleich wie die vorigen 7',
    deltaUnknown: 'braucht 14 Spiele zum Vergleich',
    resigned: 'aufgegeben',
    hintedGame: '{count} Tipps benutzt',
  },
  errors: {
    generic: 'Etwas ist schiefgelaufen. Bitte nochmal versuchen.',
    offline: 'Der Spielserver ist nicht erreichbar. Läuft er noch?',
    timeout: 'Der Server hat zu lange gebraucht.',
    not_a_word: '„{word}“ steht nicht in der {language}-Wortliste.',
    not_a_word_suggest: '„{word}“ steht nicht in der Liste. Meintest du {suggestions}?',
    wrong_length: 'Braucht {expected} Buchstaben, du hast {got} getippt.',
    game_not_found: 'Dieses Spiel ist abgelaufen. Ein neues wird gestartet.',
    game_finished: 'Dieses Spiel ist schon vorbei.',
    profile_not_found: 'Dieses Profil gibt es nicht mehr.',
    no_words_for_length: 'Keine Wörter mit {length} Buchstaben für diese Sprache.',
    unsupported_language: 'Diese Sprache wird nicht unterstützt.',
    bank_unavailable: 'Die Wortbänke fehlen. Bitte den Build ausführen und neu starten.',
    solver_unavailable: 'Tipps sind gerade nicht verfügbar.',
    rate_limited: 'Einen Moment langsamer.',
    internal_error: 'Auf dem Server ist ein unerwarteter Fehler aufgetreten.',
    startFailed: 'Das Spiel konnte nicht gestartet werden.',
    meaningFailed: 'Die Bedeutung konnte nicht geladen werden.',
    dashboardFailed: 'Deine Statistik konnte nicht geladen werden.',
    retry: 'Nochmal versuchen',
  },
  languages: { en: 'Englisch', tr: 'Türkisch', de: 'Deutsch' },
};

const CATALOG = { en: EN, tr: TR, de: DE };
const STORAGE_KEY = 'oflaz-wordle:locale';

let current = 'en';

function lookup(catalog, path) {
  return path.split('.').reduce((node, key) => (node == null ? undefined : node[key]), catalog);
}

/** Translate a key, interpolating {placeholders}. */
export function t(path, params) {
  let value = lookup(CATALOG[current], path);
  if (value === undefined) value = lookup(EN, path);
  if (value === undefined) return path;
  if (!params) return value;
  return value.replace(/\{(\w+)\}/g, (match, key) =>
    Object.prototype.hasOwnProperty.call(params, key) ? String(params[key]) : match
  );
}

export function getLocale() {
  return current;
}

export function setLocale(locale) {
  current = CATALOG[locale] ? locale : 'en';
  try {
    localStorage.setItem(STORAGE_KEY, current);
  } catch {
    /* private browsing — the locale simply will not persist */
  }
  document.documentElement.lang = current;
  applyTranslations();
  document.dispatchEvent(new CustomEvent('localechange', { detail: { locale: current } }));
  return current;
}

/** Restore a stored locale, else follow the browser, else English. */
export function initLocale(preferred) {
  let locale = preferred;
  if (!locale) {
    try {
      locale = localStorage.getItem(STORAGE_KEY);
    } catch {
      locale = null;
    }
  }
  if (!locale) {
    const browser = (navigator.languages || [navigator.language || 'en'])
      .map((tag) => String(tag).slice(0, 2).toLowerCase())
      .find((tag) => CATALOG[tag]);
    locale = browser || 'en';
  }
  return setLocale(locale);
}

/**
 * Fill every element carrying a data-i18n attribute.
 *   data-i18n            -> textContent
 *   data-i18n-aria-label -> aria-label
 *   data-i18n-title      -> title
 *   data-i18n-placeholder-> placeholder
 * Values are written with textContent / setAttribute, never innerHTML.
 */
export function applyTranslations(root = document) {
  root.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  const attrs = [
    ['data-i18n-aria-label', 'aria-label'],
    ['data-i18n-title', 'title'],
    ['data-i18n-placeholder', 'placeholder'],
  ];
  for (const [dataAttr, target] of attrs) {
    root.querySelectorAll(`[${dataAttr}]`).forEach((el) => {
      el.setAttribute(target, t(el.getAttribute(dataAttr)));
    });
  }
}

/** Locale-correct date, using the interface language rather than the OS. */
export function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat(current, { dateStyle: 'medium' }).format(date);
}

export function formatPercent(value, digits = 0) {
  return new Intl.NumberFormat(current, {
    style: 'percent',
    maximumFractionDigits: digits,
  }).format(value || 0);
}

export function formatNumber(value, digits = 0) {
  return new Intl.NumberFormat(current, {
    maximumFractionDigits: digits,
  }).format(value || 0);
}

/**
 * Translate a count-dependent key, picking `<path>.one` / `<path>.other` by the
 * locale's own plural rules. English "1 words" and the "attempt(s)" parenthetical
 * the old code used are both wrong in every language, and Turkish does not
 * pluralize after a numeral at all — `Intl.PluralRules` knows that; a ternary
 * on `n === 1` does not.
 */
export function plural(path, count, params) {
  const rule = new Intl.PluralRules(current).select(count);
  const key = lookup(CATALOG[current], `${path}.${rule}`) !== undefined ? rule : 'other';
  return t(`${path}.${key}`, { count: formatNumber(count), ...params });
}

/** Turkish needs its own casing: 'i' uppercases to 'İ', and 'I' lowercases to 'ı'. */
export function upper(text, locale = current) {
  return String(text).toLocaleUpperCase(locale === 'tr' ? 'tr-TR' : locale);
}

export function lower(text, locale = current) {
  return String(text).toLocaleLowerCase(locale === 'tr' ? 'tr-TR' : locale);
}

export const LANGUAGE_NAMES = { en: 'English', tr: 'Türkçe', de: 'Deutsch' };
