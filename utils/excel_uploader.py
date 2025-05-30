import streamlit as st
import pandas as pd

def upload_and_process_excel(st_object, required_cols, custom_floor_sort_order_for_val_not_used_directly):
    """
    Handles Excel file uploading and initial processing.

    Args:
        st_object (streamlit): The Streamlit module instance.
        required_cols (list): A list of column names that are mandatory in the Excel file.
        custom_floor_sort_order_for_val_not_used_directly (list): Passed but not directly used here.
                                                                  Retained for signature consistency if needed later.

    Returns:
        tuple: A pandas DataFrame (or None if error/no upload) and a status message (or None).
    """
    uploaded_file = st_object.sidebar.file_uploader("Tải lên file Excel của bạn", type=['xls', 'xlsx'], key="file_uploader")
    df_processed = None
    status_message = None

    if uploaded_file:
        try:
            excel_file_obj = pd.ExcelFile(uploaded_file)
            sheet_name_options = excel_file_obj.sheet_names

            if not sheet_name_options:
                status_message = "Lỗi: File Excel không chứa sheet nào."
                return None, status_message

            selected_sheet_name = st_object.sidebar.selectbox("Chọn sheet để phân tích", sheet_name_options, key="sheet_selector")

            if selected_sheet_name:
                df_main_raw = pd.read_excel(excel_file_obj, sheet_name=selected_sheet_name)
                
                # --- Column Validation and Renaming (Case-insensitive and strip whitespace) ---
                actual_columns_from_file = df_main_raw.columns.tolist()
                # Create a mapping from lowercase, stripped column names to their original names in the file
                col_map_lower_to_original = { str(col).lower().strip(): str(col) for col in actual_columns_from_file }
                
                renamed_cols_dict = {} # To store {original_name_in_file: canonical_name}
                missing_required_cols_for_error = []

                for req_col_canonical_case in required_cols:
                    req_col_lower = str(req_col_canonical_case).lower().strip()
                    if req_col_lower in col_map_lower_to_original:
                        original_name_in_file = col_map_lower_to_original[req_col_lower]
                        # If the original name in file (after lowercasing and stripping) matches the required one,
                        # but the casing is different, we need to rename it to the canonical casing.
                        if original_name_in_file != req_col_canonical_case:
                             renamed_cols_dict[original_name_in_file] = req_col_canonical_case
                    else:
                        # This required column (in its lowercase, stripped form) was not found
                        missing_required_cols_for_error.append(req_col_canonical_case)

                if missing_required_cols_for_error:
                    status_message = f"Lỗi: File Excel thiếu các cột bắt buộc sau (đã kiểm tra không phân biệt chữ hoa/thường và bỏ qua khoảng trắng): {', '.join(missing_required_cols_for_error)}"
                    return None, status_message

                df_processed = df_main_raw.copy()
                if renamed_cols_dict:
                    df_processed.rename(columns=renamed_cols_dict, inplace=True)
                
                # Final check to ensure all required columns are present with canonical names
                final_missing_check = [col for col in required_cols if col not in df_processed.columns]
                if final_missing_check:
                    status_message = f"Lỗi sau khi cố gắng chuẩn hóa tên cột: Vẫn thiếu các cột bắt buộc: {', '.join(final_missing_check)}"
                    return None, status_message
                
                # --- Data Type Conversion and Cleaning ---
                numeric_cols_for_conversion = ['sqr', 'rental_VND', 'service_VND', 'foreign_ex', 'rental_USD', 'service_USD', 'total_USD']
                for col in numeric_cols_for_conversion:
                    if col in df_processed.columns: # Ensure column exists before trying to convert
                        df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
                
                # Drop rows with NaN in critical numeric columns that were just converted
                cols_to_check_for_nan = [col for col in numeric_cols_for_conversion if col in df_processed.columns]
                if cols_to_check_for_nan: # Only drop if there are numeric columns to check
                    df_processed.dropna(subset=cols_to_check_for_nan, how='any', inplace=True)

                if df_processed.empty:
                    status_message = "Cảnh báo: Không tìm thấy dữ liệu hợp lệ trong sheet đã chọn sau khi làm sạch. File có thể trống hoặc các dòng chứa giá trị không phải số trong các cột số."
                    return df_processed, status_message # Return empty DataFrame and warning
                
                # Add 'floor_selector_val' column
                if 'floor' in df_processed.columns:
                    df_processed['floor_selector_val'] = df_processed['floor'].astype(str)
                else:
                    # This case should ideally be caught by the REQUIRED_COLUMNS check if 'floor' is required.
                    # If 'floor' is not in REQUIRED_COLUMNS but is essential here, this error is valid.
                    status_message = "Lỗi: Cột 'floor' không tìm thấy sau khi chuẩn hóa và không thể tạo 'floor_selector_val'."
                    return None, status_message
                
                status_message = "File đã được tải lên và xử lý thành công." # Success message
                return df_processed, status_message

        except Exception as e:
            status_message = f"Đã xảy ra lỗi khi đọc hoặc xử lý file Excel: {e}"
            return None, status_message
    
    return None, None # No file uploaded
