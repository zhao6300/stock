#!/usr/bin/env bash
set -euo pipefail

echo "Installing required Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
