"""Rule-based audit tests reproduced from the Fraudit assignment."""
import pandas as pd

HIGH_VALUE = 10_000_000  # KRW; strict ">" reproduces the assignment's reported 1,128 lines


def load(path='data/journal_entries.csv'):
    df = pd.read_csv(path, encoding='utf-8-sig')
    df['증빙일자'] = pd.to_datetime(df['증빙일자'])
    df['전표일자'] = pd.to_datetime(df['전표일자'])
    df['amount'] = df[['차변금액', '대변금액']].abs().max(axis=1)
    df['delay'] = (df['전표일자'] - df['증빙일자']).dt.days  # signed: posting - evidence
    return df


def apply_rules(df, delay_days=7, high=HIGH_VALUE):
    df['R_delay'] = df['delay'] >= delay_days
    df['R_neg'] = (df['차변금액'] < 0) | (df['대변금액'] < 0)
    df['R_high'] = (df['차변금액'] > high) | (df['대변금액'] > high)
    df['R_any'] = df[['R_delay', 'R_neg', 'R_high']].any(axis=1)
    return df


if __name__ == '__main__':
    df = apply_rules(load())
    print('Flagged lines per rule:\n', df[['R_delay', 'R_neg', 'R_high', 'R_any']].sum(), sep='')

    at_threshold = ((df['차변금액'] == HIGH_VALUE) | (df['대변금액'] == HIGH_VALUE)).sum()
    print('lines exactly at 10M (counted only under ">="):', at_threshold)

    sets = df.groupby(['전표일자', '전표번호'])[['차변금액', '대변금액']].sum()
    print('voucher sets:', len(sets), '| debit != credit:', (sets['차변금액'] != sets['대변금액']).sum())

    print('posting before evidence date:', (df['delay'] < 0).sum(),
          '| by more than 30 days:', (df['delay'] < -30).sum())
    print('accounts / preparers / departments:',
          df['계정과목'].nunique(), df['전표생성자ID'].nunique(), df['전표생성자부서'].nunique())
