from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager

DOMAINS = (
    "full_stack",
    "data_science",
    "data_analytics",
    "cybersecurity",
    "cloud_computing",
    "machine_learning",
    "soft_skills",
)
LEVELS = ("beginner", "intermediate", "advanced", "expert")
RESOURCE_TYPES = ("youtube", "mp4", "pdf", "ppt", "assignment", "link")


# BigInteger auto-increment works on MySQL natively; on SQLite (tests) it must
# fall back to INTEGER for rowid auto-increment to kick in.
BIGINT = db.BigInteger().with_variant(db.Integer, "sqlite")


def _enum(*values):
    return db.Enum(*values, validate_strings=True)


# --------------------------------------------------------------------------- #
# Identity & organization
# --------------------------------------------------------------------------- #
class Organization(db.Model):
    __tablename__ = "organizations"
    id = db.Column(BIGINT, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    departments = db.relationship("Department", backref="organization", lazy=True)


class Department(db.Model):
    __tablename__ = "departments"
    __table_args__ = (db.UniqueConstraint("organization_id", "name", name="uq_dept_name"),)
    id = db.Column(BIGINT, primary_key=True)
    organization_id = db.Column(
        db.BigInteger, db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(BIGINT, primary_key=True)
    organization_id = db.Column(
        db.BigInteger, db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    department_id = db.Column(
        db.BigInteger, db.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    manager_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    role = db.Column(_enum("admin", "manager", "employee"), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(190), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(_enum("active", "inactive"), default="active", nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    department = db.relationship("Department", foreign_keys=[department_id])
    manager = db.relationship("User", remote_side=[id], backref="team_members")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_manager(self):
        return self.role == "manager"

    @property
    def is_employee(self):
        return self.role == "employee"

    @property
    def is_active(self):  # consumed by Flask-Login
        return self.status == "active"

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class PasswordReset(db.Model):
    __tablename__ = "password_resets"
    id = db.Column(BIGINT, primary_key=True)
    user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# --------------------------------------------------------------------------- #
# Learning
# --------------------------------------------------------------------------- #
class LearningModule(db.Model):
    __tablename__ = "learning_modules"
    id = db.Column(BIGINT, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    domain = db.Column(_enum(*DOMAINS), nullable=False)
    domain_id = db.Column(
        db.BigInteger, db.ForeignKey("domains.id", ondelete="SET NULL"), nullable=True
    )
    content_type = db.Column(_enum("youtube", "pdf", "ppt", "internal"), nullable=False)
    content_url = db.Column(db.String(500))
    file_key = db.Column(db.String(500))
    thumbnail_key = db.Column(db.String(500))
    duration_minutes = db.Column(db.Integer)
    difficulty = db.Column(_enum(*LEVELS), default="beginner", nullable=False)
    created_by = db.Column(BIGINT, db.ForeignKey("users.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    resources = db.relationship(
        "ModuleResource", backref="module", lazy=True,
        order_by="ModuleResource.display_order", cascade="all, delete-orphan"
    )

    @property
    def is_video(self):
        return self.content_type == "youtube"


class ModuleAssignment(db.Model):
    __tablename__ = "module_assignments"
    __table_args__ = (db.UniqueConstraint("module_id", "employee_id", name="uq_ma"),)
    id = db.Column(BIGINT, primary_key=True)
    module_id = db.Column(
        db.BigInteger, db.ForeignKey("learning_modules.id", ondelete="CASCADE"), nullable=False
    )
    employee_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    assigned_by = db.Column(BIGINT, db.ForeignKey("users.id"), nullable=False)
    due_date = db.Column(db.Date)
    status = db.Column(
        _enum("assigned", "in_progress", "completed"), default="assigned", nullable=False
    )
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    module = db.relationship("LearningModule")


class LearningProgress(db.Model):
    __tablename__ = "learning_progress"
    __table_args__ = (db.UniqueConstraint("employee_id", "module_id", name="uq_lp"),)
    id = db.Column(BIGINT, primary_key=True)
    employee_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    module_id = db.Column(
        db.BigInteger, db.ForeignKey("learning_modules.id", ondelete="CASCADE"), nullable=False
    )
    status = db.Column(
        _enum("not_started", "in_progress", "completed"), default="not_started", nullable=False
    )
    watch_percentage = db.Column(db.Numeric(5, 2), default=0, nullable=False)
    watch_seconds = db.Column(db.Integer, default=0, nullable=False)
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    last_activity_at = db.Column(db.DateTime)

    module = db.relationship("LearningModule")


class LearningActivity(db.Model):
    __tablename__ = "learning_activity"
    __table_args__ = (db.UniqueConstraint("employee_id", "activity_date", name="uq_la"),)
    id = db.Column(BIGINT, primary_key=True)
    employee_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    activity_date = db.Column(db.Date, nullable=False)
    active_minutes = db.Column(db.Integer, default=0, nullable=False)


class Domain(db.Model):
    __tablename__ = "domains"
    id = db.Column(BIGINT, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text)
    banner_image_key = db.Column(db.String(500))
    thumbnail_key = db.Column(db.String(500))
    created_by = db.Column(BIGINT, db.ForeignKey("users.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    modules = db.relationship(
        "LearningModule", foreign_keys="LearningModule.domain_id",
        backref="lms_domain", lazy="dynamic"
    )


class ModuleResource(db.Model):
    __tablename__ = "module_resources"
    id = db.Column(BIGINT, primary_key=True)
    module_id = db.Column(
        db.BigInteger, db.ForeignKey("learning_modules.id", ondelete="CASCADE"), nullable=False
    )
    title = db.Column(db.String(200), nullable=False)
    resource_type = db.Column(_enum(*RESOURCE_TYPES), nullable=False)
    video_url = db.Column(db.String(500))
    file_key = db.Column(db.String(500))
    duration_minutes = db.Column(db.Integer)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ResourceProgress(db.Model):
    __tablename__ = "resource_progress"
    __table_args__ = (db.UniqueConstraint("employee_id", "resource_id", name="uq_rp"),)
    id = db.Column(BIGINT, primary_key=True)
    employee_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    resource_id = db.Column(
        db.BigInteger, db.ForeignKey("module_resources.id", ondelete="CASCADE"), nullable=False
    )
    progress_percentage = db.Column(db.Numeric(5, 2), default=0, nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    last_activity_at = db.Column(db.DateTime)


# --------------------------------------------------------------------------- #
# Assessments
# --------------------------------------------------------------------------- #
class Assessment(db.Model):
    __tablename__ = "assessments"
    id = db.Column(BIGINT, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type = db.Column(_enum("mcq", "coding", "practical", "project"), nullable=False)
    grading_mode = db.Column(_enum("auto", "manual"), nullable=False)
    domain = db.Column(_enum(*DOMAINS))
    total_marks = db.Column(db.Integer, default=100, nullable=False)
    pass_percentage = db.Column(db.Numeric(5, 2), default=40, nullable=False)
    duration_minutes = db.Column(db.Integer)
    scheduled_at = db.Column(db.DateTime)
    max_attempts = db.Column(db.Integer, default=3, nullable=False)
    created_by = db.Column(BIGINT, db.ForeignKey("users.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    questions = db.relationship(
        "AssessmentQuestion", backref="assessment", lazy=True, cascade="all, delete-orphan"
    )


class AssessmentQuestion(db.Model):
    __tablename__ = "assessment_questions"
    id = db.Column(BIGINT, primary_key=True)
    assessment_id = db.Column(
        db.BigInteger, db.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(500))
    option_b = db.Column(db.String(500))
    option_c = db.Column(db.String(500))
    option_d = db.Column(db.String(500))
    correct_option = db.Column(_enum("A", "B", "C", "D"))
    marks = db.Column(db.Integer, default=1, nullable=False)


class AssessmentAssignment(db.Model):
    __tablename__ = "assessment_assignments"
    __table_args__ = (db.UniqueConstraint("assessment_id", "employee_id", name="uq_aa"),)
    id = db.Column(BIGINT, primary_key=True)
    assessment_id = db.Column(
        db.BigInteger, db.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    employee_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    assigned_by = db.Column(BIGINT, db.ForeignKey("users.id"), nullable=False)
    due_date = db.Column(db.DateTime)
    status = db.Column(
        _enum("assigned", "in_progress", "submitted", "graded"),
        default="assigned",
        nullable=False,
    )
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    assessment = db.relationship("Assessment")


class AssessmentAttempt(db.Model):
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        db.UniqueConstraint(
            "assessment_id", "employee_id", "attempt_number", name="uq_att"
        ),
    )
    id = db.Column(BIGINT, primary_key=True)
    assessment_id = db.Column(
        db.BigInteger, db.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    employee_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number = db.Column(db.Integer, default=1, nullable=False)
    started_at = db.Column(db.DateTime)
    submitted_at = db.Column(db.DateTime)
    time_taken_seconds = db.Column(db.Integer)
    score = db.Column(db.Numeric(6, 2))
    percentage = db.Column(db.Numeric(5, 2))
    result = db.Column(_enum("pass", "fail"))
    status = db.Column(
        _enum("in_progress", "submitted", "graded"), default="in_progress", nullable=False
    )
    submission_file_key = db.Column(db.String(500))
    submission_url = db.Column(db.String(500))
    graded_by = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    graded_at = db.Column(db.DateTime)
    feedback = db.Column(db.Text)

    assessment = db.relationship("Assessment")
    employee = db.relationship("User", foreign_keys=[employee_id])


class AssessmentAnswer(db.Model):
    __tablename__ = "assessment_answers"
    __table_args__ = (db.UniqueConstraint("attempt_id", "question_id", name="uq_ans"),)
    id = db.Column(BIGINT, primary_key=True)
    attempt_id = db.Column(
        db.BigInteger, db.ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False
    )
    question_id = db.Column(
        db.BigInteger, db.ForeignKey("assessment_questions.id", ondelete="CASCADE"), nullable=False
    )
    selected_option = db.Column(_enum("A", "B", "C", "D"))
    is_correct = db.Column(db.Boolean)
    marks_awarded = db.Column(db.Numeric(6, 2), default=0, nullable=False)


# --------------------------------------------------------------------------- #
# Goals & skills
# --------------------------------------------------------------------------- #
class Goal(db.Model):
    __tablename__ = "goals"
    id = db.Column(BIGINT, primary_key=True)
    employee_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type = db.Column(_enum("weekly", "monthly"), nullable=False)
    status = db.Column(
        _enum("pending", "in_progress", "completed", "missed"), default="pending", nullable=False
    )
    start_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Skill(db.Model):
    __tablename__ = "skills"
    id = db.Column(BIGINT, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    domain = db.Column(_enum(*DOMAINS))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class EmployeeSkill(db.Model):
    __tablename__ = "employee_skills"
    __table_args__ = (db.UniqueConstraint("employee_id", "skill_id", name="uq_es"),)
    id = db.Column(BIGINT, primary_key=True)
    employee_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    skill_id = db.Column(
        db.BigInteger, db.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    level = db.Column(_enum(*LEVELS), nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    skill = db.relationship("Skill")


class SkillHistory(db.Model):
    __tablename__ = "skill_history"
    id = db.Column(BIGINT, primary_key=True)
    employee_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    skill_id = db.Column(
        db.BigInteger, db.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    level = db.Column(_enum(*LEVELS), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# --------------------------------------------------------------------------- #
# Intelligence & engagement
# --------------------------------------------------------------------------- #
class PerformanceScore(db.Model):
    __tablename__ = "performance_scores"
    __table_args__ = (
        db.UniqueConstraint("employee_id", "period_type", "period_start", name="uq_ps"),
    )
    id = db.Column(BIGINT, primary_key=True)
    employee_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    period_type = db.Column(_enum("weekly", "monthly", "quarterly"), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    learning_score = db.Column(db.Numeric(5, 2), nullable=False)
    assessment_score = db.Column(db.Numeric(5, 2), nullable=False)
    goal_score = db.Column(db.Numeric(5, 2), nullable=False)
    skill_growth_score = db.Column(db.Numeric(5, 2), nullable=False)
    consistency_score = db.Column(db.Numeric(5, 2), nullable=False)
    overall_score = db.Column(db.Numeric(5, 2), nullable=False)
    category = db.Column(
        _enum("elite", "high_performer", "good", "needs_improvement", "critical"),
        nullable=False,
    )
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    employee = db.relationship("User")


class Badge(db.Model):
    __tablename__ = "badges"
    id = db.Column(BIGINT, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.String(255))
    criteria = db.Column(db.String(255))
    icon_key = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class EmployeeBadge(db.Model):
    __tablename__ = "employee_badges"
    __table_args__ = (db.UniqueConstraint("employee_id", "badge_id", name="uq_eb"),)
    id = db.Column(BIGINT, primary_key=True)
    employee_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    badge_id = db.Column(
        db.BigInteger, db.ForeignKey("badges.id", ondelete="CASCADE"), nullable=False
    )
    awarded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    badge = db.relationship("Badge")


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(BIGINT, primary_key=True)
    user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type = db.Column(
        _enum(
            "new_module",
            "upcoming_assessment",
            "goal_deadline",
            "badge_awarded",
            "assessment_graded",
        ),
        nullable=False,
    )
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    channel = db.Column(_enum("email", "dashboard"), nullable=False)
    related_entity_type = db.Column(db.String(50))
    related_entity_id = db.Column(db.BigInteger)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ReportExport(db.Model):
    __tablename__ = "report_exports"
    id = db.Column(BIGINT, primary_key=True)
    requested_by = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    report_type = db.Column(_enum("employee", "team", "organization"), nullable=False)
    format = db.Column(_enum("pdf", "excel", "csv"), nullable=False)
    file_key = db.Column(db.String(500))
    status = db.Column(
        _enum("pending", "processing", "completed", "failed"), default="pending", nullable=False
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(BIGINT, primary_key=True)
    user_id = db.Column(
        db.BigInteger, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.BigInteger)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
