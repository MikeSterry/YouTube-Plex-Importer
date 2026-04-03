"""App factory and dependency wiring."""

from __future__ import annotations

import logging
import uuid

from flask import Flask, g, jsonify, request

from app.config.container import build_container
from app.config.logging_config import configure_logging
from app.controllers.api_controller import api_blueprint
from app.controllers.health_controller import health_blueprint
from app.controllers.ui_controller import ui_blueprint
from app.exceptions import AppError
from app.utils.logging_context import (
    clear_job_id,
    clear_request_id,
    set_request_id,
)

LOGGER = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    container = build_container()
    configure_logging(app_type="web", log_level=container.settings.log_level)

    app = Flask(__name__)
    app.config["APP_CONTAINER"] = container
    app.config["SECRET_KEY"] = container.settings.secret_key
    app.config["MAX_CONTENT_LENGTH"] = container.settings.max_content_length
    app.container = container

    _register_request_hooks(app)
    _register_error_handlers(app)
    _register_blueprints(app)
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


def _register_error_handlers(app: Flask) -> None:
    """Register JSON error handlers for API routes."""

    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        """Return structured responses for known application errors."""
        payload = error.to_payload()
        if request.blueprint == "api":
            return jsonify(payload.to_dict()), payload.status_code
        raise error

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        """Return a predictable JSON 500 response for unhandled API exceptions."""
        LOGGER.exception("Unhandled application error", exc_info=error)
        if request.blueprint == "api":
            return (
                jsonify(
                    {
                        "error": "An unexpected server error occurred.",
                        "code": "internal_server_error",
                        "status_code": 500,
                    }
                ),
                500,
            )
        raise error


def _register_blueprints(app: Flask) -> None:
    """Register all application blueprints."""
    app.register_blueprint(ui_blueprint)
    app.register_blueprint(api_blueprint)
    app.register_blueprint(health_blueprint)