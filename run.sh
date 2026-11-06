#!/usr/bin/env bash
# Launcher script for NIFTY 50 Option Seller Radar
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"
source "$DIR/venv/bin/activate"
echo "Starting NIFTY 50 Option Seller Radar on http://localhost:8501 ..."
streamlit run app.py --server.port 8501 --server.headless true
