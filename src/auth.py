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

JWT_SECRET = os.environ.get('JWT_SECRET_KEY', 'dev-secret-change-in-production')
JWT_ALGO = 'HS256'
TOKEN_EXPIRY_HOURS = 8
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')


def generate_token(role: str, email: str = None) -> str:
    payload = {
        'role': role, 'email': email,
        'exp': datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])


def verify_admin_login(password: str) -> bool:
    return password == ADMIN_PASSWORD


def verify_student_login(email: str, master_df) -> bool:
    if master_df is None or master_df.empty:
        return False
    return email.strip().lower() in master_df['email'].str.lower().values


def _get_token_from_request():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    return None


def require_auth(f):
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
