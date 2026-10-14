# Chatting

## Run locally

Install the packages and start the app:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000` and share the invite link with the other person. The first browser to join becomes Person 1, and the second becomes Person 2. Each browser keeps its role when it reconnects; each conversation is limited to two browser profiles.

## Deploy on Render

The `render.yaml` file selects Python, installs the requirements, and starts the web app with Gunicorn. If configuring the existing Render service manually, set the build command to `python -m pip install -r requirements.txt` and the start command to `python -m gunicorn app:app --bind 0.0.0.0:$PORT`.

SQLite files on Render's default filesystem are not durable across restarts or deploys. To retain chat history, attach a persistent disk mounted at `/var/data` and set `DATABASE_PATH` to `/var/data/chat_history.db` in the service environment. Persistent disks require a paid Render service.