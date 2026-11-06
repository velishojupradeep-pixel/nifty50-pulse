"""
Yahoo Finance Data Provider for NIFTY 50 and Constituent Stocks.
Serves as reliable fallback for live quotes and primary provider for 20-day average volumes (RVOL).
"""

from typing import Dict, Any, Tuple, List
import pandas as pd
import yfinance as yf
from data.base import BaseDataProvider
from config import NIFTY_50_WEIGHTS, DEFAULT_NIFTY_VALUE


class YFinanceProvider(BaseDataProvider):
    """Fetches constituent data and historical volume from Yahoo Finance."""

    def __init__(self):
        self.cached_avg_volumes: Dict[str, float] = {}

    def fetch_nifty_data(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Fetches live/near-realtime quotes for NIFTY 50 and constituents via Yahoo Finance.
        """
        symbols = list(NIFTY_50_WEIGHTS.keys())
        yf_symbols = [f"{sym}.NS" for sym in symbols]
        all_tickers = yf_symbols + ["^NSEI"]

        # Batch download 5-day history for all tickers
        data = yf.download(
            tickers=" ".join(all_tickers),
            period="5d",
            interval="1d",
            group_by="ticker",
            progress=False,
            auto_adjust=False,
        )

        records = []
        nifty_meta = {
            "lastPrice": DEFAULT_NIFTY_VALUE,
            "change": 0.0,
            "pChange": 0.0,
            "previousClose": DEFAULT_NIFTY_VALUE,
        }

        # Process NIFTY index
        if "^NSEI" in data.columns.levels[0]:
            nifty_df = data["^NSEI"].dropna()
            if len(nifty_df) >= 2:
                prev_close = float(nifty_df["Close"].iloc[-2])
                last_price = float(nifty_df["Close"].iloc[-1])
                change = last_price - prev_close
                p_change = (change / prev_close) * 100.0 if prev_close else 0.0
                nifty_meta = {
                    "lastPrice": round(last_price, 2),
                    "change": round(change, 2),
                    "pChange": round(p_change, 2),
                    "previousClose": round(prev_close, 2),
                }

        # Process constituent stocks
        for sym in symbols:
            yf_sym = f"{sym}.NS"
            if yf_sym in data.columns.levels[0]:
                stock_df = data[yf_sym].dropna()
                if len(stock_df) >= 1:
                    last_price = float(stock_df["Close"].iloc[-1])
                    prev_close = (
                        float(stock_df["Close"].iloc[-2])
                        if len(stock_df) >= 2
                        else last_price
                    )
                    change = last_price - prev_close
                    p_change = (change / prev_close) * 100.0 if prev_close else 0.0
                    volume = int(stock_df["Volume"].iloc[-1])

                    records.append(
                        {
                            "symbol": sym,
                            "lastPrice": round(last_price, 2),
                            "change": round(change, 2),
                            "pChange": round(p_change, 2),
                            "volume": volume,
                            "previousClose": round(prev_close, 2),
                        }
                    )

        df = pd.DataFrame(records)
        return df, nifty_meta

    def fetch_average_volumes(self, days: int = 20) -> Dict[str, float]:
        """
        Calculates 20-day average daily volume for each NIFTY constituent.
        Cached in memory to prevent repeated slow API calls.
        """
        if self.cached_avg_volumes:
            return self.cached_avg_volumes

        symbols = list(NIFTY_50_WEIGHTS.keys())
        yf_symbols = [f"{sym}.NS" for sym in symbols]

        try:
            hist_data = yf.download(
                tickers=" ".join(yf_symbols),
                period=f"{days + 10}d",
                interval="1d",
                group_by="ticker",
                progress=False,
                auto_adjust=False,
            )

            avg_vols = {}
            for sym in symbols:
                yf_sym = f"{sym}.NS"
                if yf_sym in hist_data.columns.levels[0]:
                    vol_series = hist_data[yf_sym]["Volume"].dropna().tail(days)
                    if not vol_series.empty:
                        avg_vols[sym] = float(vol_series.mean())
                    else:
                        avg_vols[sym] = 1_000_000.0
                else:
                    avg_vols[sym] = 1_000_000.0

            self.cached_avg_volumes = avg_vols
            return avg_vols
        except Exception:
            # Fallback benchmark volumes if network fails
            return {sym: 1_500_000.0 for sym in symbols}
