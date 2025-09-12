# Volatility Surface Viewer

This repository provides a simple script that fetches option chain data for a given
equity and renders a three-dimensional implied volatility surface.

## Requirements

Install dependencies with:

```bash
pip install -r requirements.txt
```

## Usage

Generate a surface for a ticker (for example, AAPL) and save it to an HTML file:

```bash
python vol_surface.py AAPL --output aapl_surface.html
```

The resulting file can be opened in a web browser to explore the surface. The axes
represent moneyness (strike divided by spot price), days until expiration, and the
implied volatility for each option contract.
