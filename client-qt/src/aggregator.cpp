
#include "rakshak/aggregator.hpp"
#include <algorithm>
#include <cmath>

void SlidingStats::add(double t, const std::string& etype, const std::string& user){
    events.push_back({t, etype, user});
    counts[etype]++;
    if(!user.empty()) users.insert(user);
}

void SlidingStats::evict(double now){
    double cutoff = now - window;
    while(!events.empty() && events.front().ts < cutoff){
        auto e = events.front(); events.pop_front();
        counts[e.type]--;
        if(counts[e.type] <= 0) counts.erase(e.type);
        // users set is not aggressively shrunk (cheap)
    }
}

Features SlidingStats::features(double now){
    evict(now);
    Features f;
    f.invalid_user = counts.count("invalid_user") ? counts["invalid_user"] : 0;
    f.failed_password = counts.count("failed_password") ? counts["failed_password"] : 0;
    f.preauth_close = counts.count("preauth_close") ? counts["preauth_close"] : 0;
    f.distinct_users = static_cast<double>(users.size());
    double total = f.invalid_user + f.failed_password + f.preauth_close + 1e-6;
    f.failed_rate = f.failed_password / total;
    f.burstiness = std::max({f.invalid_user, f.failed_password, f.preauth_close});
    // inter-arrival over last 50 events
    std::vector<double> gaps;
    double last = NAN;
    size_t start = events.size() > 50 ? events.size()-50 : 0;
    for(size_t i=start;i<events.size();++i){
        double ts = events[i].ts;
        if(!std::isnan(last)) gaps.push_back(ts-last);
        last = ts;
    }
    if(gaps.empty()){ f.inter_mean = window; f.inter_var=0; }
    else {
        double m=0; for(double g: gaps) m+=g; m/=gaps.size();
        double v=0; for(double g: gaps) v+=(g-m)*(g-m); v/=gaps.size();
        f.inter_mean = m; f.inter_var = v;
    }
    return f;
}