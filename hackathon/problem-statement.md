# Problem statement

**Team:** Garima Shrivastava, Abdul Wahid Khan, Anna Mariya Martin

## Assigned theme

**Problem Statement 1: Autonomous Threat Hunter for Insider Attacks**

> Insider threats are among the hardest to detect because the activity often resembles
> normal behavior right up until damage is done - an employee quietly accessing sensitive
> files before resignation, or data being moved out in small, disguised increments.
>
> Build a system that ingests simulated organizational logs (login activity, file access,
> data transfers) and uses behavioral baselining to identify insider threats. The system
> should minimize false positives by relying on anomaly detection rather than static,
> rule-based triggers alone.

## The gap

An insider isn't running exploit code a signature can match, and there's no labeled
dataset of "insider attacks" the way there is for network intrusions or malware families -
the same person's badge-in, file open, and file copy look identical whether they're doing
their job or staging an exit. Two failures compound this:

1. **Rule-based triggers can't tell "unusual for anyone" from "unusual for this person."**
   A flat threshold ("more than N files/hour") either fires constantly for anyone whose job
   involves bulk access, or misses a quiet, gradual pattern that never crosses the global
   line. The PS is explicit about this: false positives have to come down by comparing
   behavior to the *individual's own normal*, not a office-wide rule.
2. **There's nothing to supervise-learn against.** Insider incidents are rare, mostly
   undisclosed, and each org's "normal" is different - a labeled training set doesn't
   really exist. Any system that requires one is answering a different, easier problem.

The PS background names the exact shape of the threat: sensitive-file access that quietly
increases before a resignation, and data moved out in small, individually unremarkable
increments rather than one obvious bulk exfil.

## Who this is for

A security team monitoring an organization's endpoints from one place - not an
employee-facing tool, and not something installed with detection logic on every machine.
The architecture question the PS forces is *where does the analysis happen*: RAKSHAK
answers it as one central node doing the baselining/scoring/alerting, fed by thin
collector agents on each monitored machine that only forward events. See
`solution-overview.md` for why that split matters and what it rules out.
