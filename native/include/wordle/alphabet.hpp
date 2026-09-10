// Per-language alphabets. Every supported language fits in <= 32 letters, which
// lets a word pack into 5 bits per position and a letter-set into a uint32 mask.
#pragma once

#include <array>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace wordle {

inline constexpr int kMaxLen = 10;
inline constexpr int kMinLen = 5;
inline constexpr int kMaxAlphabet = 32;
inline constexpr std::uint8_t kNoCode = 0xFF;

// Highest codepoint we ever index directly (s-cedilla, U+015F).
inline constexpr char32_t kCodepointLimit = 0x0180;

enum class Lang : std::uint8_t { en = 0, tr = 1, de = 2 };

// Ordered letter set for one language. `order` is the collation order used when
// the word banks are sorted, so binary search over a bank stays valid.
struct Alphabet {
    Lang lang;
    std::vector<char32_t> letters;                 // code -> codepoint
    std::array<std::uint8_t, kCodepointLimit> index{};  // codepoint -> code

    std::uint8_t code_of(char32_t cp) const {
        if (cp >= kCodepointLimit) return kNoCode;
        return index[static_cast<std::size_t>(cp)];
    }
    std::size_t size() const { return letters.size(); }
};

const Alphabet& alphabet(Lang lang);
bool parse_lang(std::string_view name, Lang& out);
std::string_view lang_name(Lang lang);

}  // namespace wordle
