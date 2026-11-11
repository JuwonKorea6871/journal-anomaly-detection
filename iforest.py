"""Isolation Forest vs. rule-based flags on 9,721 journal entry lines, at the same flag budget."""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import IsolationForest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rules import apply_rules, load  # noqa: E402

N_SEEDS, N_TREES = 10, 500

df = apply_rules(load())

# ---- features: each one says how unusual an entry is relative to its context
la = np.log1p(df['amount'])
g = la.groupby(df['계정과목'])
iqr = (g.transform(lambda s: s.quantile(.75)) - g.transform(lambda s: s.quantile(.25))).replace(0, np.nan)
X = pd.DataFrame({
    'log_amount': la,
    'amount_vs_account': ((la - g.transform('median')) / iqr).fillna(0).clip(-10, 10),  # robust z within account
    'delay_days': df['delay'],
    'weekend': (df['전표일자'].dt.dayofweek >= 5).astype(int),
    'negative': df['R_neg'].astype(int),
    'account_freq': np.log(df.groupby('계정과목')['계정과목'].transform('size')),
    'preparer_account_freq': np.log(df.groupby(['전표생성자ID', '계정과목'])['계정과목'].transform('size')),
    'dept_account_freq': np.log(df.groupby(['전표생성자부서', '계정과목'])['계정과목'].transform('size')),
    'round_million': ((df['amount'] % 1_000_000 == 0) & (df['amount'] >= 1_000_000)).astype(int),
})

# ---- fit: average anomaly scores over seeds; flag as many lines as the rules do
K = int(df['R_any'].sum())


def score(seed):
    model = IsolationForest(n_estimators=N_TREES, random_state=seed).fit(X)
    return -model.score_samples(X)  # higher = more anomalous


scores = np.array([score(s) for s in range(N_SEEDS)])
df['if_score'] = scores.mean(0)
df['IF_top'] = df['if_score'].rank(ascending=False, method='first') <= K

tops = [set(np.argsort(-s)[:K]) for s in scores]
stab_rho = np.mean([spearmanr(scores[0], scores[i])[0] for i in range(1, N_SEEDS)])
stab_overlap = np.mean([len(tops[0] & tops[i]) / K for i in range(1, N_SEEDS)])

# ---- compare
R, I = df['R_any'], df['IF_top']
top200 = df['if_score'].rank(ascending=False, method='first') <= 200
res = {
    'n': len(df),
    'K_flagged_each': K,
    'both': int((R & I).sum()),
    'rules_only': int((R & ~I).sum()),
    'if_only': int((~R & I).sum()),
    'jaccard': round((R & I).sum() / (R | I).sum(), 3),
    'share_of_IF_flags_also_flagged_by_rules': round((R & I).sum() / K, 3),
    'share_of_each_rule_caught_by_IF': {r: round((df[r] & I).sum() / df[r].sum(), 3)
                                        for r in ['R_delay', 'R_neg', 'R_high']},
    'seed_stability_spearman': round(stab_rho, 4),
    'seed_stability_topK_overlap': round(stab_overlap, 3),
    'top200_share_flagged_by_rules': round((top200 & R).sum() / 200, 3),
}
print(json.dumps(res, ensure_ascii=False, indent=1))

# ---- what does the forest flag that the rules miss?
io = df[~R & I].join(X[['amount_vs_account', 'preparer_account_freq', 'weekend', 'round_million']])
print(f'\nIF-only lines (n={len(io)}): share vs all lines')
print('  weekend posting            ', round(io.weekend.mean(), 3), round(X.weekend.mean(), 3))
print('  rare preparer-account (<=2)', round((np.exp(io.preparer_account_freq) <= 2.01).mean(), 3),
      round((np.exp(X.preparer_account_freq) <= 2.01).mean(), 3))
print('  |amount_vs_account| > 3    ', round((io.amount_vs_account.abs() > 3).mean(), 3),
      round((X.amount_vs_account.abs() > 3).mean(), 3))
print('  round million              ', round(io.round_million.mean(), 3), round(X.round_million.mean(), 3))
print('  posting before evidence    ', round((io.delay < 0).mean(), 3), round((df.delay < 0).mean(), 3))
print(io['계정과목'].value_counts().head(8))

# ---- what do the rules flag that the forest treats as normal?
ro = df[R & ~I]
print('\nrules-only lines by rule:', ro[['R_delay', 'R_neg', 'R_high']].sum().to_dict())
print('  high-value, top accounts:', ro[ro.R_high]['계정과목'].value_counts().head(5).to_dict())
print('  negative, top accounts:  ', ro[ro.R_neg]['계정과목'].value_counts().head(5).to_dict())

# ---- outputs: aggregate results are committed; line-level scores stay in data/ (not committed)
cols = ['전표번호', '전표일자', '증빙일자', 'delay', '전표생성자부서', '전표생성자ID', '계정과목',
        '차변금액', '대변금액', 'if_score', 'R_delay', 'R_neg', 'R_high', 'R_any', 'IF_top']
df.sort_values('if_score', ascending=False)[cols].to_csv('data/scored.csv', index=False, encoding='utf-8-sig')
os.makedirs('results', exist_ok=True)
with open('results/results.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
