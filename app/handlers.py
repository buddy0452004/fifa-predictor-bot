"""
Command handlers — parse commands from incoming WhatsApp messages.
"""
from datetime import datetime, timedelta
from .database import db, User, Match, Prediction, Result, Inventory
from .scoring import calculate_score, STORE_ITEMS
from .achievements import check_and_award
from .whatsapp import (
    send_text,
    msg_new_match, msg_predict_form, msg_prediction_saved,
    msg_score_result, msg_achievement, msg_leaderboard,
    msg_profile, msg_store,
)

# ─── Admin Commands ────────────────────────────────────────────────────────────

import os
ADMIN_PHONES = [p.strip() for p in os.environ.get("ADMIN_PHONES","").split(",") if p.strip()]


def is_admin(phone: str) -> bool:
    return phone in ADMIN_PHONES


def handle_create_match(phone: str, text: str) -> str:
    """
    /creatematch
    Team1: PSG
    Team2: Real Madrid
    Date: 11 Jul 2026
    Time: 00:30
    """
    if not is_admin(phone):
        return "❌ Admin only command."

    lines = {l.split(":")[0].strip().lower(): l.split(":", 1)[1].strip()
             for l in text.strip().split("\n") if ":" in l}

    team1 = lines.get("team1")
    team2 = lines.get("team2")
    date_str = lines.get("date")
    time_str = lines.get("time", "00:00")

    if not all([team1, team2, date_str]):
        return "❌ Format:\n/creatematch\nTeam1: PSG\nTeam2: Real Madrid\nDate: 11 Jul 2026\nTime: 00:30"

    try:
        start_time = datetime.strptime(f"{date_str} {time_str}", "%d %b %Y %H:%M")
    except ValueError:
        return "❌ Date format error. Use: 11 Jul 2026"

    match = Match(team1=team1, team2=team2, start_time=start_time, status="open")
    db.session.add(match)
    db.session.commit()

    return msg_new_match(match)


def handle_result(phone: str, text: str) -> str:
    """
    /result 101
    Winner: PSG
    MVP: Dembele
    Top1: Dembele
    Top2: Hakimi
    Top3: Fabian Ruiz
    Score: 3-1
    """
    if not is_admin(phone):
        return "❌ Admin only command."

    parts = text.strip().split("\n")
    first_line = parts[0].strip()
    match_id_str = first_line.replace("/result", "").strip()

    try:
        match_id = int(match_id_str)
    except ValueError:
        return "❌ Usage: /result [match_id]\nThen fill Winner, MVP, Top1, Top2, Top3, Score"

    match = Match.query.get(match_id)
    if not match:
        return f"❌ Match #{match_id} not found."

    lines = {l.split(":")[0].strip().lower(): l.split(":", 1)[1].strip()
             for l in parts[1:] if ":" in l}

    result = Result(
        match_id=match_id,
        winner=lines.get("winner"),
        mvp=lines.get("mvp"),
        top1=lines.get("top1"),
        top2=lines.get("top2"),
        top3=lines.get("top3"),
        score=lines.get("score"),
    )
    db.session.add(result)
    match.status = "completed"
    db.session.commit()

    # Score all predictions for this match
    predictions = Prediction.query.filter_by(match_id=match_id).all()
    responses = [f"✅ Result entered for Match #{match_id}\n📊 Scoring {len(predictions)} predictions...\n"]

    for pred in predictions:
        user = User.query.get(pred.user_id)
        # Check active powers
        active_powers = []
        for power in ["double_points", "score_shield"]:
            inv = Inventory.query.filter_by(user_id=user.id, power=power).first()
            # In a real system, you'd check if power was activated for this match
        
        score_result = calculate_score(pred, result, active_powers)
        pred.points_awarded = score_result["total"]
        user.points += score_result["total"]
        if score_result["is_perfect"]:
            user.perfect_predictions += 1

        newly_awarded = check_and_award(user, pred, score_result)

        # Send personal DM to user
        try:
            send_text(user.phone, msg_score_result(user, match, result, score_result))
            for ach in newly_awarded:
                send_text(user.phone, msg_achievement(ach))
        except Exception:
            pass  # Don't fail if DM fails

    db.session.commit()
    return "\n".join(responses) + "✅ All scores updated!"


# ─── User Commands ────────────────────────────────────────────────────────────

def handle_predict(phone: str, text: str) -> str:
    """
    /predict 101
    Winner: PSG
    MVP: Dembele
    Top1: Dembele
    Top2: Hakimi
    Top3: Fabian Ruiz
    Score: 3-1
    """
    lines_raw = text.strip().split("\n")
    first = lines_raw[0].strip()
    match_id_str = first.replace("/predict", "").strip()

    try:
        match_id = int(match_id_str)
    except ValueError:
        return "❌ Usage: /predict [match_id]\nThen fill Winner, MVP, Top1, Top2, Top3, Score"

    match = Match.query.get(match_id)
    if not match:
        return f"❌ Match #{match_id} not found."
    if match.status != "open":
        return "🔒 Predictions are closed for this match."
    if datetime.utcnow() >= match.start_time - timedelta(minutes=5):
        match.status = "closed"
        db.session.commit()
        return "🔒 Predictions closed — too close to kickoff!"

    lines = {l.split(":")[0].strip().lower(): l.split(":", 1)[1].strip()
             for l in lines_raw[1:] if ":" in l}

    required = ["winner", "mvp", "top1", "top2", "top3", "score"]
    missing = [r for r in required if not lines.get(r)]
    if missing:
        return f"❌ Missing fields: {', '.join(missing)}"

    # Get or create user
    user = User.query.filter_by(phone=phone).first()
    is_new = user is None
    if is_new:
        name = phone[-4:]  # default name from last 4 digits, user can change with /setname
        user = User(phone=phone, name=f"Player_{name}")
        db.session.add(user)
        db.session.flush()

    # Check for duplicate
    existing = Prediction.query.filter_by(user_id=user.id, match_id=match_id).first()
    if existing:
        # Update prediction
        existing.winner = lines["winner"]
        existing.mvp = lines["mvp"]
        existing.top1 = lines["top1"]
        existing.top2 = lines["top2"]
        existing.top3 = lines["top3"]
        existing.score = lines["score"]
        db.session.commit()
        return f"🔄 Prediction updated for Match #{match_id}!\n\nGood luck, {user.name}! 🤞"

    pred = Prediction(
        user_id=user.id,
        match_id=match_id,
        winner=lines["winner"],
        mvp=lines["mvp"],
        top1=lines["top1"],
        top2=lines["top2"],
        top3=lines["top3"],
        score=lines["score"],
    )
    db.session.add(pred)
    user.predictions_count += 1
    db.session.commit()

    return msg_prediction_saved(user, match)


def handle_copy(phone: str, text: str) -> str:
    match_id_str = text.replace("/copy", "").strip()
    try:
        match_id = int(match_id_str)
    except ValueError:
        # Show latest open match
        match = Match.query.filter_by(status="open").order_by(Match.start_time).first()
        if not match:
            return "❌ No open matches right now."
        return msg_predict_form(match)

    match = Match.query.get(match_id)
    if not match:
        return f"❌ Match #{match_id} not found."
    return msg_predict_form(match)


def handle_profile(phone: str) -> str:
    user = User.query.filter_by(phone=phone).first()
    if not user:
        return "❌ No profile yet. Submit a prediction first!"
    return msg_profile(user)


def handle_leaderboard() -> str:
    top10 = User.query.order_by(User.points.desc()).limit(10).all()
    if not top10:
        return "🏆 No players yet!"
    return msg_leaderboard(top10)


def handle_store() -> str:
    return msg_store()


def handle_buy(phone: str, text: str) -> str:
    power_key = text.replace("/buy", "").strip().lower()
    if power_key not in STORE_ITEMS:
        items = ", ".join(STORE_ITEMS.keys())
        return f"❌ Unknown item. Available: {items}"

    user = User.query.filter_by(phone=phone).first()
    if not user:
        return "❌ No profile found. Make a prediction first!"

    item = STORE_ITEMS[power_key]
    if user.tokens < item["cost"]:
        return f"❌ Not enough tokens! You have {user.tokens} 🪙, need {item['cost']} 🪙"

    user.tokens -= item["cost"]
    inv = Inventory.query.filter_by(user_id=user.id, power=power_key).first()
    if inv:
        inv.quantity += 1
    else:
        inv = Inventory(user_id=user.id, power=power_key, quantity=1)
        db.session.add(inv)
    db.session.commit()
    return f"✅ Purchased {item['name']}!\n🪙 Remaining tokens: {user.tokens}"


def handle_inventory(phone: str) -> str:
    user = User.query.filter_by(phone=phone).first()
    if not user:
        return "❌ No profile found."
    items = Inventory.query.filter_by(user_id=user.id).all()
    if not items:
        return "🎒 Your inventory is empty.\nVisit */store* to buy powers!"
    lines = ["🎒 *Your Inventory*\n"]
    for inv in items:
        item = STORE_ITEMS.get(inv.power, {})
        lines.append(f"{item.get('name', inv.power)} x{inv.quantity}")
    lines.append(f"\nUse: */use [power_name] [match_id]*")
    return "\n".join(lines)


def handle_use(phone: str, text: str) -> str:
    parts = text.replace("/use", "").strip().split()
    if len(parts) < 2:
        return "❌ Usage: /use [power] [match_id]"
    power_key, match_id_str = parts[0], parts[1]

    try:
        match_id = int(match_id_str)
    except ValueError:
        return "❌ Invalid match ID"

    user = User.query.filter_by(phone=phone).first()
    if not user:
        return "❌ No profile found."

    inv = Inventory.query.filter_by(user_id=user.id, power=power_key).first()
    if not inv or inv.quantity < 1:
        return f"❌ You don't have any {power_key}. Buy from */store*"

    match = Match.query.get(match_id)
    if not match or match.status != "open":
        return "❌ Match not found or predictions are closed."

    # Mark power as activated (in real system store in a MatchPower table)
    inv.quantity -= 1
    db.session.commit()
    item = STORE_ITEMS.get(power_key, {})
    return f"⚡ *{item.get('name', power_key)}* activated for Match #{match_id}!\n{item.get('description', '')}"


def handle_setname(phone: str, text: str) -> str:
    name = text.replace("/setname", "").strip()
    if not name or len(name) < 2:
        return "❌ Usage: /setname YourName"
    user = User.query.filter_by(phone=phone).first()
    if not user:
        return "❌ No profile yet. Make a prediction first!"
    user.name = name[:50]
    db.session.commit()
    return f"✅ Name updated to *{user.name}*!"
