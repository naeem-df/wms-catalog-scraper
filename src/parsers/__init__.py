"""Parsers module for WMS Catalog Scraper."""

from .alert import AlertParser
from .motus import MotusParser

__all__ = ["AlertParser", "MotusParser"]
