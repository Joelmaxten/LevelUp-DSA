"""
Seeds the Skill DNA Map: the ten CareerPath rows (if missing), the DSA topic nodes with
their prerequisite edges, and the canonical problems with their verified test cases,
all from app/pipeline/dsa_seed_data.py.

Safe to re-run: rows are matched on name / topic / (node, title) and updated in place,
so ids, and any NodeMastery / UserDSAActivity rows pointing at them, are preserved. It
never deletes: a node or problem removed from the seed file stays in the database.

Run:  python scripts/seed_dsa.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app import models
from app.pipeline.career_quiz_data import CAREER_PATHS
from app.pipeline.dsa_graph import topological_order
from app.pipeline.dsa_seed_data import NODES, POINTS_BY_DIFFICULTY, PROBLEMS

import scripts.verify_dsa_seed as verifier


def main():
    # Never seed data that fails its own checks (wrong expected output, cycle, ...).
    total = verifier.check_test_cases()
    verifier.check_structure()
    if verifier.failures:
        print("Seed data failed verification, nothing written:")
        for message in verifier.failures:
            print(" -", message)
        sys.exit(1)
    print(f"Seed data verified ({total} test cases).")

    app = create_app()
    with app.app_context():
        db.create_all()  # only creates tables that don't exist yet (e.g. dsa_problem_framings)

        # Career paths: DSANode.career_paths stores CareerPath ids, so the rows must exist.
        path_ids = {}
        for name in CAREER_PATHS:
            row = models.CareerPath.query.filter_by(name=name).first()
            if row is None:
                row = models.CareerPath(name=name, type="IT")
                db.session.add(row)
            path_ids[name] = row
        db.session.flush()
        path_ids = {name: row.id for name, row in path_ids.items()}

        # Nodes, pass 1: make sure every topic has a row (and so an id).
        nodes = {}
        for spec in NODES:
            node = models.DSANode.query.filter_by(topic=spec["topic"]).first()
            if node is None:
                node = models.DSANode(topic=spec["topic"], difficulty=spec["difficulty"])
                db.session.add(node)
            nodes[spec["topic"]] = node
        db.session.flush()

        # Pass 2: difficulty, career highlights and prerequisite ids.
        for spec in NODES:
            node = nodes[spec["topic"]]
            node.difficulty = spec["difficulty"]
            node.career_paths = sorted(path_ids[p] for p in spec["career_paths"])
            node.prerequisites = sorted(nodes[p].id for p in spec["prerequisites"])
        topological_order({n.id: list(n.prerequisites) for n in nodes.values()})  # DAG check on the real ids

        created = updated = 0
        for spec in PROBLEMS:
            node = nodes[spec["node"]]
            problem = models.DSAProblem.query.filter_by(node_id=node.id, title=spec["title"]).first()
            if problem is None:
                problem = models.DSAProblem(node_id=node.id, title=spec["title"])
                db.session.add(problem)
                created += 1
            else:
                updated += 1
            problem.description = spec["description"]
            problem.test_cases = spec["test_cases"]
            problem.points = POINTS_BY_DIFFICULTY[spec["difficulty"]]

        db.session.commit()
        print(f"CareerPath rows: {len(path_ids)}  |  nodes: {len(nodes)}  |  "
              f"problems: {created} created, {updated} updated")


if __name__ == "__main__":
    main()
