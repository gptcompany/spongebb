"""HTML Export functionality for the dashboard.

Provides standalone HTML export that can be opened in any browser
without requiring a running server.

VIZ-04: Dashboard exportable to standalone HTML.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import plotly.io as pio


class HTMLExporter:
    """Export dashboard charts to standalone HTML files.

    Example:
        exporter = HTMLExporter()

        # Export all figures
        figures = {
            'Net Liquidity': net_liq_fig,
            'Global Liquidity': global_liq_fig,
        }
        output_path = exporter.export_dashboard(figures)

        # Export single figure
        path = exporter.export_single_figure(fig, 'my_chart')
    """

    def __init__(self, output_dir: Path | str | None = None) -> None:
        """Initialize the HTML exporter.

        Args:
            output_dir: Directory for exported files. Defaults to 'exports/'.
        """
        self.output_dir = Path(output_dir) if output_dir else Path("exports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_dashboard(
        self,
        figures: dict[str, go.Figure],
        title: str = "Global Liquidity Monitor",
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Export all dashboard figures to a single HTML file.

        Args:
            figures: Mapping of chart names to Plotly Figure objects.
            title: Dashboard title.
            metadata: Optional metadata to include (quality score, etc.).

        Returns:
            Path to the generated HTML file.
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"liquidity_dashboard_{timestamp}.html"

        html_parts = [self._create_header(title, metadata)]

        # Add each figure
        for name, fig in figures.items():
            html_parts.append(f'<div class="chart-container">')
            html_parts.append(f'<h2>{name}</h2>')
            # Include plotlyjs only for first chart, reference for others
            include_js = "cdn" if name == list(figures.keys())[0] else False
            html_parts.append(
                pio.to_html(
                    fig,
                    full_html=False,
                    include_plotlyjs=include_js,
                    config={"displayModeBar": True, "displaylogo": False},
                )
            )
            html_parts.append("</div>")

        html_parts.append(self._create_footer())

        full_html = self._wrap_html(html_parts, title)

        output_path.write_text(full_html, encoding="utf-8")

        return output_path

    def export_single_figure(
        self,
        fig: go.Figure,
        name: str,
        title: str | None = None,
    ) -> Path:
        """Export a single figure to a standalone HTML file.

        Args:
            fig: Plotly Figure to export.
            name: Base name for the file (without extension).
            title: Optional title for the HTML page.

        Returns:
            Path to the generated HTML file.
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        safe_name = name.lower().replace(" ", "_")
        output_path = self.output_dir / f"{safe_name}_{timestamp}.html"

        # Use plotly's built-in HTML export with full plotlyjs
        pio.write_html(
            fig,
            output_path,
            include_plotlyjs="cdn",
            full_html=True,
            config={"displayModeBar": True, "displaylogo": False},
        )

        return output_path

    def _create_header(
        self,
        title: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create HTML header section.

        Args:
            title: Dashboard title.
            metadata: Optional metadata to display.

        Returns:
            HTML string for header.
        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

        metadata_html = ""
        if metadata:
            quality_score = metadata.get("quality_score", "N/A")
            if isinstance(quality_score, (int, float)):
                quality_score = f"{quality_score:.0f}%"

            stale_sources = metadata.get("stale_sources", [])
            stale_html = (
                f'<span class="warning">Stale: {", ".join(stale_sources)}</span>'
                if stale_sources
                else '<span class="success">All data fresh</span>'
            )

            metadata_html = f"""
            <div class="metadata">
                <span class="meta-item">Quality Score: <strong>{quality_score}</strong></span>
                <span class="meta-item">{stale_html}</span>
            </div>
            """

        return f"""
        <div class="header">
            <h1>{title}</h1>
            <p class="timestamp">Generated: {timestamp}</p>
            {metadata_html}
        </div>
        """

    def _create_footer(self) -> str:
        """Create HTML footer section.

        Returns:
            HTML string for footer.
        """
        year = datetime.now(UTC).year
        return f"""
        <div class="footer">
            <p>Global Liquidity Monitor - OpenBB SDK | {year}</p>
            <p class="disclaimer">
                Data for informational purposes only. Not financial advice.
            </p>
        </div>
        """

    def _wrap_html(self, parts: list[str], title: str) -> str:
        """Wrap content parts in full HTML document.

        Args:
            parts: List of HTML content strings.
            title: Page title.

        Returns:
            Complete HTML document string.
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                         'Helvetica Neue', Arial, sans-serif;
            background: #1a1a2e;
            color: #eaeaea;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #333;
        }}
        h1 {{
            color: #00ff88;
            margin: 0 0 10px 0;
            font-size: 2rem;
        }}
        h2 {{
            color: #aaa;
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
            margin-top: 0;
            font-size: 1.25rem;
        }}
        .timestamp {{
            color: #888;
            font-size: 0.9rem;
            margin: 0;
        }}
        .metadata {{
            margin-top: 15px;
            padding: 10px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            display: inline-block;
        }}
        .meta-item {{
            margin: 0 15px;
            font-size: 0.9rem;
        }}
        .success {{
            color: #00ff88;
        }}
        .warning {{
            color: #ffaa00;
        }}
        .chart-container {{
            background: rgba(255, 255, 255, 0.02);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #333;
            color: #666;
        }}
        .disclaimer {{
            font-size: 0.8rem;
            color: #555;
        }}
        /* Make Plotly charts responsive */
        .js-plotly-plot {{
            width: 100% !important;
        }}
    </style>
</head>
<body>
    {''.join(parts)}
</body>
</html>"""

    def get_export_content(
        self,
        figures: dict[str, go.Figure],
        title: str = "Global Liquidity Monitor",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Get HTML content without writing to file.

        Useful for Dash download callback which handles file creation.

        Args:
            figures: Mapping of chart names to Plotly Figure objects.
            title: Dashboard title.
            metadata: Optional metadata to include.

        Returns:
            Complete HTML document string.
        """
        html_parts = [self._create_header(title, metadata)]

        for name, fig in figures.items():
            html_parts.append('<div class="chart-container">')
            html_parts.append(f"<h2>{name}</h2>")
            include_js = "cdn" if name == list(figures.keys())[0] else False
            html_parts.append(
                pio.to_html(
                    fig,
                    full_html=False,
                    include_plotlyjs=include_js,
                    config={"displayModeBar": True, "displaylogo": False},
                )
            )
            html_parts.append("</div>")

        html_parts.append(self._create_footer())

        return self._wrap_html(html_parts, title)
