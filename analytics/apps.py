from django.apps import AppConfig

class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analytics'
    verbose_name = 'Esports Analytics'
    
    def ready(self):
        """
        Called when app is fully loaded
        Use this to register signals or run startup code
        """
        
        # Make models available via app_config
        from .models import Team, Match, TeamAnalysis
        self.Team = Team
        self.Match = Match
        self.TeamAnalysis = TeamAnalysis