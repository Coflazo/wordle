#include "wordle/score.hpp"

namespace wordle {

void unpack(Pattern p, int len, std::uint8_t* out) {
    for (int i = 0; i < len; ++i) {
        out[i] = static_cast<std::uint8_t>(p % 3);
        p = static_cast<Pattern>(p / 3);
    }
}

Pattern pack(const std::uint8_t* marks, int len) {
    Pattern p = 0;
    for (int i = 0; i < len; ++i) p += static_cast<Pattern>(marks[i]) * kPow3[i];
    return p;
}

std::vector<std::string> pattern_to_names(Pattern p, int len) {
    static const char* kNames[3] = {"gray", "yellow", "green"};
    std::uint8_t marks[kMaxLen];
    unpack(p, len, marks);
    std::vector<std::string> out;
    out.reserve(static_cast<std::size_t>(len));
    for (int i = 0; i < len; ++i) out.emplace_back(kNames[marks[i]]);
    return out;
}

bool names_to_pattern(const std::vector<std::string>& names, Pattern& out) {
    if (names.empty() || names.size() > kMaxLen) return false;
    std::uint8_t marks[kMaxLen];
    for (std::size_t i = 0; i < names.size(); ++i) {
        if (names[i] == "gray" || names[i] == "grey") marks[i] = kGray;
        else if (names[i] == "yellow") marks[i] = kYellow;
        else if (names[i] == "green") marks[i] = kGreen;
        else return false;
    }
    out = pack(marks, static_cast<int>(names.size()));
    return true;
}

}  // namespace wordle
