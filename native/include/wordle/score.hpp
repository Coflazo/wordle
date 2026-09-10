// Guess scoring. Mirrors the reference two-pass algorithm exactly: greens are
// claimed first, then yellows are drawn from the remaining letter budget.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "wordle/word.hpp"

namespace wordle {

enum : std::uint8_t { kGray = 0, kYellow = 1, kGreen = 2 };

// 3^10 = 59049 distinct masks, so a base-3 packed mask fits in a uint16.
using Pattern = std::uint16_t;
inline constexpr Pattern kPow3[kMaxLen + 1] = {1,    3,    9,     27,    81,   243,
                                               729,  2187, 6561,  19683, 59049};

// Per-answer letter counts, hoisted out of the inner loop so a bulk scan pays
// for them once per answer instead of once per (guess, answer) pair.
struct Counts {
    std::uint8_t n[kMaxAlphabet];
    void reset(const Word& w) {
        std::memset(n, 0, sizeof(n));
        for (int i = 0; i < w.len; ++i) ++n[w.code[i]];
    }
};

// Hot path. `answer_counts` must match `answer`.
inline Pattern score(const Word& answer, const Counts& answer_counts, const Word& guess) {
    std::uint8_t left[kMaxAlphabet];
    std::memcpy(left, answer_counts.n, sizeof(left));

    std::uint8_t marks[kMaxLen];
    const int L = answer.len;

    for (int i = 0; i < L; ++i) {
        if (guess.code[i] == answer.code[i]) {
            marks[i] = kGreen;
            --left[guess.code[i]];
        } else {
            marks[i] = kGray;
        }
    }
    for (int i = 0; i < L; ++i) {
        if (marks[i] == kGreen) continue;
        std::uint8_t c = guess.code[i];
        if (left[c] > 0) {
            marks[i] = kYellow;
            --left[c];
        }
    }

    Pattern p = 0;
    for (int i = 0; i < L; ++i) p += static_cast<Pattern>(marks[i]) * kPow3[i];
    return p;
}

inline Pattern score(const Word& answer, const Word& guess) {
    Counts c;
    c.reset(answer);
    return score(answer, c, guess);
}

// All-green is 2 in every position: 2 * (3^L - 1) / 2 = 3^L - 1.
inline Pattern all_green(int len) { return static_cast<Pattern>(kPow3[len] - 1); }

void unpack(Pattern p, int len, std::uint8_t* out);
Pattern pack(const std::uint8_t* marks, int len);

// "green"/"yellow"/"gray" strings, matching the JSON the API already returns.
std::vector<std::string> pattern_to_names(Pattern p, int len);
bool names_to_pattern(const std::vector<std::string>& names, Pattern& out);

}  // namespace wordle
