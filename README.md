# Volatility Surface Viewer

A command-line tool to visualize implied volatility surfaces for equity options. Pulls option chain data from Yahoo Finance, computes implied volatility using the Black-Scholes model, and generates an interactive 3D surface plot.

## Features

- **Smart Data Filtering**: Automatically filters outliers and extreme values using IQR and percentile methods
- **Smooth Surface Visualization**: Uses binning, averaging, and Gaussian smoothing to create clean, professional surfaces
- **Dual Visualization**: Shows both a smoothed surface and raw data points overlaid
- **Time Range Control**: Focus on near-term options (default 180 days) or include LEAPs
- **Non-linear Time Scaling**: Optional square-root transform for better resolution of near-term options
- **Better Price Data**: Uses bid-ask midpoint when available for more accurate pricing

## Setup

Install the dependencies:

```bash
pip install -r requirements.txt
```

Or if using a virtual environment:

```bash
python -m venv myvenv
source myvenv/bin/activate  # On Windows: myvenv\Scripts\activate
python -m pip install -r requirements.txt
```

## Usage

### Basic Usage

Plot the volatility surface for a ticker (defaults to 180 days max expiration):

```bash
python vol_surface.py AAPL
```

This creates an interactive HTML file (`vol_surface_AAPL.html`) that you can open in any web browser.

### Command Line Options

```bash
python vol_surface.py TICKER [OPTIONS]
```

**Options:**
- `-t, --type {call,put,both}`: Option type to include (default: `both`)
- `--max-days N`: Maximum days to expiration to include (default: `180`, use `0` for no limit)
- `--sqrt-time`: Use square-root transform for time axis to give more visual resolution to near-term options
- `--debug`: Print detailed debug information about data filtering and processing
- `--debug-rows N`: Max rows to print per expiry/type when debugging (default: `5`)

### Examples

**Focus on near-term options (90 days) with sqrt time transform:**
```bash
python vol_surface.py AAPL --max-days 90 --sqrt-time
```

**Show only call options for 6 months:**
```bash
python vol_surface.py SPY -t call --max-days 180
```

**Include all LEAPs (no time limit):**
```bash
python vol_surface.py VOO --max-days 0
```

**Debug mode to see data filtering:**
```bash
python vol_surface.py MSFT --debug
```

## Output

The plot shows:
- **X-axis**: Moneyness (strike / spot price)
- **Y-axis**: Days to Expiration (or √days if `--sqrt-time` is used)
- **Z-axis**: Implied Volatility

The visualization includes:
- A **smooth, colored surface** showing the averaged volatility trend
- **Scatter points** overlaid showing the raw data
- Interactive controls to rotate, zoom, and explore the 3D surface

## How It Works

1. **Data Fetching**: Retrieves option chain data from Yahoo Finance
2. **Price Selection**: Uses bid-ask midpoint when available, falls back to last price
3. **IV Calculation**: Computes implied volatility using Black-Scholes via Brent's method
4. **Outlier Filtering**: 
   - Hard caps volatility between 1% and 200%
   - Filters extreme moneyness (0.5x to 1.5x spot)
   - Applies IQR-based filtering (1.5× multiplier)
   - Removes top/bottom 2% of values
5. **Surface Generation**:
   - Bins data into 30×30 grid and averages within each bin
   - Interpolates to 100×100 grid using cubic splines
   - Applies Gaussian smoothing (sigma=2.0) for final surface
   - Clamps interpolated values to prevent artifacts

## Requirements

- Python 3.7+
- numpy
- pandas
- scipy
- plotly
- yfinance

See `requirements.txt` for specific versions.
