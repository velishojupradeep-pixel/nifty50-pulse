"""
Configuration file for NIFTY 50 Tracker & Option Seller Radar
Contains constituent weights, sector mappings, and trading strategy thresholds.
"""

# Symbol alias mapping for Yahoo Finance / Broker APIs
SYMBOL_ALIASES = {
    "TATAMOTORS": "TMPV",
    "TATA-MOTORS": "TMPV",
}

# Up-to-date base weights for NIFTY 50 constituents (normalized to 100%)
# These are periodically updated by NSE based on free-float market capitalization.
NIFTY_50_WEIGHTS = {
    "HDFCBANK": 11.45,
    "RELIANCE": 8.92,
    "ICICIBANK": 7.64,
    "INFY": 5.48,
    "BHARTIARTL": 4.38,
    "ITC": 3.79,
    "TCS": 3.68,
    "LT": 3.62,
    "AXISBANK": 3.12,
    "SBIN": 2.85,
    "KOTAKBANK": 2.74,
    "M&M": 2.45,
    "HINDUNILVR": 2.18,
    "BAJFINANCE": 1.95,
    "MARUTI": 1.72,
    "SUNPHARMA": 1.64,
    "TMPV": 1.55,
    "HCLTECH": 1.42,
    "TITAN": 1.38,
    "NTPC": 1.34,
    "TRENT": 1.32,
    "ULTRACEMCO": 1.25,
    "POWERGRID": 1.24,
    "ADANIENT": 1.21,
    "ADANIPORTS": 1.18,
    "BEL": 1.15,
    "TATASTEEL": 1.14,
    "COALINDIA": 1.05,
    "ONGC": 1.02,
    "ASIANPAINT": 0.98,
    "SHRIRAMFIN": 0.96,
    "JSWSTEEL": 0.94,
    "TECHM": 0.92,
    "BAJAJFINSV": 0.88,
    "HINDALCO": 0.85,
    "BAJAJ-AUTO": 0.82,
    "NESTLEIND": 0.78,
    "GRASIM": 0.76,
    "CIPLA": 0.75,
    "APOLLOHOSP": 0.74,
    "DRREDDY": 0.71,
    "EICHERMOT": 0.69,
    "TATACONSUM": 0.68,
    "SBILIFE": 0.67,
    "WIPRO": 0.66,
    "BPCL": 0.64,
    "HEROMOTOCO": 0.62,
    "DIVISLAB": 0.58,
    "INDUSINDBK": 0.56,
    "HDFCLIFE": 0.52,
}

# Sector classification for every stock
STOCK_SECTORS = {
    # Financial Services (Banking, NBFC, Insurance)
    "HDFCBANK": "Financial Services",
    "ICICIBANK": "Financial Services",
    "AXISBANK": "Financial Services",
    "SBIN": "Financial Services",
    "KOTAKBANK": "Financial Services",
    "BAJFINANCE": "Financial Services",
    "BAJAJFINSV": "Financial Services",
    "SHRIRAMFIN": "Financial Services",
    "SBILIFE": "Financial Services",
    "HDFCLIFE": "Financial Services",
    "INDUSINDBK": "Financial Services",

    # Oil, Gas & Consumable Fuels / Energy
    "RELIANCE": "Oil & Gas / Energy",
    "ONGC": "Oil & Gas / Energy",
    "BPCL": "Oil & Gas / Energy",
    "COALINDIA": "Oil & Gas / Energy",
    "NTPC": "Power & Energy",
    "POWERGRID": "Power & Energy",

    # Information Technology
    "INFY": "Information Technology",
    "TCS": "Information Technology",
    "HCLTECH": "Information Technology",
    "TECHM": "Information Technology",
    "WIPRO": "Information Technology",
    "LTIM": "Information Technology",

    # Automobile and Auto Components
    "M&M": "Automobile",
    "MARUTI": "Automobile",
    "TATAMOTORS": "Automobile",
    "TMPV": "Automobile",
    "BAJAJ-AUTO": "Automobile",
    "EICHERMOT": "Automobile",
    "HEROMOTOCO": "Automobile",

    # Fast Moving Consumer Goods (FMCG)
    "ITC": "FMCG",
    "HINDUNILVR": "FMCG",
    "NESTLEIND": "FMCG",
    "TATACONSUM": "FMCG",

    # Construction & Capital Goods / Defence
    "LT": "Capital Goods & Infra",
    "BEL": "Defence & Electronics",

    # Telecommunication
    "BHARTIARTL": "Telecommunication",

    # Metals & Mining
    "TATASTEEL": "Metals & Mining",
    "JSWSTEEL": "Metals & Mining",
    "HINDALCO": "Metals & Mining",

    # Healthcare & Pharmaceuticals
    "SUNPHARMA": "Healthcare & Pharma",
    "CIPLA": "Healthcare & Pharma",
    "APOLLOHOSP": "Healthcare & Pharma",
    "DRREDDY": "Healthcare & Pharma",
    "DIVISLAB": "Healthcare & Pharma",

    # Consumer Services & Retail
    "TITAN": "Consumer Durables",
    "TRENT": "Retail & Consumer",
    "ASIANPAINT": "Consumer Durables",

    # Construction Materials / Cement
    "ULTRACEMCO": "Cement & Materials",
    "GRASIM": "Cement & Materials",

    # Conglomerates / Ports / Logistics
    "ADANIENT": "Diversified / Commodities",
    "ADANIPORTS": "Services & Logistics",
}

# The Top 5 heavyweights that determine ~40% of NIFTY's momentum
TOP_5_HEAVYWEIGHTS = ["HDFCBANK", "RELIANCE", "ICICIBANK", "INFY", "BHARTIARTL"]
TOP_10_HEAVYWEIGHTS = [
    "HDFCBANK", "RELIANCE", "ICICIBANK", "INFY", "BHARTIARTL",
    "ITC", "TCS", "LT", "AXISBANK", "SBIN"
]

# Option Seller Regime Thresholds
REGIME_THRESHOLDS = {
    # If heavyweight alignment score is within this range, market is in Tug-of-War / Rangebound
    "RANGEBOUND_MIN": -25.0,
    "RANGEBOUND_MAX": 25.0,
    # Above this, heavyweights are collectively bullish -> Trend day risk for call sellers
    "BULLISH_TREND": 45.0,
    # Below this, heavyweights are collectively bearish -> Trend day risk for put sellers
    "BEARISH_TREND": -45.0,
}

# Volume thresholds (RVOL = Current Volume / 20-Day SMA Volume)
VOLUME_THRESHOLDS = {
    "RVOL_MODERATE": 1.3,
    "RVOL_HIGH": 1.8,
    "RVOL_EXTREME": 2.5,
}

# Default Nifty 50 base value if not fetched
DEFAULT_NIFTY_VALUE = 24500.0
