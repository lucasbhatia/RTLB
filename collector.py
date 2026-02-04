"""Snapshot collector for odds data."""

import logging
from datetime import datetime
from typing import Optional

import pytz

from config import config
from database import OddsSnapshot, init_database, save_snapshots
from odds_api import OddsAPIClient, OddsAPIError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

EST = pytz.timezone(config.TIMEZONE)


def get_snapshot_type(now: Optional[datetime] = None) -> Optional[str]:
    """
    Determine the snapshot type based on current time.
    
    Returns:
        'morning' if around 12:30 PM EST
        'evening' if around 6:00 PM EST
        None if outside snapshot windows
    """
    now = now or datetime.now(EST)
    hour, minute = now.hour, now.minute
    
    # Morning window: 12:00 PM - 1:00 PM
    if 12 <= hour < 13:
        return "morning"
    
    # Evening window: 5:30 PM - 6:30 PM
    if (hour == 17 and minute >= 30) or (hour == 18 and minute < 30):
        return "evening"
    
    return None


def is_target_sportsbook(name: str) -> bool:
    """Check if a sportsbook is one we want to track."""
    name_lower = name.lower()
    return any(target in name_lower for target in config.TARGET_SPORTSBOOKS)


def parse_game_odds(game: dict, snapshot_type: str, timestamp: str) -> list[OddsSnapshot]:
    """
    Parse a game's odds data into snapshot objects.
    
    Args:
        game: Raw game data from API
        snapshot_type: 'morning' or 'evening'
        timestamp: ISO format timestamp
        
    Returns:
        List of OddsSnapshot objects for target sportsbooks
    """
    snapshots = []
    
    bookmakers = game.get("bookmakers", [])
    if not bookmakers:
        return snapshots
    
    game_id = game.get("id", "")
    league = game.get("sport_key", "")
    away_team = game.get("away_team", "")
    home_team = game.get("home_team", "")
    commence_time = game.get("commence_time", "")
    
    for book in bookmakers:
        book_name = book.get("title", "")
        
        if not is_target_sportsbook(book_name):
            continue
        
        markets = {m["key"]: m for m in book.get("markets", [])}
        
        # Parse spreads
        spreads_market = markets.get("spreads", {})
        spreads = spreads_market.get("outcomes", [])
        
        away_spread = away_spread_price = home_spread = home_spread_price = None
        
        for outcome in spreads:
            if outcome.get("name") == away_team:
                away_spread = outcome.get("point")
                away_spread_price = outcome.get("price")
            elif outcome.get("name") == home_team:
                home_spread = outcome.get("point")
                home_spread_price = outcome.get("price")
        
        # Parse totals
        totals_market = markets.get("totals", {})
        totals = totals_market.get("outcomes", [])
        
        total = over_price = under_price = None
        
        for outcome in totals:
            if outcome.get("name") == "Over":
                total = outcome.get("point")
                over_price = outcome.get("price")
            elif outcome.get("name") == "Under":
                under_price = outcome.get("price")
        
        snapshot = OddsSnapshot(
            timestamp=timestamp,
            snapshot_type=snapshot_type,
            league=league,
            game_id=game_id,
            away_team=away_team,
            home_team=home_team,
            commence_time=commence_time,
            sportsbook=book_name,
            away_spread=away_spread,
            away_spread_price=away_spread_price,
            home_spread=home_spread,
            home_spread_price=home_spread_price,
            total=total,
            over_price=over_price,
            under_price=under_price
        )
        
        snapshots.append(snapshot)
    
    return snapshots


def collect_snapshot(snapshot_type: Optional[str] = None, force: bool = False):
    """
    Collect and save odds snapshot.
    
    Args:
        snapshot_type: Override automatic type detection ('morning' or 'evening')
        force: Force collection even if outside time window
    """
    now = datetime.now(EST)
    
    # Determine snapshot type
    if snapshot_type is None:
        snapshot_type = get_snapshot_type(now)
        
        if snapshot_type is None and not force:
            logger.info(f"Outside snapshot window. Current time: {now.strftime('%I:%M %p %Z')}")
            return
    
    if snapshot_type not in ("morning", "evening"):
        logger.error(f"Invalid snapshot type: {snapshot_type}")
        return
    
    logger.info(f"Collecting {snapshot_type} snapshot at {now.strftime('%Y-%m-%d %I:%M %p %Z')}")
    
    # Initialize database
    init_database()
    
    # Fetch odds
    client = OddsAPIClient()
    
    try:
        all_games = client.fetch_all_sports()
    except OddsAPIError as e:
        logger.error(f"Failed to fetch odds: {e}")
        return
    
    if not all_games:
        logger.warning("No games returned from API")
        return
    
    # Parse and save snapshots
    timestamp = now.isoformat()
    all_snapshots = []
    
    for game in all_games:
        snapshots = parse_game_odds(game, snapshot_type, timestamp)
        all_snapshots.extend(snapshots)
    
    if all_snapshots:
        save_snapshots(all_snapshots)
        logger.info(f"Collected {len(all_snapshots)} snapshots for {len(all_games)} games")
    else:
        logger.warning("No target sportsbook data found")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Collect odds snapshots")
    parser.add_argument(
        "--type", "-t",
        choices=["morning", "evening"],
        help="Force specific snapshot type"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force collection even outside time window"
    )
    
    args = parser.parse_args()
    
    collect_snapshot(snapshot_type=args.type, force=args.force)


if __name__ == "__main__":
    main()
