#!/usr/bin/env bash
set -euo pipefail

echo "Building frontend..."
cd frontend
npm ci
npm run build
cd ..

echo "Installing backend dependencies..."
cd backend
pip install -r requirements.txt

echo "Copying frontend build into backend static..."
rm -rf app/static
mkdir -p app/static
cp -r ../frontend/dist/* app/static/

echo "Build complete."
