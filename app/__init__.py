"""App factory and dependency wiring."""

from flask import Flask

from app.config.container import build_container
from app.controllers.api_controller import api_blueprint
from app.controllers.health_controller import health_blueprint
from app.controllers.ui_controller import ui_blueprint


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    container = build_container()
    app.config["APP_CONTAINER"] = container
    app.config["SECRET_KEY"] = container.settings.secret_key
    app.config["MAX_CONTENT_LENGTH"] = container.settings.max_content_length
    register_blueprints(app)
    return app



def register_blueprints(app: Flask) -> None:
    """Register all application blueprints."""
    app.register_blueprint(ui_blueprint)
    app.register_blueprint(api_blueprint)
    app.register_blueprint(health_blueprint)
