"""Tests for HTML export functionality."""

import tempfile
from pathlib import Path

import plotly.graph_objects as go


class TestHTMLExporter:
    """Test HTML export functionality."""

    def test_exporter_init_creates_directory(self) -> None:
        """Test that exporter creates output directory."""
        from liquidity.dashboard.export import HTMLExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "test_exports"
            exporter = HTMLExporter(output_dir)

            assert exporter.output_dir == output_dir
            assert output_dir.exists()

    def test_exporter_init_default_directory(self) -> None:
        """Test that exporter uses default directory."""
        from liquidity.dashboard.export import HTMLExporter

        exporter = HTMLExporter()

        assert exporter.output_dir == Path("exports")

    def test_export_dashboard_creates_file(self) -> None:
        """Test that export_dashboard creates an HTML file."""
        from liquidity.dashboard.export import HTMLExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = HTMLExporter(tmpdir)

            # Create sample figures
            fig1 = go.Figure(go.Scatter(x=[1, 2, 3], y=[1, 2, 3], name="Test"))
            fig2 = go.Figure(go.Bar(x=[1, 2, 3], y=[1, 2, 3], name="Test2"))

            figures = {"Chart 1": fig1, "Chart 2": fig2}

            output_path = exporter.export_dashboard(figures)

            assert output_path.exists()
            assert output_path.suffix == ".html"
            assert "liquidity_dashboard_" in output_path.name

    def test_export_dashboard_with_metadata(self) -> None:
        """Test that export includes metadata."""
        from liquidity.dashboard.export import HTMLExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = HTMLExporter(tmpdir)

            fig = go.Figure(go.Scatter(x=[1, 2, 3], y=[1, 2, 3]))
            figures = {"Test Chart": fig}

            metadata = {
                "quality_score": 95,
                "stale_sources": ["source1"],
            }

            output_path = exporter.export_dashboard(figures, metadata=metadata)

            content = output_path.read_text()

            assert "95%" in content
            assert "Stale:" in content or "stale" in content.lower()

    def test_export_dashboard_html_structure(self) -> None:
        """Test that exported HTML has correct structure."""
        from liquidity.dashboard.export import HTMLExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = HTMLExporter(tmpdir)

            fig = go.Figure(go.Scatter(x=[1, 2], y=[1, 2], name="Test"))
            figures = {"Test": fig}

            output_path = exporter.export_dashboard(figures)
            content = output_path.read_text()

            # Check HTML structure
            assert "<!DOCTYPE html>" in content
            assert "<html" in content
            assert "</html>" in content
            assert "Global Liquidity Monitor" in content
            assert "Generated:" in content

    def test_export_single_figure(self) -> None:
        """Test exporting a single figure."""
        from liquidity.dashboard.export import HTMLExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = HTMLExporter(tmpdir)

            fig = go.Figure(go.Scatter(x=[1, 2, 3], y=[1, 2, 3], name="Test"))

            output_path = exporter.export_single_figure(fig, "test_chart")

            assert output_path.exists()
            assert "test_chart_" in output_path.name
            assert output_path.suffix == ".html"

    def test_get_export_content_returns_string(self) -> None:
        """Test that get_export_content returns HTML string."""
        from liquidity.dashboard.export import HTMLExporter

        exporter = HTMLExporter()

        fig = go.Figure(go.Scatter(x=[1, 2], y=[1, 2]))
        figures = {"Test": fig}

        content = exporter.get_export_content(figures)

        assert isinstance(content, str)
        assert "<!DOCTYPE html>" in content
        assert "Test" in content

    def test_export_with_custom_title(self) -> None:
        """Test exporting with custom title."""
        from liquidity.dashboard.export import HTMLExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = HTMLExporter(tmpdir)

            fig = go.Figure(go.Scatter(x=[1, 2], y=[1, 2]))
            figures = {"Test": fig}

            output_path = exporter.export_dashboard(
                figures, title="Custom Dashboard Title"
            )
            content = output_path.read_text()

            assert "Custom Dashboard Title" in content

    def test_export_file_is_standalone(self) -> None:
        """Test that exported file includes plotly.js CDN reference."""
        from liquidity.dashboard.export import HTMLExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = HTMLExporter(tmpdir)

            fig = go.Figure(go.Scatter(x=[1, 2], y=[1, 2]))
            figures = {"Test": fig}

            output_path = exporter.export_dashboard(figures)
            content = output_path.read_text()

            # Should include CDN reference for standalone viewing
            assert "plotly" in content.lower()
            assert "cdn.plot.ly" in content or "plotlyjs" in content.lower()

    def test_export_empty_figures_dict(self) -> None:
        """Test exporting with empty figures dict."""
        from liquidity.dashboard.export import HTMLExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = HTMLExporter(tmpdir)

            output_path = exporter.export_dashboard({})

            assert output_path.exists()
            content = output_path.read_text()
            assert "<!DOCTYPE html>" in content

    def test_export_preserves_dark_theme(self) -> None:
        """Test that export preserves dark theme styling."""
        from liquidity.dashboard.export import HTMLExporter

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = HTMLExporter(tmpdir)

            fig = go.Figure(go.Scatter(x=[1, 2], y=[1, 2]))
            figures = {"Test": fig}

            output_path = exporter.export_dashboard(figures)
            content = output_path.read_text()

            # Check for dark theme colors in CSS
            assert "#1a1a2e" in content or "dark" in content.lower()
            assert "#00ff88" in content  # Green accent color
