"""Streamlit 应用：实时比特币价格看板"""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd
import requests
import streamlit as st
from plotly import graph_objects as go


class DataFetchError(RuntimeError):
    """表示远端数据获取失败"""


@dataclass
class AppConfig:
    """应用配置，可从环境变量覆盖"""

    api_base_url: str = "https://api.coingecko.com/api/v3"
    market_days: int = 2

    @classmethod
    def from_env(cls) -> "AppConfig":
        cfg = cls()
        cfg.api_base_url = os.getenv("COINGECKO_API_URL", cfg.api_base_url)
        market_days = os.getenv("COINGECKO_MARKET_DAYS")
        if market_days:
            cfg.market_days = max(1, int(market_days))
        return cfg


def validate_price_data(func):
    """验证数据字段与基本合理性"""

    def wrapper(*args, **kwargs):
        data = func(*args, **kwargs)
        required = ["current_price", "price_change_24h", "price_change_percentage_24h"]
        for field in required:
            if data.get(field) is None:
                raise DataFetchError(f"缺少字段: {field}")
        if data["current_price"] <= 0:
            raise DataFetchError("价格数据异常")
        return data

    return wrapper


class BitcoinDataService:
    """封装与 CoinGecko 通信的服务"""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    @validate_price_data
    def fetch_current_metrics(self) -> Dict[str, Any]:
        url = (
            f"{self.config.api_base_url}/simple/price"
            "?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
        )
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        payload = response.json()["bitcoin"]
        current_price = payload["usd"]
        change_percent = payload["usd_24h_change"]
        change_abs = current_price * change_percent / 100
        return {
            "current_price": current_price,
            "price_change_24h": change_abs,
            "price_change_percentage_24h": change_percent,
        }

    def fetch_market_chart(self) -> pd.DataFrame:
        url = (
            f"{self.config.api_base_url}/coins/bitcoin/market_chart"
            f"?vs_currency=usd&days={self.config.market_days}"
        )
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        prices = response.json().get("prices", [])
        if not prices:
            raise DataFetchError("未获取到价格曲线")
        df = pd.DataFrame(prices, columns=["timestamp", "price"])
        df["time"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("time").drop(columns=["timestamp"])
        return df


def init_session_state(data_service: Optional[BitcoinDataService] = None) -> None:
    if data_service is None:
        data_service = BitcoinDataService(AppConfig.from_env())
    state = st.session_state
    state.setdefault("data_service", data_service)
    state.setdefault("price_data", None)
    state.setdefault("market_df", None)
    state.setdefault("last_update", None)
    state.setdefault("auto_refresh", False)
    state.setdefault("refresh_interval", 60)
    state.setdefault("manual_refresh_triggered", False)


def should_refresh_data() -> bool:
    state = st.session_state
    needs_refresh = state["price_data"] is None
    manual = state.get("manual_refresh_triggered", False)
    auto = False
    if state["auto_refresh"] and state["last_update"]:
        delta = datetime.now() - state["last_update"]
        auto = delta.total_seconds() >= state["refresh_interval"]
    return any([needs_refresh, manual, auto])


def handle_auto_refresh() -> None:
    state = st.session_state
    if not state["auto_refresh"] or not state["last_update"]:
        return
    now = datetime.now()
    next_refresh = state["last_update"] + timedelta(seconds=state["refresh_interval"])
    if now >= next_refresh:
        state["manual_refresh_triggered"] = True
        state["last_update"] = now
        st.rerun()


def refresh_data() -> None:
    state = st.session_state
    service: BitcoinDataService = state["data_service"]
    with st.spinner("正在获取比特币行情..."):
        price_data = service.fetch_current_metrics()
        market_df = service.fetch_market_chart()
        state["price_data"] = price_data
        state["market_df"] = market_df
        state["last_update"] = datetime.now()
    state["manual_refresh_triggered"] = False


def format_price(value: float) -> str:
    return f"${value:,.2f}"


def render_price_display(data: Dict[str, Any]) -> None:
    price = data["current_price"]
    change_abs = data["price_change_24h"]
    change_pct = data["price_change_percentage_24h"]
    is_up = change_abs >= 0
    emoji = "📈" if is_up else "📉"
    cls = "change-up" if is_up else "change-down"
    sign = "+" if is_up else "-"

    st.markdown(
        f"""
        <div class="price-display">
            <div class="price-main">{emoji} {format_price(price)}</div>
            <div class="{cls}">{sign}{abs(change_abs):,.2f} USD ({sign}{abs(change_pct):.2f}%)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chart(df: pd.DataFrame) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["price"], mode="lines", name="BTC/USD"))
    fig.update_layout(
        margin=dict(l=12, r=12, t=30, b=12),
        height=320,
        template="plotly_dark",
        yaxis_title="价格 (USD)",
        xaxis_title="时间",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_sidebar() -> None:
    st.sidebar.header("刷新设置")
    st.sidebar.checkbox(
        "自动刷新", key="auto_refresh", help="按照指定间隔自动更新数据"
    )
    st.sidebar.slider(
        "刷新间隔 (秒)",
        min_value=10,
        max_value=300,
        step=10,
        key="refresh_interval",
    )
    if st.sidebar.button("立即刷新", use_container_width=True):
        st.session_state["manual_refresh_triggered"] = True
        st.experimental_rerun()


def main() -> None:
    st.set_page_config(page_title="BTC 实时价格", page_icon="💰", layout="wide")
    st.title("💰 比特币实时价格看板")
    st.caption("数据来源：CoinGecko API，展示当前价格、涨跌幅及趋势图")

    st.markdown(
        """
        <style>
        .price-display {font-size: 1.4rem; padding: 0.8rem 1rem; border-radius: 0.6rem; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);}
        .price-main {font-weight: 600; margin-bottom: 0.2rem;}
        .change-up {color: #4ade80;}
        .change-down {color: #f87171;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    init_session_state()
    render_sidebar()
    handle_auto_refresh()

    if should_refresh_data():
        try:
            refresh_data()
        except (requests.RequestException, DataFetchError) as err:
            st.error(f"获取数据失败：{err}")

    state = st.session_state
    col_left, col_right = st.columns([1, 1])
    with col_left:
        if state["price_data"]:
            render_price_display(state["price_data"])
            if state["last_update"]:
                st.markdown(
                    f"**最近更新时间：** {state['last_update'].strftime('%Y-%m-%d %H:%M:%S')}"
                )
        else:
            st.info("暂无价格数据，请刷新")

    with col_right:
        if state["market_df"] is not None:
            render_chart(state["market_df"])
        else:
            st.info("暂无趋势数据")

    if state["market_df"] is not None:
        st.subheader("📊 价格明细")
        preview = state["market_df"].tail(20).copy()
        preview.index = preview.index.strftime("%Y-%m-%d %H:%M")
        st.dataframe(preview.rename(columns={"price": "BTC/USD"}))


if __name__ == "__main__":
    main()