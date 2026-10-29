# R1 legacy reconciliation: v1 → L1, one correction per step

Steps (cumulative, order fixed before any result, D1.4; attribution is order-dependent): **S0** v1 as committed (own Yahoo/Cboe data, own accounting); reproduced; **S1** t+1 execution; **S2** cash at bills + financing (bill MMY + 25 bp on borrowed notional); **S3** charter costs (3/2 bp per side) on true traded turnover with drift; **S4** excess-return Sharpe + standard Sortino (metric only; returns identical to S3); **S5** no shorts: negative v1 weights floored at 0 (to cash); **S6** VIX -> realised-vol proxy (v1's 20-day convention) on v1's local SPY; **S7** permitted prices: KF Hi 20, GSW 25y, H.15, KF calendar; realised vol from Hi 20  (= L1).

Metrics: S0–S3 use v1's own definitions (Sharpe without the risk-free rate, v1's Sortino); from S4 on, Sharpe is
on returns over H.15 bills and Sortino uses the standard downside deviation vs 0. Turnover = annualised one-way
traded Σ|Δw| (S0–S2 without drift, S3+ with drift; v1's own reported figure, signal changes only, was 18.73× in test). Cost, cash and financing are mean contributions per year.
Windows: v1's train 2005–14 and validation 2015–19 (in-sample: v1 chose its parameters there); test 2020–25 =
**seen by owner in v1, disclosed**. S0–S6 run on v1's local Yahoo/Cboe file (statistics only; the file is never
committed); S7 runs on permitted data: SPY proxy (KF Hi 20), TLT proxy, QA vs TLT corr 0.99 / TE 2.06%/yr, H.15 bills.
Produced by `make reconcile` (scripts/reconcile.py); figures in reports/figures/R1/.

| Step | Window | CAGR | Vol | Sharpe | Sortino | Max DD | Turnover/yr | Cost/yr | Cash/yr | Fin./yr | Gross |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S0 | train | 7.7% | 16.2% | 0.54 | 0.64 | -39.4% | 28.0× | 1.4% | 0.0% | 0.0% | 1.19 |
| S0 | validation | 11.5% | 15.8% | 0.77 | 0.89 | -19.2% | 36.2× | 1.8% | 0.0% | 0.0% | 1.43 |
| S0 | test | 16.3% | 16.4% | 1.00 | 1.29 | -17.7% | 26.6× | 1.3% | 0.0% | 0.0% | 1.10 |
| S1 | train | 9.4% | 16.2% | 0.64 | 0.78 | -36.3% | 28.0× | 1.4% | 0.0% | 0.0% | 1.18 |
| S1 | validation | 8.2% | 16.4% | 0.56 | 0.58 | -21.0% | 36.2× | 1.8% | 0.0% | 0.0% | 1.43 |
| S1 | test | 14.0% | 16.7% | 0.87 | 1.09 | -20.5% | 26.6× | 1.3% | 0.0% | 0.0% | 1.10 |
| S2 | train | 8.7% | 16.2% | 0.60 | 0.72 | -35.9% | 28.0× | 1.4% | 0.1% | 0.7% | 1.18 |
| S2 | validation | 7.6% | 16.4% | 0.53 | 0.54 | -21.0% | 36.2× | 1.8% | 0.1% | 0.7% | 1.43 |
| S2 | test | 13.4% | 16.7% | 0.84 | 1.04 | -20.6% | 26.6× | 1.3% | 0.3% | 0.8% | 1.10 |
| S3 | train | 9.4% | 16.2% | 0.64 | 0.78 | -35.2% | 28.2× | 0.8% | 0.1% | 0.7% | 1.18 |
| S3 | validation | 8.5% | 16.4% | 0.58 | 0.60 | -20.9% | 36.6× | 1.0% | 0.1% | 0.7% | 1.43 |
| S3 | test | 14.1% | 16.7% | 0.88 | 1.09 | -20.4% | 26.7× | 0.7% | 0.3% | 0.8% | 1.10 |
| S4 | train | 9.4% | 16.2% | 0.55 | 0.76 | -35.2% | 28.2× | 0.8% | 0.1% | 0.7% | 1.18 |
| S4 | validation | 8.5% | 16.4% | 0.51 | 0.67 | -20.9% | 36.6× | 1.0% | 0.1% | 0.7% | 1.43 |
| S4 | test | 14.1% | 16.7% | 0.71 | 0.96 | -20.4% | 26.7× | 0.7% | 0.3% | 0.8% | 1.10 |
| S5 | train | 9.9% | 16.0% | 0.58 | 0.80 | -35.4% | 23.9× | 0.7% | 0.1% | 0.7% | 1.17 |
| S5 | validation | 9.5% | 16.4% | 0.57 | 0.75 | -20.9% | 31.6× | 0.9% | 0.1% | 0.7% | 1.42 |
| S5 | test | 14.0% | 16.7% | 0.70 | 0.95 | -20.3% | 23.6× | 0.7% | 0.3% | 0.8% | 1.10 |
| S6 | train | 10.0% | 16.0% | 0.58 | 0.81 | -35.3% | 24.2× | 0.7% | 0.1% | 0.7% | 1.17 |
| S6 | validation | 9.3% | 16.4% | 0.56 | 0.74 | -22.0% | 31.4× | 0.9% | 0.1% | 0.7% | 1.41 |
| S6 | test | 14.0% | 16.8% | 0.70 | 0.95 | -20.8% | 23.4× | 0.7% | 0.3% | 0.8% | 1.09 |
| S7 | train | 10.8% | 15.9% | 0.63 | 0.88 | -31.1% | 23.9× | 0.7% | 0.1% | 0.7% | 1.18 |
| S7 | validation | 8.5% | 16.4% | 0.52 | 0.68 | -23.3% | 31.0× | 0.9% | 0.1% | 0.6% | 1.39 |
| S7 | test | 15.5% | 16.7% | 0.78 | 1.06 | -19.8% | 19.7× | 0.6% | 0.3% | 0.7% | 1.06 |
