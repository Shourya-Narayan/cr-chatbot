from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for)
from google import genai
from google.genai import types
from dotenv import load_dotenv
from functools import wraps
import firebase_service as fb
import os
import traceback

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "cr-chatbot-secret-change-me")

API_KEYS = [k for k in [
    os.getenv("GEMINI_API_KEY_1", ""),
    os.getenv("GEMINI_API_KEY_2", ""),
    os.getenv("GEMINI_API_KEY_3", ""),
    os.getenv("GEMINI_API_KEY_4", ""),
] if k]

ADMIN_NAME = os.getenv("ADMIN_NAME", "").strip().lower()

ADMIN_KNOWLEDGE = """
You are the official AI assistant for the Class Representative (CR).
Your job is to answer student questions based ONLY on the information below.
Be friendly, helpful, and concise.

IMPORTANT INFO / ANNOUNCEMENTS:
1. Engineering Materials: There is a quiz next Friday at 6:00 PM. (The normal class will still take place that day).
2. Math: Tomorrow (Sunday) there will be a math class from 8:00 AM to 9:00 AM.
3. Mechanical Theory: Last week's Friday class has been rescheduled to Monday from 3:00 PM to 4:00 PM.

LINKS:
- Class schedule: https://drive.google.com/file/d/1rdlji6W6JU75uzLu_XHAcsuWo2FsR3Tn/view?usp=sharing
- PYQs / Notes: https://iiitbh-pyq-hub.vercel.app
- Syllabus: go figure it out yourself.

IMPORTANT RULE:
If a student asks something NOT in this list, reply: "I don't have that information right now. Don't ask irrelevant stuff. Please DM the CR directly if you believe your query is genuine!"
"""

WELCOME_MESSAGE = """👋 Welcome! Here are the latest class updates:

1. **Engineering Materials:** Quiz next Friday at 6:00 PM (normal class still takes place).
2. **Math:** Class is tomorrow (Sunday) from 8:00 AM to 9:00 AM.
3. **Mechanical Theory:** Rescheduled to Monday from 3:00 PM to 4:00 PM.

What else can I help you with?"""


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
        if "user" not in session or not session.get("is_admin"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return dec


# Health check route — helps debug startup
@app.route("/health")
def health():
    status = {
        "api_keys": len(API_KEYS),
        "admin_name_set": bool(ADMIN_NAME),
        "firebase_creds_set": bool(os.getenv("FIREBASE_CREDENTIALS_JSON")),
    }
    return jsonify(status)


@app.route("/")
@login_required
def index():
    user = session["user"]
    try:
        history = fb.get_user_messages(user["uid"])
    except Exception:
        history = []
    return render_template("index.html",
                           welcome=WELCOME_MESSAGE,
                           user=user,
                           history=history,
                           is_admin=session.get("is_admin", False))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        pin  = request.form.get("pin", "").strip()
        if not name or len(pin) != 4 or not pin.isdigit():
            error = "Please enter your name and a valid 4-digit PIN."
        else:
            try:
                uid, user, status = fb.login_or_register(name, pin)
                if status == "wrong_pin":
                    error = "wrong_pin"
                else:
                    session["user"] = user
                    session["messages"] = []
                    session["is_admin"] = (fb.make_uid(name) == ADMIN_NAME or
                                           name.strip().lower() == ADMIN_NAME)
                    return redirect(url_for("index"))
            except Exception as e:
                error = f"Server error: {str(e)}"
    return render_template("login.html", error=error)


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
    uid = session["user"]["uid"]
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
    try:
        users = fb.get_all_users()
    except Exception as e:
        users = []
    return render_template("admin.html", users=users)


@app.route("/admin/user/<uid>")
@admin_required
def admin_user(uid):
    try:
        user, messages = fb.get_user_full_chat(uid)
    except Exception:
        user, messages = {}, []
    return render_template("admin_chat.html", user=user, messages=messages)


@app.errorhandler(500)
def server_error(e):
    return f"""
    <html><body style="font-family:monospace;padding:30px;background:#0a0010;color:#e0d7ff">
    <h2 style="color:#f87171">500 Server Error</h2>
    <pre style="background:rgba(255,255,255,0.05);padding:16px;border-radius:8px">{traceback.format_exc()}</pre>
    </body></html>
    """, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
