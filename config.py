"""Configuration settings for the odds tracker."""

import os
from dataclasses import dataclass


def get_api_key():
    """Get API key from environment or Streamlit secrets."""
    # First try environment variable
    key = os.getenv("ODDS_API_KEY")
    if key and key != "YOUR_ODDS_API_KEY":
        return key

    # Then try Streamlit secrets
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and "ODDS_API_KEY" in st.secrets:
            return st.secrets["ODDS_API_KEY"]
    except Exception:
        pass

    return "YOUR_ODDS_API_KEY"


def get_db_path():
    """Get database path - uses Railway volume if available."""
    # Check if running on Railway with a volume
    railway_volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if railway_volume:
        # Ensure directory exists
        os.makedirs(railway_volume, exist_ok=True)
        return os.path.join(railway_volume, "odds.db")

    # Local development
    return "odds.db"


@dataclass(frozen=True)
class Config:
    """Application configuration."""

    # API Settings
    ODDS_API_KEY: str = get_api_key()
    BASE_URL: str = "https://api.the-odds-api.com/v4/sports"

    # Database - uses persistent volume on Railway
    DB_FILE: str = get_db_path()
    
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
