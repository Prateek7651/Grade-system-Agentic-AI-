"""
api.py

Flask REST API — the bridge between your HTML/CSS/JS frontend
and the existing Python pipeline modules.

Run with:
    python api.py

Server starts at: http://localhost:5000

All routes that return data are protected.
Auth flow:
    1. POST /api/login  -> returns JWT token
    2. Every other request sends:  Authorization: Bearer <token>

Endpoints:
    POST /api/login              public    login as admin or student
    GET  /api/me                 any       who am I (role + email)
    GET  /api/students           admin     all students ranked
    GET  /api/student/<email>    auth      one student's full record
    GET  /api/modules            admin     module-wise summary
    GET  /api/stats              admin     cohort KPI numbers
    POST /api/run-pipeline       admin     trigger parse+calculate+export
    POST /api/send-emails        admin     trigger dry-run or real send
    GET  /api/grade-card/<email> auth      download PDF grade card
"""

import os
import sys
import pandas as pd
from pathlib import Path
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

sys.path.insert(0, '.')
from src.auth import (
    generate_token, verify_admin_login, verify_student_login,
    require_auth, require_admin, require_student_or_admin
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

MASTER_PATH = Path('data/processed/master_performance.csv')
MODULE_PATH  = Path('data/processed/module_summary.csv')
GRADE_DIR    = Path('output/grade_cards')


def load_master():
    if not MASTER_PATH.exists():
        return None
    return pd.read_csv(MASTER_PATH)

def load_module():
    if not MODULE_PATH.exists():
        return None
    return pd.read_csv(MODULE_PATH)


# ── /api/login ─────────────────────────────────────────────────────────────
@app.route('/api/login', methods=['POST'])
def login():
    """
    Body: { "role": "admin", "password": "..." }
        or { "role": "student", "email": "..." }

    Returns: { "token": "...", "role": "...", "email": "..." }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    role = data.get('role', '').strip()

    if role == 'admin':
        password = data.get('password', '')
        if not verify_admin_login(password):
            return jsonify({'error': 'Incorrect admin password'}), 401
        token = generate_token('admin')
        return jsonify({'token': token, 'role': 'admin', 'email': None})

    elif role == 'student':
        email = data.get('email', '').strip().lower()
        if not email:
            return jsonify({'error': 'Email is required'}), 400

        master = load_master()
        if not verify_student_login(email, master):
            return jsonify({'error': 'Email not found in student records'}), 401

        token = generate_token('student', email)
        # return the student's display name too, so the frontend can greet them
        name = master[master['email'] == email]['name'].iloc[0]
        return jsonify({'token': token, 'role': 'student', 'email': email, 'name': name})

    else:
        return jsonify({'error': 'role must be "admin" or "student"'}), 400


# ── /api/me ────────────────────────────────────────────────────────────────
@app.route('/api/me', methods=['GET'])
@require_auth
def me():
    """Returns the current user's role and email from their token."""
    return jsonify(request.current_user)


# ── /api/stats ─────────────────────────────────────────────────────────────
@app.route('/api/stats', methods=['GET'])
@require_admin
def stats():
    """Cohort-level KPIs for the admin dashboard header."""
    master = load_master()
    if master is None:
        return jsonify({'error': 'No data. Run the pipeline first.'}), 404

    grade_dist = master['grade'].value_counts().to_dict()
    return jsonify({
        'total_students': len(master),
        'cohort_average': round(master['avg_percentage'].mean(), 1),
        'top_score': round(master['avg_percentage'].max(), 1),
        'lowest_score': round(master['avg_percentage'].min(), 1),
        'grade_distribution': grade_dist,
        'quizzes_in_data': int(master['quizzes_attempted'].max()),
        'students_needing_support': int((master['avg_percentage'] < 55).sum()),
        'ap_count': int((master['grade'] == 'A+').sum()),
    })


# ── /api/students ──────────────────────────────────────────────────────────
@app.route('/api/students', methods=['GET'])
@require_admin
def students():
    """All students sorted by rank. Admin only."""
    master = load_master()
    if master is None:
        return jsonify({'error': 'No data. Run the pipeline first.'}), 404

    cols = ['rank', 'name', 'email', 'quizzes_attempted',
            'avg_percentage', 'final_percentile', 'grade']
    return jsonify(master[cols].to_dict('records'))


# ── /api/student/<email> ───────────────────────────────────────────────────
@app.route('/api/student/<path:email>', methods=['GET'])
@require_student_or_admin
def student(email):
    """
    Returns one student's full record + their module breakdown.
    Students can only fetch their own email.
    Admins can fetch any email.
    """
    user = request.current_user
    email = email.strip().lower()

    # Students can only see themselves
    if user['role'] == 'student' and user['email'] != email:
        return jsonify({'error': 'Access denied. You can only view your own record.'}), 403

    master = load_master()
    module = load_module()
    if master is None:
        return jsonify({'error': 'No data. Run the pipeline first.'}), 404

    row = master[master['email'] == email]
    if row.empty:
        return jsonify({'error': f'Student not found: {email}'}), 404

    student_data = row.iloc[0].to_dict()
    # convert numpy types to plain Python for JSON serialisation
    student_data = {k: (int(v) if hasattr(v, 'item') else v)
                    for k, v in student_data.items()}

    modules = []
    if module is not None:
        mod_rows = module[module['email'] == email]
        modules = mod_rows[['module', 'marks_scored', 'marks_possible',
                             'module_percentage', 'module_percentile']].to_dict('records')

    return jsonify({'student': student_data, 'modules': modules})


# ── /api/modules ───────────────────────────────────────────────────────────
@app.route('/api/modules', methods=['GET'])
@require_admin
def modules():
    """Module-wise average performance for the admin charts."""
    module = load_module()
    if module is None:
        return jsonify({'error': 'No data. Run the pipeline first.'}), 404

    module_avg = (
        module.groupby('module')['module_percentage']
        .agg(['mean', 'min', 'max', 'count'])
        .reset_index()
    )
    module_avg.columns = ['module', 'avg', 'min', 'max', 'student_count']
    module_avg = module_avg.round(1)
    return jsonify(module_avg.to_dict('records'))


# ── /api/run-pipeline ──────────────────────────────────────────────────────
@app.route('/api/run-pipeline', methods=['POST'])
@require_admin
def run_pipeline():
    """
    Triggers the full pipeline: parse → roster → calculate → export → grade cards.
    Returns a summary of what was processed.
    Admin only -- this is a write operation.
    """
    try:
        from src.quiz_parser import parse_all_quiz_files
        from src.roster import apply_roster
        from src.calculator import build_master_performance
        from src.exporter import export_all_outputs
        from src.grade_card import generate_all_grade_cards

        long_df = parse_all_quiz_files('data/raw/')
        long_df = apply_roster(long_df)
        results = build_master_performance(long_df)
        export_all_outputs(results)
        generate_all_grade_cards(results, use_ai=True)

        return jsonify({
            'success': True,
            'students_processed': len(results['master']),
            'quizzes_found': long_df['quiz_id'].nunique(),
            'grade_cards_generated': len(list(GRADE_DIR.glob('*.pdf'))),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── /api/send-emails ──────────────────────────────────────────────────────
@app.route('/api/send-emails', methods=['POST'])
@require_admin
def send_emails():
    """
    Body: { "dry_run": true }   <- simulate only (default, safe)
          { "dry_run": false }  <- actually send

    Returns: summary of sent/failed/skipped.
    """
    data = request.get_json() or {}
    dry_run = data.get('dry_run', True)  # always default to safe

    try:
        from src.emailer import send_all_grade_cards

        master = load_master()
        if master is None:
            return jsonify({'error': 'No data. Run the pipeline first.'}), 404

        grade_card_paths = {}
        for _, row in master.iterrows():
            safe = row['email'].replace('@', '_at_').replace('.', '_')
            p = GRADE_DIR / f'{safe}.pdf'
            if p.exists():
                grade_card_paths[row['email']] = str(p)

        results = send_all_grade_cards(master, grade_card_paths, dry_run=dry_run)

        summary = {
            'dry_run': dry_run,
            'total': len(results),
            'sent': sum(1 for r in results if r['status'] == 'SENT'),
            'failed': sum(1 for r in results if r['status'] == 'FAILED'),
            'skipped': sum(1 for r in results if r['status'] == 'SKIPPED'),
            'dry_run_count': sum(1 for r in results if r['status'] == 'DRY_RUN'),
            'details': results
        }
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── /api/grade-card/<email> ────────────────────────────────────────────────
@app.route('/api/grade-card/<path:email>', methods=['GET'])
@require_student_or_admin
def grade_card(email):
    """Serves the PDF grade card file for download."""
    user = request.current_user
    email = email.strip().lower()

    if user['role'] == 'student' and user['email'] != email:
        return jsonify({'error': 'Access denied.'}), 403

    safe = email.replace('@', '_at_').replace('.', '_')
    pdf_path = GRADE_DIR / f'{safe}.pdf'

    if not pdf_path.exists():
        return jsonify({'error': 'Grade card not found. Run the pipeline first.'}), 404

    return send_file(str(pdf_path), as_attachment=True,
                     download_name=f'grade_card_{email}.pdf',
                     mimetype='application/pdf')


# ── Run ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("\nGrade System API")
    print("=" * 40)
    print("Running at: http://localhost:5000")
    print()
    print("Admin login  : POST /api/login  { role:'admin', password:'admin123' }")
    print("Student login: POST /api/login  { role:'student', email:'you@liet.in' }")
    print()
    print("Change ADMIN_PASSWORD in your .env file before sharing with anyone.")
    print("=" * 40 + "\n")
    app.run(debug=True, port=5000)
