#!/usr/bin/env python3
"""
Dashboard Panel Health Probe Script.
Inspects dashboard panel fetchers and callback helpers to report data health.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import date, datetime
from typing import Any

import pandas as pd
import plotly.graph_objects as go

# Add src to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from liquidity.dashboard.callbacks_main import (
        _fetch_dashboard_data,
        _fetch_extended_data,
        _fetch_fomc_statement_dates,
        _fetch_news_data,
        _fetch_quality_data,
    )
    from liquidity.dashboard.callbacks.eia_callbacks import _fetch_eia_data
    from liquidity.dashboard.callbacks.inflation_callbacks import _fetch_inflation_data
except ImportError as e:
    print(f"Error importing dashboard fetchers: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def json_serializable(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, pd.DataFrame):
        return f"DataFrame({len(obj)} rows)"
    if isinstance(obj, pd.Series):
        return f"Series({len(obj)} rows)"
    if isinstance(obj, go.Figure):
        return f"Figure({len(obj.data)} traces)"
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return str(obj)

def probe_panel(name: str, fetcher_func, *args, **kwargs) -> dict[str, Any]:
    """Probe a single panel's data."""
    logger.info(f"Probing panel: {name}...")
    start_time = datetime.now()
    result = {
        "panel": name,
        "status": "ok",
        "rows": 0,
        "latest_timestamp": None,
        "trace_count": 0,
        "placeholder_text": None,
        "error": None,
        "metrics_found": [],
    }

    try:
        data = fetcher_func(*args, **kwargs)
        
        # Generic data inspection
        if isinstance(data, dict):
            # Check for error signals in data
            if "error" in data and data["error"]:
                result["status"] = "broken"
                result["error"] = data["error"]
            
            # Count rows in primary DataFrames and look for metrics
            for key, val in data.items():
                if isinstance(val, pd.DataFrame):
                    result["rows"] = max(result["rows"], len(val))
                    if not val.empty and "timestamp" in val.columns:
                        ts = val["timestamp"].max()
                        if result["latest_timestamp"] is None or ts > pd.Timestamp(result["latest_timestamp"]):
                            result["latest_timestamp"] = ts.isoformat()
                elif isinstance(val, list):
                    result["rows"] = max(result["rows"], len(val))
                elif isinstance(val, (int, float, str)):
                    result["metrics_found"].append(key)

            # Specific panel inspections
            if name == "Central Bank News":
                if not data:
                    result["status"] = "degraded"
                    result["placeholder_text"] = "No news items"
            
            if name == "Extended Data":
                if "consumer_credit_metrics" in data:
                    result["metrics_found"].append("consumer_credit")
                if not data or result["rows"] == 0:
                    result["status"] = "degraded"

            if name == "FOMC Dates":
                result["rows"] = len(data)
                if not data:
                    result["status"] = "degraded"

        elif isinstance(data, list):
            result["rows"] = len(data)
            if not data:
                result["status"] = "degraded"

        # Check for fallback mode
        if os.getenv("LIQUIDITY_DASHBOARD_FORCE_FALLBACK") == "1":
            # If we are in fallback, degraded is "ok" for the test
            result["status"] = "degraded"
            result["placeholder_text"] = "Forced fallback mode"

    except Exception as e:
        result["status"] = "broken"
        result["error"] = str(e)
        logger.error(f"Panel {name} probe failed: {e}")

    result["probe_duration_ms"] = (datetime.now() - start_time).total_seconds() * 1000
    return result

def main():
    # Ensure we are in a predictable mode
    # LIQUIDITY_DASHBOARD_FORCE_FALLBACK might be set by the environment
    
    panels = [
        ("Liquidity & Regime", _fetch_dashboard_data),
        ("Extended Data", _fetch_extended_data),
        ("Central Bank News", _fetch_news_data),
        ("FOMC Dates", _fetch_fomc_statement_dates),
        ("EIA Petroleum", _fetch_eia_data),
        ("Inflation Expectations", _fetch_inflation_data),
        ("Quality Data", _fetch_quality_data),
    ]

    results = []
    for name, fetcher in panels:
        results.append(probe_panel(name, fetcher))

    # Output JSON to stdout
    print(json.dumps(results, indent=2, default=json_serializable))

    # Summary report to stderr
    logger.info("=== Probe Summary ===")
    all_ok = True
    for r in results:
        status_color = "\033[92m" if r["status"] == "ok" else ("\033[93m" if r["status"] == "degraded" else "\033[91m")
        reset_color = "\033[0m"
        logger.info(f"{r['panel']}: {status_color}{r['status']}{reset_color} ({r['rows']} rows, {r.get('probe_duration_ms', 0):.0f}ms)")
        if r["status"] == "broken":
            all_ok = False
    
    if not all_ok:
        sys.exit(1)

if __name__ == "__main__":
    main()
