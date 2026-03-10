"""Spiders package for WMS Catalog Scraper."""

from .alert import AlertSpider
from .motus import MotusSpider

__all__ = ["AlertSpider", "MotusSpider"]
