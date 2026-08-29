#!/usr/bin/env bash
set -o errexit

# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install frontend dependencies and build
cd frontend
npm install
npm run build
cd ..

# 3. Create uploads directory
mkdir -p uploads

echo "Build complete!"
