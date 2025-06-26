from django.test import TestCase
from unittest.mock import patch, MagicMock
from analytics.utils.data_fetcher import DataFetcher
from analytics.models import Team

class DataFetcherTests(TestCase):
    @patch('analytics.models.teams.update_team_from_api')
    @patch('requests.Session.get')
    def test_successful_match_fetch(self, mock_get, mock_update_team):
        """Test successful match data retrieval"""
        # Mock update_team responses
        mock_team1 = MagicMock(spec=Team)
        mock_team1.name = 'Fanatic'
        mock_team2 = MagicMock(spec=Team)
        mock_team2.name = 'Cloud9'
        mock_update_team.side_effect = [mock_team1, mock_team2]
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{
            'id': 12345,
            'name': 'Test Match',
            'begin_at': '2025-06-27T15:00:00Z',
            'status': 'not started',
            'opponents': [
                {'opponent': {'id': 1, 'name': 'Fanatic', 'slug': 'F4TC'}},
                {'opponent': {'id': 2, 'name': 'Cloud9', 'slug': 'C9'}}
            ],
            'league': {'name': 'Test Tournament'}
        }]
        mock_get.return_value = mock_response

        # Execute fetcher
        fetcher = DataFetcher()
        matches = fetcher.fetch_matches()

        # Validation results
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['name'], 'Test Match')
        self.assertEqual(matches[0]['team1'].name, 'Fanatic')
        self.assertEqual(matches[0]['team2'].name, 'Cloud9')

    @patch('requests.Session.get')
    def test_rate_limit_handling(self, mock_get):
        """Test automatic handling of rate limits"""
        # First response: Rate limit
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {'X-Rate-Limit-Reset': '5'}

        # Second response: Success
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = []

        mock_get.side_effect = [rate_limit_response, success_response]

        # Execute fetcher
        fetcher = DataFetcher()
        matches = fetcher.fetch_matches()

        # Validate behavior
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(len(matches), 0)