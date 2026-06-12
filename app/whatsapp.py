"""
Meta WhatsApp Cloud API — message sending helpers.
"""
import os
import requests
from flask import current_app

GRAPH_API_VERSION = "v19.0"


def _graph_url():
    phone_number_id = current_app.config["WHATSAPP_PHONE_NUMBER_ID"]
    return f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"


def _headers():
    token = current_app.config["WHATSAPP_ACCESS_TOKEN"]
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def send_text(to: str, message: str):
    """
    Send a plain text message via Meta WhatsApp Cloud API.
    `to` is a bare digit phone number (e.g. '919409688470') — same
    format already used throughout handlers.py.
    """
    clean_to = to.replace("whatsapp:", "").replace("+", "").strip()

    # Meta hard limit is 4096 chars per text message; split if needed
    MAX_LEN = 4000
    chunks = [message[i:i + MAX_LEN] for i in range(0, len(message), MAX_LEN)] or [""]

    last_resp = None
    for chunk in chunks:
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_to,
            "type": "text",
            "text": {"body": chunk, "preview_url": False},
        }
        try:
            resp = requests.post(_graph_url(), headers=_headers(), json=payload, timeout=15)
            if resp.status_code >= 400:
                current_app.logger.error(
                    f"WhatsApp send failed ({resp.status_code}): {resp.text}"
                )
            last_resp = resp
        except requests.RequestException as e:
            current_app.logger.error(f"WhatsApp send exception: {e}")

    return last_resp.json().get("messages", [{}])[0].get("id") if last_resp else None


def send_group_text(group_id: str, message: str):
    """Kept for compatibility — not used by Meta Cloud API directly."""
    return send_text(group_id, message)


# ─── Message Templates (UNCHANGED — keep as-is) ───────────────────────────────

def msg_new_match(match) -> str:
    return (
        f"⚽ *NEW MATCH — #{match.id}*\n\n"
        f"🆚 *{match.team1}* vs *{match.team2}*\n"
        f"🕐 Kickoff: {match.start_time.strftime('%d %b %Y %I:%M %p')}\n"
        f"🔒 Predictions close 5 mins before kickoff\n\n"
        f"Use */predict {match.id}* to submit your prediction\n"
        f"Use */copy {match.id}* to see the form"
    )


def msg_predict_form(match) -> str:
    return (
        f"📋 *Prediction Form — Match #{match.id}*\n"
        f"🆚 {match.team1} vs {match.team2}\n\n"
        f"Reply with:\n"
        f"Winner: [team name]\n"
        f"MVP: [player name]\n"
        f"Top1: [player name]\n"
        f"Top2: [player name]\n"
        f"Top3: [player name]\n"
        f"Score: [e.g. 2-1]\n\n"
        f"_Copy this and fill in your answers_"
    )


def msg_prediction_saved(user, match) -> str:
    return (
        f"✅ *Prediction Saved!*\n"
        f"Match: {match.team1} vs {match.team2}\n"
        f"Good luck, {user.name}! 🤞"
    )


def msg_score_result(user, match, result, score_result) -> str:
    b = score_result["breakdown"]
    lines = [
        f"📊 *Match Result — {match.team1} vs {match.team2}*\n",
        f"👤 Player: {user.name}",
        f"",
        f"✅ Winner: {'✔️' if b.get('winner') else '❌'} {'+' + str(b.get('winner',0)) + ' pts' if b.get('winner') else '0 pts'}",
        f"🌟 MVP: {'✔️' if b.get('mvp') else '❌'} {'+' + str(b.get('mvp',0)) + ' pts' if b.get('mvp') else '0 pts'}",
        f"👥 Top3: {b.get('top3_correct', score_result.get('top3_correct', 0))}/3 correct  +{b.get('top3', 0)} pts",
        f"🎯 Score: {'✔️' if b.get('score', 0) > 0 else '❌'} +{b.get('score', 0)} pts",
    ]
    if score_result["is_perfect"]:
        lines.append(f"💎 Perfect Bonus: +{b.get('perfect_bonus', 0)} pts")
    lines += [
        f"",
        f"🏅 *Total: {score_result['total']} pts*",
        f"📈 Career: {user.points} pts",
    ]
    return "\n".join(lines)


def msg_achievement(achievement) -> str:
    return (
        f"🎉 *Achievement Unlocked!*\n"
        f"{achievement.emoji} *{achievement.name}*\n"
        f"{achievement.description}\n"
        f"🪙 +{achievement.token_reward} Tokens rewarded!"
    )


def msg_leaderboard(users_top10) -> str:
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 *LEADERBOARD — TOP 10*\n"]
    for i, u in enumerate(users_top10):
        prefix = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{prefix} {u.name} — {u.points:,} pts")
    return "\n".join(lines)


def msg_profile(user) -> str:
    return (
        f"👤 *Your Profile*\n\n"
        f"📛 Name: {user.name}\n"
        f"🏅 Points: {user.points:,}\n"
        f"🪙 Tokens: {user.tokens:,}\n"
        f"📊 Predictions: {user.predictions_count}\n"
        f"💎 Perfect: {user.perfect_predictions}\n"
        f"🎖️ Achievements: {len(user.achievements)}"
    )


def msg_store() -> str:
    from .scoring import STORE_ITEMS
    lines = ["🏪 *POWER STORE*\n"]
    for key, item in STORE_ITEMS.items():
        lines.append(f"{item['name']} — {item['cost']} 🪙\n_{item['description']}_\nBuy: */buy {key}*\n")
    return "\n".join(lines)


def send_message(to, message):
    return send_text(to, message)