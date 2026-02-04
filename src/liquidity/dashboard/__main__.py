"""Entry point for running the dashboard as a module.

Usage:
    python -m liquidity.dashboard
    python -m liquidity.dashboard --debug --port 8050
"""

import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> None:
    """Main entry point for dashboard."""
    parser = argparse.ArgumentParser(description="Global Liquidity Monitor Dashboard")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with hot-reloading",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8050,
        help="Server port (default: 8050)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Server host (default: 0.0.0.0)",
    )

    args = parser.parse_args()

    from liquidity.dashboard import run_server

    print(f"Starting Global Liquidity Monitor on http://{args.host}:{args.port}")
    run_server(debug=args.debug, port=args.port, host=args.host)


if __name__ == "__main__":
    main()
