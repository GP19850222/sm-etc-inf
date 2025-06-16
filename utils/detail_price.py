import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, GridUpdateMode # Removed ColumnsAutoSizeMode as it's not explicitly used

number_formatter = JsCode("""
    function formatNumberWithPoint(params) {
        if (params.value == null || isNaN(params.value)) { 
            return ""; 
        }
        return Number(params.value).toLocaleString('vi-VN', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        });
    }""")
decimal_formatter = JsCode("""
    function formatNumberWithPoint(params) {
        if (params.value == null || isNaN(params.value)) { 
            return ""; 
        }
        return Number(params.value).toLocaleString('vi-VN', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
        });
    }""")
def display_ag_grid_table(df_filtered_for_table, custom_floor_sort_order, st_object):
    """
    Displays the detailed price data using AgGrid.

    Args:
        df_filtered_for_table (pd.DataFrame): The DataFrame to display.
        custom_floor_sort_order (list): The custom sort order for the 'Tầng' column.
        st_object (streamlit): The Streamlit module instance for displaying messages.
    """
    if df_filtered_for_table is not None and not df_filtered_for_table.empty:
        # Define which columns to show and their display names
        cols_for_aggrid = ['floor', 
                           'customer_name', 
                           'period', 
                           'sqr', 
                           'rental_usd', 
                           'service_usd', 
                           'total_usd', 
                           'rental_vnd', 
                           'service_vnd',
                           'org_fx',
                           'org_rental_usd',
                           'org_service_usd',
                           'org_total_usd'
                           ]
        # Ensure only existing columns are selected to avoid KeyError
        display_cols_aggrid = [col for col in cols_for_aggrid if col in df_filtered_for_table.columns]
        
        if not display_cols_aggrid:
            st_object.info("Không có cột dữ liệu nào phù hợp để hiển thị trong bảng chi tiết.")
            return

        aggrid_display_df = df_filtered_for_table[display_cols_aggrid].copy()
        
        rename_map_aggrid = {
            'customer_name': 'Tên Khách Hàng',
            'floor': 'Tầng',
            'sqr': 'Diện Tích (m²)', 
            'period': 'Kỳ Hạn', 
            'rental_usd': 'Giá Thuê (USD)',
            'service_usd': 'Phí Dịch Vụ (USD)',
            'total_usd': 'Tổng (USD)',
            'rental_vnd': 'Giá Thuê (VND)',
            'service_vnd': 'Phí Dịch Vụ (VND)',
            'org_fx': 'Tỷ giá ký HĐ',
            'org_rental_usd': 'Giá Thuê (USD) Ký HĐ',
            'org_service_usd': 'Phí Dịch Vụ (USD) Ký HĐ',
            'org_total_usd': 'Tổng (USD) Ký HĐ'
        }
        aggrid_display_df.columns = [rename_map_aggrid.get(col, col) for col in aggrid_display_df.columns]

        # --- Custom Sort JS for 'Tầng' Column ---
        # Ensure the sort order list is correctly formatted for JS
        js_sort_order_list = str(custom_floor_sort_order).replace("'", '"') # JS needs double quotes for strings in array

        custom_floor_sort_js = f"""
        function(valueA, valueB) {{
            const sortOrder = {js_sort_order_list};
            const map = {{}};
            for (let i = 0; i < sortOrder.length; i++) {{
                map[sortOrder[i]] = i;
            }}
            const indexA = map[valueA] !== undefined ? map[valueA] : sortOrder.length;
            const indexB = map[valueB] !== undefined ? map[valueB] : sortOrder.length;

            if (indexA === indexB) return 0;
            return indexA < indexB ? -1 : 1;
        }}
        """
        
        gb = GridOptionsBuilder.from_dataframe(aggrid_display_df, enableRowGroup=True, rowGroupPanelShow='always')
        gb.configure_pagination(enabled=True, paginationAutoPageSize=False, paginationPageSize=20) 
        
        # Default column configurations
        gb.configure_default_column(
            resizable=True, 
            groupable=True, # Allow grouping by any column
            filter='agTextColumnFilter', # Default filter type
            filterParams={"buttons": ['clear']}, # Default filter buttons
            filterable=True, 
            sortable=True, 
            floatingFilter=True, # Enable floating filters for all columns
            Width=100 # Default min width
        )

        # Specific column configurations
        gb.configure_column(field='Tầng',
                            sort='asc', # Initial sort direction
                            rowGroup=True, # Enable row grouping by 'Tầng' by default
                            comparator=JsCode(custom_floor_sort_js),
                            minWidth=120# Specific width for Tầng
                           )
        gb.configure_column(field='Tên Khách Hàng', width=200,hide = True)
        gb.configure_column(field='Diện Tích (m²)', type=["numericColumn", "numberColumnFilter"], aggFunc='sum', width=150,valueFormatter= number_formatter)
        gb.configure_column(field='Giá Thuê (USD)', type=["numericColumn", "numberColumnFilter"],width=150,valueFormatter= decimal_formatter)
        gb.configure_column(field='Phí Dịch Vụ (USD)', type=["numericColumn", "numberColumnFilter"],width=180,valueFormatter= decimal_formatter)
        gb.configure_column(field='Tổng (USD)', type=["numericColumn", "numberColumnFilter"], width=150,valueFormatter= decimal_formatter)
        gb.configure_column(field='Kỳ Hạn', width=200)
        gb.configure_column(field='Giá Thuê (VND)', type=["numericColumn", "numberColumnFilter"], width=150,valueFormatter= number_formatter)
        gb.configure_column(field='Phí Dịch Vụ (VND)', type=["numericColumn", "numberColumnFilter"], width=180,valueFormatter= number_formatter)
        gb.configure_column(field='Tỷ giá ký HĐ', type=["numericColumn", "numberColumnFilter"], width=180,valueFormatter= number_formatter)
        

        # Configure how grouped rows are displayed
        autoGroupColDef_dict = {
            "headerName": "Khách hàng", # Name for the auto-group column
            "field": 'Tên Khách Hàng', # The field being grouped (though AgGrid handles this internally)
            "pinned": "left",
            "cellRendererParams": {
                "suppressCount": True, # Show count of items in group
            },
            "filter": 'agTextColumnFilter', # Allow filtering on the grouped column
            "floatingFilter": True,
            "minWidth": 200 # Width for the group column
        }
        gb.configure_grid_options(
            groupDefaultExpanded=-1, # Expand all groups by default
            autoGroupColumnDef=autoGroupColDef_dict,
            domLayout='autoHeight' # Adjusts grid height to content, use with caution for large datasets
        )
        
        gridOptions = gb.build()

        AgGrid(
            aggrid_display_df,
            gridOptions=gridOptions,
            height=700, # Fixed height for the grid
            fit_columns_on_grid_load=True, # Can cause issues if minWidths are also set. Let user resize.
            allow_unsafe_jscode=True, 
            enable_enterprise_modules=True, # Assuming enterprise version is available for row grouping features
            key='price_detail_grid', # Unique key for the AgGrid instance
            update_mode=GridUpdateMode.MODEL_CHANGED # How grid updates
        )
    else:
        st_object.info("Không có dữ liệu chi tiết để hiển thị dựa trên bộ lọc hiện tại hoặc chưa có file nào được tải lên.")
