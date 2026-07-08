"""
src/emailer.py

Sends each student's grade card PDF to their email via Gmail SMTP.

Why Gmail App Passwords (not your real password):
Google blocks "less secure app" logins by default. An App Password is
a 16-character code generated specifically for one app/script -- it
works with regular SMTP login but can be revoked independently of your
main password, and only works if 2-Step Verification is already on.
Generate one at: https://myaccount.google.com/apppasswords

Why smtplib + email.mime (built into Python, no extra install):
This is the standard library's own SMTP client. No external service,
no cost, works with any SMTP provider (Gmail, Outlook, your college's
mail server) by just changing host/port.

Safety details worth knowing:
- SMTP_SSL on port 465 encrypts the connection end-to-end.
- We send ONE EMAIL AT A TIME in a loop with a short delay between
  sends, to stay well under Gmail's per-day sending limits and avoid
  being flagged as spam-like bulk behavior.
- Every send is logged (success/failure) to output/reports/email_log.csv
  so a partial failure (e.g. network drop at student #30 of 49) is
  fully visible and resumable -- we don't have to guess who got their
  email and who didn't.
"""

import os
import re
import time
import smtplib
import csv
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional -- env vars can still be set directly


SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 465
SECONDS_BETWEEN_EMAILS = 2  # gentle pacing, avoids spam-flagging

EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def is_valid_email(email: str) -> bool:
    """
    Basic format check -- catches typos like 'name@gmail;.com' (a real
    case found in this project's actual data: a stray semicolon from a
    student's typo) BEFORE we waste an SMTP attempt or, worse, silently
    fail without explanation.
    """
    return bool(EMAIL_PATTERN.match(email or ''))


def build_email_body(student_row: dict) -> str:
    """Plain-text email body accompanying the PDF attachment."""
    return f"""Dear {student_row['name']},

Your performance grade card for the Summer Training: ML and Agentic AI
program is attached to this email.

Overall Average: {student_row['avg_percentage']}%
Grade: {student_row['grade']}
Rank: #{student_row['rank']}

Please find the detailed module-wise breakdown and mentor's feedback
in the attached PDF.

Keep up the great work!

Best regards,
Training Coordination Team
Lloyd Institute of Engineering & Technology
"""


def send_single_email(student_row: dict, pdf_path: str, sender_email: str,
                       sender_password: str, smtp_connection=None) -> tuple:
    """
    Sends one grade card email. Returns (success: bool, error_message: str|None).

    Accepts an optional already-open smtp_connection so a bulk send can
    reuse one login instead of reconnecting 49 times (faster, and avoids
    Gmail flagging rapid repeated logins).
    """
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = student_row['email']
    msg['Subject'] = f"Your Grade Card - {student_row['name']} - ML & Agentic AI Training"

    msg.attach(MIMEText(build_email_body(student_row), 'plain'))

    try:
        with open(pdf_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename="grade_card_{student_row["name"].replace(" ", "_")}.pdf"'
        )
        msg.attach(part)
    except FileNotFoundError:
        return (False, f"PDF not found at {pdf_path}")

    try:
        if smtp_connection is not None:
            smtp_connection.sendmail(sender_email, student_row['email'], msg.as_string())
        else:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, student_row['email'], msg.as_string())
        return (True, None)
    except smtplib.SMTPAuthenticationError:
        return (False, "Authentication failed -- check SENDER_EMAIL/SENDER_APP_PASSWORD")
    except smtplib.SMTPRecipientsRefused:
        return (False, f"Recipient address refused: {student_row['email']}")
    except Exception as e:
        return (False, str(e))


def send_all_grade_cards(master_df, grade_card_paths: dict, sender_email: str = None,
                          sender_password: str = None, dry_run: bool = True,
                          log_path: str = 'output/reports/email_log.csv') -> list:
    """
    Sends grade card emails to every student in master_df.

    grade_card_paths: dict mapping email -> pdf filepath (from grade_card.py)
    dry_run: if True, does NOT actually send anything -- just simulates
             and logs what WOULD be sent. This is the default on purpose:
             you should always dry-run first on a real student list to
             catch mistakes (typos, missing PDFs) before sending real email.

    Returns a list of result dicts: {email, name, status, error}
    """
    sender_email = sender_email or os.environ.get('SENDER_EMAIL')
    sender_password = sender_password or os.environ.get('SENDER_APP_PASSWORD')

    # If credentials are missing, always fall back to dry_run regardless of
    # what was requested -- never attempt a network connection with empty values
    if not sender_email or not sender_password:
        if not dry_run:
            print("  Note: SENDER_EMAIL / SENDER_APP_PASSWORD not set in .env")
            print("  Falling back to dry-run mode. Set credentials to send real emails.\n")
        dry_run = True

    results = []
    smtp_connection = None

    if not dry_run:
        smtp_connection = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
        smtp_connection.login(sender_email, sender_password)
        print(f"Logged in as {sender_email}. Sending real emails...\n")
    else:
        print("DRY RUN -- no emails will actually be sent.\n")

    total = len(master_df)
    for idx, (_, student_row) in enumerate(master_df.iterrows(), start=1):
        student_dict = student_row.to_dict()
        email = student_dict['email']
        pdf_path = grade_card_paths.get(email)

        if not is_valid_email(email):
            results.append({'email': email, 'name': student_dict['name'],
                             'status': 'SKIPPED', 'error': 'Invalid email format -- fix in roster'})
            print(f"  [{idx}/{total}] SKIPPED {student_dict['name']} -- invalid email: {email}")
            continue

        if pdf_path is None:
            results.append({'email': email, 'name': student_dict['name'],
                             'status': 'SKIPPED', 'error': 'No grade card PDF found'})
            print(f"  [{idx}/{total}] SKIPPED {student_dict['name']} -- no PDF")
            continue

        if dry_run:
            print(f"  [{idx}/{total}] Would send to {student_dict['name']} <{email}> ({pdf_path})")
            results.append({'email': email, 'name': student_dict['name'],
                             'status': 'DRY_RUN', 'error': None})
            continue

        success, error = send_single_email(student_dict, pdf_path, sender_email,
                                            sender_password, smtp_connection)
        status = 'SENT' if success else 'FAILED'
        results.append({'email': email, 'name': student_dict['name'],
                         'status': status, 'error': error})
        print(f"  [{idx}/{total}] {status}: {student_dict['name']} <{email}>" +
              (f" -- {error}" if error else ""))

        time.sleep(SECONDS_BETWEEN_EMAILS)

    if smtp_connection is not None:
        smtp_connection.quit()

    _save_log(results, log_path)
    return results


def _save_log(results: list, log_path: str):
    """Writes the send log to CSV -- essential for auditing/resending failures."""
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'email', 'name', 'status', 'error'])
        writer.writeheader()
        timestamp = datetime.now().isoformat()
        for r in results:
            writer.writerow({'timestamp': timestamp, **r})

    sent = sum(1 for r in results if r['status'] == 'SENT')
    failed = sum(1 for r in results if r['status'] == 'FAILED')
    skipped = sum(1 for r in results if r['status'] == 'SKIPPED')
    dry = sum(1 for r in results if r['status'] == 'DRY_RUN')

    print(f"\nLog saved to {path}")
    print(f"Summary: {sent} sent, {failed} failed, {skipped} skipped, {dry} dry-run")


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from src.quiz_parser import parse_all_quiz_files
    from src.roster import apply_roster
    from src.calculator import build_master_performance
    from pathlib import Path

    long_df = parse_all_quiz_files('data/raw/')
    long_df = apply_roster(long_df)
    results = build_master_performance(long_df)

    # Map each student's email to their already-generated PDF path
    grade_card_dir = Path('output/grade_cards/')
    grade_card_paths = {}
    for _, row in results['master'].iterrows():
        safe_name = row['email'].replace('@', '_at_').replace('.', '_')
        pdf_path = grade_card_dir / f"{safe_name}.pdf"
        if pdf_path.exists():
            grade_card_paths[row['email']] = str(pdf_path)

    # ALWAYS dry-run first
    send_all_grade_cards(results['master'], grade_card_paths, dry_run=True)
