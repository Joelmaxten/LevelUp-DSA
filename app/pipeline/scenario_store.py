"""
Loads scenario files from data/scenarios/, validates each one and caches the result.

A file that fails validation (or cannot be read) is refused: it is treated as missing, so a broken file can
never be served. The cache is keyed by file modification time, so editing a file on disk is picked up on the
next call without a restart. Pure of Flask and the database.
"""
from pathlib import Path

from app.pipeline.scenario_validator import load_and_validate

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"

_directory = DEFAULT_DIR
_cache = {}   # file path -> (mtime_ns, data or None)


def set_directory(path):
    """For tests: read scenario files from another directory (None restores the default) and drop the cache."""
    global _directory
    _directory = Path(path) if path is not None else DEFAULT_DIR
    _cache.clear()


def _load(file):
    try:
        stamp = file.stat().st_mtime_ns
    except OSError:
        return None
    cached = _cache.get(file)
    if cached and cached[0] == stamp:
        return cached[1]
    data, result = load_and_validate(file)
    data = None if result["errors"] else data
    _cache[file] = (stamp, data)
    return data


def load_all():
    """{path name: validated file data} for every valid file. Invalid files are skipped."""
    out = {}
    if not _directory.is_dir():
        return out
    for file in sorted(_directory.glob("*.json")):
        data = _load(file)
        if data is not None and data["path"] not in out:
            out[data["path"]] = data
    return out


def list_paths():
    return list(load_all())


def get_path(path_name):
    """The validated file data for a career path, or None."""
    return load_all().get(path_name)


def find_scenario(scenario_id):
    """(path data, scenario) for a scenario id, or (None, None)."""
    for data in load_all().values():
        for scenario in data["scenarios"]:
            if scenario["id"] == scenario_id:
                return data, scenario
    return None, None


def slugify(path_name):
    """URL form of a career path name: Machine Learning Engineering -> machine-learning-engineering."""
    return "-".join("".join(c.lower() if c.isalnum() else " " for c in path_name).split())


def get_by_slug(slug):
    for name, data in load_all().items():
        if slugify(name) == slug:
            return data
    return None
