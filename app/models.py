from datetime import datetime

from flask_login import UserMixin

from app import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)   # full name shown on the profile; starts as the username
    # Added after the table existed (scripts/add_usernames.py adds the column, fills it for older accounts and adds
    # the unique index). Always stored lowercase; nullable in the database only so the column can be added in place.
    username = db.Column(db.String(20), unique=True, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def display_name(self):
        return self.username or self.name

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


class UserProfile(db.Model):
    """Optional personal details, one row per user (created on first save). A new table, so db.create_all() adds it."""
    __tablename__ = "user_profiles"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    phone = db.Column(db.String(20))
    college = db.Column(db.String(150))
    branch = db.Column(db.String(100))
    year_of_study = db.Column(db.Integer)      # 1-5
    graduation_year = db.Column(db.Integer)
    city = db.Column(db.String(80))
    linkedin_url = db.Column(db.String(200))
    github_url = db.Column(db.String(200))
    bio = db.Column(db.String(300))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("profile", uselist=False))


class UserAvatar(db.Model):
    """
    The profile picture, stored in the database as a re-encoded 256x256 JPEG (about 10-30 KB), not as a file:
    it survives a redeploy on a host with a throwaway disk, and re-encoding drops any metadata (EXIF, GPS) and
    anything that is not really an image. A new table, so db.create_all() adds it.
    """
    __tablename__ = "user_avatars"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    image = db.Column(db.LargeBinary, nullable=False)
    mime = db.Column(db.String(30), nullable=False, default="image/jpeg")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("avatar", uselist=False))


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


# The old Skill DNA Map tables (dsa_nodes, dsa_problems, user_dsa_activity, node_mastery, dsa_problem_framings,
# weakness_profiles, user_attempts) were removed when scenario code questions replaced the map. Their rows may still
# exist in an older database: scripts/drop_old_dsa_tables.py lists them and, with --drop, removes them.


class Resume(db.Model):
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    extracted_skills = db.Column(ARRAY(db.String))
    ai_feedback = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    # True for a resume saved by POST /resume/discover that no target path has been analyzed
    # against yet. latest_resume_analysis() skips these, so a "which path fits" upload never
    # gets paired with an older, unrelated skill gap. NULL/False = a normal analyzed resume.
    # Added after the table existed: ALTER TABLE resumes ADD COLUMN analysis_pending BOOLEAN DEFAULT FALSE.
    analysis_pending = db.Column(db.Boolean, default=False)

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
    steps = db.Column(db.JSON, nullable=False)             # {phases: [{phase_number, title, steps: [{step_number,
                                                            # global_step_index, title, description, subtopics,
                                                            # topic_refs, projects, more_topics}]}]} - more_topics is
                                                            # [{node_id, title}], this phase's remaining topics not in
                                                            # topic_refs, assigned to their nearest step by embedding
                                                            # similarity - older rows predate phases and are a flat
                                                            # list of steps (some also predate subtopics/topic_refs/
                                                            # projects/global_step_index/more_topics). Once
                                                            # /roadmap/<id>/resources has run (youtube_resources.py),
                                                            # each step also has "videos" ([{title, url, video_id,
                                                            # source: "roadmap.sh"|"youtube_search", topic}], KB-first
                                                            # then YouTube-search fallback) and "resources" ([{type:
                                                            # "official"|"course", title, url, topic}], KB-only) -
                                                            # "resource" ({title, url} of the first video, or None) is
                                                            # also still set, kept only for compatibility with pages
                                                            # that predate "videos"/"resources".
    retrieved_chunks = db.Column(db.JSON)                  # {phases: [{phase_number, title, queries, retrieved,
                                                            # steps}]} audit trail of what grounded each phase - older
                                                            # rows predate phases (a flat {queries, retrieved, steps}
                                                            # dict, or, older still, a flat [{source, score}] list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="generated_roadmaps")

    def __repr__(self):
        return f"<GeneratedRoadmap user={self.user_id} path={self.career_path}>"

class RoadmapProgress(db.Model):
    """
    Per-step completion state for a generated roadmap - one row per
    COMPLETED step; a step the student hasn't ticked has no row at all
    (not a row with completed=False), so "is this step done" is simply
    "does a row exist". step_index means whatever
    routes/roadmap.py's step_indexes() computed for that roadmap's shape
    at tick time (a phased roadmap's global_step_index, or an old flat
    roadmap's step_number) - this table doesn't care which shape produced
    it, only that it's stable for that one roadmap_id.
    """
    __tablename__ = "roadmap_progress"
    __table_args__ = (
        db.UniqueConstraint("user_id", "roadmap_id", "step_index", name="uq_progress_user_roadmap_step"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    roadmap_id = db.Column(db.Integer, db.ForeignKey("generated_roadmaps.id"), nullable=False)
    step_index = db.Column(db.Integer, nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="roadmap_progress")
    roadmap = db.relationship("GeneratedRoadmap", backref="progress_rows")

    def __repr__(self):
        return f"<RoadmapProgress user={self.user_id} roadmap={self.roadmap_id} step={self.step_index}>"

class JobListing(db.Model):
    __tablename__ = "job_listings"

    id = db.Column(db.Integer, primary_key=True)
    job_title = db.Column(db.String(300), nullable=False)
    location = db.Column(db.String(200))
    state = db.Column(db.String(100))
    locality = db.Column(db.String(200))
    annual_salary = db.Column(db.Float)              # None if unparseable
    salary_suspicious = db.Column(db.Boolean, default=False)
    career_paths = db.Column(ARRAY(db.String), default=[])  # tagged, not filtered
    source = db.Column(db.String(100), default="kaggle_india_jobs")

    def __repr__(self):
        return f"<JobListing {self.job_title!r}>"

class SurveyRespondent(db.Model):
    __tablename__ = "survey_respondents"

    id = db.Column(db.Integer, primary_key=True)
    dev_type = db.Column(db.String(200))
    career_path = db.Column(db.String(120))  # None if DevType didn't map
    years_code = db.Column(db.Float)
    work_exp = db.Column(db.Float)
    ed_level = db.Column(db.String(200))
    remote_work = db.Column(db.String(100))
    converted_comp_yearly = db.Column(db.Float)  # USD, None if not reported
    languages = db.Column(ARRAY(db.String), default=[])
    databases = db.Column(ARRAY(db.String), default=[])
    platforms = db.Column(ARRAY(db.String), default=[])
    webframes = db.Column(ARRAY(db.String), default=[])
    # Nullable, added later (scripts/add_survey_skill_columns.py): the 2025 survey's other
    # skill-like columns - IDEs/editors, SO tags (newer technologies), collaboration tools.
    dev_envs = db.Column(ARRAY(db.String))
    so_tags = db.Column(ARRAY(db.String))
    office_stack = db.Column(ARRAY(db.String))
    source = db.Column(db.String(100), default="so_survey_2025_india")

    def __repr__(self):
        return f"<SurveyRespondent id={self.id} career_path={self.career_path!r}>"

class ScenarioAttempt(db.Model):
    """One run through a scenario (scenario-based practice). Created on start, completed on submit."""
    __tablename__ = "scenario_attempts"
    __table_args__ = (db.Index("ix_scenario_attempts_user_scenario", "user_id", "scenario_id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    path = db.Column(db.String(100))
    scenario_id = db.Column(db.String(40))
    answers = db.Column(db.JSON)              # the submitted answers, keyed by question id
    score = db.Column(db.Integer)
    max_score = db.Column(db.Integer)
    passed = db.Column(db.Boolean)
    shuffle_seed = db.Column(db.Integer)      # same seed -> same option order on resume
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)     # NULL = unfinished

    user = db.relationship("User", backref="scenario_attempts")

    def __repr__(self):
        return f"<ScenarioAttempt user={self.user_id} scenario={self.scenario_id}>"


class PasswordResetToken(db.Model):
    """One "forgot password" link. Only the SHA-256 of the token is stored (the token itself exists only in the
    emailed link), it expires, and it works once. A new table, so db.create_all() adds it."""
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)

