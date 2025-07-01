import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import models
from analytics.models import Team, TeamAnalysis, HistoricalMatch
from analytics.utils.data_fetcher import DataFetcher

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Updates team analytics based on historical match data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--team-id',
            type=int,
            help='Process a specific team by PandaScore ID'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even if recently updated'
        )
    
    def handle(self, *args, **options):
        logger.info("Starting analytics update process")
        fetcher = DataFetcher()
        teams = self.get_teams_to_update(options['force'], options['team_id'])
        
        if not teams.exists():
            logger.info("All teams are up-to-date")
            return
            
        logger.info(f"Processing {teams.count()} teams")
        
        for team in teams:
            logger.info(f"Updating {team.name} (ID: {team.pandascore_id})")
            try:
                self.process_team(team, fetcher)
            except Exception as e:
                logger.error(f"Failed to update {team.name}: {str(e)}")
        
        logger.info("Analytics update completed")
    
    def get_teams_to_update(self, force_update, specific_team):
        """Determine which teams need updates"""
        base_query = Team.objects.all()
        
        if specific_team:
            base_query = base_query.filter(pandascore_id=specific_team)
            
        if force_update:
            return base_query
            
        # Teams without analysis or with stale data (>24 hours)
        outdated_threshold = timezone.now() - timedelta(hours=24)
        return base_query.filter(
            models.Q(analysis__isnull=True) | 
            models.Q(analysis__last_updated__lt=outdated_threshold)
        ).distinct()
    
    def process_team(self, team, fetcher):
        """Full update pipeline for a single team"""
        # Step 1: Fetch and store historical matches
        historical_data = fetcher.fetch_team_history(team.pandascore_id)
        self.store_historical_matches(historical_data)
        
        # Step 2: Update analytics
        self.update_team_analysis(team)
    
    def store_historical_matches(self, historical_data):
        """Create HistoricalMatch records from fetched data"""
        for match_data in historical_data:
            # Skip existing matches
            if HistoricalMatch.objects.filter(match_id=match_data['match_id']).exists():
                continue
                
            try:
                # Validate teams exist
                teams = Team.objects.filter(pandascore_id__in=match_data['team_ids'])
                if teams.count() < 2:
                    logger.warning(f"Skipping match {match_data['match_id']}: Insufficient teams")
                    continue
                    
                # Validate winner exists
                winner = Team.objects.filter(pandascore_id=match_data['winner_id']).first()
                if not winner:
                    logger.warning(f"Skipping match {match_data['match_id']}: Winner not found")
                    continue
                    
                # Create match record
                match = HistoricalMatch.objects.create(
                    match_id=match_data['match_id'],
                    date=match_data['date'],
                    tournament=match_data['tournament'],
                    winner=winner
                )
                match.teams.set(teams)
                logger.debug(f"Created historical match: {match}")
                
            except Exception as e:
                logger.error(f"Failed to create match {match_data['match_id']}: {str(e)}")
    
    def update_team_analysis(self, team):
        """Calculate and update analytics metrics for a team"""
        analysis, created = TeamAnalysis.objects.get_or_create(team=team)
        
        # Get last 10 matches - keep as queryset
        recent_matches = HistoricalMatch.objects.filter(
            teams=team
        ).order_by('-date')[:10]
        
        # Convert to list to preserve queryset state
        recent_matches_list = list(recent_matches)
        total = len(recent_matches_list)
        
        if total == 0:
            logger.warning(f"No historical matches for {team.name}")
            return
            
        # Count wins by iterating through matches
        wins = sum(1 for match in recent_matches_list if match.winner_id == team.id)
        win_rate = wins / total
        
        # Update analysis
        analysis.last_ten_winrate = win_rate
        analysis.last_match_data = recent_matches_list[0].date if recent_matches_list else None
        analysis.save()
        logger.info(f"Updated {team.name}: Win rate = {win_rate:.2f} ({wins}/{total})")