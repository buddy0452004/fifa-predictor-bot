"""
Background scheduler — auto-closes predictions 5 minutes before kickoff.
Run this alongside your Flask app or integrate with APScheduler.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta


def auto_close_matches(app):
    """Close matches that are about to start."""
    with app.app_context():
        from app.database import db, Match
        cutoff = datetime.utcnow() + timedelta(minutes=5)
        open_matches = Match.query.filter(
            Match.status == "open",
            Match.start_time <= cutoff
        ).all()
        for match in open_matches:
            match.status = "closed"
        if open_matches:
            db.session.commit()
            print(f"[Scheduler] Closed {len(open_matches)} match(es)")


def start_scheduler(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: auto_close_matches(app),
        trigger="interval",
        minutes=1,
        id="auto_close_matches",
    )
    scheduler.start()
    return scheduler
