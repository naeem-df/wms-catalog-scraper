# WMS Catalog Scraper

Automated Python web scraper for Alert and Motus auto parts catalogs. Weekly sync to d3mvdb PostgreSQL using Scrapy + scrapy-playwright.

## Architecture

| Layer | Tool | Role |
|-------|------|------|
| Crawl scheduler | Scrapy + scrapy-playwright for production-grade crawling with JavaScript rendering.

**Repository:** https://github.com/naeem-df/wms-catalog-scraper
**Frequency:** Weekly (Sunday 02:00 SAST)
**Target Database:** PostgreSQL on DigitalOcean London

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Scrapy        │────▶│  scrapy-playwright│────▶│   PostgreSQL    │
│   Scheduler     │     │  (JS Rendering)   │     │   Database      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │                        │
        ▼                        ▼                        ▼
   Request Queue          Browser Context          Data Pipeline
   Retry Logic            Anti-Bot Evasion         UPSERT Logic
   Concurrency            Cookie Management        Sync Logging
```

### Stack

| Layer | Tool | Purpose |
|-------|------|---------|
| Crawl Scheduler | Scrapy | Request queuing, retries, concurrency |
| Browser Rendering | scrapy-playwright | JavaScript rendering, anti-bot evasion |
| Parser | Scrapy Spiders | Data extraction from HTML |
| Pipeline | Scrapy Pipeline | PostgreSQL storage, deduplication |
| CLI | Typer + Rich | User interface |
| Notifications | Telegram API | Completion/failure alerts |

---

## Quick Start

```bash
# Clone repo
git clone https://github.com/naeem-df/wms-catalog-scraper.git
cd wms-catalog-scraper

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium --with-deps

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Initialize database tables
python run.py init-db

# Test login (opens visible browser)
python run.py test-login alert

# Run scraper
python run.py scrape all --headless
```

---

## Commands

### `scrape` - Run Scrapers

```bash
# Scrape both catalogs
python run.py scrape all

# Scrape specific catalog
python run.py scrape alert
python run.py scrape motus

# Run with visible browser (debugging)
python run.py scrape alert --no-headless

# Output to file
python run.py scrape all -o catalog_parts.json
```

### `test-login` - Test Authentication

```bash
# Test Alert login (opens browser)
python run.py test-login alert

# Test Motus login
python run.py test-login motus
```

### `status` - View Sync History

```bash
python run.py status
```

### `init-db` - Initialize Database

```bash
python run.py init-db
```

### `install` - Install Playwright Browsers

```bash
python run.py install
```

---

## Configuration

### Environment Variables (`.env`)

```bash
# Database Configuration
DB_HOST=lon1-sparescentre-do-user-13257464-0.b.db.ondigitalocean.com
DB_PORT=25060
DB_NAME=defaultdb
DB_USER=doadmin
DB_PASSWORD=your_password_here

# Alert Catalog Credentials
ALERT_USERNAME=MMOIABK
ALERT_PASSWORD=RMVW1

# Motus Catalog Credentials
MOTUS_USERNAME=MWADEER
MOTUS_PASSWORD=KGAv29

# Telegram Notifications (Optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Scraper Settings
SCRAPER_HEADLESS=true
SCRAPER_DELAY_MIN=2
SCRAPER_DELAY_MAX=5
```

### Scrapy Settings (`wms_scraper/settings.py`)

Key settings:

| Setting | Value | Purpose |
|---------|-------|---------|
| `CONCURRENT_REQUESTS` | 4 | Max parallel requests |
| `DOWNLOAD_DELAY` | 2s | Base delay between requests |
| `PLAYWRIGHT_BROWSER_TYPE` | chromium | Browser engine |
| `PLAYWRIGHT_LAUNCH_OPTIONS.headless` | true | Headless mode |

---

## Database Schema

### `catalog_parts`

```sql
CREATE TABLE catalog_parts (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(100) NOT NULL,
    supplier VARCHAR(50) NOT NULL,  -- 'alert' or 'motus'
    description TEXT,
    category VARCHAR(100),
    subcategory VARCHAR(100),
    brand VARCHAR(100),
    oem_number VARCHAR(100),
    cost_price DECIMAL(10, 2),
    retail_price DECIMAL(10, 2),
    stock_quantity INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sku, supplier)
);
```

### `catalog_sync_log`

```sql
CREATE TABLE catalog_sync_log (
    id SERIAL PRIMARY KEY,
    supplier VARCHAR(50) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR(20),  -- 'running', 'success', 'failed'
    parts_scraped INTEGER DEFAULT 0,
    parts_updated INTEGER DEFAULT 0,
    error_message TEXT
);
```

---

## Scheduling

### Cron (Linux)

```bash
# Edit crontab
crontab -e

# Add entry for weekly run (Sunday 02:00 SAST = 00:00 UTC)
0 0 * * 0 /opt/wms-catalog-scraper/scripts/run_weekly.sh
```

### GitHub Actions (Alternative)

```yaml
name: Weekly Catalog Sync
on:
  schedule:
    - cron: '0 0 * * 0'  # Sunday 00:00 UTC
  workflow_dispatch:

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install chromium --with-deps
      
      - name: Run scraper
        env:
          DB_HOST: ${{ secrets.DB_HOST }}
          DB_PORT: ${{ secrets.DB_PORT }}
          DB_NAME: ${{ secrets.DB_NAME }}
          DB_USER: ${{ secrets.DB_USER }}
          DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
          ALERT_USERNAME: ${{ secrets.ALERT_USERNAME }}
          ALERT_PASSWORD: ${{ secrets.ALERT_PASSWORD }}
          MOTUS_USERNAME: ${{ secrets.MOTUS_USERNAME }}
          MOTUS_PASSWORD: ${{ secrets.MOTUS_PASSWORD }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python run.py scrape all --headless
```

---

## Anti-Bot Evasion

The scraper uses multiple techniques to evade detection:

1. **Realistic User Agent** - Rotating Chrome user agents
2. **Random Delays** - 2-5 second delays between requests
3. **Browser Fingerprint** - Hiding automation markers
4. **Context Isolation** - Separate browser contexts per session
5. **Cookie Persistence** - Maintaining session state

```javascript
// Anti-detection scripts injected into browser
navigator.webdriver = undefined
window.chrome = { runtime: {} }
```

---

## Project Structure

```
wms-catalog-scraper/
├── wms_scraper/
│   ├── __init__.py
│   ├── settings.py          # Scrapy settings
│   ├── items.py             # Data models
│   ├── middlewares.py       # Request/response middleware
│   ├── pipelines.py         # Database pipeline
│   └── spiders/
│       ├── __init__.py
│       ├── alert.py         # Alert catalog spider
│       └── motus.py         # Motus catalog spider
├── config/
│   └── config.yaml          # Configuration
├── scripts/
│   ├── run_weekly.sh        # Cron script
│   └── install_dependencies.sh
├── tests/
│   └── test_scraper.py
├── logs/                    # Log files
├── .env                     # Environment variables
├── .env.example             # Template
├── scrapy.cfg               # Scrapy config
├── run.py                   # CLI entry point
├── requirements.txt         # Dependencies
├── TECH_SPEC.md             # Technical specification
└── README.md                # This file
```

---

## Troubleshooting

### Login Issues

```bash
# Test with visible browser
python run.py test-login alert

# Check screenshots in /tmp
ls /tmp/*login*.png
```

### Database Connection Issues

```bash
# Test connection
python -c "
import asyncpg
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

async def test():
    conn = await asyncpg.connect(
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT')),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
    )
    print('✓ Connected successfully')
    await conn.close()

asyncio.run(test())
"
```

### Playwright Issues

```bash
# Reinstall browsers
playwright install chromium --with-deps

# Check browser
playwright --help
```

---

## Monitoring

### Telegram Notifications

On completion, the scraper sends a message like:

```
WMS Catalog Scraper Results

✅ ALERT: 1,234 parts scraped, 890 updated
✅ MOTUS: 567 parts scraped, 234 updated
```

### Sync Log

Query sync history:

```sql
SELECT * FROM catalog_sync_log 
ORDER BY started_at DESC 
LIMIT 10;
```

---

## References

- [Scrapy Documentation](https://docs.scrapy.org/)
- [scrapy-playwright](https://github.com/scrapy-plugins/scrapy-playwright)
- [Playwright Python](https://playwright.dev/python/)
- [TopMotive Platform](https://www.topmotive.eu/)

---

*Created: 2026-03-10*
*Author: Danny (WMS Mission Control)*
*Issue: #1*
