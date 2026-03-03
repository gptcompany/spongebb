#!/bin/bash
# Write OpenBB credentials from env vars to user_settings.json
# This bridges Docker env vars to OpenBB Platform's credential system.

SETTINGS_DIR="$HOME/.openbb_platform"
SETTINGS_FILE="$SETTINGS_DIR/user_settings.json"

mkdir -p "$SETTINGS_DIR"

# Build credentials JSON from OPENBB_* env vars
python3 -c "
import json, os

creds = {}
if os.getenv('OPENBB_FRED_API_KEY'):
    creds['fred_api_key'] = os.environ['OPENBB_FRED_API_KEY']
if os.getenv('OPENBB_EIA_API_KEY'):
    creds['eia_api_key'] = os.environ['OPENBB_EIA_API_KEY']

settings = {
    'credentials': creds,
    'preferences': {},
    'defaults': {'commands': {}}
}

with open('$SETTINGS_FILE', 'w') as f:
    json.dump(settings, f, indent=4)

if creds:
    print(f'OpenBB credentials configured: {list(creds.keys())}')
else:
    print('No OpenBB credentials found in env vars')
"

# Execute the original command
exec "$@"
