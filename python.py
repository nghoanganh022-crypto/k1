import streamlit as st
import pandas as pd
from google import genai
from google.genai.errors import APIError
from google.genai import types # Thêm import này để sử dụng types.GenerateContentConfig

# --- Cấu hình Trang Streamlit ---
st.set_page_config(
    page_title="App Phân Tích Báo Cáo Tài Chính",
    layout="wide"
)

st.title("Ứng dụng Phân Tích Báo Cáo Tài Chính 📊")

# --- Khởi tạo Client và Session (Cho khung Chat) ---

# 1. Khởi tạo Client Gemini (Chỉ chạy 1 lần)
if "gemini_client" not in st.session_state:
    api_key = st.secrets.get("GEMINI_API_KEY")
    if api_key:
        try:
            st.session_state.gemini_client = genai.Client(api_key=api_key)
        except Exception as e:
            st.session_state.gemini_client = None
            st.error(f"Lỗi khởi tạo Gemini Client: {e}")
    else:
        st.session_state.gemini_client = None

# 2. Khởi tạo Chat Session (Chỉ chạy 1 lần)
if "chat_session" not in st.session_state and st.session_state.gemini_client:
    # Định nghĩa hướng dẫn hệ thống để đặt bối cảnh cho AI
    system_instruction = "You are a friendly and professional financial analyst chatbot. Answer questions concisely based on the context provided or general financial knowledge."
    
    config = types.GenerateContentConfig(
        system_instruction=system_instruction
    )
    
    # Khởi tạo phiên chat
    st.session_state.chat_session = st.session_state.gemini_client.chats.create(
        model="gemini-2.5-flash",
        config=config
    )
    
    # Thiết lập lịch sử chat ban đầu
    st.session_state.chat_history = [{
        "role": "assistant", 
        "content": "Chào bạn! Tôi là Gemini AI, chuyên gia phân tích tài chính. Hãy tải lên file Excel để tôi giúp bạn, hoặc hỏi tôi bất cứ điều gì về tài chính nhé!"
    }]

# --- Hàm tính toán chính (Sử dụng Caching để Tối ưu hiệu suất) ---
@st.cache_data
def process_financial_data(df):
    """Thực hiện các phép tính Tăng trưởng và Tỷ trọng."""
    
    # Đảm bảo các giá trị là số để tính toán
    numeric_cols = ['Năm trước', 'Năm sau']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 1. Tính Tốc độ Tăng trưởng
    df['Tốc độ tăng trưởng (%)'] = (
        (df['Năm sau'] - df['Năm trước']) / df['Năm trước'].replace(0, 1e-9)
    ) * 100

    # 2. Tính Tỷ trọng theo Tổng Tài sản
    tong_tai_san_row = df[df['Chỉ tiêu'].str.contains('TỔNG CỘNG TÀI SẢN', case=False, na=False)]
    
    if tong_tai_san_row.empty:
        raise ValueError("Không tìm thấy chỉ tiêu 'TỔNG CỘNG TÀI SẢN'.")

    tong_tai_san_N_1 = tong_tai_san_row['Năm trước'].iloc[0]
    tong_tai_san_N = tong_tai_san_row['Năm sau'].iloc[0]

    # Xử lý chia cho 0 thủ công
    divisor_N_1 = tong_tai_san_N_1 if tong_tai_san_N_1 != 0 else 1e-9
    divisor_N = tong_tai_san_N if tong_tai_san_N != 0 else 1e-9

    # Tính tỷ trọng với mẫu số đã được xử lý
    df['Tỷ trọng Năm trước (%)'] = (df['Năm trước'] / divisor_N_1) * 100
    df['Tỷ trọng Năm sau (%)'] = (df['Năm sau'] / divisor_N) * 100
    
    return df

# --- Hàm gọi API Gemini (Cho Chức năng 5 - Phân tích tự động) ---
def get_ai_analysis(data_for_ai, api_key):
    """Gửi dữ liệu phân tích đến Gemini API và nhận nhận xét."""
    try:
        client = genai.Client(api_key=api_key)
        model_name = 'gemini-2.5-flash' 

        prompt = f"""
        Bạn là một chuyên gia phân tích tài chính chuyên nghiệp. Dựa trên các chỉ số tài chính sau, hãy đưa ra một nhận xét khách quan, ngắn gọn (khoảng 3-4 đoạn) về tình hình tài chính của doanh nghiệp. Đánh giá tập trung vào tốc độ tăng trưởng, thay đổi cơ cấu tài sản và khả năng thanh toán hiện hành.
        
        Dữ liệu thô và chỉ số:
        {data_for_ai}
        """

        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        return response.text

    except APIError as e:
        return f"Lỗi gọi Gemini API: Vui lòng kiểm tra Khóa API hoặc giới hạn sử dụng. Chi tiết lỗi: {e}"
    except KeyError:
        return "Lỗi: Không tìm thấy Khóa API 'GEMINI_API_KEY'. Vui lòng kiểm tra cấu hình Secrets trên Streamlit Cloud."
    except Exception as e:
        return f"Đã xảy ra lỗi không xác định: {e}"

# --- Hàm xử lý Phản hồi Chat (Cho khung Chat) ---
def generate_chat_response():
    """Xử lý input từ khung chat, gửi tới AI và cập nhật lịch sử."""
    user_prompt = st.session_state.user_chat_input
    if not user_prompt:
        return

    # Thêm tin nhắn người dùng vào lịch sử
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})

    # Xóa nội dung ô nhập liệu
    st.session_state.user_chat_input = "" 

    # Thêm bối cảnh dữ liệu tài chính (nếu đã tải file)
    full_prompt = user_prompt
    if 'financial_data_for_ai' in st.session_state:
        financial_data = st.session_state['financial_data_for_ai']
        context = f"\n\n[CONTEXT DỮ LIỆU ĐÃ TẢI LÊN:\n{financial_data}\nEND CONTEXT]\n\n"
        full_prompt = f"{context} {user_prompt}"

    try:
        # Gửi prompt tới phiên chat đã được khởi tạo
        with st.spinner('Đang chờ Gemini phản hồi...'):
            response = st.session_state.chat_session.send_message(full_prompt)
            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
    except Exception as e:
        error_message = f"Đã xảy ra lỗi khi giao tiếp với AI: {e}"
        st.session_state.chat_history.append({"role": "assistant", "content": error_message})


# --- Chức năng 1: Tải File ---
uploaded_file = st.file_uploader(
    "1. Tải file Excel Báo cáo Tài chính (Chỉ tiêu | Năm trước | Năm sau)",
    type=['xlsx', 'xls']
)

# Khởi tạo biến chỉ số để tránh lỗi nếu người dùng chưa tải file
thanh_toan_hien_hanh_N = "N/A"
thanh_toan_hien_hanh_N_1 = "N/A"

if uploaded_file is not None:
    try:
        df_raw = pd.read_excel(uploaded_file)
        
        # Tiền xử lý: Đảm bảo chỉ có 3 cột quan trọng
        df_raw.columns = ['Chỉ tiêu', 'Năm trước', 'Năm sau']
        
        # Xử lý dữ liệu
        df_processed = process_financial_data(df_raw.copy())

        if df_processed is not None:
            
            # --- Chức năng 2 & 3: Hiển thị Kết quả ---
            st.subheader("2. Tốc độ Tăng trưởng & 3. Tỷ trọng Cơ cấu Tài sản")
            st.dataframe(df_processed.style.format({
                'Năm trước': '{:,.0f}',
                'Năm sau': '{:,.0f}',
                'Tốc độ tăng trưởng (%)': '{:.2f}%',
                'Tỷ trọng Năm trước (%)': '{:.2f}%',
                'Tỷ trọng Năm sau (%)': '{:.2f}%'
            }), use_container_width=True)
            
            # --- Chức năng 4: Tính Chỉ số Tài chính ---
            st.subheader("4. Các Chỉ số Tài chính Cơ bản")
            
            try:
                # Lấy Tài sản ngắn hạn
                tsnh_n = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
                tsnh_n_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

                # Lấy Nợ ngắn hạn
                no_ngan_han_N = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]  
                no_ngan_han_N_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

                # Tính toán, xử lý chia cho 0
                if no_ngan_han_N != 0:
                    thanh_toan_hien_hanh_N = tsnh_n / no_ngan_han_N
                if no_ngan_han_N_1 != 0:
                    thanh_toan_hien_hanh_N_1 = tsnh_n_1 / no_ngan_han_N_1
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        label="Chỉ số Thanh toán Hiện hành (Năm trước)",
                        value=f"{thanh_toan_hien_hanh_N_1:.2f} lần" if isinstance(thanh_toan_hien_hanh_N_1, float) else thanh_toan_hien_hanh_N_1
                    )
                with col2:
                    delta_value = f"{thanh_toan_hien_hanh_N - thanh_toan_hien_hanh_N_1:.2f}" if isinstance(thanh_toan_hien_hanh_N, float) and isinstance(thanh_toan_hien_hanh_N_1, float) else None
                    st.metric(
                        label="Chỉ số Thanh toán Hiện hành (Năm sau)",
                        value=f"{thanh_toan_hien_hanh_N:.2f} lần" if isinstance(thanh_toan_hien_hanh_N, float) else thanh_toan_hien_hanh_N,
                        delta=delta_value
                    )
                    
            except IndexError:
                st.warning("Thiếu chỉ tiêu 'TÀI SẢN NGẮN HẠN' hoặc 'NỢ NGẮN HẠN' để tính chỉ số.")
                thanh_toan_hien_hanh_N = "N/A"
                thanh_toan_hien_hanh_N_1 = "N/A"
            except ZeroDivisionError:
                st.warning("Lỗi: Nợ Ngắn Hạn bằng 0, không thể tính Chỉ số Thanh toán Hiện hành.")
                thanh_toan_hien_hanh_N = "N/A"
                thanh_toan_hien_hanh_N_1 = "N/A"
            
            # --- Chức năng 5: Nhận xét AI ---
            st.subheader("5. Nhận xét Tình hình Tài chính (AI)")
            
            # Chuẩn bị dữ liệu để gửi cho AI
            data_for_ai = pd.DataFrame({
                'Chỉ tiêu': [
                    'Toàn bộ Bảng phân tích (dữ liệu thô)',  
                    'Tăng trưởng Tài sản ngắn hạn (%)',  
                    'Thanh toán hiện hành (N-1)',  
                    'Thanh toán hiện hành (N)'
                ],
                'Giá trị': [
                    df_processed.to_markdown(index=False),
                    f"{df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Tốc độ tăng trưởng (%)'].iloc[0]:.2f}%",  
                    f"{thanh_toan_hien_hanh_N_1}",  
                    f"{thanh_toan_hien_hanh_N}"
                ]
            }).to_markdown(index=False) 

            # LƯU DỮ LIỆU VÀO SESSION STATE ĐỂ CHAT AI SỬ DỤNG
            st.session_state['financial_data_for_ai'] = data_for_ai
            
            if st.button("Yêu cầu AI Phân tích"):
                api_key = st.secrets.get("GEMINI_API_KEY") 
                
                if api_key:
                    with st.spinner('Đang gửi dữ liệu và chờ Gemini phân tích...'):
                        ai_result = get_ai_analysis(data_for_ai, api_key)
                        st.markdown("**Kết quả Phân tích từ Gemini AI:**")
                        st.info(ai_result)
                else:
                    st.error("Lỗi: Không tìm thấy Khóa API. Vui lòng cấu hình Khóa 'GEMINI_API_KEY' trong Streamlit Secrets.")

    except ValueError as ve:
        st.error(f"Lỗi cấu trúc dữ liệu: {ve}")
    except Exception as e:
        st.error(f"Có lỗi xảy ra khi đọc hoặc xử lý file: {e}. Vui lòng kiểm tra định dạng file.")

else:
    st.info("Vui lòng tải lên file Excel để bắt đầu phân tích.")

# --- CHỨC NĂNG 6: KHUNG CHAT TƯƠNG TÁC ---
st.markdown("---") # Đường phân cách
st.subheader("Trò chuyện với Gemini AI 💬")

if st.session_state.gemini_client is None:
    st.error("⚠️ Lỗi: Không thể khởi tạo AI chat. Vui lòng kiểm tra khóa 'GEMINI_API_KEY' trong Streamlit Secrets.")
elif "chat_history" in st.session_state:
    # Hiển thị lịch sử chat
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Ô nhập liệu cho người dùng
    st.chat_input("Nhập câu hỏi của bạn (ví dụ: 'Thanh toán hiện hành là gì?' hoặc 'Nhận xét về tăng trưởng tài sản ngắn hạn')", 
                  key="user_chat_input", 
                  on_submit=generate_chat_response)
