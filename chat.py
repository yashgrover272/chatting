import json
import socket
import sqlite3
import threading
from contextlib import closing
from pathlib import Path


PORT = 5000
DATABASE_PATH = Path(__file__).with_name("chat_history.db")


def save_message(person, message):
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        connection.execute(
            "INSERT INTO messages (person, message) VALUES (?, ?)",
            (person, message),
        )
        connection.commit()


def receive_messages(connection):
    try:
        with connection.makefile("r", encoding="utf-8") as incoming:
            for line in incoming:
                message_data = json.loads(line)
                if message_data["type"] == "close":
                    print("\nThe other person left the chat.")
                    return

                person = message_data["person"]
                message = message_data["message"]
                save_message(person, message)
                print(f"\n{person}: {message}\nYou: ", end="", flush=True)
    except (ConnectionError, OSError, json.JSONDecodeError):
        pass


def connect(mode):
    if mode == "host":
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", PORT))
            server.listen(1)
            print(f"Waiting for the other person on port {PORT}...")
            connection, _ = server.accept()
            return connection

    host_address = input("Host computer IP address: ").strip()
    return socket.create_connection((host_address, PORT))


def main():
    person = input("Your name: ").strip() or "Person"
    mode = input("Type host or join: ").strip().lower()
    while mode not in {"host", "join"}:
        mode = input("Type host or join: ").strip().lower()

    with closing(sqlite3.connect(DATABASE_PATH)) as database:
        database.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY, person TEXT NOT NULL, message TEXT NOT NULL)"
        )
        database.commit()
        history = database.execute(
            "SELECT person, message FROM messages ORDER BY id"
        ).fetchall()

    for saved_person, saved_message in history:
        print(f"{saved_person}: {saved_message}")

    connection = connect(mode)
    receiver = threading.Thread(
        target=receive_messages, args=(connection,), daemon=True
    )
    receiver.start()

    try:
        while True:
            message = input("You: ")
            if message.strip().lower() == "exit":
                close_message = json.dumps({"type": "close"}) + "\n"
                connection.sendall(close_message.encode("utf-8"))
                break

            message_data = json.dumps(
                {"type": "message", "person": person, "message": message},
                ensure_ascii=False,
            )
            connection.sendall((message_data + "\n").encode("utf-8"))
            save_message(person, message)
    except (EOFError, ConnectionError, OSError):
        pass
    finally:
        connection.shutdown(socket.SHUT_RDWR)
        connection.close()


if __name__ == "__main__":
    main()