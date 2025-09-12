import argparse
import datetime as dt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf

def fetch_option_data(ticker: str) -> pd.DataFrame:
    """Fetch option chain data and compute moneyness and days to expiration."""
    tk = yf.Ticker(ticker)
    spot_price = tk.info["regularMarketPrice"]
    expirations = tk.options
    records = []
    today = pd.Timestamp.today()
    for exp in expirations:
        exp_date = pd.Timestamp(exp)
        days = (exp_date - today).days
        chain = tk.option_chain(exp)
        calls = chain.calls
        for _, row in calls.iterrows():
            strike = row["strike"]
            iv = row["impliedVolatility"]
            price = (row["bid"] + row["ask"]) / 2
            moneyness = strike / spot_price
            records.append({
                "price": price,
                "strike": strike,
                "moneyness": moneyness,
                "iv": iv,
                "days": days,
            })
    return pd.DataFrame(records)

def plot_surface(df: pd.DataFrame, ticker: str, output: str) -> None:
    pivot = df.pivot_table(values="iv", index="days", columns="moneyness")
    x = pivot.columns.values
    y = pivot.index.values
    z = pivot.values
    fig = go.Figure(data=[go.Surface(x=x, y=y, z=z, colorscale="Viridis")])
    fig.update_layout(
        title=f"{ticker} Implied Volatility Surface",
        scene=dict(
            xaxis_title="Moneyness (K/S)",
            yaxis_title="Days to Expiration",
            zaxis_title="Implied Volatility",
        ),
    )
    fig.write_html(output)

def main() -> None:
    parser = argparse.ArgumentParser(description="Plot an implied volatility surface for a given equity.")
    parser.add_argument("ticker", help="Ticker symbol, e.g. AAPL or VOO")
    parser.add_argument("--output", default="vol_surface.html", help="Path to save the generated HTML file")
    args = parser.parse_args()
    df = fetch_option_data(args.ticker)
    plot_surface(df, args.ticker, args.output)
    print(f"Saved volatility surface to {args.output}")

if __name__ == "__main__":
    main()
