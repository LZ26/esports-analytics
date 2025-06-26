from django.db import models
import logging

logger = logging.getLogger(__name__)

class TeamManager(models.Manager):
    """Custom manager for Team model with API update method"""
    
    def update_from_api(self, api_data):
        """
        Create or update a team from PandaScore API data
        """
        try:
            if not api_data or not api_data.get('id'):
                logger.warning("Invalid API data for team update")
                return None
                
            team_id = api_data['id']
            name = api_data.get('name', 'Unknown Team')
            slug = api_data.get('slug', '')
            image_url = api_data.get('image_url', '')
        
        
            # Try to get existing team or create new
            team, created = self.get_or_create(
                pandascore_id=team_id,
                defaults={
                    'name': name,
                    'slug': slug,
                    'image_url': image_url
                }
            )
            
            # Update if existing and data changed
            if not created:
                needs_save = False
                if team.name != name:
                    team.name = name
                    needs_save = True
                if team.slug != slug:
                    team.slug = slug
                    needs_save = True
                if team.image_url != image_url:
                    team.image_url = image_url
                    needs_save = True
                    
                if needs_save:
                    team.save()
                    
            return team
            
        except Exception as e:
            # Log error but don't break the flow
            logger.error(f"Error updating team from API: {str(e)}")
            return None
    
class Team(models.Model):
    # Represents an esports team with core identification data

    pandascore_id = models.IntegerField(
        unique=True,
        help_text="Unique identifier from PandaScore API"
    )
    name = models.CharField(
        db_index=True,
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

    # Use custom manager
    objects = TeamManager()

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

def update_team_from_api(api_data):
    """Direct access function to update team from API data"""
    return Team.objects.update_from_api(api_data)