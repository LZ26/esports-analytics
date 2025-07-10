import os
import django
import sys
from datetime import datetime, timedelta
from django.utils import timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from analytics.models import Team, TeamAnalysis, HistoricalMatch
from analytics.utils.predictors import MatchPredictor

def create_test_data():
    """Create real-world test scenario"""
    # Create teams
    team1 = Team.objects.create(
        pandascore_id=1001,
        name="Natus Vincere",
        slug="natus-vincere",
        image_url="https://example.com/navi.png"
    )
    
    team2 = Team.objects.create(
        pandascore_id=1002,
        name="Team Vitality",
        slug="vitality",
        image_url="https://example.com/vitality.png"
    )
    
    # Create historical matches
    now = timezone.now()
    matches = [
        {"winner": team1, "date": now - timedelta(days=5), "teams": [team1, team2]},
        {"winner": team1, "date": now - timedelta(days=4), "teams": [team1, team2]},
        {"winner": team2, "date": now - timedelta(days=3), "teams": [team1, team2]},
        {"winner": team1, "date": now - timedelta(days=2), "teams": [team1, team2]},
        {"winner": team2, "date": now - timedelta(days=1), "teams": [team1, team2]},
    ]
    
    for i, match_data in enumerate(matches):
        match = HistoricalMatch.objects.create(
            match_id=f"testmatch{i}",
            date=match_data["date"],
            tournament="Test Tournament",
            winner=match_data["winner"]
        )
        match.teams.set(match_data["teams"])
    
    # Create analysis
    analysis1 = TeamAnalysis.objects.create(
        team=team1,
        last_ten_winrate=0.7,  # 70% winrate
        h2h_advantage={"1002": 0.6},  # 60% winrate against Vitality
        last_match_data=now - timedelta(hours=72)  # 3 days ago
    )
    
    analysis2 = TeamAnalysis.objects.create(
        team=team2,
        last_ten_winrate=0.6,  # 60% winrate
        h2h_advantage={"1001": 0.4},  # 40% winrate against Navi
        last_match_data=now - timedelta(hours=24)  # 1 day ago
    )
    
    return team1, team2

def run_prediction(team1, team2):
    """Run prediction and display results"""
    predictor = MatchPredictor(team1, team2)
    prediction = predictor.predict()
    
    print(f"\n{'='*50}")
    print(f"PREDICTION: {team1.name} vs {team2.name}")
    print(f"Winner: {prediction['winner'].name}")
    print(f"Confidence: {prediction['confidence']:.2%}")
    print("\nFactors:")
    print(f"  Winrate: {team1.name} - {prediction['factors']['winrate']['home']:.2%}")
    print(f"           {team2.name} - {prediction['factors']['winrate']['away']:.2%}")
    print(f"  H2H: {prediction['factors']['h2h']:.2%} advantage for {team1.name}")
    print(f"  Fatigue: {team1.name} - {prediction['factors']['fatigue']['home']:.2f} ({get_fatigue_status(prediction['factors']['fatigue']['home'])})")
    print(f"           {team2.name} - {prediction['factors']['fatigue']['away']:.2f} ({get_fatigue_status(prediction['factors']['fatigue']['away'])})")
    print("="*50)

def get_fatigue_status(score):
    """Convert fatigue score to status"""
    if score >= 0.75: return "Well-rested"
    elif score >= 0.5: return "Moderately rested"
    elif score >= 0.25: return "Slightly fatigued"
    else: return "Heavily fatigued"

def test_edge_cases():
    """Test special scenarios"""
    # Create teams with incomplete data
    team3 = Team.objects.create(
        pandascore_id=1003,
        name="New Team",
        slug="new-team",
        image_url="https://example.com/new.png"
    )
    
    team4 = Team.objects.create(
        pandascore_id=1004,
        name="Unknown Team",
        slug="unknown",
        image_url="https://example.com/unknown.png"
    )
    
    # Create minimal analysis
    TeamAnalysis.objects.create(team=team3)  # All defaults
    TeamAnalysis.objects.create(team=team4, last_ten_winrate=0.5)
    
    print("\nTesting Edge Cases:")
    run_prediction(team3, team4)

if __name__ == "__main__":
    # Clear previous test data
    HistoricalMatch.objects.all().delete()
    TeamAnalysis.objects.all().delete()
    Team.objects.all().delete()
    
    # Create test data and run predictions
    team1, team2 = create_test_data()
    run_prediction(team1, team2)
    
    # Test edge cases
    test_edge_cases()