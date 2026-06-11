from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    points = db.Column(db.Integer, default=0)
    tokens = db.Column(db.Integer, default=0)
    predictions_count = db.Column(db.Integer, default=0)
    perfect_predictions = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    predictions = db.relationship("Prediction", backref="user", lazy=True)
    achievements = db.relationship("UserAchievement", backref="user", lazy=True)
    inventory = db.relationship("Inventory", backref="user", lazy=True)


class Match(db.Model):
    __tablename__ = "matches"
    id = db.Column(db.Integer, primary_key=True)
    team1 = db.Column(db.String(100), nullable=False)
    team2 = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="open")  # open | closed | completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    predictions = db.relationship("Prediction", backref="match", lazy=True)
    result = db.relationship("Result", backref="match", uselist=False, lazy=True)


class Prediction(db.Model):
    __tablename__ = "predictions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False)
    winner = db.Column(db.String(100))
    mvp = db.Column(db.String(100))
    top1 = db.Column(db.String(100))
    top2 = db.Column(db.String(100))
    top3 = db.Column(db.String(100))
    score = db.Column(db.String(10))
    points_awarded = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "match_id", name="unique_user_match"),)


class Result(db.Model):
    __tablename__ = "results"
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False, unique=True)
    winner = db.Column(db.String(100))
    mvp = db.Column(db.String(100))
    top1 = db.Column(db.String(100))
    top2 = db.Column(db.String(100))
    top3 = db.Column(db.String(100))
    score = db.Column(db.String(10))
    entered_at = db.Column(db.DateTime, default=datetime.utcnow)


class Achievement(db.Model):
    __tablename__ = "achievements"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    token_reward = db.Column(db.Integer, default=0)
    emoji = db.Column(db.String(10), default="🏆")


class UserAchievement(db.Model):
    __tablename__ = "user_achievements"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey("achievements.id"), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)

    achievement = db.relationship("Achievement")
    __table_args__ = (db.UniqueConstraint("user_id", "achievement_id", name="unique_user_achievement"),)


class Inventory(db.Model):
    __tablename__ = "inventory"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    power = db.Column(db.String(50), nullable=False)  # double_points | score_shield | mvp_hint
    quantity = db.Column(db.Integer, default=0)
    __table_args__ = (db.UniqueConstraint("user_id", "power", name="unique_user_power"),)
