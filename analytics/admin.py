from django.contrib import admin
from analytics.models import Team, TeamAnalysis, Match

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'pandascore_id', 'slug', 'last_updated')
    search_fields = ('name', 'pandascore_id')
    readonly_fields = ('last_updated',)
    list_filter = ('last_updated',)

@admin.register(TeamAnalysis)
class TeamAnalysisAdmin(admin.ModelAdmin):
    list_display = ('team', 'last_ten_winrate', 'last_match_data')
    search_fields = ('team__name',)
    raw_id_fields = ('team',)

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'team1', 'team2', 'start_time', 'status', 'game')
    list_filter = ('status', 'game', 'start_time')
    search_fields = ('name', 'tournament')
    raw_id_fields = ('team1', 'team2')
    readonly_fields = ('last_updated',)