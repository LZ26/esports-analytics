from django.db import models
from analytics.models.teams import Team

class HistoricalMatch(models.Model):
    """
    Represents a completed match from the past used for analytics.
    Stores essential match details while minimizing storage requirements.
    """
    match_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique identifier from PandaScore API"
    )
    teams = models.ManyToManyField(
        'analytics.Team',
        related_name='historical_matches',
        help_text="Teams participating in this match"
    )
    winner = models.ForeignKey(
        'analytics.Team',
        on_delete=models.CASCADE,
        related_name='historical_wins',
        help_text="Winning team of this match"
    )
    date = models.DateTimeField(
        help_text="Date and time when the match was played"
    )
    tournament = models.CharField(
        max_length=200,
        blank=True, # allow empty tournament names
        help_text="Tournament or league name"
    )
    last_updated = models.DateTimeField(
        auto_now=True, # auto-update on save
        help_text="Timestamp of last data sync"
    )

    class Meta:
        verbose_name = "Historical Match",
        verbose_name_plural = "Historical Matches"
        ordering = ['-date'] # by newest matches first

    def __str__(self):
        """Human-readable representation: Team1, Team2 - Date"""
        team_names = ", ".join([team.name for team in self.teams.all()])
        return f"{team_names} - {self.date.strftime('%Y-%m-%d')}"