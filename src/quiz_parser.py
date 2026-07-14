import pandas as pd
import re
from pathlib import Path


def extract_quiz_info_from_filename(filepath: str) -> dict:
    filename = Path(filepath).stem
    quiz_match = re.search(r'[Qq]uiz[_\s]*(\d+)', filename)
    quiz_id = f"Quiz{quiz_match.group(1)}" if quiz_match else None
    date_match = re.search(r'(\d{1,2})_(\d{1,2})_(\d{2,4})', filename)
    quiz_date = None
    if date_match:
        day, month, year = date_match.groups()
        year = f"20{year}" if len(year) == 2 else year
        quiz_date = f"{year}-{int(month):02d}-{int(day):02d}"
    module = None
    if quiz_match and date_match:
        start = quiz_match.end()
        end = date_match.start()
        module_raw = filename[start:end].strip('_').strip()
        if module_raw:
            module = module_raw.replace('_', ' ')
    return {'quiz_id': quiz_id or filename, 'module': module or 'Unspecified', 'quiz_date': quiz_date, 'source_file': filename}


def clean_email(email):
    if pd.isna(email): return None
    return str(email).strip().lower()

def clean_name(name):
    if pd.isna(name): return None
    return str(name).strip()

def parse_total_score(score_text):
    if pd.isna(score_text): return (None, None)
    match = re.match(r'([\d.]+)\s*/\s*([\d.]+)', str(score_text))
    if match: return (float(match.group(1)), float(match.group(2)))
    return (None, None)


def parse_quiz_file(filepath: str) -> pd.DataFrame:
    raw = pd.read_csv(filepath)
    info = extract_quiz_info_from_filename(filepath)
    if 'Username' in raw.columns:
        email_col = 'Username'
    elif 'Email' in raw.columns:
        email_col = 'Email'
    else:
        raise ValueError(f"No email column found in {filepath}")
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
    before = len(clean)
    clean = clean.dropna(subset=['email'])
    dropped = before - len(clean)
    if dropped > 0:
        print(f"  Warning: dropped {dropped} row(s) with missing email in {info['source_file']}")
    return clean


def parse_all_quiz_files(folder: str = 'data/raw/') -> pd.DataFrame:
    folder_path = Path(folder)
    csv_files = sorted(folder_path.glob('*.csv'))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {folder}")
    all_quizzes = []
    print(f"Found {len(csv_files)} quiz file(s):")
    for f in csv_files:
        print(f"  - Parsing {f.name}...")
        df = parse_quiz_file(str(f))
        print(f"    -> {df['quiz_id'].iloc[0]} | module: {df['module'].iloc[0]} | {len(df)} students | date: {df['quiz_date'].iloc[0]}")
        all_quizzes.append(df)
    combined = pd.concat(all_quizzes, ignore_index=True)
    combined = combined.sort_values('percentage', ascending=False)
    combined = combined.drop_duplicates(subset=['email', 'quiz_id'], keep='first')
    return combined.reset_index(drop=True)


if __name__ == '__main__':
    result = parse_all_quiz_files('data/raw/')
    print(f"\nTotal rows: {len(result)}")
    print(f"Unique students: {result['email'].nunique()}")
    print(f"Quizzes found: {sorted(result['quiz_id'].unique().tolist())}")
    print(f"Modules: {result['module'].unique().tolist()}")
