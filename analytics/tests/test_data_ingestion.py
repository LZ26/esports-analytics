import os
import django
import sys
import logging
from pathlib import Path
from django.core.management import call_command

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def setup_django():
    """Configure and initialize Django environment"""
    try:
        # Determine project root
        BASE_DIR = Path(__file__).resolve().parent.parent.parent
        sys.path.append(str(BASE_DIR))
        
        # Configure environment
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        
        # Initialize Django
        django.setup()
        logger.info("Django environment configured")
        
        # Run migrations
        logger.info("Running database migrations...")
        call_command('makemigrations', 'analytics', interactive=False)
        call_command('migrate', interactive=False)
        logger.info("Database migrations completed")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to configure Django: {str(e)}")
        return False

def test_data_ingestion():
    """End-to-end test of data fetching and persistence"""
    if not setup_django():
        return False
        
    try:
        logger.info("Starting Data Ingestion Test")
        # Import models AFTER setup
        from analytics.models import Team, Match
        from analytics.utils.data_fetcher import DataFetcher

        logger.info("Starting Data Ingestion Test")
        
        # Clean previous test data
        logger.info("Clearing previous test data...")
        Match.objects.all().delete()
        Team.objects.all().delete()
        logger.info("Cleared previous test data")
        
        # Initialize data fetcher
        fetcher = DataFetcher()
        
        # Fetch matches from API
        logger.info("Fetching matches from PandaScore...")
        matches = fetcher.fetch_matches(page_size=2)
        
        if not matches:
            logger.error("Failed to fetch matches from API")
            return False
            
        logger.info(f"Retrieved {len(matches)} matches")
        
        # Save matches to database
        logger.info("Saving matches to database...")
        save_success = fetcher.save_matches_to_db(matches)

        if not save_success:
            logger.error("Failed to save matches to database")
            return False
        
        # Verify database records
        team_count = Team.objects.count()
        match_count = Match.objects.count()
        
        logger.info(f"Database Status: {team_count} teams, {match_count} matches")
        
        if team_count >= 2 and match_count >= 1:
            logger.info("Data Ingestion Test PASSED")
            return True
        else:
            logger.error("Data Ingestion Test FAILED")
            return False
            
    except Exception as e:
        logger.exception(f"Critical error during test: {str(e)}")
        return False

if __name__ == "__main__":
    if test_data_ingestion():
        sys.exit(0)
    else:
        sys.exit(1)