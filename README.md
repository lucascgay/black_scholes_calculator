# Volatility Surface Viewer

This project provides a simple command line utility to visualize the implied volatility surface for an equity option chain.

It pulls option prices from Yahoo Finance via the `yfinance` package, computes implied volatility using the Black–Scholes model, and generates an interactive 3D surface where:

- **X-axis:** Moneyness (strike / spot price)
- **Y-axis:** Days to expiration
- **Z-axis:** Implied volatility

Both calls and puts are included, missing grid points are linearly interpolated, and the resulting plot is saved as an HTML file that can be opened in any web browser.

## Setup

Install the dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the script with a ticker symbol, for example `AAPL` or `VOO`:

```bash
python vol_surface.py AAPL
```

An HTML file (e.g. `vol_surface_AAPL.html`) will be created in the current directory.
