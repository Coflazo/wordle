// Python bindings for the Wordle native core.
//
// Everything that touches a word bank or runs a solver scan releases the GIL,
// so a hint request never blocks the event loop that served it.

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "wordle/alphabet.hpp"
#include "wordle/normalize.hpp"
#include "wordle/score.hpp"
#include "wordle/solver.hpp"
#include "wordle/suggest.hpp"
#include "wordle/word.hpp"
#include "wordle/wordbank.hpp"

namespace py = pybind11;
using namespace wordle;

namespace {

Lang need_lang(const std::string& name) {
    Lang l;
    if (!parse_lang(name, l)) {
        throw py::value_error("unsupported language '" + name + "'; expected en, tr or de");
    }
    return l;
}

std::uint32_t tier_mask_from(const py::object& tiers) {
    if (tiers.is_none()) return 0;
    std::uint32_t mask = 0;
    for (const py::handle& h : tiers) {
        std::string name = py::cast<std::string>(h);
        if (name == "common") mask |= 1u << kCommon;
        else if (name == "standard") mask |= 1u << kStandard;
        else if (name == "rare") mask |= 1u << kRare;
        else throw py::value_error("unknown tier '" + name + "'; expected common, standard or rare");
    }
    return mask;
}

// Wraps WordBank so Python sees a normal object with str in / str out, while
// the C++ side keeps working in packed codes.
class Bank {
  public:
    explicit Bank(const std::string& path) { bank_.open(path); }

    std::string language() const { return std::string(lang_name(bank_.lang())); }
    std::uint32_t target_count() const { return bank_.target_count(); }
    std::uint32_t allowed_count() const { return bank_.allowed_count(); }

    Word need_word(const std::string& text) const {
        Word w;
        std::string folded = fold(text, bank_.lang());
        if (!encode(folded, bank_.alpha(), w)) {
            throw py::value_error("'" + text + "' is not writable in the " + language() +
                                  " alphabet");
        }
        return w;
    }

    // Returns false rather than raising: an unencodable guess is simply not a
    // word in this language, which is the same answer the caller needs.
    bool is_allowed(const std::string& text) const {
        Word w;
        if (!encode(fold(text, bank_.lang()), bank_.alpha(), w)) return false;
        return bank_.is_allowed(w);
    }

    bool is_target(const std::string& text) const {
        Word w;
        if (!encode(fold(text, bank_.lang()), bank_.alpha(), w)) return false;
        return bank_.is_target(w);
    }

    std::string display(const std::string& text) const {
        Word w;
        if (!encode(fold(text, bank_.lang()), bank_.alpha(), w)) return text;
        return bank_.display(w);
    }

    std::uint32_t count_targets(int len, const py::object& tiers) const {
        return bank_.count_targets(len, tier_mask_from(tiers));
    }
    std::uint32_t count_allowed(int len) const { return bank_.count_allowed(len); }

    std::vector<std::string> targets(int len, const py::object& tiers) const {
        std::uint32_t mask = tier_mask_from(tiers);
        std::vector<Word> ws;
        {
            py::gil_scoped_release release;
            ws = bank_.targets(len, mask);
        }
        return to_strings(ws);
    }

    py::object pick(int len, const py::object& tiers, std::uint64_t seed) const {
        std::uint32_t mask = tier_mask_from(tiers);
        Word w;
        bool ok;
        {
            py::gil_scoped_release release;
            ok = bank_.pick(len, mask, seed, w);
        }
        if (!ok) return py::none();
        return py::cast(decode(w, bank_.alpha()));
    }

    std::vector<std::string> suggest_words(const std::string& text, int limit, int max_distance,
                                           bool same_length_only) const {
        Word q;
        if (!encode(fold(text, bank_.lang()), bank_.alpha(), q)) return {};
        std::vector<Suggestion> hits;
        {
            py::gil_scoped_release release;
            hits = wordle::suggest(bank_, q, limit, max_distance, same_length_only);
        }
        std::vector<std::string> out;
        out.reserve(hits.size());
        for (const Suggestion& s : hits) out.push_back(decode(s.word, bank_.alpha()));
        return out;
    }

    // history: [(guess, ["green", "gray", ...]), ...]
    py::dict hint(int len, const py::list& history, int top_k, const std::string& guess_pool,
                  const py::object& tiers, int candidate_sample) const {
        std::vector<Constraint> constraints = parse_history(history, len);
        std::uint32_t mask = tier_mask_from(tiers);
        bool use_allowed = guess_pool == "allowed";
        if (guess_pool != "allowed" && guess_pool != "targets") {
            throw py::value_error("guess_pool must be 'targets' or 'allowed'");
        }

        std::vector<Word> candidates;
        std::vector<Ranked> ranked;
        {
            py::gil_scoped_release release;
            candidates = filter(bank_.targets(len, mask), constraints);
            if (!candidates.empty()) {
                std::vector<Word> pool = use_allowed ? bank_.allowed(len) : bank_.targets(len, mask);
                ranked = rank(candidates, pool, top_k);
            }
        }

        py::list suggestions;
        for (const Ranked& r : ranked) {
            py::dict d;
            d["word"] = decode(r.word, bank_.alpha());
            d["bits"] = r.bits;
            d["expected_remaining"] = r.expected_remaining;
            d["is_candidate"] = r.is_candidate;
            suggestions.append(d);
        }

        std::vector<Word> sample = candidates;
        if (candidate_sample >= 0 && sample.size() > static_cast<std::size_t>(candidate_sample)) {
            sample.resize(static_cast<std::size_t>(candidate_sample));
        }

        py::dict out;
        out["candidates_remaining"] = candidates.size();
        out["candidates"] = to_strings(sample);
        out["suggestions"] = suggestions;
        return out;
    }

    // Offline: mean greedy-entropy solve turns per target, used to assign tiers.
    py::dict sweep(int len, const std::string& opener, int max_turns, int guess_budget,
                   int threads) const {
        Word op;
        if (!encode(fold(opener, bank_.lang()), bank_.alpha(), op)) {
            throw py::value_error("opener '" + opener + "' is not writable in " + language());
        }
        if (op.len != len) {
            throw py::value_error("opener length " + std::to_string(op.len) +
                                  " does not match requested length " + std::to_string(len));
        }
        std::vector<Word> answers;
        std::vector<double> turns;
        {
            py::gil_scoped_release release;
            answers = bank_.targets(len, 0);
            turns = sweep_difficulty(answers, answers, op, max_turns, guess_budget, threads);
        }
        py::dict out;
        for (std::size_t i = 0; i < answers.size(); ++i) {
            out[py::str(decode(answers[i], bank_.alpha()))] = turns[i];
        }
        return out;
    }

    py::dict best_opener_for(int len, int threads) const {
        std::vector<Word> pool;
        Ranked best;
        {
            py::gil_scoped_release release;
            pool = bank_.targets(len, 0);
            best = best_opener(pool, pool, threads);
        }
        py::dict out;
        out["word"] = decode(best.word, bank_.alpha());
        out["bits"] = best.bits;
        out["expected_remaining"] = best.expected_remaining;
        return out;
    }

  private:
    std::vector<std::string> to_strings(const std::vector<Word>& ws) const {
        std::vector<std::string> out;
        out.reserve(ws.size());
        for (const Word& w : ws) out.push_back(decode(w, bank_.alpha()));
        return out;
    }

    std::vector<Constraint> parse_history(const py::list& history, int len) const {
        std::vector<Constraint> out;
        out.reserve(history.size());
        for (const py::handle& item : history) {
            auto pair = py::cast<std::pair<std::string, std::vector<std::string>>>(item);
            Word g;
            if (!encode(fold(pair.first, bank_.lang()), bank_.alpha(), g)) {
                throw py::value_error("history guess '" + pair.first + "' is not writable in " +
                                      language());
            }
            if (g.len != len) {
                throw py::value_error("history guess '" + pair.first + "' has length " +
                                      std::to_string(g.len) + ", expected " + std::to_string(len));
            }
            if (pair.second.size() != static_cast<std::size_t>(len)) {
                throw py::value_error("history mask for '" + pair.first + "' has " +
                                      std::to_string(pair.second.size()) + " entries, expected " +
                                      std::to_string(len));
            }
            Pattern p;
            if (!names_to_pattern(pair.second, p)) {
                throw py::value_error("history mask for '" + pair.first +
                                      "' must contain only green, yellow or gray");
            }
            out.push_back(Constraint{g, p});
        }
        return out;
    }

    WordBank bank_;
};

std::vector<std::string> score_words(const std::string& answer, const std::string& guess,
                                     const std::string& language) {
    Lang l = need_lang(language);
    const Alphabet& ab = alphabet(l);
    Word a, g;
    if (!encode(fold(answer, l), ab, a)) {
        throw py::value_error("answer '" + answer + "' is not writable in " + language);
    }
    if (!encode(fold(guess, l), ab, g)) {
        throw py::value_error("guess '" + guess + "' is not writable in " + language);
    }
    if (a.len != g.len) {
        throw py::value_error("answer and guess must be the same length (" +
                              std::to_string(a.len) + " vs " + std::to_string(g.len) + ")");
    }
    return pattern_to_names(score(a, g), a.len);
}

void py_write_bank(const std::string& path, const std::string& language, const py::list& entries) {
    Lang l = need_lang(language);
    std::vector<BuildEntry> out;
    out.reserve(entries.size());
    for (const py::handle& h : entries) {
        py::dict d = py::cast<py::dict>(h);
        BuildEntry e;
        e.fold = py::cast<std::string>(d["fold"]);
        e.display = d.contains("display") ? py::cast<std::string>(d["display"]) : e.fold;
        e.is_target = d.contains("is_target") && py::cast<bool>(d["is_target"]);
        if (d.contains("tier")) {
            std::string t = py::cast<std::string>(d["tier"]);
            e.tier = t == "common" ? kCommon : (t == "rare" ? kRare : kStandard);
        }
        out.push_back(std::move(e));
    }
    py::gil_scoped_release release;
    write_bank(path, l, std::move(out));
}

}  // namespace

PYBIND11_MODULE(wordle_core, m) {
    m.doc() = "Native core for Oflaz Wordle: normalization, word banks, scoring, solver.";
    m.attr("__version__") = "1.0.0";
    m.attr("MIN_LEN") = kMinLen;
    m.attr("MAX_LEN") = kMaxLen;
    m.attr("FORMAT_VERSION") = kFormatVersion;
    m.attr("TIERS") = py::make_tuple("common", "standard", "rare");
    m.attr("LANGUAGES") = py::make_tuple("en", "tr", "de");

    m.def("fold", [](const std::string& s, const std::string& lang) {
        return wordle::fold(s, need_lang(lang));
    }, py::arg("text"), py::arg("language"),
       "Locale-correct lowercase + composition. Turkish maps I->i-dotless and I-dot->i.");

    m.def("upper", [](const std::string& s, const std::string& lang) {
        return wordle::upper(s, need_lang(lang));
    }, py::arg("text"), py::arg("language"), "Locale-correct uppercase.");

    m.def("deaccent", &wordle::deaccent, py::arg("text"),
          "Strip diacritics to ASCII. For suggestions only, never for guess validation.");

    m.def("alphabet", [](const std::string& lang) {
        const Alphabet& ab = alphabet(need_lang(lang));
        std::string out;
        for (char32_t c : ab.letters) utf8_append(out, c);
        return out;
    }, py::arg("language"), "The language's letters, in collation order.");

    m.def("encodable", [](const std::string& text, const std::string& lang) {
        Lang l = need_lang(lang);
        Word w;
        return encode(wordle::fold(text, l), alphabet(l), w);
    }, py::arg("text"), py::arg("language"),
       "True if the folded text is spelled entirely from this language's alphabet "
       "and is 1..MAX_LEN letters long.");

    m.def("score", &score_words, py::arg("answer"), py::arg("guess"), py::arg("language"),
          "Score a guess. Returns a list of 'green' / 'yellow' / 'gray'.");

    m.def("write_bank", &py_write_bank, py::arg("path"), py::arg("language"), py::arg("entries"),
          "Serialize a .wbk from [{'fold','display','is_target','tier'}, ...].");

    py::class_<Bank>(m, "Bank")
        .def(py::init<const std::string&>(), py::arg("path"))
        .def_property_readonly("language", &Bank::language)
        .def_property_readonly("target_count", &Bank::target_count)
        .def_property_readonly("allowed_count", &Bank::allowed_count)
        .def("is_allowed", &Bank::is_allowed, py::arg("word"))
        .def("is_target", &Bank::is_target, py::arg("word"))
        .def("display", &Bank::display, py::arg("word"))
        .def("count_targets", &Bank::count_targets, py::arg("length"),
             py::arg("tiers") = py::none())
        .def("count_allowed", &Bank::count_allowed, py::arg("length"))
        .def("targets", &Bank::targets, py::arg("length"), py::arg("tiers") = py::none())
        .def("pick", &Bank::pick, py::arg("length"), py::arg("tiers") = py::none(),
             py::arg("seed") = 0,
             "Random target. seed=0 draws fresh; any other seed is reproducible.")
        .def("suggest", &Bank::suggest_words, py::arg("word"), py::arg("limit") = 5,
             py::arg("max_distance") = 2, py::arg("same_length_only") = false)
        .def("hint", &Bank::hint, py::arg("length"), py::arg("history"), py::arg("top_k") = 5,
             py::arg("guess_pool") = "targets", py::arg("tiers") = py::none(),
             py::arg("candidate_sample") = 12)
        .def("sweep_difficulty", &Bank::sweep, py::arg("length"), py::arg("opener"),
             py::arg("max_turns") = 8, py::arg("guess_budget") = 600, py::arg("threads") = 0)
        .def("best_opener", &Bank::best_opener_for, py::arg("length"), py::arg("threads") = 0);
}
