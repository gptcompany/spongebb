import pandas as pd
import numpy as np
import pytest
from dash import html

from liquidity.dashboard.components.inflation import (
    create_inflation_panel,
    create_real_rates_chart,
    create_breakeven_chart,
    create_oil_rates_scatter,
    create_inflation_summary,
    INFLATION_CONCERN_THRESHOLD,
    DEFLATION_RISK_THRESHOLD,
)


def test_create_inflation_panel():
    panel = create_inflation_panel()
    assert panel is not None
    # Check for IDs
    body = panel.children[1] # CardBody
    tabs = body.children[0]
    assert tabs.id == "inflation-tabs"


def test_create_real_rates_chart():
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=10),
        "tips_10y": np.linspace(1.0, 1.5, 10),
        "tips_5y": np.linspace(0.8, 1.2, 10)
    })
    fig = create_real_rates_chart(df)
    assert len(fig.data) == 2 # 10Y and 5Y
    assert fig.data[0].name == "10Y TIPS"
    assert fig.data[1].name == "5Y TIPS"


def test_create_breakeven_chart():
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=10),
        "bei_10y": np.linspace(2.2, 2.4, 10),
        "bei_5y": np.linspace(2.1, 2.3, 10),
        "forward_5y5y": np.linspace(2.3, 2.5, 10)
    })
    fig = create_breakeven_chart(df)
    assert len(fig.data) == 3 # 10Y, 5Y, 5Y5Y
    assert any(shape.type == "rect" for shape in fig.layout.shapes)


def test_create_oil_rates_scatter():
    df = pd.DataFrame({
        "rates_diff": np.random.normal(0, 0.1, 50),
        "oil_ret": np.random.normal(0, 0.02, 50),
        "regime": ["normal"] * 25 + ["breakdown"] * 25
    })
    fig = create_oil_rates_scatter(df)
    # 2 regimes + 1 regression line = 3 traces
    assert len(fig.data) == 3
    assert any("R² =" in ann.text for ann in fig.layout.annotations)


def test_create_inflation_summary_thresholds():
    # Test concern color (Red)
    summary_red = create_inflation_summary(bei_10y=2.7) # > 2.5
    # Navigate to 10Y BEI span: Div -> dbc.Row -> dbc.Col -> [Small, Span]
    # Children[0] is Row, Row.children[0] is 10Y BEI Col
    bei_span = summary_red.children.children[0].children[1]
    assert bei_span.style["color"] == "#ff6b6b"
    
    # Test deflation color (Blue)
    summary_blue = create_inflation_summary(bei_10y=1.2) # < 1.5
    bei_span_blue = summary_blue.children.children[0].children[1]
    assert bei_span_blue.style["color"] == "#4dabf7"
    
    # Test normal color (Green)
    summary_green = create_inflation_summary(bei_10y=2.0)
    bei_span_green = summary_green.children.children[0].children[1]
    assert bei_span_green.style["color"] == "#00ff88"


def test_empty_data_handling():
    # All should return a valid figure or div even with None
    assert create_real_rates_chart(None) is not None
    assert create_breakeven_chart(pd.DataFrame()) is not None
    assert create_oil_rates_scatter(None) is not None
    assert create_inflation_summary(None) is not None
