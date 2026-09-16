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

    def set_password(self, plain_password):
        import bcrypt
        self.password_hash = bcrypt.hashpw(
            plain_password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, plain_password):
        import bcrypt
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), self.password_hash.encode("utf-8")
        )

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

class Resume(db.Model):
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    extracted_skills = db.Column(ARRAY(db.String))
    ai_feedback = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="resumes")

    def __repr__(self):
        return f"<Resume user={self.user_id}>"


class SkillGap(db.Model):
    __tablename__ = "skill_gaps"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    missing_skills = db.Column(ARRAY(db.String))
    target_role = db.Column(db.String(120))
    salary_range = db.Column(db.String(80))

    user = db.relationship("User", backref="skill_gaps")

    def __repr__(self):
        return f"<SkillGap user={self.user_id} target={self.target_role}>"


class WeaknessProfile(db.Model):
    __tablename__ = "weakness_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    node_id = db.Column(db.Integer, db.ForeignKey("dsa_nodes.id"), nullable=False)
    weakness_score = db.Column(db.Float, default=0.0)
    is_bandit_node = db.Column(db.Boolean, default=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="weakness_profiles")
    node = db.relationship("DSANode", backref="weakness_profiles")

    def __repr__(self):
        return f"<WeaknessProfile user={self.user_id} node={self.node_id}>"


class UserAttempt(db.Model):
    __tablename__ = "user_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    node_id = db.Column(db.Integer, db.ForeignKey("dsa_nodes.id"), nullable=False)
    problem_id = db.Column(db.Integer, db.ForeignKey("dsa_problems.id"), nullable=False)
    time_taken = db.Column(db.Integer)  # seconds
    attempts_count = db.Column(db.Integer, default=1)
    hints_used = db.Column(db.Integer, default=0)
    is_correct = db.Column(db.Boolean, default=False)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="attempts")
    node = db.relationship("DSANode", backref="attempts")
    problem = db.relationship("DSAProblem", backref="attempts")

    def __repr__(self):
        return f"<UserAttempt user={self.user_id} problem={self.problem_id}>"

class CareerProfile(db.Model):
    __tablename__ = "career_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    career_ranking = db.Column(db.JSON, nullable=False)       # build_profile()'s "career_ranking" list
    conversation_signals = db.Column(db.JSON, nullable=False) # build_profile()'s "conversation_signals" dict
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="career_profiles")

    def __repr__(self):
        return f"<CareerProfile user={self.user_id} created={self.created_at}>"

class GeneratedRoadmap(db.Model):
    __tablename__ = "generated_roadmaps"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    career_path = db.Column(db.String(120), nullable=False)
    steps = db.Column(db.JSON, nullable=False)            # list of {step_number, title, description}
    retrieved_chunks = db.Column(db.JSON)                  # which KB chunks grounded this generation - audit trail
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="generated_roadmaps")

    def __repr__(self):
        return f"<GeneratedRoadmap user={self.user_id} path={self.career_path}>"