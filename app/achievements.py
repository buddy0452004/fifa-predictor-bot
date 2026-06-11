"""
Achievement system — checks and awards achievements after scoring.
"""
from .database import db, Achievement, UserAchievement, User

ACHIEVEMENT_DEFS = [
    {"key": "debut_goal",      "name": "⚽ Debut Goal",       "description": "Made your first prediction",               "token_reward": 50,  "emoji": "⚽"},
    {"key": "first_mvp",       "name": "🌟 Star Spotter",     "description": "Correctly predicted an MVP",               "token_reward": 30,  "emoji": "🌟"},
    {"key": "perfect_10",      "name": "💎 Perfect 10",       "description": "Got a perfect prediction",                 "token_reward": 100, "emoji": "💎"},
    {"key": "five_perfect",    "name": "🔥 On Fire",          "description": "5 perfect predictions",                   "token_reward": 200, "emoji": "🔥"},
    {"key": "century",         "name": "💯 Century",          "description": "100 total predictions",                   "token_reward": 500, "emoji": "💯"},
    {"key": "score_sniper",    "name": "🎯 Score Sniper",     "description": "Correctly predicted 10 exact scores",      "token_reward": 150, "emoji": "🎯"},
    {"key": "ten_predictions", "name": "📊 Veteran",          "description": "Made 10 predictions",                     "token_reward": 75,  "emoji": "📊"},
    {"key": "top3_master",     "name": "👑 Top3 Master",      "description": "Correctly predicted all Top3 in 5 matches","token_reward": 120, "emoji": "👑"},
]


def seed_achievements():
    """Seed achievement definitions into DB."""
    for a in ACHIEVEMENT_DEFS:
        if not Achievement.query.filter_by(key=a["key"]).first():
            db.session.add(Achievement(**a))
    db.session.commit()


def check_and_award(user: User, prediction=None, score_result: dict = None) -> list:
    """
    Check and award achievements for a user.

    Can be called in two ways:

    1. After conversational prediction (new flow) — no scoring context available:
         check_and_award(user)

    2. After full scoring with breakdown (old flow) — all context available:
         check_and_award(user, prediction, score_result)

    Achievements that require score_result (first_mvp) are only checked when
    score_result is provided. All stat-based achievements (debut_goal,
    ten_predictions, century, perfect_10, five_perfect) work in both cases.

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

    # ── Always safe — based purely on user stats ──────────────────────────────

    # First prediction ever
    if user.predictions_count == 1:
        _award("debut_goal")

    # 10 predictions milestone
    if user.predictions_count >= 10:
        _award("ten_predictions")

    # 100 predictions milestone
    if user.predictions_count >= 100:
        _award("century")

    # Perfect prediction (user.perfect_predictions is incremented by the scorer
    # in handlers.py before check_and_award is called)
    if user.perfect_predictions >= 1:
        _award("perfect_10")

    # 5 perfect predictions
    if user.perfect_predictions >= 5:
        _award("five_perfect")

    # ── Only checked when full score_result breakdown is available ────────────

    if score_result is not None:
        breakdown = score_result.get("breakdown", {})

        # MVP correctly predicted
        if breakdown.get("mvp", 0) > 0:
            _award("first_mvp")

    db.session.commit()
    return newly_awarded