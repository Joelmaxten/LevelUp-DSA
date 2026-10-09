# Blind-solve review: Full-Stack Development

A model answered each question without seeing the key. Each disagreement below needs a human decision: the question may be ambiguous, or the key may be wrong.

| Scenario | Questions | Agreed | Disagreed | Note |
|---|---|---|---|---|
| fsd-1 | 4 | 4 | 0 | |
| fsd-2 | 4 | 4 | 0 | |
| fsd-3 | 5 | 5 | 0 | |
| fsd-4 | 4 | 4 | 0 | |
| fsd-5 | 5 | 4 | 1 | |
| **Total** | **22** | **21** | **1** | |

## Disagreements

### fsd-5-q1 (order)

**Question:** Put these steps in order to rename customers.phone to mobile_number with no downtime during rolling deploys.

**Key answer:** a (Add a nullable mobile_number column alongside phone); b (Deploy code that writes to both columns and still reads phone); c (Backfill mobile_number from phone for all existing rows); d (Deploy code that reads mobile_number while still writing both); e (Once no old version runs, stop writing phone and drop the column)

**Model answer:** a (Add a nullable mobile_number column alongside phone); c (Backfill mobile_number from phone for all existing rows); b (Deploy code that writes to both columns and still reads phone); d (Deploy code that reads mobile_number while still writing both); e (Once no old version runs, stop writing phone and drop the column)

**key_justification:** Expand, migrate, then contract: every step must work with both the old and the new code.
