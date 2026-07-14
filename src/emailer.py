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
    pass

SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 465
SECONDS_BETWEEN_EMAILS = 2
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def is_valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.match(email or ''))

def build_email_body(student_row: dict) -> str:
    return f"""Dear {student_row['name']},

Your performance grade card for the Summer Training: ML and Agentic AI
program is attached to this email.

Overall Average: {student_row['avg_percentage']}%
Grade: {student_row['grade']}
Rank: #{student_row['rank']}

Please find the detailed module-wise breakdown and mentor's feedback
in the attached PDF.

Best regards,
Training Coordination Team
Lloyd Institute of Engineering & Technology
"""

def send_single_email(student_row, pdf_path, sender_email, sender_password, smtp_connection=None):
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
        part.add_header('Content-Disposition', f'attachment; filename="grade_card_{student_row["name"].replace(" ","_")}.pdf"')
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

def send_all_grade_cards(master_df, grade_card_paths, sender_email=None, sender_password=None, dry_run=True, log_path='output/reports/email_log.csv'):
    sender_email = sender_email or os.environ.get('SENDER_EMAIL')
    sender_password = sender_password or os.environ.get('SENDER_APP_PASSWORD')
    if not sender_email or not sender_password:
        if not dry_run:
            print("  Note: SENDER_EMAIL / SENDER_APP_PASSWORD not set in .env")
            print("  Falling back to dry-run mode.\n")
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
        if not is_valid_email(email):
            results.append({'email': email, 'name': student_dict['name'], 'status': 'SKIPPED', 'error': 'Invalid email format'})
            print(f"  [{idx}/{total}] SKIPPED {student_dict['name']} -- invalid email: {email}")
            continue
        pdf_path = grade_card_paths.get(email)
        if pdf_path is None:
            results.append({'email': email, 'name': student_dict['name'], 'status': 'SKIPPED', 'error': 'No grade card PDF found'})
            print(f"  [{idx}/{total}] SKIPPED {student_dict['name']} -- no PDF")
            continue
        if dry_run:
            print(f"  [{idx}/{total}] Would send to {student_dict['name']} <{email}>")
            results.append({'email': email, 'name': student_dict['name'], 'status': 'DRY_RUN', 'error': None})
            continue
        success, error = send_single_email(student_dict, pdf_path, sender_email, sender_password, smtp_connection)
        status = 'SENT' if success else 'FAILED'
        results.append({'email': email, 'name': student_dict['name'], 'status': status, 'error': error})
        print(f"  [{idx}/{total}] {status}: {student_dict['name']}" + (f" -- {error}" if error else ""))
        time.sleep(SECONDS_BETWEEN_EMAILS)
    if smtp_connection:
        smtp_connection.quit()
    _save_log(results, log_path)
    return results

def _save_log(results, log_path):
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp','email','name','status','error'])
        writer.writeheader()
        timestamp = datetime.now().isoformat()
        for r in results:
            writer.writerow({'timestamp': timestamp, **r})
    sent = sum(1 for r in results if r['status']=='SENT')
    failed = sum(1 for r in results if r['status']=='FAILED')
    skipped = sum(1 for r in results if r['status']=='SKIPPED')
    dry = sum(1 for r in results if r['status']=='DRY_RUN')
    print(f"\nLog saved to {log_path}")
    print(f"Summary: {sent} sent, {failed} failed, {skipped} skipped, {dry} dry-run")
