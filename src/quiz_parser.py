"""
src/quiz_parser.py

Parses raw Google Forms quiz-score CSV exports into a clean,
standardized format we can merge across multiple quiz days.

Real Google Forms quiz exports are messy:
- "Total score" comes as text like "15.00 / 25" (score AND max combined)
- Some files have a "Username" column (Google account email), others don't
- The "Email" column is student-typed -> inconsistent casing/typos
- Dozens of per-question columns we don't need for grading
- File naming has no fixed standard (we infer quiz number + date from filename)

This module only extracts what we need: who took the quiz, when,
and what they scored -- nothing else.
"""

import pandas as pd
import re
from pathlib import Path


def extract_quiz_info_from_filename(filepath: str) -> dict:
    """
    Pulls quiz number, module name, and date out of the filename.

    Expected naming convention:
        Quiz<N>_<Module_Name>_<DD>_<MM>_<YY>.csv

    Example:
        'Quiz1_AI_Fundamentals_15_6_26.csv'
            -> quiz_id='Quiz1', module='AI Fundamentals', date='2026-06-15'
        'Quiz3_Python_DataStructures_17_6_26.csv'
            -> quiz_id='Quiz3', module='Python DataStructures', date='2026-06-17'

    Falls back gracefully (module='Unspecified') if the filename doesn't
    follow the convention, so the pipeline never crashes on an unexpected
    naming style -- it just flags it for manual review later.
    """
    filename = Path(filepath).stem  # drops .csv

    # find a "Quiz" + number anywhere in the name (handles "Quiz1" and "Quiz_3")
    quiz_match = re.search(r'[Qq]uiz[_\s]*(\d+)', filename)
    quiz_id = f"Quiz{quiz_match.group(1)}" if quiz_match else None

    # find a date pattern like 15_6_26 or 17_6_26 (day_month_year, 2-digit year)
    date_match = re.search(r'(\d{1,2})_(\d{1,2})_(\d{2,4})', filename)
    quiz_date = None
    if date_match:
        day, month, year = date_match.groups()
        year = f"20{year}" if len(year) == 2 else year
        quiz_date = f"{year}-{int(month):02d}-{int(day):02d}"

    # module name = everything BETWEEN the quiz number and the date
    module = None
    if quiz_match and date_match:
        start = quiz_match.end()
        end = date_match.start()
        module_raw = filename[start:end].strip('_').strip()
        if module_raw:
            module = module_raw.replace('_', ' ')

    return {
        'quiz_id': quiz_id or filename,
        'module': module or 'Unspecified',
        'quiz_date': quiz_date,
        'source_file': filename
    }


def clean_email(email: str) -> str:
    """
    Normalizes student-typed emails: lowercase + strip whitespace.
    This is critical -- 'MOHITbtech23-27@liet.in' and
    'mohitbtech23-27@liet.in' must be treated as the same student.
    """
    if pd.isna(email):
        return None
    return str(email).strip().lower()


def clean_name(name: str) -> str:
    """Normalizes student names: strip whitespace, title-case for display."""
    if pd.isna(name):
        return None
    return str(name).strip()


def parse_total_score(score_text: str) -> tuple:
    """
    Splits Google Forms' combined score string into two numbers.
    '15.00 / 25' -> (15.0, 25.0)
    Returns (None, None) if the format is unexpected, rather than crashing,
    so one malformed row doesn't take down the whole pipeline.
    """
    if pd.isna(score_text):
        return (None, None)
    match = re.match(r'([\d.]+)\s*/\s*([\d.]+)', str(score_text))
    if match:
        return (float(match.group(1)), float(match.group(2)))
    return (None, None)


def parse_quiz_file(filepath: str) -> pd.DataFrame:
    """
    Reads one raw Google Forms quiz CSV and returns a clean DataFrame with:
    email, name, score, max_score, percentage, quiz_id, quiz_date, timestamp

    This is the ONLY function the rest of the pipeline needs to call.
    """
    raw = pd.read_csv(filepath)
    info = extract_quiz_info_from_filename(filepath)

    # Some quiz exports use 'Email' for the student-typed answer,
    # but if a 'Username' column exists, that's Google's authenticated
    # account email -- more reliable. Prefer it when available.
    if 'Username' in raw.columns:
        email_col = 'Username'
    elif 'Email' in raw.columns:
        email_col = 'Email'
    else:
        raise ValueError(
            f"No email/username column found in {filepath}. "
            f"Available columns: {list(raw.columns)[:5]}..."
        )

    clean = pd.DataFrame()
    clean['email'] = raw[email_col].apply(clean_email)
    clean['name'] = raw['Name'].apply(clean_name)

    scores = raw['Total score'].apply(parse_total_score)
    clean['score'] = scores.apply(lambda x: x[0])
    clean['max_score'] = scores.apply(lambda x: x[1])
    clean['percentage'] = (clean['score'] / clean['max_score'] * 100).round(2)

    clean['quiz_id'] = info['quiz_id']
    clean['module'] = info['module']
    clean['quiz_date'] = info['quiz_date']
    clean['timestamp'] = raw['Timestamp'] if 'Timestamp' in raw.columns else None

    # Drop rows with no email -- can't attribute a score to nobody
    before = len(clean)
    clean = clean.dropna(subset=['email'])
    dropped = before - len(clean)
    if dropped > 0:
        print(f"  Warning: dropped {dropped} row(s) with missing email in {info['source_file']}")

    return clean


def parse_all_quiz_files(folder: str = 'data/raw/') -> pd.DataFrame:
    """
    Parses every CSV in the raw data folder and stacks them into one
    long-format DataFrame: one row per (student, quiz).
    """
    folder_path = Path(folder)
    csv_files = sorted(folder_path.glob('*.csv'))

    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {folder}")

    all_quizzes = []
    print(f"Found {len(csv_files)} quiz file(s):")
    for f in csv_files:
        print(f" - Parsing {f.name}...")
        df = parse_quiz_file(str(f))
        print(f"   -> {df['quiz_id'].iloc[0]} | module: {df['module'].iloc[0]} | {len(df)} students | date: {df['quiz_date'].iloc[0]}")
        all_quizzes.append(df)

    combined = pd.concat(all_quizzes, ignore_index=True)

    # Handle duplicate attempts: if a student appears twice in the SAME quiz
    # (e.g. submitted the form twice), keep their best score.
    combined = combined.sort_values('percentage', ascending=False)
    combined = combined.drop_duplicates(subset=['email', 'quiz_id'], keep='first')

    return combined.reset_index(drop=True)


if __name__ == '__main__':
    result = parse_all_quiz_files('data/raw/')
    print("\n--- Combined long-format data (first 10 rows) ---")
    print(result.head(10).to_string())
    print(f"\nTotal rows: {len(result)}")
    print(f"Unique students: {result['email'].nunique()}")
    print(f"Quizzes found: {result['quiz_id'].unique().tolist()}")
