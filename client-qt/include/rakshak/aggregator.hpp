
#pragma once
#include <string>
#include <deque>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <chrono>

struct Features {
    double invalid_user=0, failed_password=0, distinct_users=0, preauth_close=0;
    double failed_rate=0, burstiness=0, inter_mean=60, inter_var=0;
};

struct Event {
    double ts;
    std::string type;
    std::string user;
};

class SlidingStats {
public:
    explicit SlidingStats(double window_sec = 60.0): window(window_sec) {}
    void add(double t, const std::string& etype, const std::string& user);
    Features features(double now);

private:
    double window;
    std::deque<Event> events;
    std::unordered_map<std::string,int> counts;
    std::unordered_set<std::string> users;
    void evict(double now);
};