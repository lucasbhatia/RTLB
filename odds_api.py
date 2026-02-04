"""Client for The Odds API with error handling and retry logic."""

import logging
import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import config

logger = logging.getLogger(__name__)


class OddsAPIError(Exception):
    """Custom exception for Odds API errors."""
    pass


class OddsAPIClient:
    """Client for fetching odds from The Odds API."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.ODDS_API_KEY
        self.base_url = config.BASE_URL
        self.session = self._create_session()
        
        if self.api_key == "YOUR_ODDS_API_KEY":
            logger.warning("Using placeholder API key. Set ODDS_API_KEY environment variable.")
    
    def _create_session(self) -> requests.Session:
        """Create a session with retry logic."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session
    
    def fetch_odds(
        self,
        sport_key: str,
        markets: str = "spreads,totals",
        bookmakers: Optional[list[str]] = None
    ) -> list[dict]:
        """
        Fetch odds for a specific sport.
        
        Args:
            sport_key: Sport identifier (e.g., 'basketball_nba')
            markets: Comma-separated market types
            bookmakers: Optional list of specific bookmakers to fetch
            
        Returns:
            List of game odds data
        """
        url = f"{self.base_url}/{sport_key}/odds"
        
        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "markets": markets,
            "oddsFormat": "american"
        }
        
        if bookmakers:
            params["bookmakers"] = ",".join(bookmakers)
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            
            # Log remaining API requests
            remaining = response.headers.get("x-requests-remaining", "unknown")
            logger.info(f"API requests remaining: {remaining}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching odds for {sport_key}")
            raise OddsAPIError(f"Timeout fetching odds for {sport_key}")
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching odds: {e}")
            raise OddsAPIError(f"HTTP error: {e}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching odds: {e}")
            raise OddsAPIError(f"Request error: {e}")
    
    def fetch_all_sports(self, sports: Optional[list[str]] = None) -> list[dict]:
        """
        Fetch odds for multiple sports.
        
        Args:
            sports: List of sport keys to fetch. Defaults to configured sports.
            
        Returns:
            Combined list of all game odds
        """
        sports = sports or list(config.SPORTS)
        all_games = []
        
        for sport in sports:
            try:
                games = self.fetch_odds(sport)
                all_games.extend(games)
                logger.info(f"Fetched {len(games)} games for {sport}")
                time.sleep(0.5)  # Be nice to the API
            except OddsAPIError as e:
                logger.error(f"Failed to fetch {sport}: {e}")
                continue
        
        return all_games


# Module-level convenience function
def fetch_odds(sport_key: str) -> list[dict]:
    """Convenience function for fetching odds."""
    client = OddsAPIClient()
    return client.fetch_odds(sport_key)
