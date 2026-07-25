
#include "rakshak/ngram.hpp"
#include <cmath>
#include <sstream>

std::string NGram::key(const std::vector<std::string>& ctx, const std::string& tok){
    std::ostringstream oss;
    for(size_t i=0;i<ctx.size();++i){ if(i) oss<<'|'; oss<<ctx[i]; }
    oss<<"->"<<tok; return oss.str();
}
std::string NGram::ctx_key(const std::vector<std::string>& ctx){
    std::ostringstream oss;
    for(size_t i=0;i<ctx.size();++i){ if(i) oss<<'|'; oss<<ctx[i]; }
    return oss.str();
}
void NGram::decay_counts() const{
    for(auto it=counts.begin(); it!=counts.end();){
        it->second *= decay;
        if(it->second < 1e-6) it = counts.erase(it); else ++it;
    }
    for(auto it=ctx_counts.begin(); it!=ctx_counts.end();){
        it->second *= decay;
        if(it->second < 1e-6) it = ctx_counts.erase(it); else ++it;
    }
}
void NGram::update(const std::string& token){
    if((int)window.size() == n-1){
        std::vector<std::string> ctx(window.begin(), window.end());
        counts[key(ctx, token)] += 1.0;
        ctx_counts[ctx_key(ctx)] += 1.0;
    }
    if((int)window.size() == n-1) window.pop_front();
    window.push_back(token);
    decay_counts();
}
double NGram::score(const std::vector<std::string>& seq) const{
    if(seq.empty()) return 0.0;
    double ll=0.0;
    std::deque<std::string> w;
    for(const auto& tok: seq){
        if((int)w.size() == n-1){
            std::vector<std::string> ctx(w.begin(), w.end());
            double numer = counts.count(key(ctx, tok)) ? counts.at(key(ctx, tok)) + 0.1 : 0.1;
            double denom = ctx_counts.count(ctx_key(ctx)) ? ctx_counts.at(ctx_key(ctx)) + 1.0 : 1.0;
            double p = numer/denom;
            if(p < 1e-9) p = 1e-9;
            ll += -std::log(p);
        }
        if((int)w.size() == n-1) w.pop_front();
        w.push_back(tok);
    }
    double avg = ll / std::max<size_t>(1, seq.size());
    return 1 - std::exp(-avg);
}