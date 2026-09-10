#include "wordle/solver.hpp"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>
#include <thread>

namespace wordle {
namespace {

int resolve_threads(int requested, std::size_t work) {
    if (requested > 0) return requested;
    unsigned hc = std::thread::hardware_concurrency();
    int n = hc == 0 ? 4 : static_cast<int>(hc);
    // One thread per ~64 units of work; spinning up 8 threads for 12 guesses
    // costs more than it saves.
    int by_work = static_cast<int>(work / 64) + 1;
    return std::max(1, std::min(n, by_work));
}

// Histogram over base-3 patterns. Only the touched buckets are cleared between
// guesses, so the 3^L allocation is paid once per thread, not once per guess.
class Histogram {
  public:
    explicit Histogram(int len) : counts_(static_cast<std::size_t>(kPow3[len]), 0) {
        touched_.reserve(256);
    }
    void add(Pattern p) {
        if (counts_[p]++ == 0) touched_.push_back(p);
    }
    // bits = log2(N) - (1/N) * sum(c * log2(c));  E[remaining] = (1/N) * sum(c^2)
    void finish(double n, double& bits, double& expected_remaining) {
        double sum_c_log = 0.0;
        double sum_sq = 0.0;
        for (Pattern p : touched_) {
            double c = static_cast<double>(counts_[p]);
            sum_c_log += c * std::log2(c);
            sum_sq += c * c;
            counts_[p] = 0;
        }
        touched_.clear();
        bits = std::log2(n) - sum_c_log / n;
        expected_remaining = sum_sq / n;
    }

  private:
    std::vector<std::uint32_t> counts_;
    std::vector<Pattern> touched_;
};

void rank_range(const std::vector<Word>& candidates,
                const std::vector<Counts>& candidate_counts,
                const std::vector<Word>& guesses,
                std::size_t begin,
                std::size_t end,
                int len,
                std::vector<Ranked>& out) {
    Histogram hist(len);
    const double n = static_cast<double>(candidates.size());
    for (std::size_t gi = begin; gi < end; ++gi) {
        const Word& g = guesses[gi];
        for (std::size_t ci = 0; ci < candidates.size(); ++ci) {
            hist.add(score(candidates[ci], candidate_counts[ci], g));
        }
        double bits = 0.0, rem = 0.0;
        hist.finish(n, bits, rem);
        out[gi] = Ranked{g, bits, rem, false};
    }
}

void mark_candidates(const std::vector<Word>& candidates, std::vector<Ranked>& ranked) {
    std::vector<Word> sorted = candidates;
    std::sort(sorted.begin(), sorted.end());
    for (Ranked& r : ranked) {
        r.is_candidate = std::binary_search(sorted.begin(), sorted.end(), r.word);
    }
}

// A guess that could itself be the answer wins ties: same information, plus a
// chance of ending the game this turn. Word order is the final tie-break so the
// whole ranking is deterministic and reproducible across runs.
bool better(const Ranked& a, const Ranked& b) {
    if (a.bits != b.bits) return a.bits > b.bits;
    if (a.is_candidate != b.is_candidate) return a.is_candidate;
    return std::memcmp(a.word.code, b.word.code, kMaxLen) < 0;
}

}  // namespace

std::vector<Word> filter(const std::vector<Word>& pool, const std::vector<Constraint>& history) {
    if (history.empty()) return pool;

    std::vector<Counts> gc(history.size());
    std::vector<Word> out;
    out.reserve(pool.size());

    for (const Word& w : pool) {
        Counts wc;
        wc.reset(w);
        bool ok = true;
        for (const Constraint& c : history) {
            if (c.guess.len != w.len) {
                ok = false;
                break;
            }
            // Scoring is symmetric in the sense we need: if w were the answer,
            // the played guess would have produced exactly this pattern.
            if (score(w, wc, c.guess) != c.pattern) {
                ok = false;
                break;
            }
        }
        if (ok) out.push_back(w);
    }
    return out;
}

std::vector<Ranked> rank(const std::vector<Word>& candidates,
                         const std::vector<Word>& guesses,
                         int top_k,
                         int threads) {
    std::vector<Ranked> out;
    if (candidates.empty() || guesses.empty()) return out;

    const int len = candidates.front().len;
    std::vector<Counts> cc(candidates.size());
    for (std::size_t i = 0; i < candidates.size(); ++i) cc[i].reset(candidates[i]);

    out.resize(guesses.size());
    const std::size_t work = candidates.size() * guesses.size() / 512 + 1;
    int nthreads = resolve_threads(threads, work);

    if (nthreads <= 1) {
        rank_range(candidates, cc, guesses, 0, guesses.size(), len, out);
    } else {
        std::vector<std::thread> pool;
        pool.reserve(static_cast<std::size_t>(nthreads));
        const std::size_t chunk = (guesses.size() + static_cast<std::size_t>(nthreads) - 1) /
                                  static_cast<std::size_t>(nthreads);
        for (int t = 0; t < nthreads; ++t) {
            std::size_t b = static_cast<std::size_t>(t) * chunk;
            std::size_t e = std::min(b + chunk, guesses.size());
            if (b >= e) break;
            pool.emplace_back([&, b, e] { rank_range(candidates, cc, guesses, b, e, len, out); });
        }
        for (auto& th : pool) th.join();
    }

    mark_candidates(candidates, out);
    if (top_k > 0 && static_cast<std::size_t>(top_k) < out.size()) {
        std::partial_sort(out.begin(), out.begin() + top_k, out.end(), better);
        out.resize(static_cast<std::size_t>(top_k));
    } else {
        std::sort(out.begin(), out.end(), better);
    }
    return out;
}

Ranked best_opener(const std::vector<Word>& candidates,
                   const std::vector<Word>& guesses,
                   int threads) {
    std::vector<Ranked> top = rank(candidates, guesses, 1, threads);
    if (top.empty()) return Ranked{Word{}, 0.0, 0.0, false};
    return top.front();
}

namespace {

// One greedy-entropy playthrough. Returns the turn the answer was reached on,
// or max_turns + 1 if the policy never converged.
int solve_one(const Word& answer,
              const std::vector<Word>& pool,
              const std::vector<Word>& guess_pool,
              const Word& opener,
              int max_turns,
              int guess_budget,
              Histogram& hist) {
    std::vector<Word> candidates = pool;
    Word guess = opener;

    for (int turn = 1; turn <= max_turns; ++turn) {
        Counts ac;
        ac.reset(answer);
        Pattern p = score(answer, ac, guess);
        if (p == all_green(answer.len)) return turn;

        Constraint c{guess, p};
        candidates = filter(candidates, {c});
        if (candidates.empty()) return max_turns + 1;
        if (candidates.size() == 1) {
            guess = candidates.front();
            continue;
        }

        // Rank the candidates themselves plus a deterministic slice of the wider
        // guess pool. Ranking all 42k Turkish words per turn per answer would
        // make the sweep hours long for no measurable gain in the tier split.
        std::vector<Word> probes = candidates;
        if (static_cast<int>(probes.size()) > guess_budget) {
            probes.resize(static_cast<std::size_t>(guess_budget));
        } else if (!guess_pool.empty()) {
            std::size_t room = static_cast<std::size_t>(guess_budget) - probes.size();
            std::size_t stride = std::max<std::size_t>(1, guess_pool.size() / std::max<std::size_t>(1, room));
            for (std::size_t i = 0; i < guess_pool.size() && room > 0; i += stride, --room) {
                probes.push_back(guess_pool[i]);
            }
        }

        std::vector<Counts> cc(candidates.size());
        for (std::size_t i = 0; i < candidates.size(); ++i) cc[i].reset(candidates[i]);

        double best_bits = -1.0;
        Word best = candidates.front();
        bool best_is_cand = false;
        const double n = static_cast<double>(candidates.size());
        for (const Word& g : probes) {
            for (std::size_t ci = 0; ci < candidates.size(); ++ci) {
                hist.add(score(candidates[ci], cc[ci], g));
            }
            double bits = 0.0, rem = 0.0;
            hist.finish(n, bits, rem);
            bool is_cand = std::find(candidates.begin(), candidates.end(), g) != candidates.end();
            if (bits > best_bits || (bits == best_bits && is_cand && !best_is_cand)) {
                best_bits = bits;
                best = g;
                best_is_cand = is_cand;
            }
        }
        guess = best;
    }
    return max_turns + 1;
}

}  // namespace

std::vector<double> sweep_difficulty(const std::vector<Word>& answers,
                                     const std::vector<Word>& guess_pool,
                                     const Word& opener,
                                     int max_turns,
                                     int guess_budget,
                                     int threads) {
    std::vector<double> out(answers.size(), 0.0);
    if (answers.empty()) return out;
    const int len = answers.front().len;

    int nthreads = resolve_threads(threads, answers.size());
    std::atomic<std::size_t> next{0};

    auto worker = [&] {
        Histogram hist(len);
        for (;;) {
            std::size_t i = next.fetch_add(1);
            if (i >= answers.size()) return;
            out[i] = static_cast<double>(
                solve_one(answers[i], answers, guess_pool, opener, max_turns, guess_budget, hist));
        }
    };

    if (nthreads <= 1) {
        worker();
    } else {
        std::vector<std::thread> pool;
        pool.reserve(static_cast<std::size_t>(nthreads));
        for (int t = 0; t < nthreads; ++t) pool.emplace_back(worker);
        for (auto& th : pool) th.join();
    }
    return out;
}

}  // namespace wordle
