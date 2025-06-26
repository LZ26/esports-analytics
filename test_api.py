# test_api.py
from src.data_fetcher import DataFetcher
import time
import pandas as pd
import os

def main():
    print("🔌 API CONNECTION TEST SUITE")
    
    # Initialize fetcher
    fetcher = DataFetcher()
    
    # Test PandaScore matches API
    test_pandascore_matches(fetcher)
    
    # Test The Odds API
    test_odds_api(fetcher)
    
    # Test team name normalization
    test_team_normalization(fetcher)

def test_pandascore_matches(fetcher):
    print("\n" + "="*50)
    print("🕹️ TESTING PANDASCORE MATCHES API")
    print("="*50)
    
    start_time = time.time()
    matches = fetcher.fetch_live_matches()
    elapsed = time.time() - start_time
    
    print("\n📊 RESULTS:")
    print(f"Response time: {elapsed:.2f}s")
    print(f"Retrieved {len(matches)} matches")
    
    if not matches.empty:
        print("\nSample match:")
        print(matches.iloc[0].to_dict())
        
        # Data quality checks
        print("\n DATA QUALITY CHECKS:")
        print(f"Match ID valid: {matches.iloc[0]['match_id'] > 0}")
        print(f"team1 present: {bool(matches.iloc[0]['team1'])}")
        print(f"team2 present: {bool(matches.iloc[0]['team2'])}")
        print(f"Start time present: {bool(matches.iloc[0]['start_time'])}")
    else:
        print("Failed to retrieve matches")
        
    return matches

def test_odds_api(fetcher):
    print("\n" + "="*50)
    print("🎲 TESTING THE ODDS API")
    print("="*50)
    
    start_time = time.time()
    odds = fetcher.fetch_odds()
    elapsed = time.time() - start_time
    
    print(f"\n⏱️ Response time: {elapsed:.2f}s")
    print(f"📊 Retrieved {len(odds)} odds entries")
    
    if not odds.empty:
        print("\n✅ Sample odds entry:")
        print(odds.iloc[0].to_dict())
        
        # Data quality checks
        print("\n DATA QUALITY CHECKS:")
        print(f"Event ID valid: {bool(odds.iloc[0]['event_id'])}")
        print(f"Bookmaker present: {bool(odds.iloc[0]['bookmaker'])}")
        print(f"Team present: {bool(odds.iloc[0]['team'])}")
        print(f"Odds value: {odds.iloc[0]['odds']} (should be > 1.0)")
        print(f"Start time present: {bool(odds.iloc[0]['start_time'])}")
        
        # Check for multiple teams in events
        event_id = odds.iloc[0]['event_id']
        event_odds = odds[odds['event_id'] == event_id]
        teams = event_odds['team'].unique()
        print(f"Teams in event: {len(teams)} - {', '.join(teams)}")
    else:
        print("Failed to retrieve odds")
        
    return odds

def test_team_normalization(fetcher):
    print("\n" + "="*50)
    print("TESTING TEAM NAME NORMALIZATION")
    print("="*50)
    
    # Create test data
    test_data = pd.DataFrame({
        'team': ['Natus Vincere', 'Team Vitality', 'G2 Esports', 'FaZe Clan', 'FURIA Esports']
    })
    
    print("Test data before normalization:")
    print(test_data)
    
    # Apply normalization
    normalized = fetcher.normalize_team_names(test_data.copy())
    
    print("\nAfter normalization:")
    print(normalized)
    
    # Verify results
    expected = ['NAVI', 'Vitality', 'G2', 'FaZe', 'FURIA']
    actual = normalized['team'].tolist()
    
    if actual == expected:
        print("✅ Normalization successful!")
    else:
        print(f"Normalization failed. Expected {expected}, got {actual}")

def test_full_workflow(fetcher):
    print("\n" + "="*50)
    print("TESTING FULL WORKFLOW INTEGRATION")
    print("="*50)
    
    # Fetch data
    matches = fetcher.fetch_live_matches()
    odds = fetcher.fetch_odds()
    
    if matches.empty or odds.empty:
        print("Insufficient data for workflow test")
        return
        
    # Normalize names
    matches = fetcher.normalize_team_names(matches, 'team1')
    matches = fetcher.normalize_team_names(matches, 'team2')
    odds = fetcher.normalize_team_names(odds)
    
    # Create team pairs for matching
    matches['team_pair'] = matches.apply(
        lambda row: tuple(sorted([row['team1'], row['team2']])), 
        axis=1
    )
    
    # Group odds by event to create team pairs
    event_odds = odds.groupby('event_id').agg({
        'team': list,
        'start_time': 'first'
    }).reset_index()
    event_odds['team_pair'] = event_odds['team'].apply(
        lambda teams: tuple(sorted(teams)) if len(teams) >= 2 else None
    )
    
    # Merge datasets
    merged = pd.merge(
        matches,
        event_odds,
        on='team_pair',
        how='inner'
    )
    
    print(f"\n Found {len(merged)} matched events")
    
    if not merged.empty:
        print("\nSample matched event:")
        print(merged.iloc[0][['team1', 'team2', 'team_pair']])
        
        # Check if we can get individual odds
        event_id = merged.iloc[0]['event_id']
        event_odds = odds[odds['event_id'] == event_id]
        print(f"\nOdds for event {event_id}:")
        print(event_odds[['bookmaker', 'team', 'odds']])
    else:
        print("No matches found between matches and odds data")

if __name__ == "__main__":
    # Run tests
    matches = test_pandascore_matches(DataFetcher())
    odds = test_odds_api(DataFetcher())
    test_team_normalization(DataFetcher())
    
    # Only run workflow test if we have data
    if not matches.empty and not odds.empty:
        test_full_workflow(DataFetcher())