import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.security import generate_password_hash, check_password_hash
import os, json, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

_db = None

# Pre-defined student list with PINs (generated once)
STUDENT_PINS = {'abhinav.260103001@iiitbh.ac.in': '2824', 'abhishek.260103002@iiitbh.ac.in': '1409', 'adrish.260103003@iiitbh.ac.in': '5506', 'aniket.260103004@iiitbh.ac.in': '5012', 'anshika.260103005@iiitbh.ac.in': '4657', 'anuj.260103006@iiitbh.ac.in': '3286', 'arpan.260103007@iiitbh.ac.in': '2679', 'arunika.260103008@iiitbh.ac.in': '9935', 'auroshish.260103009@iiitbh.ac.in': '2424', 'avishkar.260103010@iiitbh.ac.in': '7912', 'ayala.260103011@iiitbh.ac.in': '1520', 'ayush.260103012@iiitbh.ac.in': '1488', 'ayush.260103013@iiitbh.ac.in': '2535', 'bhoma.260103014@iiitbh.ac.in': '4582', 'bormala.260103015@iiitbh.ac.in': '4811', 'burle.260103016@iiitbh.ac.in': '9279', 'chaitanya.260103017@iiitbh.ac.in': '1434', 'chirantan.260103018@iiitbh.ac.in': '4257', 'deependra.260103019@iiitbh.ac.in': '9928', 'dhruv.260103020@iiitbh.ac.in': '7873', 'dushyant.260103021@iiitbh.ac.in': '4611', 'gautam.260103022@iiitbh.ac.in': '8359', 'guguloth.260103023@iiitbh.ac.in': '5557', 'harsh.260103024@iiitbh.ac.in': '1106', 'himanshu.260103025@iiitbh.ac.in': '3615', 'jasthi.260103026@iiitbh.ac.in': '7924', 'kanderi.260103027@iiitbh.ac.in': '6574', 'kornana.260103028@iiitbh.ac.in': '5552', 'krishika.260103029@iiitbh.ac.in': '3547', 'laban.260103030@iiitbh.ac.in': '4527', 'manne.260103031@iiitbh.ac.in': '6514', 'manupati.260103032@iiitbh.ac.in': '2674', 'medasari.260103033@iiitbh.ac.in': '2519', 'mukul.260103034@iiitbh.ac.in': '7224', 'parteek.260103035@iiitbh.ac.in': '2584', 'parth.260103036@iiitbh.ac.in': '6881', 'pechetti.260103037@iiitbh.ac.in': '6635', 'prince.260103038@iiitbh.ac.in': '5333', 'priya.260103039@iiitbh.ac.in': '1711', 'rahul.260103040@iiitbh.ac.in': '8527', 'raja.260103041@iiitbh.ac.in': '9785', 'ravi.260103042@iiitbh.ac.in': '3045', 'reyansh.260103043@iiitbh.ac.in': '7201', 'rishav.260103044@iiitbh.ac.in': '2291', 'saiteja.260103045@iiitbh.ac.in': '5803', 'saksham.260103046@iiitbh.ac.in': '6925', 'sakshi.260103047@iiitbh.ac.in': '4150', 'sanjeet.260103048@iiitbh.ac.in': '2139', 'satyam.260103049@iiitbh.ac.in': '1750', 'sayan.260103050@iiitbh.ac.in': '4733', 'shivam.260103051@iiitbh.ac.in': '5741', 'shourya.260103052@iiitbh.ac.in': '2307', 'shubh.260103053@iiitbh.ac.in': '4814', 'shubham.260103054@iiitbh.ac.in': '2654', 'shubham.260103055@iiitbh.ac.in': '7227', 'soumanka.260103056@iiitbh.ac.in': '5554', 'sudhama.260103057@iiitbh.ac.in': '8428', 'tanishq.260103058@iiitbh.ac.in': '6977', 'thirunamalli.260103059@iiitbh.ac.in': '3664', 'utkarsh.260103060@iiitbh.ac.in': '7065'}

def get_db():
    global _db
    if _db is not None:
        return _db
    if not firebase_admin._apps:
        cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
        if not cred_json:
            raise RuntimeError("FIREBASE_CREDENTIALS_JSON not set!")
        try:
            cred_dict = json.loads(cred_json)
        except json.JSONDecodeError:
            cred_dict = json.loads(cred_json.replace("\\n", "\n"))
        if "private_key" in cred_dict:
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
        firebase_admin.initialize_app(credentials.Certificate(cred_dict))
    _db = firestore.client()
    return _db


def email_to_uid(email):
    """Use email as Firestore doc ID (safe — dots/@ allowed)."""
    return email.strip().lower()


def get_display_name(email):
    """Extract first name from email like harsh.260103024@iiitbh.ac.in -> Harsh"""
    name_part = email.split(".")[0]
    return name_part.capitalize()


# ── SEEDING ──────────────────────────────────────────────────────────────
def seed_all_students():
    """Write all 60 students to Firebase (upsert — safe to re-run)."""
    db = get_db()
    count = 0
    for email, pin in STUDENT_PINS.items():
        uid = email_to_uid(email)
        ref = db.collection("students").document(uid)
        # set() without merge overwrites; existing pin_hash & last_seen preserved via merge
        ref.set({
            "email":      email,
            "name":       get_display_name(email),
            "pin_hash":   generate_password_hash(pin),
            "pin_plain":  pin,
            "created_at": firestore.SERVER_TIMESTAMP,
            "last_seen":  None,
            "email_sent": False,
        }, merge=True)   # merge=True: only writes fields if not already present
        count += 1
    return count


# ── AUTH ─────────────────────────────────────────────────────────────────
def verify_login(email, pin):
    """Returns (uid, user_dict) or raises ValueError."""
    db = get_db()
    uid = email_to_uid(email)
    doc = db.collection("students").document(uid).get()
    if not doc.exists:
        raise ValueError("not_found")
    user = doc.to_dict()
    user["uid"] = uid
    if not check_password_hash(user["pin_hash"], pin):
        raise ValueError("wrong_pin")
    db.collection("students").document(uid).update({"last_seen": firestore.SERVER_TIMESTAMP})
    return uid, user


# ── MESSAGES ─────────────────────────────────────────────────────────────
def save_message(uid, role, content):
    db = get_db()
    db.collection("students").document(uid).collection("messages").add({
        "role":      role,
        "content":   content,
        "timestamp": firestore.SERVER_TIMESTAMP,
    })


def get_user_messages(uid):
    db = get_db()
    docs = (db.collection("students").document(uid)
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


# ── ADMIN ─────────────────────────────────────────────────────────────────
def get_all_students():
    db = get_db()
    students = []
    for doc in db.collection("students").stream():
        s = doc.to_dict()
        s["id"] = doc.id
        msgs = list(db.collection("students").document(doc.id).collection("messages").stream())
        s["message_count"] = len(msgs)
        last = s.get("last_seen")
        s["last_seen_str"] = last.strftime("%d %b, %I:%M %p") if last else "Never logged in"
        students.append(s)
    students.sort(key=lambda x: (x.get("last_seen") or 0), reverse=True)
    return students


def get_student_full_chat(uid):
    db = get_db()
    doc = db.collection("students").document(uid).get()
    user = doc.to_dict() if doc.exists else {}
    docs = (db.collection("students").document(uid)
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


# ── EMAIL ─────────────────────────────────────────────────────────────────
def send_pin_email(to_email, student_name, pin, sender_email, app_password, site_url):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your CR Chatbot Login PIN"
    msg["From"]    = f"CR Bot <{sender_email}>"
    msg["To"]      = to_email

    body = f"""Hi {student_name},

Your login credentials for the CR Chatbot are ready!

  Website : {site_url}
  Email   : {to_email}
  PIN     : {pin}

Use these to login and get the latest class updates, schedule, PYQs and more.

— Class Representative, IIIT Bhagalpur
"""
    html = f"""
<div style="font-family:Inter,sans-serif;max-width:480px;margin:0 auto;background:#0d0118;color:#ede9fe;border-radius:16px;padding:32px;border:1px solid rgba(139,92,246,0.3)">
  <div style="text-align:center;font-size:2.5rem;margin-bottom:16px">🎓</div>
  <h2 style="color:#c4b5fd;text-align:center;margin:0 0 8px">CR Chatbot — Login PIN</h2>
  <p style="color:rgba(200,185,255,0.6);text-align:center;font-size:0.9rem;margin:0 0 28px">Hi {student_name}! Here are your login credentials.</p>
  <div style="background:rgba(139,92,246,0.1);border:1px solid rgba(139,92,246,0.3);border-radius:12px;padding:20px;margin-bottom:24px">
    <p style="margin:0 0 8px;font-size:0.8rem;color:rgba(200,185,255,0.5)">EMAIL</p>
    <p style="margin:0 0 16px;font-weight:500">{to_email}</p>
    <p style="margin:0 0 8px;font-size:0.8rem;color:rgba(200,185,255,0.5)">YOUR PIN</p>
    <p style="font-size:2.5rem;font-weight:700;letter-spacing:12px;color:#a78bfa;margin:0">{pin}</p>
  </div>
  <a href="{site_url}" style="display:block;text-align:center;background:linear-gradient(135deg,#7c3aed,#4f46e5);color:#fff;padding:13px;border-radius:12px;text-decoration:none;font-weight:500">Open Chatbot →</a>
  <p style="text-align:center;font-size:0.72rem;color:rgba(200,185,255,0.3);margin-top:20px">IIIT Bhagalpur · Class Representative Portal</p>
</div>
"""
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, app_password)
        server.sendmail(sender_email, to_email, msg.as_string())

    # Mark email as sent
    db = get_db()
    db.collection("students").document(email_to_uid(to_email)).update({"email_sent": True})
