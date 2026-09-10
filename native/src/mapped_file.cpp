#include "wordle/mapped_file.hpp"

#include <stdexcept>
#include <utility>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>
#endif

namespace wordle {
namespace {

[[noreturn]] void fail(const std::string& path, const std::string& why) {
    throw std::runtime_error("cannot map " + path + ": " + why);
}

#ifdef _WIN32
std::string last_error() {
    DWORD code = ::GetLastError();
    char* text = nullptr;
    DWORD n = ::FormatMessageA(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM |
            FORMAT_MESSAGE_IGNORE_INSERTS,
        nullptr, code, 0, reinterpret_cast<char*>(&text), 0, nullptr);
    std::string out = n && text ? std::string(text, n) : "error " + std::to_string(code);
    if (text) ::LocalFree(text);
    while (!out.empty() && (out.back() == '\n' || out.back() == '\r')) out.pop_back();
    return out;
}
#endif

}  // namespace

MappedFile::~MappedFile() { close(); }

MappedFile::MappedFile(MappedFile&& o) noexcept { *this = std::move(o); }

MappedFile& MappedFile::operator=(MappedFile&& o) noexcept {
    if (this != &o) {
        close();
        data_ = o.data_;
        size_ = o.size_;
        o.data_ = nullptr;
        o.size_ = 0;
#ifdef _WIN32
        file_ = o.file_;
        mapping_ = o.mapping_;
        o.file_ = nullptr;
        o.mapping_ = nullptr;
#endif
    }
    return *this;
}

#ifdef _WIN32

void MappedFile::open(const std::string& path) {
    close();
    HANDLE file = ::CreateFileA(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr,
                                OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) fail(path, last_error());

    LARGE_INTEGER size{};
    if (!::GetFileSizeEx(file, &size)) {
        std::string why = last_error();
        ::CloseHandle(file);
        fail(path, why);
    }
    if (size.QuadPart == 0) {
        ::CloseHandle(file);
        fail(path, "file is empty");
    }

    HANDLE mapping = ::CreateFileMappingA(file, nullptr, PAGE_READONLY, 0, 0, nullptr);
    if (mapping == nullptr) {
        std::string why = last_error();
        ::CloseHandle(file);
        fail(path, why);
    }
    void* view = ::MapViewOfFile(mapping, FILE_MAP_READ, 0, 0, 0);
    if (view == nullptr) {
        std::string why = last_error();
        ::CloseHandle(mapping);
        ::CloseHandle(file);
        fail(path, why);
    }

    file_ = file;
    mapping_ = mapping;
    data_ = static_cast<const std::uint8_t*>(view);
    size_ = static_cast<std::size_t>(size.QuadPart);
}

void MappedFile::close() {
    if (data_ != nullptr) ::UnmapViewOfFile(const_cast<std::uint8_t*>(data_));
    if (mapping_ != nullptr) ::CloseHandle(mapping_);
    if (file_ != nullptr && file_ != INVALID_HANDLE_VALUE) ::CloseHandle(file_);
    data_ = nullptr;
    size_ = 0;
    mapping_ = nullptr;
    file_ = nullptr;
}

#else

void MappedFile::open(const std::string& path) {
    close();
    int fd = ::open(path.c_str(), O_RDONLY);
    if (fd < 0) fail(path, std::strerror(errno));

    struct stat st {};
    if (::fstat(fd, &st) != 0) {
        int e = errno;
        ::close(fd);
        fail(path, std::strerror(e));
    }
    if (st.st_size <= 0) {
        ::close(fd);
        fail(path, "file is empty");
    }

    void* m = ::mmap(nullptr, static_cast<std::size_t>(st.st_size), PROT_READ, MAP_PRIVATE, fd, 0);
    int e = errno;
    ::close(fd);  // the mapping holds its own reference to the file
    if (m == MAP_FAILED) fail(path, std::strerror(e));

    data_ = static_cast<const std::uint8_t*>(m);
    size_ = static_cast<std::size_t>(st.st_size);
}

void MappedFile::close() {
    if (data_ != nullptr) {
        ::munmap(const_cast<std::uint8_t*>(data_), size_);
        data_ = nullptr;
        size_ = 0;
    }
}

#endif

}  // namespace wordle
