"""Health and status routes."""

from flask import Blueprint, current_app, jsonify

health_blueprint = Blueprint("health", __name__)


@health_blueprint.get("/health")
def health():
    """Return basic health information."""
    return jsonify({"status": "ok"})


@health_blueprint.get("/status")
def status():
    """Return lightweight runtime status information."""
    container = current_app.config["APP_CONTAINER"]
    outputs = container.output_repository.list_outputs()
    return jsonify({"status": "ok", "output_count": len(outputs), "redis_configured": bool(container.settings.redis_url)})
