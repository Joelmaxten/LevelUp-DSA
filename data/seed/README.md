# Seed data for a fresh clone

The app needs two database tables that are filled from large CSV files which are not in git:

| Table | What | Used by |
|---|---|---|
| `survey_respondents` | Stack Overflow Developer Survey 2025, India only (2,547 rows) | resume skill vocabulary, required skills per path |
| `job_listings` | Processed India jobs data (835 rows) | salary insights |

Without `survey_respondents` the resume analyzer finds no skills.

## Owner (has the data): export once
    PYTHONPATH=. python scripts/export_seed_data.py
This writes `survey_respondents.jsonl.gz` and `job_listings.jsonl.gz` here. They are git-ignored until you decide the
data may be published (Stack Overflow survey data is ODbL: attribution and share-alike; check the jobs dataset licence).
Share the two files privately (never `.env`).

## Teammate: load
Copy the two files into this folder, then:
    PYTHONPATH=. python scripts/setup_dev.py
