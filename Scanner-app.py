import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import warnings
import logging

# 1. STREAMLIT UI SETUP (Replaces print statements)
st.set_page_config(page_title="Chicago Breakout Scanner", layout="wide")
st.title("🏙️ Chicago S&P 500 Scanner")
st.write("Target: Price > Yesterday's IB High (8:30-9:30) AND Price > Today's ON High")

# Silence warnings
warnings.filterwarnings("ignore", category=FutureWarning)
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

def get_sp500_tickers():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        df = pd.read_html(response.text)[0]
        raw_list = df.iloc[:, 0].astype(str).tolist()
        return [t.strip().upper().replace('.', '-') for t in raw_list if len(t) < 7 and t != 'Symbol']
    except:
        return []

# 2. THE SCANNER BUTTON (Websites shouldn't run automatically)
if st.button('🚀 Start Live Scan'):
    tickers = get_sp500_tickers()
    bullish_stocks = []
    
    # Visual Progress Bar for the Web
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, ticker in enumerate(tickers):
        try:
            # Update web progress
            progress_bar.progress((i + 1) / len(tickers))
            status_text.text(f"Analyzing {ticker}...")

            data = yf.download(ticker, period="3d", interval="5m", prepost=True, progress=False, auto_adjust=True)
            if data.empty or len(data) < 20: continue
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)

            data.index = data.index.tz_convert('America/Chicago')
            days = sorted(data.index.normalize().unique())
            if len(days) < 2: continue
            
            yesterday, today = days[-2], days[-1]

            # Logic 1: Prev Day IB High
            prev_day_data = data.loc[yesterday.strftime('%Y-%m-%d')]
            prev_ib_high = prev_day_data.between_time('08:30', '09:30')['High'].max()

            # Logic 2: Today ON High
            today_data = data.loc[today.strftime('%Y-%m-%d')]
            on_high = today_data.between_time('00:00', '08:30')['High'].max()

            # Logic 3: Current Price
            current_price = today_data['Close'].iloc[-1]

            if current_price > prev_ib_high and current_price > on_high:
                bullish_stocks.append({
                    "Ticker": ticker,
                    "Price": round(float(current_price), 2),
                    "Pivot (ON High)": round(float(on_high), 2),
                    "Gap_Up_%": round(((float(current_price) / float(prev_ib_high)) - 1) * 100, 2)
                })
        except:
            continue

    status_text.empty()
    progress_bar.empty()

    # 3. DISPLAY RESULTS (Replaces display())
    if bullish_stocks:
        st.success(f"Found {len(bullish_stocks)} matches!")
        df_results = pd.DataFrame(bullish_stocks)
        st.dataframe(df_results.sort_values(by="Gap_Up_%", ascending=False), use_container_width=True)
    else:
        st.warning("No stocks currently meet the breakout criteria.")
