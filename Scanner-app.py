import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import warnings
import logging

# --- SETTINGS ---
MIN_MARKET_CAP = 50_000_000_000 

st.set_page_config(page_title="Weighted Chicago Scanner", layout="wide")
st.title("🏙️ Weighted S&P 500 Breakout Scanner")
st.write(f"Targeting: **>${MIN_MARKET_CAP/1e9:.0f}B Market Cap** | Price > Prev IB High & Today ON High")

warnings.filterwarnings("ignore")
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

def get_sp500_tickers():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    df = pd.read_html(requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text)[0]
    return [t.strip().upper().replace('.', '-') for t in df.iloc[:, 0].astype(str).tolist() if t != 'Symbol']

if st.button('🚀 Start Weighted Scan'):
    tickers = get_sp500_tickers()
    bullish_stocks = []
    skipped_errors = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, ticker in enumerate(tickers):
        try:
            progress_bar.progress((i + 1) / len(tickers))
            status_text.text(f"Evaluating {ticker}...")

            t_obj = yf.Ticker(ticker)
            
            # --- IMPROVED MARKET CAP LOGIC ---
            try:
                # fast_info is much more reliable on cloud servers
                mkt_cap = t_obj.fast_info.get('marketCap', 0)
            except:
                mkt_cap = 0 

            # If we can't find market cap, we DON'T skip (Safety First)
            # We only skip if we POSITIVELY know it is a small cap.
            if 0 < mkt_cap < MIN_MARKET_CAP:
                continue 
            
            if mkt_cap == 0:
                skipped_errors.append(ticker)

            # --- DATA DOWNLOAD ---
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
                    "Market Cap ($B)": round(mkt_cap / 1_000_000_000, 1) if mkt_cap > 0 else "Unknown",
                    "Breakout_%": round(((current_price / prev_ib_high) - 1) * 100, 2)
                })
        except Exception as e:
            continue

    status_text.empty()
    progress_bar.empty()

    # --- DISPLAY RESULTS ---
    if bullish_stocks:
        df_res = pd.DataFrame(bullish_stocks)
        st.success(f"Found {len(df_res)} High-Weight matches!")
        st.dataframe(df_res.sort_values(by="Breakout_%", ascending=False), use_container_width=True)
    else:
        st.warning("No heavyweights meet the criteria right now.")

    # --- DEBUG SECTION ---
    if skipped_errors:
        with st.expander("⚠️ System Logs (Data Fallbacks)"):
            st.write("The following tickers had 'Unknown' Market Cap data and were scanned anyway for safety:")
            st.write(", ".join(skipped_errors))
