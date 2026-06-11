"""
Command handlers — parse commands from incoming WhatsApp messages.
"""

import json
import re
import shlex
from datetime import datetime
from .database import db, User, Match, Prediction, Result, Inventory, TournamentPick, ConversationSession
from .scoring import calculate_score, STORE_ITEMS
from .achievements import check_and_award
from .whatsapp import send_message

# ─────────────────────────────────────────────
#  CONVERSATION STATE  (DB-backed, survives restarts)
#  Uses ConversationSession model in database.py
# ─────────────────────────────────────────────

def get_session(phone):
    row = ConversationSession.query.filter_by(phone=phone).first()
    if not row:
        return None
    return {"flow": row.flow, "step": row.step, "data": json.loads(row.data)}


def set_session(phone, flow, step, data=None):
    row = ConversationSession.query.filter_by(phone=phone).first()
    if row:
        row.flow = flow
        row.step = step
        row.data = json.dumps(data or {})
    else:
        row = ConversationSession(phone=phone, flow=flow, step=step, data=json.dumps(data or {}))
        db.session.add(row)
    db.session.commit()


def clear_session(phone):
    ConversationSession.query.filter_by(phone=phone).delete()
    db.session.commit()


# ─────────────────────────────────────────────
#  TOURNAMENT CONFIG
# ─────────────────────────────────────────────

ROUND_POINTS = {
    "round_of_16": 500,
    "quarterfinal": 1000,
    "semifinal": 2500,
    "final": 5000,
    "champion": 10000,
}

ROUND_LABELS = {
    "round_of_16":  "⚽ Round of 16",
    "quarterfinal": "🔥 Quarter-Final",
    "semifinal":    "🌟 Semi-Final",
    "final":        "🏆 Final",
    "champion":     "👑 Champion",
}

TOURNAMENT_ACHIEVEMENTS = {
    "round_of_16":  ("🎯", "Early Eye",       "One of your picks reached Round of 16!"),
    "quarterfinal": ("⚡", "Quarter Caller",   "One of your picks reached the Quarter-Finals!"),
    "semifinal":    ("🔮", "Semi Prophet",     "One of your picks reached the Semi-Finals!"),
    "final":        ("🌠", "Finalist Finder",  "One of your picks reached the Final!"),
    "champion":     ("🏆", "Nostradamus",      "You predicted the Champion! Legendary!"),
}

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def fmt_sep():
    return "━━━━━━━━━━━━━━━━━━━━"


def get_or_create_user(phone):
    user = User.query.filter_by(phone=phone).first()
    if not user:
        user = User(phone=phone, name=phone[-4:])
        db.session.add(user)
        db.session.commit()
    return user


def broadcast(message, exclude_phone=None):
    """Send a message to all registered users."""
    users = User.query.all()
    for u in users:
        if u.phone != exclude_phone:
            send_message(u.phone, message)


# ─────────────────────────────────────────────
#  /help
# ─────────────────────────────────────────────

def cmd_help(user):
    return (
        f"🌍⚽ *FIFA PREDICTOR BOT*\n"
        f"_By Buddy — Your Ultimate Match Prediction Game!_\n"
        f"{fmt_sep()}\n\n"
        f"📋 *COMMANDS*\n\n"
        f"🔮 */predict [id]* — Submit your match prediction\n"
        f"🏆 */leaderboard* — Top 10 players\n"
        f"👤 */profile* — Your stats & achievements\n"
        f"🎯 */pick5* — Pick 5 teams to go far in the tournament\n\n"
        f"🛒 *STORE & POWER-UPS*\n\n"
        f"🏪 */store* — Browse available power-ups\n"
        f"💳 */buy [item]* — Purchase a power-up\n"
        f"🎒 */inventory* — Your power-up stash\n"
        f"⚡ */use [item] [match_id]* — Activate a power\n\n"
        f"⚙️ *ACCOUNT*\n\n"
        f"✏️ */setname [name]* — Set your display name\n"
        f"❓ */help* — Show this menu\n\n"
        f"{fmt_sep()}\n"
        f"💬 *Any queries? Message Buddy directly!*\n"
        f"🌟 _Good luck & may the best predictor win!_ ⚽🏆"
    )


# ─────────────────────────────────────────────
#  /setname
# ─────────────────────────────────────────────

def cmd_setname(user, parts):
    if len(parts) < 2:
        return (
            f"✏️ *Set Your Name*\n"
            f"{fmt_sep()}\n"
            f"Usage: */setname [your name]*\n"
            f"Example: `setname Ronaldo Fan`\n\n"
            f"_Your name shows up on the leaderboard!_ 🌟"
        )
    name = " ".join(parts[1:])[:50]
    old = user.name
    user.name = name
    db.session.commit()
    return (
        f"✅ *Name Updated!*\n"
        f"{fmt_sep()}\n"
        f"📛 *Before:* {old}\n"
        f"🌟 *Now:* {name}\n\n"
        f"_See yourself shine on the leaderboard!_ 🏆"
    )


# ─────────────────────────────────────────────
#  /profile
# ─────────────────────────────────────────────

def cmd_profile(user):
    achs = user.achievements
    ach_lines = "\n".join(
        f"  {ua.achievement.emoji} *{ua.achievement.name}* — _{ua.achievement.description}_"
        for ua in achs
    ) or "  _No achievements yet — keep predicting!_ 💪"

    inv = {i.power: i.quantity for i in user.inventory if i.quantity > 0}
    inv_lines = "\n".join(
        f"  ⚡ *{k}* × {v}" for k, v in inv.items()
    ) or "  _No power-ups — visit /store!_ 🏪"

    picks = TournamentPick.query.filter_by(user_id=user.id).all()
    pick_lines = "\n".join(
        f"  🌍 *{p.team}* — _{ROUND_LABELS.get(p.furthest_round, 'Still going...')}_ (+{p.points_earned} pts)"
        for p in picks
    ) or "  _No picks yet — try /pick5!_ 🎯"

    return (
        f"👤 *{user.name}'s Profile*\n"
        f"{fmt_sep()}\n"
        f"📱 Phone: `{user.phone[-4:]}`\n"
        f"⭐ *Points:* {user.points}\n"
        f"🪙 *Tokens:* {user.tokens}\n"
        f"🔮 *Predictions:* {user.predictions_count}\n"
        f"🎯 *Perfect Calls:* {user.perfect_predictions}\n\n"
        f"🎖️ *Achievements*\n{ach_lines}\n\n"
        f"🎯 *Tournament Picks*\n{pick_lines}\n\n"
        f"🎒 *Power-Ups*\n{inv_lines}\n\n"
        f"{fmt_sep()}\n"
        f"_Keep predicting to climb the leaderboard!_ 🚀"
    )


# ─────────────────────────────────────────────
#  /leaderboard
# ─────────────────────────────────────────────

def cmd_leaderboard(user):
    top = User.query.order_by(User.points.desc()).limit(10).all()
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    lines = []
    for i, u in enumerate(top):
        marker = " ◀ *YOU*" if u.id == user.id else ""
        lines.append(f"{medals[i]} *{i+1}. {u.name}* — {u.points} pts{marker}")

    rank_row = ""
    if user not in top:
        total = User.query.count()
        rank = User.query.filter(User.points > user.points).count() + 1
        rank_row = f"\n📍 *Your Rank:* #{rank} of {total}\n"

    return (
        f"🏆 *LEADERBOARD*\n"
        f"{fmt_sep()}\n"
        + "\n".join(lines)
        + rank_row
        + f"\n{fmt_sep()}\n"
        f"_Predict more matches to climb the ranks!_ 🚀"
    )


# ─────────────────────────────────────────────
#  /store
# ─────────────────────────────────────────────

def cmd_store(user):
    lines = []
    for key, item in STORE_ITEMS.items():
        lines.append(
            f"⚡ *{item['name']}* — 🪙 {item['cost']} tokens\n"
            f"   _{item['description']}_\n"
            f"   Buy: `/buy {key}`"
        )
    return (
        f"🏪 *POWER-UP STORE*\n"
        f"{fmt_sep()}\n"
        f"🪙 *Your Tokens:* {user.tokens}\n\n"
        + "\n\n".join(lines)
        + f"\n\n{fmt_sep()}\n"
        f"_Use */inventory* to see what you own!_ 🎒"
    )


# ─────────────────────────────────────────────
#  /buy
# ─────────────────────────────────────────────

def cmd_buy(user, parts):
    if len(parts) < 2:
        return (
            f"💳 *Buy a Power-Up*\n"
            f"{fmt_sep()}\n"
            f"Usage: */buy [item]*\n"
            f"Example: `buy double_points`\n\n"
            f"_See all items with /store_ 🏪"
        )
    item_key = parts[1].lower()
    if item_key not in STORE_ITEMS:
        return (
            f"❌ *Item Not Found*\n"
            f"{fmt_sep()}\n"
            f"_`{item_key}` doesn't exist in the store._\n\n"
            f"Use */store* to see available items 🏪"
        )
    item = STORE_ITEMS[item_key]
    if user.tokens < item["cost"]:
        return (
            f"😔 *Not Enough Tokens*\n"
            f"{fmt_sep()}\n"
            f"💰 *Need:* {item['cost']} tokens\n"
            f"🪙 *You have:* {user.tokens} tokens\n\n"
            f"_Earn tokens by predicting matches correctly!_ 🔮"
        )
    user.tokens -= item["cost"]
    inv = Inventory.query.filter_by(user_id=user.id, power=item_key).first()
    if not inv:
        inv = Inventory(user_id=user.id, power=item_key, quantity=0)
        db.session.add(inv)
    inv.quantity += 1
    db.session.commit()
    return (
        f"✅ *Purchase Successful!*\n"
        f"{fmt_sep()}\n"
        f"⚡ *Bought:* {item['name']}\n"
        f"🪙 *Tokens Left:* {user.tokens}\n\n"
        f"_Use */inventory* to see your items!_ 🎒"
    )


# ─────────────────────────────────────────────
#  /inventory
# ─────────────────────────────────────────────

def cmd_inventory(user):
    items = [i for i in user.inventory if i.quantity > 0]
    if not items:
        return (
            f"🎒 *Your Inventory*\n"
            f"{fmt_sep()}\n"
            f"_You don't own any power-ups yet._\n\n"
            f"Visit */store* to grab some! 🏪"
        )
    lines = [
        f"⚡ *{i.power}* × {i.quantity}"
        for i in items
    ]
    return (
        f"🎒 *Your Inventory*\n"
        f"{fmt_sep()}\n"
        + "\n".join(lines)
        + f"\n\n{fmt_sep()}\n"
        f"_Use: */use [item] [match_id]*_ ⚡"
    )


# ─────────────────────────────────────────────
#  /use
# ─────────────────────────────────────────────

def cmd_use(user, parts):
    if len(parts) < 3:
        return (
            f"⚡ *Use a Power-Up*\n"
            f"{fmt_sep()}\n"
            f"Usage: */use [item] [match_id]*\n"
            f"Example: `use double_points 5`\n\n"
            f"_See your items with /inventory_ 🎒"
        )
    item_key, match_id = parts[1].lower(), parts[2]
    inv = Inventory.query.filter_by(user_id=user.id, power=item_key).first()
    if not inv or inv.quantity < 1:
        return (
            f"❌ *Power-Up Not Found*\n"
            f"{fmt_sep()}\n"
            f"_You don't own *{item_key}*._\n\n"
            f"Buy it at */store* 🏪"
        )
    inv.quantity -= 1
    db.session.commit()
    return (
        f"⚡ *Power Activated!*\n"
        f"{fmt_sep()}\n"
        f"🎯 *{item_key}* used on match *#{match_id}*\n"
        f"📦 *Remaining:* {inv.quantity}\n\n"
        f"_Good luck with your prediction!_ 🔮"
    )


# ─────────────────────────────────────────────
#  /pick5  (tournament team picks)
# ─────────────────────────────────────────────

def cmd_pick5(user, parts):
    existing = TournamentPick.query.filter_by(user_id=user.id).all()

    if len(parts) < 2:
        if existing:
            lines = "\n".join(
                f"  {i+1}. 🌍 *{p.team}* — {ROUND_LABELS.get(p.furthest_round, 'Still going...')} (+{p.points_earned} pts)"
                for i, p in enumerate(existing)
            )
            return (
                f"🎯 *Your Tournament Picks*\n"
                f"{fmt_sep()}\n"
                + lines
                + f"\n\n{fmt_sep()}\n"
                f"💰 *Points per milestone:*\n"
                f"  ⚽ Round of 16 — 500 pts\n"
                f"  🔥 Quarter-Final — 1,000 pts\n"
                f"  🌟 Semi-Final — 2,500 pts\n"
                f"  🏆 Final — 5,000 pts\n"
                f"  👑 Champion — 10,000 pts\n\n"
                f"_Picks are locked once submitted!_ 🔒"
            )
        return (
            f"🎯 *Pick 5 Tournament Teams!*\n"
            f"{fmt_sep()}\n"
            f"Pick 5 teams you think will go far — earn points every time one advances!\n\n"
            f"💰 *Points per milestone:*\n"
            f"  ⚽ Round of 16 — 500 pts\n"
            f"  🔥 Quarter-Final — 1,000 pts\n"
            f"  🌟 Semi-Final — 2,500 pts\n"
            f"  🏆 Final — 5,000 pts\n"
            f"  👑 Champion — 10,000 pts\n\n"
            f"📝 *How to submit:*\n"
            f"`pick5 Brazil, France, Germany, Argentina, England`\n\n"
            f"_Picks are locked after submission — choose wisely!_ 🔒"
        )

    if existing:
        return (
            f"🔒 *Picks Already Locked!*\n"
            f"{fmt_sep()}\n"
            f"_You've already submitted your 5 teams._\n"
            f"Type */pick5* to see them.\n\n"
            f"_Good luck — watch those points roll in!_ 🍀"
        )

    raw = " ".join(parts[1:])
    teams = [t.strip() for t in raw.split(",") if t.strip()]
    if len(teams) != 5:
        return (
            f"❌ *Exactly 5 Teams Required*\n"
            f"{fmt_sep()}\n"
            f"_You entered {len(teams)} team(s)._\n\n"
            f"Example:\n"
            f"`pick5 Brazil, France, Germany, Argentina, England`"
        )

    for team in teams:
        pick = TournamentPick(user_id=user.id, team=team)
        db.session.add(pick)
    db.session.commit()

    lines = "\n".join(f"  {i+1}. 🌍 *{t}*" for i, t in enumerate(teams))
    return (
        f"🎯 *Tournament Picks Locked!*\n"
        f"{fmt_sep()}\n"
        f"Your 5 teams:\n"
        + lines
        + f"\n\n💰 Earn points as each team advances:\n"
        f"  ⚽ R16 → 🔥 QF → 🌟 SF → 🏆 Final → 👑 Champion\n\n"
        f"{fmt_sep()}\n"
        f"_May your teams go all the way!_ 🚀⚽"
    )


# ─────────────────────────────────────────────
#  CONVERSATIONAL /predict  FLOW
#
#  Step 1: /predict 12         → bot asks "Who will win?"
#  Step 2: user replies "1"    → bot asks "What will be the score?"
#  Step 3: user replies "2-1"  → bot confirms & saves
# ─────────────────────────────────────────────

def cmd_predict_start(user, parts):
    """Entry point: /predict [match_id]"""
    if len(parts) < 2 or not parts[1].isdigit():
        return (
            f"🔮 *Submit Prediction*\n"
            f"{fmt_sep()}\n"
            f"Usage: */predict [match_id]*\n"
            f"Example: `/predict 12`\n\n"
            f"_Find the Match ID in the announcement message._ 📢"
        )

    match = Match.query.get(int(parts[1]))
    if not match:
        return (
            f"❌ *Match Not Found*\n"
            f"{fmt_sep()}\n"
            f"_No match with ID #{parts[1]}._\n\n"
            f"_Check the latest announcements for valid IDs._ 📢"
        )
    if match.status != "open":
        return (
            f"🔒 *Predictions Closed*\n"
            f"{fmt_sep()}\n"
            f"⚽ *{match.team1}* vs *{match.team2}*\n\n"
            f"_This match is no longer accepting predictions._\n"
            f"_Stay ready for the next one!_ ⏰"
        )
    if datetime.utcnow() >= match.start_time:
        return (
            f"⏰ *Too Late!*\n"
            f"{fmt_sep()}\n"
            f"⚽ *{match.team1}* vs *{match.team2}*\n\n"
            f"_The match has already started. Predictions are closed._\n"
            f"_Be early next time!_ 🏃"
        )

    # Start conversation session
    set_session(user.phone, "predict", "winner", {"match_id": match.id})

    return (
        f"🔮 *Prediction — Match #{match.id}*\n"
        f"{fmt_sep()}\n"
        f"⚽ *{match.team1}* vs *{match.team2}*\n\n"
        f"*Who will win?*\n\n"
        f"  1️⃣  {match.team1}\n"
        f"  2️⃣  {match.team2}\n"
        f"  3️⃣  Draw\n\n"
        f"_Reply with 1, 2, or 3_"
    )


def cmd_predict_winner(user, session, body):
    """Step 2: capture winner choice, ask for score."""
    match_id = session["data"]["match_id"]
    match = Match.query.get(match_id)
    text = body.strip()

    if text == "1":
        winner = match.team1
    elif text == "2":
        winner = match.team2
    elif text == "3":
        winner = "Draw"
    else:
        return (
            f"❓ *Please reply with 1, 2, or 3*\n\n"
            f"  1️⃣  {match.team1}\n"
            f"  2️⃣  {match.team2}\n"
            f"  3️⃣  Draw"
        )

    # Save winner, advance to score step
    session["data"]["winner"] = winner
    set_session(user.phone, "predict", "score", session["data"])

    return (
        f"✅ *Winner:* {winner}\n\n"
        f"⚽ *What will be the final score?*\n"
        f"_{match.team1} — {match.team2}_\n\n"
        f"Example: `2-1`"
    )


def cmd_predict_score(user, session, body):
    """Step 3: capture score, save prediction."""
    match_id = session["data"]["match_id"]
    winner   = session["data"]["winner"]
    match    = Match.query.get(match_id)
    score    = body.strip()

    # Basic score format validation (e.g. 2-1, 0-0, 10-3)
    if not re.match(r"^\d{1,2}-\d{1,2}$", score):
        return (
            f"❓ *Invalid format.*\n\n"
            f"Please enter the score like this: `2-1`\n"
            f"_(Goals for {match.team1} — Goals for {match.team2})_"
        )

    # Save or update prediction
    existing = Prediction.query.filter_by(user_id=user.id, match_id=match.id).first()
    if existing:
        existing.winner = winner
        existing.score  = score
        db.session.commit()
        clear_session(user.phone)
        return (
            f"✏️ *Prediction Updated!*\n"
            f"{fmt_sep()}\n"
            f"⚽ *{match.team1}* vs *{match.team2}*\n\n"
            f"🏆 *Winner:* {winner}\n"
            f"📊 *Score:* {score}\n\n"
            f"_Good luck! Results after the match._ 🍀"
        )

    pred = Prediction(
        user_id=user.id,
        match_id=match.id,
        winner=winner,
        score=score,
    )
    db.session.add(pred)
    user.predictions_count += 1
    db.session.commit()
    check_and_award(user)
    clear_session(user.phone)

    return (
        f"✅ *Prediction Saved!*\n"
        f"{fmt_sep()}\n"
        f"⚽ *{match.team1}* vs *{match.team2}*\n\n"
        f"🏆 *Winner:* {winner}\n"
        f"📊 *Score:* {score}\n\n"
        f"_May the best call win!_ 🔮🍀"
    )


# ─────────────────────────────────────────────
#  ADMIN: /creatematch  (inline format)
#
#  /creatematch Brazil France 15-Jun-2026 20:00
# ─────────────────────────────────────────────

def cmd_creatematch(user, body):
    """
    Supports both single-word and quoted multi-word team names.

    Single-word teams (no quotes needed):
      /creatematch Brazil France 15-Jun-2026 20:00

    Multi-word teams (use quotes):
      /creatematch "Real Madrid" "Manchester City" 15-Jun-2026 20:00
      /creatematch "Paris Saint-Germain" France 15-Jun-2026 20:00

    Date format: DD-Mon-YYYY  (e.g. 15-Jun-2026)
    Time format: HH:MM        (24-hour, e.g. 20:00)
    """
    USAGE = (
        f"⚙️ *Create Match*\n"
        f"{fmt_sep()}\n"
        f"Single-word teams:\n"
        f"`/creatematch Brazil France 15-Jun-2026 20:00`\n\n"
        f"Multi-word teams (use quotes):\n"
        f'`/creatematch "Real Madrid" "Man City" 15-Jun-2026 20:00`'
    )

    # Use shlex to split respecting quoted strings, then drop the command token
    try:
        tokens = shlex.split(body)
    except ValueError:
        return USAGE
    tokens = tokens[1:]  # drop "/creatematch"

    if len(tokens) < 4:
        return USAGE

    # Last two tokens are always date and time; everything before is team1 team2
    date_str = tokens[-2]
    time_str = tokens[-1]
    team_tokens = tokens[:-2]   # everything between command and date

    if len(team_tokens) < 2:
        return USAGE

    # If exactly 2 tokens remain they're team1 and team2 directly (shlex already
    # handled the quoted case). For unquoted multi-word: not supported — user must quote.
    team1 = team_tokens[0]
    team2 = team_tokens[1]

    try:
        start_time = datetime.strptime(f"{date_str} {time_str}", "%d-%b-%Y %H:%M")
    except ValueError:
        return (
            f"❌ *Invalid Date/Time Format*\n"
            f"{fmt_sep()}\n"
            f"Use: `DD-Mon-YYYY HH:MM`\n"
            f"Example: `15-Jun-2026 20:00`"
        )

    match = Match(team1=team1, team2=team2, start_time=start_time)
    db.session.add(match)
    db.session.commit()

    # Broadcast to all users
    announcement = (
        f"🔥 *NEW MATCH OPEN* 🔥\n"
        f"{fmt_sep()}\n"
        f"⚽ *{team1}* vs *{team2}*\n"
        f"🆔 *Match ID:* {match.id}\n"
        f"⏰ *Kickoff:* {start_time.strftime('%d %B %Y, %I:%M %p')}\n"
        f"{fmt_sep()}\n\n"
        f"To participate, send:\n"
        f"*/predict {match.id}*\n\n"
        f"_Predictions close at kickoff._\n"
        f"{fmt_sep()}\n"
        f"Good luck! 🏆"
    )
    broadcast(announcement, exclude_phone=user.phone)

    return (
        f"✅ *Match Created!*\n"
        f"{fmt_sep()}\n"
        f"⚽ *{team1}* vs *{team2}*\n"
        f"🆔 *Match ID:* #{match.id}\n"
        f"⏰ *Kickoff:* {start_time.strftime('%d %B %Y, %I:%M %p')}\n\n"
        f"📢 _Announcement sent to all players!_ ✅"
    )


# ─────────────────────────────────────────────
#  ADMIN: /result  (conversational)
#
#  Step 1: /result 12        → bot asks "Enter Winner:"
#  Step 2: admin types name  → bot asks "Enter Final Score:"
#  Step 3: admin types score → saves, scores all, broadcasts
# ─────────────────────────────────────────────

def cmd_result_start(user, parts):
    """Entry point: /result [match_id]"""
    if len(parts) < 2 or not parts[1].isdigit():
        return (
            f"⚙️ *Enter Result*\n"
            f"{fmt_sep()}\n"
            f"Usage: `/result [match_id]`\n"
            f"Example: `/result 12`"
        )

    match = Match.query.get(int(parts[1]))
    if not match:
        return f"❌ Match #{parts[1]} not found."

    if match.status == "completed":
        return (
            f"⚠️ *Match Already Completed*\n"
            f"{fmt_sep()}\n"
            f"⚽ *{match.team1}* vs *{match.team2}* has already been scored."
        )

    set_session(user.phone, "result", "winner", {"match_id": match.id})

    return (
        f"⚙️ *Enter Result — Match #{match.id}*\n"
        f"{fmt_sep()}\n"
        f"⚽ *{match.team1}* vs *{match.team2}*\n\n"
        f"*Enter Winner:*\n"
        f"_(Type the winning team's name, or 'Draw')_"
    )


def cmd_result_winner(user, session, body):
    """Step 2: capture winner, ask for score."""
    session["data"]["winner"] = body.strip()
    match_id = session["data"]["match_id"]
    match = Match.query.get(match_id)
    set_session(user.phone, "result", "score", session["data"])

    return (
        f"✅ *Winner:* {session['data']['winner']}\n\n"
        f"*Enter Final Score:*\n"
        f"_{match.team1} — {match.team2}_\n\n"
        f"Example: `2-1`"
    )


def cmd_result_score(user, session, body):
    """Step 3: capture score, save result, score all predictions, broadcast."""
    score = body.strip()

    if not re.match(r"^\d{1,2}-\d{1,2}$", score):
        return (
            f"❓ *Invalid format.*\n\n"
            f"Please enter the score like this: `2-1`"
        )

    match_id = session["data"]["match_id"]
    winner   = session["data"]["winner"]
    match    = Match.query.get(match_id)

    result = Result(
        match_id=match.id,
        winner=winner,
        score=score,
    )
    db.session.add(result)
    match.status = "completed"
    db.session.commit()
    clear_session(user.phone)

    # ── Score all predictions ──────────────────
    predictions = Prediction.query.filter_by(match_id=match.id).all()
    for pred in predictions:
        pts = _calculate_simple_score(pred.winner, pred.score, winner, score)
        pred.points_awarded = pts
        pred.user.points += pts
        if pts == 500:  # perfect
            pred.user.perfect_predictions += 1
        db.session.commit()
        check_and_award(pred.user)

    # ── Leaderboard snapshot ───────────────────
    top = User.query.order_by(User.points.desc()).limit(5).all()
    medals = ["🥇", "🥈", "🥉", "🔹", "🔹"]
    lb_lines = "\n".join(
        f"  {medals[i]} *{u.name}* — {u.points} pts"
        for i, u in enumerate(top)
    )

    # ── Personal result message to each predictor ──
    for pred in predictions:
        u = pred.user
        winner_correct = pred.winner == winner
        score_correct  = pred.score  == score
        pts_earned     = pred.points_awarded

        personal = (
            f"🏆 *MATCH RESULT*\n"
            f"{fmt_sep()}\n"
            f"⚽ *{match.team1}* {score} *{match.team2}*\n\n"
            f"*Your Prediction:*\n"
            f"  Winner: {pred.winner} {'✅' if winner_correct else '❌'}\n"
            f"  Score:  {pred.score}  {'✅' if score_correct  else '❌'}\n\n"
            f"⭐ *Points Earned:* +{pts_earned}\n"
            f"🏦 *Total Points:* {u.points}\n\n"
            f"_Use /leaderboard to see rankings._"
        )
        send_message(u.phone, personal)

    # ── Notify non-predictors ──────────────────
    predicted_ids = {p.user_id for p in predictions}
    all_users = User.query.all()
    for u in all_users:
        if u.id not in predicted_ids and u.phone != user.phone:
            send_message(u.phone, (
                f"⚽ *MATCH RESULT*\n"
                f"{fmt_sep()}\n"
                f"*{match.team1}* {score} *{match.team2}*\n"
                f"🏆 *Winner:* {winner}\n\n"
                f"😔 _You didn't predict this match — don't miss the next one!_\n\n"
                f"_View standings: /leaderboard_ 🏆"
            ))

    # ── Public broadcast to all ────────────────
    broadcast_msg = (
        f"🏆 *FULL TIME*\n"
        f"{fmt_sep()}\n"
        f"⚽ *{match.team1}* {score} *{match.team2}*\n\n"
        f"_Predictions have been scored._\n\n"
        f"View your score: */profile*\n"
        f"View leaderboard: */leaderboard*"
    )
    # Send to everyone except admin (they get the summary below)
    for u in User.query.all():
        if u.phone != user.phone:
            send_message(u.phone, broadcast_msg)

    return (
        f"✅ *Result Entered & Scored!*\n"
        f"{fmt_sep()}\n"
        f"⚽ *{match.team1}* vs *{match.team2}*\n"
        f"🏆 *Winner:* {winner}\n"
        f"📊 *Score:* {score}\n\n"
        f"📢 *{len(predictions)} player(s)* scored & notified!\n\n"
        f"🏆 *Top 5:*\n{lb_lines}"
    )


def _calculate_simple_score(pred_winner, pred_score, actual_winner, actual_score):
    """
    Points system:
      Correct winner only  → 100 pts
      Correct score only   → 300 pts  (implies correct winner too)
      Perfect (both)       → 500 pts
    """
    winner_correct = pred_winner == actual_winner
    score_correct  = pred_score  == actual_score

    if winner_correct and score_correct:
        return 500   # perfect
    if score_correct:
        return 300   # exact score (winner implied correct if score is exact)
    if winner_correct:
        return 100   # just winner
    return 0


# ─────────────────────────────────────────────
#  ADMIN: /advanceteam  (tournament round update)
# ─────────────────────────────────────────────

def cmd_advanceteam(user, body):
    """
    /advanceteam Brazil quarterfinal
    /advanceteam "Real Madrid" semifinal
    Round key is always the LAST token; team name is everything before it.
    Rounds: round_of_16 | quarterfinal | semifinal | final | champion
    """
    USAGE = (
        f"⚙️ *Advance a Team*\n"
        f"{fmt_sep()}\n"
        f"Single-word:  `/advanceteam Brazil quarterfinal`\n"
        f'Multi-word:   `/advanceteam "Real Madrid" semifinal`\n\n'
        f"Rounds: `round_of_16` | `quarterfinal` | `semifinal` | `final` | `champion`"
    )
    try:
        tokens = shlex.split(body)
    except ValueError:
        return USAGE
    tokens = tokens[1:]  # drop "/advanceteam"

    if len(tokens) < 2:
        return USAGE

    round_key = tokens[-1].lower()          # last token is always the round
    team      = " ".join(tokens[:-1])       # everything else is the team name

    if round_key not in ROUND_POINTS:
        return (
            f"❌ *Invalid Round*\n"
            f"{fmt_sep()}\n"
            f"Valid rounds: `round_of_16`, `quarterfinal`, `semifinal`, `final`, `champion`"
        )

    picks = TournamentPick.query.filter_by(team=team).all()
    if not picks:
        return f"⚠️ No one picked *{team}* — no points awarded."

    pts   = ROUND_POINTS[round_key]
    label = ROUND_LABELS[round_key]
    emoji, ach_name, ach_desc = TOURNAMENT_ACHIEVEMENTS[round_key]
    notified = 0

    for pick in picks:
        pick.furthest_round   = round_key
        pick.points_earned    = (pick.points_earned or 0) + pts
        pick.user.points     += pts
        db.session.commit()
        check_and_award(pick.user)

        send_message(pick.user.phone, (
            f"🎉 *Tournament Update!*\n"
            f"{fmt_sep()}\n"
            f"🌍 *{team}* has reached the *{label}*!\n\n"
            f"⭐ *+{pts} points* added to your score!\n"
            f"🏦 *Total Points:* {pick.user.points}\n\n"
            f"{emoji} *Achievement Unlocked: {ach_name}!*\n"
            f"_{ach_desc}_\n\n"
            f"{fmt_sep()}\n"
            f"_Keep cheering!_ ⚽🔥"
        ))
        notified += 1

    db.session.commit()
    return (
        f"✅ *Team Advanced!*\n"
        f"{fmt_sep()}\n"
        f"🌍 *{team}* → *{label}*\n"
        f"⭐ *+{pts} pts* awarded to *{notified} player(s)*"
    )


# ─────────────────────────────────────────────
#  MAIN DISPATCHER
# ─────────────────────────────────────────────

# Must match the format routes.py sends: "whatsapp:" and "+" are already stripped there
ADMIN_PHONES = ["919409688470"]  # ← your admin number (no "whatsapp:" prefix, no "+")


def handle_message(phone, body):
    user  = get_or_create_user(phone)
    body  = body.strip()
    parts = body.split()

    if not parts:
        return cmd_help(user)

    # ── Check if user is mid-conversation ─────
    session = get_session(phone)
    if session:
        # Allow /cancel anywhere to abort
        if parts[0].lstrip("/").lower() == "cancel":
            clear_session(phone)
            return "❌ *Cancelled.* Send any command to continue."

        flow = session["flow"]
        step = session["step"]

        if flow == "predict":
            if step == "winner":
                return cmd_predict_winner(user, session, body)
            elif step == "score":
                return cmd_predict_score(user, session, body)

        elif flow == "result":
            if step == "winner":
                return cmd_result_winner(user, session, body)
            elif step == "score":
                return cmd_result_score(user, session, body)

    # ── Normal command routing ─────────────────
    cmd      = parts[0].lstrip("/").lower()
    is_admin = phone in ADMIN_PHONES

    if cmd == "help":
        return cmd_help(user)
    elif cmd == "setname":
        return cmd_setname(user, parts)
    elif cmd == "profile":
        return cmd_profile(user)
    elif cmd == "leaderboard":
        return cmd_leaderboard(user)
    elif cmd == "store":
        return cmd_store(user)
    elif cmd == "buy":
        return cmd_buy(user, parts)
    elif cmd == "inventory":
        return cmd_inventory(user)
    elif cmd == "use":
        return cmd_use(user, parts)
    elif cmd == "predict":
        return cmd_predict_start(user, parts)
    elif cmd == "pick5":
        return cmd_pick5(user, parts)
    elif cmd == "creatematch" and is_admin:
        return cmd_creatematch(user, body)
    elif cmd == "result" and is_admin:
        return cmd_result_start(user, parts)
    elif cmd == "advanceteam" and is_admin:
        return cmd_advanceteam(user, body)
    else:
        return (
            f"🤔 *Unknown Command*\n"
            f"{fmt_sep()}\n"
            f"_I didn't understand that._\n\n"
            f"Type */help* to see all available commands! 📋"
        )