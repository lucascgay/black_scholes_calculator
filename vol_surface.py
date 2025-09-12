import argparse
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from scipy.stats import norm
from scipy.optimize import brentq

RISK_FREE_RATE = 0.03


def bs_price(s, k, t, r, sigma, option_type):
    if t <= 0:
        return max(s - k, 0) if option_type == "call" else max(k - s, 0)
    d1 = (np.log(s / k) + (r + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)
    if option_type == "call":
        return s * norm.cdf(d1) - k * np.exp(-r * t) * norm.cdf(d2)
    return k * np.exp(-r * t) * norm.cdf(-d2) - s * norm.cdf(-d1)


def implied_vol(price, s, k, t, r, option_type):
    try:
        return brentq(lambda x: bs_price(s, k, t, r, x, option_type) - price, 1e-6, 5)
    except ValueError:
        return np.nan


def fetch_option_chain(ticker: str) -> pd.DataFrame:
    """Fetch option prices and compute implied volatility via Black-Scholes."""
    t = yf.Ticker(ticker)
    try:
        spot_price = t.fast_info["lastPrice"]
    except Exception:
        hist = t.history(period="1d")
        if hist.empty:
            raise RuntimeError(f"No price data for {ticker}")
        spot_price = hist["Close"].iloc[-1]

    records = []
    now = datetime.utcnow()
    for exp in t.options:
        chain = t.option_chain(exp)
        exp_dt = pd.to_datetime(exp)
        for opt_type, frame in [("call", chain.calls), ("put", chain.puts)]:
            subset = frame[["strike", "lastPrice"]].rename(columns={"lastPrice": "price"})
            subset = subset[(subset["price"].notna()) & (subset["price"] > 0)].copy()
            subset["expiration"] = exp_dt
            subset["type"] = opt_type
            subset["T"] = (exp_dt - now).days / 365
            subset["impliedVolatility"] = subset.apply(
                lambda row: implied_vol(row["price"], spot_price, row["strike"], row["T"], RISK_FREE_RATE, opt_type),
                axis=1,
            )
            records.append(subset)

    df = pd.concat(records, ignore_index=True)
    df = df.dropna(subset=["impliedVolatility"])
    df["days_to_exp"] = (df["expiration"] - now).dt.days
    df["moneyness"] = (df["strike"] / spot_price).round(2)
    return df


def plot_surface(df: pd.DataFrame, ticker: str) -> None:
    """Plot implied volatility surface using moneyness and time to expiration."""
    surface = (
        df.pivot_table(index="days_to_exp", columns="moneyness", values="impliedVolatility")
        .interpolate(method="linear", axis=0)
        .interpolate(method="linear", axis=1)
    )
    x = surface.columns.astype(float)
    y = surface.index.astype(float)
    z = surface.values
    fig = go.Figure(data=[go.Surface(x=x, y=y, z=z)])
    fig.update_layout(
        title=f"Implied Volatility Surface for {ticker}",
        scene=dict(
            xaxis_title="Moneyness (strike/spot)",
            yaxis_title="Days to Expiration",
            zaxis_title="Implied Volatility",
        ),
    )
    output_file = f"vol_surface_{ticker}.html"
    fig.write_html(output_file)
    print(f"Volatility surface saved to {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description='Plot option volatility surface for a ticker')
    parser.add_argument('ticker', help='Ticker symbol, e.g. AAPL or VOO')
    args = parser.parse_args()
    df = fetch_option_chain(args.ticker)
    plot_surface(df, args.ticker)


if __name__ == '__main__':
    main()
