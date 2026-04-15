import os
import atexit
import signal

from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_compress import Compress
from flask_swagger_ui import get_swaggerui_blueprint
import flask_monitoringdashboard as dashboard

from src.database import init_app as init_database, close_db
from src.cache import cache
from src.routes.analytics import analytics
from src.routes.authors import authors_bp
from src.routes.frontend import frontend
from src.routes.health import health
from src.routes.microtopics import microtopics_bp
from src.routes.papers import papers_bp
from src.routes.reports import reports_bp
from src.routes.users import users_bp
from src.routes.spec import spec_bp

app = Flask(__name__, static_folder=None)
Compress(app)

# Configure monitoring dashboard (bind later after routes are registered)
dashboard.config.init_from(file='config.cfg')

# Initialize database connection
init_database(app)

# Initialize caching
cache.init_app(app, config={
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 300  # 5 minutes default
})

# Graceful shutdown for containers
def shutdown_handler(signum, frame):
    app.logger.info("Shutting down gracefully...")
    close_db()
    exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)
atexit.register(close_db)

# Register spec blueprint FIRST (highest priority)
app.register_blueprint(spec_bp)

# Register API blueprints
app.register_blueprint(health)
app.register_blueprint(authors_bp)
app.register_blueprint(papers_bp)
app.register_blueprint(users_bp)
app.register_blueprint(microtopics_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(analytics)

# Configure Swagger UI blueprint
SWAGGER_URL = '/api'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    '/api/openapi.json',
    config={
        'app_name': "ResearchViewer API"
    }
)
app.register_blueprint(swaggerui_blueprint)

# Frontend must be registered LAST (catch-all route)
app.register_blueprint(frontend)

# Bind monitoring dashboard AFTER all routes are registered
dashboard.bind(app)


def _sync_dashboard_password():
    """Force the flask-monitoringdashboard admin user to match config on every boot.

    flask-monitoringdashboard only reads config.password when its User table is empty
    (see flask_monitoringdashboard/database/auth.py). That means rotating
    DASHBOARD_PASSWORD has no effect on an existing monitoring.db. We re-sync the
    password (and create the user if missing) every time the app starts so the
    secret pulled by deploy.sh is always the source of truth.
    """
    from flask_monitoringdashboard import config as fmd_config
    from flask_monitoringdashboard.database import User, session_scope

    try:
        with session_scope() as session:
            user = session.query(User).filter(User.username == fmd_config.username).one_or_none()
            if user is None:
                user = User(username=fmd_config.username, is_admin=True)
                user.set_password(password=fmd_config.password)
                session.add(user)
                app.logger.info("Dashboard user '%s' created from config", fmd_config.username)
            else:
                user.set_password(password=fmd_config.password)
                user.is_admin = True
                app.logger.info("Dashboard user '%s' password re-synced from config", fmd_config.username)
    except Exception as exc:
        app.logger.warning("Could not sync dashboard password: %s", exc)


_sync_dashboard_password()

CORS(app)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, threaded=False)
