# Trains or serves model workflows for fuse.

def fuse(a_hst, a_seq, p_sgd, w1=0.4, w2=0.3, w3=0.3):
    # map probability to anomaly-ish [0,1]
    a_sgd = max(0.0, min(1.0, 2*p_sgd - 1.0))
    s = w1 * a_hst + w2 * a_seq + w3 * a_sgd
    return s
