from flask import Flask, render_template, request, jsonify, session
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "cr-chatbot-secret-2024")

# --- 1. API KEYS (4 keys with fallback) ---
API_KEYS = [
    os.getenv("GEMINI_API_KEY_1", ""),
    os.getenv("GEMINI_API_KEY_2", ""),
    os.getenv("GEMINI_API_KEY_3", ""),
    os.getenv("GEMINI_API_KEY_4", ""),
]
API_KEYS = [k for k in API_KEYS if k]

if not API_KEYS:
    raise RuntimeError("No API keys found! Add GEMINI_API_KEY_1 .. _4 in your .env file.")


# --- 2. ADMIN KNOWLEDGE BASE ---
ADMIN_KNOWLEDGE = """
You are the official AI assistant for the Class Representative (CR).
Your job is to answer student questions based ONLY on the information below.
Be friendly, helpful, and concise.

IMPORTANT INFO / ANNOUNCEMENTS:
1. Engineering Materials: There is a quiz next Friday at 6:00 PM. (Note: The normal Engineering Materials class will still take place that day).
2. Math: Tomorrow (Sunday) there will be a math class from 8:00 AM to 9:00 AM.
3. Mechanical Theory: Last week's Friday class has been rescheduled to Monday from 3:00 PM to 4:00 PM.

LINKS:
- If a student asks for the class schedule, give them this exact link: https://drive.google.com/file/d/1rdlji6W6JU75uzLu_XHAcsuWo2FsR3Tn/view?usp=sharing
- If a student asks for pyqs, notes just send the past year notes/pyq link https://iiitbh-pyq-hub.vercel.app.
- If a student asks for syllabus, say go figure it out yourself.

IMPORTANT RULE:
If a student asks a question about something that is NOT in this list, do not guess. Simply reply: "I don't have that information right now. Don't ask irrelevant stuff. Please DM the CR directly if you believe your query is genuine!"
"""

WELCOME_MESSAGE = """👋 Welcome! Here are the latest class updates:

1. **Engineering Materials:** Quiz next Friday at 6:00 PM (normal class still takes place).
2. **Math:** Class is tomorrow (Sunday) from 8:00 AM to 9:00 AM.
3. **Mechanical Theory:** Rescheduled to Monday from 3:00 PM to 4:00 PM.

What else can I help you with? (Type your question below)"""


# --- 3. FALLBACK API CALL ---
def get_response_with_fallback(history):
    last_error = None
    for key in API_KEYS:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=history,
                config=types.GenerateContentConfig(
                    system_instruction=ADMIN_KNOWLEDGE,
                )
            )
            return response.text
        except Exception as e:
            last_error = e
            continue
    raise last_error


# --- 4. ROUTES ---
@app.route("/")
def index():
    session["messages"] = []
    return render_template("index.html", welcome=WELCOME_MESSAGE)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    if "messages" not in session:
        session["messages"] = []

    session["messages"].append({
        "role": "user",
        "parts": [{"text": user_message}]
    })
    session.modified = True

    try:
        reply = get_response_with_fallback(session["messages"])
        session["messages"].append({
            "role": "model",
            "parts": [{"text": reply}]
        })
        session.modified = True
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": f"All API keys failed: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
