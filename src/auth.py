"""
src/auth.py

Handles authentication and authorization for the Flask API.

Two roles:
  - admin  : trainer/institute staff -- full access to all data and actions
  - student: identified by their email -- can only see their own record

How it works:
  1. Client sends credentials to /api/login (admin password or student email)
  2. Server verifies and returns a signed JWT token (expires in 8 hours)
  3. Client stores the token and sends it in every subsequent request
     as: Authorization: Bearer <token>
  4. Protected routes use @require_auth or @require_admin decorators
     which verify the token before running the handler

Why JWT (not sessions):
  - Stateless: server doesn't need to store session data anywhere
  - Works naturally with fetch() from any HTML page
  - Easy to inspect (jwt.io) for debugging during development
"""

import os
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Config ─────────────────────────────────────────────────────────────────
JWT_SECRET  = os.environ.get('JWT_SECRET_KEY', 'dev-secret-change-in-production')
JWT_ALGO    = 'HS256'
TOKEN_EXPIRY_HOURS = 8
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')


def _hash_password(plain: str) -> bytes:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt())


def _check_password(plain: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed)


# ── Token generation ───────────────────────────────────────────────────────
def generate_token(role: str, email: str = None) -> str:
    """
    Creates a signed JWT token encoding the user's role and (for students)
    their email. Token expires after TOKEN_EXPIRY_HOURS hours.

    Payload shape:
      { role: 'admin' | 'student', email: str|None, exp: timestamp }
    """
    payload = {
        'role': role,
        'email': email,
        'exp': datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_token(token: str) -> dict:
    """
    Decodes and validates a JWT token. Raises jwt.ExpiredSignatureError
    if the token has expired, jwt.InvalidTokenError for anything else wrong.
    """
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])


# ── Login verification ─────────────────────────────────────────────────────
def verify_admin_login(password: str) -> bool:
    """Checks admin password against the value in .env (ADMIN_PASSWORD)."""
    return password == ADMIN_PASSWORD


def verify_student_login(email: str, master_df) -> bool:
    """
    Students don't have passwords -- they log in with just their email.
    We verify the email exists in the master performance data.
    This is intentionally simple: the grade card is not sensitive enough
    to warrant a password for each of 49 students.
    """
    if master_df is None or master_df.empty:
        return False
    email_clean = email.strip().lower()
    return email_clean in master_df['email'].str.lower().values


# ── Route decorators ────────────────────────────────────────────────────────
def _get_token_from_request() -> str | None:
    """Extracts Bearer token from the Authorization header."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None


def require_auth(f):
    """
    Decorator: allows any logged-in user (admin OR student).
    Attaches decoded token payload to request.current_user.
    Use this for routes that students and admins both need (e.g. /api/me).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _get_token_from_request()
        if not token:
            return jsonify({'error': 'No token provided. Please log in.'}), 401
        try:
            request.current_user = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Session expired. Please log in again.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token. Please log in again.'}), 401
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """
    Decorator: admin-only routes. Students get a 403 Forbidden.
    Use this for routes that expose all student data or trigger actions
    (run pipeline, send emails, view all rankings).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _get_token_from_request()
        if not token:
            return jsonify({'error': 'No token provided. Please log in.'}), 401
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Session expired. Please log in again.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token. Please log in again.'}), 401

        if payload.get('role') != 'admin':
            return jsonify({'error': 'Admin access required.'}), 403

        request.current_user = payload
        return f(*args, **kwargs)
    return decorated


def require_student_or_admin(f):
    """
    Decorator for routes where a student can access their OWN data,
    or an admin can access ANY student's data.
    The route handler checks request.current_user to decide what to return.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _get_token_from_request()
        if not token:
            return jsonify({'error': 'No token provided. Please log in.'}), 401
        try:
            request.current_user = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Session expired. Please log in again.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token. Please log in again.'}), 401
        return f(*args, **kwargs)
    return decorated


if __name__ == '__main__':
    print('Testing auth module...')
    token = generate_token('admin')
    decoded = decode_token(token)
    print(f'Admin token role: {decoded["role"]}')

    student_token = generate_token('student', 'rohan@liet.in')
    decoded2 = decode_token(student_token)
    print(f'Student token role: {decoded2["role"]}, email: {decoded2["email"]}')

    print(f'Admin password check (correct): {verify_admin_login("admin123")}')
    print(f'Admin password check (wrong):   {verify_admin_login("wrongpass")}')
    print('Auth module OK.')
