"""Database operations for odds tracking."""

import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Generator, Optional

import pytz

from config import config

logger = logging.getLogger(__name__)


@dataclass
class OddsSnapshot:
    """Represents a single odds snapshot."""
    timestamp: str
    snapshot_type: str  # 'morning' or 'evening'
    league: str
    game_id: str
    away_team: str
    home_team: str
    commence_time: str
    sportsbook: str
    away_spread: Optional[float]
    away_spread_price: Optional[int]
    home_spread: Optional[float]
    home_spread_price: Optional[int]
    total: Optional[float]
    over_price: Optional[int]
    under_price: Optional[int]


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections."""
    conn = sqlite3.connect(config.DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """Initialize the database schema."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Main snapshots table with more detailed data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS odds_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                snapshot_type TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                league TEXT NOT NULL,
                game_id TEXT NOT NULL,
                away_team TEXT NOT NULL,
                home_team TEXT NOT NULL,
                commence_time TEXT,
                sportsbook TEXT NOT NULL,
                away_spread REAL,
                away_spread_price INTEGER,
                home_spread REAL,
                home_spread_price INTEGER,
                total REAL,
                over_price INTEGER,
                under_price INTEGER,
                UNIQUE(snapshot_date, snapshot_type, game_id, sportsbook)
            )
        """)
        
        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshot_date_type 
            ON odds_snapshots(snapshot_date, snapshot_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sportsbook 
            ON odds_snapshots(sportsbook)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_game_id 
            ON odds_snapshots(game_id)
        """)
        
        conn.commit()
        logger.info("Database initialized successfully")


def save_snapshots(snapshots: list[OddsSnapshot]):
    """Save multiple snapshots to the database."""
    if not snapshots:
        logger.warning("No snapshots to save")
        return
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        for snapshot in snapshots:
            snapshot_date = snapshot.timestamp[:10]  # YYYY-MM-DD
            
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO odds_snapshots
                    (timestamp, snapshot_type, snapshot_date, league, game_id,
                     away_team, home_team, commence_time, sportsbook,
                     away_spread, away_spread_price, home_spread, home_spread_price,
                     total, over_price, under_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    snapshot.timestamp,
                    snapshot.snapshot_type,
                    snapshot_date,
                    snapshot.league,
                    snapshot.game_id,
                    snapshot.away_team,
                    snapshot.home_team,
                    snapshot.commence_time,
                    snapshot.sportsbook,
                    snapshot.away_spread,
                    snapshot.away_spread_price,
                    snapshot.home_spread,
                    snapshot.home_spread_price,
                    snapshot.total,
                    snapshot.over_price,
                    snapshot.under_price
                ))
            except sqlite3.IntegrityError as e:
                logger.warning(f"Duplicate snapshot: {e}")
        
        conn.commit()
        logger.info(f"Saved {len(snapshots)} snapshots")


def get_snapshots_for_date(
    date: str,
    snapshot_type: Optional[str] = None,
    sportsbooks: Optional[list[str]] = None
) -> list[dict]:
    """
    Get snapshots for a specific date.
    
    Args:
        date: Date string in YYYY-MM-DD format
        snapshot_type: Optional filter for 'morning' or 'evening'
        sportsbooks: Optional list of sportsbook names to filter
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM odds_snapshots WHERE snapshot_date = ?"
        params = [date]
        
        if snapshot_type:
            query += " AND snapshot_type = ?"
            params.append(snapshot_type)
        
        if sportsbooks:
            placeholders = ",".join("?" * len(sportsbooks))
            query += f" AND LOWER(sportsbook) IN ({placeholders})"
            params.extend([s.lower() for s in sportsbooks])
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_line_movements(
    date: str,
    sportsbooks: Optional[list[str]] = None
) -> list[dict]:
    """
    Calculate line movements between morning and evening snapshots.
    
    Returns games with the biggest spread and total movements.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Build sportsbook filter
        sportsbook_filter = ""
        params = [date, date]
        
        if sportsbooks:
            placeholders = ",".join("?" * len(sportsbooks))
            sportsbook_filter = f"AND LOWER(m.sportsbook) IN ({placeholders})"
            params.extend([s.lower() for s in sportsbooks])
        
        query = f"""
            SELECT 
                m.league,
                m.game_id,
                m.away_team,
                m.home_team,
                m.commence_time,
                m.sportsbook,
                m.away_spread AS open_spread,
                m.total AS open_total,
                m.away_spread_price AS open_spread_price,
                m.over_price AS open_over_price,
                e.away_spread AS close_spread,
                e.total AS close_total,
                e.away_spread_price AS close_spread_price,
                e.over_price AS close_over_price,
                (e.away_spread - m.away_spread) AS spread_move,
                (e.total - m.total) AS total_move,
                m.timestamp AS morning_time,
                e.timestamp AS evening_time
            FROM odds_snapshots m
            JOIN odds_snapshots e 
                ON m.game_id = e.game_id 
                AND m.sportsbook = e.sportsbook
                AND m.snapshot_date = e.snapshot_date
            WHERE m.snapshot_date = ?
                AND m.snapshot_type = 'morning'
                AND e.snapshot_type = 'evening'
                AND e.snapshot_date = ?
                {sportsbook_filter}
            ORDER BY ABS(e.away_spread - m.away_spread) DESC
        """
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_all_dates() -> list[str]:
    """Get all dates with snapshot data."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT snapshot_date 
            FROM odds_snapshots 
            ORDER BY snapshot_date DESC
        """)
        return [row[0] for row in cursor.fetchall()]


def get_snapshot_counts(date: str) -> dict:
    """Get counts of snapshots by type for a date."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT snapshot_type, COUNT(*) as count
            FROM odds_snapshots
            WHERE snapshot_date = ?
            GROUP BY snapshot_type
        """, (date,))
        return {row[0]: row[1] for row in cursor.fetchall()}


def get_odds_by_game(
    date: str,
    snapshot_type: str = "evening",
    sportsbooks: Optional[list[str]] = None
) -> list[dict]:
    """
    Get current odds grouped by game with all sportsbook lines.
    Returns data structured for cross-book comparison.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        sportsbook_filter = ""
        params = [date, snapshot_type]

        if sportsbooks:
            placeholders = ",".join("?" * len(sportsbooks))
            sportsbook_filter = f"AND LOWER(sportsbook) IN ({placeholders})"
            params.extend([s.lower() for s in sportsbooks])

        query = f"""
            SELECT
                game_id,
                league,
                away_team,
                home_team,
                commence_time,
                sportsbook,
                away_spread,
                home_spread,
                away_spread_price,
                home_spread_price,
                total,
                over_price,
                under_price,
                timestamp
            FROM odds_snapshots
            WHERE snapshot_date = ?
                AND snapshot_type = ?
                {sportsbook_filter}
            ORDER BY commence_time, game_id, sportsbook
        """

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_movement_by_book(
    date: str,
    sportsbooks: Optional[list[str]] = None
) -> list[dict]:
    """
    Get morning → evening line movements grouped by game.
    Shows each book's movement and finds the biggest differences across books.
    Returns games sorted by largest spread movement difference between books.
    """
    movements = get_line_movements(date, sportsbooks)

    if not movements:
        return []

    # Group by game
    games = {}
    for row in movements:
        game_id = row["game_id"]
        if game_id not in games:
            games[game_id] = {
                "game_id": game_id,
                "league": row["league"],
                "away_team": row["away_team"],
                "home_team": row["home_team"],
                "commence_time": row["commence_time"],
                "books": {}
            }

        games[game_id]["books"][row["sportsbook"]] = {
            "open_spread": row["open_spread"],
            "close_spread": row["close_spread"],
            "spread_move": row["spread_move"],
            "open_total": row["open_total"],
            "close_total": row["close_total"],
            "total_move": row["total_move"]
        }

    # Calculate max movement differences across books for each game
    results = []
    for game_id, game in games.items():
        books = game["books"]

        if len(books) < 2:
            continue

        # Get spread movements across books
        spread_moves = [
            (book, data["spread_move"])
            for book, data in books.items()
            if data["spread_move"] is not None
        ]

        # Get total movements across books
        total_moves = [
            (book, data["total_move"])
            for book, data in books.items()
            if data["total_move"] is not None
        ]

        # Calculate spread movement difference (max - min across books)
        spread_move_diff = 0
        max_spread_move_book = None
        min_spread_move_book = None
        max_spread_move = None
        min_spread_move = None

        if len(spread_moves) >= 2:
            spread_moves_sorted = sorted(spread_moves, key=lambda x: x[1])
            min_spread_move_book, min_spread_move = spread_moves_sorted[0]
            max_spread_move_book, max_spread_move = spread_moves_sorted[-1]
            spread_move_diff = abs(max_spread_move - min_spread_move)

        # Calculate total movement difference (max - min across books)
        total_move_diff = 0
        max_total_move_book = None
        min_total_move_book = None
        max_total_move = None
        min_total_move = None

        if len(total_moves) >= 2:
            total_moves_sorted = sorted(total_moves, key=lambda x: x[1])
            min_total_move_book, min_total_move = total_moves_sorted[0]
            max_total_move_book, max_total_move = total_moves_sorted[-1]
            total_move_diff = abs(max_total_move - min_total_move)

        # Calculate max absolute movement across all books (for sorting)
        max_abs_spread = max(
            (abs(m[1]) for m in spread_moves),
            default=0
        )
        max_abs_total = max(
            (abs(m[1]) for m in total_moves),
            default=0
        )

        results.append({
            "game_id": game_id,
            "league": game["league"],
            "away_team": game["away_team"],
            "home_team": game["home_team"],
            "commence_time": game["commence_time"],
            "books": books,
            "spread_move_diff": spread_move_diff,
            "max_spread_move": max_spread_move,
            "max_spread_move_book": max_spread_move_book,
            "min_spread_move": min_spread_move,
            "min_spread_move_book": min_spread_move_book,
            "total_move_diff": total_move_diff,
            "max_total_move": max_total_move,
            "max_total_move_book": max_total_move_book,
            "min_total_move": min_total_move,
            "min_total_move_book": min_total_move_book,
            "max_abs_spread": max_abs_spread,
            "max_abs_total": max_abs_total
        })

    # Sort by largest overall movement (spread + total combined)
    results.sort(key=lambda x: x["max_abs_spread"] + x["max_abs_total"], reverse=True)

    return results
