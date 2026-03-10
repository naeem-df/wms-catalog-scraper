# WMS Catalog Scraper

Automated Python web scraper for Alert and Motus auto parts catalogs. Weekly sync to d3mvdb PostgreSQL.

## Quick Start

```bash
# Clone repo
git clone https://github.com/naeem-df/wms-catalog-scraper.git
cd wms-catalog-scraper

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run scraper
python src/scraper.py
```

## Configuration

See `.env.example` for required environment variables:
- `DB_HOST` - DigitalOcean PostgreSQL host
- `DB_PORT` - Database port (25060)
- `DB_NAME` - Database name (defaultdb)
- `DB_USER` - Database user
- `DB_PASSWORD` - Database password
- `ALERT_USERNAME` - Alert catalog username
- `ALERT_PASSWORD` - Alert catalog password
- `MOTUS_USERNAME` - Motus catalog username
- `MOTUS_PASSWORD` - Motus catalog password
- `TELEGRAM_BOT_TOKEN` - Telegram bot for notifications
- `TELEGRAM_CHAT_ID` - Telegram chat ID

## Schedule

Weekly sync runs every Sunday at 02:00 SAST (00:00 UTC).

## Tech Stack

- Python 3.11+
- Playwright (browser automation)
- PostgreSQL (psycopg2)
- GitHub Actions / Cron (scheduling)

## Documentation

- [Technical Specification](./TECH_SPEC.md)

## License

MIT