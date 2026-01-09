import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import warnings
import logging
from datetime import datetime

# --- UI SETUP ---
st.set_page_config(page_title="Chicago Scanner", layout="wide")
st.title("🏙️ Chicago S&P 500 Scanner")

# Silence chatter
warnings.filterwarnings("ignore")
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

def get_sp500_tickers():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    df = pd.read_html(response.text)[0]
    return [t.strip().upper().replace('.', '-') for t in df.iloc[:, 0].astype(str).tolist() if t != 'Symbol']

if st.button('🚀 Start Live Scan'):
    tickers = get_sp500_tickers()
    bullish_stocks = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, ticker in enumerate(tickers):
        try:
            progress_bar.progress((i + 1) / len(tickers))
            status_text.text(f"Checking {ticker}...")

            # We use 5d to ensure we always have a yesterday and today regardless of timezone
            data = yf.download(ticker, period="5d", interval="5m", prepost=True, progress=False, auto_adjust=True)
            
            if data.empty: continue
            
            # FIX: Ensure columns are flat (Prevents the NaN filter bug)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            # Force Chicago Timezone
            data.index = data.index.tz_convert('America/Chicago')
            
            # Get the last two active trading days from the data itself
            all_days = sorted(data.index.normalize().unique())
            if len(all_days) < 2: continue
            
            yesterday_ts = all_days[-2]
            today_ts = all_days[-1]

            # Separate the dataframes
            yesterday_df = data[data.index.normalize() == yesterday_ts]
            today_df = data[data.index.normalize() == today_ts]

            # 1. Previous Day IB High (08:30 - 09:30)
            ib_range = yesterday_df.between_time('08:30', '09:30')
            if ib_range.empty: continue
            prev_ib_high = float(ib_range['High'].max())

            # 2. Today Overnight High (00:00 - 08:30)
            on_range = today_df.between_time('00:00', '08:30')
            if on_range.empty: continue
            on_high = float(on_range['High'].max())

            # 3. Current Price
            current_price = float(today_df['Close'].iloc[-1])

            # THE LOGIC CHECK
            if current_price > prev_ib_high and current_price > on_high:
                bullish_stocks.append({
                    "Ticker": ticker,
                    "Price": round(current_price, 2),
                    "Prev IB High": round(prev_ib_high, 2),
                    "ON High": round(on_high, 2),
                    "Breakout_%": round(((current_price / prev_ib_high) - 1) * 100, 2)
                })
        except:
            continue

    status_text.empty()
    progress_bar.empty()

    if bullish_stocks:
        df_res = pd.DataFrame(bullish_stocks)
        st.success(f"Matches: {len(df_res)}")
        st.dataframe(df_res.sort_values(by="Breakout_%", ascending=False), use_container_width=True)
    else:
        st.error("Still no matches. This suggests a data alignment issue.")
