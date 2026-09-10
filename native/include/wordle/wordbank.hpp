// Memory-mapped word bank.
//
// Replaces loading six JSON files into Python lists and sets, which measured
// 121 ms of parsing and 74 MB resident. A .wbk is mmap'd, so startup is a single
// syscall, pages are shared between processes, and nothing is on the heap.
//
// Layout (little-endian, the only byte order this ever runs on; `magic` is
// checked so a foreign-endian file is rejected rather than misread):
//
//   0   char[4]   magic "WBK1"
//   4   u32       format version
//   8   char[4]   language tag, NUL padded ("en\0\0")
//   12  u32       alphabet size
//   16  u32       target count (all lengths)
//   20  u32       allowed count (all lengths, superset of targets)
//   24  u32       strings offset
//   28  u32       strings length
//   32  u32[32]   alphabet codepoints, 0 for unused slots
//   160 Bucket[6] one per length 5..10
//   256 ...       payload
//
// Per length bucket: `allowed` is a flat array of 10-byte code strings sorted by
// memcmp, so membership is a binary search with no allocation. `targets` is an
// array of 16-byte records carrying the difficulty tier and an offset into the
// string blob for the display form (German nouns keep their capital).
#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include "wordle/alphabet.hpp"
#include "wordle/word.hpp"

namespace wordle {

inline constexpr char kMagic[4] = {'W', 'B', 'K', '1'};
inline constexpr std::uint32_t kFormatVersion = 1;
inline constexpr std::size_t kHeaderSize = 256;
inline constexpr std::size_t kAllowedStride = kMaxLen;   // 10
inline constexpr std::size_t kTargetStride = 16;
inline constexpr int kNumBuckets = kMaxLen - kMinLen + 1;  // lengths 5..10

// Difficulty tiers, produced offline by the entropy sweep in difficulty.cpp.
enum Tier : std::uint8_t { kCommon = 0, kStandard = 1, kRare = 2, kTierCount = 3 };

#pragma pack(push, 1)
struct Bucket {
    std::uint32_t target_off;
    std::uint32_t target_count;
    std::uint32_t allowed_off;
    std::uint32_t allowed_count;
};
struct TargetRec {
    std::uint8_t code[kMaxLen];
    std::uint8_t tier;
    std::uint8_t reserved;
    std::uint32_t display_off;
};
#pragma pack(pop)

static_assert(sizeof(Bucket) == 16, "Bucket must be 16 bytes");
static_assert(sizeof(TargetRec) == kTargetStride, "TargetRec must be 16 bytes");

class WordBank {
  public:
    WordBank() = default;
    ~WordBank();
    WordBank(const WordBank&) = delete;
    WordBank& operator=(const WordBank&) = delete;
    WordBank(WordBank&&) noexcept;
    WordBank& operator=(WordBank&&) noexcept;

    // Throws std::runtime_error with a message naming the path on any failure.
    void open(const std::string& path);
    bool is_open() const { return base_ != nullptr; }

    Lang lang() const { return lang_; }
    const Alphabet& alpha() const { return alphabet(lang_); }
    std::uint32_t target_count() const { return target_count_; }
    std::uint32_t allowed_count() const { return allowed_count_; }

    // O(log n) membership over the length bucket, no allocation.
    bool is_allowed(const Word& w) const;

    // Targets of one length, optionally restricted to a set of tiers given as a
    // bitmask (1<<kCommon | 1<<kRare | ...). 0 means "any tier".
    std::vector<Word> targets(int len, std::uint32_t tier_mask = 0) const;
    std::vector<Word> allowed(int len) const;

    // Zero-copy views into the mapping, for scans that must not allocate.
    // Both stay valid as long as this WordBank is open.
    const std::uint8_t* allowed_data(int len, std::uint32_t& count) const;
    const TargetRec* target_data(int len, std::uint32_t& count) const;

    // Is this word a target (not merely allowed)? O(log n), no allocation.
    bool is_target(const Word& w) const;

    // Uniformly random target of the given length and tier set. `seed` of 0
    // draws from a thread-local generator; any other value is deterministic,
    // which is what a daily or shareable puzzle needs.
    bool pick(int len, std::uint32_t tier_mask, std::uint64_t seed, Word& out) const;

    // Display form for a target (German "Straße"); falls back to the fold form.
    std::string display(const Word& w) const;

    std::uint32_t count_targets(int len, std::uint32_t tier_mask = 0) const;
    std::uint32_t count_allowed(int len) const;

  private:
    const Bucket* bucket(int len) const;
    void reset();

    const std::uint8_t* base_ = nullptr;
    std::size_t size_ = 0;
    Lang lang_ = Lang::en;
    std::uint32_t target_count_ = 0;
    std::uint32_t allowed_count_ = 0;
    std::uint32_t strings_off_ = 0;
    std::uint32_t strings_len_ = 0;
    std::string path_;
};

// Serializer used by the offline builder.
struct BuildEntry {
    std::string fold;     // canonical lowercase form
    std::string display;  // shown to the player; empty means same as fold
    bool is_target = false;
    std::uint8_t tier = kStandard;
};
void write_bank(const std::string& path, Lang lang, std::vector<BuildEntry> entries);

}  // namespace wordle
