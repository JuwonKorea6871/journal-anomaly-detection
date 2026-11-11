# Journal Entry Anomaly Detection: Rule-Based Audit Tests vs. Isolation Forest

Course project from *Financial Big Data Analytics* (Catholic University of Korea, 2026), extended on my own.
The original assignment applied three audit rules in Fraudit. This repo reproduces those rules in Python
and compares them with an unsupervised model (Isolation Forest) on the same ledger, using the same number of flags.

> **요약** — 회계 전표 9,721건에 대해 Fraudit 감사 규칙 3개를 Python으로 재현하고, 같은 개수(2,826건)를
> Isolation Forest로 뽑아 비교했습니다. 두 방법이 겹치는 비율은 Jaccard 0.36에 그쳤습니다. 규칙은 "금액이 큰 것"을,
> 모델은 "그 계정 기준으로 이례적인 것"(주말 기표, 드문 작성자–계정 조합 등)을 주로 잡았습니다.

## Key findings
- **The two methods largely disagree.** At the same flag budget, only 1,485 of 2,826 lines overlap (Jaccard 0.36).
- **Fixed thresholds miss context.** The high-value rule has the lowest agreement (38%): many of its flags are large
  amounts in accounts where large amounts are routine, such as deposits.
- **The model surfaces patterns no rule checks**: weekend postings, rare preparer–account pairs, amounts far from the
  account's usual range, and round-million amounts.
- **Reproduction found two gaps in the assignment**: a threshold mismatch (`≥` vs `>`) and 63% of lines posted
  *before* their evidence date, which no rule checks.

## Data
- 9,721 journal entry lines / 574 voucher sets (date + voucher no.), 185 accounts, 78 preparers, 22 departments.
- The source is a Fraudit `.tbl` table (gzip + a stream of Python 2 pickles). `src/parse_tbl.py` reads it with a
  **restricted unpickler** that allows only whitelisted types, so no arbitrary code can run.
- The course dataset is not included in this repo, and neither is any line-level output.

## 1. Rule-based tests (reproduced from the Fraudit assignment)
| Rule | Definition | Flagged lines |
|---|---|---|
| Posting delay | posting date − evidence date ≥ 7 days | 375 |
| Negative amount | debit < 0 or credit < 0 | 1,349 |
| High value | debit or credit > 10,000,000 KRW | 1,128 |
| Any of the above | | **2,826** |
| Debit ≠ credit per voucher set | | 0 sets |

Found while reproducing:
- The assignment text says "≥ 10M KRW", but the reported 1,128 only matches "> 10M".
  22 lines sit exactly at 10M (1,150 under "≥").
- 6,132 lines (63%) have a posting date *earlier* than the evidence date (121 by more than 30 days).
  None of the three rules looks at this direction.

## 2. Isolation Forest
Each feature describes how unusual an entry is **compared with similar entries**, not just how large a raw value is.

| Feature | Meaning |
|---|---|
| `log_amount` | log(1 + amount) |
| `amount_vs_account` | robust z-score of log amount within the same account (median / IQR) |
| `delay_days` | signed posting − evidence date |
| `weekend` | posted on Sat/Sun |
| `negative` | negative debit/credit |
| `account_freq` | log frequency of the account |
| `preparer_account_freq` | how often this preparer posts to this account (rarity) |
| `dept_account_freq` | how often this department posts to this account |
| `round_million` | amount is a multiple of 1M KRW |

- 500 trees; anomaly scores averaged over 10 random seeds.
- Seed stability: mean Spearman ρ = 0.994 between seeds; top-K overlap = 96.8%.
- For a fair comparison, the forest flags its K = 2,826 highest-scoring lines, the same number the rules flag.

## 3. Results (same flag budget, K = 2,826)
| | Lines |
|---|---|
| Flagged by both | 1,485 |
| Rules only | 1,341 |
| Isolation Forest only | 1,341 |
| Jaccard | 0.36 |

"Rules only" and "forest only" are equal by construction, because both methods flag K lines.

Share of each rule's flags that the forest also catches: delay 67%, negative 61%, high-value 38%.
Of the forest's 200 highest-scoring lines, 69.5% are also caught by at least one rule,
so agreement is much higher at the top of the ranking than across all K lines.

**What the rules flag but the forest treats as normal.** Mostly high-value lines in accounts where large amounts are
routine, such as ordinary/checking deposits and department-store receivables.
A fixed KRW threshold cannot tell "large" from "large for this account".

**What the forest flags but the rules miss** (1,341 lines, share vs. all lines):
| Pattern | Forest-only | All lines |
|---|---|---|
| Weekend posting | 44.1% | 8.9% |
| Rare preparer–account pair (≤ 2 occurrences) | 18.7% | 4.6% |
| Amount far from the account's range (\|robust z\| > 3) | 9.5% | 1.7% |
| Round-million amount | 6.6% | 1.5% |

Examples near the top of the ranking: a negative executive-salary line (−11.2M KRW), a staff housing-loan entry,
and round-amount sponsorship/promotion entries.

## Limitations and next steps
- There are no fraud labels, so overlap measures how much the methods **agree**, not which one is more accurate.
- Results depend on the chosen features. Next steps: feature ablation, scoring at the voucher-set level instead of
  the line level, and adding a rule for postings dated before their evidence.

## Repository layout
```
src/parse_tbl.py   Fraudit .tbl -> column names + value stream (restricted unpickler)
src/to_csv.py      value stream -> data/journal_entries.csv
src/rules.py       three audit rules + data checks
src/iforest.py     Isolation Forest, comparison, profiling of disagreements
results/results.json   aggregate results reported above
```

## Run
Python 3.10+. Place the course file at `data/je.tbl` (not included), then from the repo root:
```
pip install -r requirements.txt
python -I src/parse_tbl.py data/je.tbl data/je
python -I src/to_csv.py
python -I src/rules.py
python -I src/iforest.py
```
`iforest.py` writes `results/results.json` and a line-level `data/scored.csv` (git-ignored).
