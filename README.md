# Volatility Surface Viewer

This project provides a simple command line utility to visualize the implied volatility surface for an equity option chain.

It fetches options data from Yahoo Finance via the `yfinance` package and generates an interactive 3D surface where:

- **X-axis:** Moneyness (strike / spot price)
- **Y-axis:** Days to expiration
- **Z-axis:** Implied volatility

The resulting plot is saved as an HTML file that can be opened in any web browser.

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
