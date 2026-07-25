
#pragma once
#include <deque>
#include <string>
#include <unordered_map>
#include <vector>

class NGram {
public:
    explicit NGram(int n=3, double decay=0.999): n(n), decay(decay) {}
    void update(const std::string& token);
    double score(const std::vector<std::string>& seq) const;

private:
    int n;
    double decay;
    std::deque<std::string> window;
    mutable std::unordered_map<std::string,double> counts;
    mutable std::unordered_map<std::string,double> ctx_counts;
    void decay_counts() const;
    static std::string key(const std::vector<std::string>& ctx, const std::string& tok);
    static std::string ctx_key(const std::vector<std::string>& ctx);
};