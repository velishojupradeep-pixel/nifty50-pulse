# ⚡ NIFTY 50 Option Seller Radar & Constituent Volume Tracker

A real-time financial tracking dashboard built specifically for **Indian Index Option Traders** (especially option sellers / theta collectors). 

Unlike generic stock screeners that only track percentage changes, this application breaks down **real-time constituent point contributions**, **free-float weightages**, **heavyweight alignment (Tug-of-War)**, and **Relative Volume (RVOL) surges** to help you make informed decisions when selling Straddles, Strangles, Iron Condors, and Credit Spreads.

---

## 🎯 Why Option Sellers Need Constituent Weightage Analysis

When selling NIFTY options, index movement creates your primary risk: **Delta Risk / Gamma Expansion**. 

Generic screeners tell you: *"Nifty is up 80 points, Tata Motors is up 3.5%"*. 
**This is misleading for option traders because:**
1. **Unequal Power**: The top 5 stocks (**HDFC Bank, Reliance, ICICI Bank, Infosys, Bharti Airtel**) command nearly **40% of the entire index weight**.
2. **Point Impact Formula**:
   $$\Delta \text{Points}_i = \frac{\text{Weight}_i \times \% \Delta P_i \times \text{Nifty}_{\text{prev}}}{10,000}$$
   A 1.5% move in Reliance or HDFC Bank swings NIFTY **~30 to 40 points**, whereas a 4% move in a stock with 0.7% weight moves NIFTY only **~6 points**.
3. **The "Tug-of-War" Sweet Spot**:
   - When **HDFC Bank is UP** (+1.5%) and **Reliance is DOWN** (-1.2%), their points impact cancels out. The index is pinned in a tight range.
   - **Result**: Favorable environment for **Short Straddles / Iron Flies / Rangebound Iron Condors** because Delta remains neutral while Theta decays safely.
4. **Trend Day Alert**:
   - When Top 5 heavyweights align in the same direction with high Relative Volume (**RVOL > 1.8x**), the market is in a **one-way institutional trend**.
   - **Result**: Danger zone for naked call or put sellers. Alerts you to hedge short deltas or shift to defined-risk directional credit spreads.

---

## 🚀 Key Features

| Feature | Option Seller Advantage |
| :--- | :--- |
| **Market Regime & Heavyweight Alignment Meter** | Instant indicator: *Rangebound / Tug-of-War (Ideal Theta)* vs *Trend Alert (Gamma Danger)* |
| **Point Contribution Diverging Chart** | Identifies exactly which stocks are pulling the index up vs dragging it down |
| **Top 5 Heavyweight Radar** | Tracks HDFCBANK, RELIANCE, ICICIBANK, INFY, BHARTIARTL with individual RVOL and point impact |
| **Volume Surge & RVOL Tracker** | Flags institutional buying/selling by comparing live volume against the 20-day historical SMA |
| **Sector Tug-of-War** | Visualizes whether Banking is offsetting IT or Energy |
| **Complete 50 Constituents Screener** | Filter and sort by weight, point contribution, RVOL, or sector |
| **Hybrid Live Data Engine** | Runs out of the box on free live data (Yahoo Finance & NSE endpoints) + plug-and-play template for Broker APIs (Zerodha Kite / Dhan) |

---

## 🛠️ Project Structure

```text
nifty50-pulse/
├── app.py                      # Interactive Streamlit trading terminal UI
├── config.py                   # Constituent weights, sector mappings & regime thresholds
├── run.sh                      # One-click startup script
├── core/
│   ├── engine.py               # Market regime meter, points calculation, RVOL logic
│   ├── weights.py              # Dynamic weightage & point contribution mathematics
│   └── sectors.py              # Sector-wise aggregation & breadth metrics
├── data/
│   ├── base.py                 # Abstract BaseDataProvider interface
│   ├── manager.py              # Unified manager with auto-fallback & volume cache
│   ├── yfinance_provider.py    # Yahoo Finance provider for quotes & 20D average volume
│   ├── nse_provider.py         # NSE India direct live endpoint scraper
│   └── broker_provider.py      # Plug-and-play adapter for Zerodha / Dhan / Fyers
└── utils/
    └── formatting.py           # Plotly charts, currency formatters & visual tags
```

---

## ⚡ How to Run

### 1. Launch the Application
Simply run the startup script:
```bash
cd /Users/PradeepV/.gemini/antigravity/scratch/nifty50-pulse
./run.sh
```
Or start manually via python virtual environment:
```bash
source venv/bin/activate
streamlit run app.py
```

Open your browser at: **`http://localhost:8501`**

---

## 🔌 Connecting Broker APIs (Zerodha Kite / Dhan / Fyers)

The app comes with a built-in modular adapter interface in `data/broker_provider.py`. To stream sub-second tick feeds from your personal broker:

1. Open the sidebar in the app and expand **"Connect Broker API"**.
2. Enter your API Key and Access Token / Secret.
3. The adapter in `data/broker_provider.py` can be easily configured with your broker SDK (`kiteconnect`, `dhanhq`, `fyers-api-v3`).
