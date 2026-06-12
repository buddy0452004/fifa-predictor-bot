from flask import Flask
from .database import db
from .routes import webhook_bp, admin_bp
from .achievements import seed_achievements
import os

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "postgresql://localhost/predictor_db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["WHATSAPP_ACCESS_TOKEN"] = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
    app.config["WHATSAPP_PHONE_NUMBER_ID"] = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
    app.config["WHATSAPP_VERIFY_TOKEN"] = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")

    db.init_app(app)

    app.register_blueprint(webhook_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    with app.app_context():
        db.create_all()
        seed_achievements()

    return app
