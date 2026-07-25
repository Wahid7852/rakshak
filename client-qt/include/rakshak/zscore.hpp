
#pragma once
#include <vector>
#include <deque>

// Simple robust z-score anomaly on sliding window of feature vectors.
// Not HST, but very fast baseline for C++ hot path.
class ZScoreAnomaly {
public:
    explicit ZScoreAnomaly(size_t hist=200): hist(hist) {}
    double score(const std::vector<double>& x);
private:
    size_t hist;
    std::deque<std::vector<double>> buf;
};