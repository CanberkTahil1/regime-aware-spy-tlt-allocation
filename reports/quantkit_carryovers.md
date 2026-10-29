# Requests to quantkit (carry-overs; quantkit is never edited from this repo)

Each item is a request for a future quantkit tag. This repo uses it only after the owner re-pins.

## Q15 (optional) — `viz.headline` end labels longer than ~17 characters (owner O2.2, 2026-10-29)
- **Found:** R2. With quantkit v0.19.2, `viz.headline` raises when "<name>  $<end value>" leaves the figure. On the
  default figure size that happens for any label over about 17 characters, in any line position (measured 2026-10-28).
  The owner's readable names "Inverse-vol + vol target", "Inverse-vol SPY/TLT", "Vol-targeted SPY" and
  "SPY+T-bills at matched vol" do not fit.
- **Now:** this repo uses the owner's abbreviations (SPY, v1, VT SPY, 60/40, InvVol, InvVol+VT, SPY+bills) with a
  footer key (src/rspy/figures.py `SHORT`, `save_headline`).
- **Ask:** size the right margin to the longest end label, or wrap long end labels onto two lines, keeping the refusal
  for a label that still cannot fit. Optional: nothing here is blocked.
