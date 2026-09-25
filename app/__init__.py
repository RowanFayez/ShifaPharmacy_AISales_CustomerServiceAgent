"""Flask application factory for Shifa Pharmacy."""

from flask import Flask

from app.blueprints.admin import admin_bp
from app.blueprints.chat import chat_bp
from app.blueprints.webhook import webhook_bp
from app.config import Config
from app.extensions import csrf, db, migrate
from app.services import messenger_service
from app import models  # noqa: F401 - imports models for Alembic metadata discovery


def create_app(config_object: type[Config] = Config) -> Flask:
    """Create the application and register its web interfaces."""
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Meta does not send browser CSRF tokens; the webhook verifies its HMAC
    # signature before accepting every inbound request instead.
    csrf.exempt(webhook_bp)

    app.register_blueprint(admin_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(webhook_bp)
    if not app.testing and messenger_service.is_configured(app.config):
        messenger_service.start_retry_worker(app)
    return app
