"""Tests for sanity bounds component."""

import plotly.graph_objects as go


class TestSanityBounds:
    """Test SanityBounds class."""

    def test_bounds_defined(self) -> None:
        """Test that bounds are defined for expected metrics."""
        from liquidity.dashboard.components.bounds import SanityBounds

        expected_metrics = [
            "net_liquidity",
            "global_liquidity",
            "dxy",
            "vix",
            "move",
            "sofr",
            "gold",
            "copper",
        ]

        for metric in expected_metrics:
            assert metric in SanityBounds.BOUNDS

    def test_get_bounds(self) -> None:
        """Test getting bounds for a metric."""
        from liquidity.dashboard.components.bounds import SanityBounds

        bounds = SanityBounds.get_bounds("net_liquidity")

        assert bounds is not None
        assert len(bounds) == 2
        low, high = bounds
        assert low < high
        assert low == 4.5e12
        assert high == 7.0e12

    def test_get_bounds_unknown_metric(self) -> None:
        """Test getting bounds for unknown metric."""
        from liquidity.dashboard.components.bounds import SanityBounds

        bounds = SanityBounds.get_bounds("unknown_metric")

        assert bounds is None

    def test_is_outside_bounds_normal(self) -> None:
        """Test is_outside_bounds with value in range."""
        from liquidity.dashboard.components.bounds import SanityBounds

        # DXY normal range: 90-115
        assert not SanityBounds.is_outside_bounds("dxy", 100)
        assert not SanityBounds.is_outside_bounds("dxy", 90)  # At lower bound
        assert not SanityBounds.is_outside_bounds("dxy", 115)  # At upper bound

    def test_is_outside_bounds_below(self) -> None:
        """Test is_outside_bounds with value below range."""
        from liquidity.dashboard.components.bounds import SanityBounds

        assert SanityBounds.is_outside_bounds("dxy", 85)
        assert SanityBounds.is_outside_bounds("vix", 5)

    def test_is_outside_bounds_above(self) -> None:
        """Test is_outside_bounds with value above range."""
        from liquidity.dashboard.components.bounds import SanityBounds

        assert SanityBounds.is_outside_bounds("dxy", 120)
        assert SanityBounds.is_outside_bounds("vix", 90)

    def test_is_outside_bounds_unknown_metric(self) -> None:
        """Test is_outside_bounds with unknown metric."""
        from liquidity.dashboard.components.bounds import SanityBounds

        # Unknown metrics should return False (assume in bounds)
        assert not SanityBounds.is_outside_bounds("unknown", 100)


class TestBoundStatus:
    """Test bound status functionality."""

    def test_get_bound_status_normal(self) -> None:
        """Test get_bound_status for normal values."""
        from liquidity.dashboard.components.bounds import BoundStatus, SanityBounds

        status = SanityBounds.get_bound_status("dxy", 100)

        assert status == BoundStatus.NORMAL

    def test_get_bound_status_below(self) -> None:
        """Test get_bound_status for below-normal values."""
        from liquidity.dashboard.components.bounds import BoundStatus, SanityBounds

        status = SanityBounds.get_bound_status("dxy", 85)

        assert status == BoundStatus.BELOW_NORMAL

    def test_get_bound_status_above(self) -> None:
        """Test get_bound_status for above-normal values."""
        from liquidity.dashboard.components.bounds import BoundStatus, SanityBounds

        status = SanityBounds.get_bound_status("dxy", 120)

        assert status == BoundStatus.ABOVE_NORMAL

    def test_get_bound_status_unknown(self) -> None:
        """Test get_bound_status for unknown metric."""
        from liquidity.dashboard.components.bounds import BoundStatus, SanityBounds

        status = SanityBounds.get_bound_status("unknown", 100)

        assert status == BoundStatus.UNKNOWN


class TestAddBounds:
    """Test adding bounds to charts."""

    def test_add_bounds_to_figure(self) -> None:
        """Test adding bounds to a Plotly figure."""
        from liquidity.dashboard.components.bounds import SanityBounds

        fig = go.Figure(go.Scatter(x=[1, 2, 3], y=[100, 105, 110]))

        result = SanityBounds.add_bounds(fig, "dxy")

        assert result is not None
        # Figure should have shapes (hrect) added
        assert hasattr(result.layout, "shapes")
        # Should have at least 2 shapes (the band and the lines)

    def test_add_bounds_unknown_metric(self) -> None:
        """Test adding bounds for unknown metric returns unchanged figure."""
        from liquidity.dashboard.components.bounds import SanityBounds

        fig = go.Figure(go.Scatter(x=[1, 2, 3], y=[1, 2, 3]))
        original_shapes = len(fig.layout.shapes) if fig.layout.shapes else 0

        result = SanityBounds.add_bounds(fig, "unknown_metric")

        assert result is fig  # Same figure returned
        new_shapes = len(result.layout.shapes) if result.layout.shapes else 0
        assert new_shapes == original_shapes

    def test_add_bounds_with_annotation(self) -> None:
        """Test adding bounds with annotation label."""
        from liquidity.dashboard.components.bounds import SanityBounds

        fig = go.Figure(go.Scatter(x=[1, 2, 3], y=[5, 5.5, 6]))

        result = SanityBounds.add_bounds(fig, "vix", show_annotation=True)

        # Should have annotation
        assert result.layout.shapes is not None

    def test_add_bounds_without_annotation(self) -> None:
        """Test adding bounds without annotation."""
        from liquidity.dashboard.components.bounds import SanityBounds

        fig = go.Figure(go.Scatter(x=[1, 2, 3], y=[5, 5.5, 6]))

        result = SanityBounds.add_bounds(fig, "vix", show_annotation=False)

        assert result is not None


class TestAddBoundsWithAlertZones:
    """Test adding bounds with color-coded alert zones."""

    def test_add_alert_zones(self) -> None:
        """Test adding alert zone bands to figure."""
        from liquidity.dashboard.components.bounds import SanityBounds

        fig = go.Figure(go.Scatter(x=[1, 2, 3], y=[100, 105, 110]))

        result = SanityBounds.add_bounds_with_alert_zones(fig, "dxy")

        assert result is not None
        # Should have multiple shapes for different zones
        assert hasattr(result.layout, "shapes")

    def test_add_alert_zones_unknown_metric(self) -> None:
        """Test adding alert zones for unknown metric."""
        from liquidity.dashboard.components.bounds import SanityBounds

        fig = go.Figure(go.Scatter(x=[1, 2, 3], y=[1, 2, 3]))

        result = SanityBounds.add_bounds_with_alert_zones(fig, "unknown")

        assert result is fig


class TestBoundInfo:
    """Test BoundInfo data class."""

    def test_get_bound_info(self) -> None:
        """Test getting full bound info."""
        from liquidity.dashboard.components.bounds import SanityBounds

        info = SanityBounds.get_bound_info("net_liquidity")

        assert info is not None
        assert info.low == 4.5e12
        assert info.high == 7.0e12
        assert info.unit == "$"
        assert "Net Liquidity" in info.description

    def test_get_bound_info_unknown(self) -> None:
        """Test getting bound info for unknown metric."""
        from liquidity.dashboard.components.bounds import SanityBounds

        info = SanityBounds.get_bound_info("unknown")

        assert info is None


class TestFormatBoundStatus:
    """Test formatted bound status for UI display."""

    def test_format_normal_status(self) -> None:
        """Test formatting for normal status."""
        from liquidity.dashboard.components.bounds import SanityBounds

        result = SanityBounds.format_bound_status("dxy", 100)

        assert result["status"] == "normal"
        assert result["is_normal"] is True
        assert result["metric"] == "dxy"
        assert result["value"] == 100
        assert result["delta"] == 0

    def test_format_below_normal_status(self) -> None:
        """Test formatting for below-normal status."""
        from liquidity.dashboard.components.bounds import SanityBounds

        result = SanityBounds.format_bound_status("dxy", 85)

        assert result["status"] == "below_normal"
        assert result["is_normal"] is False
        assert result["delta"] < 0  # Below the low bound
        assert "delta_pct" in result

    def test_format_above_normal_status(self) -> None:
        """Test formatting for above-normal status."""
        from liquidity.dashboard.components.bounds import SanityBounds

        result = SanityBounds.format_bound_status("dxy", 120)

        assert result["status"] == "above_normal"
        assert result["is_normal"] is False
        assert result["delta"] > 0  # Above the high bound

    def test_format_without_delta(self) -> None:
        """Test formatting without delta calculation."""
        from liquidity.dashboard.components.bounds import SanityBounds

        result = SanityBounds.format_bound_status("dxy", 85, include_delta=False)

        assert "delta" not in result


class TestGetAllMetrics:
    """Test getting all defined metrics."""

    def test_get_all_metrics(self) -> None:
        """Test that all metrics list is returned."""
        from liquidity.dashboard.components.bounds import SanityBounds

        metrics = SanityBounds.get_all_metrics()

        assert isinstance(metrics, list)
        assert len(metrics) > 0
        assert "net_liquidity" in metrics
        assert "dxy" in metrics
        assert "vix" in metrics
