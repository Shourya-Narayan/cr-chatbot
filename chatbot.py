import streamlit as st
from google import genai
from google.genai import types

# --- 1. SETUP ---
API_KEY = st.secrets["GEMINI_API_KEY"]  # <--- PASTE YOUR REAL KEY HERE
client = genai.Client(api_key=API_KEY)

# --- 2. ADMIN KNOWLEDGE BASE ---
# You can change this text whenever you want to update the students!
ADMIN_KNOWLEDGE = """
You are the official AI assistant for the Class Representative (CR).
Your job is to answer student questions based ONLY on the information below. 
Be friendly, helpful, and concise.

CURRENT CLASS INFO:
- Math Class: Monday and Wednesday at 10:00 AM.
- Physics Lab: CANCELED this week.
- Assignments: Python mini-project is due this Friday at midnight. No extensions!

IMPORTANT RULE: If a student asks a question about something that is NOT in this list, do not guess. Simply reply: "I don't have that information right now. Please DM the CR directly!"
"""

# --- 3. WEB UI SETUP ---
st.set_page_config(page_title="CR Chatbot", page_icon="🎓")
st.title("🎓 Class Rep Chatbot")
st.write("Ask me anything about class timings, deadlines, or announcements!")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 4. CHAT LOGIC ---
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