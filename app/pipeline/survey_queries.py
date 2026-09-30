"""
Query helper bridging the 15 career paths to survey_respondents.dev_type.

survey_respondents.career_path still holds the OLD 10 path names -
so_survey_processor.py (which wrote it) is untouched in this stage, per
scope. Filtering on that stale column with a new path name silently
returns nothing for 12 of the 15 paths. respondents_for_path() instead
filters on dev_type (a controlled-vocabulary field, kept raw) against
career_path_registry.py's SURVEY_DEVTYPES mapping - a read-time query
translation, not a rewrite of the stored data.
"""

from app.models import SurveyRespondent
from app.pipeline.career_path_registry import SURVEY_DEVTYPES


def respondents_for_path(career_path):
    """
    A SQLAlchemy query (not yet executed) of every SurveyRespondent whose
    dev_type is one of `career_path`'s mapped DevType values. A DevType
    listed under two paths (e.g. "AI/ML engineer", mapped to both AI
    Engineering and Machine Learning Engineering - the survey has no finer
    split) counts as a respondent for both. A path with no mapped DevTypes
    still gets a valid query that matches nothing, so callers can call
    .all()/.count() unconditionally.
    """
    devtypes = SURVEY_DEVTYPES.get(career_path, [])
    return SurveyRespondent.query.filter(SurveyRespondent.dev_type.in_(devtypes))
