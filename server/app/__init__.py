from flask import Flask
from flask_cors import CORS

from .config import Config
from .db import init_app as init_db
from .routes.api import api_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
    )

    init_db(app)
    app.register_blueprint(api_bp, url_prefix="/api")
    return app
