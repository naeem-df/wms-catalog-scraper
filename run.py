#!/usr/bin/env python3
"""
WMS Catalog Scraper - Main Entry Point

CLI tool for running Alert and Motus catalog scrapers.
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Create Typer app
app = typer.Typer()
console = Console()


@app.command()
def scrape(
    spider: str = typer.Argument(
        "all",
        help="Spider to run: alert, motus, or all"
    ),
    headless: bool = typer.Option(
        True,
        "--headless/--no-headless",
        help="Run browser in headless mode"
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output", "-o",
        help="Output file for items (JSON, JSONL, CSV)"
    ),
):
    """
    Run catalog scraper(s).
    
    Examples:
        python run.py scrape alert
        python run.py scrape all --headless
        python run.py scrape motus -o motus_parts.json
    """
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    
    # Get Scrapy settings
    settings = get_project_settings()
    
    # Override headless mode
    if not headless:
        settings.set('PLAYWRIGHT_LAUNCH_OPTIONS', {'headless': False})
    
    # Configure output if specified
    if output:
        settings.set('FEEDS', {
            output: {
                'format': output.split('.')[-1],
                'encoding': 'utf-8',
                'store_empty': False,
            }
        })
    
    # Create crawler process
    process = CrawlerProcess(settings)
    
    # Determine which spiders to run
    spiders = []
    if spider == "all":
        spiders = ["alert", "motus"]
    else:
        spiders = [spider.lower()]
    
    # Add spiders to process
    for sp in spiders:
        process.crawl(sp)
    
    # Run
    console.print(f"\n[bold blue]Starting scraper(s): {', '.join(spiders)}[/bold blue]\n")
    process.start()
    
    console.print("\n[green]✓ Scraping complete[/green]")


@app.command()
def test_login(
    spider: str = typer.Argument(
        ...,
        help="Spider to test: alert or motus"
    ),
):
    """
    Test login to a catalog without full scrape.
    
    Opens visible browser to verify authentication works.
    
    Examples:
        python run.py test-login alert
        python run.py test-login motus
    """
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    
    settings = get_project_settings()
    
    # Force non-headless for testing
    settings.set('PLAYWRIGHT_LAUNCH_OPTIONS', {'headless': False})
    
    # Limit to just checking login
    settings.set('CLOSESPIDER_TIMEOUT', 60)  # Close after 60 seconds
    
    console.print(f"\n[bold]Testing login for {spider}...[/bold]")
    console.print("[yellow]Browser will open. Press Ctrl+C to close.[/yellow]\n")
    
    process = CrawlerProcess(settings)
    process.crawl(spider.lower())
    process.start()


@app.command()
def status():
    """
    Show last sync status from database.
    """
    import asyncpg
    
    async def get_status():
        try:
            conn = await asyncpg.connect(
                host=settings.get('DB_HOST'),
                port=settings.get('DB_PORT'),
                database=settings.get('DB_NAME'),
                user=settings.get('DB_USER'),
                password=settings.get('DB_PASSWORD'),
            )
            
            rows = await conn.fetch(
                """
                SELECT supplier, started_at, completed_at, status,
                       parts_scraped, parts_updated, error_message
                FROM catalog_sync_log
                ORDER BY started_at DESC
                LIMIT 10
                """
            )
            
            if not rows:
                console.print("[yellow]No sync logs found[/yellow]")
                return
            
            table = Table(title="Recent Sync History")
            table.add_column("Supplier", style="cyan")
            table.add_column("Started", style="dim")
            table.add_column("Status", style="bold")
            table.add_column("Scraped", justify="right")
            table.add_column("Updated", justify="right")
            table.add_column("Error")
            
            for row in rows:
                status_color = "green" if row['status'] == 'success' else "red"
                table.add_row(
                    row['supplier'].upper(),
                    str(row['started_at']),
                    f"[{status_color}]{row['status']}[/]",
                    str(row['parts_scraped'] or 0),
                    str(row['parts_updated'] or 0),
                    row['error_message'] or ""
                )
            
            console.print(table)
            
            await conn.close()
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
    
    from scrapy.utils.project import get_project_settings
    settings = get_project_settings()
    
    asyncio.run(get_status())


@app.command()
def init_db():
    """
    Initialize database tables.
    """
    import asyncpg
    
    async def init():
        from scrapy.utils.project import get_project_settings
        settings = get_project_settings()
        
        console.print("\n[bold]Initializing database tables...[/bold]\n")
        
        try:
            conn = await asyncpg.connect(
                host=settings.get('DB_HOST'),
                port=settings.get('DB_PORT'),
                database=settings.get('DB_NAME'),
                user=settings.get('DB_USER'),
                password=settings.get('DB_PASSWORD'),
            )
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS catalog_parts (
                    id SERIAL PRIMARY KEY,
                    sku VARCHAR(100) NOT NULL,
                    supplier VARCHAR(50) NOT NULL,
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
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS catalog_sync_log (
                    id SERIAL PRIMARY KEY,
                    supplier VARCHAR(50) NOT NULL,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    status VARCHAR(20),
                    parts_scraped INTEGER DEFAULT 0,
                    parts_updated INTEGER DEFAULT 0,
                    error_message TEXT
                )
            ''')
            
            console.print("[green]✓ Database tables created/verified[/green]")
            
            await conn.close()
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
    
    asyncio.run(init())


@app.command()
def install():
    """
    Install Playwright browsers.
    """
    import subprocess
    
    console.print("\n[bold]Installing Playwright browsers...[/bold]\n")
    
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        console.print("[green]✓ Playwright browsers installed[/green]")
        console.print(result.stdout)
    else:
        console.print(f"[red]Error: {result.stderr}[/red]")


if __name__ == "__main__":
    app()
