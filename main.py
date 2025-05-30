from utils import price_chart,detail_price
import streamlit as st
import pandas as pd
from streamlit.components.v1 import html # For JS/CSS integration
from streamlit_gsheets import GSheetsConnection # For Google Sheets

# Import functions from other modules
from price_chart import calculate_metrics_values, create_advanced_price_chart
from detail_price import display_ag_grid_table

# --- Page configuration ---
st.set_page_config(layout="wide", page_title="ETC Price Dashboard", initial_sidebar_state="expanded")
CORRECT_USERNAME = st.secrets["user_name"]
CORRECT_PASSWORD = st.secrets["pass"]
# --- Define global constants ---
GSHEET_URL = "https://docs.google.com/spreadsheets/d/10vUin48x2mqHZ3TdiuOkXWVOVWy1lq5j0M9gexO7zzM/edit?usp=sharing"

REQUIRED_COLUMNS = [
    'customer_name', 'floor', 'period', 'sqr','foreign_ex',
    'rental_VND', 'service_VND','rental_USD', 'service_USD', 'total_USD'
]
CUSTOM_FLOOR_SORT_ORDER = ["27", "26", "25", "24", "23", "22", "21", "20", "19", "18",
                           "17", "16", "15", "14", "12", "11", "10", "09", "08", "07",
                           "06", "05", "03", "02", "01", "G"]

# --- Authentication Credentials (Hardcoded for simplicity) ---
# IMPORTANT: For a real application, use a more secure way to store and manage credentials.
# Consider environment variables, Streamlit secrets, or a database.
# CORRECT_USERNAME = "NVK"
# CORRECT_PASSWORD = "sm2025"


def load_and_process_gsheet_data(gsheet_url, required_cols_canonical):
    """
    Loads data from the specified Google Sheet URL and processes it.
    """
    status_message = None
    df_processed = None
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_main_raw = conn.read(spreadsheet=gsheet_url, usecols=list(range(1, 11)), ttl=600)

        if df_main_raw.empty:
            status_message = "Lỗi: Không đọc được dữ liệu, sheet có thể rỗng hoặc URL không đúng."
            return None, status_message

        if len(df_main_raw.columns) == len(required_cols_canonical):
            df_main_raw.columns = required_cols_canonical
        else:
            status_message = (
                f"Lỗi: Số lượng cột đọc từ file ({len(df_main_raw.columns)}) "
                f"không khớp với số lượng cột yêu cầu ({len(required_cols_canonical)}). "
                f"Đọc được các cột: {list(df_main_raw.columns)}. Yêu cầu: {required_cols_canonical}. "
                "Vui lòng kiểm tra cấu hình `usecols`."
            )
            return None, status_message
        
        df_processed = df_main_raw.copy()
        numeric_cols_for_conversion = ['sqr', 'rental_VND', 'service_VND', 'foreign_ex', 
                                       'rental_USD', 'service_USD', 'total_USD']
        for col in numeric_cols_for_conversion:
            if col in df_processed.columns:
                if df_processed[col].dtype == 'object':
                    df_processed[col] = df_processed[col].astype(str).str.replace(',', '.', regex=False)
                df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
        
        cols_to_check_for_nan = [col for col in numeric_cols_for_conversion if col in df_processed.columns]
        if cols_to_check_for_nan:
            df_processed.dropna(subset=cols_to_check_for_nan, how='any', inplace=True)

        if df_processed.empty:
            status_message = "Cảnh báo: Không tìm thấy dữ liệu hợp lệ sau khi làm sạch và chuyển đổi kiểu dữ liệu."
            return df_processed, status_message 
        
        if 'floor' in df_processed.columns:
            df_processed['floor_selector_val'] = df_processed['floor'].astype(str)
        else:
            status_message = "Lỗi: Cột 'floor' không tìm thấy sau khi xử lý dữ liệu."
            return None, status_message
        
        status_message = "Dữ liệu đã được tải và xử lý thành công."
        return df_processed, status_message

    except Exception as e:
        status_message = f"Đã xảy ra lỗi khi kết nối hoặc xử lý file: {e}"
        return None, status_message

def display_login_form():
    """Displays the login form and handles authentication."""
    st.sidebar.title("🔐 Đăng Nhập")
    username = st.sidebar.text_input("Tên đăng nhập", key="login_username")
    password = st.sidebar.text_input("Mật khẩu", type="password", key="login_password")
    
    if st.sidebar.button("Đăng nhập", key="login_button"):
        if username == CORRECT_USERNAME and password == CORRECT_PASSWORD:
            st.session_state.authenticated = True
            st.session_state.login_error = False # Clear any previous error
            st.rerun() # Rerun to reflect authenticated state
        else:
            st.session_state.authenticated = False
            st.session_state.login_error = True # Set error flag
            # No need to rerun here, error message will be displayed below

    if "login_error" in st.session_state and st.session_state.login_error:
        st.sidebar.error("Tên đăng nhập hoặc mật khẩu không đúng.")


def run_dashboard_content():
    """Runs the main content of the dashboard after authentication."""
    # --- Data Loading from Google Sheets ---
    df_main, gsheet_status_message = load_and_process_gsheet_data(GSHEET_URL, REQUIRED_COLUMNS)

    st.title("📊 ETC Price Dashboard") 
    if gsheet_status_message:
        if "Lỗi" in gsheet_status_message or "Error" in gsheet_status_message:
            st.error(gsheet_status_message)
            st.stop()
        elif "Cảnh báo" in gsheet_status_message:
            st.warning(gsheet_status_message)
            if df_main is None or df_main.empty:
                 st.stop()
        else:
            st.success(gsheet_status_message)

    st.markdown("---")

    if df_main is not None and not df_main.empty:
        df_filtered_for_table_metrics = df_main.copy()

        # --- Metrics Display ---
        h_rental_price, h_service_price, avg_w_rental, l_rental_price, l_service_price, avg_w_service, avg_fx_rate = calculate_metrics_values(df_filtered_for_table_metrics)

        m_col1r1, m_col2r1, m_col3r1, m_col4r1 = st.columns(4)
        m_col1r1.metric(label="Giá thuê Cao Nhất (USD)", value=f"${h_rental_price:,.2f}")
        m_col2r1.metric(label="Giá thuê TB theo Diện Tích (USD)", value=f"${avg_w_rental:,.2f}")
        m_col3r1.metric(label="Giá thuê Thấp Nhất (USD)", value=f"${l_rental_price:,.2f}")
        m_col4r1.metric(label="Tỷ Giá Bình Quân (VND/USD)", value=f"{avg_fx_rate:,.0f}")

        m_col1r2, m_col2r2, m_col3r2, m_col4r2 = st.columns(4)
        m_col1r2.metric(label="Phí DV Cao Nhất (USD)", value=f"${h_service_price:,.2f}")
        m_col2r2.metric(label="Phí DV TB theo Diện Tích (USD)", value=f"${avg_w_service:,.2f}")
        m_col3r2.metric(label="Phí DV Thấp Nhất (USD)", value=f"${l_service_price:,.2f}")

        # --- Data Filters ---
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
                # js_code_chart = """<script> /* JS for chart interactivity (if any) */ </script>"""
                # html(js_code_chart, height=0)
                # st.markdown("""<style> /* CSS for chart (if any) */ </style>""", unsafe_allow_html=True)

            with table_col:
                st.subheader("Bảng Chi Tiết Giá")
                display_ag_grid_table(df_filtered_for_table_and_chart, CUSTOM_FLOOR_SORT_ORDER, st)
        if df_filtered_for_table_and_chart.empty and (not is_all_customers_view_active or not is_all_floors_view_active) :
             st.info("Không có dữ liệu nào khớp với các lựa chọn trong bộ lọc.")
    elif df_main is None and gsheet_status_message is None: 
        st.info("Đang chờ tải dữ liệu...")


# Main application
def run_app():
    """Initializes and runs the Streamlit application."""
    # Initialize session state for authentication if not already present
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "login_error" not in st.session_state:
        st.session_state.login_error = False


    if not st.session_state.authenticated:
        display_login_form()
    else:
        # Add a logout button in the sidebar if authenticated
        if st.sidebar.button("Đăng xuất", key="logout_button"):
            st.session_state.authenticated = False
            st.session_state.login_error = False # Clear login error on logout
            st.rerun()
        
        run_dashboard_content()


if __name__ == "__main__":
    run_app()
