"""
Command handlers — parse commands from incoming WhatsApp messages.
"""

from datetime import datetime, timedelta
from .database import db, User, Match, Prediction, Result, Inventory, TournamentPick
from .scoring import calculate_score, STORE_ITEMS
from .achievements import check_and_award
from .whatsapp import send_message

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
        f"📋 */copy [id]* — Get the prediction form\n"
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
#  /copy  (prediction form)
# ─────────────────────────────────────────────

def cmd_copy(user, parts):
    if len(parts) < 2 or not parts[1].isdigit():
        return (
            f"📋 *Get Prediction Form*\n"
            f"{fmt_sep()}\n"
            f"Usage: */copy [match_id]*\n"
            f"Example: `copy 3`\n\n"
            f"_Find match IDs on the match announcements!_ ⚽"
        )
    match = Match.query.get(int(parts[1]))
    if not match:
        return (
            f"❌ *Match Not Found*\n"
            f"{fmt_sep()}\n"
            f"_No match with ID #{parts[1]}._\n\n"
            f"_Check the latest announcements for valid IDs._ 📢"
        )
    return (
        f"📋 *Prediction Form — Match #{match.id}*\n"
        f"⚽ *{match.team1}* vs *{match.team2}*\n"
        f"{fmt_sep()}\n"
        f"Copy the template below and fill it in:\n\n"
        f"```\n"
        f"predict {match.id}\n"
        f"winner: [team name]\n"
        f"score: [e.g. 2-1]\n"
        f"mvp: [player name]\n"
        f"top1: [player]\n"
        f"top2: [player]\n"
        f"top3: [player]\n"
        f"```\n\n"
        f"_Send the filled form back to submit!_ ✅"
    )


# ─────────────────────────────────────────────
#  /predict
# ─────────────────────────────────────────────

def cmd_predict(user, parts, body):
    if len(parts) < 2 or not parts[1].isdigit():
        return (
            f"🔮 *Submit Prediction*\n"
            f"{fmt_sep()}\n"
            f"Usage: */predict [match_id]*\n"
            f"Get the form with: */copy [match_id]*\n\n"
            f"_Example: `copy 3` then fill it!_ ✏️"
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

    lines = body.strip().splitlines()
    data = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip().lower()] = v.strip()

    existing = Prediction.query.filter_by(user_id=user.id, match_id=match.id).first()
    if existing:
        existing.winner = data.get("winner", existing.winner)
        existing.score  = data.get("score",  existing.score)
        existing.mvp    = data.get("mvp",    existing.mvp)
        existing.top1   = data.get("top1",   existing.top1)
        existing.top2   = data.get("top2",   existing.top2)
        existing.top3   = data.get("top3",   existing.top3)
        db.session.commit()
        return (
            f"✏️ *Prediction Updated!*\n"
            f"{fmt_sep()}\n"
            f"⚽ *{match.team1}* vs *{match.team2}*\n\n"
            f"🏆 Winner: *{existing.winner}*\n"
            f"📊 Score: *{existing.score}*\n"
            f"⭐ MVP: *{existing.mvp}*\n\n"
            f"_Good luck! Results after the match._ 🍀"
        )

    pred = Prediction(
        user_id=user.id,
        match_id=match.id,
        winner=data.get("winner"),
        score=data.get("score"),
        mvp=data.get("mvp"),
        top1=data.get("top1"),
        top2=data.get("top2"),
        top3=data.get("top3"),
    )
    db.session.add(pred)
    user.predictions_count += 1
    db.session.commit()
    check_and_award(user)
    return (
        f"✅ *Prediction Submitted!*\n"
        f"{fmt_sep()}\n"
        f"⚽ *{match.team1}* vs *{match.team2}*\n\n"
        f"🏆 Winner: *{data.get('winner', '—')}*\n"
        f"📊 Score: *{data.get('score', '—')}*\n"
        f"⭐ MVP: *{data.get('mvp', '—')}*\n\n"
        f"_May the best call win!_ 🔮🍀"
    )


# ─────────────────────────────────────────────
#  /pick5  (tournament team picks)
# ─────────────────────────────────────────────

def cmd_pick5(user, parts):
    """
    /pick5 Brazil, France, Germany, Argentina, England
    Or /pick5 alone → show current picks / instructions
    """
    existing = TournamentPick.query.filter_by(user_id=user.id).all()

    # Show instructions if no teams given
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
            f"_{fmt_sep()}_\n"
            f"_Picks are locked after submission — choose wisely!_ 🔒"
        )

    # Already picked
    if existing:
        return (
            f"🔒 *Picks Already Locked!*\n"
            f"{fmt_sep()}\n"
            f"_You've already submitted your 5 teams._\n"
            f"Type */pick5* to see them.\n\n"
            f"_Good luck — watch those points roll in!_ 🍀"
        )

    # Parse teams
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
#  ADMIN: /creatematch
# ─────────────────────────────────────────────

def cmd_creatematch(user, parts, body):
    """
    /creatematch
    team1: Brazil
    team2: France
    time: 2026-07-01 18:00
    """
    lines = body.strip().splitlines()
    data = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip().lower()] = v.strip()

    required = ["team1", "team2", "time"]
    missing = [r for r in required if r not in data]
    if missing:
        return (
            f"⚙️ *Create Match*\n"
            f"{fmt_sep()}\n"
            f"Missing fields: *{', '.join(missing)}*\n\n"
            f"Format:\n"
            f"```\ncreatematch\nteam1: Brazil\nteam2: France\ntime: 2026-07-01 18:00\n```"
        )

    try:
        start_time = datetime.strptime(data["time"], "%Y-%m-%d %H:%M")
    except ValueError:
        return (
            f"❌ *Invalid Time Format*\n"
            f"{fmt_sep()}\n"
            f"Use: `YYYY-MM-DD HH:MM`\n"
            f"Example: `2026-07-01 18:00`"
        )

    match = Match(team1=data["team1"], team2=data["team2"], start_time=start_time)
    db.session.add(match)
    db.session.commit()

    # Broadcast match announcement to all players
    announcement = (
        f"📣 *NEW MATCH ANNOUNCED!*\n"
        f"{fmt_sep()}\n"
        f"⚽ *{match.team1}* 🆚 *{match.team2}*\n"
        f"🕐 *Kick-off:* {start_time.strftime('%d %b %Y • %H:%M')} UTC\n"
        f"🆔 *Match ID:* #{match.id}\n\n"
        f"📋 Get form: `/copy {match.id}`\n"
        f"🔮 Submit: `/predict {match.id}`\n\n"
        f"{fmt_sep()}\n"
        f"_Predictions close at kick-off — don't miss it!_ ⏰"
    )
    broadcast(announcement, exclude_phone=user.phone)

    return (
        f"✅ *Match Created!*\n"
        f"{fmt_sep()}\n"
        f"⚽ *{match.team1}* vs *{match.team2}*\n"
        f"🕐 *Kick-off:* {start_time.strftime('%d %b %Y • %H:%M')} UTC\n"
        f"🆔 *Match ID:* #{match.id}\n\n"
        f"📢 _Announcement sent to all players!_ ✅"
    )


# ─────────────────────────────────────────────
#  ADMIN: /result
# ─────────────────────────────────────────────

def cmd_result(user, parts, body):
    """
    /result [match_id]
    winner: Brazil
    score: 2-1
    mvp: Neymar
    top1: Neymar
    top2: Mbappe
    top3: Vinicius
    """
    lines = body.strip().splitlines()
    if len(parts) < 2 or not parts[1].isdigit():
        return (
            f"⚙️ *Enter Result*\n"
            f"{fmt_sep()}\n"
            f"Format:\n"
            f"```\nresult [match_id]\nwinner: Brazil\nscore: 2-1\nmvp: Neymar\ntop1: Neymar\ntop2: Mbappe\ntop3: Vinicius\n```"
        )

    match = Match.query.get(int(parts[1]))
    if not match:
        return f"❌ Match #{parts[1]} not found."

    data = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip().lower()] = v.strip()

    result = Result(
        match_id=match.id,
        winner=data.get("winner"),
        score=data.get("score"),
        mvp=data.get("mvp"),
        top1=data.get("top1"),
        top2=data.get("top2"),
        top3=data.get("top3"),
    )
    db.session.add(result)
    match.status = "completed"
    db.session.commit()

    # Score all predictions
    predictions = Prediction.query.filter_by(match_id=match.id).all()
    scored = []
    for pred in predictions:
        pts = calculate_score(pred, result)
        pred.points_awarded = pts
        pred.user.points += pts
        if pts > 0:
            scored.append((pred.user, pts))
        db.session.commit()
        check_and_award(pred.user)

    # Build leaderboard snapshot
    top = User.query.order_by(User.points.desc()).limit(5).all()
    medals = ["🥇", "🥈", "🥉", "🔹", "🔹"]
    lb_lines = "\n".join(
        f"  {medals[i]} *{u.name}* — {u.points} pts"
        for i, u in enumerate(top)
    )

    # Broadcast result + scores to everyone
    for pred in predictions:
        u = pred.user
        personal = (
            f"⚽ *MATCH RESULT*\n"
            f"{fmt_sep()}\n"
            f"*{match.team1}* 🆚 *{match.team2}*\n"
            f"🏆 *Winner:* {result.winner}\n"
            f"📊 *Score:* {result.score}\n"
            f"⭐ *MVP:* {result.mvp}\n\n"
            f"🎯 *Your Prediction:*\n"
            f"  Winner: {pred.winner} {'✅' if pred.winner == result.winner else '❌'}\n"
            f"  Score: {pred.score} {'✅' if pred.score == result.score else '❌'}\n"
            f"  MVP: {pred.mvp} {'✅' if pred.mvp == result.mvp else '❌'}\n\n"
            f"⭐ *Points Earned:* +{pred.points_awarded}\n"
            f"🏦 *Total Points:* {u.points}\n\n"
            f"🏆 *Top 5 Right Now:*\n{lb_lines}\n\n"
            f"{fmt_sep()}\n"
            f"_Keep predicting to climb higher!_ 🚀"
        )
        send_message(u.phone, personal)

    # Notify users who had no prediction
    predicted_ids = {p.user_id for p in predictions}
    all_users = User.query.all()
    for u in all_users:
        if u.id not in predicted_ids and u.phone != user.phone:
            send_message(u.phone, (
                f"⚽ *MATCH RESULT*\n"
                f"{fmt_sep()}\n"
                f"*{match.team1}* 🆚 *{match.team2}*\n"
                f"🏆 *Winner:* {result.winner}\n"
                f"📊 *Score:* {result.score}\n\n"
                f"😔 _You didn't predict this match — don't miss the next one!_\n\n"
                f"🏆 *Top 5:*\n{lb_lines}\n\n"
                f"{fmt_sep()}\n"
                f"_Stay sharp!_ ⚡"
            ))

    return (
        f"✅ *Result Entered!*\n"
        f"{fmt_sep()}\n"
        f"⚽ *{match.team1}* vs *{match.team2}*\n"
        f"🏆 Winner: *{result.winner}*\n"
        f"📊 Score: *{result.score}*\n\n"
        f"📢 *{len(predictions)} players* notified with scores!\n\n"
        f"🏆 *Top 5:*\n{lb_lines}"
    )


# ─────────────────────────────────────────────
#  ADMIN: /advanceteam  (tournament round update)
# ─────────────────────────────────────────────

def cmd_advanceteam(user, parts):
    """
    /advanceteam [team] [round]
    e.g. /advanceteam Brazil quarterfinal
    Rounds: round_of_16 | quarterfinal | semifinal | final | champion
    """
    if len(parts) < 3:
        return (
            f"⚙️ *Advance a Team*\n"
            f"{fmt_sep()}\n"
            f"Usage: */advanceteam [team] [round]*\n\n"
            f"Rounds: `round_of_16` | `quarterfinal` | `semifinal` | `final` | `champion`\n\n"
            f"Example: `advanceteam Brazil quarterfinal`"
        )

    team = parts[1]
    round_key = parts[2].lower()

    if round_key not in ROUND_POINTS:
        return (
            f"❌ *Invalid Round*\n"
            f"{fmt_sep()}\n"
            f"Valid rounds: `round_of_16`, `quarterfinal`, `semifinal`, `final`, `champion`"
        )

    picks = TournamentPick.query.filter_by(team=team).all()
    if not picks:
        return f"⚠️ No one picked *{team}* — no points awarded."

    pts = ROUND_POINTS[round_key]
    label = ROUND_LABELS[round_key]
    emoji, ach_name, ach_desc = TOURNAMENT_ACHIEVEMENTS[round_key]
    notified = 0

    for pick in picks:
        pick.furthest_round = round_key
        pick.points_earned = (pick.points_earned or 0) + pts
        pick.user.points += pts
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

ADMIN_PHONES = ["whatsapp:+919409688470"] # ← Replace with your number

def handle_message(phone, body):
    user = get_or_create_user(phone)
    parts = body.strip().split()
    if not parts:
        return cmd_help(user)

    cmd = parts[0].lstrip("/").lower()
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
    elif cmd == "copy":
        return cmd_copy(user, parts)
    elif cmd == "predict":
        return cmd_predict(user, parts, body)
    elif cmd == "pick5":
        return cmd_pick5(user, parts)
    elif cmd == "creatematch" and is_admin:
        return cmd_creatematch(user, parts, body)
    elif cmd == "result" and is_admin:
        return cmd_result(user, parts, body)
    elif cmd == "advanceteam" and is_admin:
        return cmd_advanceteam(user, parts)
    else:
        return (
            f"🤔 *Unknown Command*\n"
            f"{fmt_sep()}\n"
            f"_I didn't understand that._\n\n"
            f"Type */help* to see all available commands! 📋"
        )
