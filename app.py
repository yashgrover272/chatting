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
DEVICE_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


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
        connection.execute(
            "CREATE TABLE IF NOT EXISTS participants ("
            "room TEXT NOT NULL, device_id TEXT NOT NULL, person TEXT NOT NULL, "
            "PRIMARY KEY (room, device_id), UNIQUE (room, person))"
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


@app.post("/api/join")
def join_room():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="A conversation and device are required.")

    room = data.get("room", "")
    device_id = data.get("device_id", "")
    if not isinstance(room, str) or not ROOM_PATTERN.fullmatch(room):
        abort(400, description="A valid conversation link is required.")
    if not isinstance(device_id, str) or not DEVICE_PATTERN.fullmatch(device_id):
        abort(400, description="A valid device ID is required.")

    with closing(connect_database()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        participant = connection.execute(
            "SELECT person FROM participants WHERE room = ? AND device_id = ?",
            (room, device_id),
        ).fetchone()
        if participant:
            connection.commit()
            return jsonify({"person": participant["person"]})

        assigned_people = {
            row["person"]
            for row in connection.execute(
                "SELECT person FROM participants WHERE room = ?", (room,)
            ).fetchall()
        }
        person = next(
            (candidate for candidate in ("Person 1", "Person 2") if candidate not in assigned_people),
            None,
        )
        if person is None:
            connection.rollback()
            return jsonify({"error": "This conversation already has two people."}), 409

        connection.execute(
            "INSERT INTO participants (room, device_id, person) VALUES (?, ?, ?)",
            (room, device_id, person),
        )
        connection.commit()

    return jsonify({"person": person})


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
    device_id = data.get("device_id", "")
    message = data.get("message", "")
    if not isinstance(room, str) or not ROOM_PATTERN.fullmatch(room):
        abort(400, description="A valid conversation link is required.")
    if not isinstance(device_id, str) or not DEVICE_PATTERN.fullmatch(device_id):
        abort(400, description="A valid device ID is required.")
    if not isinstance(message, str):
        abort(400, description="Message must be text.")

    message = message.strip()
    if not message or len(message) > 2000:
        abort(400, description="Message must be between 1 and 2000 characters.")

    with closing(connect_database()) as connection:
        participant = connection.execute(
            "SELECT person FROM participants WHERE room = ? AND device_id = ?",
            (room, device_id),
        ).fetchone()
        if participant is None:
            abort(403, description="Join this conversation before sending a message.")

        cursor = connection.execute(
            "INSERT INTO messages (room, person, message) VALUES (?, ?, ?)",
            (room, participant["person"], message),
        )
        connection.commit()

    return jsonify({"id": cursor.lastrowid}), 201


initialize_database()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))