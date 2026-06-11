from app import create_app
from app.scheduler import start_scheduler

app = create_app()
scheduler = start_scheduler(app)

if __name__ == "__main__":
    app.run(debug=False, port=5000)
