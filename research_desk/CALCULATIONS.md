# Calculations and model boundaries

## Odds

For American odds A:

- A > 0: decimal d = 1 + A/100.
- A < 0: d = 1 + 100/abs(A).
- A = 0 is invalid.

For decimal odds d > 1: A = 100(d−1) if d ≥ 2; otherwise A = −100/(d−1). Raw implied probability is 1/d. Nonfinite values and boolean numbers are rejected.

## Margin removal — market benchmark only

For an exactly matched and sufficiently complete market, margin M = sum(1/d_i) − 1. Proportional normalization produces q_i = (1/d_i)/sum(1/d_j). This is the only removal method implemented. It preserves the bookmaker's relative probability proportions; it does not prove calibration or remove favourite/longshot bias. Negative margin is recorded as such, not called a positive model edge.

The adapter attempts benchmarks only for complementary same-book contracts: complete two/three-way moneylines (including Draw/Tie where required), opposite handicap lines for both teams, and Over/Under at the same point and participant. Explicit three-way markets missing the draw are incomplete. Alternate handicap lines group by absolute point and require complementary signs. Period keys stay distinct. Incomplete markets, one-sided props, general event props and priced subsets of outright fields receive no benchmark.

Book rules remain unverified. Where a push is possible, the normalized binary benchmark is conditional on a decisive outcome; it supplies neither push probability nor unconditional EV. Draw-no-bet is similarly conditional on no draw. Futures require a complete field and settlement horizon; the adapter does not infer either from a priced subset.

## Expected net profit per unit

`estimate_ev` is a deterministic utility over a **supplied exhaustive settlement distribution**, not a model. For outcomes i with probability p_i and net payout r_i per original unit: EV = sum(p_i r_i). Probabilities must sum to one, remain in [0,1], and have unique outcome names.

- Full win at decimal d: r = d−1 before fees.
- Full loss: r = −1.
- Push/void with stake returned and no fees: r = 0.
- Other partial/cash-out outcomes: explicitly specify returned gross stake and fees, so r = gross returned amount − 1 − fees per original unit.
- Dead-heat winning stake fraction f: r = f*d − 1 before commission. This applies only when the actual rules split stake that way.

`net_win_per_unit` offers explicit isolated-entry commission bases. Default `net_entry` deducts commission only from positive net entry winnings: r_net = r − max(r,0)*c. `winning_fraction` deducts f*(d−1)*c, for a contract whose fee basis explicitly uses that winning fraction. Neither computes exchange commission across a portfolio/market. Such charges require actual market-level netting and allocation; use verified fees in the ledger rather than inferring them.

Binary break-even probability for net-win r_w > 0 and net-loss r_l < 0 is −r_l/(r_w−r_l); without fees this is 1/d. With pushes, partial outcomes or dead heats, a single binary break-even probability is generally undefined and returned as `None` (JSON null), not NaN. The interface has no model-derived minimum price because no evaluated distribution supports it.

## Sensitivity and uncertainty

Provided lower/upper bounds must contain each point probability and a coherent vector summing to one. Linear EV extrema allocate remaining mass to the smallest/largest net return within those bounds. These are deterministic sensitivity ranges **conditional on supplied bounds**, not empirical confidence intervals, calibration, or proof of uncertainty quality.

No fitted probability, participation distribution, calibrated uncertainty or EV is assigned on the board. No alternate-line probability interpolation, independent-leg multiplication or same-game joint probability is implemented. A future evaluated model must supply the full relevant outcome distribution, opportunity/participation context, horizon and joint dependence before these markets can qualify.

## Matching and freshness

A board contract uses sport, league, namespaced event ID, exact market key/family, participant, selection, exact textual point, segment/rules and pregame/live scope. Book identity is normalized for duplicate/multi-vendor counting; vendor disagreement at the same time does not count as multiple books. Opaque event and rule IDs are case-sensitive. Cross-provider participant/event and rule maps are not inferred from names.

Quote histories are immutable and content hashed. Later open/suspended/closed/unknown snapshots supersede earlier same-contract book prices. Missing child timestamps, conflicting latest prices/status, stale quotes, pregame events that started, unknown provenance or rules are explained as exclusions. Unknown account availability is never presented as executable availability.

Defaults: pregame quote age 300 s; live quote/state age 15 s; live alignment and maximum reported latency 5 s. These are configurable per user in Freshness, not measured provider guarantees. Missing timestamps/latency and changed/missing state IDs still fail closed. Evaluation occurs on board retrieval, with no scheduler or active feed. An expiry timestamp is the quote-age boundary, not a promise that event state or price will stay valid until then.

## Prediction evaluation

The UI/API accepts a complete supplied universe of binary historical prediction rows. It partitions chronologically using training/validation cutoffs, checks input/price availability at prediction, rejects outcomes already known then, prevents the same event spanning partitions, checks optional fitted-artifact times and ensures fitting/selection labels were available at cutoffs. Optional test model-selection times cannot extend into test data.

Metrics: sample size, Brier score, clipped log loss, ten calibration bins, baseline equivalents and held-out sport/market/season breakdowns. Returns are descriptive only for selected, executable rows with actual execution price, timestamp, price availability window, quote observation time, positive stake and explicit fees. Prediction odds are not substituted for execution odds. Unknown limits/fills, omitted candidates, false provenance or undocumented settlement assumptions cannot be inferred or verified from supplied rows.

No training pipeline, historical dataset, model registry/promotion gate, clustered uncertainty, multiple-search correction, prospective held-out manifest or profitability result exists. The audit must not be presented as model validation completion. Software tests use synthetic probabilities solely to verify formulas.

## Closing-line value

`closing_line_value` requires identical sport, league, event, market key, participant, selection, exact line, period, rules and book, with a sourced observation after placement and no later than start. Method: placed decimal / comparable closing decimal − 1. Changed-line conversion is rejected. The caller must verify that it actually selected the last comparable closing offer. No closing feed or automatic/UI CLV is available.

## Accounting

Gross payout includes returned stake. Confirmed wager P/L = payout − original stake − fees. Confirmed ROI = total confirmed P/L / total confirmed settled stakes; empty denominator yields unavailable. Currencies and proposed/paper/actual modes are never combined. Provisional results consume open exposure. Deposit/withdrawal/bonus cash flows are excluded. Corrected settlements replace the current result with a higher revision, while both versions remain in audit history.
