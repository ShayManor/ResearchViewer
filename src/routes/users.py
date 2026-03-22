from flask import Blueprint, request, jsonify
from src.database import get_user_db, get_data_db, df_to_json_serializable
from src.cache import cache
import hashlib
import secrets
import datetime

users_bp = Blueprint("users", __name__)


def clear_user_recommendations_cache(user_id):
    """Clear all cached recommendations for a specific user."""
    # For SimpleCache with @cache.cached(), we need to clear the internal cache
    # The simplest approach is to clear the entire cache or use a wildcard pattern

    # Since SimpleCache doesn't support wildcards, we'll clear common variations
    # and also use cache.clear() as a nuclear option for development

    # In production, you might want to use Redis with key patterns instead
    cache.clear()  # Clear all cache - simple but effective for development

    # Alternatively, if cache.clear() is too aggressive, uncomment below:
    # Common query parameter combinations
    # query_variations = [
    #     '', 'limit=10', 'limit=20',
    #     'limit=10&strategy=hybrid', 'limit=10&strategy=citations',
    #     'limit=10&strategy=topics', 'strategy=hybrid',
    # ]
    # for query in query_variations:
    #     if query:
    #         key = f'view//api/users/{user_id}/recommendations?{query}'
    #     else:
    #         key = f'view//api/users/{user_id}/recommendations'
    #     cache.delete(key)


def hash_password(password: str) -> str:
    """Hash password with embedded salt using SHA-256."""
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


@users_bp.route("/api/auth/register", methods=["POST"])
def register():
    """Create account with username, email, password."""
    db = get_user_db()
    data = request.get_json()

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    focus_topics = data.get('focus_topics', [])

    if not username or not email or not password:
        return jsonify({"error": "Username, email and password are required"}), 400

    # Check if username or email already exists
    existing = db.execute(
        "SELECT COUNT(*) FROM users WHERE username = ? OR email = ?",
        [username, email]
    ).fetchone()[0]

    if existing > 0:
        return jsonify({"error": "Username or email already exists"}), 409

    # Hash password
    password_hash = hash_password(password)

    # Get next user ID from sequence
    max_id = db.execute("SELECT nextval('users_id_seq')").fetchone()[0]

    # Create user
    db.execute("""
        INSERT INTO users (id, username, email, password_hash, focus_topics, created_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, [max_id, username, email, password_hash, focus_topics])

    # Generate session token
    session_token = secrets.token_urlsafe(32)

    return jsonify({
        "user_id": max_id,
        "username": username,
        "session_token": session_token
    }), 201


@users_bp.route("/api/auth/login", methods=["POST"])
def login():
    """Authenticate user."""
    db = get_user_db()
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

    # Generate session token
    session_token = secrets.token_urlsafe(32)

    return jsonify({
        "user_id": user_id,
        "username": username,
        "session_token": session_token
    })


@users_bp.route("/api/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Get user profile with all statistics."""
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

    # Reading over time from user DB
    reading_over_time = user_db.execute("""
        SELECT
            strftime(read_at, '%Y-%m') as month,
            COUNT(*) as count
        FROM user_read_history
        WHERE user_id = ?
        GROUP BY month
        ORDER BY month
    """, [user_id]).fetchdf()

    user_data['reading_over_time'] = df_to_json_serializable(reading_over_time) if not reading_over_time.empty else []

    return jsonify(user_data)


@users_bp.route("/api/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    """Update profile fields."""
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


@users_bp.route("/api/users/<int:user_id>/link-author", methods=["PUT"])
def link_author(user_id):
    """Link an author profile to user account and import their publications."""
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
                    except Exception as insert_error:
                        print(f"ERROR inserting publication: {insert_error}")
                        print(f"  user_id={user_id}, type={type(user_id)}")
                        print(f"  title={title}, type={type(title)}")
                        print(f"  venue={venue}, type={type(venue)}")
                        print(f"  year={year}, type={type(year)}")
                        print(f"  doi={doi}, type={type(doi)}")
                        print(f"  citation_count={citation_count}, type={type(citation_count)}")
                        print(f"  coauthors={coauthors}, type={type(coauthors)}")
                        import traceback
                        traceback.print_exc()
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
                "total_citations": total_citations,
                "message": f"Imported {publications_imported} of {len(paper_dois)} publications" +
                          (f" ({publications_not_found} not found in database)" if publications_not_found > 0 else "")
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
def unlink_author(user_id):
    """Unlink author profile from user account."""
    db = get_user_db()

    db.execute(
        "UPDATE users SET linked_author_id = NULL WHERE id = ?",
        [user_id]
    )

    return jsonify({"status": "unlinked"})


@users_bp.route("/api/users/<int:user_id>/reading-list", methods=["GET"])
def get_reading_list(user_id):
    """Get user's reading list."""
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
def add_to_reading_list(user_id):
    """Add paper to reading list."""
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

    # Clear recommendations cache since reading list changed
    clear_user_recommendations_cache(user_id)

    return jsonify({"status": "added", "paper_id": paper_id}), 201


@users_bp.route("/api/users/<int:user_id>/reading-list/<path:paper_id>", methods=["DELETE"])
def remove_from_reading_list(user_id, paper_id):
    """Remove paper from reading list."""
    db = get_user_db()

    db.execute(
        "DELETE FROM user_reading_list WHERE user_id = ? AND paper_id = ?",
        [user_id, paper_id]
    )

    # Clear recommendations cache since reading list changed
    clear_user_recommendations_cache(user_id)

    return jsonify({"status": "removed"})


@users_bp.route("/api/users/<int:user_id>/read-history", methods=["GET"])
def get_read_history(user_id):
    """Get user's read history."""
    user_db = get_user_db()
    data_db = get_data_db()

    sort_by = request.args.get('sort_by', 'read_at')
    sort_order = request.args.get('sort_order', 'DESC')
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 50)), 100)

    # Validate sort field
    allowed_sorts = ['read_at', 'citation_count']
    if sort_by not in allowed_sorts:
        sort_by = 'read_at'

    if sort_order not in ['ASC', 'DESC']:
        sort_order = 'DESC'

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
def add_to_read_history(user_id):
    """Mark a paper as read."""
    db = get_user_db()
    data = request.get_json()

    paper_id = data.get('paper_id')
    read_at = data.get('read_at', datetime.date.today().isoformat())

    if not paper_id:
        return jsonify({"error": "paper_id is required"}), 400

    # Check if already added
    existing = db.execute(
        "SELECT COUNT(*) FROM user_read_history WHERE user_id = ? AND paper_id = ?",
        [user_id, paper_id]
    ).fetchone()[0]

    if existing > 0:
        return jsonify({"status": "already_exists"}), 200

    # Add to read history
    db.execute(
        "INSERT INTO user_read_history (user_id, paper_id, read_at) VALUES (?, ?, ?)",
        [user_id, paper_id, read_at]
    )

    # Clear recommendations cache since read history changed
    clear_user_recommendations_cache(user_id)

    return jsonify({"status": "added"}), 201


@users_bp.route("/api/users/<int:user_id>/read-history/<path:paper_id>", methods=["DELETE"])
def remove_from_read_history(user_id, paper_id):
    """Un-mark a paper as read."""
    db = get_user_db()

    db.execute(
        "DELETE FROM user_read_history WHERE user_id = ? AND paper_id = ?",
        [user_id, paper_id]
    )

    # Clear recommendations cache since read history changed
    clear_user_recommendations_cache(user_id)

    return jsonify({"status": "removed"})


@users_bp.route("/api/users/<int:user_id>/publications", methods=["GET"])
def get_publications(user_id):
    """Get user's publications."""
    user_db = get_user_db()

    result = user_db.execute("""
        SELECT id, title, venue, year, doi, citation_count, coauthors
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
def add_publication(user_id):
    """Add a publication."""
    db = get_user_db()
    data = request.get_json()

    title = data.get('title')
    venue = data.get('venue')
    year = data.get('year')
    doi = data.get('doi')
    citation_count = data.get('citation_count', 0)
    coauthors = data.get('coauthors', [])

    if not title or not year:
        return jsonify({"error": "Title and year are required"}), 400

    try:
        # Insert publication (ID will be auto-generated by sequence)
        # Use RETURNING to get the generated ID
        result = db.execute("""
            INSERT INTO user_publications
            (user_id, title, venue, year, doi, citation_count, coauthors)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        """, [user_id, title, venue, year, doi, citation_count, coauthors]).fetchone()

        new_id = result[0]

        return jsonify({"status": "created", "id": new_id}), 201

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to add publication", "details": str(e)}), 500


@users_bp.route("/api/users/<int:user_id>/publications/<int:pub_id>", methods=["PUT"])
def update_publication(user_id, pub_id):
    """Update a publication entry."""
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

    allowed_fields = ['title', 'venue', 'year', 'doi', 'citation_count', 'coauthors']
    for field in allowed_fields:
        if field in data:
            update_fields.append(f'{field} = ?')
            params.append(data[field])

    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    params.extend([pub_id, user_id])
    query = f"UPDATE user_publications SET {', '.join(update_fields)} WHERE id = ? AND user_id = ?"

    db.execute(query, params)

    return jsonify({"status": "updated"})


@users_bp.route("/api/users/<int:user_id>/publications/<int:pub_id>", methods=["DELETE"])
def delete_publication(user_id, pub_id):
    """Delete a publication."""
    db = get_user_db()

    db.execute(
        "DELETE FROM user_publications WHERE id = ? AND user_id = ?",
        [pub_id, user_id]
    )

    return jsonify({"status": "deleted"})


@users_bp.route("/api/users/<int:user_id>/recommendations", methods=["GET"])
@cache.cached(timeout=600, query_string=True)
def get_recommendations(user_id):
    """Get recommended papers based on reading history and topics."""
    user_db = get_user_db()
    data_db = get_data_db()

    limit = int(request.args.get('limit', 10))
    strategy = request.args.get('strategy', 'hybrid')

    # Get user's read papers from user DB
    read_papers = user_db.execute(
        "SELECT paper_id FROM user_read_history WHERE user_id = ?",
        [user_id]
    ).fetchdf()

    if read_papers.empty:
        return jsonify({"recommendations": [], "count": 0})

    read_paper_ids = read_papers['paper_id'].tolist()
    placeholders = ','.join(['?'] * len(read_paper_ids))

    recommendations = []

    if strategy in ['citation_graph', 'hybrid']:
        # Papers that cite papers user has read (query data DB)
        # Optimized: Use list_has_any instead of UNNEST for better performance
        citing_papers = data_db.execute(f"""
            SELECT DISTINCT p.id, p.title, p.citation_count, p.categories, p.update_date
            FROM papers p
            WHERE p.id NOT IN ({placeholders})
            AND list_has_any(p.citations, CAST([{placeholders}] AS VARCHAR[]))
            AND (p.deleted = false OR p.deleted IS NULL)
            ORDER BY p.citation_count DESC
            LIMIT ?
        """, read_paper_ids + read_paper_ids + [limit]).fetchdf()

        for _, paper in citing_papers.iterrows():
            recommendations.append({
                'id': paper['id'],
                'title': paper['title'],
                'citation_count': int(paper['citation_count']),
                'categories': paper['categories'],
                'update_date': paper['update_date'],
                'reason': 'Cites papers in your reading history',
                'score': 0.9
            })

    if strategy in ['topic_similarity', 'hybrid'] and len(recommendations) < limit:
        # Papers sharing microtopics with read papers (query data DB)
        # Optimized: Materialize microtopics first, then join
        # Get microtopics from read papers
        user_microtopics = data_db.execute(f"""
            SELECT DISTINCT microtopic_id
            FROM paper_microtopics
            WHERE paper_id IN ({placeholders})
        """, read_paper_ids).fetchdf()

        if not user_microtopics.empty:
            microtopic_ids = user_microtopics['microtopic_id'].tolist()
            topic_placeholders = ','.join(['?'] * len(microtopic_ids))

            similar_papers = data_db.execute(f"""
                SELECT DISTINCT p.id, p.title, p.citation_count, p.categories, p.update_date
                FROM papers p
                INNER JOIN paper_microtopics pm ON p.id = pm.paper_id
                WHERE pm.microtopic_id IN ({topic_placeholders})
                AND p.id NOT IN ({placeholders})
                AND (p.deleted = false OR p.deleted IS NULL)
                ORDER BY p.citation_count DESC
                LIMIT ?
            """, microtopic_ids + read_paper_ids + [limit - len(recommendations)]).fetchdf()
        else:
            # No microtopics found, return empty dataframe
            import pandas as pd
            similar_papers = pd.DataFrame(columns=['id', 'title', 'citation_count', 'categories', 'update_date'])

        for _, paper in similar_papers.iterrows():
            if paper['id'] not in [r['id'] for r in recommendations]:
                recommendations.append({
                    'id': paper['id'],
                    'title': paper['title'],
                    'citation_count': int(paper['citation_count']),
                    'categories': paper['categories'],
                    'update_date': paper['update_date'],
                    'reason': 'Shares topics with your reading history',
                    'score': 0.7
                })

    return jsonify({
        "recommendations": recommendations[:limit],
        "count": len(recommendations[:limit])
    })