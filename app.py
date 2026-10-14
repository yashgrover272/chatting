import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request


app = Flask(__name__)
DATABASE_PATH = Path(
    os.environ.get("DATABASE_PATH", Path(__file__).with_name("chat_history.db"))
)
ROOM_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,80}$")


def connect_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with closing(connect_database()) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "person TEXT NOT NULL, message TEXT NOT NULL)"
        )
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "room" not in columns:
            connection.execute(
                "ALTER TABLE messages ADD COLUMN room TEXT NOT NULL DEFAULT 'main'"
            )
        connection.commit()


def get_room():
    room = request.args.get("room", "")
    if not ROOM_PATTERN.fullmatch(room):
        abort(400, description="A valid conversation link is required.")
    return room


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/messages")
def get_messages():
    room = get_room()
    try:
        after_id = max(0, int(request.args.get("after", "0")))
    except ValueError:
        abort(400, description="The message cursor must be a number.")

    with closing(connect_database()) as connection:
        rows = connection.execute(
            "SELECT id, person, message FROM messages "
            "WHERE room = ? AND id > ? ORDER BY id LIMIT 200",
            (room, after_id),
        ).fetchall()

    return jsonify(
        [
            {"id": row["id"], "person": row["person"], "message": row["message"]}
            for row in rows
        ]
    )


@app.post("/api/messages")
def post_message():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="A message is required.")

    room = data.get("room", "")
    person = data.get("person", "")
    message = data.get("message", "")
    if not isinstance(room, str) or not ROOM_PATTERN.fullmatch(room):
        abort(400, description="A valid conversation link is required.")
    if not isinstance(person, str) or not isinstance(message, str):
        abort(400, description="Name and message must be text.")

    person = person.strip()
    message = message.strip()
    if not person or len(person) > 40:
        abort(400, description="Name must be between 1 and 40 characters.")
    if not message or len(message) > 2000:
        abort(400, description="Message must be between 1 and 2000 characters.")

    with closing(connect_database()) as connection:
        cursor = connection.execute(
            "INSERT INTO messages (room, person, message) VALUES (?, ?, ?)",
            (room, person, message),
        )
        connection.commit()

    return jsonify({"id": cursor.lastrowid}), 201


initialize_database()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))