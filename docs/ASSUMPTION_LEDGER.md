
# ASSUMPTION LEDGER

> A living list of what we think is true, why we think it, and how we’ll test it.

| ID | Assumption | Rationale | Risk | Test / Falsification plan | Status |
|----|------------|-----------|------|---------------------------|--------|
| A1 | A single mic + ToF + light sensor is enough to detect rich “scenes”. | Minimizes BOM; aligns with classroom budgets. | Might miss thermal / air quality cues. | Compare with IMU/PIR/CO2 in a reference run. | Open |
| A2 | Normalized features (0–1) can be mapped linearly to timbre axes for musical results. | Transparency for teaching. | Nonlinearities may be more expressive. | Try piecewise/power curves and compare subjective ratings. | Open |
| A3 | OSC round‑trip latency is acceptable for gesture→sound. | Short messages, local network/USB. | Perceptible lag in dense scenes. | Measure RTT under load; switch to on‑board audio if needed. | Open |
| A4 | Data minimization is compatible with documentation goals. | Ethics priority. | Fewer artifacts for later analysis. | Provide optional, opt‑in capture scripts. | Open |
