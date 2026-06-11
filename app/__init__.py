from flask import Flask
from .database import db
from .routes import webhook_bp, admin_bp
from .achievements import seed_achievements
import os

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "postgresql://localhost/predictor_db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["TWILIO_ACCOUNT_SID"] = os.environ.get("TWILIO_ACCOUNT_SID", "")
    app.config["TWILIO_AUTH_TOKEN"] = os.environ.get("TWILIO_AUTH_TOKEN", "")
    app.config["TWILIO_WHATSAPP_NUMBER"] = os.environ.get("TWILIO_WHATSAPP_NUMBER", "")

    db.init_app(app)

    app.register_blueprint(webhook_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    with app.app_context():
        db.create_all()
        seed_achievements()

    return app
