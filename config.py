"""Configuration settings for the odds tracker."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Application configuration."""
    
    # API Settings
    ODDS_API_KEY: str = os.getenv("ODDS_API_KEY", "YOUR_ODDS_API_KEY")
    BASE_URL: str = "https://api.the-odds-api.com/v4/sports"
    
    # Database
    DB_FILE: str = "odds.db"
    
    # Timezone
    TIMEZONE: str = "US/Eastern"
    
    # Snapshot times (24-hour format)
    MORNING_SNAPSHOT_HOUR: int = 12
    MORNING_SNAPSHOT_MINUTE: int = 30
    EVENING_SNAPSHOT_HOUR: int = 18
    EVENING_SNAPSHOT_MINUTE: int = 0
    
    # Target sportsbooks (case-insensitive matching)
    TARGET_SPORTSBOOKS: tuple = ("fanduel", "draftkings", "caesars")
    
    # Sports to track
    SPORTS: tuple = ("basketball_nba", "basketball_ncaab")
    
    # Sharp move thresholds
    SHARP_SPREAD_THRESHOLD: float = 1.5
    SHARP_TOTAL_THRESHOLD: float = 2.0


config = Config()
