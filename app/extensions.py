"""Flask extensions initialized once and bound in the application factory."""

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect


db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
