"""Application factory."""

import uuid

from flask import Flask, g, request

from app.config.container import build_container
from app.config.logging_config import configure_logging
from app.utils.logging_context import (
    clear_job_id,
    clear_request_id,
    set_request_id,
)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    container = build_container()
    configure_logging(app_type="web", log_level=container.settings.log_level)

    app = Flask(__name__)
    app.config["SECRET_KEY"] = container.settings.secret_key
    app.config["MAX_CONTENT_LENGTH"] = container.settings.max_content_length
    app.container = container

    _register_request_hooks(app)
    _register_blueprints(app, container)
    return app


def _register_request_hooks(app: Flask) -> None:
    """Register per-request MDC context hooks."""

    @app.before_request
    def before_request() -> None:
        """Seed request-scoped logging context."""
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        g.request_id = request_id
        set_request_id(request_id)
        clear_job_id()

    @app.after_request
    def after_request(response):
        """Expose request id back to the caller."""
        response.headers["X-Request-Id"] = getattr(g, "request_id", "-")
        return response

    @app.teardown_request
    def teardown_request(_exc) -> None:
        """Clear request-scoped logging context."""
        clear_request_id()
        clear_job_id()


def _register_blueprints(app: Flask, container) -> None:
    """Register controller blueprints."""
    app.register_blueprint(container.ui_controller.blueprint)
    app.register_blueprint(container.api_controller.blueprint)
    app.register_blueprint(container.health_controller.blueprint)