import pandas as pd
import altair as alt
import numpy as np
def calculate_metrics_values(df_input):
    """Calculates key metrics from the dataframe."""
    if df_input.empty:
        return 0, 0, 0, 0

    highest_rental_price = df_input['rental_usd'].max() if 'rental_usd' in df_input.columns else 0
    lowest_rental_price = df_input[df_input['rental_usd'] > 0]['rental_usd'].min() if 'rental_usd' in df_input.columns else 0
    highest_service_price = df_input['service_usd'].max() if 'service_usd' in df_input.columns else 0
    lowest_service_price = df_input[df_input['service_usd'] > 0]['service_usd'].min() if 'service_usd' in df_input.columns else 0

    # Weighted average price: sumproduct(sqr*rental_usd)/sum(sqr)
    avg_rental = 0
    if 'sqr' in df_input.columns and 'rental_usd' in df_input.columns:
        temp_df_for_avg = df_input.dropna(subset=['sqr', 'rental_usd'])
        temp_df_for_avg = temp_df_for_avg[temp_df_for_avg['rental_usd'] > 0] 
        if not temp_df_for_avg.empty and temp_df_for_avg['sqr'].sum() != 0:
            avg_rental = (temp_df_for_avg['sqr'] * temp_df_for_avg['rental_usd']).sum() / temp_df_for_avg['sqr'].sum()

    avg_service = 0
    if 'sqr' in df_input.columns and 'service_usd' in df_input.columns:
        temp_df_for_avg = df_input.dropna(subset=['sqr', 'service_usd'])
        temp_df_for_avg = temp_df_for_avg[temp_df_for_avg['service_usd'] > 0]
        if not temp_df_for_avg.empty and temp_df_for_avg['sqr'].sum() != 0:
            avg_service = (temp_df_for_avg['sqr'] * temp_df_for_avg['service_usd']).sum() / temp_df_for_avg['sqr'].sum()
            

    return highest_rental_price,highest_service_price, avg_rental, lowest_rental_price,lowest_service_price, avg_service


# Function to create the new Altair chart
def create_advanced_price_chart(df_input, 
                                customers_to_match_in_predicate, 
                                floors_to_match_in_predicate, 
                                is_all_customers_filter_view, 
                                is_all_floors_filter_view,
                                CUSTOM_FLOOR_SORT_ORDER
                                ):
    """Creates an advanced Altair chart for rental prices by floor with refined interactivity."""
    if df_input.empty or not all(col in df_input.columns for col in ['customer_name', 'floor', 'sqr', 'rental_usd', 'service_usd','total_usd']):
        # Return an empty chart with labels if no data or required columns missing
        empty_chart_df = pd.DataFrame({'floor_display': [], 'normalized_sqr': [], 'customer_name': []})
        return alt.Chart(empty_chart_df).mark_bar().encode(
            y=alt.Y('floor_display:N', title='Tầng'),
            x=alt.X('sum(normalized_sqr):Q', title='Diện tích chuẩn hóa')
        ).properties(title='Phân Bổ Diện Tích Thuê theo Tầng (Chi Tiết)')

    chart_data = df_input.copy()
    chart_data['floor_display'] = chart_data['floor'].astype(str)
    chart_data['sqr_display'] = chart_data['sqr'] 
    
    # Calculate normalized_sqr
    floor_totals = chart_data.groupby('floor_display')['sqr'].sum().replace(0, np.nan) 
    chart_data['normalized_sqr'] = chart_data.apply(
        lambda x: (x['sqr'] / floor_totals[x['floor_display']]) if pd.notna(floor_totals[x['floor_display']]) else 0,
        axis=1
    ).fillna(0)

    # --- Define selections and predicates ---
    highlight_selection = alt.selection_point(name="highlight", on="pointerover", empty=False)
    
    # Predicates for filtering based on sidebar selections
    customer_select_predicate = alt.FieldOneOfPredicate(field='customer_name', oneOf=customers_to_match_in_predicate)
    floor_select_predicate = alt.FieldOneOfPredicate(field='floor_display', oneOf=floors_to_match_in_predicate)

    # --- Logic for opacity and highlighting based on filters ---
    dim_opacity_value = alt.value(0.2)
    full_opacity_value = alt.value(1.0)

    # Determine which specific filters are active
    specific_customer_filter_active = not is_all_customers_filter_view
    specific_floor_filter_active = not is_all_floors_filter_view

    # Build the combined predicate for matching rows if specific filters are active
    combined_filter_predicate = None
    if specific_customer_filter_active and specific_floor_filter_active:
        combined_filter_predicate = customer_select_predicate & floor_select_predicate
    elif specific_customer_filter_active:
        combined_filter_predicate = customer_select_predicate
    elif specific_floor_filter_active:
        combined_filter_predicate = floor_select_predicate

    if combined_filter_predicate is None: # No specific filters active (all customers AND all floors)
        op_condition = full_opacity_value
        stroke_color_non_hover = alt.value("#696969") 
        stroke_width_non_hover = alt.value(0)       
    else: # At least one specific filter is active
        # --- CORRECTED op_condition definition ---
        op_condition = alt.when(combined_filter_predicate).then(full_opacity_value).otherwise(dim_opacity_value)
        # --- END OF CORRECTION ---
        stroke_color_non_hover = alt.when(combined_filter_predicate).then(alt.value('#000000')).otherwise(alt.value('#BBBBBB'))
        stroke_width_non_hover = alt.when(combined_filter_predicate).then(alt.value(1)).otherwise(alt.value(0.5))

    # Layer hover effect on top
    stroke_color_condition = alt.when(highlight_selection).then(alt.value('#FF0000')).otherwise(stroke_color_non_hover)
    stroke_width_condition = alt.when(highlight_selection).then(alt.value(3)).otherwise(stroke_width_non_hover)
        
    # Define color condition based on 'rental_usd'
    df_metrics = chart_data[chart_data['rental_usd'] > 0].copy() 
    if not df_metrics.empty:
        df_metrics['rental_usd_numeric'] = pd.to_numeric(df_metrics['rental_usd'], errors='coerce')
        df_metrics.dropna(subset=['rental_usd_numeric'], inplace=True)

        if not df_metrics.empty:
            min_rent = df_metrics['rental_usd_numeric'].min()
            avg_rent = df_metrics['rental_usd_numeric'].mean()
            max_rent = df_metrics['rental_usd_numeric'].max()
            
            color_domain = [0, min_rent, avg_rent, max_rent]
            color_domain = sorted(list(set(round(val, 2) for val in color_domain if pd.notna(val))))
            if len(color_domain) < 2: 
                color_domain = [0, max_rent if pd.notna(max_rent) and max_rent > 0 else 1]

            color_fill_condition = alt.Color('rental_usd:Q',
                                        scale=alt.Scale(
                                            domain=color_domain,
                                            range=['#0a0a0a', '#3399ff', '#ffff00', '#00ff00'][:len(color_domain)] 
                                        ),
                                        legend=alt.Legend(title='Giá Thuê (USD)', orient='right', format='$,.2f'))
        else: 
            color_fill_condition = alt.value('lightgray') 
    else: 
        color_fill_condition = alt.value('lightgray')

    # Create Altair bar chart
    chart_data['-'] = '__________________'
    chart = alt.Chart(chart_data).mark_bar(stroke='black', cursor="pointer").encode(
        x=alt.X('normalized_sqr:Q', stack=True, axis=None, scale=alt.Scale(domain=[0, 1])),
        y=alt.Y("floor_display:N", sort=CUSTOM_FLOOR_SORT_ORDER, title="Tầng", axis=alt.Axis(labelFontSize=12)),
        color=color_fill_condition,
        tooltip=[
            alt.Tooltip("customer_name:N", title="Khách thuê"),
            alt.Tooltip("floor_display:O", title="Tầng"),
            alt.Tooltip("sqr_display:Q", title="Diện tích (m²)", format=',.0f'),
            alt.Tooltip("rental_usd:Q", title="Giá thuê (USD)", format='$,.2f'),
            alt.Tooltip("service_usd:Q", title="Phí dịch vụ (USD)", format='$,.2f'),
            alt.Tooltip("total_usd:Q", title="Tổng Cộng (USD)", format='$,.2f'),
            alt.Tooltip("-:N", title=None),
            alt.Tooltip("org_rental_usd:Q", title="Giá thuê (USD) ký HĐ", format='$,.2f'),
            alt.Tooltip("org_service_usd:Q", title="Phí dịch vụ (USD) ký HĐ", format='$,.2f'),
            alt.Tooltip("org_fx:Q", title="Tỷ giá ký HĐ", format=',.0f'),
            # alt.Tooltip("period:O", title="Kỳ hạn")
        ],
        fillOpacity=op_condition, 
        strokeOpacity=alt.value(1), 
        stroke=stroke_color_condition, 
        strokeWidth=stroke_width_condition 
    ).properties(
        title='Phân Bổ Diện Tích Thuê theo Tầng (Chi Tiết)',
        width=alt.Step(40), 
        height=700      
    ).add_params(highlight_selection)

    return chart
