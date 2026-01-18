import os

from flask import Flask
from flask_cors import CORS

from src.routes.analytics import analytics
from src.routes.authors import authors
from src.routes.frontend import frontend
from src.routes.health import health
from src.routes.papers import papers
from src.routes.users import users

app = Flask(__name__, static_folder=None)

app.register_blueprint(frontend)
app.register_blueprint(health)
app.register_blueprint(authors)
app.register_blueprint(papers)
app.register_blueprint(users)
app.register_blueprint(analytics)
CORS(app)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
