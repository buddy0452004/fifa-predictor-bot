"""
Flask routes — webhook endpoint + admin endpoints.
"""
from flask import Blueprint, request, jsonify, current_app
from .handlers import (
    handle_create_match, handle_result,
    handle_predict, handle_copy, handle_profile,
    handle_leaderboard, handle_store, handle_buy,
    handle_inventory, handle_use, handle_setname,
)
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
        reply = dispatch_command(phone, text)

        if reply:
            send_text(phone, reply)

    except Exception as e:
        current_app.logger.error(f"Webhook processing error: {e}")

    return jsonify({"status": "ok"}), 200


def dispatch_command(phone: str, text: str) -> str:
    """Route incoming text to the correct handler."""
    lower = text.lower().strip()

    if lower.startswith("/creatematch"):
        return handle_create_match(phone, text)
    elif lower.startswith("/result"):
        return handle_result(phone, text)
    elif lower.startswith("/predict"):
        return handle_predict(phone, text)
    elif lower.startswith("/copy"):
        return handle_copy(phone, text)
    elif lower.startswith("/profile"):
        return handle_profile(phone)
    elif lower.startswith("/leaderboard"):
        return handle_leaderboard()
    elif lower.startswith("/store"):
        return handle_store()
    elif lower.startswith("/buy"):
        return handle_buy(phone, text)
    elif lower.startswith("/inventory"):
        return handle_inventory(phone)
    elif lower.startswith("/use"):
        return handle_use(phone, text)
    elif lower.startswith("/setname"):
        return handle_setname(phone, text)
    elif lower in ("/help", "help", "/start"):
        return (
            "⚽ *FIFA Predictor Bot — Commands*\n\n"
            "*/predict [id]* — Submit prediction\n"
            "*/copy [id]* — Get prediction form\n"
            "*/profile* — Your stats\n"
            "*/leaderboard* — Top 10 players\n"
            "*/store* — Buy power-ups\n"
            "*/buy [item]* — Purchase item\n"
            "*/inventory* — Your items\n"
            "*/use [item] [match_id]* — Use a power\n"
            "*/setname [name]* — Set display name\n\n"
            "_Admin: /creatematch | /result_"
        )

    return None  # ignore non-commands


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
