#!/usr/bin/env python3
"""
WMS Catalog Scraper - Main Entry Point

Scrapes Alert and Motus auto parts catalogs and syncs to PostgreSQL.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from dotenv import load_dotenv
from loguru import logger

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import get_connection, init_db, close_pool
from src.database.models import Part, SyncLog
from src.parsers.alert import AlertParser
from src.parsers.motus import MotusParser
from src.utils.helpers import setup_logging, send_telegram_message


# Load environment variables
load_dotenv()

# Create Typer app
app = typer.Typer()
console = Console()


async def upsert_parts(parts: List[Part], supplier: str) -> int:
    """
    Insert or update parts in the database.
    
    Returns:
        Number of parts updated
    """
    if not parts:
        return 0
    
    updated_count = 0
    
    async with get_connection() as conn:
        for part in parts:
            try:
                # Try to insert, on conflict update
                result = await conn.execute(
                    """
                    INSERT INTO catalog_parts 
                    (sku, supplier, description, category, subcategory, brand, oem_number, 
                     cost_price, retail_price, stock_quantity)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (sku, supplier) DO UPDATE SET
                        description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        subcategory = EXCLUDED.subcategory,
                        brand = EXCLUDED.brand,
                        oem_number = EXCLUDED.oem_number,
                        cost_price = EXCLUDED.cost_price,
                        retail_price = EXCLUDED.retail_price,
                        stock_quantity = EXCLUDED.stock_quantity,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    part.sku, part.supplier, part.description, part.category,
                    part.subcategory, part.brand, part.oem_number,
                    part.cost_price, part.retail_price, part.stock_quantity
                )
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Error upserting part {part.sku}: {e}")
                continue
    
    return updated_count


async def log_sync(supplier: str, status: str, parts_scraped: int = 0, 
                   parts_updated: int = 0, error_message: str = None) -> int:
    """Log sync attempt to database."""
    async with get_connection() as conn:
        result = await conn.fetchrow(
            """
            INSERT INTO catalog_sync_log 
            (supplier, started_at, completed_at, status, parts_scraped, parts_updated, error_message)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            supplier, datetime.now(), datetime.now() if status in ['success', 'failed'] else None,
            status, parts_scraped, parts_updated, error_message
        )
        return result['id']


async def run_scraper(supplier: str, headless: bool = True) -> tuple[int, int]:
    """
    Run scraper for a specific supplier.
    
    Returns:
        Tuple of (parts_scraped, parts_updated)
    """
    logger.info(f"Starting {supplier} scraper...")
    
    # Initialize parser
    if supplier == "alert":
        parser = AlertParser(headless=headless)
    elif supplier == "motus":
        parser = MotusParser(headless=headless)
    else:
        raise ValueError(f"Unknown supplier: {supplier}")
    
    try:
        # Start and authenticate
        await parser.start()
        
        # Scrape all parts
        parts = await parser.scrape()
        parts_scraped = len(parts)
        
        logger.info(f"Scraped {parts_scraped} parts from {supplier}")
        
        # Save to database
        parts_updated = await upsert_parts(parts, supplier)
        
        logger.info(f"Updated {parts_updated} parts in database")
        
        # Log success
        await log_sync(
            supplier=supplier,
            status="success",
            parts_scraped=parts_scraped,
            parts_updated=parts_updated
        )
        
        return parts_scraped, parts_updated
        
    except Exception as e:
        logger.error(f"{supplier} scraper failed: {e}")
        
        # Log failure
        await log_sync(
            supplier=supplier,
            status="failed",
            error_message=str(e)
        )
        
        raise
        
    finally:
        await parser.close()


async def run_all_scrapers(headless: bool = True, suppliers: List[str] = None) -> dict:
    """
    Run all scrapers and return results.
    
    Returns:
        Dictionary with results for each supplier
    """
    suppliers = suppliers or ["alert", "motus"]
    results = {}
    
    for supplier in suppliers:
        try:
            scraped, updated = await run_scraper(supplier, headless=headless)
            results[supplier] = {
                "status": "success",
                "scraped": scraped,
                "updated": updated
            }
        except Exception as e:
            results[supplier] = {
                "status": "failed",
                "error": str(e)
            }
    
    return results


@app.command()
def scrape(
    supplier: str = typer.Option(
        "all",
        "--supplier", "-s",
        help="Supplier to scrape (alert, motus, or all)"
    ),
    headless: bool = typer.Option(
        True,
        "--headless/--no-headless",
        help="Run browser in headless mode"
    ),
    notify: bool = typer.Option(
        True,
        "--notify/--no-notify",
        help="Send Telegram notification on completion"
    )
):
    """
    Scrape catalog data from Alert and/or Motus.
    """
    # Setup logging
    setup_logging()
    
    console.print("\n[bold blue]WMS Catalog Scraper[/bold blue]\n")
    
    # Initialize database
    console.print("[yellow]Initializing database...[/yellow]")
    asyncio.run(init_db())
    
    # Determine suppliers to scrape
    suppliers = ["alert", "motus"] if supplier == "all" else [supplier.lower()]
    
    # Run scrapers
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        for sup in suppliers:
            task = progress.add_task(f"[cyan]Scraping {sup} catalog...", total=None)
            
            try:
                results = asyncio.run(run_all_scrapers(headless=headless, suppliers=[sup]))
                progress.update(task, description=f"[green]✓ {sup} complete[/green]")
            except Exception as e:
                progress.update(task, description=f"[red]✗ {sup} failed: {e}[/red]")
    
    # Get final results
    results = asyncio.run(run_all_scrapers(headless=headless, suppliers=suppliers))
    
    # Display results
    table = Table(title="Scraping Results")
    table.add_column("Supplier", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Parts Scraped", justify="right")
    table.add_column("Parts Updated", justify="right")
    
    for sup, data in results.items():
        status = "[green]Success[/green]" if data["status"] == "success" else "[red]Failed[/red]"
        scraped = str(data.get("scraped", 0))
        updated = str(data.get("updated", 0))
        table.add_row(sup.upper(), status, scraped, updated)
    
    console.print(table)
    
    # Send notification
    if notify:
        message_lines = ["<b>WMS Catalog Scraper Results</b>\n"]
        
        for sup, data in results.items():
            if data["status"] == "success":
                message_lines.append(
                    f"✅ <b>{sup.upper()}</b>: {data['scraped']} parts scraped, {data['updated']} updated"
                )
            else:
                message_lines.append(
                    f"❌ <b>{sup.upper()}</b>: Failed - {data.get('error', 'Unknown error')}"
                )
        
        asyncio.run(send_telegram_message("\n".join(message_lines)))
    
    # Close database
    asyncio.run(close_pool())


@app.command()
def test_login(supplier: str = typer.Argument(..., help="Supplier to test (alert or motus)")):
    """
    Test login to a catalog without scraping.
    """
    setup_logging()
    
    console.print(f"\n[bold]Testing login to {supplier} catalog...[/bold]\n")
    
    async def test():
        if supplier.lower() == "alert":
            parser = AlertParser(headless=False)  # Show browser for testing
        elif supplier.lower() == "motus":
            parser = MotusParser(headless=False)
        else:
            console.print(f"[red]Unknown supplier: {supplier}[/red]")
            return
        
        try:
            await parser.start()
            console.print(f"[green]✓ Successfully logged into {supplier}[/green]")
            
            # Keep browser open for inspection
            console.print("\n[yellow]Press Enter to close browser...[/yellow]")
            input()
            
        except Exception as e:
            console.print(f"[red]✗ Login failed: {e}[/red]")
        finally:
            await parser.close()
    
    asyncio.run(test())


@app.command()
def status():
    """
    Show last sync status from database.
    """
    setup_logging()
    
    async def get_status():
        await init_db()
        
        async with get_connection() as conn:
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
                status_style = "[green]" if row['status'] == 'success' else "[red]"
                table.add_row(
                    row['supplier'].upper(),
                    str(row['started_at']),
                    f"{status_style}{row['status']}[/]" if row['status'] == 'success' else f"[red]{row['status']}[/]",
                    str(row['parts_scraped']),
                    str(row['parts_updated']),
                    row['error_message'] or ""
                )
            
            console.print(table)
        
        await close_pool()
    
    asyncio.run(get_status())


@app.command()
def init():
    """
    Initialize database tables.
    """
    setup_logging()
    
    console.print("\n[bold]Initializing database tables...[/bold]\n")
    
    async def init():
        await init_db()
        console.print("[green]✓ Database tables created/verified[/green]")
        await close_pool()
    
    asyncio.run(init())


if __name__ == "__main__":
    app()
