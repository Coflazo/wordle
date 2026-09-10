#include "wordle/suggest.hpp"

#include <algorithm>
#include <bit>
#include <cstring>

namespace wordle {

int edit_distance(const Word& a, const Word& b, int cutoff) {
    const int n = a.len, m = b.len;
    if (std::abs(n - m) > cutoff) return cutoff + 1;

    int prev[kMaxLen + 1], cur[kMaxLen + 1];
    for (int j = 0; j <= m; ++j) prev[j] = j;

    for (int i = 1; i <= n; ++i) {
        cur[0] = i;
        int row_min = cur[0];
        const int lo = std::max(1, i - cutoff);
        const int hi = std::min(m, i + cutoff);
        // Cells outside the band can only make the distance worse.
        for (int j = 1; j < lo; ++j) cur[j] = cutoff + 1;
        for (int j = lo; j <= hi; ++j) {
            int cost = (a.code[i - 1] == b.code[j - 1]) ? 0 : 1;
            int v = std::min({prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost});
            cur[j] = v;
            row_min = std::min(row_min, v);
        }
        for (int j = hi + 1; j <= m; ++j) cur[j] = cutoff + 1;
        if (row_min > cutoff) return cutoff + 1;
        std::memcpy(prev, cur, sizeof(int) * static_cast<std::size_t>(m + 1));
    }
    return prev[m];
}

std::vector<Suggestion> suggest(const WordBank& bank,
                                const Word& query,
                                int limit,
                                int max_distance,
                                bool same_length_only) {
    std::vector<Suggestion> out;
    if (query.len == 0 || limit <= 0) return out;

    const std::uint32_t qmask = letter_mask(query);
    const int lo = same_length_only ? query.len : std::max(kMinLen, query.len - max_distance);
    const int hi = same_length_only ? query.len : std::min(kMaxLen, query.len + max_distance);

    std::vector<Suggestion> hits;
    for (int len = lo; len <= hi; ++len) {
        std::uint32_t n = 0;
        const std::uint8_t* arr = bank.allowed_data(len, n);
        if (arr == nullptr) continue;
        for (std::uint32_t i = 0; i < n; ++i) {
            Word w;
            std::memcpy(w.code, arr + i * kAllowedStride, kMaxLen);
            w.len = static_cast<std::uint8_t>(len);
            if (w == query) continue;
            // Two words within k edits cannot differ by more than 2k letters in
            // their letter sets. One popcount rejects most of the bank.
            if (std::popcount(qmask ^ letter_mask(w)) > 2 * max_distance) continue;
            int d = edit_distance(query, w, max_distance);
            if (d > max_distance) continue;
            hits.push_back(Suggestion{w, d, false});
        }
    }
    if (hits.empty()) return out;

    // Only now pay for the target lookups, on the handful that survived.
    for (Suggestion& s : hits) s.is_target = bank.is_target(s.word);

    std::sort(hits.begin(), hits.end(), [](const Suggestion& a, const Suggestion& b) {
        if (a.distance != b.distance) return a.distance < b.distance;
        if (a.is_target != b.is_target) return a.is_target;
        return std::memcmp(a.word.code, b.word.code, kMaxLen) < 0;
    });
    if (static_cast<int>(hits.size()) > limit) hits.resize(static_cast<std::size_t>(limit));
    return hits;
}

}  // namespace wordle
