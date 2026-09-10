// Locale-correct text normalization.
//
// This exists because invariant lowercasing is wrong for two of the three
// supported languages:
//   'İSTANBUL'.lower() -> 'i̇stanbul'  (9 codepoints for an 8-letter word)
//   'KIZIL'.lower()    -> 'kizil'      (not 'kızıl' — a valid word gets rejected)
// The same code is used by the runtime guess path and by the offline bank
// builder, so a word can never be stored in one form and looked up in another.
#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include "wordle/alphabet.hpp"

namespace wordle {

// UTF-8 <-> codepoints. Invalid bytes decode to U+FFFD.
std::vector<char32_t> utf8_decode(std::string_view s);
std::string utf8_encode(const std::vector<char32_t>& cps);
void utf8_append(std::string& out, char32_t cp);

// Compose the base+combining sequences that occur in en/tr/de text
// (diaeresis, cedilla, breve, circumflex, dot above). This is not general NFC;
// it covers the Latin subset these three languages can produce.
std::vector<char32_t> compose(const std::vector<char32_t>& cps);

// Locale-aware lowercase. Turkish maps I->ı and İ->i; every other language uses
// the invariant mapping, where I->i.
std::vector<char32_t> to_lower(const std::vector<char32_t>& cps, Lang lang);
std::vector<char32_t> to_upper(const std::vector<char32_t>& cps, Lang lang);

// compose + to_lower + trim. The canonical "fold form" a word is stored and
// looked up by. Display form (e.g. German "Straße") is kept separately.
std::string fold(std::string_view s, Lang lang);
std::string upper(std::string_view s, Lang lang);

// Strip diacritics to ASCII (ç->c, ğ->g, ı->i, ö->o, ş->s, ü->u, ä->a, ß->ss,
// â->a, î->i, û->u). Used for spelling suggestions, never for guess validation.
std::string deaccent(std::string_view s);

}  // namespace wordle
