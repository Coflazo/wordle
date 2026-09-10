// solverd — the Wordle solver sidecar.
//
// Holds every language's word bank mmap'd and caches narrowed candidate sets in
// RAM, so a hint at turn 3 does not re-scan 42,907 Turkish targets from scratch.
// FastAPI talks to it over a Unix domain socket.
//
// Protocol: one request line in, one JSON line out. Deliberately not JSON on the
// way in — a hand-rolled JSON parser is a bug farm, and a space-separated
// key=value line needs none, while staying debuggable:
//
//   $ nc -U run/solverd.sock
//   hint lang=tr len=5 history=kalem:00201 top_k=3
//   {"ok":true,"candidates_remaining":37,"suggestions":[...]}
//
// Ops:
//   ping
//   stats
//   hint    lang= len= [history=w:mask|w:mask] [top_k=5] [pool=targets|allowed]
//           [tiers=common,standard] [sample=12]
//   suggest lang= word= [limit=5] [max_distance=2] [same_length=1]
//   shutdown
//
// A mask is one digit per position: 0 gray, 1 yellow, 2 green.

#include "net.hpp"

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <list>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

#include "wordle/normalize.hpp"
#include "wordle/score.hpp"
#include "wordle/solver.hpp"
#include "wordle/suggest.hpp"
#include "wordle/wordbank.hpp"

using namespace wordle;

namespace {

constexpr int kMaxConnections = 16;
constexpr std::size_t kMaxRequestBytes = 64 * 1024;
constexpr std::size_t kCacheEntries = 256;

std::atomic<bool> g_running{true};
// The signal handler closes this so a blocking accept() returns at once.
// Without it, SIGTERM only took effect on the next incoming connection, so a
// daemon with no traffic ignored shutdown until it was killed.
std::atomic<netcompat::socket_t> g_listener{netcompat::kInvalidSocket};
std::string g_token;  // empty means no auth required (unix socket case)
std::atomic<std::uint64_t> g_requests{0};
std::atomic<std::uint64_t> g_cache_hits{0};

// ---------------------------------------------------------------- JSON output

std::string json_escape(const std::string& s) {
    std::string out;
    out.reserve(s.size() + 8);
    for (unsigned char c : s) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (c < 0x20) {
                    char buf[7];
                    std::snprintf(buf, sizeof(buf), "\\u%04x", c);
                    out += buf;
                } else {
                    out.push_back(static_cast<char>(c));
                }
        }
    }
    return out;
}

std::string json_error(const std::string& message) {
    return "{\"ok\":false,\"error\":\"" + json_escape(message) + "\"}";
}

std::string fixed(double v, int places = 4) {
    std::ostringstream os;
    os.setf(std::ios::fixed);
    os.precision(places);
    os << v;
    return os.str();
}

// --------------------------------------------------------------- request line

struct Request {
    std::string op;
    std::unordered_map<std::string, std::string> args;

    const std::string& get(const std::string& key, const std::string& fallback) const {
        auto it = args.find(key);
        return it == args.end() ? fallback : it->second;
    }
    int get_int(const std::string& key, int fallback) const {
        auto it = args.find(key);
        if (it == args.end()) return fallback;
        try {
            return std::stoi(it->second);
        } catch (...) {
            return fallback;
        }
    }
};

Request parse_request(const std::string& line) {
    Request req;
    std::istringstream is(line);
    is >> req.op;
    std::string token;
    while (is >> token) {
        std::size_t eq = token.find('=');
        if (eq == std::string::npos) continue;
        req.args.emplace(token.substr(0, eq), token.substr(eq + 1));
    }
    return req;
}

std::vector<std::string> split(const std::string& s, char sep) {
    std::vector<std::string> out;
    std::string cur;
    for (char c : s) {
        if (c == sep) {
            if (!cur.empty()) out.push_back(cur);
            cur.clear();
        } else {
            cur.push_back(c);
        }
    }
    if (!cur.empty()) out.push_back(cur);
    return out;
}

std::uint32_t parse_tiers(const std::string& spec) {
    if (spec.empty()) return 0;
    std::uint32_t mask = 0;
    for (const std::string& name : split(spec, ',')) {
        if (name == "common") mask |= 1u << kCommon;
        else if (name == "standard") mask |= 1u << kStandard;
        else if (name == "rare") mask |= 1u << kRare;
    }
    return mask;
}

// ------------------------------------------------------------------ bank pool

class Banks {
  public:
    explicit Banks(const std::string& dir) {
        for (const char* name : {"en", "tr", "de"}) {
            std::string path = dir + "/" + name + ".wbk";
            if (!std::filesystem::exists(path)) {
                throw std::runtime_error("missing bank: " + path +
                                         "\nrun: python -m scripts.build_wordbanks");
            }
            Lang lang;
            parse_lang(name, lang);
            banks_[static_cast<int>(lang)].open(path);
        }
    }
    const WordBank& get(Lang lang) const { return banks_[static_cast<int>(lang)]; }

  private:
    WordBank banks_[3];
};

// ------------------------------------------------------------- candidate cache
//
// The whole reason this runs as a daemon rather than in the request path: a
// narrowed candidate set for (language, length, history) is expensive to derive
// and is asked for repeatedly as the player thinks about their next guess.

class CandidateCache {
  public:
    bool get(const std::string& key, std::vector<Word>& out) {
        std::lock_guard<std::mutex> lock(mu_);
        auto it = index_.find(key);
        if (it == index_.end()) return false;
        order_.splice(order_.begin(), order_, it->second);
        out = it->second->second;
        return true;
    }

    void put(const std::string& key, const std::vector<Word>& value) {
        std::lock_guard<std::mutex> lock(mu_);
        auto it = index_.find(key);
        if (it != index_.end()) {
            it->second->second = value;
            order_.splice(order_.begin(), order_, it->second);
            return;
        }
        order_.emplace_front(key, value);
        index_.emplace(key, order_.begin());
        while (index_.size() > kCacheEntries) {
            index_.erase(order_.back().first);
            order_.pop_back();
        }
    }

    std::size_t size() {
        std::lock_guard<std::mutex> lock(mu_);
        return index_.size();
    }

  private:
    using Entry = std::pair<std::string, std::vector<Word>>;
    std::mutex mu_;
    std::list<Entry> order_;
    std::unordered_map<std::string, std::list<Entry>::iterator> index_;
};

// ----------------------------------------------------------------- operations

struct Server {
    Banks banks;
    CandidateCache cache;

    explicit Server(const std::string& dir) : banks(dir) {}

    std::string handle(const std::string& line) {
        Request req = parse_request(line);
        g_requests.fetch_add(1);

        // Only set when listening on TCP. A loopback port is reachable by every
        // account on the machine, unlike a mode-0600 socket file.
        if (!g_token.empty() && req.get("token", "") != g_token) {
            return json_error("unauthorized");
        }

        if (req.op == "ping") return "{\"ok\":true,\"service\":\"solverd\"}";
        if (req.op == "shutdown") {
            g_running.store(false);
            return "{\"ok\":true,\"stopping\":true}";
        }
        if (req.op == "stats") {
            return "{\"ok\":true,\"requests\":" + std::to_string(g_requests.load()) +
                   ",\"cache_hits\":" + std::to_string(g_cache_hits.load()) +
                   ",\"cached_sets\":" + std::to_string(cache.size()) + "}";
        }
        if (req.op == "hint") return hint(req);
        if (req.op == "suggest") return suggest_op(req);
        return json_error("unknown op '" + req.op + "'");
    }

    std::string hint(const Request& req) {
        Lang lang;
        if (!parse_lang(req.get("lang", ""), lang)) return json_error("bad or missing lang");
        int len = req.get_int("len", 0);
        if (len < kMinLen || len > kMaxLen) return json_error("len must be 5..10");

        const WordBank& bank = banks.get(lang);
        const Alphabet& ab = bank.alpha();
        std::uint32_t tier_mask = parse_tiers(req.get("tiers", ""));
        int top_k = std::max(0, std::min(req.get_int("top_k", 5), 50));
        int sample = std::max(0, std::min(req.get_int("sample", 12), 200));
        bool use_allowed = req.get("pool", "targets") == "allowed";

        std::vector<Constraint> history;
        const std::string& raw_history = req.get("history", "");
        for (const std::string& item : split(raw_history, '|')) {
            std::size_t colon = item.find(':');
            if (colon == std::string::npos) return json_error("history item needs word:mask");
            Word g;
            if (!encode(fold(item.substr(0, colon), lang), ab, g)) {
                return json_error("history word '" + item.substr(0, colon) + "' is not spellable");
            }
            std::string mask = item.substr(colon + 1);
            if (g.len != len || static_cast<int>(mask.size()) != len) {
                return json_error("history item '" + item + "' does not match len " +
                                  std::to_string(len));
            }
            std::uint8_t marks[kMaxLen];
            for (int i = 0; i < len; ++i) {
                if (mask[i] < '0' || mask[i] > '2') return json_error("mask digits must be 0,1,2");
                marks[i] = static_cast<std::uint8_t>(mask[i] - '0');
            }
            history.push_back(Constraint{g, pack(marks, len)});
        }

        std::string key = std::string(lang_name(lang)) + "|" + std::to_string(len) + "|" +
                          std::to_string(tier_mask) + "|" + raw_history;
        std::vector<Word> candidates;
        if (cache.get(key, candidates)) {
            g_cache_hits.fetch_add(1);
        } else {
            candidates = filter(bank.targets(len, tier_mask), history);
            cache.put(key, candidates);
        }

        std::vector<Ranked> ranked;
        if (!candidates.empty() && top_k > 0) {
            std::vector<Word> pool =
                use_allowed ? bank.allowed(len) : bank.targets(len, tier_mask);
            ranked = rank(candidates, pool, top_k);
        }

        std::string out = "{\"ok\":true,\"candidates_remaining\":" +
                          std::to_string(candidates.size()) + ",\"candidates\":[";
        for (std::size_t i = 0; i < candidates.size() && i < static_cast<std::size_t>(sample); ++i) {
            if (i) out += ",";
            out += "\"" + json_escape(decode(candidates[i], ab)) + "\"";
        }
        out += "],\"suggestions\":[";
        for (std::size_t i = 0; i < ranked.size(); ++i) {
            if (i) out += ",";
            out += "{\"word\":\"" + json_escape(decode(ranked[i].word, ab)) + "\",\"bits\":" +
                   fixed(ranked[i].bits) + ",\"expected_remaining\":" +
                   fixed(ranked[i].expected_remaining) + ",\"is_candidate\":" +
                   (ranked[i].is_candidate ? "true" : "false") + "}";
        }
        out += "]}";
        return out;
    }

    std::string suggest_op(const Request& req) {
        Lang lang;
        if (!parse_lang(req.get("lang", ""), lang)) return json_error("bad or missing lang");
        const WordBank& bank = banks.get(lang);
        Word query;
        if (!encode(fold(req.get("word", ""), lang), bank.alpha(), query)) {
            return "{\"ok\":true,\"suggestions\":[]}";
        }
        int limit = std::max(1, std::min(req.get_int("limit", 5), 25));
        int max_distance = std::max(1, std::min(req.get_int("max_distance", 2), 3));
        bool same_length = req.get_int("same_length", 0) != 0;

        std::vector<Suggestion> hits =
            wordle::suggest(bank, query, limit, max_distance, same_length);

        std::string out = "{\"ok\":true,\"suggestions\":[";
        for (std::size_t i = 0; i < hits.size(); ++i) {
            if (i) out += ",";
            out += "{\"word\":\"" + json_escape(decode(hits[i].word, bank.alpha())) +
                   "\",\"distance\":" + std::to_string(hits[i].distance) +
                   ",\"is_target\":" + (hits[i].is_target ? "true" : "false") + "}";
        }
        out += "]}";
        return out;
    }
};

// -------------------------------------------------------------------- sockets

bool send_all(netcompat::socket_t fd, const std::string& payload) {
    std::size_t sent = 0;
    while (sent < payload.size()) {
        int n = static_cast<int>(::send(fd, payload.data() + sent,
                                        static_cast<int>(payload.size() - sent), 0));
        if (n <= 0) return false;
        sent += static_cast<std::size_t>(n);
    }
    return true;
}

void serve_connection(netcompat::socket_t fd, Server& server) {
    std::string buffer;
    char chunk[4096];
    for (;;) {
        int n = static_cast<int>(::recv(fd, chunk, sizeof(chunk), 0));
        if (n <= 0) break;
        buffer.append(chunk, static_cast<std::size_t>(n));
        if (buffer.size() > kMaxRequestBytes) {
            send_all(fd, json_error("request too large") + "\n");
            break;
        }
        std::size_t nl;
        while ((nl = buffer.find('\n')) != std::string::npos) {
            std::string line = buffer.substr(0, nl);
            buffer.erase(0, nl + 1);
            if (line.empty()) continue;
            std::string reply;
            try {
                reply = server.handle(line);
            } catch (const std::exception& e) {
                reply = json_error(e.what());
            }
            if (!send_all(fd, reply + "\n")) {
                netcompat::close_socket(fd);
                return;
            }
        }
    }
    netcompat::close_socket(fd);
}

void on_signal(int) {
    g_running.store(false);
    netcompat::socket_t fd = g_listener.exchange(netcompat::kInvalidSocket);
    // close() is on the POSIX async-signal-safe list; this is what unblocks
    // the accept() the main loop is sitting in.
    if (netcompat::is_valid(fd)) netcompat::close_socket(fd);
}

}  // namespace

int main(int argc, char** argv) {
    std::string socket_path = "run/solverd.sock";
    std::string bank_dir = "app/data/banks";
    int tcp_port = 0;  // 0 = use a unix socket
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--socket" && i + 1 < argc) socket_path = argv[++i];
        else if (arg == "--banks" && i + 1 < argc) bank_dir = argv[++i];
        else if (arg == "--tcp" && i + 1 < argc) tcp_port = std::atoi(argv[++i]);
        else if (arg == "--token" && i + 1 < argc) g_token = argv[++i];
        else if (arg == "--help") {
            std::cout << "usage: solverd [--socket PATH | --tcp PORT [--token SECRET]]"
                         " [--banks DIR]\n";
            return 0;
        } else {
            std::cerr << "solverd: unknown argument " << arg << "\n";
            return 2;
        }
    }

    if (!netcompat::startup()) {
        std::cerr << "solverd: socket library failed to initialize\n";
        return 1;
    }

    // A dead process leaves its socket file behind and bind() would fail on it.
    // Safe to remove: if another solverd were live on this path, the bind below
    // would fail anyway and we exit.
    std::error_code ec;
    if (tcp_port == 0) {
        std::filesystem::create_directories(std::filesystem::path(socket_path).parent_path(), ec);
        netcompat::remove_file(socket_path);
    }

    std::unique_ptr<Server> server;
    try {
        server = std::make_unique<Server>(bank_dir);
    } catch (const std::exception& e) {
        std::cerr << "solverd: " << e.what() << "\n";
        return 1;
    }

    netcompat::socket_t listener;
    std::string endpoint;

    if (tcp_port > 0) {
        // Loopback only. Never INADDR_ANY: this answers questions about the
        // word the player is mid-way through guessing.
        listener = ::socket(AF_INET, SOCK_STREAM, 0);
        if (!netcompat::is_valid(listener)) {
            std::cerr << "solverd: cannot create socket\n";
            return 1;
        }
        int reuse = 1;
        ::setsockopt(listener, SOL_SOCKET, SO_REUSEADDR,
                     reinterpret_cast<const char*>(&reuse), sizeof(reuse));
        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_port = htons(static_cast<std::uint16_t>(tcp_port));
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        if (::bind(listener, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
            std::cerr << "solverd: cannot bind 127.0.0.1:" << tcp_port
                      << " (already in use?)\n";
            return 1;
        }
        endpoint = "127.0.0.1:" + std::to_string(tcp_port);
        if (g_token.empty()) {
            std::cerr << "solverd: refusing to listen on TCP without --token\n";
            return 1;
        }
    } else {
        listener = ::socket(AF_UNIX, SOCK_STREAM, 0);
        if (!netcompat::is_valid(listener)) {
            std::cerr << "solverd: cannot create socket\n";
            return 1;
        }
        sockaddr_un addr{};
        addr.sun_family = AF_UNIX;
        if (socket_path.size() >= sizeof(addr.sun_path)) {
            std::cerr << "solverd: socket path too long (" << socket_path.size() << " >= "
                      << sizeof(addr.sun_path) << "): " << socket_path << "\n";
            return 1;
        }
        std::strncpy(addr.sun_path, socket_path.c_str(), sizeof(addr.sun_path) - 1);
        if (::bind(listener, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
            std::cerr << "solverd: cannot bind " << socket_path
                      << " (is another solverd already running?)\n";
            return 1;
        }
        netcompat::restrict_to_owner(socket_path);
        endpoint = socket_path;
    }

    if (::listen(listener, kMaxConnections) != 0) {
        std::cerr << "solverd: cannot listen on " << endpoint << "\n";
        return 1;
    }

    g_listener.store(listener);
    std::signal(SIGINT, on_signal);
    std::signal(SIGTERM, on_signal);
#ifdef SIGPIPE
    std::signal(SIGPIPE, SIG_IGN);  // a client that hangs up must not kill us
#endif

    std::cout << "solverd listening on " << endpoint << " (banks: " << bank_dir << ")"
              << std::endl;

    // Connections are handled on detached threads, so the cap is an atomic
    // counter rather than a container of joinables — a detached thread is never
    // joinable, so trying to reap a vector of them would let the cap through.
    std::atomic<int> active{0};
    while (g_running.load()) {
        netcompat::socket_t fd = ::accept(listener, nullptr, nullptr);
        if (!netcompat::is_valid(fd)) {
            if (netcompat::interrupted()) continue;
            break;
        }
        if (active.load() >= kMaxConnections) {
            send_all(fd, json_error("server busy") + "\n");
            netcompat::close_socket(fd);
            continue;
        }
        active.fetch_add(1);
        std::thread([fd, &server, &active] {
            serve_connection(fd, *server);
            active.fetch_sub(1);
        }).detach();
    }

    netcompat::socket_t remaining = g_listener.exchange(netcompat::kInvalidSocket);
    if (netcompat::is_valid(remaining)) netcompat::close_socket(remaining);
    if (tcp_port == 0) netcompat::remove_file(socket_path);
    netcompat::shutdown_lib();
    std::cout << "solverd stopped" << std::endl;
    return 0;
}
