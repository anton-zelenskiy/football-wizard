"""Script to analyze completed betting opportunities and propose rule improvements"""
from collections import defaultdict
import csv
from pathlib import Path

import structlog


logger = structlog.get_logger()


def analyze_betting_opportunities(csv_file: str = 'betting_opportunities_analysis.csv'):
    """Analyze betting opportunities and propose improvements"""
    csv_path = Path(csv_file)

    if not csv_path.exists():
        logger.error(f'CSV file not found: {csv_path}')
        return

    opportunities = []
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            opportunities.append(row)

    logger.info(f'Analyzing {len(opportunities)} betting opportunities')

    # Analysis 1: Win/Lose rates by rule type
    print('\n' + '=' * 80)
    print('ANALYSIS 1: WIN/LOSE RATES BY RULE TYPE')
    print('=' * 80)

    rule_stats = defaultdict(lambda: {'win': 0, 'lose': 0, 'total': 0})

    for opp in opportunities:
        rule_slug = opp['rule_slug']
        outcome = opp['outcome']
        rule_stats[rule_slug]['total'] += 1
        if outcome == 'win':
            rule_stats[rule_slug]['win'] += 1
        elif outcome == 'lose':
            rule_stats[rule_slug]['lose'] += 1

    for rule_slug, stats in sorted(rule_stats.items()):
        win_rate = (stats['win'] / stats['total']) * 100 if stats['total'] > 0 else 0
        print(f'\n{rule_slug}:')
        print(f'  Total: {stats["total"]}')
        print(f'  Wins: {stats["win"]} ({stats["win"]/stats["total"]*100:.1f}%)')
        print(f'  Losses: {stats["lose"]} ({stats["lose"]/stats["total"]*100:.1f}%)')
        print(f'  Win Rate: {win_rate:.1f}%')

    # Analysis 2: Consecutive Losses Rule - Rank analysis
    print('\n' + '=' * 80)
    print('ANALYSIS 2: CONSECUTIVE LOSSES RULE - RANK ANALYSIS')
    print('=' * 80)

    consecutive_losses_opps = [
        opp for opp in opportunities if opp['rule_slug'] == 'consecutive_losses'
    ]

    # Group by team rank (need to determine league size)
    rank_outcomes = defaultdict(lambda: {'win': 0, 'lose': 0, 'total': 0, 'ranks': []})

    for opp in consecutive_losses_opps:
        team_analyzed = opp['team_analyzed']
        outcome = opp['outcome']

        # Find the rank of the team analyzed
        if team_analyzed == opp['home_team']:
            rank = opp['home_team_rank']
        else:
            rank = opp['away_team_rank']

        if rank != 'N/A':
            try:
                rank_int = int(rank)
                rank_outcomes[rank_int]['total'] += 1
                rank_outcomes[rank_int]['ranks'].append(rank_int)
                if outcome == 'win':
                    rank_outcomes[rank_int]['win'] += 1
                elif outcome == 'lose':
                    rank_outcomes[rank_int]['lose'] += 1
            except (ValueError, TypeError):
                pass

    print('\nConsecutive Losses Rule - Performance by Team Rank:')
    print('Rank | Total | Wins | Losses | Win Rate')
    print('-' * 50)

    for rank in sorted(rank_outcomes.keys()):
        stats = rank_outcomes[rank]
        win_rate = (stats['win'] / stats['total']) * 100 if stats['total'] > 0 else 0
        print(
            f'{rank:4d} | {stats["total"]:5d} | {stats["win"]:4d} | {stats["lose"]:6d} | {win_rate:6.1f}%'
        )

    # Identify bottom 3 ranks
    all_ranks = []
    for opp in consecutive_losses_opps:
        if opp['home_team_rank'] != 'N/A':
            try:
                all_ranks.append(int(opp['home_team_rank']))
            except (ValueError, TypeError):
                pass
        if opp['away_team_rank'] != 'N/A':
            try:
                all_ranks.append(int(opp['away_team_rank']))
            except (ValueError, TypeError):
                pass

    if all_ranks:
        max_rank = max(all_ranks)
        bottom_3_start = max_rank - 2

        print(f'\nBottom 3 ranks analysis (ranks {bottom_3_start}-{max_rank}):')
        bottom_3_stats = {'win': 0, 'lose': 0, 'total': 0}

        for opp in consecutive_losses_opps:
            team_analyzed = opp['team_analyzed']
            outcome = opp['outcome']

            if team_analyzed == opp['home_team']:
                rank = opp['home_team_rank']
            else:
                rank = opp['away_team_rank']

            if rank != 'N/A':
                try:
                    rank_int = int(rank)
                    if rank_int >= bottom_3_start:
                        bottom_3_stats['total'] += 1
                        if outcome == 'win':
                            bottom_3_stats['win'] += 1
                        elif outcome == 'lose':
                            bottom_3_stats['lose'] += 1
                except (ValueError, TypeError):
                    pass

        if bottom_3_stats['total'] > 0:
            win_rate = (bottom_3_stats['win'] / bottom_3_stats['total']) * 100
            print(f'  Total: {bottom_3_stats["total"]}')
            print(f'  Wins: {bottom_3_stats["win"]} ({win_rate:.1f}%)')
            print(f'  Losses: {bottom_3_stats["lose"]} ({(100-win_rate):.1f}%)')

    # Analysis 3: Confidence score effectiveness
    print('\n' + '=' * 80)
    print('ANALYSIS 3: CONFIDENCE SCORE EFFECTIVENESS')
    print('=' * 80)

    confidence_buckets = {
        '0.5': {'win': 0, 'lose': 0, 'total': 0},
        '0.5-0.6': {'win': 0, 'lose': 0, 'total': 0},
        '0.6-0.7': {'win': 0, 'lose': 0, 'total': 0},
        '0.7+': {'win': 0, 'lose': 0, 'total': 0},
    }

    for opp in opportunities:
        try:
            confidence = float(opp['confidence_score'])
            outcome = opp['outcome']

            if confidence == 0.5:
                bucket = '0.5'
            elif 0.5 < confidence <= 0.6:
                bucket = '0.5-0.6'
            elif 0.6 < confidence <= 0.7:
                bucket = '0.6-0.7'
            else:
                bucket = '0.7+'

            confidence_buckets[bucket]['total'] += 1
            if outcome == 'win':
                confidence_buckets[bucket]['win'] += 1
            elif outcome == 'lose':
                confidence_buckets[bucket]['lose'] += 1
        except (ValueError, TypeError):
            pass

    print('\nWin Rate by Confidence Score:')
    print('Confidence | Total | Wins | Losses | Win Rate')
    print('-' * 55)
    for bucket, stats in confidence_buckets.items():
        if stats['total'] > 0:
            win_rate = (stats['win'] / stats['total']) * 100
            print(
                f'{bucket:10s} | {stats["total"]:5d} | {stats["win"]:4d} | {stats["lose"]:6d} | {win_rate:6.1f}%'
            )

    # Analysis 4: Opponent rank difference analysis
    print('\n' + '=' * 80)
    print('ANALYSIS 4: OPPONENT RANK DIFFERENCE ANALYSIS (Consecutive Losses Rule)')
    print('=' * 80)

    rank_diff_stats = defaultdict(lambda: {'win': 0, 'lose': 0, 'total': 0})

    for opp in consecutive_losses_opps:
        team_analyzed = opp['team_analyzed']
        outcome = opp['outcome']

        try:
            home_rank = (
                int(opp['home_team_rank']) if opp['home_team_rank'] != 'N/A' else None
            )
            away_rank = (
                int(opp['away_team_rank']) if opp['away_team_rank'] != 'N/A' else None
            )

            if home_rank and away_rank:
                if team_analyzed == opp['home_team']:
                    team_rank = home_rank
                    opponent_rank = away_rank
                else:
                    team_rank = away_rank
                    opponent_rank = home_rank

                rank_diff = opponent_rank - team_rank  # Positive = opponent is weaker

                # Bucket the differences
                if rank_diff <= -5:
                    bucket = 'Opponent much stronger (-5+)'
                elif rank_diff <= -2:
                    bucket = 'Opponent stronger (-2 to -5)'
                elif rank_diff <= 2:
                    bucket = 'Similar strength (-2 to +2)'
                elif rank_diff <= 5:
                    bucket = 'Opponent weaker (+2 to +5)'
                else:
                    bucket = 'Opponent much weaker (+5+)'

                rank_diff_stats[bucket]['total'] += 1
                if outcome == 'win':
                    rank_diff_stats[bucket]['win'] += 1
                elif outcome == 'lose':
                    rank_diff_stats[bucket]['lose'] += 1
        except (ValueError, TypeError):
            pass

    print('\nWin Rate by Opponent Rank Difference:')
    print('Rank Difference | Total | Wins | Losses | Win Rate')
    print('-' * 60)
    for bucket, stats in sorted(rank_diff_stats.items()):
        if stats['total'] > 0:
            win_rate = (stats['win'] / stats['total']) * 100
            print(
                f'{bucket:30s} | {stats["total"]:5d} | {stats["win"]:4d} | {stats["lose"]:6d} | {win_rate:6.1f}%'
            )

    # Analysis 5: Consecutive losses count analysis
    print('\n' + '=' * 80)
    print('ANALYSIS 5: CONSECUTIVE LOSSES COUNT ANALYSIS')
    print('=' * 80)

    losses_count_stats = defaultdict(lambda: {'win': 0, 'lose': 0, 'total': 0})

    for opp in consecutive_losses_opps:
        team_analyzed = opp['team_analyzed']
        outcome = opp['outcome']

        if team_analyzed == opp['home_team']:
            losses = opp['home_consecutive_losses']
        else:
            losses = opp['away_consecutive_losses']

        if losses != 'N/A':
            try:
                losses_int = int(losses)
                losses_count_stats[losses_int]['total'] += 1
                if outcome == 'win':
                    losses_count_stats[losses_int]['win'] += 1
                elif outcome == 'lose':
                    losses_count_stats[losses_int]['lose'] += 1
            except (ValueError, TypeError):
                pass

    print('\nWin Rate by Consecutive Losses Count:')
    print('Losses | Total | Wins | Losses | Win Rate')
    print('-' * 50)
    for losses in sorted(losses_count_stats.keys()):
        stats = losses_count_stats[losses]
        win_rate = (stats['win'] / stats['total']) * 100 if stats['total'] > 0 else 0
        print(
            f'{losses:6d} | {stats["total"]:5d} | {stats["win"]:4d} | {stats["lose"]:6d} | {win_rate:6.1f}%'
        )

    # Analysis 6: Live Red Card Rule analysis
    print('\n' + '=' * 80)
    print('ANALYSIS 6: LIVE RED CARD RULE ANALYSIS')
    print('=' * 80)

    live_red_card_opps = [
        opp for opp in opportunities if opp['rule_slug'] == 'live_red_card'
    ]

    print(f'\nTotal Live Red Card opportunities: {len(live_red_card_opps)}')
    live_wins = sum(1 for opp in live_red_card_opps if opp['outcome'] == 'win')
    live_losses = sum(1 for opp in live_red_card_opps if opp['outcome'] == 'lose')

    if len(live_red_card_opps) > 0:
        win_rate = (live_wins / len(live_red_card_opps)) * 100
        print(f'Wins: {live_wins} ({win_rate:.1f}%)')
        print(f'Losses: {live_losses} ({(100-win_rate):.1f}%)')

    # Analysis 7: Consecutive Draws Rule analysis
    print('\n' + '=' * 80)
    print('ANALYSIS 7: CONSECUTIVE DRAWS RULE ANALYSIS')
    print('=' * 80)

    consecutive_draws_opps = [
        opp for opp in opportunities if opp['rule_slug'] == 'consecutive_draws'
    ]

    draws_wins = sum(1 for opp in consecutive_draws_opps if opp['outcome'] == 'win')
    draws_losses = sum(1 for opp in consecutive_draws_opps if opp['outcome'] == 'lose')

    print(f'\nTotal Consecutive Draws opportunities: {len(consecutive_draws_opps)}')
    if len(consecutive_draws_opps) > 0:
        win_rate = (draws_wins / len(consecutive_draws_opps)) * 100
        print(f'Wins: {draws_wins} ({win_rate:.1f}%)')
        print(f'Losses: {draws_losses} ({(100-win_rate):.1f}%)')

    # Summary and Recommendations
    print('\n' + '=' * 80)
    print('RECOMMENDATIONS')
    print('=' * 80)

    recommendations = []

    # Recommendation 1: Filter out bottom 3 teams for Consecutive Losses Rule
    if bottom_3_stats.get('total', 0) > 0:
        bottom_3_win_rate = (bottom_3_stats['win'] / bottom_3_stats['total']) * 100
        if bottom_3_win_rate < 50:
            recommendations.append(
                f"1. CONSECUTIVE LOSSES RULE: Filter out teams in bottom 3 positions "
                f"(ranks {bottom_3_start}-{max_rank}). Current win rate: {bottom_3_win_rate:.1f}% "
                f"({bottom_3_stats['win']}/{bottom_3_stats['total']}). These teams are too weak "
                f"and consecutive losses may indicate fundamental quality issues rather than "
                f"temporary form."
            )

    # Recommendation 2: Confidence score adjustments
    low_confidence_win_rate = (
        (confidence_buckets['0.5']['win'] / confidence_buckets['0.5']['total']) * 100
        if confidence_buckets['0.5']['total'] > 0
        else 0
    )
    if low_confidence_win_rate < 50:
        recommendations.append(
            f"2. CONFIDENCE SCORE: Consider filtering out opportunities with confidence = 0.5 "
            f"(base confidence only). Current win rate: {low_confidence_win_rate:.1f}% "
            f"({confidence_buckets['0.5']['win']}/{confidence_buckets['0.5']['total']}). "
            f"These may be too weak signals."
        )

    # Recommendation 3: Opponent strength consideration
    if rank_diff_stats:
        strong_opponent_stats = rank_diff_stats.get('Opponent much stronger (-5+)', {})
        if strong_opponent_stats.get('total', 0) > 0:
            strong_opp_win_rate = (
                strong_opponent_stats['win'] / strong_opponent_stats['total']
            ) * 100
            if strong_opp_win_rate < 50:
                recommendations.append(
                    f"3. OPPONENT STRENGTH: Consider filtering out matches where the team with "
                    f"consecutive losses faces a much stronger opponent (rank difference -5 or more). "
                    f"Current win rate: {strong_opp_win_rate:.1f}% "
                    f"({strong_opponent_stats['win']}/{strong_opponent_stats['total']})."
                )

    # Recommendation 4: Live Red Card Rule
    if len(live_red_card_opps) > 0:
        live_win_rate = (live_wins / len(live_red_card_opps)) * 100
        if live_win_rate < 40:
            recommendations.append(
                f'4. LIVE RED CARD RULE: Current win rate is {live_win_rate:.1f}% '
                f'({live_wins}/{len(live_red_card_opps)}). Consider reviewing the rule logic, '
                f'especially regarding which team to bet on and timing considerations.'
            )

    # Recommendation 5: Consecutive losses count threshold
    if losses_count_stats:
        losses_3 = losses_count_stats.get(3, {})
        losses_4_plus = {k: v for k, v in losses_count_stats.items() if k >= 4}
        if losses_3.get('total', 0) > 0 and losses_4_plus:
            losses_3_win_rate = (
                (losses_3['win'] / losses_3['total']) * 100
                if losses_3['total'] > 0
                else 0
            )
            losses_4_plus_total = sum(s['total'] for s in losses_4_plus.values())
            losses_4_plus_wins = sum(s['win'] for s in losses_4_plus.values())
            losses_4_plus_win_rate = (
                (losses_4_plus_wins / losses_4_plus_total) * 100
                if losses_4_plus_total > 0
                else 0
            )

            if losses_4_plus_win_rate > losses_3_win_rate:
                recommendations.append(
                    f'5. CONSECUTIVE LOSSES THRESHOLD: Teams with 4+ consecutive losses have '
                    f'better win rate ({losses_4_plus_win_rate:.1f}%) than teams with exactly 3 '
                    f'losses ({losses_3_win_rate:.1f}%). Consider increasing the threshold to 4 '
                    f'or adjusting confidence calculation based on loss count.'
                )

    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f'\n{rec}')
    else:
        print('\nNo specific recommendations based on current data patterns.')

    print('\n' + '=' * 80)


if __name__ == '__main__':
    import sys

    csv_file = (
        sys.argv[1] if len(sys.argv) > 1 else 'betting_opportunities_analysis.csv'
    )
    analyze_betting_opportunities(csv_file)
