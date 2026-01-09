import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import warnings
import logging

# --- SETTINGS ---
# Adjust this to narrow your list (e.g., 100e9 for $100B+)
MIN_MARKET_CAP = 50_000_000 

st.set_page_config(page_title="Weighted Chicago Scanner", layout="wide")
st.title("🏙️ Weighted S&P 500 Breakout Scanner")
st.write(f"Filtering for stocks over **${MIN_MARKET_CAP/1e9:.0f}B Market Cap**")

warnings.filterwarnings("ignore")
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

def get_sp500_tickers():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    df = pd.read_html(requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text)[0]
    return [t.strip().upper().replace('.', '-') for t in df.iloc[:, 0].astype(str).tolist() if t != 'Symbol']

if st.button('🚀 Start Weighted Scan'):
    tickers = get_sp500_tickers()
    bullish_stocks = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, ticker in enumerate(tickers):
        try:
            progress_bar.progress((i + 1) / len(tickers))
            status_text.text(f"Evaluating {ticker}...")

            # STEP 1: Fast Market Cap Check (The Gatekeeper)
            t_obj = yf.Ticker(ticker)
            # Use fast_info if available or standard info
            mkt_cap = t_obj.info.get('marketCap', 0)
            
            if mkt_cap < MIN_MARKET_CAP:
                continue # Skip small stocks immediately

            # STEP 2: Download Price Data (Only for heavyweights)
            data = yf.download(ticker, period="3d", interval="5m", prepost=True, progress=False, auto_adjust=True)
            if data.empty: continue
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)

            data.index = data.index.tz_convert('America/Chicago')
            days = sorted(data.index.normalize().unique())
            if len(days) < 2: continue
            
            yesterday_df = data[data.index.normalize() == days[-2]]
            today_df = data[data.index.normalize() == days[-1]]

            # Logic
            prev_ib_high = float(yesterday_df.between_time('08:30', '09:30')['High'].max())
            on_high = float(today_df.between_time('00:00', '08:30')['High'].max())
            current_price = float(today_df['Close'].iloc[-1])

            if current_price > prev_ib_high and current_price > on_high:
                bullish_stocks.append({
                    "Ticker": ticker,
                    "Price": round(current_price, 2),
                    "Market Cap ($B)": round(mkt_cap / 1_000_000_000, 1),
                    "Breakout_%": round(((current_price / prev_ib_high) - 1) * 100, 2)
                })
        except:
            continue

    status_text.empty()
    progress_bar.empty()

    if bullish_stocks:
        df_res = pd.DataFrame(bullish_stocks)
        st.success(f"Found {len(df_res)} High-Weight matches!")
        st.dataframe(df_res.sort_values(by="Market Cap ($B)", ascending=False), use_container_width=True)
    else:
        st.warning("No heavyweights meet the criteria right now.")
