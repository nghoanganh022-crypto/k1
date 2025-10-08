import streamlit as st
import google.generativeai as genai

# --- Cấu hình Gemini API ---
genai.configure(api_key=st.secrets["gemini_api_key"])

# --- Khởi tạo mô hình ---
model = genai.GenerativeModel("gemini-1.5-flash")

# --- Giao diện Chat ---
st.markdown("---")
st.subheader("💬 Trò chuyện với Gemini")

# Khởi tạo session state cho lịch sử hội thoại
if "messages" not in st.session_state:
    st.session_state.messages = []

# Hiển thị lịch sử
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Ô nhập chat
if prompt := st.chat_input("Nhập câu hỏi của bạn..."):
    # Hiển thị ngay tin nhắn người dùng
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    try:
        # Gọi API Gemini
        response = model.generate_content(prompt)
        reply = response.text

    except Exception as e:
        reply = f"⚠️ Lỗi khi gọi Gemini API: {e}"

    # Hiển thị phản hồi
    with st.chat_message("assistant"):
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
