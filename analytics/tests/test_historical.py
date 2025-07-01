from django.test import TestCase
from django.core.cache import cache
from unittest.mock import patch, MagicMock
from analytics.models import Team, HistoricalMatch, TeamAnalysis
from analytics.utils.data_fetcher import DataFetcher
from datetime import datetime, timedelta
import time
from django.utils import timezone
from django.apps import apps


class HistoricalDataTests(TestCase):
    def setUp(self):
        self.team1 = Team.objects.create(
            pandascore_id=1, 
            name="Team Alpha",
            slug="alpha"
        )
        self.team2 = Team.objects.create(
            pandascore_id=2, 
            name="Team Beta",
            slug="beta"
        )
        self.analysis = TeamAnalysis.objects.create(team=self.team1)

        self.HistoricalMatch = apps.get_model('analytics', 'HistoricalMatch')

    def test_historical_match_creation(self):
        """Test creating HistoricalMatch with relationships"""
        match = HistoricalMatch.objects.create(
            match_id="hist123",
            date=timezone.now(),
            tournament="Test Tournament",
            winner=self.team1
        )
        match.teams.set([self.team1, self.team2])
        
        self.assertEqual(match.teams.count(), 2)
        self.assertEqual(match.winner, self.team1)
        self.assertIn(match, self.team1.historical_matches.all())

    @patch('requests.Session.get')
    def test_fetch_team_history(self, mock_get):
        """Test end-to-end historical data fetching"""
        # Mock API response with complete data
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{
            'id': 1001, 
            'begin_at': '2023-01-01T12:00:00Z',
            'opponents': [
                {'opponent': {'id': 1, 'name': 'Alpha'}},
                {'opponent': {'id': 2, 'name': 'Beta'}}
            ], 
            'league': {'name': 'Test League'},
            'winner': {'id': 1}
        }]
        mock_get.return_value = mock_response
        
        fetcher = DataFetcher()
        history = fetcher.fetch_team_history(1)
        
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['match_id'], '1001')
        self.assertEqual(history[0]['team_ids'], [1, 2])
        self.assertEqual(history[0]['winner_id'], 1)
        
        # Test caching
        cached_history = fetcher.fetch_team_history(1)
        self.assertEqual(len(cached_history), 1)
        
        # Test cache expiration
        cache.clear()
        history = fetcher.fetch_team_history(1)
        self.assertEqual(mock_get.call_count, 2)

    def test_winrate_calculation(self):
        """Test winrate calculation for team analysis"""
        now = timezone.now()
        
        # Create historical matches
        match1 = HistoricalMatch.objects.create(
            match_id="m1", 
            date=now - timedelta(days=3),
            tournament="Test Cup",
            winner=self.team1
        )
        match1.teams.set([self.team1, self.team2])
        
        match2 = HistoricalMatch.objects.create(
            match_id="m2", 
            date=now - timedelta(days=2),
            tournament="Test Cup",
            winner=self.team2
        )
        match2.teams.set([self.team1, self.team2])
        
        # Update analytics
        self.analysis.update_from_history()
        self.analysis.refresh_from_db()
        
        # Should be 1 win out of 2 matches = 0.5
        self.assertEqual(self.analysis.last_ten_winrate, 0.5)
        # Compare datetime objects directly
        self.assertEqual(self.analysis.last_match_data, match2.date)
        
        # Add another win
        match3 = HistoricalMatch.objects.create(
            match_id="m3", 
            date=now - timedelta(days=1),
            tournament="Test Cup",
            winner=self.team1
        )
        match3.teams.set([self.team1, self.team2])
        
        # Update again
        self.analysis.update_from_history()
        self.analysis.refresh_from_db()
        
        # Should be 2 wins out of 3 matches
        self.assertEqual(self.analysis.last_ten_winrate, 2/3)
        self.assertEqual(self.analysis.last_match_data, match3.date)

    def test_cache_expiration(self):
        """Test cache expiration behavior"""
        cache_key = "team_history_123"
        test_data = [{'match_id': 'test1'}]
        cache.set(cache_key, test_data, 1)  # 1-second TTL
        self.assertEqual(cache.get(cache_key), test_data)
        
        time.sleep(1.1)
        self.assertIsNone(cache.get(cache_key))

# Add to TeamAnalysis model in teams.py
def update_from_history(self):
    """Recalculates analytics from historical matches"""
    recent_matches = self.team.historical_matches.order_by('-date')[:10]
    total = recent_matches.count()
    if total > 0:
        wins = recent_matches.filter(winner=self.team).count()
        self.last_ten_winrate = wins / total
        self.last_match_data = recent_matches.first().date
        self.save()