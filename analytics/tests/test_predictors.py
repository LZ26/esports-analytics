from django.test import TestCase
from django.utils import timezone
from analytics.models import Team, TeamAnalysis
from analytics.utils.predictors import MatchPredictor
from datetime import timedelta

class PredictorTests(TestCase):
    def setUp(self):
        self.team_a = Team.objects.create(
            pandascore_id=101, 
            name="Team Alpha",
            slug="alpha",
            image_url="https://example.com/alpha.jpg"
        )
        self.team_b = Team.objects.create(
            pandascore_id=102, 
            name="Team Beta",
            slug="beta",
            image_url="https://example.com/beta.jpg"
        )
        
        # Create analysis records with valid winrate values
        self.analysis_a = TeamAnalysis.objects.create(
            team=self.team_a,
            last_ten_winrate=0.7,
            h2h_advantage={"102": 0.6},
            last_match_data=timezone.now() - timedelta(hours=100)
        )
        self.analysis_b = TeamAnalysis.objects.create(
            team=self.team_b,
            last_ten_winrate=0.5,
            h2h_advantage={"101": 0.4},
            last_match_data=timezone.now() - timedelta(hours=24)
        )
    
    def test_basic_prediction(self):
        """Test prediction with complete data"""
        predictor = MatchPredictor(self.team_a, self.team_b)
        prediction = predictor.predict()
        
        # Team A should win with confidence > 0.5
        self.assertEqual(prediction["winner"], self.team_a)
        self.assertGreater(prediction["confidence"], 0.5)
        
        # Expected confidence calculation
        home_score = (0.7 * 0.6) + (0.6 * 0.3) + (1.0 * 0.1)  # 0.42 + 0.18 + 0.1 = 0.7
        away_score = (0.5 * 0.6) + (0.4 * 0.3) + (0.25 * 0.1)  # 0.3 + 0.12 + 0.025 = 0.445
        expected_confidence = home_score / (home_score + away_score)  # ≈ 0.611
        
        self.assertAlmostEqual(prediction["confidence"], expected_confidence, delta=0.01)
    
    def test_missing_winrate(self):
        """Test prediction with missing winrate data"""
        # Update existing analysis
        self.analysis_a.last_ten_winrate = None
        self.analysis_a.save()
        
        predictor = MatchPredictor(self.team_a, self.team_b)
        prediction = predictor.predict()
        
        # Should still work with default values
        self.assertIsNotNone(prediction["winner"])
        self.assertIn("winrate", prediction["factors"])
        # Should use neutral value (0.5) for missing winrate
        self.assertEqual(prediction["factors"]["winrate"]["home"], 0.5)
    
    def test_missing_h2h(self):
        """Test prediction with no H2H data"""
        self.analysis_a.h2h_advantage = {}
        self.analysis_a.save()
        
        predictor = MatchPredictor(self.team_a, self.team_b)
        prediction = predictor.predict()
        
        # Should use neutral H2H value
        self.assertEqual(prediction["factors"]["h2h"], 0.5)
        self.assertIsNotNone(prediction["winner"])
    
    def test_fatigue_calculation(self):
        """Test fatigue scoring logic"""
        # Team B just played
        self.analysis_b.last_match_data = timezone.now() - timedelta(hours=12)
        self.analysis_b.save()
        
        predictor = MatchPredictor(self.team_a, self.team_b)
        prediction = predictor.predict()
        
        # Team B should have high fatigue (0.0)
        self.assertEqual(prediction["factors"]["fatigue"]["away"], 0.0)
        
        # Team A is well-rested (1.0)
        self.assertEqual(prediction["factors"]["fatigue"]["home"], 1.0)
    
    def test_draw_condition(self):
        """Test equal scores results"""
        # Make teams identical from home team's perspective
        self.analysis_a.last_ten_winrate = 0.7
        self.analysis_b.last_ten_winrate = 0.7
        self.analysis_a.h2h_advantage = {"102": 0.5}  # Neutral H2H
        self.analysis_a.save()
        
        # Set both teams as well-rested
        now = timezone.now()
        self.analysis_a.last_match_data = now - timedelta(hours=100)
        self.analysis_b.last_match_data = now - timedelta(hours=100)
        self.analysis_a.save()
        self.analysis_b.save()
        
        predictor = MatchPredictor(self.team_a, self.team_b)
        prediction = predictor.predict()
        
        # Should be a toss-up
        self.assertAlmostEqual(prediction["confidence"], 0.5, delta=0.01)
    
    def test_missing_fatigue_data(self):
        """Test no last match data"""
        self.analysis_a.last_match_data = None
        self.analysis_a.save()
        
        predictor = MatchPredictor(self.team_a, self.team_b)
        prediction = predictor.predict()
        
        # Should default to fresh team
        self.assertEqual(prediction["factors"]["fatigue"]["home"], 1.0)