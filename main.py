"""
main.py

The single entry point for the entire Automated Training Performance
Management System. Run this one file to execute every phase:

    python main.py               <- full pipeline, email dry-run
    python main.py --send        <- full pipeline + actually send emails
    python main.py --no-cards    <- skip PDF generation (faster, data only)

Pipeline order:
    1. Parse all quiz CSVs in data/raw/
    2. Apply student roster (fix cross-email duplicate identities)
    3. Calculate performance (scores, percentile, rank, grade)
    4. Export Excel/CSV output files
    5. Generate PDF grade cards with AI comments
    6. Email grade cards (dry-run by default, --send to actually send)

Every step logs what it's doing. Failures in one step are reported but
don't crash the whole run where possible -- so a bad email address or
one malformed CSV won't silently kill all 49 grade cards.
"""

import sys
import argparse
from pathlib import Path


def print_header(title: str):
    width = 55
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def run_pipeline(send_emails: bool = False, generate_cards: bool = True):

    # ── Step 1: Parse ────────────────────────────────────────────
    print_header("Step 1/5 — Parsing quiz files")
    from src.quiz_parser import parse_all_quiz_files
    long_df = parse_all_quiz_files('data/raw/')
    print(f"  Total quiz attempts loaded: {len(long_df)}")

    # ── Step 2: Roster ───────────────────────────────────────────
    print_header("Step 2/5 — Applying student roster")
    from src.roster import apply_roster, find_unlisted_duplicates
    flagged = find_unlisted_duplicates(long_df)
    if not flagged.empty:
        print("  ⚠ Possible new duplicate students (not yet in roster):")
        print(flagged.to_string(index=False))
        print("  → Add them to config/student_roster.csv before re-running.")
    long_df = apply_roster(long_df)
    print(f"  Unique students after normalization: {long_df['email'].nunique()}")

    # ── Step 3: Calculate ─────────────────────────────────────────
    print_header("Step 3/5 — Calculating performance")
    from src.calculator import build_master_performance
    results = build_master_performance(long_df)
    master = results['master']
    print(f"  Students ranked: {len(master)}")
    print(f"  Grade distribution:")
    for grade, count in master['grade'].value_counts().sort_index().items():
        bar = '█' * count
        print(f"    {grade:3s}  {bar} ({count})")

    # ── Step 4: Export ────────────────────────────────────────────
    print_header("Step 4/5 — Exporting output files")
    from src.exporter import export_all_outputs
    paths = export_all_outputs(results)

    # ── Step 5: Grade cards ────────────────────────────────────────
    if not generate_cards:
        print("\n  Grade card generation skipped (--no-cards).")
        grade_card_paths = {}
    else:
        print_header("Step 5/5 — Generating PDF grade cards")
        from src.grade_card import generate_all_grade_cards
        pdf_paths = generate_all_grade_cards(results, use_ai=True)

        # Build email → filepath lookup for the emailer
        grade_card_paths = {}
        for _, row in master.iterrows():
            safe = row['email'].replace('@', '_at_').replace('.', '_')
            p = Path(f'output/grade_cards/{safe}.pdf')
            if p.exists():
                grade_card_paths[row['email']] = str(p)

    # ── Step 6: Email ──────────────────────────────────────────────
    print_header("Step 6/6 — Sending emails" + (" (DRY RUN)" if not send_emails else ""))
    from src.emailer import send_all_grade_cards
    send_all_grade_cards(
        master,
        grade_card_paths,
        dry_run=not send_emails
    )

    # ── Done ──────────────────────────────────────────────────────
    print_header("Pipeline complete")
    print(f"  Students processed : {len(master)}")
    print(f"  Output files       : data/processed/")
    print(f"  Grade cards        : output/grade_cards/")
    print(f"  Email log          : output/reports/email_log.csv")
    if not send_emails:
        print("\n  Emails were NOT sent (dry run).")
        print("  To send for real: python main.py --send")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Grade System Pipeline')
    parser.add_argument('--send', action='store_true',
                        help='Actually send emails (default is dry-run only)')
    parser.add_argument('--no-cards', action='store_true',
                        help='Skip PDF grade card generation')
    args = parser.parse_args()

    run_pipeline(send_emails=args.send, generate_cards=not args.no_cards)
