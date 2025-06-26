import os
import requests
import pandas as pd
import time
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv
from pathlib import Path

# Path resolution for .env file
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
env_path = project_root / '.env'

load_dotenv(env_path)

class DataFetcher:
    def __init__(self):
        """Initialize with both API keys"""
        self.pandascore_key = os.environ.get("PANDASCORE_API_KEY", "").strip()
        self.odds_api_key = os.environ.get("ODDS_API_KEY", "").strip()
        
        # Create requests session
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "eSportsOddsCalculator/1.0"
        })

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1.5))
    def fetch_live_matches(self):
        """Fetch live and upcoming CS:GO matches from PandaScore"""  
        try:
            url = "https://api.pandascore.co/csgo/matches"
            params = {
                "filter[status]": "running,not_started",
                "sort": "begin_at",
                "page[size]": 5
            }
            headers = {"Authorization": f"Bearer {self.pandascore_key}"}
            
            response = self.session.get(url, params=params, headers=headers, timeout=10)
            
            # Handle API errors
            if response.status_code == 401:
                raise ValueError("Authentication failed: Invalid credentials")
            if response.status_code == 429:
                reset_time = int(response.headers.get('X-Rate-Limit-Reset', 60))
                print(f"Rate limited. Sleeping for {reset_time} seconds")
                time.sleep(reset_time)
                return self.fetch_live_matches()
                
            response.raise_for_status()
            return self._parse_matches(response.json())
            
        except Exception as e:
            print(f"PandaScore API error: {str(e)}")
            return pd.DataFrame()

    def _parse_matches(self, data):
        """Parse match data"""
        matches = []
        for match in data:
            try:
                opponents = match.get('opponents', [])
                team1 = opponents[0]['opponent']['name'] if len(opponents) > 0 else None
                team2 = opponents[1]['opponent']['name'] if len(opponents) > 1 else None
                
                matches.append({
                    "match_id": match.get('id'),
                    "team1": team1,
                    "team2": team2,
                    "start_time": match.get('begin_at', ''),
                    "tournament": match.get('league', {}).get('name', ''),
                })
            except Exception as e:
                print(f"⚠️ Error parsing match: {str(e)}")
        return pd.DataFrame(matches)
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1))
    def fetch_odds(self):
        """Fetch odds from The Odds API"""  
        try:
            url = "https://api.the-odds-api.com/v4/sports/esports_csgo/odds"
            params = {
                "apiKey": self.odds_api_key,
                "regions": "eu",
                "markets": "h2h",
                "oddsFormat": "decimal"
            }
            
            response = self.session.get(url, params=params, timeout=8)
            
            # Handle API limits
            if response.status_code == 429:
                reset_time = int(response.headers.get('x-requests-reset', 60))
                print(f"Rate limited. Sleeping for {reset_time}s")
                time.sleep(reset_time)
                return self.fetch_odds()
                
            response.raise_for_status()
            
            # Track usage
            if 'x-requests-remaining' in response.headers:
                remaining = response.headers['x-requests-remaining']
                print(f"Odds API requests remaining: {remaining}")
            
            return self._parse_odds_api_response(response.json())
        except Exception as e:
            print(f"Odds API error: {str(e)}")
            return pd.DataFrame()
    
    def _parse_odds_api_response(self, data):
        """Parse The Odds API response"""
        odds_data = []
        for event in data:
            event_id = event.get('id')
            commence_time = event.get('commence_time', '')
            
            for bookmaker in event.get('bookmakers', []):
                bookmaker_name = bookmaker.get('key', '')
                
                for market in bookmaker.get('markets', []):
                    if market.get('key') == 'h2h':
                        for outcome in market.get('outcomes', []):
                            odds_data.append({
                                "event_id": event_id,
                                "bookmaker": bookmaker_name,
                                "team": outcome.get('name', ''),
                                "odds": outcome.get('price', 0.0),
                                "start_time": commence_time
                            })
        return pd.DataFrame(odds_data)
    
    def normalize_team_names(self, df, column='team'):
        """Normalize team names for consistent matching"""
        # Common name mappings
        name_map = {
            'Natus Vincere': 'NAVI',
            'Team Vitality': 'Vitality',
            'G2 Esports': 'G2',
            'FaZe Clan': 'FaZe',
            'FURIA Esports': 'FURIA'
        }
        
        df[column] = df[column].replace(name_map)
        df[column] = df[column].str.replace(r'\bEsports\b|\bTeam\b', '', regex=True)
        df[column] = df[column].str.strip()
        return df