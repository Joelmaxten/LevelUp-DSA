"""
Validates every scenario file in data/scenarios/ (or the directory given as the first argument).

Usage:
    PYTHONPATH=. python scripts/validate_scenarios.py [DIR]

Prints one block per file, then exits 1 if any file has an error (warnings never fail the run).
"""
import sys
from pathlib import Path

from app.pipeline.scenario_validator import load_and_validate

DEFAULT_DIR = Path("data/scenarios")


def main(argv):
    directory = Path(argv[1]) if len(argv) > 1 else DEFAULT_DIR
    files = sorted(directory.glob("*.json"))
    if not files:
        print(f"No scenario files in {directory}")
        return 1
    failed = 0
    for f in files:
        _, result = load_and_validate(f)
        status = "FAIL" if result["errors"] else "OK"
        print(f"{status}  {f.name}: {len(result['errors'])} error(s), {len(result['warnings'])} warning(s)")
        for e in result["errors"]:
            print(f"    ERROR   {e}")
        for w in result["warnings"]:
            print(f"    WARNING {w}")
        failed += bool(result["errors"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
