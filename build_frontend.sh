#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/frontend"
npm install
npm run build
echo "Production frontend output: frontend/dist"
