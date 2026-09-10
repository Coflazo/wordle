// Candidate narrowing and expected-information-gain ranking.
//
// This is the reason the project has a C++ backend at all. Turkish has 42,907
// targets; ranking every allowed guess against every surviving candidate is a
// quadratic scan that Python cannot do inside a request. A full precomputed
// pattern matrix is not an option either — 42,907^2 uint16 entries is ~3.7 GB —
// so patterns are computed on the fly from packed words and the work is split
// across a thread pool.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "wordle/score.hpp"
#include "wordle/word.hpp"

namespace wordle {

struct Constraint {
    Word guess;
    Pattern pattern;
};

struct Ranked {
    Word word;
    double bits;                // expected information gain
    double expected_remaining;  // expected candidates left after playing it
    bool is_candidate;          // could this guess itself be the answer
};

// Keep only the words consistent with every (guess, pattern) already played.
std::vector<Word> filter(const std::vector<Word>& pool, const std::vector<Constraint>& history);

// Rank `guesses` by expected information gain against `candidates`.
// `top_k` <= 0 returns every guess. `threads` <= 0 auto-sizes.
std::vector<Ranked> rank(const std::vector<Word>& candidates,
                         const std::vector<Word>& guesses,
                         int top_k = 10,
                         int threads = 0);

// Turns a greedy-entropy solver needs to reach each answer, starting from
// `opener`. Offline only; feeds the difficulty tiers baked into the bank.
// `guess_budget` caps how many guesses are ranked per turn so the sweep stays
// tractable on the larger Turkish and German buckets.
std::vector<double> sweep_difficulty(const std::vector<Word>& answers,
                                     const std::vector<Word>& guess_pool,
                                     const Word& opener,
                                     int max_turns = 8,
                                     int guess_budget = 600,
                                     int threads = 0);

// Best opening guess for a pool, by information gain. Offline only.
Ranked best_opener(const std::vector<Word>& candidates,
                   const std::vector<Word>& guesses,
                   int threads = 0);

}  // namespace wordle
