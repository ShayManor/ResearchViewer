from flask import Blueprint, request, jsonify, g
from src.database import get_user_db, get_data_db, df_to_json_serializable
from src.cache import cache
from src.auth import require_auth
from src.sql_safety import (
    InvalidParameter,
    safe_int,
    safe_sort_field,
    safe_sort_order,
)
import datetime

users_bp = Blueprint("users", __name__)


def clear_user_recommendations_cache(user_id):
    """Invalidate cached recommendations for a user.

    SimpleCache has no pattern-delete, so we clear the whole cache. This
    is blunt but correct — recommendations change rarely and the rest of
    the cache rewarms cheaply.
    """
    cache.clear()


@users_bp.route("/api/auth/register", methods=["POST"])
def register():
    """
    Register new user after Firebase authentication.
    Called by frontend after user completes Google OAuth.
    """
    db = get_user_db()
    data = request.get_json()

    firebase_uid = data.get('firebase_uid')
    email = data.get('email')
    username = data.get('username')
    focus_topics = data.get('focus_topics', [])

    if not firebase_uid or not email or not username:
        return jsonify({"error": "Missing required fields (firebase_uid, email, username)"}), 400

    # Check if user with this firebase_uid already exists
    existing_by_firebase = db.execute(
        "SELECT id, username, email FROM users WHERE firebase_uid = ?",
        [firebase_uid]
    ).fetchone()

    if existing_by_firebase:
        # User already fully registered with this Firebase UID
        return jsonify({
            "user_id": existing_by_firebase[0],
            "username": existing_by_firebase[1],
            "email": existing_by_firebase[2]
        }), 200

    # Check if user with this email already exists (but different firebase_uid)
    existing_by_email = db.execute(
        "SELECT id, username, email, firebase_uid FROM users WHERE email = ?",
        [email]
    ).fetchone()

    if existing_by_email:
        # User exists with this email but different/missing firebase_uid
        # Update their firebase_uid to link the accounts
        db.execute(
            "UPDATE users SET firebase_uid = ? WHERE email = ?",
            [firebase_uid, email]
        )
        db.commit()

        return jsonify({
            "user_id": existing_by_email[0],
            "username": existing_by_email[1],
            "email": existing_by_email[2]
        }), 200

    # Check if username is taken
    existing_username = db.execute(
        "SELECT id FROM users WHERE username = ?",
        [username]
    ).fetchone()

    if existing_username:
        return jsonify({"error": "Username already taken"}), 409

    # Get next user ID from sequence
    next_id = db.execute("SELECT nextval('users_id_seq')").fetchone()[0]

    # Create new user
    db.execute("""
        INSERT INTO users (id, username, email, firebase_uid, password_hash, focus_topics, created_at)
        VALUES (?, ?, ?, ?, '', ?, CURRENT_TIMESTAMP)
    """, [next_id, username, email, firebase_uid, focus_topics])

    db.commit()

    return jsonify({
        "user_id": next_id,
        "username": username,
        "email": email
    }), 201


@users_bp.route("/api/auth/me", methods=["GET"])
@require_auth
def get_current_user():
    """Get currently authenticated user's profile."""
    return get_user(g.user_id)


@users_bp.route("/api/users/<int:user_id>", methods=["GET"])
@require_auth
def get_user(user_id):
    """Get user profile with all statistics."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    user_db = get_user_db()
    data_db = get_data_db()

    # Get user info from user DB
    user = user_db.execute(
        "SELECT id, username, email, focus_topics, linked_author_id, created_at FROM users WHERE id = ?",
        [user_id]
    ).fetchone()

    if not user:
        return jsonify({"error": "User not found"}), 404

    user_data = {
        'user_id': user[0],
        'username': user[1],
        'email': user[2],
        'focus_topics': user[3] or [],
        'linked_author_id': user[4],
        'created_at': user[5].isoformat() if user[5] else None
    }

    # Get linked author name from data DB
    if user[4]:
        author = data_db.execute(
            "SELECT name FROM authors WHERE author_id = ?",
            [user[4]]
        ).fetchone()
        user_data['linked_author_name'] = author[0] if author else None

    # Calculate statistics from user DB
    reading_list_count = user_db.execute(
        "SELECT COUNT(*) FROM user_reading_list WHERE user_id = ?",
        [user_id]
    ).fetchone()[0]

    papers_read_count = user_db.execute(
        "SELECT COUNT(*) FROM user_read_history WHERE user_id = ?",
        [user_id]
    ).fetchone()[0]

    publication_count = user_db.execute(
        "SELECT COUNT(*) FROM user_publications WHERE user_id = ?",
        [user_id]
    ).fetchone()[0]

    publication_citations = user_db.execute(
        "SELECT SUM(citation_count) FROM user_publications WHERE user_id = ?",
        [user_id]
    ).fetchone()[0] or 0

    # Get paper IDs from read history, then query papers from data DB
    read_paper_ids = user_db.execute(
        "SELECT paper_id FROM user_read_history WHERE user_id = ?",
        [user_id]
    ).fetchdf()

    total_citations_covered = 0
    avg_citations_per_read = 0
    if not read_paper_ids.empty:
        paper_ids = read_paper_ids['paper_id'].tolist()
        placeholders = ','.join(['?'] * len(paper_ids))
        read_papers = data_db.execute(f"""
            SELECT citation_count
            FROM papers
            WHERE id IN ({placeholders})
        """, paper_ids).fetchdf()

        total_citations_covered = int(read_papers['citation_count'].sum()) if not read_papers.empty else 0
        avg_citations_per_read = int(read_papers['citation_count'].mean()) if not read_papers.empty else 0

    # Calculate reading pace (papers per week)
    if user[5]:
        days_since_join = (datetime.datetime.now() - user[5]).days
        reading_pace_per_week = papers_read_count / (days_since_join / 7) if days_since_join > 0 else 0
    else:
        days_since_join = 0
        reading_pace_per_week = 0

    user_data['stats'] = {
        'reading_list_count': reading_list_count,
        'papers_read_count': papers_read_count,
        'total_citations_covered': total_citations_covered,
        'avg_citations_per_read': avg_citations_per_read,
        'reading_pace_per_week': round(reading_pace_per_week, 1),
        'publication_count': publication_count,
        'publication_citations': publication_citations,
        'days_since_join': days_since_join
    }

    # Reading by microtopic - get paper IDs from user DB, then join with data DB
    if not read_paper_ids.empty:
        paper_ids = read_paper_ids['paper_id'].tolist()
        placeholders = ','.join(['?'] * len(paper_ids))
        reading_by_microtopic = data_db.execute(f"""
            SELECT
                m.microtopic_id,
                m.label as microtopic_label,
                m.bucket_value as topic,
                SPLIT_PART(m.bucket_value, '/', 1) as domain,
                COUNT(DISTINCT pm.paper_id) as count
            FROM paper_microtopics pm
            INNER JOIN microtopics m ON pm.microtopic_id = m.microtopic_id
            WHERE pm.paper_id IN ({placeholders})
            GROUP BY m.microtopic_id, m.label, m.bucket_value
            ORDER BY count DESC
        """, paper_ids).fetchdf()
        user_data['reading_by_microtopic'] = df_to_json_serializable(reading_by_microtopic) if not reading_by_microtopic.empty else []
    else:
        user_data['reading_by_microtopic'] = []

    # Reading over time from user DB - dynamic bucketing based on date range
    # First, get the date range
    date_range = user_db.execute("""
        SELECT
            MIN(read_at) as min_date,
            MAX(read_at) as max_date,
            DATE_DIFF('day', MIN(read_at), MAX(read_at)) as days_range
        FROM user_read_history
        WHERE user_id = ?
    """, [user_id]).fetchone()

    reading_over_time = None
    if date_range and date_range[2] is not None:
        days_range = date_range[2]

        # Choose bucketing strategy based on range
        if days_range <= 30:
            # Daily buckets for <= 30 days
            reading_over_time = user_db.execute("""
                SELECT
                    CAST(read_at AS DATE) as month,
                    COUNT(*) as count
                FROM user_read_history
                WHERE user_id = ?
                GROUP BY month
                ORDER BY month
            """, [user_id]).fetchdf()
        elif days_range <= 180:
            # Weekly buckets for 30-180 days (6 months)
            reading_over_time = user_db.execute("""
                SELECT
                    DATE_TRUNC('week', read_at) as month,
                    COUNT(*) as count
                FROM user_read_history
                WHERE user_id = ?
                GROUP BY month
                ORDER BY month
            """, [user_id]).fetchdf()
        else:
            # Monthly buckets for > 180 days
            reading_over_time = user_db.execute("""
                SELECT
                    DATE_TRUNC('month', read_at) as month,
                    COUNT(*) as count
                FROM user_read_history
                WHERE user_id = ?
                GROUP BY month
                ORDER BY month
            """, [user_id]).fetchdf()

    user_data['reading_over_time'] = df_to_json_serializable(reading_over_time) if reading_over_time is not None and not reading_over_time.empty else []

    return jsonify(user_data)


@users_bp.route("/api/users/<int:user_id>", methods=["PUT"])
@require_auth
def update_user(user_id):
    """Update profile fields."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    db = get_user_db()
    data = request.get_json()

    # Check if user exists
    existing = db.execute(
        "SELECT COUNT(*) FROM users WHERE id = ?",
        [user_id]
    ).fetchone()[0]

    if existing == 0:
        return jsonify({"error": "User not found"}), 404

    # Build update query
    update_fields = []
    params = []

    allowed_fields = ['email', 'focus_topics', 'linked_author_id']
    for field in allowed_fields:
        if field in data:
            update_fields.append(f'{field} = ?')
            params.append(data[field])

    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    params.append(user_id)
    query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"

    db.execute(query, params)

    return jsonify({"status": "updated"})


@users_bp.route("/api/users/<int:user_id>", methods=["DELETE"])
@require_auth
def delete_user(user_id):
    """Delete user account and all associated data."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    db = get_user_db()

    # Get firebase_uid before deleting
    user = db.execute("SELECT firebase_uid FROM users WHERE id = ?", [user_id]).fetchone()
    firebase_uid = user[0] if user else None

    # Start transaction
    db.execute("BEGIN TRANSACTION")

    try:
        # Delete all user data in order
        db.execute("DELETE FROM user_reading_list WHERE user_id = ?", [user_id])
        db.execute("DELETE FROM user_read_history WHERE user_id = ?", [user_id])
        db.execute("DELETE FROM user_publications WHERE user_id = ?", [user_id])
        db.execute("DELETE FROM users WHERE id = ?", [user_id])

        # Commit transaction
        db.execute("COMMIT")

        # Delete from Firebase Auth
        if firebase_uid:
            try:
                from firebase_admin import auth
                auth.delete_user(firebase_uid)
                print(f"Deleted Firebase user: {firebase_uid}")
            except Exception as firebase_error:
                # Log but don't fail if Firebase deletion fails
                # (user might already be deleted from Firebase)
                print(f"Warning: Failed to delete Firebase user {firebase_uid}: {firebase_error}")

        # Clear cache
        clear_user_recommendations_cache(user_id)

        return jsonify({"status": "deleted"}), 200

    except Exception as e:
        # Rollback on error
        db.execute("ROLLBACK")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to delete account", "details": str(e)}), 500


@users_bp.route("/api/users/<int:user_id>/link-author", methods=["PUT"])
@require_auth
def link_author(user_id):
    """Link an author profile to user account and import their publications."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    user_db = get_user_db()
    data_db = get_data_db()
    data = request.get_json()

    author_id = data.get('author_id')

    if not author_id:
        return jsonify({"error": "author_id is required"}), 400

    try:
        # Validate author exists in data DB
        author = data_db.execute(
            "SELECT author_id, name, h_index, works_count, paper_dois FROM authors WHERE author_id = ?",
            [author_id]
        ).fetchone()

        if not author:
            return jsonify({"error": "Author not found"}), 404

        # Start transaction
        user_db.execute("BEGIN TRANSACTION")

        try:
            # Update user in user DB
            user_db.execute(
                "UPDATE users SET linked_author_id = ? WHERE id = ?",
                [author_id, user_id]
            )

            # Import author's publications into user_publications
            paper_dois = author[4] if author[4] else []
            publications_imported = 0
            publications_not_found = 0
            total_citations = 0

            # FIRST: Clear ALL existing auto-imported publications for this user
            # (Keep only manually added ones, which have no DOI from papers table)
            # Delete any publication that has a DOI - these are auto-imported
            user_db.execute(
                "DELETE FROM user_publications WHERE user_id = ? AND doi IS NOT NULL AND doi != ''",
                [user_id]
            )

            if paper_dois and len(paper_dois) > 0:
                doi_placeholders = ','.join(['?'] * len(paper_dois))

                # Get papers from data DB
                papers = data_db.execute(f"""
                    SELECT
                        title,
                        "journal-ref" as venue,
                        YEAR(update_date) as year,
                        doi,
                        citation_count,
                        authors
                    FROM papers
                    WHERE doi IN ({doi_placeholders})
                    AND doi IS NOT NULL
                """, list(paper_dois)).fetchall()

                # Track which DOIs were found
                found_dois = set()

                # Insert papers into user_publications
                for paper in papers:
                    title, venue, year, doi, citation_count, authors = paper
                    found_dois.add(doi)

                    # Parse coauthors - split by comma if string
                    coauthors = []
                    if authors:
                        if isinstance(authors, str):
                            coauthors = [a.strip() for a in authors.split(',') if a.strip()]
                        else:
                            coauthors = authors

                    # Insert with explicit type casting in SQL to avoid parameter binding issues
                    try:
                        user_db.execute("""
                            INSERT INTO user_publications (user_id, title, venue, year, doi, citation_count, coauthors)
                            VALUES (CAST(? AS INTEGER), CAST(? AS VARCHAR), CAST(? AS VARCHAR),
                                    CAST(? AS INTEGER), CAST(? AS VARCHAR), CAST(? AS INTEGER),
                                    CAST(? AS VARCHAR[]))
                        """, [
                            user_id,
                            title or 'Untitled',
                            venue,
                            year or 2024,
                            doi,
                            citation_count or 0,
                            coauthors
                        ])
                    except Exception:
                        # Continue with other publications even if one fails
                        continue

                    publications_imported += 1
                    total_citations += (citation_count or 0)

                # Count how many papers were not found in database
                publications_not_found = len(paper_dois) - len(found_dois)

            # Commit transaction
            user_db.execute("COMMIT")

            return jsonify({
                "status": "linked",
                "author_id": author[0],
                "author_name": author[1],
                "h_index": author[2],
                "works_count": author[3],
                "publications_imported": publications_imported,
                "publications_not_found": publications_not_found,
                "total_citations": total_citations
            })

        except Exception as e:
            # Rollback on any error
            user_db.execute("ROLLBACK")
            raise e

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "Failed to link author",
            "details": str(e)
        }), 500


@users_bp.route("/api/users/<int:user_id>/link-author", methods=["DELETE"])
@require_auth
def unlink_author(user_id):
    """Unlink author profile from user account and remove auto-imported publications."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    db = get_user_db()

    # Start transaction
    db.execute("BEGIN TRANSACTION")

    try:
        # Delete all auto-imported publications (those with DOIs)
        db.execute(
            "DELETE FROM user_publications WHERE user_id = ? AND doi IS NOT NULL AND doi != ''",
            [user_id]
        )

        # Unlink author
        db.execute(
            "UPDATE users SET linked_author_id = NULL WHERE id = ?",
            [user_id]
        )

        # Commit transaction
        db.execute("COMMIT")

        return jsonify({"status": "unlinked"})

    except Exception as e:
        # Rollback on error
        db.execute("ROLLBACK")
        raise e


@users_bp.route("/api/users/<int:user_id>/reading-list", methods=["GET"])
@require_auth
def get_reading_list(user_id):
    """Get user's reading list."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    user_db = get_user_db()
    data_db = get_data_db()

    sort_by = request.args.get('sort_by', 'added_at')
    sort_order = request.args.get('sort_order', 'DESC')

    # Validate sort field
    allowed_sorts = ['added_at', 'citation_count', 'update_date']
    if sort_by not in allowed_sorts:
        sort_by = 'added_at'

    if sort_order not in ['ASC', 'DESC']:
        sort_order = 'DESC'

    # Get reading list from user DB
    reading_list = user_db.execute("""
        SELECT paper_id, added_at
        FROM user_reading_list
        WHERE user_id = ?
    """, [user_id]).fetchdf()

    if reading_list.empty:
        return jsonify({"papers": [], "count": 0})

    # Get paper details from data DB
    paper_ids = reading_list['paper_id'].tolist()
    placeholders = ','.join(['?'] * len(paper_ids))
    papers = data_db.execute(f"""
        SELECT id, title, citation_count, categories, update_date
        FROM papers
        WHERE id IN ({placeholders})
    """, paper_ids).fetchdf()

    # Merge reading list with paper details
    result = reading_list.merge(papers, left_on='paper_id', right_on='id', how='left')

    # Sort
    if sort_by == 'added_at':
        result = result.sort_values('added_at', ascending=(sort_order == 'ASC'))
    else:
        result = result.sort_values(sort_by, ascending=(sort_order == 'ASC'))

    return jsonify({
        "papers": df_to_json_serializable(result) if not result.empty else [],
        "count": len(result)
    })


@users_bp.route("/api/users/<int:user_id>/reading-list", methods=["POST"])
@require_auth
def add_to_reading_list(user_id):
    """Add paper to reading list."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    db = get_user_db()
    data = request.get_json()

    paper_id = data.get('paper_id')

    if not paper_id:
        return jsonify({"error": "paper_id is required"}), 400

    # Check if user exists
    user_exists = db.execute(
        "SELECT COUNT(*) FROM users WHERE id = ?",
        [user_id]
    ).fetchone()[0]

    if user_exists == 0:
        return jsonify({"error": "User not found"}), 404

    # Check if already added
    existing = db.execute(
        "SELECT COUNT(*) FROM user_reading_list WHERE user_id = ? AND paper_id = ?",
        [user_id, paper_id]
    ).fetchone()[0]

    if existing > 0:
        return jsonify({"status": "already_exists"}), 409

    # Add to reading list
    db.execute(
        "INSERT INTO user_reading_list (user_id, paper_id, added_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        [user_id, paper_id]
    )
    db.commit()

    # Clear recommendations cache since reading list changed
    clear_user_recommendations_cache(user_id)

    return jsonify({"status": "added", "paper_id": paper_id}), 201


@users_bp.route("/api/users/<int:user_id>/reading-list/<path:paper_id>", methods=["DELETE"])
@require_auth
def remove_from_reading_list(user_id, paper_id):
    """Remove paper from reading list."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    db = get_user_db()

    db.execute(
        "DELETE FROM user_reading_list WHERE user_id = ? AND paper_id = ?",
        [user_id, paper_id]
    )
    db.commit()

    # Clear recommendations cache since reading list changed
    clear_user_recommendations_cache(user_id)

    return jsonify({"status": "removed"})


@users_bp.route("/api/users/<int:user_id>/read-history", methods=["GET"])
@require_auth
def get_read_history(user_id):
    """Get user's read history."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    user_db = get_user_db()
    data_db = get_data_db()

    try:
        page = safe_int(request.args.get('page'), default=1, minimum=1)
        per_page = safe_int(
            request.args.get('per_page'), default=50, minimum=1, maximum=100
        )
    except InvalidParameter as exc:
        return jsonify({"error": str(exc)}), 400

    sort_by = safe_sort_field(
        request.args.get('sort_by'),
        allowed=('read_at', 'citation_count'),
        default='read_at',
    )
    sort_order = safe_sort_order(request.args.get('sort_order'))

    # Get total count from user DB
    total = user_db.execute(
        "SELECT COUNT(*) FROM user_read_history WHERE user_id = ?",
        [user_id]
    ).fetchone()[0]

    # Get read history from user DB with pagination
    read_history = user_db.execute(f"""
        SELECT paper_id, read_at
        FROM user_read_history
        WHERE user_id = ?
        ORDER BY read_at {sort_order}
        LIMIT ? OFFSET ?
    """, [user_id, per_page, (page - 1) * per_page]).fetchdf()

    if read_history.empty:
        result = read_history
    else:
        # Get paper details from data DB
        paper_ids = read_history['paper_id'].tolist()
        placeholders = ','.join(['?'] * len(paper_ids))
        papers = data_db.execute(f"""
            SELECT id, title, citation_count, categories
            FROM papers
            WHERE id IN ({placeholders})
        """, paper_ids).fetchdf()

        # Merge
        result = read_history.merge(papers, left_on='paper_id', right_on='id', how='left')

        # Re-sort if needed
        if sort_by == 'citation_count':
            result = result.sort_values('citation_count', ascending=(sort_order == 'ASC'))

    return jsonify({
        "history": df_to_json_serializable(result) if not result.empty else [],
        "count": total,
        "page": page,
        "per_page": per_page
    })


@users_bp.route("/api/users/<int:user_id>/read-history", methods=["POST"])
@require_auth
def add_to_read_history(user_id):
    """Mark a paper as read and remove from reading list."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    db = get_user_db()
    data = request.get_json()

    paper_id = data.get('paper_id')
    read_at = data.get('read_at', datetime.datetime.now().isoformat())

    if not paper_id:
        return jsonify({"error": "paper_id is required"}), 400

    # Start transaction to ensure atomic operation
    db.execute("BEGIN TRANSACTION")

    try:
        # Check if already added to read history
        existing = db.execute(
            "SELECT COUNT(*) FROM user_read_history WHERE user_id = ? AND paper_id = ?",
            [user_id, paper_id]
        ).fetchone()[0]

        if existing == 0:
            # Add to read history
            db.execute(
                "INSERT INTO user_read_history (user_id, paper_id, read_at) VALUES (?, ?, ?)",
                [user_id, paper_id, read_at]
            )

        # Remove from reading list (if present)
        db.execute(
            "DELETE FROM user_reading_list WHERE user_id = ? AND paper_id = ?",
            [user_id, paper_id]
        )

        # Commit transaction
        db.execute("COMMIT")

        # Clear recommendations cache since read history changed
        clear_user_recommendations_cache(user_id)

        return jsonify({"status": "added" if existing == 0 else "already_exists"}), 201 if existing == 0 else 200

    except Exception as e:
        # Rollback on error
        db.execute("ROLLBACK")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to mark as read", "details": str(e)}), 500


@users_bp.route("/api/users/<int:user_id>/read-history/<path:paper_id>", methods=["DELETE"])
@require_auth
def remove_from_read_history(user_id, paper_id):
    """Un-mark a paper as read."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    db = get_user_db()

    db.execute(
        "DELETE FROM user_read_history WHERE user_id = ? AND paper_id = ?",
        [user_id, paper_id]
    )

    # Clear recommendations cache since read history changed
    clear_user_recommendations_cache(user_id)

    return jsonify({"status": "removed"})


@users_bp.route("/api/users/<int:user_id>/publications", methods=["GET"])
@require_auth
def get_publications(user_id):
    """Get user's publications."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    user_db = get_user_db()

    result = user_db.execute("""
        SELECT id, title, venue, year, doi, url, citation_count, coauthors
        FROM user_publications
        WHERE user_id = ?
        ORDER BY year DESC, id DESC
    """, [user_id]).fetchdf()

    publications = df_to_json_serializable(result) if not result.empty else []

    total_citations = user_db.execute(
        "SELECT SUM(citation_count) FROM user_publications WHERE user_id = ?",
        [user_id]
    ).fetchone()[0] or 0

    return jsonify({
        "publications": publications,
        "count": len(publications),
        "total_citations": total_citations
    })


@users_bp.route("/api/users/<int:user_id>/publications", methods=["POST"])
@require_auth
def add_publication(user_id):
    """Add a publication."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    db = get_user_db()
    data = request.get_json()

    title = data.get('title')
    venue = data.get('venue')
    year = data.get('year')
    doi = data.get('doi')
    url = data.get('url')
    citation_count = data.get('citation_count', 0)
    coauthors = data.get('coauthors', [])

    if not title or not year:
        return jsonify({"error": "Title and year are required"}), 400

    try:
        # Insert publication (ID will be auto-generated by sequence)
        # Use RETURNING to get the generated ID
        result = db.execute("""
            INSERT INTO user_publications
            (user_id, title, venue, year, doi, url, citation_count, coauthors)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        """, [user_id, title, venue, year, doi, url, citation_count, coauthors]).fetchone()

        new_id = result[0]

        return jsonify({"status": "created", "id": new_id}), 201

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to add publication", "details": str(e)}), 500


@users_bp.route("/api/users/<int:user_id>/publications/<int:pub_id>", methods=["PUT"])
@require_auth
def update_publication(user_id, pub_id):
    """Update a publication entry."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    db = get_user_db()
    data = request.get_json()

    # Check if publication exists and belongs to user
    existing = db.execute(
        "SELECT COUNT(*) FROM user_publications WHERE id = ? AND user_id = ?",
        [pub_id, user_id]
    ).fetchone()[0]

    if existing == 0:
        return jsonify({"error": "Publication not found"}), 404

    # Build update query
    update_fields = []
    params = []

    allowed_fields = ['title', 'venue', 'year', 'doi', 'url', 'citation_count', 'coauthors']
    for field in allowed_fields:
        if field in data:
            update_fields.append(f'{field} = ?')
            params.append(data[field])

    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    params.extend([pub_id, user_id])
    query = f"UPDATE user_publications SET {', '.join(update_fields)} WHERE id = ? AND user_id = ?"

    db.execute(query, params)
    db.commit()  # CRITICAL: Commit the transaction

    return jsonify({"status": "updated"})


@users_bp.route("/api/users/<int:user_id>/publications/<int:pub_id>", methods=["DELETE"])
@require_auth
def delete_publication(user_id, pub_id):
    """Delete a publication."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    db = get_user_db()

    db.execute(
        "DELETE FROM user_publications WHERE id = ? AND user_id = ?",
        [pub_id, user_id]
    )

    return jsonify({"status": "deleted"})


@users_bp.route("/api/users/<int:user_id>/recommendations", methods=["GET"])
@require_auth
@cache.cached(timeout=600, query_string=True)
def get_recommendations(user_id):
    """Get recommended papers based on reading history and topics with temporal weighting."""
    # Verify the authenticated user matches the requested user_id
    if g.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    user_db = get_user_db()
    data_db = get_data_db()

    try:
        limit = safe_int(
            request.args.get('limit'), default=10, minimum=1, maximum=50
        )
    except InvalidParameter as exc:
        return jsonify({"error": str(exc)}), 400
    strategy = request.args.get('strategy', 'hybrid')
    if strategy not in ('hybrid', 'citation_graph', 'topic_similarity'):
        strategy = 'hybrid'

    # Get user's read papers with timestamps from user DB
    read_papers = user_db.execute(
        "SELECT paper_id, read_at FROM user_read_history WHERE user_id = ? ORDER BY read_at DESC",
        [user_id]
    ).fetchdf()

    if read_papers.empty:
        return jsonify({"recommendations": [], "count": 0})

    # Calculate temporal weights (recent reads weighted more heavily)
    import datetime as dt
    now = dt.datetime.now()
    read_papers['days_ago'] = read_papers['read_at'].apply(
        lambda x: (now - x).days if isinstance(x, dt.datetime) else 365
    )

    # Exponential decay: papers read in last 30 days get 2x weight, 60 days get 1.5x, etc.
    read_papers['weight'] = read_papers['days_ago'].apply(
        lambda days: max(0.5, 2.0 * (0.5 ** (days / 30)))
    )

    read_paper_ids = read_papers['paper_id'].tolist()
    placeholders = ','.join(['?'] * len(read_paper_ids))

    # Create weighted lookup for papers (for citation scoring)
    paper_weights = dict(zip(read_papers['paper_id'], read_papers['weight']))

    recommendations = []

    if strategy in ['citation_graph', 'hybrid']:
        # Papers that cite papers user has read (query data DB)
        citing_papers = data_db.execute(f"""
            SELECT p.id, p.title, p.citation_count, p.categories, p.update_date, p.citations
            FROM papers p
            WHERE p.id NOT IN ({placeholders})
            AND list_has_any(p.citations, CAST([{placeholders}] AS VARCHAR[]))
            AND (p.deleted = false OR p.deleted IS NULL)
            LIMIT {limit * 3}
        """, read_paper_ids + read_paper_ids).fetchdf()

        for _, paper in citing_papers.iterrows():
            # Calculate temporal score: how many recently-read papers does this cite?
            cited_papers = paper['citations'] if paper['citations'] else []
            citation_weight = sum(
                paper_weights.get(cited_id, 0)
                for cited_id in cited_papers
                if cited_id in paper_weights
            )

            # Base score 0.9, boosted by temporal weight (can go up to ~1.8 for highly relevant recent citations)
            temporal_score = 0.9 + (citation_weight * 0.1)

            recommendations.append({
                'id': paper['id'],
                'title': paper['title'],
                'citation_count': int(paper['citation_count']),
                'categories': paper['categories'],
                'update_date': paper['update_date'],
                'reason': 'Cites papers in your reading history',
                'score': temporal_score
            })

    if strategy in ['topic_similarity', 'hybrid'] and len(recommendations) < limit * 2:
        # Get microtopics with temporal weighting
        user_microtopics = data_db.execute(f"""
            SELECT pm.microtopic_id, pm.paper_id
            FROM paper_microtopics pm
            WHERE pm.paper_id IN ({placeholders})
        """, read_paper_ids).fetchdf()

        if not user_microtopics.empty:
            # Calculate weight for each microtopic based on recency of papers that have it
            user_microtopics['weight'] = user_microtopics['paper_id'].map(paper_weights)
            microtopic_weights = user_microtopics.groupby('microtopic_id')['weight'].sum().to_dict()

            microtopic_ids = list(microtopic_weights.keys())
            topic_placeholders = ','.join(['?'] * len(microtopic_ids))

            similar_papers = data_db.execute(f"""
                SELECT p.id, p.title, p.citation_count, p.categories, p.update_date,
                       pm.microtopic_id
                FROM papers p
                INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
                WHERE pm.microtopic_id IN ({topic_placeholders})
                AND p.id NOT IN ({placeholders})
                AND (p.deleted = false OR p.deleted IS NULL)
                LIMIT {limit * 3}
            """, microtopic_ids + read_paper_ids).fetchdf()

            # Group by paper and calculate topic overlap weight
            for paper_id in similar_papers['id'].unique():
                paper_rows = similar_papers[similar_papers['id'] == paper_id]
                paper_data = paper_rows.iloc[0]

                # Sum weights of all shared microtopics
                topic_weight = sum(
                    microtopic_weights.get(mid, 0)
                    for mid in paper_rows['microtopic_id'].values
                )

                # Base score 0.7, boosted by topic weight (niche recent topics get higher scores)
                temporal_score = 0.7 + (topic_weight * 0.05)

                if paper_id not in [r['id'] for r in recommendations]:
                    recommendations.append({
                        'id': paper_data['id'],
                        'title': paper_data['title'],
                        'citation_count': int(paper_data['citation_count']),
                        'categories': paper_data['categories'],
                        'update_date': paper_data['update_date'],
                        'reason': 'Shares topics with your reading history',
                        'score': temporal_score
                    })

    # Sort by score (descending), then by citation count
    recommendations.sort(key=lambda x: (x['score'], x['citation_count']), reverse=True)

    return jsonify({
        "recommendations": recommendations[:limit],
        "count": len(recommendations[:limit])
    })