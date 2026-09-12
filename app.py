from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from google import genai
from google.genai import types
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from functools import wraps
import firebase_service as fb
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "cr-chatbot-secret-key-change-me")

# --- API KEYS ---
API_KEYS = [k for k in [
    os.getenv("GEMINI_API_KEY_1", ""),
    os.getenv("GEMINI_API_KEY_2", ""),
    os.getenv("GEMINI_API_KEY_3", ""),
    os.getenv("GEMINI_API_KEY_4", ""),
] if k]

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

# --- GOOGLE OAUTH ---
oauth = OAuth(app)
google_oauth = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# --- KNOWLEDGE BASE ---
ADMIN_KNOWLEDGE = """
You are the official AI assistant for the Class Representative (CR).
Your job is to answer student questions based ONLY on the information below.
Be friendly, helpful, and concise.

IMPORTANT INFO / ANNOUNCEMENTS:
1. Engineering Materials: There is a quiz next Friday at 6:00 PM. (Note: The normal Engineering Materials class will still take place that day).
2. Math: Tomorrow (Sunday) there will be a math class from 8:00 AM to 9:00 AM.
3. Mechanical Theory: Last week's Friday class has been rescheduled to Monday from 3:00 PM to 4:00 PM.

LINKS:
- If a student asks for the class schedule: https://drive.google.com/file/d/1rdlji6W6JU75uzLu_XHAcsuWo2FsR3Tn/view?usp=sharing
- If a student asks for pyqs / notes: https://iiitbh-pyq-hub.vercel.app
- If a student asks for syllabus, say: go figure it out yourself.

IMPORTANT RULE:
If a student asks something NOT in this list, reply: "I don't have that information right now. Don't ask irrelevant stuff. Please DM the CR directly if you believe your query is genuine!"
"""

WELCOME_MESSAGE = """👋 Welcome! Here are the latest class updates:

1. **Engineering Materials:** Quiz next Friday at 6:00 PM (normal class still takes place).
2. **Math:** Class is tomorrow (Sunday) from 8:00 AM to 9:00 AM.
3. **Mechanical Theory:** Rescheduled to Monday from 3:00 PM to 4:00 PM.

What else can I help you with?"""


# --- HELPERS ---
def get_ai_reply(history):
    last_error = None
    for key in API_KEYS:
        try:
            client = genai.Client(api_key=key)
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=history,
                config=types.GenerateContentConfig(system_instruction=ADMIN_KNOWLEDGE),
            )
            return resp.text
        except Exception as e:
            last_error = e
    raise last_error


def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return dec


def admin_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if "user" not in session:
            return redirect(url_for("login"))
        if session["user"].get("email") != ADMIN_EMAIL:
            return "<h2 style='font-family:sans-serif;color:red;padding:40px'>403 — Access Denied</h2>", 403
        return f(*a, **kw)
    return dec


# --- ROUTES ---
@app.route("/")
@login_required
def index():
    user = session["user"]
    history = fb.get_user_messages(user["sub"])
    return render_template("index.html", welcome=WELCOME_MESSAGE, user=user, history=history)


@app.route("/login")
def login():
    if "user" in session:
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/google-login")
def google_login():
    return google_oauth.authorize_redirect(url_for("callback", _external=True))


@app.route("/callback")
def callback():
    token = google_oauth.authorize_access_token()
    session["user"] = dict(token.get("userinfo"))
    session["messages"] = []
    fb.save_user(session["user"])
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/chat", methods=["POST"])
@login_required
def chat():
    user_message = request.get_json().get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    uid = session["user"]["sub"]
    if "messages" not in session:
        session["messages"] = []

    session["messages"].append({"role": "user", "parts": [{"text": user_message}]})
    session.modified = True

    try:
        reply = get_ai_reply(session["messages"])
        session["messages"].append({"role": "model", "parts": [{"text": reply}]})
        session.modified = True
        fb.save_message(uid, "user", user_message)
        fb.save_message(uid, "assistant", reply)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin")
@admin_required
def admin():
    return render_template("admin.html", users=fb.get_all_users())


@app.route("/admin/user/<uid>")
@admin_required
def admin_user(uid):
    user, messages = fb.get_user_full_chat(uid)
    return render_template("admin_chat.html", user=user, messages=messages)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
