"""台灣股票 / 美股近一年估價值診斷工具。"""

from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="近一年估價值診斷",
    page_icon="📈",
    layout="wide",
)


def normalize_ticker(raw: str) -> str:
    """整理代號：純數字視為台股，自動補上 .TW。"""
    ticker = raw.strip().upper()
    if re.fullmatch(r"\d{4,6}", ticker):
        return f"{ticker}.TW"
    return ticker


@st.cache_data(ttl=60 * 15, show_spinner=False)
def load_one_year_history(ticker: str) -> pd.DataFrame:
    history = yf.Ticker(ticker).history(period="1y", auto_adjust=True)
    if history.empty or "Close" not in history.columns:
        raise ValueError(f"找不到代號「{ticker}」的有效報價資料。")
    return history.dropna(subset=["Close"])


def position_in_range(latest: float, year_low: float, year_high: float) -> float | None:
    span = year_high - year_low
    if span <= 0:
        return None
    return (latest - year_low) / span * 100


def advice_text(pct: float | None) -> tuple[str, str]:
    if pct is None:
        return "info", "近一年高低價幾乎相同，區間位置參考意義有限。"
    if pct >= 80:
        return (
            "warning",
            f"目前股價位於近一年 **{pct:.1f}%** 高位，請注意追高風險。",
        )
    if pct >= 50:
        return (
            "info",
            f"目前股價位於近一年區間中偏上（**{pct:.1f}%**），建議搭配基本面再判斷。",
        )
    if pct >= 20:
        return (
            "info",
            f"目前股價位於近一年區間中偏下（**{pct:.1f}%**），相對離低點較近。",
        )
    return (
        "success",
        f"目前股價位於近一年 **{pct:.1f}%** 低位，較靠近一年低點（仍須留意基本面與流動性）。",
    )


# 新增 chart_type 參數，預設為 "折線圖"
def build_price_chart(
    history: pd.DataFrame,
    ticker: str,
    year_low: float,
    year_high: float,
    latest: float,
    chart_type: str = "折線圖",
) -> go.Figure:
    fig = go.Figure()

    # 根據選取的圖表類型選擇對應的 Plotly Trace
    if chart_type == "K線圖" and {"Open", "High", "Low", "Close"}.issubset(history.columns):
        fig.add_trace(
            go.Candlestick(
                x=history.index,
                open=history["Open"],
                high=history["High"],
                low=history["Low"],
                close=history["Close"],
                name="K線",
                increasing_line_color="#ef4444",  # 紅漲
                decreasing_line_color="#22c55e",  # 綠跌
            )
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=history.index,
                y=history["Close"],
                mode="lines",
                name="收盤價",
                line=dict(color="#2563eb", width=2),
                hovertemplate="%{x|%Y-%m-%d}<br>收盤：%{y:.2f}<extra></extra>",
            )
        )

    fig.add_hline(
        y=year_high,
        line_dash="dash",
        line_color="#ef4444",
        annotation_text="近一年最高",
        annotation_position="top left",
    )
    fig.add_hline(
        y=year_low,
        line_dash="dash",
        line_color="#22c55e",
        annotation_text="近一年最低",
        annotation_position="bottom left",
    )
    fig.add_hline(
        y=latest,
        line_dash="dot",
        line_color="#7c3aed",
        annotation_text="最新收盤",
        annotation_position="top right",
    )
    fig.update_layout(
        title=f"{ticker} 近一年股價走勢 ({chart_type})",
        xaxis_title="日期",
        yaxis_title="價格",
        template="plotly_white",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=60, b=20),
        height=480,
        showlegend=False,
        # K線圖預設會自帶下方縮放滑桿 (rangeslider)，關閉它讓畫面更乾淨
        xaxis_rangeslider_visible=False,
    )
    return fig


st.title("📈 台灣股票 / 美股估價值診斷")
st.caption("以近一年高低價區間位置做簡易參考，不是投資建議。")

with st.sidebar:
    st.header("查詢設定")
    raw_ticker = st.text_input(
        "股票代號",
        value="2330.TW",
        help="台股可用 2330 或 2330.TW；美股如 AAPL、MSFT。",
    )
    
    # 新增圖表類型選擇器
    chart_type = st.radio(
        "圖表顯示模式",
        options=["折線圖", "K線圖"],
        horizontal=True,
    )
    
    lookup = st.button("開始診斷", type="primary", use_container_width=True)
    st.markdown(
        """
範例：
- `2330` / `2330.TW` 台積電
- `2317.TW` 鴻海
- `AAPL` 蘋果
- `NVDA` 輝達
        """
    )

if lookup or raw_ticker:
    ticker = normalize_ticker(raw_ticker)
    if not ticker:
        st.warning("請輸入股票代號。")
        st.stop()

    try:
        with st.spinner(f"正在抓取 {ticker} 近一年資料…"):
            history = load_one_year_history(ticker)
    except Exception as exc:
        st.error(str(exc) if str(exc) else f"無法取得 {ticker} 的資料，請確認代號後再試。")
        st.stop()

    latest = float(history["Close"].iloc[-1])
    year_high = float(history["High"].max()) if "High" in history.columns else float(history["Close"].max())
    year_low = float(history["Low"].min()) if "Low" in history.columns else float(history["Close"].min())
    pct = position_in_range(latest, year_low, year_high)
    as_of = history.index[-1].strftime("%Y-%m-%d")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("最新收盤", f"{latest:,.2f}", help=f"資料日期：{as_of}")
    col2.metric("近一年最高", f"{year_high:,.2f}")
    col3.metric("近一年最低", f"{year_low:,.2f}")
    col4.metric("區間位置", "—" if pct is None else f"{pct:.1f}%")

    if pct is not None:
        st.progress(min(max(pct / 100, 0), 1), text=f"相對近一年高低區間：{pct:.1f}%（越低越靠近低點）")

    level, message = advice_text(pct)
    getattr(st, level)(message)

    # 傳入選取的 chart_type
    st.plotly_chart(
        build_price_chart(history, ticker, year_low, year_high, latest, chart_type),
        use_container_width=True,
    )

    with st.expander("計算方式"):
        st.markdown(
            f"""
區間位置 = (最新收盤 − 近一年最低) ÷ (近一年最高 − 近一年最低) × 100

目前代入：`({latest:.2f} − {year_low:.2f}) ÷ ({year_high:.2f} − {year_low:.2f}) × 100`

資料來源為 Yahoo Finance（`yfinance`），台股請使用 `.TW` 後綴。
            """
        )
else:
    st.info("在左側輸入代號後按下「開始診斷」。")
