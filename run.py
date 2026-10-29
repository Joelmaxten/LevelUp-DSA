import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app()


def warn_if_data_missing():
    """The resume analyzer needs survey_respondents; say so loudly instead of quietly finding no skills."""
    try:
        from app import db
        from app.models import SurveyRespondent
        with app.app_context():
            empty = db.session.query(SurveyRespondent.id).first() is None
        if empty:
            print("\nWARNING: survey_respondents is empty, so resume analysis will find no skills.\n"
                  "         Run:  PYTHONPATH=. python scripts/setup_dev.py   (see data/seed/README.md)\n")
    except Exception:
        print("\nWARNING: could not read the database. Run:  PYTHONPATH=. python scripts/setup_dev.py\n")


if __name__ == "__main__" and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
    warn_if_data_missing()

if __name__ != "__main__":
    # Imported by a WSGI server (e.g. gunicorn run:app): warm up in the background.
    from app.pipeline.warmup import start_warmup
    start_warmup()

if __name__ == "__main__":
    # Under the dev reloader this file runs twice: a parent that only watches for edits
    # and a child (WERKZEUG_RUN_MAIN=true) that serves. Only the child needs the models.
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        from app.pipeline.warmup import start_warmup
        start_warmup()
    app.run(debug=True)