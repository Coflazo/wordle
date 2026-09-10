#include "wordle/normalize.hpp"

#include <algorithm>
#include <array>
#include <unordered_map>

namespace wordle {
namespace {

constexpr char32_t kReplacement = 0xFFFD;

// Combining marks that appear in en/tr/de input.
constexpr char32_t kCombGrave = 0x0300;
constexpr char32_t kCombAcute = 0x0301;
constexpr char32_t kCombCircumflex = 0x0302;
constexpr char32_t kCombBreve = 0x0306;
constexpr char32_t kCombDotAbove = 0x0307;
constexpr char32_t kCombDiaeresis = 0x0308;
constexpr char32_t kCombCedilla = 0x0327;

struct Pair {
    char32_t base;
    char32_t mark;
    char32_t composed;
};

// The precomposed forms reachable from these three languages' keyboards.
constexpr Pair kCompose[] = {
    {U'a', kCombDiaeresis, U'ä'},   {U'A', kCombDiaeresis, U'Ä'},
    {U'o', kCombDiaeresis, U'ö'},   {U'O', kCombDiaeresis, U'Ö'},
    {U'u', kCombDiaeresis, U'ü'},   {U'U', kCombDiaeresis, U'Ü'},
    {U'c', kCombCedilla, U'ç'},     {U'C', kCombCedilla, U'Ç'},
    {U's', kCombCedilla, U'ş'},     {U'S', kCombCedilla, U'Ş'},
    {U'g', kCombBreve, U'ğ'},       {U'G', kCombBreve, U'Ğ'},
    {U'a', kCombCircumflex, U'â'},  {U'A', kCombCircumflex, U'Â'},
    {U'i', kCombCircumflex, U'î'},  {U'I', kCombCircumflex, U'Î'},
    {U'u', kCombCircumflex, U'û'},  {U'U', kCombCircumflex, U'Û'},
    {U'e', kCombAcute, U'é'},       {U'E', kCombAcute, U'É'},
    {U'e', kCombGrave, U'è'},       {U'E', kCombGrave, U'È'},
    {U'I', kCombDotAbove, U'İ'},
};

struct CaseMap {
    char32_t upper;
    char32_t lower;
};

// Shared by every locale. Turkish overrides I and İ below.
constexpr CaseMap kCase[] = {
    {U'Ç', U'ç'}, {U'Ğ', U'ğ'}, {U'Ö', U'ö'}, {U'Ş', U'ş'}, {U'Ü', U'ü'},
    {U'Ä', U'ä'}, {U'Â', U'â'}, {U'Î', U'î'}, {U'Û', U'û'}, {U'É', U'é'},
    {U'È', U'è'}, {U'Ï', U'ï'}, {U'Ô', U'ô'}, {U'Ê', U'ê'}, {U'À', U'à'},
    {U'Á', U'á'}, {U'Ó', U'ó'}, {U'Ú', U'ú'}, {U'Ñ', U'ñ'}, {U'Å', U'å'},
    {U'Æ', U'æ'}, {U'Ø', U'ø'}, {U'Œ', U'œ'}, {U'Ý', U'ý'}, {U'Ÿ', U'ÿ'},
    {U'Ì', U'ì'}, {U'Í', U'í'}, {U'Ò', U'ò'}, {U'Õ', U'õ'}, {U'Ã', U'ã'},
};

// U+1E9E LATIN CAPITAL LETTER SHARP S lowercases to ß.
constexpr char32_t kCapitalSharpS = 0x1E9E;

bool is_ascii_upper(char32_t c) { return c >= U'A' && c <= U'Z'; }
bool is_ascii_lower(char32_t c) { return c >= U'a' && c <= U'z'; }

char32_t lower_one(char32_t c, Lang lang) {
    if (lang == Lang::tr) {
        // The whole reason this file exists.
        if (c == U'I') return U'ı';
        if (c == U'İ') return U'i';
    } else {
        if (c == U'İ') return U'i';  // drop the dot rather than emit i + U+0307
    }
    if (is_ascii_upper(c)) return c + 32;
    if (c == kCapitalSharpS) return U'ß';
    for (const auto& m : kCase) {
        if (m.upper == c) return m.lower;
    }
    return c;
}

char32_t upper_one(char32_t c, Lang lang) {
    if (lang == Lang::tr) {
        if (c == U'i') return U'İ';
        if (c == U'ı') return U'I';
    } else {
        if (c == U'ı') return U'I';
    }
    if (is_ascii_lower(c)) return c - 32;
    if (c == U'ß') return kCapitalSharpS;
    for (const auto& m : kCase) {
        if (m.lower == c) return m.upper;
    }
    return c;
}

bool is_space(char32_t c) {
    return c == U' ' || c == U'\t' || c == U'\n' || c == U'\r' || c == U'\f' || c == U'\v';
}

}  // namespace

void utf8_append(std::string& out, char32_t cp) {
    if (cp < 0x80) {
        out.push_back(static_cast<char>(cp));
    } else if (cp < 0x800) {
        out.push_back(static_cast<char>(0xC0 | (cp >> 6)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    } else if (cp < 0x10000) {
        out.push_back(static_cast<char>(0xE0 | (cp >> 12)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    } else {
        out.push_back(static_cast<char>(0xF0 | (cp >> 18)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    }
}

std::vector<char32_t> utf8_decode(std::string_view s) {
    std::vector<char32_t> out;
    out.reserve(s.size());
    std::size_t i = 0;
    while (i < s.size()) {
        unsigned char b = static_cast<unsigned char>(s[i]);
        char32_t cp;
        int extra;
        if (b < 0x80) {
            cp = b;
            extra = 0;
        } else if ((b & 0xE0) == 0xC0) {
            cp = b & 0x1F;
            extra = 1;
        } else if ((b & 0xF0) == 0xE0) {
            cp = b & 0x0F;
            extra = 2;
        } else if ((b & 0xF8) == 0xF0) {
            cp = b & 0x07;
            extra = 3;
        } else {
            out.push_back(kReplacement);
            ++i;
            continue;
        }
        if (i + static_cast<std::size_t>(extra) >= s.size()) {
            out.push_back(kReplacement);
            break;
        }
        bool ok = true;
        for (int k = 1; k <= extra; ++k) {
            unsigned char cb = static_cast<unsigned char>(s[i + static_cast<std::size_t>(k)]);
            if ((cb & 0xC0) != 0x80) {
                ok = false;
                break;
            }
            cp = (cp << 6) | (cb & 0x3F);
        }
        if (!ok) {
            out.push_back(kReplacement);
            ++i;
            continue;
        }
        out.push_back(cp);
        i += static_cast<std::size_t>(extra) + 1;
    }
    return out;
}

std::string utf8_encode(const std::vector<char32_t>& cps) {
    std::string out;
    out.reserve(cps.size() * 2);
    for (char32_t c : cps) utf8_append(out, c);
    return out;
}

std::vector<char32_t> compose(const std::vector<char32_t>& cps) {
    std::vector<char32_t> out;
    out.reserve(cps.size());
    for (char32_t c : cps) {
        if (!out.empty()) {
            char32_t base = out.back();
            bool done = false;
            for (const auto& p : kCompose) {
                if (p.base == base && p.mark == c) {
                    out.back() = p.composed;
                    done = true;
                    break;
                }
            }
            if (done) continue;
            // A dot above an i is already implied by the letter itself.
            if (c == kCombDotAbove && (base == U'i' || base == U'ı')) {
                out.back() = U'i';
                continue;
            }
        }
        out.push_back(c);
    }
    return out;
}

std::vector<char32_t> to_lower(const std::vector<char32_t>& cps, Lang lang) {
    std::vector<char32_t> out;
    out.reserve(cps.size());
    for (char32_t c : cps) out.push_back(lower_one(c, lang));
    return out;
}

std::vector<char32_t> to_upper(const std::vector<char32_t>& cps, Lang lang) {
    std::vector<char32_t> out;
    out.reserve(cps.size());
    for (char32_t c : cps) out.push_back(upper_one(c, lang));
    return out;
}

namespace {
std::vector<char32_t> trim(std::vector<char32_t> v) {
    std::size_t b = 0, e = v.size();
    while (b < e && is_space(v[b])) ++b;
    while (e > b && is_space(v[e - 1])) --e;
    return std::vector<char32_t>(v.begin() + static_cast<long>(b), v.begin() + static_cast<long>(e));
}
}  // namespace

std::string fold(std::string_view s, Lang lang) {
    return utf8_encode(to_lower(compose(trim(utf8_decode(s))), lang));
}

std::string upper(std::string_view s, Lang lang) {
    return utf8_encode(to_upper(compose(trim(utf8_decode(s))), lang));
}

std::string deaccent(std::string_view s) {
    static const std::unordered_map<char32_t, const char*> kMap = {
        {U'ç', "c"}, {U'ğ', "g"}, {U'ı', "i"}, {U'ö', "o"}, {U'ş', "s"}, {U'ü', "u"},
        {U'ä', "a"}, {U'ß', "ss"}, {U'â', "a"}, {U'î', "i"}, {U'û', "u"}, {U'é', "e"},
        {U'è', "e"}, {U'ê', "e"}, {U'ë', "e"}, {U'ï', "i"}, {U'ô', "o"}, {U'à', "a"},
        {U'á', "a"}, {U'ó', "o"}, {U'ú', "u"}, {U'ñ', "n"}, {U'å', "a"}, {U'ø', "o"},
        {U'ì', "i"}, {U'í', "i"}, {U'ò', "o"}, {U'õ', "o"}, {U'ã', "a"}, {U'ý', "y"},
    };
    std::string out;
    out.reserve(s.size());
    for (char32_t c : compose(utf8_decode(s))) {
        auto it = kMap.find(c);
        if (it != kMap.end()) {
            out += it->second;
        } else {
            utf8_append(out, c);
        }
    }
    return out;
}

}  // namespace wordle
