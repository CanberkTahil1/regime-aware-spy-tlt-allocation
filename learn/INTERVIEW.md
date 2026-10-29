# Interview questions (one block per phase)

## R0
1. **Why reproduce the old strategy exactly before improving it?** So every later difference has a known cause. If v1
   didn't reproduce, I couldn't tell whether a change in results came from the new data, the new accounting or a bug.
   Matching to 1e-15 means the baseline row in the ladder is really v1.
2. **Why did you stop using Yahoo and VIX data?** Their terms bar automated collection (Yahoo) and storing or
   redistributing (Cboe), and v1 had committed both to a public repository. v2 uses public-domain Fed data, a disclosed
   Ken French proxy kept out of git, and realised volatility instead of VIX.
3. **How do you make sure a shared library doesn't change your results?** quantkit is installed from a git tag, not
   editable, and every run hashes each quantkit file it loaded against a pinned list. If a loaded file differs, the run
   fails.
