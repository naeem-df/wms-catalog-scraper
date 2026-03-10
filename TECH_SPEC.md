# WMS Catalog Scraper - Technical Specification

## Project Overview

Automated Python web scraper that syncs parts catalog data from two suppliers (Alert and Motus) to WMS GROUP's d3mvdb PostgreSQL database on DigitalOcean.

**Repository:** https://github.com/naeem-df/wms-catalog-scraper
**Frequency:** Weekly (Sunday 02:00 SAST)
**Target Database:** d3mvdb on DigitalOcean London

---

## Data Sources

### Catalog 1: Alert
- **URL:** https://web1.carparts-cat.com/default.aspx?10=7FD0A9CE5E4D41DEACA81956B6408394494004&14=4&12=1003
- **Platform:** TopMotive (carparts-cat.com)
- **Username:** MMOIABK
- **Password:** RMVW1

### Catalog 2: Motus
- **URL:** https://web1.carparts-cat.com/default.aspx (same platform, different credentials)
- **Platform:** TopMotive (carparts-cat.com)
- **Username:** MWADEER
- **Password:** KGAv29

---

## Technical Architecture

### Stack
- **Language:** Python 3.11+
- **Scraper:** Playwright (handles JavaScript, anti-bot evasion)
- **Database:** PostgreSQL (psycopg2)
- **Scheduling:** Cron (Linux) or GitHub Actions
- **Notifications:** Telegram alerts on completion/failure

### Project Structure
```
wms-catalog-scraper/
├── src/
│   ├── __init__.py
│   ├── scraper.py          # Main scraper logic
│   ├── auth.py             # Login handling
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── alert.py        # Alert catalog parser
│   │   └── motus.py        # Motus catalog parser
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py   # PostgreSQL connection
│   │   └── models.py       # Data models
│   └── utils/
│       ├── __init__.py
│       └── helpers.py      # Utility functions
├── config/
│   ├── config.yaml         # Configuration (credentials from env)
│   └── logging.yaml        # Logging configuration
├── scripts/
│   └── run_weekly.sh       # Cron script
├── tests/
│   └── test_scraper.py     # Unit tests
├── .env.example            # Environment variables template
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker container
├── docker-compose.yml      # Docker orchestration
└── README.md               # Documentation
```

---

## Database Schema

### Target Tables (d3mvdb)

#### `catalog_parts` (Main parts table)
```sql
CREATE TABLE IF NOT EXISTS catalog_parts (
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

#### `catalog_sync_log` (Sync history)
```sql
CREATE TABLE IF NOT EXISTS catalog_sync_log (
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

## Scraper Flow

### 1. Authentication
```
POST /default.aspx
- Username field
- Password field
- Store session cookies
```

### 2. Navigation
```
Browse categories → Subcategories → Product listings
```

### 3. Data Extraction
For each product:
- SKU / Part Number
- Description
- Category / Subcategory
- Brand
- OEM Number
- Cost Price
- Retail Price
- Stock Quantity

### 4. Database Update
```
- UPSERT into catalog_parts
- Log sync in catalog_sync_log
```

---

## Anti-Bot Evasion

### Playwright Configuration
- Headless mode with realistic viewport
- Random user agent rotation
- Request throttling (2-5 second delays)
- Cookie persistence
- Stealth plugin for evasion

### Rate Limiting
- Max 100 requests per minute
- Random delays between requests
- Respect robots.txt

---

## Scheduling

### Cron Configuration
```bash
# Weekly sync: Sunday 02:00 SAST (00:00 UTC)
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
      - name: Run scraper
        run: python src/scraper.py
```

---

## Error Handling

### Retry Logic
- 3 retries for failed requests
- Exponential backoff (5s, 15s, 45s)
- Log all failures

### Notifications
- Telegram message on completion
- Telegram message on failure (with error details)

---

## Security

### Credentials Storage
- Environment variables (not in code)
- `.env` file (gitignored)
- DigitalOcean secrets (for production)

### Database Access
- Connection string from environment
- Read-only during scrape, write on sync
- Transaction rollback on error

---

## Deliverables

### Phase 1: Setup (Day 1)
- [ ] Repo structure created
- [ ] Dependencies installed
- [ ] Database schema created
- [ ] Auth module working

### Phase 2: Scraper (Day 2-3)
- [ ] Alert catalog scraper
- [ ] Motus catalog scraper
- [ ] Data extraction working
- [ ] Database insertion working

### Phase 3: Automation (Day 4)
- [ ] Cron job configured
- [ ] Telegram notifications
- [ ] Error handling
- [ ] Testing complete

### Phase 4: Documentation (Day 5)
- [ ] README complete
- [ ] API documentation
- [ ] Deployment guide

---

## Success Criteria

- [ ] Both catalogs scrape successfully
- [ ] Data stored in d3mvdb
- [ ] Weekly sync runs automatically
- [ ] Telegram notifications working
- [ ] Error handling robust
- [ ] Documentation complete

---

## References

- TopMotive Platform: https://www.topmotive.eu/
- Playwright Docs: https://playwright.dev/python/
- d3mvdb Connection: DigitalOcean London (port 25060)

---

*Created: 2026-03-10*
*Author: Danny (WMS Mission Control)*