#!/bin/bash
# Run the dashboard with secrets loaded from dotenvx
# Usage: ./scripts/run-dashboard.sh [--debug] [--port 8050]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Check if dotenvx is available
if ! command -v dotenvx &> /dev/null; then
    echo "Error: dotenvx not found. Install with: npm install -g @dotenvx/dotenvx"
    exit 1
fi

# Default env file location
ENV_FILE="${DOTENV_FILE:-/media/sam/1TB/.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "Warning: $ENV_FILE not found. Running without secrets."
    cd "$PROJECT_DIR" && uv run python -m liquidity.dashboard "$@"
else
    cd "$PROJECT_DIR" && dotenvx run -f "$ENV_FILE" -- uv run python -m liquidity.dashboard "$@"
fi
