from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Team, TeamAnalysis
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Team)
def create_team_analysis(sender, instance, created, **kwargs):
    """Automatically create TeamAnalysis when new Team is created"""
    if created:
        TeamAnalysis.objects.get_or_create(team=instance)
        logger.info(f"Created TeamAnalysis for {instance.name}")