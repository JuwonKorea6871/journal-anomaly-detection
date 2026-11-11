"""Reshape the flat value stream from parse_tbl.py into data/journal_entries.csv.

The stream starts with the row count, followed by the cells row by row.
"""
import json
import pickle

import pandas as pd

with open('data/je.vals.pkl', 'rb') as f:   # our own file written by parse_tbl.py
    vals = pickle.load(f)
with open('data/je.cols.json', encoding='utf-8') as f:
    cols = json.load(f)[0]

n_rows, n_cols = vals[0], len(cols)
body = vals[1:1 + n_rows * n_cols]
df = pd.DataFrame([body[i * n_cols:(i + 1) * n_cols] for i in range(n_rows)], columns=cols)
df.to_csv('data/journal_entries.csv', index=False, encoding='utf-8-sig')
print(df.shape)
print(df.head())
