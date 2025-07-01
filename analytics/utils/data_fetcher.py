import os
import requests
import time
from tenacity import retry, stop_after_attempt, wait_exponential
from django.core.cache import cache
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from dotenv import load_dotenv
from pathlib import Path
from analytics.models import Team, Match
from analytics.models.teams import update_team_from_api
import logging

logger = logging.getLogger(__name__)

# Path resolution for .env file
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(env_path)

class DataFetcher:
    """Handles API communication with PandaScore for data retrieval"""

    def __init__(self):
        # Retrieve API key from environment
        self.pandascore_key = os.environ.get("PANDASCORE_API_KEY", "").strip()
        # Configure HTTP session
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
            
            # Handle rate limiting
            if response.status_code == 429:
                reset_time = int(response.headers.get('X-Rate-Limit-Reset', 60))
                logger.warning(f"Rate limited. Sleeping for {reset_time} seconds")
                time.sleep(reset_time)
                return self.fetch_matches()
            
            # Raise exception for other HTTP errors
            response.raise_for_status()

            # Parse and return match data
            return self._parse_matches(response.json(), game)
            
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
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

        if not isinstance(data, list):
            logger.error(f"Unexpected API response format: {type(data)}")
            return parsed_matches

        for match in data:
            try:
                # Extract opponents safely
                opponents = match.get('opponents', [])
                
                # Get or create team objects
                team1 = None
                if len(opponents) > 0 and 'opponent' in opponents[0]:
                    team1 = update_team_from_api(opponents[0]['opponent'])
                
                team2 = None
                if len(opponents) > 1 and 'opponent' in opponents[1]:
                    team2 = update_team_from_api(opponents[1]['opponent'])
                
                # Extract next map information
                next_map = None
                if match.get('games'):
                    for game_data in match['games']:
                        if game_data.get('status') == 'not_started':
                            next_map = game_data.get('map', {}).get('name')
                            break
                
                # Build match dictionary
                parsed_matches.append({
                    "pandascore_id": match.get('id'),
                    "name": match.get('name', ''),
                    "team1": team1,
                    "team2": team2,
                    "start_time": match.get('begin_at'),
                    "tournament": match.get('league', {}).get('name', ''),
                    "status": match.get('status'),
                    "game": game,
                    "next_map": next_map
                })
            except Exception as e:
                logger.error(f"Match parsing error: {str(e)}")
                logger.debug(f"Problematic match data: {match}")
        return parsed_matches
    
    def _process_team(self, team_data):
        """Create or update team from API data"""
        if not team_data:
            return None
        
        team, created = Team.objects.get_or_create(
            pandascore_id=team_data['id'],
            defaults={
                'name': team_data.get('name', 'Unknown Team'),
                'slug': team_data.get('slug', ''),
                'image_url': team_data.get('image_url', '')
            }
        )

        # Update existing record if needed
        if not created:
            update_fields = []
            if team.name != team_data.get('name'):
                team.name = team_data.get('name')
                update_fields.append('name')
            if team.slug != team_data.get('slug'):
                team.slug = team_data.get('slug')
                update_fields.append('slug')
            if team.image_url != team_data.get('image_url'):
                team.image_url = team_data.get('image_url')
                update_fields.append('image_url')
            if update_fields:
                team.save(update_fields=update_fields)

        return team
    
    def save_matches_to_db(self, matches):
        """
        Save parsed matches to database

        Args:
            matches: list of match dictionaries from _parse_matches()
        """
        saved_count = 0
        for match_data in matches:
            # Validate required fields
            if not match_data.get('team1'):
                logger.warning(f"Skipping match {match_data.get('name')}: Missing team1")
                continue
            if not match_data.get('team2'):
                logger.warning(f"Skipping match {match_data.get('name')}: Missing team2")
                continue
            if not match_data.get('start_time'):
                logger.warning(f"Skipping match {match_data.get('name')}: Missing start_time")
                continue
        
        try:
            # Handle next_map conversion: None to empty string
            next_map = match_data.get('next_map', '')

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
                    'next_map': next_map or None
                }
            )
            
            action = "Created" if created else "Updated"
            logger.info(f"{action} match: {match}")

            saved_count += 1
        except Exception as e:
            logger.error(f"Failed to save match {match_data.get('name')}: {str(e)}")

        logger.info(f"Successfully saved {saved_count}/{len(matches)} matches")
        return saved_count > 0
    
    def fetch_team_history(self, team_id):
        """
        Fetches historical match data for a team with caching.
        Implements cache-aside pattern: check cache first, then API.

        Args:
            team_id: PandaScore team identifier

        Returns:
            List of parsed match dictionaries or empty list on error
        """

        cache_key = f"team_history_{team_id}"

        # Check cache first
        if cached_data := cache.get(cache_key):
            logger.info(f"Using cached historical data for team {team_id}")
            return cached_data
        
        try:
            logger.info(f"Fetching historical matches for team {team_id}")
            url = f"https://api.pandascore.co/teams/{team_id}/matches"

            # API parameters: finished matches, sorted newest first
            params = {
                "filter[status]": "finished",
                "sort": "-begin_at", # most recent first
                "page[size]": 10 # get last 10 matches for analytics
            }
            headers = {"Authorization": f"Bearer {self.pandascore_key}"}

            # Execute API request with existing sesion
            response = self.session.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status() # Raise exceptionss for 4xx or 5xx errors

            # Process API response
            historical_data = []
            for match in response.json():
                if parsed := self._parse_historical_match(match):
                    historical_data.append(parsed)

            # Cache results for 6 hours (21600 seconds)
            cache.set(cache_key, historical_data, 21600)
            return historical_data
        
        except Exception as e:
            logger.error(f"Failed to fetch history for team {team_id}: {str(e)}")
            return [] # handle the exception gracefully rather than causing crash here
        
    def _parse_historical_match(self, api_data):
        """
        Converts raw API match data into standardized format.
        Handles data inconsistencies and missing fields.

        Args:
            api_data: Raw match dictionary from API

        Returns:
            Dict with normalized structure or None on error
        """
        try:
            # Required fields extraction with fallbacks
            match_id = str(api_data.get('id')) # Convert to string for consistency
            date_str = api_data.get('begin_at') # ISO 8601 format string
            if not date_str:
                logger.warning(f"Missing begin_at for match {match_id}")
                return None
            
            # Convert ISO 8601 string to timezone-aware datetime
            date = parse_datetime(date_str)
            if not date:
                logger.warning(f"Invalid date format for match {match_id}: {date_str}")
                return None
                
            # Make datetime timezone-aware if not already
            if not timezone.is_aware(date):
                date = timezone.make_aware(date, timezone=timezone.utc)

            tournament = api_data.get('league', {}).get('name', 'Unknown Tournament')

            # Extract winner ID if available
            winner_id = None
            if winner := api_data.get('winner'):
                winner_id = winner.get('id')

            # Extract team IDs from opponents
            team_ids = []
            for opponent in api_data.get('opponents', []):
                if opp_data := opponent.get('opponent'):
                    team_ids.append(opp_data['id'])
            
            return {
                'match_id': match_id,
                'date': date,
                'tournament': tournament,
                'team_ids': team_ids,
                'winner_id': winner_id
            }
        except Exception as e:
            logger.error(f"Error parsing historical match: {str(e)}")
            logger.debug(f"Problematic match data: {api_data}")
            return None