import os

from flask import Flask
from flask_cors import CORS

from src.routes.frontend import frontend

app = Flask(__name__, static_folder=None)

app.register_blueprint(frontend)
CORS(app)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
