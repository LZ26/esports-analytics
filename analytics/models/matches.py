from django.db import models
from analytics.models.teams import Team

class Match(models.Model):
    # Represents a competitive match between two teams
    STATUS_CHOICES = [
        ('running', 'In Progress'),
        ('not_started', 'Scheduled'),
        ('finished', 'Completed'),
        ('canceled', 'Canceled'),
    ]

    GAME_CHOICES = [
        ('csgo', 'Counter-Strike 2'),
        ('dota2', 'Dota 2'),
        ('valorant', 'Valorant'),
    ]

    pandascore_id = models.IntegerField(
        unique=True,
        help_text="Unique match ID from PandaScore"
    )
    name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Descriptive match name"
    )
    team1 = models.ForeignKey(
        Team,
        related_name='home_matches',
        on_delete=models.CASCADE,
        null=True,
        help_text="First participating team"
    )
    team2 = models.ForeignKey(
        Team,
        related_name='away_matches',
        on_delete=models.CASCADE,
        null=True,
        help_text="Second participating team"
    )
    start_time = models.DateTimeField(
        help_text="Scheduled start time of the match"
    )
    tournament = models.CharField(
        max_length=200,
        blank=True,
        help_text="Tournament or league name"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='not started',
        help_text="Current status of the match"
    )
    game = models.CharField(
        max_length=20,
        choices=GAME_CHOICES,
        default='csgo',
        help_text="Game being played"
    )
    next_map = models.CharField(
        max_length=50,
        blank=True,
        help_text="Next map in the series (needed for tactical analysis)"
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of last update"
    )

    def get_game_display(self):
        """Get human-readable game name from choices"""
        return dict(self.GAME_CHOICES).get(self.game, 'Unknown Game')
    
    def __str__(self):
        """Safe string representation with proper display handling"""
        # Get team names safely
        team1_name = self.team1.name if self.team1 else "Unknown Team 1"
        team2_name = self.team2.name if self.team2 else "Unknown Team 2"
        
        # Get game display name
        game_display = self.get_game_display()
        
        return f"{team1_name} vs {team2_name} - {game_display}"