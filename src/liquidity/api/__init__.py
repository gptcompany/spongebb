"""Global Liquidity Monitor API.

FastAPI-based REST API for liquidity metrics and regime classification.

Example usage:
    # Start the server
    uvicorn liquidity.api:app --reload

    # Or use the main function
    from liquidity.api import main
    main()

Endpoints:
    - GET /health - Health check
    - GET /liquidity/net - Net Liquidity Index
    - GET /liquidity/global - Global Liquidity Index
    - GET /regime/current - Current regime classification
    - GET /metrics/stealth-qe - Stealth QE Score
"""

from liquidity.api.server import app, main

__all__ = [
    "app",
    "main",
]
