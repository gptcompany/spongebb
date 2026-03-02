import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import pandas as pd
from dash import Dash

from liquidity.dashboard.callbacks.eia_callbacks import (
    register_eia_callbacks,
    update_eia_panel_logic,
    _fetch_eia_data_async,
)


@pytest.fixture
def app():
    return Dash(__name__)


def test_register_eia_callbacks(app):
    register_eia_callbacks(app)
    # Just verify it doesn't crash and adds something to callback_map
    assert len(app.callback_map) > 0


@pytest.mark.asyncio
@patch("importlib.util.find_spec")
async def test_fetch_eia_data_async_success(mock_find_spec):
    mock_find_spec.return_value = True
    
    # Mock EIACollector
    mock_collector = MagicMock()
    mock_df = pd.DataFrame({
        "timestamp": ["2024-01-01"],
        "value": [25000.0]
    })
    mock_collector.collect_cushing = AsyncMock(return_value=mock_df)
    mock_collector.collect_refinery_utilization = AsyncMock(return_value=mock_df)
    mock_collector.collect_production = AsyncMock(return_value=mock_df)
    mock_collector.collect_imports = AsyncMock(return_value=mock_df)
    mock_collector.calculate_utilization_signal = MagicMock(return_value="Bullish")
    mock_collector.close = AsyncMock()
    
    with patch("liquidity.collectors.eia.EIACollector", return_value=mock_collector), \
         patch("liquidity.collectors.eia.CUSHING_CAPACITY_KB", 76000):
        
        data = await _fetch_eia_data_async()
        
        assert "cushing_df" in data
        assert "cushing_utilization_pct" in data
        assert data["refinery_signal"] == "Bullish"
        assert "production_df" in data
        assert "imports_df" in data


@patch("liquidity.dashboard.callbacks.eia_callbacks._fetch_eia_data")
def test_update_eia_panel_success(mock_fetch):
    mock_fetch.return_value = {
        "cushing_df": pd.DataFrame({"test": [1]}),
        "cushing_utilization_pct": 33.0,
        "refinery_df": pd.DataFrame({"test": [1]}),
        "refinery_signal": "Bullish",
        "production_df": pd.DataFrame({"test": [1]}),
        "imports_df": pd.DataFrame({"test": [1]})
    }
    
    outputs = update_eia_panel_logic()
    
    # Returns 6 outputs: cushing_fig, cushing_badge, refinery_fig, refinery_badge, production_fig, imports_fig
    assert len(outputs) == 6
    assert data_in_fig(outputs[0])
    assert "33.0%" in str(outputs[1])


def data_in_fig(fig):
    """Utility to check if fig has data."""
    return hasattr(fig, "data") or (isinstance(fig, dict) and "data" in fig)


@patch("liquidity.dashboard.callbacks.eia_callbacks._fetch_eia_data")
def test_update_eia_panel_error(mock_fetch):
    mock_fetch.side_effect = Exception("Fetch failed")
    
    outputs = update_eia_panel_logic()
    assert len(outputs) == 6
    # Badges should indicate data unavailable
    assert "--" in str(outputs[1])
    assert "--" in str(outputs[3])
