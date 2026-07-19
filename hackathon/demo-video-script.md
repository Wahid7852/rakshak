# Demo video script

5 minutes, shot by shot. Everything runs against the real backend and real Qt client
started with `scripts/dev.sh`; nothing shown is mocked or scripted output.

**Before recording:** run `scripts/dev.sh` once so the venv and build are warm, then close
the app. Have a second terminal ready in the same repo root for `samples/simulate_tail.sh`.

## 0:00 to 0:30, hook

**On screen:** title card or the app's Dashboard on first launch.

**Say:** "Quantum ML for threat detection asks for a hybrid classical and quantum system
that catches unknown malware in real time and reads ransomware behavior off user logs.
This is RAKSHAK: a working cascade that runs both, on your own machine, with no cloud
dependency."

## 0:30 to 1:15, architecture in one breath

**On screen:** cut to the deck's architecture slide, or narrate over the Dashboard.

**Say:** "Every request goes through one decision core. Log lines get scored by a small
cascade of anomaly detectors, no labels needed. Files get scored by classical models
first, and only genuinely borderline cases escalate to a quantum-embedded SVM. Cheap
first, quantum last, so it stays real time."

## 1:15 to 2:15, live file scan

**On screen:** `scripts/dev.sh` running, app open on the Scan page.

**Do:** scan `samples/quarantine-test.txt`.

**Say while it runs:** "This file has a PE header, high-entropy padding, and command
strings a real detector would flag." (verdict appears) "Malicious signal, real score, real
confidence, not a canned response." Switch to Dashboard, point at the "files scanned"
counter ticking up.

**Say:** "That number is live cumulative state, not a placeholder."

## 2:15 to 3:15, log analysis

**On screen:** second terminal.

**Do:** run `samples/simulate_tail.sh /tmp/watched.log`, with Settings -> Log path already
pointed at `/tmp/watched.log` and saved. Switch to Log Analysis.

**Say:** "This script appends one real log line every two seconds. RAKSHAK tails it live:
every line lands in Raw Tail, and anything scored suspicious shows up here in Flagged
Lines and on the Dashboard's Recent Activity." Also paste one line manually into "Check
line" for an on-demand verdict.

**Say:** "Manual checks and background tailing both feed the same view. Nothing an
operator does by hand is invisible to the rest of the UI."

## 3:15 to 4:00, quarantine

**On screen:** terminal.

**Do:** run `.venv/bin/python samples/seed_quarantine.py`, restart the backend (Ctrl+C and
re-run `scripts/dev.sh`), open the Quarantine page, hit Refresh.

**Say:** "No synthetic file crosses the auto-quarantine confidence bar under default
settings; that's a deliberate safety ceiling, not a limitation. This seeds one real entry
directly, Fernet-encrypted and HMAC-signed on disk." Restore it, then delete it, showing
both actions completing against the real store.

## 4:00 to 4:40, adjustability and theme

**On screen:** any page with a table (Log Analysis or Quarantine), and the sidebar.

**Do:** drag a column header to resize it, drag the sidebar splitter, click the theme
toggle to flip to dark mode live, restart the app to show both the column width and the
theme choice persisted.

**Say:** "Every layout choice here is real state, saved and restored, not cosmetic."

## 4:40 to 5:00, close

**On screen:** Dashboard or the deck's engineering-rigor slide.

**Say:** "216 tests, real coverage, a CI pipeline that scans its own code and its own
dependencies. For a tool whose job is telling you what to trust, that has to hold up to
the same scrutiny. That's RAKSHAK."
