import streamlit as st
from google import genai
from google.genai import types

# --- 1. SETUP ---
API_KEY = st.secrets["GEMINI_API_KEY"]  
client = genai.Client(api_key=API_KEY)

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
-If a student asks for pyqs, notes just send the past year notes/pyq link https://iiitbh-pyq-hub.vercel.app.
-If a student asks for syllabus, say go figure it out yourself.

IMPORTANT RULE: 
If a student asks a question about something that is NOT in this list, do not guess. Simply reply: "I don't have that information right now. Don't ask irrelevant stuff. Please DM the CR directly if you believe your query is genuine!"
"""

# --- 3. THE FIRST MESSAGE ---
# This is what pops up immediately when they open the website!
WELCOME_MESSAGE = """👋 Welcome! Here are the latest class updates:

1. **Engineering Materials:** Quiz next Friday at 6:00 PM (normal class still takes place).
2. **Math:** Class is tomorrow (Sunday) from 8:00 AM to 9:00 AM.
3. **Mechanical Theory:** Rescheduled to Monday from 3:00 PM to 4:00 PM.

What else can I help you with? (Type your question below)"""


# --- 4. WEB UI SETUP ---
st.set_page_config(page_title="CR Chatbot", page_icon="🎓")
st.title("🎓 Class Rep Chatbot")
# --- FLUID BACKGROUND ---
# --- ULTRA PREMIUM FLUID BACKGROUND ---
fluid_bg = """
<style>
/* 1. The Fluid Aurora Background */
.stApp {
    background: linear-gradient(-45deg, #050505, #1B092A, #2F0B38, #0A192F, #050505);
    background-size: 300% 300%;
    animation: aurora 20s ease infinite;
}
@keyframes aurora {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* 2. Hide the default Streamlit top header line */
[data-testid="stHeader"] {
    background-color: transparent !important;
}

/* 3. Frosted Glass Chat Bubbles */
[data-testid="stChatMessage"] {
    background: rgba(255, 255, 255, 0.03) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 15px !important;
    margin-bottom: 15px;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
}

/* 4. Glass Text Input Box */
[data-testid="stChatInput"] {
    background: rgba(255, 255, 255, 0.05) !important;
    backdrop-filter: blur(15px) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 20px !important;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3) !important;
}
</style>
"""
st.markdown(fluid_bg, unsafe_allow_html=True)

# Set up the chat history and inject the WELCOME_MESSAGE first!
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": WELCOME_MESSAGE}
    ]

# Display past chat bubbles
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 5. CHAT LOGIC ---
if user_question := st.chat_input("Ask a question..."):
    
    st.session_state.messages.append({"role": "user", "content": user_question})
    with st.chat_message("user"):
        st.markdown(user_question)

    with st.chat_message("assistant"):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=user_question,
                config=types.GenerateContentConfig(
                    system_instruction=ADMIN_KNOWLEDGE,
                )
            )
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            st.error(f"Error: {e}")
