"""
src/roster.py

Solves the "same student, different email" problem.

Students sometimes use their institute email on one quiz and a personal
Gmail on another (confirmed in real data: Devashish Dobhal, Anushka Garg,
Aman Singh, Nilesh Sarkar, and Ritik all did this across Quiz1/Quiz3).
Pure email-based grouping would silently treat them as TWO different
students and produce wrong ranks/percentiles.

config/student_roster.csv is the single source of truth: each row lists
a canonical_email and every other email variant known to belong to that
same student. This module rewrites the 'email' column in the long-format
quiz data to always use the canonical email before any calculation runs.

This file is meant to be maintained by hand (the trainer/admin) --
new students are added automatically with their first-seen email as
canonical; you only need to edit this file when you discover a student
used two different emails.
"""

import pandas as pd
from pathlib import Path


def load_roster(roster_path: str = 'config/student_roster.csv') -> dict:
    """
    Loads the roster CSV and builds a flat lookup dict:
        {alternate_email: canonical_email, ...}

    Every email listed in 'known_emails' (comma-separated) maps to that
    row's canonical_email. If the roster file doesn't exist yet, returns
    an empty dict -- the pipeline still works, it just won't merge any
    cross-email duplicates (safe default, not a crash).
    """
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
    """
    Rewrites the 'email' column using the roster lookup, so every known
    variant collapses to one canonical email before grouping/ranking.

    Also fixes a follow-on problem: once emails are normalized, the same
    student can still appear with inconsistent name casing/spacing
    ('Aman Singh' vs 'aman singh' vs 'Aman singh' across quizzes -- all
    confirmed in real data). Grouping by (email, name) together would
    still split them. So after normalizing email, we also pick ONE
    display name per canonical email -- the most frequently used
    spelling -- and apply it everywhere.

    Reports how many rows were affected, so changes are visible rather
    than silent.
    """
    lookup = load_roster(roster_path)

    df = long_df.copy()
    original_emails = df['email'].copy()

    if lookup:
        df['email'] = df['email'].apply(lambda e: lookup.get(e, e))
        changed = (df['email'] != original_emails).sum()
        if changed > 0:
            print(f"  Roster applied: normalized {changed} row(s) to canonical emails.")

    # Pick the most common name spelling per email and apply it to every row
    name_mode = (
        df.groupby('email')['name']
        .agg(lambda names: names.value_counts().idxmax())
    )
    name_changed = (df['name'] != df['email'].map(name_mode)).sum()
    df['name'] = df['email'].map(name_mode)
    if name_changed > 0:
        print(f"  Name normalization: standardized {name_changed} row(s) to one consistent spelling per student.")

    return df


def find_unlisted_duplicates(long_df: pd.DataFrame, roster_path: str = 'config/student_roster.csv') -> pd.DataFrame:
    """
    Diagnostic helper: finds students with the SAME NAME but DIFFERENT
    emails that are NOT already covered by the roster. Run this whenever
    you add new quiz files, to catch new cross-email duplicates early
    instead of finding out from a wrong leaderboard.

    Returns a DataFrame of suspicious (name, email) groups for manual review.
    """
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
        print("These students have multiple emails NOT yet in the roster:")
        print(flagged.to_string(index=False))

    print("\n--- Applying roster ---")
    cleaned = apply_roster(long_df)
    print(f"Unique students before roster: {long_df['email'].nunique()}")
    print(f"Unique students after roster:  {cleaned['email'].nunique()}")
