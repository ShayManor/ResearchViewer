from flask import Blueprint, request, jsonify
from src.database import get_db
import hashlib
import secrets

users_bp = Blueprint("users", __name__)


def hash_password(password: str) -> str:
    """Hash password with embedded salt using SHA-256.

    Returns password_hash in format: salt$hash
    """
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against stored hash."""
    try:
        salt, stored_hash = password_hash.split('$', 1)
        new_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return new_hash == stored_hash
    except:
        return False


@users_bp.route("/api/users/register", methods=["POST"])
def register():
    """Create new user. Input: username, password."""
    db = get_db()
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    # Check if username already exists
    existing = db.execute(
        "SELECT COUNT(*) FROM users WHERE username = ?",
        [username]
    ).fetchone()[0]

    if existing > 0:
        return jsonify({"error": "Username already exists"}), 409

    # Hash password
    password_hash = hash_password(password)

    # Get next user ID
    max_id = db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM users").fetchone()[0]

    # Create user
    db.execute("""
        INSERT INTO users (id, username, password_hash)
        VALUES (?, ?, ?)
    """, [max_id, username, password_hash])

    user_id = max_id

    return jsonify({
        "status": "created",
        "user_id": user_id,
        "username": username
    }), 201


@users_bp.route("/api/users/login", methods=["POST"])
def login():
    """Authenticate user. Input: username, password. Returns: session token."""
    db = get_db()
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    # Get user
    result = db.execute(
        "SELECT id, password_hash FROM users WHERE username = ?",
        [username]
    ).fetchone()

    if not result:
        return jsonify({"error": "Invalid credentials"}), 401

    user_id, stored_hash = result

    # Verify password
    if not verify_password(password, stored_hash):
        return jsonify({"error": "Invalid credentials"}), 401

    # Generate session token (simple token for now)
    session_token = secrets.token_urlsafe(32)

    return jsonify({
        "status": "authenticated",
        "user_id": user_id,
        "username": username,
        "session_token": session_token
    })


@users_bp.route("/api/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Get user profile. Returns: username, read_papers, subjects_of_interest."""
    db = get_db()

    # Get user info
    user = db.execute(
        "SELECT id, username FROM users WHERE id = ?",
        [user_id]
    ).fetchone()

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Get subjects of interest
    subjects = db.execute(
        "SELECT subject FROM user_subjects WHERE user_id = ?",
        [user_id]
    ).fetchall()

    # Get read papers
    read_papers = db.execute(
        "SELECT doi FROM user_read_papers WHERE user_id = ?",
        [user_id]
    ).fetchall()

    return jsonify({
        "user_id": user[0],
        "username": user[1],
        "subjects_of_interest": [s[0] for s in subjects],
        "read_papers": [p[0] for p in read_papers]
    })


@users_bp.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    """Remove user and all associated data."""
    db = get_db()

    # Check if user exists
    existing = db.execute(
        "SELECT COUNT(*) FROM users WHERE id = ?",
        [user_id]
    ).fetchone()[0]

    if existing == 0:
        return jsonify({"error": "User not found"}), 404

    # Delete related data
    db.execute("DELETE FROM user_subjects WHERE user_id = ?", [user_id])
    db.execute("DELETE FROM user_read_papers WHERE user_id = ?", [user_id])
    db.execute("DELETE FROM user_candidates WHERE user_id = ?", [user_id])
    db.execute("DELETE FROM users WHERE id = ?", [user_id])

    return jsonify({"status": "deleted", "user_id": user_id})


@users_bp.route("/api/users/<int:user_id>/subjects", methods=["POST"])
def add_subject(user_id):
    """Add subject to user interests. Input: subject."""
    db = get_db()
    data = request.get_json()

    subject = data.get('subject')

    if not subject:
        return jsonify({"error": "Subject is required"}), 400

    # Check if user exists
    user_exists = db.execute(
        "SELECT COUNT(*) FROM users WHERE id = ?",
        [user_id]
    ).fetchone()[0]

    if user_exists == 0:
        return jsonify({"error": "User not found"}), 404

    # Check if already added
    existing = db.execute(
        "SELECT COUNT(*) FROM user_subjects WHERE user_id = ? AND subject = ?",
        [user_id, subject]
    ).fetchone()[0]

    if existing > 0:
        return jsonify({"status": "already_exists"}), 200

    # Add subject
    db.execute(
        "INSERT INTO user_subjects (user_id, subject) VALUES (?, ?)",
        [user_id, subject]
    )

    return jsonify({"status": "added", "subject": subject})


@users_bp.route("/api/users/<int:user_id>/subjects/<subject>", methods=["DELETE"])
def remove_subject(user_id, subject):
    """Remove subject from user interests."""
    db = get_db()

    db.execute(
        "DELETE FROM user_subjects WHERE user_id = ? AND subject = ?",
        [user_id, subject]
    )

    return jsonify({"status": "removed", "subject": subject})


@users_bp.route("/api/users/<int:user_id>/read", methods=["POST"])
def add_read_paper(user_id):
    """Add paper to read list. Input: doi."""
    db = get_db()
    data = request.get_json()

    doi = data.get('doi')

    if not doi:
        return jsonify({"error": "DOI is required"}), 400

    # Check if user exists
    user_exists = db.execute(
        "SELECT COUNT(*) FROM users WHERE id = ?",
        [user_id]
    ).fetchone()[0]

    if user_exists == 0:
        return jsonify({"error": "User not found"}), 404

    # Check if already added
    existing = db.execute(
        "SELECT COUNT(*) FROM user_read_papers WHERE user_id = ? AND doi = ?",
        [user_id, doi]
    ).fetchone()[0]

    if existing > 0:
        return jsonify({"status": "already_exists"}), 200

    # Add to read list
    db.execute(
        "INSERT INTO user_read_papers (user_id, doi) VALUES (?, ?)",
        [user_id, doi]
    )

    return jsonify({"status": "added", "doi": doi})


@users_bp.route("/api/users/<int:user_id>/read/<path:doi>", methods=["DELETE"])
def remove_read_paper(user_id, doi):
    """Remove paper from read list."""
    db = get_db()

    db.execute(
        "DELETE FROM user_read_papers WHERE user_id = ? AND doi = ?",
        [user_id, doi]
    )

    return jsonify({"status": "removed", "doi": doi})


@users_bp.route("/api/users/<int:user_id>/recommendations", methods=["GET"])
def get_recommendations(user_id):
    """Get recommended papers based on read history and subjects. Query params: limit (default 10)."""
    db = get_db()

    limit = int(request.args.get('limit', 10))

    # Get user's subjects and read papers
    subjects = db.execute(
        "SELECT subject FROM user_subjects WHERE user_id = ?",
        [user_id]
    ).fetchall()

    read_dois = db.execute(
        "SELECT doi FROM user_read_papers WHERE user_id = ?",
        [user_id]
    ).fetchall()

    if not subjects and not read_dois:
        return jsonify({"recommendations": [], "count": 0})

    # Build recommendation query
    # Strategy: Find papers that:
    # 1. Are in user's subjects of interest
    # 2. Cite or are cited by papers user has read
    # 3. Are highly cited
    # 4. User hasn't read yet

    recommendations = []

    # Recommend based on subjects
    if subjects:
        subject_list = [s[0] for s in subjects]
        placeholders = ','.join(['?'] * len(subject_list))

        subject_recs = db.execute(f"""
            SELECT doi, title, abstract, categories, citation_count
            FROM papers
            WHERE (deleted = false OR deleted IS NULL)
            AND categories IN ({placeholders})
            ORDER BY citation_count DESC
            LIMIT ?
        """, subject_list + [limit]).fetchdf()

        recommendations.extend(subject_recs.to_dict('records'))

    # Recommend based on citation graph (papers that cite what user read)
    if read_dois and len(recommendations) < limit:
        read_list = [d[0] for d in read_dois]
        placeholders = ','.join(['?'] * len(read_list))

        citation_recs = db.execute(f"""
            SELECT DISTINCT p.doi, p.title, p.abstract, p.categories, p.citation_count
            FROM papers p
            WHERE (p.deleted = false OR p.deleted IS NULL)
            AND EXISTS (
                SELECT 1 FROM unnest(p.citations) AS c(citation)
                WHERE c.citation IN ({placeholders})
            )
            ORDER BY p.citation_count DESC
            LIMIT ?
        """, read_list + [limit - len(recommendations)]).fetchdf()

        recommendations.extend(citation_recs.to_dict('records'))

    # Remove duplicates and papers already read
    seen = set([d[0] for d in read_dois])
    unique_recs = []
    for rec in recommendations:
        if rec['doi'] not in seen:
            unique_recs.append(rec)
            seen.add(rec['doi'])
            if len(unique_recs) >= limit:
                break

    return jsonify({
        "recommendations": unique_recs[:limit],
        "count": len(unique_recs[:limit])
    })
