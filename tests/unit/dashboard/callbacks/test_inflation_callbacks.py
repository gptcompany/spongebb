from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from dash import Dash

from liquidity.dashboard.callbacks.inflation_callbacks import (
    _fetch_inflation_data_async,
    register_inflation_callbacks,
    update_inflation_panel_logic,
)


@pytest.fixture
def app():
    return Dash(__name__)


def test_register_inflation_callbacks(app):
    register_inflation_callbacks(app)
    assert len(app.callback_map) > 0


@pytest.mark.asyncio
@patch("importlib.util.find_spec")
async def test_fetch_inflation_data_async_success(mock_find_spec):
    mock_find_spec.return_value = True

    # Mock RealRatesAnalyzer
    mock_analyzer = MagicMock()
    mock_df = pd.DataFrame({
        "bei_10y": [2.5],
        "bei_5y": [2.4],
        "forward_5y5y": [2.6],
        "tips_10y": [1.5],
        "tips_5y": [1.4]
    })
    mock_analyzer.calculate_breakeven = AsyncMock(return_value=mock_df)

    # Mock OilRealRatesAnalyzer
    mock_oil_analyzer = MagicMock()
    mock_oil_df = pd.DataFrame({"corr": [0.5]})
    mock_oil_analyzer.compute_correlation = AsyncMock(return_value=mock_oil_df)
    mock_state = MagicMock(corr_30d=0.5, regime="Bullish")
    mock_oil_analyzer.get_current_state = AsyncMock(return_value=mock_state)

    with patch("liquidity.analyzers.real_rates.RealRatesAnalyzer", return_value=mock_analyzer), \
         patch("liquidity.analyzers.oil_real_rates.OilRealRatesAnalyzer", return_value=mock_oil_analyzer):

        data = await _fetch_inflation_data_async()

        assert "breakeven_df" in data
        assert data["bei_10y"] == 2.5
        assert data["oil_corr"] == 0.5
        assert data["regime"] == "Bullish"


@patch("liquidity.dashboard.callbacks.inflation_callbacks._fetch_inflation_data")
def test_update_inflation_panel_success(mock_fetch):
    mock_fetch.return_value = {
        "breakeven_df": pd.DataFrame({"test": [1]}),
        "oil_rates_df": pd.DataFrame({"test": [1]}),
        "bei_10y": 2.5,
        "forward_5y5y": 2.6,
        "tips_10y": 1.5,
        "oil_corr": 0.5,
        "regime": "Normal"
    }

    outputs = update_inflation_panel_logic()

    # Returns 4 outputs: real_rates_fig, breakeven_fig, scatter_fig, summary
    assert len(outputs) == 4
    # Figures should be plotly dicts/objects
    assert hasattr(outputs[0], "data") or isinstance(outputs[0], dict)


@patch("liquidity.dashboard.callbacks.inflation_callbacks._fetch_inflation_data")
def test_update_inflation_panel_error(mock_fetch):
    mock_fetch.side_effect = Exception("Fetch failed")

    outputs = update_inflation_panel_logic()
    assert len(outputs) == 4
    # Summary should indicate error/unavailable
    assert "unavailable" in str(outputs[3]).lower()
