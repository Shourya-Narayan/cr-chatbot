import firebase_admin
from firebase_admin import credentials, firestore
import os, json

def _init():
    if firebase_admin._apps:
        return firestore.client()
    cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
    elif os.path.exists("firebase-credentials.json"):
        cred = credentials.Certificate("firebase-credentials.json")
    else:
        raise RuntimeError("Firebase credentials not found! Set FIREBASE_CREDENTIALS_JSON env var.")
    firebase_admin.initialize_app(cred)
    return firestore.client()

db = _init()


def save_user(user_info):
    db.collection("users").document(user_info["sub"]).set({
        "name":      user_info.get("name", ""),
        "email":     user_info.get("email", ""),
        "photo":     user_info.get("picture", ""),
        "last_seen": firestore.SERVER_TIMESTAMP,
    }, merge=True)


def save_message(google_id, role, content):
    db.collection("users").document(google_id).collection("messages").add({
        "role":      role,
        "content":   content,
        "timestamp": firestore.SERVER_TIMESTAMP,
    })


def get_user_messages(google_id):
    docs = (db.collection("users").document(google_id)
              .collection("messages").order_by("timestamp").stream())
    result = []
    for doc in docs:
        m = doc.to_dict()
        result.append({
            "role":    m.get("role", ""),
            "content": m.get("content", ""),
            "time":    m["timestamp"].strftime("%I:%M %p") if m.get("timestamp") else "",
        })
    return result


def get_all_users():
    users = []
    for doc in db.collection("users").stream():
        u = doc.to_dict()
        u["id"] = doc.id
        msgs = list(db.collection("users").document(doc.id).collection("messages").stream())
        u["message_count"] = len(msgs)
        last = u.get("last_seen")
        u["last_seen_str"] = last.strftime("%d %b, %I:%M %p") if last else "—"
        users.append(u)
    users.sort(key=lambda x: x.get("last_seen") or 0, reverse=True)
    return users


def get_user_full_chat(google_id):
    doc = db.collection("users").document(google_id).get()
    user = doc.to_dict() if doc.exists else {}
    docs = (db.collection("users").document(google_id)
              .collection("messages").order_by("timestamp").stream())
    messages = []
    for d in docs:
        m = d.to_dict()
        messages.append({
            "role":    m.get("role", ""),
            "content": m.get("content", ""),
            "time":    m["timestamp"].strftime("%d %b, %I:%M %p") if m.get("timestamp") else "",
        })
    return user, messages
