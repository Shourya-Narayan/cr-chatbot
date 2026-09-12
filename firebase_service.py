import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.security import generate_password_hash, check_password_hash
import os, json, re

_db = None

def get_db():
    """Lazy Firebase init — only connects when first used, not at import time."""
    global _db
    if _db is not None:
        return _db
    if not firebase_admin._apps:
        cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
        if not cred_json:
            raise RuntimeError("FIREBASE_CREDENTIALS_JSON env var not set!")
        try:
            cred_dict = json.loads(cred_json)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid FIREBASE_CREDENTIALS_JSON: {e}")
        # Fix mangled private_key newlines (common Heroku paste issue)
        if "private_key" in cred_dict:
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    _db = firestore.client()
    return _db


def make_uid(name):
    return re.sub(r"[^a-z0-9_]", "_", name.strip().lower())


def login_or_register(name, pin):
    db = get_db()
    uid = make_uid(name)
    ref = db.collection("users").document(uid)
    doc = ref.get()
    if not doc.exists:
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
    return None, None, "wrong_pin"


def save_message(uid, role, content):
    db = get_db()
    db.collection("users").document(uid).collection("messages").add({
        "role":      role,
        "content":   content,
        "timestamp": firestore.SERVER_TIMESTAMP,
    })


def get_user_messages(uid):
    db = get_db()
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
    db = get_db()
    users = []
    for doc in db.collection("users").stream():
        u = doc.to_dict()
        u["id"] = doc.id
        msgs = list(db.collection("users").document(doc.id).collection("messages").stream())
        u["message_count"] = len(msgs)
        last = u.get("last_seen")
        u["last_seen_str"] = last.strftime("%d %b, %I:%M %p") if last else "Never"
        users.append(u)
    users.sort(key=lambda x: x.get("last_seen") or 0, reverse=True)
    return users


def get_user_full_chat(uid):
    db = get_db()
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
