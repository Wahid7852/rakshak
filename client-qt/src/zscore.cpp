
#include "rakshak/zscore.hpp"
#include <cmath>
#include <algorithm>

double ZScoreAnomaly::score(const std::vector<double>& x){
    buf.push_back(x);
    if(buf.size() > hist) buf.pop_front();
    if(buf.size() < 10) return 0.0;
    size_t d = x.size();
    std::vector<double> mean(d,0.0), sd(d,0.0);
    for(const auto& v: buf){
        for(size_t i=0;i<d;++i) mean[i]+=v[i];
    }
    for(size_t i=0;i<d;++i) mean[i]/=buf.size();
    for(const auto& v: buf){
        for(size_t i=0;i<d;++i){ double diff=v[i]-mean[i]; sd[i]+=diff*diff; }
    }
    for(size_t i=0;i<d;++i){ sd[i]=std::sqrt(sd[i]/buf.size()); if(sd[i]<1e-6) sd[i]=1e-6; }
    double s=0.0;
    for(size_t i=0;i<d;++i){
        double z = std::fabs(x[i]-mean[i])/sd[i];
        s += std::tanh(z/5.0);
    }
    // Normalize roughly to [0,1]
    return std::min(1.0, s / (double)d);
}