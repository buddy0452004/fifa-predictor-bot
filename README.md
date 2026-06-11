# ⚽ FIFA Predictor League — WhatsApp Bot

A skill-based football prediction game that runs entirely inside a WhatsApp group. No app installs, no registration friction.

---

## Features

- `/predict` — Submit match predictions
- `/leaderboard` — Live top 10 rankings
- `/profile` — Personal stats and achievements
- `/store` — Buy power-ups with earned tokens
- Auto-scoring engine with achievement detection
- Background scheduler auto-locks predictions at kickoff

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.11 + Flask |
| Database | PostgreSQL |
| WhatsApp | Meta WhatsApp Cloud API |
| Deployment | Any VPS (Railway, Render, DigitalOcean) |

---

## Setup Guide

### 1. Clone and install

```bash
git clone <your-repo>
cd whatsapp-predictor
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in your values
```

### 3. Get WhatsApp Cloud API credentials

1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Create an App → Business → WhatsApp
3. Under WhatsApp → API Setup, copy:
   - **Phone Number ID** → `WHATSAPP_PHONE_ID`
   - **Temporary Access Token** → `WHATSAPP_TOKEN` (use permanent token for production)
4. Set your `VERIFY_TOKEN` to any random string

### 4. Set up PostgreSQL

```bash
createdb predictor_db
```

### 5. Run the app

```bash
python run.py
```

### 6. Expose to internet (for webhook)

Use [ngrok](https://ngrok.com) for local dev:
```bash
ngrok http 5000
```

Set webhook URL in Meta dashboard:
```
https://your-ngrok-url.ngrok.io/webhook
```

Verification token = whatever you set in `VERIFY_TOKEN`

---

## Admin Setup

In `app/handlers.py`, add admin phone numbers:

```python
ADMIN_PHONES = ["911234567890", "919876543210"]
```

Phone numbers must be in international format without `+`.

---

## Commands Reference

### Player Commands
| Command | Description |
|---------|-------------|
| `/predict [match_id]` | Submit prediction |
| `/copy [match_id]` | Get fillable form |
| `/profile` | View your stats |
| `/leaderboard` | Top 10 players |
| `/store` | Browse power-ups |
| `/buy [item]` | Purchase power-up |
| `/inventory` | Your items |
| `/use [item] [match_id]` | Activate power |
| `/setname [name]` | Set display name |
| `/help` | All commands |

### Admin Commands
| Command | Description |
|---------|-------------|
| `/creatematch` | Create a new match |
| `/result [match_id]` | Enter match result + trigger scoring |

---

## Scoring System

| Prediction | Points |
|-----------|--------|
| Correct winner | +10 |
| Correct MVP | +20 |
| Each correct Top3 player | +10 (max +30) |
| Correct exact score | +30 |
| **Perfect prediction bonus** | **+20** |
| **Max per match** | **110** |

---

## Power-Ups (Store)

| Power | Cost | Effect |
|-------|------|--------|
| ⚡ Double Points | 200 🪙 | 2× points for one match |
| 🛡️ Score Shield | 150 🪙 | Half points even for wrong score |
| 🔍 MVP Hint | 100 🪙 | Admin-provided MVP hint |

---

## Achievements

| Achievement | Trigger | Tokens |
|------------|---------|--------|
| ⚽ Debut Goal | First prediction | +50 |
| 🌟 Star Spotter | First correct MVP | +30 |
| 💎 Perfect 10 | First perfect prediction | +100 |
| 🔥 On Fire | 5 perfect predictions | +200 |
| 📊 Veteran | 10 predictions | +75 |
| 💯 Century | 100 predictions | +500 |

---

## Deployment (Production)

### Railway (Recommended — Free tier available)
```bash
railway init
railway up
railway variables set WHATSAPP_TOKEN=... WHATSAPP_PHONE_ID=... VERIFY_TOKEN=... DATABASE_URL=...
```

### Render
1. Connect GitHub repo
2. Build: `pip install -r requirements.txt`
3. Start: `gunicorn run:app`
4. Add PostgreSQL database service

---

## Version 2 Ideas

- World Cup tournament bracket mode
- Lucky draw with token pool
- Match statistics page
- Streak tracking (win streaks, prediction streaks)
- Group vs group leagues
