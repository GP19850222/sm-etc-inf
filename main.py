import streamlit as st
import pandas as pd
from streamlit.components.v1 import html # For JS/CSS integration
from streamlit_gsheets import GSheetsConnection # For Google Sheets
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
# Import functions from other modules
from utils.price_chart import calculate_metrics_values, create_advanced_price_chart
from utils.detail_price import display_ag_grid_table

# --- Page configuration ---
st.set_page_config(layout="wide", page_title="ETC Price Dashboard", initial_sidebar_state="expanded")
st.cache_data(ttl=3600) 
CORRECT_USERNAME = st.secrets["user_name"]
CORRECT_PASSWORD = st.secrets["pass"]
# --- Define global constants ---
GSHEET_URL = st.secrets["URL"]
CUSTOM_FLOOR_SORT_ORDER = ["27", "26", "25", "24", "23", "22", "21", "20", "19", "18",
                           "17", "16", "15", "14", "12", "11", "10", "09", "08", "07",
                           "06", "05", "03", "02", "01", "G"]
FX_LINK = "https://portal.vietcombank.com.vn/Usercontrols/TVPortal.TyGia/pXML.aspx"
@st.cache_data(ttl=3600)
def fx_getter(fx_url):
    """
    Truy cập API tỷ giá của Vietcombank, lấy tỷ giá bán USD và thời gian cập nhật.

    Returns:
        tuple: Một tuple chứa (fx_rate, fx_time) nếu thành công,
               (None, None) nếu có lỗi.
    """
    try:
        response = requests.get(fx_url, timeout=10)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        
        # Lấy thời gian cập nhật
        datetime_element = root.find('DateTime')
        fx_time_str = datetime_element.text if datetime_element is not None else ""
        datetime_object = datetime.strptime(fx_time_str, "%m/%d/%Y %I:%M:%S %p")
        fx_time = datetime_object.strftime("%d/%m/%Y")

        # Lấy tỷ giá USD
        for exrate in root.findall('Exrate'):
            if exrate.get('CurrencyCode') == 'USD':
                fx_rate_str = exrate.get('Sell')
                fx_rate = float(fx_rate_str.replace(',', ''))
                return fx_rate, fx_time
        
        return None, fx_time # Không tìm thấy USD

    except requests.exceptions.RequestException as e:
        st.error(f"Lỗi khi truy cập URL tỷ giá: {e}")
    except (ET.ParseError, ValueError, AttributeError) as e:
        st.error(f"Lỗi khi xử lý dữ liệu tỷ giá: {e}")
    
    return None, None

def load_and_process_gsheet_data(gsheet_url, fx_rate_to_apply):
    """
    Tải dữ liệu từ Google Sheet và xử lý nó bằng tỷ giá được cung cấp.
    """
    if fx_rate_to_apply is None or fx_rate_to_apply <= 0:
        return None, "Lỗi: Tỷ giá không hợp lệ. Vui lòng cung cấp một tỷ giá dương."
        
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_main_raw = conn.read(spreadsheet=gsheet_url, usecols=list(range(1, 11)), ttl=600)

        if df_main_raw.empty:
            return None, "Lỗi: Không đọc được dữ liệu, sheet có thể rỗng hoặc URL không đúng."

        # Áp dụng tỷ giá để tính toán các cột USD
        df_main_raw['rental_usd'] = round(df_main_raw['rental_vnd'] / fx_rate_to_apply, 2)
        df_main_raw['service_usd'] = round(df_main_raw['service_vnd'] / fx_rate_to_apply, 2)
        df_main_raw['total_usd'] = df_main_raw['rental_usd'] + df_main_raw['service_usd']

        df_processed = df_main_raw.copy()
        
        # Chuyển đổi các cột số liệu
        numeric_cols = ['sqr', 'rental_vnd', 'service_vnd', 'org_fx', 'org_rental_usd', 
                        'org_service_usd', 'org_total_usd', 'rental_usd', 'service_usd', 'total_usd']
        
        for col in numeric_cols:
            if col in df_processed.columns:
                if df_processed[col].dtype == 'object':
                    df_processed[col] = df_processed[col].astype(str).str.replace(',', '.', regex=False)
                df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
        
        # Loại bỏ các hàng có dữ liệu số không hợp lệ
        cols_to_check_for_nan = [col for col in numeric_cols if col in df_processed.columns]
        df_processed.dropna(subset=cols_to_check_for_nan, how='any', inplace=True)

        if df_processed.empty:
            return None, "Cảnh báo: Không tìm thấy dữ liệu hợp lệ sau khi làm sạch."

        if 'floor' in df_processed.columns:
            df_processed['floor_selector_val'] = df_processed['floor'].astype(str)
        else:
            return None, "Lỗi: Cột 'floor' không tìm thấy."
        
        return df_processed, "Dữ liệu đã được tải và xử lý thành công."

    except Exception as e:
        return None, f"Đã xảy ra lỗi khi kết nối hoặc xử lý file: {e}"

def display_login_form():
    """Hiển thị form đăng nhập và xử lý xác thực."""
    st.sidebar.title("🔐 Đăng Nhập")
    username = st.sidebar.text_input("Tên đăng nhập", key="login_username")
    password = st.sidebar.text_input("Mật khẩu", type="password", key="login_password")
    
    if st.sidebar.button("Đăng nhập", key="login_button"):
        if username == CORRECT_USERNAME and password == CORRECT_PASSWORD:
            st.session_state.authenticated = True
            st.session_state.login_error = False
            st.rerun()
        else:
            st.session_state.authenticated = False
            st.session_state.login_error = True

    if "login_error" in st.session_state and st.session_state.login_error:
        st.sidebar.error("Tên đăng nhập hoặc mật khẩu không đúng.")

def run_dashboard_content():
    """Chạy nội dung chính của dashboard sau khi đã xác thực."""
    
    # --- Bước 1: Lấy tỷ giá từ API làm giá trị mặc định và tham chiếu ---
    api_fx_rate, update_time = fx_getter(FX_LINK)
    if api_fx_rate is None:
        api_fx_rate = 25450.0  # Giá trị dự phòng nếu API lỗi
        update_time = "N/A"
        st.warning(f"Không thể lấy tỷ giá từ VCB. Đang sử dụng tỷ giá mặc định: {api_fx_rate:,.0f}")

    st.title("📊 ETC Price Dashboard")
    st.markdown("---")

    # --- Bước 2: Tạo layout và các widget ---
    m_col1r1, m_col2r1, m_col3r1, m_col4r1 = st.columns(4)
    m_col1r2, m_col2r2, m_col3r2, m_col4r2 = st.columns(4)
    
    # *** THAY ĐỔI: Hiển thị tỷ giá tham chiếu từ API trong m_col4r1 ***
    m_col4r1.metric(label="Tỷ Giá bán USD (VND/USD)", help=f"Tỷ giá được cập nhật lúc: {update_time}", value=f"{api_fx_rate:,.0f}")

    # Widget cho người dùng nhập tỷ giá để tính toán
    with m_col4r2:
        user_fx_rate = st.number_input(
            "Nhập tỷ giá để tính toán lại",
            help="Nhập tỷ giá mới và nhấn Enter, đơn giá USD sẽ tự động cập nhật.",
            min_value=20000.0,
            max_value=50000.0,
            step=10.0,
            value=api_fx_rate,
            key="fx_rate_input",
            format="%.0f"
        )

    # --- Bước 3: Tải và xử lý dữ liệu với tỷ giá do người dùng nhập ---
    df_main, gsheet_status_message = load_and_process_gsheet_data(GSHEET_URL, user_fx_rate)

    # --- Xử lý trạng thái tải dữ liệu ---
    if df_main is None or df_main.empty:
        st.error(gsheet_status_message)
        st.stop()

    # --- Bước 4: Tính toán và hiển thị các chỉ số dựa trên dữ liệu đã được xử lý bằng user_fx_rate ---
    h_rental_price, h_service_price, avg_w_rental, l_rental_price, l_service_price, avg_w_service = calculate_metrics_values(df_main)
    
    m_col1r1.metric(label="Giá thuê Cao Nhất (USD)", value=f"${h_rental_price:,.2f}")
    m_col2r1.metric(label="Giá thuê TB theo Diện Tích (USD)", help="(Giá thuê x diện tích) / tổng diện tích", value=f"${avg_w_rental:,.2f}")
    m_col3r1.metric(label="Giá thuê Thấp Nhất (USD)", value=f"${l_rental_price:,.2f}")
    
    m_col1r2.metric(label="Phí DV Cao Nhất (USD)", value=f"${h_service_price:,.2f}")
    m_col2r2.metric(label="Phí DV TB theo Diện Tích (USD)", value=f"${avg_w_service:,.2f}")
    m_col3r2.metric(label="Phí DV Thấp Nhất (USD)", value=f"${l_service_price:,.2f}")
    
    # --- Bước 5: Bộ lọc và hiển thị biểu đồ, bảng ---
    st.header("Bộ Lọc Dữ Liệu")
    filter_container = st.container()
    with filter_container:
            customer_filter_col, floor_filter_col = st.columns(2)

            with customer_filter_col:
                customer_options_unique = sorted(df_main['customer_name'].astype(str).unique().tolist())
                selected_customers_multiselect = st.multiselect(
                    'Chọn Khách Hàng:',
                    options=customer_options_unique,
                    default=[], 
                    key="customer_multiselect_filter"
                )
                is_all_customers_view_active = not selected_customers_multiselect
                final_selected_customers_for_predicate = customer_options_unique if is_all_customers_view_active else selected_customers_multiselect

            with floor_filter_col:
                floor_options_unique = sorted(df_main['floor_selector_val'].unique().tolist(), key=lambda x: CUSTOM_FLOOR_SORT_ORDER.index(x) if x in CUSTOM_FLOOR_SORT_ORDER else float('inf'))
                selected_floors_multiselect = st.multiselect(
                    'Chọn Tầng:',
                    options=floor_options_unique,
                    default=[], 
                    key="floor_multiselect_filter"
                )
                is_all_floors_view_active = not selected_floors_multiselect
                final_selected_floors_for_predicate = floor_options_unique if is_all_floors_view_active else selected_floors_multiselect

    # Lọc DataFrame dựa trên lựa chọn
    df_filtered_for_table_and_chart = df_main.copy()
    if not is_all_customers_view_active:
        df_filtered_for_table_and_chart = df_filtered_for_table_and_chart[df_filtered_for_table_and_chart['customer_name'].astype(str).isin(final_selected_customers_for_predicate)]
    if not is_all_floors_view_active:
            df_filtered_for_table_and_chart = df_filtered_for_table_and_chart[df_filtered_for_table_and_chart['floor_selector_val'].isin(final_selected_floors_for_predicate)]

    st.markdown("---")
    data_display_container = st.container()
    with data_display_container:
        chart_col, table_col = st.columns([2, 3])

        with chart_col:
            st.subheader("Biểu Đồ Phân Bổ Diện Tích và Giá Thuê theo Tầng")
            altair_chart_object = create_advanced_price_chart(
                df_main.copy(),
                final_selected_customers_for_predicate,
                final_selected_floors_for_predicate,
                is_all_customers_view_active,
                is_all_floors_view_active,
                CUSTOM_FLOOR_SORT_ORDER
            )
            st.altair_chart(altair_chart_object, use_container_width=True)


        with table_col:
            st.subheader("Bảng Chi Tiết Giá Thuê và Phí Dịch Vụ")
            st.text("Tỷ giá áp dụng: " + f"{user_fx_rate:,.0f} VND/USD")
            display_ag_grid_table(df_filtered_for_table_and_chart, CUSTOM_FLOOR_SORT_ORDER, st)
        if df_filtered_for_table_and_chart.empty and (not is_all_customers_view_active or not is_all_floors_view_active) :
                st.info("Không có dữ liệu nào khớp với các lựa chọn trong bộ lọc.")
        elif df_main is None and gsheet_status_message is None: 
            st.info("Đang chờ tải dữ liệu...")

def run_app():
    """Khởi tạo và chạy ứng dụng Streamlit."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "login_error" not in st.session_state:
        st.session_state.login_error = False

    if not st.session_state.authenticated:
        display_login_form()
    else:
        if st.sidebar.button("Đăng xuất", key="logout_button"):
            # Xóa các session state liên quan để reset
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        run_dashboard_content()

if __name__ == "__main__":
    run_app()
