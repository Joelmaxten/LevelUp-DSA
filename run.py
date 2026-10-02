import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app()

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