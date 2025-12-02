# Betting Rules Analysis & Recommendations

## Executive Summary

Analysis of 113 completed betting opportunities reveals several patterns and opportunities for improvement. Key findings:

- **Consecutive Draws Rule**: Excellent performance (76% win rate)
- **Top 5 Consecutive Losses Rule**: Good performance (66.7% win rate)
- **Consecutive Losses Rule**: Moderate performance (54.7% win rate) - **needs improvement**
- **Live Red Card Rule**: Poor performance (20% win rate) - **needs major review**

---

## Detailed Analysis

### 1. Overall Performance by Rule Type

| Rule | Total | Wins | Losses | Win Rate |
|------|-------|------|--------|----------|
| Consecutive Draws | 25 | 19 | 6 | **76.0%** ✅ |
| Top 5 Consecutive Losses | 9 | 6 | 3 | **66.7%** ✅ |
| Consecutive Losses | 64 | 35 | 29 | **54.7%** ⚠️ |
| Live Red Card | 15 | 3 | 12 | **20.0%** ❌ |

---

### 2. Consecutive Losses Rule - Rank Analysis

#### Performance by Team Rank

**Key Finding**: Teams in bottom positions (ranks 18-20) show 54.2% win rate, which is similar to the overall average. However, there are patterns worth exploring:

- **Ranks 14-16**: Lower win rates (40-44%)
- **Ranks 17, 19**: Higher win rates (75%)
- **Rank 20**: Low win rate (40%)

**Bottom 3 Ranks (18-20)**: 24 opportunities, 13 wins (54.2%), 11 losses

#### Recommendation 1: Filter Bottom Teams
**PROPOSED**: Exclude teams in the bottom 3 positions (e.g., ranks 18-20 in a 20-team league) from the Consecutive Losses Rule.

**Rationale**:
- Bottom teams often have fundamental quality issues, not just temporary form
- While win rate is 54.2%, it's not significantly better than overall average
- Filtering these out may improve overall rule quality

---

### 3. Opponent Strength Analysis (Consecutive Losses Rule)

| Opponent Strength | Total | Wins | Win Rate |
|------------------|-------|------|----------|
| Much weaker (+5+) | 4 | 2 | 50.0% |
| Weaker (+2 to +5) | 5 | 4 | **80.0%** ✅ |
| Similar (-2 to +2) | 8 | 4 | 50.0% |
| Stronger (-2 to -5) | 13 | 9 | **69.2%** ✅ |
| Much stronger (-5+) | 34 | 16 | **47.1%** ❌ |

#### Recommendation 2: Filter Strong Opponents
**PROPOSED**: Exclude matches where the team with consecutive losses faces a much stronger opponent (rank difference of -5 or more).

**Rationale**:
- Win rate drops to 47.1% when facing much stronger opponents
- This represents 34 opportunities (53% of all consecutive losses opportunities)
- Teams with consecutive losses are less likely to recover against significantly stronger opposition

---

### 4. Consecutive Losses Count Analysis

| Consecutive Losses | Total | Wins | Win Rate |
|--------------------|-------|------|----------|
| 3 losses | 38 | 20 | 52.6% |
| 4 losses | 13 | 9 | **69.2%** ✅ |
| 5 losses | 13 | 6 | 46.2% |

#### Recommendation 3: Consider Increasing Threshold
**PROPOSED**: Consider increasing the threshold from 3 to 4 consecutive losses, OR adjust confidence calculation to favor teams with exactly 4 losses.

**Rationale**:
- Teams with exactly 4 consecutive losses show 69.2% win rate
- Teams with 3 losses show only 52.6% win rate
- Teams with 5+ losses drop to 46.2% (possibly too many losses = fundamental issues)

**Alternative Approach**: Keep threshold at 3, but give higher confidence to teams with exactly 4 losses.

---

### 5. Confidence Score Effectiveness

| Confidence Range | Total | Wins | Win Rate |
|------------------|-------|------|----------|
| 0.5 (base) | 57 | 35 | 61.4% |
| 0.5-0.6 | 25 | 12 | 48.0% |
| 0.6-0.7 | 29 | 16 | 55.2% |
| 0.7+ | 2 | 0 | **0.0%** ❌ |

#### Recommendation 4: Review High Confidence Logic
**PROPOSED**: Investigate why opportunities with confidence > 0.7 have 0% win rate (2/2 lost).

**Rationale**:
- Very small sample size (only 2 opportunities)
- But 100% failure rate suggests the confidence calculation may be overconfident
- Review what factors lead to high confidence scores

---

### 6. Live Red Card Rule - Critical Issue

**Current Performance**: 3 wins / 15 opportunities = **20% win rate**

#### Recommendation 5: Major Review Required
**PROPOSED**: Complete review of Live Red Card Rule logic.

**Issues to Investigate**:
1. **Team Selection**: Are we betting on the correct team (team without red card)?
2. **Timing**: Is the rule being applied at the right moment in the match?
3. **Score Context**: The rule requires a draw score - is this the right condition?
4. **Confidence Calculation**: Current confidence scores may not reflect actual probability

**Potential Improvements**:
- Review match outcomes to see if teams without red cards actually won
- Consider match minute when red card occurred (early red cards may have different impact)
- Review if score being tied is the right condition (maybe consider goal difference)
- Consider team strength even with red card advantage

---

### 7. Consecutive Draws Rule - Excellent Performance

**Current Performance**: 19 wins / 25 opportunities = **76% win rate** ✅

**Status**: This rule is performing excellently. No changes recommended at this time.

---

### 8. Top 5 Consecutive Losses Rule - Good Performance

**Current Performance**: 6 wins / 9 opportunities = **66.7% win rate** ✅

**Status**: This rule is performing well. No changes recommended at this time.

---

## Summary of Recommendations

### High Priority

1. **Live Red Card Rule**: Complete review required (20% win rate)
   - Investigate team selection logic
   - Review timing and conditions
   - Consider removing or significantly modifying the rule

2. **Consecutive Losses Rule - Opponent Strength**: Filter out matches vs. much stronger opponents
   - Exclude when rank difference ≤ -5
   - Could improve win rate from 54.7% to potentially 60%+

### Medium Priority

3. **Consecutive Losses Rule - Bottom Teams**: Consider filtering bottom 3 teams
   - Exclude teams in bottom 3 positions
   - May improve overall rule quality

4. **Consecutive Losses Threshold**: Consider adjusting for 4-loss teams
   - Either increase threshold to 4 OR give higher confidence to 4-loss teams
   - Teams with exactly 4 losses show 69.2% win rate

### Low Priority

5. **High Confidence Scores**: Investigate why confidence > 0.7 fails
   - Small sample size but 100% failure rate
   - Review confidence calculation logic

---

## Implementation Priority

1. **Immediate**: Review and fix Live Red Card Rule (critical issue)
2. **Short-term**: Implement opponent strength filter for Consecutive Losses Rule
3. **Medium-term**: Consider bottom team filter and threshold adjustments
4. **Ongoing**: Monitor confidence score effectiveness as more data accumulates

---

## Data Quality Notes

- Total opportunities analyzed: 113
- Date range: September 2025 - November 2025
- Rules covered: consecutive_losses, consecutive_draws, top5_consecutive_losses, live_red_card
- All opportunities have completed outcomes (win/lose)

---

*Analysis generated: 2025-12-02*
*Script: `app/scripts/analyze_betting_opportunities.py`*
