# Tracks third-party software notices and license obligations.
# Third-Party Notices

This project may integrate with external open-source tools. Do not vendor or redistribute
third-party source, binaries, VM images, signatures, or rules unless the license obligations
below have been reviewed and satisfied.

This document is not legal advice. It is an engineering compliance checklist for the repo.

## CAPE Sandbox

- Project: CAPE Sandbox / CAPEv2
- Upstream: https://github.com/kevoreilly/CAPEv2
- License: GNU General Public License version 3
- License text: https://raw.githubusercontent.com/kevoreilly/CAPEv2/master/LICENSE
- Planned RAKSHAK integration: external service adapter only

### How RAKSHAK Uses CAPE

RAKSHAK should talk to a separately installed CAPE instance through a narrow adapter. CAPE code,
VM images, analyzers, binaries, signatures, and modified CAPE files must not be copied into this
repository unless we intentionally accept and document the GPLv3 redistribution obligations.

### Compliance Rules

- Keep CAPE as a separately installed external service by default.
- Preserve CAPE copyright, license, and attribution notices in any deployment guide.
- If we distribute CAPE with RAKSHAK, include the GPLv3 license text and corresponding source
  access for CAPE and any CAPE modifications we distribute.
- If we modify CAPE, mark those files as modified and record the date and purpose.
- Do not imply CAPE authors endorse RAKSHAK.
- Keep RAKSHAK adapter code separate from copied CAPE implementation code.
- Review license obligations again before packaging installers, Docker images, VM appliances,
  or hosted bundles that include CAPE.

### Current Repository Status

- CAPE is not vendored in this repository.
- RAKSHAK contains only an adapter placeholder under `backend.engine.adapters.sandbox`.
- The default sandbox adapter remains a local static/fake adapter for tests and development.
