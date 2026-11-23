# Decisions

One line per methodological decision: what you chose, why, and what it changed.
Agents append here via the `/new-feature` skill; you append here by hand.

- Exclude `casual`, `registered`: they sum to `cnt` exactly. Leaky model R^2 1.000 -> honest ridge 0.583.
- Exclude `cnt_2d_bfr`: a shipped 2-day lag we cannot test the alignment of. Build our own lags instead.
- Exclude `instant`, `yr`, `days_since_2011`: time indexes let a tree predict a flat constant past 2011 and a linear model extrapolate a trend we have no grounds for.
- Split 2011 / H1 2012 / H2 2012 by date. Test set touched once, after all feature work.
- Report mean and persistence baselines with every score. Persistence (test R^2 0.510, MAE 840) is within 0.07 R^2 of ridge and beats it on MAE; that caveat goes in the report.
- Added `rides_2_days_ago` (`cnt.shift(2)` on the reindexed calendar): a count from d-2 is observed two days before d is predicted, so nothing on or after d enters it. Valid R^2 ridge 0.6475 -> 0.6453 (-0.0022, bootstrap 95% CI [-0.0106, +0.0063]), hgb 0.2185 -> 0.2481 (+0.0296, CI [+0.0119, +0.0505]): it only helps the model that still loses to persistence, so the recommendation is to drop it.
- `cnt_2d_bfr`, excluded as unverified, turns out to be exactly `shift(2)` on the calendar (714/714 rows) once we had a tested lag to check it against; the exclusion stands because we now own and test the lag ourselves.
