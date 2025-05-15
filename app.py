import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from plotly.subplots import make_subplots
import requests
import os

def fetch_fred_rate(series_id):
    FRED_API_KEY = os.environ.get("FRED_API_KEY") or ""
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json&sort_order=desc&limit=1"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            obs = data['observations'][0]
            rate = float(obs['value'])
            date = obs['date']
            return rate, date
    except Exception:
        pass
    return None, None

def fetch_current_mortgage_rates():
    # 30-year fixed: MORTGAGE30US, 15-year fixed: MORTGAGE15US
    rate_30, date_30 = fetch_fred_rate("MORTGAGE30US")
    rate_15, date_15 = fetch_fred_rate("MORTGAGE15US")
    # Fallbacks
    if rate_30 is None:
        rate_30, date_30 = 6.96, None
    if rate_15 is None:
        rate_15, date_15 = 6.28, None
    return (rate_30, date_30), (rate_15, date_15)

def calculate_mortgage(principal, annual_rate, years):
    # Convert annual rate to monthly rate
    monthly_rate = annual_rate / 12 / 100
    
    # Calculate number of payments
    num_payments = years * 12
    
    # Calculate monthly payment using the formula: P = L[c(1 + c)^n]/[(1 + c)^n - 1]
    monthly_payment = principal * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)
    
    # Create amortization schedule
    schedule = []
    balance = principal
    cumulative_payment = 0
    
    for payment_num in range(1, num_payments + 1):
        interest_payment = balance * monthly_rate
        principal_payment = monthly_payment - interest_payment
        balance -= principal_payment
        cumulative_payment += monthly_payment
        
        schedule.append({
            'Payment_Number': payment_num,
            'Payment': monthly_payment,
            'Principal': principal_payment,
            'Interest': interest_payment,
            'Balance': balance,
            'Cumulative_Payment': cumulative_payment
        })
    
    return pd.DataFrame(schedule)

def main():
    st.title("Mortgage Calculator")
    st.write("Calculate your mortgage payments and visualize the amortization schedule")
    
    # Fetch current mortgage rates
    (rate_30, date_30), (rate_15, date_15) = fetch_current_mortgage_rates()

    # Input parameters
    col1, col2 = st.columns(2)
    with col2:
        rate_options = [
            f"30-year fixed ({rate_30:.2f}%)",
            f"15-year fixed ({rate_15:.2f}%)",
            "Custom"
        ]
        rate_option = st.radio(
            "Choose a rate:",
            rate_options,
            horizontal=True,
            help="Select a rate type or choose Custom to enter your own."
        )
        if rate_option.startswith("30-year"):
            default_rate = rate_30
        elif rate_option.startswith("15-year"):
            default_rate = rate_15
        else:
            default_rate = rate_30
        annual_rate = st.number_input(
            "Annual Interest Rate (%)",
            min_value=0.1,
            max_value=20.0,
            value=default_rate,
            step=0.1,
            key="interest_rate_input"
        )
    with col1:
        # Home purchase price input with commas
        home_price_str = st.text_input(
            "Home Purchase Price ($)",
            value=f"{400000:,}",
            help="Enter the home purchase price. Commas are allowed."
        )
        try:
            home_price = int(home_price_str.replace(",", ""))
            if home_price < 10000 or home_price > 10000000:
                st.error("Home purchase price must be between $10,000 and $10,000,000.")
        except ValueError:
            home_price = 400000
            st.error("Please enter a valid number for the home purchase price.")
        # Down payment percent
        down_payment_percent = st.number_input(
            "Down Payment (%)",
            min_value=0.0,
            max_value=100.0,
            value=20.0,
            step=0.1,
            help="Enter the down payment percentage."
        )
        # Calculate down payment amount
        down_payment_amount = int(home_price * down_payment_percent / 100)
        st.text_input(
            "Down Payment Amount ($)",
            value=f"{down_payment_amount:,}",
            disabled=True,
            help="Calculated as Home Price × Down Payment %."
        )
        # Calculate loan amount
        principal = int(home_price * (1 - down_payment_percent / 100))
        st.text_input(
            "Loan Amount ($)",
            value=f"{principal:,}",
            disabled=True,
            help="Calculated as Home Price minus Down Payment."
        )
        years = st.number_input("Loan Term (Years)", min_value=1, max_value=30, value=30, step=1)
    
    # Calculate mortgage automatically when inputs change
    schedule = calculate_mortgage(principal, annual_rate, years)
    
    # Display summary
    monthly_payment = schedule['Payment'].iloc[0]
    total_payment = schedule['Payment'].sum()
    total_interest = schedule['Interest'].sum()
    total_principal = schedule['Principal'].sum()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Monthly Payment", f"${monthly_payment:,.2f}")
    with col2:
        st.metric("Total Payment", f"${total_payment:,.2f}")
    with col3:
        st.metric("Total Interest", f"${total_interest:,.2f}")

    # Pie chart for total principal vs total interest
    pie_labels = ['Principal', 'Interest']
    pie_values = [total_principal, total_interest]
    pie_colors = ['#2ecc71', '#e74c3c']
    pie_fig = go.Figure(data=[go.Pie(labels=pie_labels, values=pie_values, marker=dict(colors=pie_colors), hole=0.4)])
    pie_fig.update_layout(title_text='Total Principal vs Total Interest Paid', height=200, title_font_size=14, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(pie_fig, use_container_width=True)
    
    # Combined visualization for principal/interest and cumulative payments
    combined_fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Stacked area for principal and interest payments (primary y-axis)
    combined_fig.add_trace(
        go.Scatter(
            x=schedule['Payment_Number'],
            y=schedule['Principal'],
            name='Principal',
            mode='lines',
            stackgroup='one',
            line=dict(color='#2ecc71')
        ),
        secondary_y=False
    )
    combined_fig.add_trace(
        go.Scatter(
            x=schedule['Payment_Number'],
            y=schedule['Interest'],
            name='Interest',
            mode='lines',
            stackgroup='one',
            line=dict(color='#e74c3c')
        ),
        secondary_y=False
    )

    # Cumulative payments as a line (secondary y-axis)
    combined_fig.add_trace(
        go.Scatter(
            x=schedule['Payment_Number'],
            y=schedule['Cumulative_Payment'],
            name='Cumulative Payment',
            mode='lines',
            line=dict(color='#3498db', width=2)
        ),
        secondary_y=True
    )

    # Loan amount reference line (secondary y-axis)
    combined_fig.add_shape(
        type="line",
        x0=1, x1=len(schedule),
        y0=principal, y1=principal,
        line=dict(color="#e74c3c", width=2, dash="dash"),
        yref="y2"
    )
    combined_fig.add_annotation(
        x=len(schedule)//2,
        y=principal,
        text="Loan Amount",
        showarrow=False,
        yshift=10,
        font=dict(color="#e74c3c"),
        yref="y2"
    )

    combined_fig.update_layout(
        title='Principal & Interest Payments and Cumulative Payments Over Time',
        xaxis_title='Payment Number',
        yaxis_title='Payment Amount ($)',
        yaxis2_title='Cumulative Payment ($)',
        height=500,
        legend=dict(x=0.01, y=0.99)
    )
    st.plotly_chart(combined_fig, use_container_width=True)
    
    # Display detailed schedule
    st.subheader("Amortization Schedule")
    st.dataframe(schedule.style.format({
        'Payment': '${:,.2f}',
        'Principal': '${:,.2f}',
        'Interest': '${:,.2f}',
        'Balance': '${:,.2f}',
        'Cumulative_Payment': '${:,.2f}'
    }))

if __name__ == "__main__":
    main() 