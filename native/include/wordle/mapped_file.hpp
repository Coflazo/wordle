// Read-only memory-mapped file, POSIX and Windows.
//
// Kept behind its own type so wordbank.cpp stays free of platform ifdefs and
// there is exactly one place that knows how a mapping is created and released.
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace wordle {

class MappedFile {
  public:
    MappedFile() = default;
    ~MappedFile();
    MappedFile(const MappedFile&) = delete;
    MappedFile& operator=(const MappedFile&) = delete;
    MappedFile(MappedFile&&) noexcept;
    MappedFile& operator=(MappedFile&&) noexcept;

    // Throws std::runtime_error naming the path and the OS error on failure.
    void open(const std::string& path);
    void close();

    const std::uint8_t* data() const { return data_; }
    std::size_t size() const { return size_; }
    bool is_open() const { return data_ != nullptr; }

  private:
    const std::uint8_t* data_ = nullptr;
    std::size_t size_ = 0;
#ifdef _WIN32
    void* file_ = nullptr;     // HANDLE
    void* mapping_ = nullptr;  // HANDLE
#endif
};

}  // namespace wordle
