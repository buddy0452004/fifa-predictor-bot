"""
Scoring Engine
Points breakdown:
  Winner correct:       +10
  MVP correct:          +20
  Each Top3 correct:    +10 per player (max +30)
  Score correct:        +30
  Perfect prediction:   +20 bonus
"""

POINTS = {
    "winner": 10,
    "mvp": 20,
    "top_player": 10,   # per player
    "score": 30,
    "perfect_bonus": 20,
}

STORE_ITEMS = {
    "double_points": {"name": "⚡ Double Points", "cost": 200, "description": "Double your points for one match"},
    "score_shield":  {"name": "🛡️ Score Shield",  "cost": 150, "description": "Keep your score points even if wrong"},
    "mvp_hint":      {"name": "🔍 MVP Hint",      "cost": 100, "description": "Get a hint about the likely MVP"},
}


def calculate_score(prediction, result, active_powers=None):
    """
    Compare a Prediction object against a Result object.
    Returns dict: { breakdown: {...}, total: int, is_perfect: bool }
    """
    active_powers = active_powers or []
    breakdown = {}
    total = 0
    correct_count = 0
    possible_correct = 5  # winner + mvp + 3 top players + score = 6 fields, but score is bonus

    # Winner
    if prediction.winner and result.winner:
        if prediction.winner.strip().lower() == result.winner.strip().lower():
            breakdown["winner"] = POINTS["winner"]
            total += POINTS["winner"]
            correct_count += 1
        else:
            breakdown["winner"] = 0

    # MVP
    if prediction.mvp and result.mvp:
        if prediction.mvp.strip().lower() == result.mvp.strip().lower():
            breakdown["mvp"] = POINTS["mvp"]
            total += POINTS["mvp"]
            correct_count += 1
        else:
            breakdown["mvp"] = 0

    # Top 3 players
    predicted_top3 = {
        prediction.top1.strip().lower() if prediction.top1 else None,
        prediction.top2.strip().lower() if prediction.top2 else None,
        prediction.top3.strip().lower() if prediction.top3 else None,
    }
    predicted_top3.discard(None)

    result_top3 = {
        result.top1.strip().lower() if result.top1 else None,
        result.top2.strip().lower() if result.top2 else None,
        result.top3.strip().lower() if result.top3 else None,
    }
    result_top3.discard(None)

    top3_correct = len(predicted_top3 & result_top3)
    top3_points = top3_correct * POINTS["top_player"]
    breakdown["top3"] = top3_points
    total += top3_points
    correct_count += top3_correct

    # Score
    score_correct = False
    if prediction.score and result.score:
        if prediction.score.strip() == result.score.strip():
            score_pts = POINTS["score"]
            if "score_shield" in active_powers:
                score_pts = POINTS["score"]  # shield not relevant if correct
            breakdown["score"] = score_pts
            total += score_pts
            score_correct = True
            correct_count += 1
        else:
            if "score_shield" in active_powers:
                breakdown["score"] = POINTS["score"] // 2  # half points with shield
                total += POINTS["score"] // 2
            else:
                breakdown["score"] = 0

    # Perfect bonus (winner + mvp + all 3 top players + score all correct)
    is_perfect = (
        breakdown.get("winner", 0) > 0
        and breakdown.get("mvp", 0) > 0
        and top3_correct == 3
        and score_correct
    )

    if is_perfect:
        breakdown["perfect_bonus"] = POINTS["perfect_bonus"]
        total += POINTS["perfect_bonus"]

    # Double points power
    if "double_points" in active_powers:
        total *= 2
        breakdown["double_points_applied"] = True

    return {
        "breakdown": breakdown,
        "total": total,
        "is_perfect": is_perfect,
        "top3_correct": top3_correct,
    }
