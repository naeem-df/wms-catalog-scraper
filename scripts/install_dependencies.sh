#!/bin/bash
#
# Setup script for WMS Catalog Scraper
#

set -e

echo "=========================================="
echo "WMS Catalog Scraper - Setup"
echo "=========================================="

# Navigate to project directory
cd "$(dirname "$0")/.."

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers
echo "Installing Playwright browsers..."
playwright install chromium

# Create log directory
echo "Creating log directory..."
mkdir -p logs

# Create .env from example if not exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "Please edit .env with your credentials"
fi

echo "=========================================="
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your credentials"
echo "2. Run: python -m src.scraper init"
echo "3. Test: python -m src.scraper test-login alert"
echo "4. Run: python -m src.scraper scrape"
echo "=========================================="
