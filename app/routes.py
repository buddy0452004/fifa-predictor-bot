"""
Flask routes — webhook endpoint + admin endpoints.
"""
import os
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


# ─── Meta Webhook Verification (GET) ──────────────────────────────────────────

@webhook_bp.route("/webhook", methods=["GET"])
def verify_webhook():
    """
    Meta calls this once when setting up the webhook in the App Dashboard.
    Must echo hub.challenge back if hub.verify_token matches our configured token.
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    expected_token = current_app.config["WHATSAPP_VERIFY_TOKEN"]

    if mode == "subscribe" and token == expected_token:
        current_app.logger.info("Webhook verified successfully.")
        return challenge, 200

    current_app.logger.warning("Webhook verification failed.")
    return "Verification failed", 403


# ─── WhatsApp Webhook (POST — Meta Cloud API) ────────────────────────────────

@webhook_bp.route("/webhook", methods=["POST"])
def receive_message():
    """Receive incoming messages from Meta WhatsApp Cloud API."""
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"status": "invalid_payload"}), 200

    try:
        entries = data.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages")

                # Status updates (sent/delivered/read) have no "messages" key — ignore
                if not messages:
                    continue

                for message in messages:
                    sender = message.get("from", "")  # bare digits, e.g. "919409688470"
                    phone = sender.replace("whatsapp:", "").replace("+", "").strip()

                    msg_type = message.get("type")
                    if msg_type == "text":
                        text = message.get("text", {}).get("body", "").strip()
                    else:
                        # Non-text message (image, button reply, etc.)
                        send_text(phone, "🤔 I can only understand text commands. Type */help* for options.")
                        continue

                    if not phone or not text:
                        continue

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
