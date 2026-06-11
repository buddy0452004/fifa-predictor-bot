"""
Achievement system — checks and awards achievements after scoring.
"""
from .database import db, Achievement, UserAchievement, User

ACHIEVEMENT_DEFS = [
    {"key": "debut_goal",      "name": "⚽ Debut Goal",       "description": "Made your first prediction",         "token_reward": 50,  "emoji": "⚽"},
    {"key": "first_mvp",       "name": "🌟 Star Spotter",     "description": "Correctly predicted an MVP",          "token_reward": 30,  "emoji": "🌟"},
    {"key": "perfect_10",      "name": "💎 Perfect 10",       "description": "Got a perfect prediction",            "token_reward": 100, "emoji": "💎"},
    {"key": "five_perfect",    "name": "🔥 On Fire",          "description": "5 perfect predictions",              "token_reward": 200, "emoji": "🔥"},
    {"key": "century",         "name": "💯 Century",          "description": "100 total predictions",              "token_reward": 500, "emoji": "💯"},
    {"key": "score_sniper",    "name": "🎯 Score Sniper",     "description": "Correctly predicted 10 exact scores", "token_reward": 150, "emoji": "🎯"},
    {"key": "ten_predictions", "name": "📊 Veteran",          "description": "Made 10 predictions",                "token_reward": 75,  "emoji": "📊"},
    {"key": "top3_master",     "name": "👑 Top3 Master",      "description": "Correctly predicted all Top3 in 5 matches", "token_reward": 120, "emoji": "👑"},
]


def seed_achievements():
    """Seed achievement definitions into DB."""
    for a in ACHIEVEMENT_DEFS:
        if not Achievement.query.filter_by(key=a["key"]).first():
            db.session.add(Achievement(**a))
    db.session.commit()


def check_and_award(user: User, prediction, score_result: dict) -> list:
    """
    After a prediction is scored, check which achievements the user has now unlocked.
    Returns list of newly awarded Achievement objects.
    """
    newly_awarded = []

    def _award(key):
        achievement = Achievement.query.filter_by(key=key).first()
        if not achievement:
            return
        already = UserAchievement.query.filter_by(
            user_id=user.id, achievement_id=achievement.id
        ).first()
        if not already:
            ua = UserAchievement(user_id=user.id, achievement_id=achievement.id)
            db.session.add(ua)
            user.tokens += achievement.token_reward
            newly_awarded.append(achievement)

    # First prediction ever
    if user.predictions_count == 1:
        _award("debut_goal")

    # MVP correct
    if score_result["breakdown"].get("mvp", 0) > 0:
        _award("first_mvp")

    # Perfect prediction
    if score_result["is_perfect"]:
        _award("perfect_10")

    # 5 perfect predictions
    if user.perfect_predictions >= 5:
        _award("five_perfect")

    # 100 predictions
    if user.predictions_count >= 100:
        _award("century")

    # 10 predictions
    if user.predictions_count >= 10:
        _award("ten_predictions")

    db.session.commit()
    return newly_awarded
