#include "wordle/alphabet.hpp"

#include <mutex>

namespace wordle {
namespace {

// Collation order per language. Turkish and German both stay under 32 letters,
// which is what allows the 5-bit packing everywhere else.
constexpr char32_t kEn[] = {U'a', U'b', U'c', U'd', U'e', U'f', U'g', U'h', U'i',
                            U'j', U'k', U'l', U'm', U'n', U'o', U'p', U'q', U'r',
                            U's', U't', U'u', U'v', U'w', U'x', U'y', U'z'};

// Turkish alphabet, dictionary order. No q/w/x; ı and i are distinct letters.
constexpr char32_t kTr[] = {U'a', U'b', U'c', U'ç', U'd', U'e', U'f', U'g', U'ğ',
                            U'h', U'ı', U'i', U'j', U'k', U'l', U'm', U'n', U'o',
                            U'ö', U'p', U'r', U's', U'ş', U't', U'u', U'ü', U'v',
                            U'y', U'z'};

// German: the 26 basic letters plus the three umlauts and eszett.
constexpr char32_t kDe[] = {U'a', U'ä', U'b', U'c', U'd', U'e', U'f', U'g', U'h',
                            U'i', U'j', U'k', U'l', U'm', U'n', U'o', U'ö', U'p',
                            U'q', U'r', U's', U'ß', U't', U'u', U'ü', U'v', U'w',
                            U'x', U'y', U'z'};

Alphabet build(Lang lang, const char32_t* src, std::size_t n) {
    Alphabet ab;
    ab.lang = lang;
    ab.letters.assign(src, src + n);
    ab.index.fill(kNoCode);
    for (std::size_t i = 0; i < n; ++i) {
        ab.index[static_cast<std::size_t>(src[i])] = static_cast<std::uint8_t>(i);
    }
    return ab;
}

}  // namespace

const Alphabet& alphabet(Lang lang) {
    static const Alphabet en = build(Lang::en, kEn, std::size(kEn));
    static const Alphabet tr = build(Lang::tr, kTr, std::size(kTr));
    static const Alphabet de = build(Lang::de, kDe, std::size(kDe));
    switch (lang) {
        case Lang::tr: return tr;
        case Lang::de: return de;
        default: return en;
    }
}

bool parse_lang(std::string_view name, Lang& out) {
    if (name == "en") { out = Lang::en; return true; }
    if (name == "tr") { out = Lang::tr; return true; }
    if (name == "de") { out = Lang::de; return true; }
    return false;
}

std::string_view lang_name(Lang lang) {
    switch (lang) {
        case Lang::tr: return "tr";
        case Lang::de: return "de";
        default: return "en";
    }
}

static_assert(std::size(kTr) <= kMaxAlphabet, "Turkish alphabet must fit 5 bits");
static_assert(std::size(kDe) <= kMaxAlphabet, "German alphabet must fit 5 bits");
static_assert(std::size(kEn) <= kMaxAlphabet, "English alphabet must fit 5 bits");

}  // namespace wordle
