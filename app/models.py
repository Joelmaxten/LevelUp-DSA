from datetime import datetime

from flask_login import UserMixin

from app import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class CareerPath(db.Model):
    __tablename__ = "career_paths"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # "IT" or "non-IT"
    description = db.Column(db.Text)

    def __repr__(self):
        return f"<CareerPath {self.name}>"


class RoadmapStep(db.Model):
    __tablename__ = "roadmap_steps"

    id = db.Column(db.Integer, primary_key=True)
    career_path_id = db.Column(db.Integer, db.ForeignKey("career_paths.id"), nullable=False)
    step_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    resource_link = db.Column(db.String(500))
    is_free = db.Column(db.Boolean, default=True)

    career_path = db.relationship("CareerPath", backref="roadmap_steps")

    def __repr__(self):
        return f"<RoadmapStep {self.step_number}: {self.title}>"


class UserProgress(db.Model):
    __tablename__ = "user_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    step_id = db.Column(db.Integer, db.ForeignKey("roadmap_steps.id"), nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="progress")
    step = db.relationship("RoadmapStep", backref="completions")

    def __repr__(self):
        return f"<UserProgress user={self.user_id} step={self.step_id}>"

from sqlalchemy.dialects.postgresql import ARRAY


class DSANode(db.Model):
    __tablename__ = "dsa_nodes"

    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(120), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)  # e.g. "Easy", "Medium", "Hard"
    career_paths = db.Column(ARRAY(db.Integer), default=[])  # list of career_path IDs
    prerequisites = db.Column(ARRAY(db.Integer), default=[])  # list of prerequisite node IDs

    def __repr__(self):
        return f"<DSANode {self.topic}>"


class DSAProblem(db.Model):
    __tablename__ = "dsa_problems"

    id = db.Column(db.Integer, primary_key=True)
    node_id = db.Column(db.Integer, db.ForeignKey("dsa_nodes.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    test_cases = db.Column(db.JSON)  # list of {"input": ..., "expected_output": ...}
    points = db.Column(db.Integer, default=10)

    node = db.relationship("DSANode", backref="problems")

    def __repr__(self):
        return f"<DSAProblem {self.title}>"


class UserDSAActivity(db.Model):
    __tablename__ = "user_dsa_activity"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    problem_id = db.Column(db.Integer, db.ForeignKey("dsa_problems.id"), nullable=False)
    solved_at = db.Column(db.DateTime, default=datetime.utcnow)
    points_earned = db.Column(db.Integer, default=0)

    user = db.relationship("User", backref="dsa_activity")
    problem = db.relationship("DSAProblem", backref="activity_log")

    def __repr__(self):
        return f"<UserDSAActivity user={self.user_id} problem={self.problem_id}>"


class NodeMastery(db.Model):
    __tablename__ = "node_mastery"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    node_id = db.Column(db.Integer, db.ForeignKey("dsa_nodes.id"), nullable=False)
    xp_earned = db.Column(db.Integer, default=0)
    problems_solved = db.Column(db.Integer, default=0)
    mastery_level = db.Column(db.Float, default=0.0)  # e.g. 0.0-1.0, drives D3.js node brightness

    user = db.relationship("User", backref="node_mastery")
    node = db.relationship("DSANode", backref="mastery_records")

    def __repr__(self):
        return f"<NodeMastery user={self.user_id} node={self.node_id}>"