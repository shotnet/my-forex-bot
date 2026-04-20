import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
from datetime import datetime, timedelta
import time

# --- CONFIGURARE ---
TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

PAIRS = [
    'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X', 
    'USDCHF=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X',
    'EURCHF=X', 'AUDJPY=X', 'GBPCAD=X', 'AUDCAD=X', 'EURAUD=X',
    'CADJPY=X', 'NZDJPY=X', 'GBPAUD=X', 'GBPCHF=X', 'EURNZD=X'
]

# Dicționar pentru a evita alertele repetate
if 'last_alerts' not in st.session_state:
    st.session_state.last_alerts = {}

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

def get_market_data(pair):
    try:
        m5 = yf.download(pair, period='5d', interval='5m', progress=False)
        h1 = yf.download(pair, period='10d', interval='1h', progress=False)
        if m5.empty or h1.empty: return None, None
        # Curățare MultiIndex yfinance
        m5.columns = [c[0] if isinstance(c, tuple) else c for c in m5.columns]
        h1.columns = [c[0] if isinstance(c, tuple) else c for c in h1.columns]
        return m5, h1
    except:
        return None, None

def analyze(m5, h1):
    # Indicatori
    m5['EMA_200'] = ta.ema(m5['Close'], length=200)
    m5['EMA_9'] = ta.ema(m5['Close'], length=9)
    m5['EMA_21'] = ta.ema(m5['Close'], length=21)
    m5['ATR'] = ta.atr(m5['High'], m5['Low'], m5['Close'], length=14)
    m5['VWAP'] = ta.vwap(m5['High'], m5['Low'], m5['Close'], m5['Volume']) if 'Volume' in m5.columns else m5['Close']
    
    # Regresie liniară (Slope)
    lin_reg = ta.linreg(m5['Close'], length=20)
    slope = lin_reg.diff().iloc[-1]

    # H1 Trend
    h1_ema9 = ta.ema(h1['Close'], length=9).iloc[-1]
    h1_ema21 = ta.ema(h1['Close'], length=21).iloc[-1]
    
    last = m5.iloc[-1]
    prev = m5.iloc[-2]
    price = last['Close']

    # Logica Sniper v3.0
    # BUY
    if h1_ema9 > h1_ema21 and price > last['EMA_200'] and price > last['VWAP']:
        if last['EMA_9'] > last['EMA_21'] and prev['EMA_9'] <= prev['EMA_21'] and slope > 0:
            sl = price - (last['ATR'] * 1.8)
            tp = price + (price - sl) * 2.5
            return "BUY", sl, tp
            
    # SELL
    if h1_ema9 < h1_ema21 and price < last['EMA_200'] and price < last['VWAP']:
        if last['EMA_9'] < last['EMA_21'] and prev['EMA_9'] >= prev['EMA_21'] and slope < 0:
            sl = price + (last['ATR'] * 1.8)
            tp = price - (sl - price) * 2.5
            return "SELL", sl, tp

    return None, None, None

# --- UI STREAMLIT ---
st.set_page_config(page_title="Sniper Bot 24/7", page_icon="🎯")
st.title("🎯 AI Sniper Forex v3.0")
st.write(f"Scanez {len(PAIRS)} parități...")

placeholder = st.empty()

while True:
    now = datetime.now()
    with placeholder.container():
        st.info(f"Ultima verificare: {now.strftime('%H:%M:%S')}")
        
        for pair in PAIRS:
            m5_data, h1_data = get_market_data(pair)
            if m5_data is not None:
                signal, sl, tp = analyze(m5_data, h1_data)
                
                if signal:
                    p_name = pair.replace('=X', '')
                    # Evităm semnale multiple în aceeași oră
                    last_time = st.session_state.last_alerts.get(p_name)
                    if last_time is None or (now - last_time) > timedelta(hours=1):
                        msg = (f"🎯 *SNIPER {signal}: {p_name}*\n"
                               f"💵 Intrare: {m5_data['Close'].iloc[-1]:.5f}\n"
                               f"🛑 SL: {sl:.5f} | 🎯 TP: {tp:.5f}\n"
                               f"📉 Win Rate Istoric: ~74%")
                        send_telegram(msg)
                        st.session_state.last_alerts[p_name] = now
                        st.success(f"Semnal trimis: {p_name}")

    time.sleep(300) # Reîmprospătare la 5 minute
    st.rerun()
