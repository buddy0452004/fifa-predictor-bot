"""
Flask routes — webhook endpoint + admin endpoints.
"""
from flask import Blueprint, request, jsonify, current_app
from .handlers import handle_message
from .whatsapp import send_text

webhook_bp = Blueprint("webhook", __name__)
admin_bp = Blueprint("admin", __name__)


# ─── Home Route ───────────────────────────────────────────────────────────────

@webhook_bp.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "message": "FIFA Predictor WhatsApp Bot is running successfully!"
    }), 200


# ─── WhatsApp Webhook ─────────────────────────────────────────────────────────

@webhook_bp.route("/webhook", methods=["POST"])
def receive_message():
    """Receive incoming messages from Twilio WhatsApp."""
    phone = request.form.get("From", "").replace("whatsapp:", "").replace("+", "").strip()
    text = request.form.get("Body", "").strip()

    if not phone or not text:
        return jsonify({"status": "invalid_payload"}), 200

    try:
        reply = handle_message(phone, text)

        if reply:
            send_text(phone, reply)

    except Exception as e:
        current_app.logger.error(f"Webhook processing error: {e}")

    return jsonify({"status": "ok"}), 200


# ─── Admin REST API (for dashboard) ──────────────────────────────────────────

@admin_bp.route("/matches", methods=["GET"])
def list_matches():
    from .database import Match
    matches = Match.query.order_by(Match.start_time.desc()).limit(20).all()
    return jsonify([{
        "id": m.id, "team1": m.team1, "team2": m.team2,
        "start_time": m.start_time.isoformat(), "status": m.status
    } for m in matches])


@admin_bp.route("/leaderboard", methods=["GET"])
def leaderboard_api():
    from .database import User
    users = User.query.order_by(User.points.desc()).limit(20).all()
    return jsonify([{
        "name": u.name, "points": u.points, "tokens": u.tokens,
        "predictions": u.predictions_count, "perfect": u.perfect_predictions
    } for u in users])
