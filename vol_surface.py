import argparse
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from scipy.stats import norm
from scipy.optimize import brentq
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter

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


def fetch_option_chain(
    ticker: str,
    option_type: str = "both",
    max_days: int = None,
    debug: bool = False,
    debug_rows: int = 5,
) -> pd.DataFrame:
    """Fetch option prices and compute implied volatility via Black-Scholes.

    Parameters
    - ticker: Underlying ticker symbol
    - option_type: One of {"call", "put", "both"} to select which option legs to include
    - max_days: Maximum days to expiration to include (None = no limit)
    - debug: If True, prints detailed chain stats for troubleshooting
    - debug_rows: Max number of rows to print per type/expiry in debug output
    """
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
    if debug:
        weekday = now.weekday()
        minutes_utc = now.hour * 60 + now.minute
        approx_us_open = 13 * 60 + 30
        approx_us_close = 21 * 60
        likely_us_market_hours = (weekday < 5) and (approx_us_open <= minutes_utc < approx_us_close)
        print(f"[DEBUG] {ticker}: now UTC={now.isoformat()}Z, spot={spot_price:.4f}")
        print(f"[DEBUG] Approx US market hours window 13:30–21:00 UTC; in_window={likely_us_market_hours}")
    for exp in t.options:
        chain = t.option_chain(exp)
        exp_dt = pd.to_datetime(exp)
        types_to_fetch = ["call", "put"] if option_type == "both" else [option_type]
        for opt_type in types_to_fetch:
            frame = chain.calls if opt_type == "call" else chain.puts
            if debug:
                raw_count = len(frame)
                zeros = frame["lastPrice"].eq(0).sum() if "lastPrice" in frame.columns else 0
                nans = frame["lastPrice"].isna().sum() if "lastPrice" in frame.columns else 0
                min_strike = float(np.nanmin(frame["strike"])) if len(frame) else np.nan
                max_strike = float(np.nanmax(frame["strike"])) if len(frame) else np.nan
                print(f"[DEBUG] {exp_dt.date()} {opt_type}: raw={raw_count}, lastPrice zeros={zeros}, nans={nans}, strikes=[{min_strike:.2f}, {max_strike:.2f}]")
                cols_to_show = [c for c in ["strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility"] if c in frame.columns]
                if raw_count and cols_to_show:
                    tmp = frame.copy()
                    if "bid" in tmp.columns and "ask" in tmp.columns:
                        tmp["mid"] = (tmp["bid"].fillna(0) + tmp["ask"].fillna(0)) / 2.0
                        cols = [c for c in ["strike", "lastPrice", "bid", "ask", "mid", "volume", "openInterest"] if c in tmp.columns]
                    else:
                        cols = cols_to_show
                    tmp = tmp.assign(_dist=(tmp["strike"] - spot_price).abs()).sort_values("_dist").head(debug_rows)
                    print(tmp[cols].to_string(index=False))
            # Use bid-ask midpoint if available, otherwise fall back to lastPrice
            if "bid" in frame.columns and "ask" in frame.columns:
                frame_copy = frame.copy()
                frame_copy["price"] = (frame_copy["bid"] + frame_copy["ask"]) / 2.0
                # If bid-ask mid is 0 or NaN, use lastPrice as fallback
                frame_copy.loc[frame_copy["price"] <= 0, "price"] = frame_copy.loc[frame_copy["price"] <= 0, "lastPrice"]
                subset = frame_copy[["strike", "price"]].copy()
            else:
                subset = frame[["strike", "lastPrice"]].rename(columns={"lastPrice": "price"})
            subset = subset[(subset["price"].notna()) & (subset["price"] > 0)].copy()
            if debug:
                kept = len(subset)
                dropped = len(frame) - kept
                print(f"[DEBUG] {exp_dt.date()} {opt_type}: kept={kept}, dropped={dropped} due to missing/zero price")
            subset["expiration"] = exp_dt
            subset["type"] = opt_type
            subset["T"] = (exp_dt - now).days / 365
            subset["impliedVolatility"] = subset.apply(
                lambda row: implied_vol(row["price"], spot_price, row["strike"], row["T"], RISK_FREE_RATE, opt_type),
                axis=1,
            )
            if debug:
                iv_nan = subset["impliedVolatility"].isna().sum()
                iv_ok = len(subset) - iv_nan
                print(f"[DEBUG] {exp_dt.date()} {opt_type}: IV computed ok={iv_ok}, nan={iv_nan}")
            records.append(subset)

    if not records:
        raise RuntimeError(f"No option data fetched for type '{option_type}' on {ticker}")
    df = pd.concat(records, ignore_index=True)
    df = df.dropna(subset=["impliedVolatility"])
    df["days_to_exp"] = (df["expiration"] - now).dt.days
    df["moneyness"] = df["strike"] / spot_price
    
    if debug:
        before_filter = len(df)
        print(f"[DEBUG] Days to expiration range: [{df['days_to_exp'].min()}, {df['days_to_exp'].max()}]")
        print(f"[DEBUG] IV range before filtering: [{df['impliedVolatility'].min():.4f}, {df['impliedVolatility'].max():.4f}]")
        print(f"[DEBUG] Moneyness range: [{df['moneyness'].min():.4f}, {df['moneyness'].max():.4f}]")
    
    # Filter by max days to expiration if specified
    if max_days is not None:
        df = df[df["days_to_exp"] <= max_days]
        if debug:
            print(f"[DEBUG] After filtering to max {max_days} days: {len(df)} rows remaining")
        if len(df) == 0:
            raise RuntimeError(f"No options remaining with days to expiration <= {max_days}")
    
    # Step 1: Hard cap on volatility - remove extreme outliers first
    df = df[(df["impliedVolatility"] >= 0.01) & (df["impliedVolatility"] <= 2.0)]
    
    # Step 2: Filter extreme moneyness (keep strikes within 0.5 to 1.5 of spot)
    df = df[(df["moneyness"] >= 0.5) & (df["moneyness"] <= 1.5)]
    
    if len(df) == 0:
        raise RuntimeError("No data remaining after filtering extreme values")
    
    # Step 3: More aggressive IQR-based filtering
    q1 = df["impliedVolatility"].quantile(0.25)
    q3 = df["impliedVolatility"].quantile(0.75)
    iqr = q3 - q1
    lower_bound = max(0.01, q1 - 1.5 * iqr)
    upper_bound = min(1.5, q3 + 1.5 * iqr)  # Cap at 150% vol
    
    if debug:
        print(f"[DEBUG] After hard cap: {len(df)} rows, IV range: [{df['impliedVolatility'].min():.4f}, {df['impliedVolatility'].max():.4f}]")
        print(f"[DEBUG] IQR bounds: [{lower_bound:.4f}, {upper_bound:.4f}]")
    
    df = df[(df["impliedVolatility"] >= lower_bound) & (df["impliedVolatility"] <= upper_bound)]
    
    # Step 4: Remove extreme percentiles (top/bottom 2%)
    p2 = df["impliedVolatility"].quantile(0.02)
    p98 = df["impliedVolatility"].quantile(0.98)
    df = df[(df["impliedVolatility"] >= p2) & (df["impliedVolatility"] <= p98)]
    
    if debug:
        after_filter = len(df)
        print(f"[DEBUG] Filtered {before_filter - after_filter} outliers, {after_filter} rows remaining")
        print(f"[DEBUG] Final IV range: [{df['impliedVolatility'].min():.4f}, {df['impliedVolatility'].max():.4f}]")
        print(f"[DEBUG] Final moneyness range: [{df['moneyness'].min():.4f}, {df['moneyness'].max():.4f}]")
    
    if len(df) < 10:
        raise RuntimeError(f"Insufficient data after filtering: only {len(df)} points remaining")
    
    df["moneyness"] = df["moneyness"].round(2)
    return df


def plot_surface(df: pd.DataFrame, ticker: str, option_type: str = "both", sqrt_time: bool = False, debug: bool = False) -> None:
    """Plot implied volatility surface using moneyness and time to expiration.
    
    Parameters
    - df: DataFrame with option data
    - ticker: Ticker symbol
    - option_type: Type of options ("call", "put", or "both")
    - sqrt_time: If True, use sqrt(days) for time axis to give more resolution to near-term options
    - debug: If True, print debug information
    """
    
    # Extract data points
    df_plot = df.copy()
    
    # Apply sqrt transform to time axis if requested
    if sqrt_time:
        df_plot["time_axis"] = np.sqrt(df_plot["days_to_exp"])
        time_label = "Time to Maturity (√days)"
        if debug:
            print(f"[DEBUG] Using sqrt time transform")
    else:
        df_plot["time_axis"] = df_plot["days_to_exp"]
        time_label = "Days to Expiration"
    
    points = df_plot[["moneyness", "time_axis"]].values
    values = df_plot["impliedVolatility"].values
    
    if debug:
        print(f"[DEBUG] Data points: {len(points)}, moneyness range: [{df_plot['moneyness'].min():.2f}, {df_plot['moneyness'].max():.2f}]")
        print(f"[DEBUG] Time range: [{df_plot['time_axis'].min():.2f}, {df_plot['time_axis'].max():.2f}]")
    
    # Step 1: Create averaged/binned data for smoother surface
    # Bin the data into cells and take the average
    moneyness_bins = np.linspace(df_plot["moneyness"].min(), df_plot["moneyness"].max(), 30)
    time_bins = np.linspace(df_plot["time_axis"].min(), df_plot["time_axis"].max(), 30)
    
    # Assign each point to a bin
    df_plot["money_bin"] = pd.cut(df_plot["moneyness"], bins=moneyness_bins, labels=False, include_lowest=True)
    df_plot["time_bin"] = pd.cut(df_plot["time_axis"], bins=time_bins, labels=False, include_lowest=True)
    
    # Average within each bin
    binned = df_plot.groupby(["money_bin", "time_bin"], observed=True)["impliedVolatility"].mean().reset_index()
    binned["moneyness"] = moneyness_bins[binned["money_bin"]]
    binned["time_axis"] = time_bins[binned["time_bin"]]
    
    binned_points = binned[["moneyness", "time_axis"]].values
    binned_values = binned["impliedVolatility"].values
    
    if debug:
        print(f"[DEBUG] Binned to {len(binned_values)} averaged points")
    
    # Step 2: Create a high-resolution grid for smooth interpolation
    moneyness_range = np.linspace(df_plot["moneyness"].min(), df_plot["moneyness"].max(), 100)
    time_range = np.linspace(df_plot["time_axis"].min(), df_plot["time_axis"].max(), 100)
    grid_x, grid_y = np.meshgrid(moneyness_range, time_range)
    
    # Interpolate from binned/averaged data
    try:
        grid_z = griddata(binned_points, binned_values, (grid_x, grid_y), method='cubic')
        if debug:
            print(f"[DEBUG] Using cubic interpolation on binned data")
    except Exception as e:
        if debug:
            print(f"[DEBUG] Cubic interpolation failed ({e}), falling back to linear")
        grid_z = griddata(binned_points, binned_values, (grid_x, grid_y), method='linear')
    
    # Fill any remaining NaNs with nearest neighbor
    nan_mask = np.isnan(grid_z)
    if nan_mask.any():
        grid_z_filled = griddata(binned_points, binned_values, (grid_x, grid_y), method='nearest')
        grid_z[nan_mask] = grid_z_filled[nan_mask]
        if debug:
            print(f"[DEBUG] Filled {nan_mask.sum()} NaN cells with nearest neighbor")
    
    # Step 3: Apply Gaussian smoothing to reduce noise
    grid_z = gaussian_filter(grid_z, sigma=2.0)
    
    # Clamp interpolated values to reasonable range
    min_iv = np.percentile(values, 1)
    max_iv = np.percentile(values, 99)
    grid_z = np.clip(grid_z, min_iv, max_iv)
    
    if debug:
        print(f"[DEBUG] Grid z-range after smoothing: [{np.nanmin(grid_z):.4f}, {np.nanmax(grid_z):.4f}]")
    
    # Step 4: Create the plot with both surface and scatter points
    fig = go.Figure()
    
    # Add smooth surface (semi-transparent)
    fig.add_trace(go.Surface(
        x=grid_x[0], 
        y=grid_y[:, 0], 
        z=grid_z, 
        colorscale='Viridis',
        opacity=0.9,
        name='Smoothed Surface',
        showscale=True
    ))
    
    # Add scatter points for raw data
    fig.add_trace(go.Scatter3d(
        x=df_plot["moneyness"],
        y=df_plot["time_axis"],
        z=df_plot["impliedVolatility"],
        mode='markers',
        marker=dict(
            size=2,
            color='rgba(0, 0, 0, 0.5)',
            symbol='circle'
        ),
        name='Raw Data',
        showlegend=True
    ))
    
    fig.update_layout(
        title=f"Implied Volatility Surface for {ticker} ({option_type})",
        scene=dict(
            xaxis_title="Moneyness (strike/spot)",
            yaxis_title=time_label,
            zaxis_title="Implied Volatility",
        ),
    )
    output_file = f"vol_surface_{ticker}.html"
    fig.write_html(output_file)
    print(f"Volatility surface saved to {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description='Plot option volatility surface for a ticker')
    parser.add_argument('ticker', help='Ticker symbol, e.g. AAPL or VOO')
    parser.add_argument('-t', '--type', dest='option_type', choices=['call', 'put', 'both'], default='both',
                        help='Option type to include: call, put, or both (default)')
    parser.add_argument('--max-days', type=int, default=180, 
                        help='Maximum days to expiration to include (default: 180, use 0 for no limit)')
    parser.add_argument('--sqrt-time', action='store_true',
                        help='Use sqrt(days) for time axis to give more visual resolution to near-term options')
    parser.add_argument('--debug', action='store_true', help='Print detailed debug info about fetched options and grid sparsity')
    parser.add_argument('--debug-rows', type=int, default=5, help='Max rows to print per expiry/type when debugging')
    args = parser.parse_args()
    
    max_days = None if args.max_days == 0 else args.max_days
    
    df = fetch_option_chain(args.ticker, option_type=args.option_type, max_days=max_days, 
                           debug=args.debug, debug_rows=args.debug_rows)
    plot_surface(df, args.ticker, option_type=args.option_type, sqrt_time=args.sqrt_time, debug=args.debug)


if __name__ == '__main__':
    main()
