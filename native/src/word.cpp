#include "wordle/word.hpp"

#include "wordle/normalize.hpp"

namespace wordle {

bool encode(std::string_view folded, const Alphabet& ab, Word& out) {
    out.clear();
    std::vector<char32_t> cps = utf8_decode(folded);
    if (cps.size() < 1 || cps.size() > kMaxLen) return false;
    for (std::size_t i = 0; i < cps.size(); ++i) {
        std::uint8_t c = ab.code_of(cps[i]);
        if (c == kNoCode) return false;
        out.code[i] = c;
    }
    out.len = static_cast<std::uint8_t>(cps.size());
    return true;
}

std::string decode(const Word& w, const Alphabet& ab) {
    std::string out;
    for (int i = 0; i < w.len; ++i) {
        std::uint8_t c = w.code[i];
        if (c >= ab.size()) return {};
        utf8_append(out, ab.letters[c]);
    }
    return out;
}

}  // namespace wordle
