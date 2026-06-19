#!/bin/bash
# Build CymaticVisualizer.app
# Run once: bash build.sh
# Then drag CymaticVisualizer.app from dist/ to /Applications

set -e
PY=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
PIP=$PY -m pip

echo "=== Installing dependencies ==="
$PY -m pip install -r requirements.txt pyinstaller

echo "=== Building .app bundle ==="
$PY -m PyInstaller cymatic.spec --noconfirm

echo ""
echo "Done!  App is at: dist/CymaticVisualizer.app"
echo "Drag it to /Applications to install, or double-click to run."
