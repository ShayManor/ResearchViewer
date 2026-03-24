"""
Firebase Authentication Middleware

Provides @require_auth decorator to protect Flask routes with Firebase ID token verification.
"""

import os
from functools import wraps
from flask import request, jsonify, g
import firebase_admin
from firebase_admin import credentials, auth

# Initialize Firebase Admin SDK
cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH', 'firebase-service-account.json')
if not os.path.exists(cred_path):
    print(f"Warning: Firebase credentials not found at {cred_path}")
    print("Authentication will fail until credentials are provided.")
else:
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print(f"Firebase Admin SDK initialized with credentials from {cred_path}")
    except Exception as e:
        print(f"Error initializing Firebase Admin SDK: {e}")


def require_auth(f):
    """
    Decorator to require Firebase ID token authentication.

    Verifies the Firebase ID token from the Authorization header,
    looks up the user in DuckDB, and stores user info in Flask's g object.

    Usage:
        @app.route('/api/users/<int:user_id>')
        @require_auth
        def get_user(user_id):
            # Access authenticated user via g.user_id, g.firebase_uid, g.firebase_email
            if g.user_id != user_id:
                return jsonify({'error': 'Unauthorized'}), 403
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid authorization header'}), 401

        id_token = auth_header.split('Bearer ')[1]

        try:
            # Verify the ID token with Firebase
            decoded_token = auth.verify_id_token(id_token)
            g.firebase_uid = decoded_token['uid']
            g.firebase_email = decoded_token.get('email')

            # Look up user in DuckDB by Firebase UID
            from src.database import get_user_db
            user_db = get_user_db()
            user = user_db.execute(
                "SELECT id, username, email FROM users WHERE firebase_uid = ?",
                [g.firebase_uid]
            ).fetchone()

            if not user:
                return jsonify({'error': 'User not found in database'}), 404

            g.user_id = user[0]  # Store authenticated user ID in Flask g
            g.username = user[1]
            g.user_email = user[2]

            return f(*args, **kwargs)

        except auth.InvalidIdTokenError:
            return jsonify({'error': 'Invalid authentication token'}), 401
        except auth.ExpiredIdTokenError:
            return jsonify({'error': 'Authentication token expired'}), 401
        except Exception as e:
            return jsonify({'error': f'Authentication failed: {str(e)}'}), 401

    return decorated_function
