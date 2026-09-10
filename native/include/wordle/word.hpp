// Packed word representation used by every hot loop.
#pragma once

#include <cstdint>
#include <cstring>
#include <string>
#include <string_view>

#include "wordle/alphabet.hpp"

namespace wordle {

// A word as fixed-stride letter codes. Unused positions hold kNoCode so that
// memcmp over the full stride is a valid lexicographic comparison.
struct Word {
    std::uint8_t code[kMaxLen];
    std::uint8_t len;

    Word() { clear(); }
    void clear() {
        std::memset(code, kNoCode, kMaxLen);
        len = 0;
    }
    bool operator==(const Word& o) const {
        return len == o.len && std::memcmp(code, o.code, kMaxLen) == 0;
    }
    bool operator<(const Word& o) const {
        return std::memcmp(code, o.code, kMaxLen) < 0;
    }
};

// Encode an already-folded UTF-8 word. Returns false if any character is
// outside the language's alphabet or the length is out of range.
bool encode(std::string_view folded, const Alphabet& ab, Word& out);
std::string decode(const Word& w, const Alphabet& ab);

// Letter-presence bitmask, one bit per alphabet code.
inline std::uint32_t letter_mask(const Word& w) {
    std::uint32_t m = 0;
    for (int i = 0; i < w.len; ++i) m |= (1u << w.code[i]);
    return m;
}

}  // namespace wordle
