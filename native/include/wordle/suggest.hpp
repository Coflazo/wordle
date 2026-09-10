// "Did you mean" suggestions over the full allowed list.
//
// Replaces an exact ASCII-fold dictionary lookup that only worked for Turkish,
// was lowercase-only, and missed circumflex spellings such as "sebatkâr".
// Bounded Levenshtein over packed codes handles all three languages, so a
// German player who types "muede" is offered "müde".
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "wordle/wordbank.hpp"

namespace wordle {

struct Suggestion {
    Word word;
    int distance;
    bool is_target;
};

// Words within `max_distance` edits of `query`. Ranked by distance, then
// targets before allowed-only words, then difficulty tier, then alphabetically.
// `same_length_only` restricts to the query's length, which is what guess
// validation wants — a suggestion of a different length can never be played.
std::vector<Suggestion> suggest(const WordBank& bank,
                                const Word& query,
                                int limit = 5,
                                int max_distance = 2,
                                bool same_length_only = false);

// Levenshtein with an early exit once every band cell exceeds `cutoff`.
int edit_distance(const Word& a, const Word& b, int cutoff);

}  // namespace wordle
