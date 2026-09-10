// Socket compatibility for solverd.
//
// A Unix domain socket by default: it lives in the filesystem, so it cannot be
// reached from another machine, and file permissions decide who may ask about
// the word the player is currently guessing.
//
// Windows also supports AF_UNIX (since 10 1803), but CPython does not expose
// `socket.AF_UNIX` there, so Python cannot dial one. For that case the daemon
// also speaks TCP on loopback, guarded by a shared token — loopback alone would
// let any other account on the machine connect.
#pragma once

#include <string>

#ifdef _WIN32

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <winsock2.h>
// afunix.h must follow winsock2.h.
#include <afunix.h>
#include <ws2tcpip.h>
#include <windows.h>

namespace netcompat {

using socket_t = SOCKET;
inline constexpr socket_t kInvalidSocket = INVALID_SOCKET;

inline bool startup() {
    WSADATA data;
    return ::WSAStartup(MAKEWORD(2, 2), &data) == 0;
}
inline void shutdown_lib() { ::WSACleanup(); }
inline void close_socket(socket_t s) { ::closesocket(s); }
inline bool is_valid(socket_t s) { return s != INVALID_SOCKET; }
inline bool interrupted() { return ::WSAGetLastError() == WSAEINTR; }
inline void remove_file(const std::string& path) { ::DeleteFileA(path.c_str()); }
// Windows applies the containing directory's ACL to the socket file; there is
// no chmod equivalent, and the default already excludes other users.
inline void restrict_to_owner(const std::string&) {}

}  // namespace netcompat

#else

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

#include <cerrno>

namespace netcompat {

using socket_t = int;
inline constexpr socket_t kInvalidSocket = -1;

inline bool startup() { return true; }
inline void shutdown_lib() {}
inline void close_socket(socket_t s) { ::close(s); }
inline bool is_valid(socket_t s) { return s >= 0; }
inline bool interrupted() { return errno == EINTR; }
inline void remove_file(const std::string& path) { ::unlink(path.c_str()); }
inline void restrict_to_owner(const std::string& path) { ::chmod(path.c_str(), 0600); }

}  // namespace netcompat

#endif
