from django.utils import timezone
from analytics.models import TeamAnalysis
import logging

logger = logging.getLogger(__name__)

class MatchPredictor:
    def __init__(self, home_team, away_team):
        self.home_team = home_team
        self.away_team = away_team
        self.home_analysis = TeamAnalysis.objects.get_or_create(team=home_team)[0]
        self.away_analysis = TeamAnalysis.objects.get_or_create(team=away_team)[0]

    def _calculate_winrate(self, team_analysis):
        """Calculate normalized winrate score: 0 - 1"""
        if team_analysis.last_ten_winrate is None:
            logger.warning(f"No winrate data for {team_analysis.team.name}")
            return 0.5 # Neutral value for missing data
        return team_analysis.last_ten_winrate
    
    def _calculate_h2h(self):
        """Calculate head to head advantage score: 0 - 1"""
        # Get h2h advantage from home team's perspective
        opponent_id = str(self.away_team.pandascore_id)
        h2h_data = self.home_analysis.h2h_advantage

        if not h2h_data or opponent_id not in h2h_data:
            logger.info(f"N h2h data between {self.home_team.name} and {self.away_team.name}")
            return 0.5 # Returns neutral value
        
        return float(h2h_data[opponent_id])
    
    def _calculate_fatigue(self, team_analysis):
        """Calculate fatigure index score (0 - 1) where 0=most fatigued"""
        if not team_analysis.last_match_data:
            logger.warning(f"No last match data for {team_analysis.team.name}")
            return 1.0 # No matches which means its a fresh team
        
        hours_since_last = (timezone.now() - team_analysis.last_match_data).total_seconds() / 3600

        """
        Fatigue scale:
            < 24h: 0.0 (extremely fatigued)
            24 - 48h: 0.25
            48 - 72h: 0.5
            72 - 96h: 0.75
            > 96h: 1.0 (fully rested)
        """
        # below needs refactoring for simpler logic, otherwise looks spaghetti
        if hours_since_last < 24:
            return 0.0
        elif hours_since_last < 48:
            return 0.25
        elif hours_since_last < 72:
            return 0.5
        elif hours_since_last < 96:
            return 0.75
        else:
            return 1.0
    
    def predict(self):
        """Generate prediction with confidence score"""
        # Calculate factors
        home_winrate = self._calculate_winrate(self.home_analysis)
        away_winrate = self._calculate_winrate(self.away_analysis)
        h2h = self._calculate_h2h()
        home_fatigue = self._calculate_fatigue(self.home_analysis)
        away_fatigue = self._calculate_fatigue(self.away_analysis)

        # Weighted scores
        home_score = (
            (home_winrate * 0.6) +
            (h2h * 0.3) +
            (home_fatigue * 0.1))
    
        away_score = (
            (away_winrate * 0.6) +
            ((1 - h2h) * 0.3) +
            (away_fatigue * 0.1))
        
        # Determine winner and confidence
        total = home_score + away_score
        if total == 0:  # Prevent division by zero
            confidence = 0.5
            winner = None
        else:
            home_confidence = home_score / total
            away_confidence = away_score / total
            
            if home_confidence > away_confidence:
                winner = self.home_team
                confidence = home_confidence
            else:
                winner = self.away_team
                confidence = away_confidence
        
        return {
            "winner": winner,
            "confidence": confidence,
            "factors": {
                "winrate": {
                    "home": home_winrate,
                    "away": away_winrate
                },
                "h2h": h2h,
                "fatigue": {
                    "home": home_fatigue,
                    "away": away_fatigue
                }
            }
        }