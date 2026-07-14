import pandas as pd
import numpy as np

GRADE_BINS = [0, 40, 55, 70, 85, 100.0001]
GRADE_LABELS = ['F', 'C', 'B', 'A', 'A+']


def calculate_module_performance(long_df: pd.DataFrame) -> pd.DataFrame:
    module_perf = (
        long_df.groupby(['email', 'module'])
        .agg(name=('name', 'first'), marks_scored=('score', 'sum'),
             marks_possible=('max_score', 'sum'), quizzes_in_module=('quiz_id', 'nunique'))
        .reset_index()
    )
    module_perf['module_percentage'] = (module_perf['marks_scored'] / module_perf['marks_possible'] * 100).round(2)
    module_perf['module_percentile'] = (
        module_perf.groupby('module')['module_percentage'].rank(pct=True) * 100
    ).round(1)
    return module_perf


def calculate_cumulative_performance(long_df: pd.DataFrame) -> pd.DataFrame:
    cumulative = (
        long_df.groupby('email')
        .agg(name=('name', 'first'), quizzes_attempted=('quiz_id', 'nunique'),
             total_marks_scored=('score', 'sum'), total_marks_possible=('max_score', 'sum'),
             avg_percentage=('percentage', 'mean'))
        .reset_index()
    )
    cumulative['avg_percentage'] = cumulative['avg_percentage'].round(2)
    cumulative['cumulative_percentage'] = (
        cumulative['total_marks_scored'] / cumulative['total_marks_possible'] * 100
    ).round(2)
    return cumulative


def add_final_percentile_rank_grade(cumulative_df: pd.DataFrame) -> pd.DataFrame:
    df = cumulative_df.copy()
    df['final_percentile'] = (df['avg_percentage'].rank(pct=True) * 100).round(1)
    df['rank'] = df['avg_percentage'].rank(ascending=False, method='min').astype(int)
    df['grade'] = pd.cut(df['avg_percentage'], bins=GRADE_BINS, labels=GRADE_LABELS)
    return df.sort_values('rank').reset_index(drop=True)


def build_master_performance(long_df: pd.DataFrame) -> dict:
    cumulative = calculate_cumulative_performance(long_df)
    master = add_final_percentile_rank_grade(cumulative)
    module = calculate_module_performance(long_df)
    return {'master': master, 'module': module, 'daily': long_df}


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from src.quiz_parser import parse_all_quiz_files
    from src.roster import apply_roster, find_unlisted_duplicates
    long_df = parse_all_quiz_files('data/raw/')
    flagged = find_unlisted_duplicates(long_df)
    if not flagged.empty:
        print("WARNING: possible unlisted duplicates:\n", flagged.to_string(index=False))
    long_df = apply_roster(long_df)
    results = build_master_performance(long_df)
    print("\n=== MASTER PERFORMANCE ===")
    print(results['master'][['rank','name','avg_percentage','grade']].head(10).to_string(index=False))
    print(f"\nTotal students: {len(results['master'])}")
    print(f"Grade distribution:\n{results['master']['grade'].value_counts()}")
