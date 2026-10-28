import os

from app import create_app, socketio

app = create_app()

app.config["AT_USERNAME"] = os.getenv(
    "AT_USERNAME",
    "sandbox"
)

app.config["AT_API_KEY"] = os.getenv("AT_API_KEY")

if __name__ == "__main__":
    socketio.run(app, debug=True)
