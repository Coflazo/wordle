#include "wordle/wordbank.hpp"

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <random>
#include <stdexcept>
#include <unordered_map>

#include "wordle/normalize.hpp"

namespace wordle {
namespace {

std::uint32_t rd32(const std::uint8_t* p) {
    std::uint32_t v;
    std::memcpy(&v, p, 4);
    return v;
}

void wr32(std::string& out, std::uint32_t v) {
    out.append(reinterpret_cast<const char*>(&v), 4);
}

[[noreturn]] void fail(const std::string& path, const std::string& why) {
    throw std::runtime_error("word bank " + path + ": " + why);
}

}  // namespace

WordBank::~WordBank() { reset(); }

WordBank::WordBank(WordBank&& o) noexcept { *this = std::move(o); }

WordBank& WordBank::operator=(WordBank&& o) noexcept {
    if (this != &o) {
        reset();
        map_ = std::move(o.map_);
        base_ = o.base_;
        size_ = o.size_;
        lang_ = o.lang_;
        target_count_ = o.target_count_;
        allowed_count_ = o.allowed_count_;
        strings_off_ = o.strings_off_;
        strings_len_ = o.strings_len_;
        path_ = std::move(o.path_);
        o.base_ = nullptr;
        o.size_ = 0;
    }
    return *this;
}

void WordBank::reset() {
    map_.close();
    base_ = nullptr;
    size_ = 0;
}

void WordBank::open(const std::string& path) {
    reset();
    map_.open(path);  // throws with the path and OS error already in the message
    if (map_.size() < kHeaderSize) {
        reset();
        fail(path, "shorter than a header; rebuild with scripts/build_wordbanks.py");
    }
    base_ = map_.data();
    size_ = map_.size();
    path_ = path;

    if (std::memcmp(base_, kMagic, 4) != 0) {
        reset();
        fail(path, "bad magic; not a .wbk file");
    }
    std::uint32_t version = rd32(base_ + 4);
    if (version != kFormatVersion) {
        reset();
        fail(path, "format version " + std::to_string(version) + ", expected " +
                       std::to_string(kFormatVersion) + "; rebuild the banks");
    }
    char tag[5] = {};
    std::memcpy(tag, base_ + 8, 4);
    Lang lang;
    if (!parse_lang(std::string_view(tag, std::strlen(tag)), lang)) {
        reset();
        fail(path, std::string("unknown language tag '") + tag + "'");
    }
    lang_ = lang;
    target_count_ = rd32(base_ + 16);
    allowed_count_ = rd32(base_ + 20);
    strings_off_ = rd32(base_ + 24);
    strings_len_ = rd32(base_ + 28);

    if (static_cast<std::size_t>(strings_off_) + strings_len_ > size_) {
        reset();
        fail(path, "string blob runs past end of file");
    }
    for (int len = kMinLen; len <= kMaxLen; ++len) {
        const Bucket* b = bucket(len);
        std::size_t a_end = static_cast<std::size_t>(b->allowed_off) +
                            static_cast<std::size_t>(b->allowed_count) * kAllowedStride;
        std::size_t t_end = static_cast<std::size_t>(b->target_off) +
                            static_cast<std::size_t>(b->target_count) * kTargetStride;
        if (a_end > size_ || t_end > size_) {
            reset();
            fail(path, "bucket for length " + std::to_string(len) + " runs past end of file");
        }
    }
}

const Bucket* WordBank::bucket(int len) const {
    return reinterpret_cast<const Bucket*>(base_ + 160) + (len - kMinLen);
}

bool WordBank::is_allowed(const Word& w) const {
    if (base_ == nullptr) return false;
    if (w.len < kMinLen || w.len > kMaxLen) return false;
    const Bucket* b = bucket(w.len);
    if (b->allowed_count == 0) return false;

    const std::uint8_t* arr = base_ + b->allowed_off;
    std::size_t lo = 0, hi = b->allowed_count;
    while (lo < hi) {
        std::size_t mid = lo + (hi - lo) / 2;
        int cmp = std::memcmp(arr + mid * kAllowedStride, w.code, kAllowedStride);
        if (cmp == 0) return true;
        if (cmp < 0) lo = mid + 1;
        else hi = mid;
    }
    return false;
}

std::vector<Word> WordBank::targets(int len, std::uint32_t tier_mask) const {
    std::vector<Word> out;
    if (base_ == nullptr || len < kMinLen || len > kMaxLen) return out;
    const Bucket* b = bucket(len);
    const TargetRec* recs = reinterpret_cast<const TargetRec*>(base_ + b->target_off);
    out.reserve(b->target_count);
    for (std::uint32_t i = 0; i < b->target_count; ++i) {
        if (tier_mask != 0 && (tier_mask & (1u << recs[i].tier)) == 0) continue;
        Word w;
        std::memcpy(w.code, recs[i].code, kMaxLen);
        w.len = static_cast<std::uint8_t>(len);
        out.push_back(w);
    }
    return out;
}

std::vector<Word> WordBank::allowed(int len) const {
    std::vector<Word> out;
    if (base_ == nullptr || len < kMinLen || len > kMaxLen) return out;
    const Bucket* b = bucket(len);
    const std::uint8_t* arr = base_ + b->allowed_off;
    out.reserve(b->allowed_count);
    for (std::uint32_t i = 0; i < b->allowed_count; ++i) {
        Word w;
        std::memcpy(w.code, arr + i * kAllowedStride, kMaxLen);
        w.len = static_cast<std::uint8_t>(len);
        out.push_back(w);
    }
    return out;
}

const std::uint8_t* WordBank::allowed_data(int len, std::uint32_t& count) const {
    if (base_ == nullptr || len < kMinLen || len > kMaxLen) {
        count = 0;
        return nullptr;
    }
    const Bucket* b = bucket(len);
    count = b->allowed_count;
    return base_ + b->allowed_off;
}

const TargetRec* WordBank::target_data(int len, std::uint32_t& count) const {
    if (base_ == nullptr || len < kMinLen || len > kMaxLen) {
        count = 0;
        return nullptr;
    }
    const Bucket* b = bucket(len);
    count = b->target_count;
    return reinterpret_cast<const TargetRec*>(base_ + b->target_off);
}

bool WordBank::is_target(const Word& w) const {
    std::uint32_t n = 0;
    const TargetRec* recs = target_data(w.len, n);
    if (recs == nullptr || n == 0) return false;
    std::size_t lo = 0, hi = n;
    while (lo < hi) {
        std::size_t mid = lo + (hi - lo) / 2;
        int cmp = std::memcmp(recs[mid].code, w.code, kMaxLen);
        if (cmp == 0) return true;
        if (cmp < 0) lo = mid + 1;
        else hi = mid;
    }
    return false;
}

bool WordBank::pick(int len, std::uint32_t tier_mask, std::uint64_t seed, Word& out) const {
    std::uint32_t n = 0;
    const TargetRec* recs = target_data(len, n);
    if (recs == nullptr || n == 0) return false;

    std::uint32_t eligible = 0;
    if (tier_mask == 0) {
        eligible = n;
    } else {
        for (std::uint32_t i = 0; i < n; ++i) {
            if (tier_mask & (1u << recs[i].tier)) ++eligible;
        }
        // An over-narrow tier filter must not make a length unplayable.
        if (eligible == 0) {
            tier_mask = 0;
            eligible = n;
        }
    }

    std::uint64_t r;
    if (seed == 0) {
        static thread_local std::mt19937_64 rng{std::random_device{}()};
        r = rng();
    } else {
        std::mt19937_64 rng{seed};
        r = rng();
    }
    std::uint32_t pick_index = static_cast<std::uint32_t>(r % eligible);

    for (std::uint32_t i = 0; i < n; ++i) {
        if (tier_mask != 0 && (tier_mask & (1u << recs[i].tier)) == 0) continue;
        if (pick_index == 0) {
            std::memcpy(out.code, recs[i].code, kMaxLen);
            out.len = static_cast<std::uint8_t>(len);
            return true;
        }
        --pick_index;
    }
    return false;
}

std::uint32_t WordBank::count_targets(int len, std::uint32_t tier_mask) const {
    if (base_ == nullptr || len < kMinLen || len > kMaxLen) return 0;
    const Bucket* b = bucket(len);
    if (tier_mask == 0) return b->target_count;
    const TargetRec* recs = reinterpret_cast<const TargetRec*>(base_ + b->target_off);
    std::uint32_t n = 0;
    for (std::uint32_t i = 0; i < b->target_count; ++i) {
        if (tier_mask & (1u << recs[i].tier)) ++n;
    }
    return n;
}

std::uint32_t WordBank::count_allowed(int len) const {
    if (base_ == nullptr || len < kMinLen || len > kMaxLen) return 0;
    return bucket(len)->allowed_count;
}

std::string WordBank::display(const Word& w) const {
    const Alphabet& ab = alpha();
    std::string folded = decode(w, ab);
    if (base_ == nullptr || w.len < kMinLen || w.len > kMaxLen) return folded;

    const Bucket* b = bucket(w.len);
    const TargetRec* recs = reinterpret_cast<const TargetRec*>(base_ + b->target_off);
    std::size_t lo = 0, hi = b->target_count;
    while (lo < hi) {
        std::size_t mid = lo + (hi - lo) / 2;
        int cmp = std::memcmp(recs[mid].code, w.code, kMaxLen);
        if (cmp == 0) {
            std::uint32_t off = recs[mid].display_off;
            if (off == 0 || off >= strings_len_) return folded;
            const char* s = reinterpret_cast<const char*>(base_ + strings_off_ + off);
            return std::string(s);
        }
        if (cmp < 0) lo = mid + 1;
        else hi = mid;
    }
    return folded;
}

void write_bank(const std::string& path, Lang lang, std::vector<BuildEntry> entries) {
    const Alphabet& ab = alphabet(lang);

    struct Rec {
        Word w;
        std::string display;
        bool is_target;
        std::uint8_t tier;
    };
    std::vector<Rec> recs;
    recs.reserve(entries.size());
    for (auto& e : entries) {
        Word w;
        if (!encode(e.fold, ab, w)) continue;  // builder already filtered; skip stragglers
        if (w.len < kMinLen || w.len > kMaxLen) continue;
        recs.push_back({w, e.display == e.fold ? std::string() : e.display, e.is_target, e.tier});
    }

    // Collapse duplicates, preferring the target record so tier/display survive.
    std::sort(recs.begin(), recs.end(), [](const Rec& a, const Rec& b) {
        int c = std::memcmp(a.w.code, b.w.code, kMaxLen);
        if (c != 0) return c < 0;
        return a.is_target > b.is_target;
    });
    recs.erase(std::unique(recs.begin(), recs.end(),
                           [](const Rec& a, const Rec& b) { return a.w == b.w; }),
               recs.end());

    // String blob. Offset 0 is a sentinel meaning "no display form", so the blob
    // starts with a NUL that nothing points at.
    std::string strings(1, '\0');
    std::unordered_map<std::string, std::uint32_t> interned;
    auto intern = [&](const std::string& s) -> std::uint32_t {
        if (s.empty()) return 0;
        auto it = interned.find(s);
        if (it != interned.end()) return it->second;
        std::uint32_t off = static_cast<std::uint32_t>(strings.size());
        strings += s;
        strings.push_back('\0');
        interned.emplace(s, off);
        return off;
    };

    std::string allowed_blob[kNumBuckets];
    std::string target_blob[kNumBuckets];
    std::uint32_t allowed_n[kNumBuckets] = {};
    std::uint32_t target_n[kNumBuckets] = {};

    for (const Rec& r : recs) {
        int bi = r.w.len - kMinLen;
        allowed_blob[bi].append(reinterpret_cast<const char*>(r.w.code), kMaxLen);
        ++allowed_n[bi];
        if (r.is_target) {
            TargetRec tr{};
            std::memcpy(tr.code, r.w.code, kMaxLen);
            tr.tier = r.tier;
            tr.reserved = 0;
            tr.display_off = intern(r.display);
            target_blob[bi].append(reinterpret_cast<const char*>(&tr), sizeof(tr));
            ++target_n[bi];
        }
    }

    std::uint32_t total_targets = 0, total_allowed = 0;
    for (int i = 0; i < kNumBuckets; ++i) {
        total_targets += target_n[i];
        total_allowed += allowed_n[i];
    }

    // Lay out the payload so every offset is known before the header is written.
    std::uint32_t cursor = static_cast<std::uint32_t>(kHeaderSize);
    Bucket buckets[kNumBuckets] = {};
    for (int i = 0; i < kNumBuckets; ++i) {
        buckets[i].allowed_off = cursor;
        buckets[i].allowed_count = allowed_n[i];
        cursor += static_cast<std::uint32_t>(allowed_blob[i].size());
    }
    for (int i = 0; i < kNumBuckets; ++i) {
        buckets[i].target_off = cursor;
        buckets[i].target_count = target_n[i];
        cursor += static_cast<std::uint32_t>(target_blob[i].size());
    }
    std::uint32_t strings_off = cursor;

    std::string header;
    header.append(kMagic, 4);
    wr32(header, kFormatVersion);
    char tag[4] = {};
    std::string_view name = lang_name(lang);
    std::memcpy(tag, name.data(), name.size());
    header.append(tag, 4);
    wr32(header, static_cast<std::uint32_t>(ab.size()));
    wr32(header, total_targets);
    wr32(header, total_allowed);
    wr32(header, strings_off);
    wr32(header, static_cast<std::uint32_t>(strings.size()));
    for (int i = 0; i < kMaxAlphabet; ++i) {
        wr32(header, i < static_cast<int>(ab.size()) ? static_cast<std::uint32_t>(ab.letters[i]) : 0);
    }
    header.append(reinterpret_cast<const char*>(buckets), sizeof(buckets));
    header.resize(kHeaderSize, '\0');

    std::string tmp = path + ".tmp";
    FILE* f = std::fopen(tmp.c_str(), "wb");
    if (f == nullptr) fail(tmp, std::strerror(errno));
    auto put = [&](const std::string& s) {
        if (!s.empty() && std::fwrite(s.data(), 1, s.size(), f) != s.size()) {
            std::fclose(f);
            fail(tmp, "short write");
        }
    };
    put(header);
    for (int i = 0; i < kNumBuckets; ++i) put(allowed_blob[i]);
    for (int i = 0; i < kNumBuckets; ++i) put(target_blob[i]);
    put(strings);
    if (std::fclose(f) != 0) fail(tmp, std::strerror(errno));
    // Rename last so a reader never sees a half-written bank.
    if (std::rename(tmp.c_str(), path.c_str()) != 0) fail(path, std::strerror(errno));
}

}  // namespace wordle
