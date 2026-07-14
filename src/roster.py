import pandas as pd
from pathlib import Path


def load_roster(roster_path: str = 'config/student_roster.csv') -> dict:
    path = Path(roster_path)
    if not path.exists():
        print(f"  Note: no roster file found at {roster_path} -- skipping email normalization.")
        return {}
    roster_df = pd.read_csv(path)
    lookup = {}
    for _, row in roster_df.iterrows():
        canonical = str(row['canonical_email']).strip().lower()
        variants = str(row['known_emails']).split(',')
        for v in variants:
            v_clean = v.strip().lower()
            if v_clean:
                lookup[v_clean] = canonical
    return lookup


def apply_roster(long_df: pd.DataFrame, roster_path: str = 'config/student_roster.csv') -> pd.DataFrame:
    lookup = load_roster(roster_path)
    df = long_df.copy()
    original_emails = df['email'].copy()
    if lookup:
        df['email'] = df['email'].apply(lambda e: lookup.get(e, e))
        changed = (df['email'] != original_emails).sum()
        if changed > 0:
            print(f"  Roster applied: normalized {changed} row(s) to canonical emails.")
    name_mode = df.groupby('email')['name'].agg(lambda names: names.value_counts().idxmax())
    name_changed = (df['name'] != df['email'].map(name_mode)).sum()
    df['name'] = df['email'].map(name_mode)
    if name_changed > 0:
        print(f"  Name normalization: standardized {name_changed} row(s).")
    return df


def find_unlisted_duplicates(long_df: pd.DataFrame, roster_path: str = 'config/student_roster.csv') -> pd.DataFrame:
    lookup = load_roster(roster_path)
    df = long_df.copy()
    df['email_normalized'] = df['email'].apply(lambda e: lookup.get(e, e))
    df['name_normalized'] = df['name'].str.strip().str.lower()
    pairs = df[['name_normalized', 'email_normalized']].drop_duplicates()
    name_email_counts = pairs.groupby('name_normalized')['email_normalized'].nunique()
    suspicious_names = name_email_counts[name_email_counts > 1].index
    if len(suspicious_names) == 0:
        return pd.DataFrame(columns=['name', 'email'])
    flagged = df[df['name_normalized'].isin(suspicious_names)][['name', 'email']].drop_duplicates()
    return flagged.sort_values('name').reset_index(drop=True)


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from src.quiz_parser import parse_all_quiz_files
    long_df = parse_all_quiz_files('data/raw/')
    print("\n--- Checking for unlisted duplicate students ---")
    flagged = find_unlisted_duplicates(long_df)
    if flagged.empty:
        print("None found -- roster is up to date.")
    else:
        print(flagged.to_string(index=False))
    print("\n--- Applying roster ---")
    cleaned = apply_roster(long_df)
    print(f"Unique students before: {long_df['email'].nunique()}")
    print(f"Unique students after:  {cleaned['email'].nunique()}")
