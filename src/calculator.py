"""
src/calculator.py

Takes the long-format quiz data (one row per student per quiz, from
quiz_parser.py) and computes everything the problem statement asks for:

  1. Module-wise performance   -> total marks & % per student per module
  2. Cumulative performance    -> overall % across ALL quizzes so far
  3. Module-wise percentile    -> relative standing WITHIN each module
  4. Final percentile          -> overall relative standing
  5. Rank                      -> 1, 2, 3... based on cumulative %
  6. Grade                     -> letter grade from cumulative %

Important real-world detail (confirmed from your actual data):
Only 11 of 54 students took BOTH quizzes; most took just one. So we
calculate each student's cumulative % as the AVERAGE OF THEIR OWN
percentages across whatever quizzes THEY attempted -- never penalizing
someone for a quiz that isn't in their record. A separate
'quizzes_attempted' column makes this transparent rather than hidden.
"""

import pandas as pd
import numpy as np


# Grade boundaries -- tweak these to match your institute's grading policy
GRADE_BINS = [0, 40, 55, 70, 85, 100.0001]
GRADE_LABELS = ['F', 'C', 'B', 'A', 'A+']


def calculate_module_performance(long_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each (student, module) pair, computes total marks scored,
    total possible marks, and percentage within that module.

    A student may have taken multiple quizzes within the same module
    (e.g. two quizzes both tagged 'Python Basics') -- those get summed.
    """
    module_perf = (
        long_df.groupby(['email', 'module'])
        .agg(
            name=('name', 'first'),
            marks_scored=('score', 'sum'),
            marks_possible=('max_score', 'sum'),
            quizzes_in_module=('quiz_id', 'nunique')
        )
        .reset_index()
    )
    module_perf['module_percentage'] = (
        module_perf['marks_scored'] / module_perf['marks_possible'] * 100
    ).round(2)

    # Module-wise percentile: relative standing among students who
    # took THAT module's quizzes (not all 54 students -- only ones
    # who actually attempted something in this module).
    module_perf['module_percentile'] = (
        module_perf.groupby('module')['module_percentage']
        .rank(pct=True) * 100
    ).round(1)

    return module_perf


def calculate_cumulative_performance(long_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each student, computes their overall cumulative performance
    across every quiz THEY attempted (not penalized for quizzes they
    haven't reached yet or skipped).

    Groups by 'email' alone (not (email, name)) -- after roster.py runs,
    email is the canonical identity and name is already standardized,
    but grouping on email only is the robust choice regardless.
    """
    cumulative = (
        long_df.groupby('email')
        .agg(
            name=('name', 'first'),
            quizzes_attempted=('quiz_id', 'nunique'),
            total_marks_scored=('score', 'sum'),
            total_marks_possible=('max_score', 'sum'),
            avg_percentage=('percentage', 'mean'),   # avg of per-quiz %
        )
        .reset_index()
    )
    cumulative['avg_percentage'] = cumulative['avg_percentage'].round(2)
    cumulative['cumulative_percentage'] = (
        cumulative['total_marks_scored'] / cumulative['total_marks_possible'] * 100
    ).round(2)

    return cumulative


def add_final_percentile_rank_grade(cumulative_df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds final percentile, rank, and letter grade based on cumulative
    percentage. Uses avg_percentage (average of per-quiz %) as the
    primary metric -- this is fairer than total marks when quizzes
    have different max scores (Quiz1=15, Quiz3=25 in your real data).
    """
    df = cumulative_df.copy()

    df['final_percentile'] = (df['avg_percentage'].rank(pct=True) * 100).round(1)
    df['rank'] = df['avg_percentage'].rank(ascending=False, method='min').astype(int)
    df['grade'] = pd.cut(df['avg_percentage'], bins=GRADE_BINS, labels=GRADE_LABELS)

    df = df.sort_values('rank').reset_index(drop=True)
    return df


def build_master_performance(long_df: pd.DataFrame) -> dict:
    """
    Main entry point. Runs the full calculation pipeline and returns
    three DataFrames matching the problem statement's required outputs:

      - 'master'  -> one row per student: cumulative %, percentile, rank, grade
      - 'module'  -> one row per (student, module): module-wise %, percentile
      - 'daily'   -> the original long-format data (per quiz, per student)

    These map directly to the project's required output files:
      1. Master Performance File  -> master
      2. Module Summary File      -> module
      3. Final Rankings File      -> master sorted by rank
    """
    cumulative = calculate_cumulative_performance(long_df)
    master = add_final_percentile_rank_grade(cumulative)
    module = calculate_module_performance(long_df)

    return {
        'master': master,
        'module': module,
        'daily': long_df
    }


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from src.quiz_parser import parse_all_quiz_files
    from src.roster import apply_roster, find_unlisted_duplicates

    long_df = parse_all_quiz_files('data/raw/')

    # Warn about any cross-email duplicates the roster doesn't know about yet
    flagged = find_unlisted_duplicates(long_df)
    if not flagged.empty:
        print("\n  WARNING: possible unlisted duplicate students found:")
        print(flagged.to_string(index=False))
        print("  Consider adding them to config/student_roster.csv\n")

    long_df = apply_roster(long_df)
    results = build_master_performance(long_df)

    print("\n=== MASTER PERFORMANCE (Final Rankings) ===")
    print(results['master'].to_string(index=False))

    print("\n=== MODULE-WISE PERFORMANCE (first 10 rows) ===")
    print(results['module'].head(10).to_string(index=False))

    print(f"\nTotal students: {len(results['master'])}")
    print(f"Grade distribution:\n{results['master']['grade'].value_counts()}")
