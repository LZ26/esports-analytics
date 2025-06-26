import os
import requests
import time
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv
from pathlib import Path
from django.utils import timezone
from analytics.models.matches import Match
from analytics.models.teams import Team

# Path resolution for .env file
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
env_path = project_root / '.env'
load_dotenv(env_path)

class DataFetcher:
    def __init__(self):
        """Initialize with both API keys"""
        self.pandascore_key = os.environ.get("PANDASCORE_API_KEY", "").strip()
        # Create requests session
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "EsportsAnalytics/1.0"
        })

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1.5))
    def fetch_matches(self, game="csgo", status="running,not_started", page_size=20):
        """Fetch matches from PandaScore API with retry logic
        
        Args:
            game: game slug (csgo, dota2, valorant)
            status: comman-separated statuses (running, not_started, finished)
            page_size: number of matches to return
        Returns:
            List of parsed match dictionaries
        """
        try:
            # Construct API endpoint URL
            url = f"https://api.pandascore.co/{game}/matches"
            # Configure query parameters
            params = {
                "filter[status]": status,
                "sort": "begin_at",
                "page[size]": page_size
            }
            headers = {"Authorization": f"Bearer {self.pandascore_key}"}
            
            # Execute API request
            response = self.session.get(url, params=params, headers=headers, timeout=10)
            
            # Handle API errors
            if response.status_code == 429:
                reset_time = int(response.headers.get('X-Rate-Limit-Reset', 60))
                print(f"Rate limited. Sleeping for {reset_time} seconds")
                time.sleep(reset_time)
                return self.fetch_live_matches()
            
            # Raise exception for other HTTP errors
            response.raise_for_status()

            # Parse and return match data
            return self._parse_matches(response.json(), game)
            
        except Exception as e:
            print(f"PandaScore API error: {str(e)}")
            return []

    def _parse_matches(self, data, game):
        """
        Convert raw API response into structured match data

        Args:
            data: JSON response from PandaScore
            game: game identifier

        Returns:
            List of dictionaries with parsed match attributes
        """
        parsed_matches = []

        for match in data:
            try:
                # Extract opponent teams
                opponents = match.get('opponents', [])

                # Get or create team objects from API data
                if len(opponents) > 0 and 'opponent' in opponents[0]:
                    team1 = Team.objects.update_from_api(opponents[0]['opponent'])
                if len(opponents) > 1 and 'opponent' in opponents[1]:
                    team2 = Team.objects.update_from_api(opponents[1]['opponent'])
                
                # Extract next map information if available
                next_map = None
                if match.get('games'):
                    for game_data in match['games']:
                        if game_data.get('status') == 'not_started':
                            next_map = game_data.get('map', {}).get('name')
                            break  # Break out here as only first upcoming map is needed

                # Build match dictionary
                parsed_matches.append({

                })
                matches.append({
                    "pandascore_id": match.get('id'),
                    "name": match.get('name', ''),
                    "team1": team1,
                    "team2": team2,
                    "start_time": match.get('begin_at'),
                    "tournament": match.get('league', {}).get('name', ''),
                    "status": match.get('status'),
                    "game": game,
                    "next_map": next_map,
                    "raw_data": match  # raw JSON for debugging if needed

                })
            except Exception as e:
                print(f"Error parsing match: {str(e)}")
        return parsed_matches
    
    def save_matches_to_db(self, matches):
        """
        Save parsed matches to database

        Args:
            matches: list of match dictionaries from _parse_matches()
        """

        for match_data in matches:
            # Validate required fields
            if not all([match_data.get('team1'), match_data.get('team2'), match_data.get('start_time')]):
                print(f"Skipping match due to missing data: {match_data.get('name')}")
                continue

        # Create or update match record
        match, created = Match.objects.update_or_create(
            pandascore_id=match_data['pandascore_id'],
            defaults={
                'name': match_data['name'],
                'team1': match_data['team1'],
                'team2': match_data['team2'],
                'start_time': match_data['start_time'],
                'tournament': match_data.get('tournament', ''),
                'status': match_data.get('status', 'unknown'),
                'game': match_data.get('game', 'csgo'),
                'next_map': match_data.get('next_map', ''),
            }
        )
        
        # Log creation/update
        if created:
            print(f"Created new match: {match}")
        else:
            print(f"Updated existing match: {match}")
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1))
    def fetch_odds(self):
        """Fetch odds from The Odds API"""  
        try:
            url = "https://api.the-odds-api.com/v4/sports/esports_cs2/odds"
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