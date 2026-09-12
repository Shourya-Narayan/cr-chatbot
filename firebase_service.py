import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.security import generate_password_hash, check_password_hash
import os, json, re

def _init():
    if firebase_admin._apps:
        return firestore.client()
    cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
    elif os.path.exists("firebase-credentials.json"):
        cred = credentials.Certificate("firebase-credentials.json")
    else:
        raise RuntimeError("Firebase credentials not found!")
    firebase_admin.initialize_app(cred)
    return firestore.client()

db = _init()


def make_uid(name):
    """Convert name to a safe Firestore document ID."""
    return re.sub(r"[^a-z0-9_]", "_", name.strip().lower())


def login_or_register(name, pin):
    """
    Returns (uid, user_dict, status)
    status: "ok" | "wrong_pin" | "registered"
    """
    uid = make_uid(name)
    ref = db.collection("users").document(uid)
    doc = ref.get()

    if not doc.exists:
        # New user — register
        ref.set({
            "name":      name.strip(),
            "pin_hash":  generate_password_hash(pin),
            "created_at": firestore.SERVER_TIMESTAMP,
            "last_seen":  firestore.SERVER_TIMESTAMP,
        })
        return uid, {"name": name.strip(), "uid": uid}, "registered"

    user = doc.to_dict()
    user["uid"] = uid

    if check_password_hash(user["pin_hash"], pin):
        ref.update({"last_seen": firestore.SERVER_TIMESTAMP})
        return uid, user, "ok"
    else:
        return None, None, "wrong_pin"


def save_message(uid, role, content):
    db.collection("users").document(uid).collection("messages").add({
        "role":      role,
        "content":   content,
        "timestamp": firestore.SERVER_TIMESTAMP,
    })


def get_user_messages(uid):
    docs = (db.collection("users").document(uid)
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


def get_user_full_chat(uid):
    doc = db.collection("users").document(uid).get()
    user = doc.to_dict() if doc.exists else {}
    docs = (db.collection("users").document(uid)
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
