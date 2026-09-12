from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for)
from google import genai
from google.genai import types
from dotenv import load_dotenv
from functools import wraps
import firebase_service as fb
import os, traceback, threading, time


def _auto_seed():
    """Auto-seed students on startup if Firebase is empty. Runs in background."""
    time.sleep(5)  # wait for app to be ready
    try:
        if not fb.get_all_students():
            count = fb.seed_all_students()
            print(f"[AUTO-SEED] Seeded {count} students.")
        else:
            print("[AUTO-SEED] Students already exist, skipping.")
    except Exception as e:
        print(f"[AUTO-SEED] Error: {e}")

threading.Thread(target=_auto_seed, daemon=True).start()

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "cr-chatbot-secret-change-me")

API_KEYS = [k for k in [
    os.getenv("GEMINI_API_KEY_1", ""),
    os.getenv("GEMINI_API_KEY_2", ""),
    os.getenv("GEMINI_API_KEY_3", ""),
    os.getenv("GEMINI_API_KEY_4", ""),
] if k]

ADMIN_EMAIL  = os.getenv("ADMIN_EMAIL", "").strip().lower()
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
GMAIL_APP_PW = os.getenv("GMAIL_APP_PASSWORD", "")
SITE_URL     = os.getenv("SITE_URL", "https://shourya-and-harsh-cr.tech")

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


@app.route("/health")
def health():
    return {"api_keys": len(API_KEYS), "admin_email": bool(ADMIN_EMAIL),
            "sender_email": bool(SENDER_EMAIL), "firebase": bool(os.getenv("FIREBASE_CREDENTIALS_JSON"))}


@app.route("/")
@login_required
def index():
    user = session["user"]
    try:
        history = fb.get_user_messages(user["uid"])
    except Exception:
        history = []
    return render_template("index.html", welcome=WELCOME_MESSAGE, user=user,
                           history=history, is_admin=session.get("is_admin", False))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pin   = request.form.get("pin", "").strip()
        if not email or len(pin) != 4 or not pin.isdigit():
            error = "Please enter your email and 4-digit PIN."
        else:
            # ── Special admin login (bypasses Firebase student list) ──
            ADMIN_PIN = os.getenv("ADMIN_PIN", "2030")
            if email == ADMIN_EMAIL and pin == ADMIN_PIN:
                session["user"] = {"uid": "admin", "email": email, "name": "CR Admin"}
                session["messages"] = []
                session["is_admin"] = True
                return redirect(url_for("admin"))  # straight to admin panel

            # ── Regular student login via Firebase ──
            try:
                uid, user = fb.verify_login(email, pin)
                session["user"] = {"uid": uid, "email": email, "name": user.get("name", email.split(".")[0].capitalize())}
                session["messages"] = []
                session["is_admin"] = False
                return redirect(url_for("index"))
            except ValueError as e:
                error = str(e)
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    response = redirect(url_for("login"))
    response.delete_cookie("session")   # fully remove cookie from browser
    return response


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


# ── ADMIN ROUTES ──────────────────────────────────────────────────────────
@app.route("/admin")
@admin_required
def admin():
    try:
        students = fb.get_all_students()
    except Exception as e:
        students = []
    seeded = len(students) > 0
    return render_template("admin.html", students=students, seeded=seeded)


@app.route("/admin/seed", methods=["POST"])
@admin_required
def admin_seed():
    try:
        count = fb.seed_all_students()
        return jsonify({"ok": True, "seeded": count})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/admin/user/<uid>")
@admin_required
def admin_user(uid):
    try:
        user, messages = fb.get_student_full_chat(uid)
    except Exception:
        user, messages = {}, []
    return render_template("admin_chat.html", user=user, messages=messages)


@app.route("/admin/send-pin/<uid>", methods=["POST"])
@admin_required
def send_pin(uid):
    if not SENDER_EMAIL or not GMAIL_APP_PW:
        return jsonify({"ok": False, "error": "SENDER_EMAIL or GMAIL_APP_PASSWORD not set in Config Vars"}), 500
    try:
        db_doc = fb.get_db().collection("students").document(uid).get()
        if not db_doc.exists:
            return jsonify({"ok": False, "error": "Student not found"}), 404
        s = db_doc.to_dict()
        fb.send_pin_email(s["email"], s["name"], s["pin_plain"],
                          SENDER_EMAIL, GMAIL_APP_PW, SITE_URL)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/admin/send-all-pins", methods=["POST"])
@admin_required
def send_all_pins():
    if not SENDER_EMAIL or not GMAIL_APP_PW:
        return jsonify({"ok": False, "error": "Email credentials not set"}), 500
    def send_in_bg():
        students = fb.get_all_students()
        for s in students:
            try:
                fb.send_pin_email(s["email"], s["name"], s["pin_plain"],
                                  SENDER_EMAIL, GMAIL_APP_PW, SITE_URL)
            except Exception:
                pass
    threading.Thread(target=send_in_bg, daemon=True).start()
    return jsonify({"ok": True, "message": "Sending in background..."})


@app.errorhandler(500)
def server_error(e):
    return f"""<html><body style="font-family:monospace;padding:30px;background:#0a0010;color:#e0d7ff">
    <h2 style="color:#f87171">500 Server Error</h2>
    <pre style="background:rgba(255,255,255,0.05);padding:16px;border-radius:8px">{traceback.format_exc()}</pre>
    </body></html>""", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
