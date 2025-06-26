from django.db import models

class Team(models.Model):
    # Represents an esports team with core identification data

    pandascore_id = models.IntegerField(
        unique=True,
        help_text="Unique identifier from PandaScore API"
    )
    name = models.CharField(
        max_length=100,
        blank=True,
        help_text="URL-friendly identifier for the team"
    )
    slug = models.SlugField(
        max_length=100,
        blank=True,
        help_text="URL-friendly identifier for the team"
    )
    image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL to team's logo image"
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of last data sync"
    )

    def __str__(self):
        return self.name
class TeamAnalysis(models.Model):
    # Stores compute analytics metrics for teams
    team = models.OneToOneField(
        Team,
        on_delete=models.CASCADE,
        related_name='analysis',
        help_text="Associated team for these analytics"
    )
    last_ten_winrate = models.FloatField(
        default=0.0,
        help_text="Win rate percentage from last 10 matches (0.0 - 1.0)"
    )
    h2h_advantage = models.JSONField(
        default=dict,
        blank=True,
        help_text="Head to head advantage against opponents {opponent_id: win_rate}"
    )
    last_match_data = models.DateField(
        null=True,
        blank=True,
        help_text="Date of most recent match for fatigure calculation"
    )

    def __str__(self):
        return f"Performance analysis for {self.team.name}"