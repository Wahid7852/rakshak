# Problem statement

**Team:** Garima Shrivastava, Abdul Wahid Khan, Anna Mariya Martin

## Assigned theme

**Theme 2 (Quantum Machine Learning for Threat Detection)**
*"Quantum Malware Hunter & AI + Quantum = Early Ransomware Detection"*

> Use quantum-enhanced ML to detect unknown malware patterns in real-time. Build a hybrid
> AI system (classical + quantum) that predicts ransomware deployment patterns from user
> behavior logs.

Suggested dataset: simulated network traffic or malware signatures.

## The gap

Signature and blacklist-based detection only catches what it has already seen. Ransomware
and novel malware families are built specifically to slip past that: a new packer, a new
hash, a slightly mutated binary, and a purely signature-based tool is blind. By the time a
payload actually executes and starts encrypting files, the useful window for intervention
has already closed. AV-TEST tracks roughly 450,000 new malware samples surfacing daily;
volume alone rules out anything that depends on humans curating signatures fast enough.

Two separate failures compound this:

1. **Classical-only ML plateaus on borderline cases.** A single classical model either
   overfits to its training distribution or produces a lot of false positives when pushed
   to catch genuinely novel patterns. There's no cheap way to say "I'm not sure, escalate
   this one." Sommer and Paxson's 2010 IEEE S&P survey made this point about network
   intrusion detection specifically: classical ML struggles to generalize past what it was
   trained on, which is exactly the failure mode a defence-grade system can't afford.
2. **Most quantum-security demos are quantum-only toy models.** They run a quantum circuit
   over a small illustrative dataset and stop there, with no real classical backbone, no
   real-time constraint, no actual system a security operator could run. That's a research
   notebook, not a threat detector.

Ransomware in particular has a shape before it detonates: mass file touches, authentication
anomalies, privilege-escalation attempts, unusual process bursts, all visible in ordinary
user/system behavior logs, minutes before the encryption payload runs. A system that scores
that behavior stream in real time, and knows when to escalate an ambiguous case to a more
expensive (quantum) judgment, is the correct shape of answer to this theme.

## Who this is for

Security operators in high-assurance, air-gapped, or near-air-gapped environments, where
the cost of a miss isn't measured in dollars and there's zero tolerance for a cloud
dependency or an option to just "send the sample to a vendor and wait." Any credible
answer has to run entirely local, entirely offline, on hardware the operator already
controls. The same design serves any security operator or small team with the same
constraint, but the bar RAKSHAK is built against is the high-assurance one, not a
consumer one.
