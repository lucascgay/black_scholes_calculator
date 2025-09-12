import argparse
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf


def fetch_option_chain(ticker: str) -> pd.DataFrame:
    """Fetch options chain for all expirations and return DataFrame."""
    t = yf.Ticker(ticker)
    hist = t.history(period="1d")
    if hist.empty:
        raise RuntimeError(f"No price history for {ticker}")
    spot_price = hist['Close'].iloc[-1]
    records = []
    for exp in t.options:
        chain = t.option_chain(exp)
        calls = chain.calls[['strike', 'impliedVolatility']].copy()
        calls['expiration'] = pd.to_datetime(exp)
        records.append(calls)
    df = pd.concat(records, ignore_index=True)
    df['days_to_exp'] = (df['expiration'] - datetime.utcnow()).dt.days
    df['moneyness'] = (df['strike'] / spot_price).round(2)
    return df


def plot_surface(df: pd.DataFrame, ticker: str) -> None:
    """Plot implied volatility surface using moneyness and time to expiration."""
    surface = df.pivot_table(index='days_to_exp', columns='moneyness', values='impliedVolatility')
    x = surface.columns.astype(float)
    y = surface.index.astype(float)
    z = surface.values
    fig = go.Figure(data=[go.Surface(x=x, y=y, z=z)])
    fig.update_layout(
        title=f'Implied Volatility Surface for {ticker}',
        scene=dict(
            xaxis_title='Moneyness (strike/spot)',
            yaxis_title='Days to Expiration',
            zaxis_title='Implied Volatility'
        )
    )
    output_file = f'vol_surface_{ticker}.html'
    fig.write_html(output_file)
    print(f'Volatility surface saved to {output_file}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Plot option volatility surface for a ticker')
    parser.add_argument('ticker', help='Ticker symbol, e.g. AAPL or VOO')
    args = parser.parse_args()
    df = fetch_option_chain(args.ticker)
    plot_surface(df, args.ticker)


if __name__ == '__main__':
    main()
