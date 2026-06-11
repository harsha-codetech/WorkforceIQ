"""Idempotent demo data: one org, departments, users, content, activity."""
import random
from datetime import date, datetime, timedelta

from app.extensions import db
from app.models import (
    Assessment,
    AssessmentAssignment,
    AssessmentAttempt,
    AssessmentQuestion,
    Department,
    EmployeeSkill,
    Goal,
    LearningActivity,
    LearningModule,
    ModuleAssignment,
    LearningProgress,
    Organization,
    Skill,
    SkillHistory,
    User,
)
from app.utils.badges import evaluate_badges, seed_badges
from app.utils.scoring import recompute_all

DEFAULT_PW = "Password123"


def _get_or_create_user(org_id, **kw):
    user = User.query.filter_by(email=kw["email"]).first()
    if user:
        return user
    user = User(organization_id=org_id, **kw)
    user.set_password(DEFAULT_PW)
    db.session.add(user)
    db.session.flush()
    return user


def seed_demo_data():
    random.seed(42)
    seed_badges()

    org = Organization.query.filter_by(name="Acme Technologies").first()
    if not org:
        org = Organization(name="Acme Technologies")
        db.session.add(org)
        db.session.flush()

    dept_names = ["Engineering", "Data & Analytics", "Cloud & Security"]
    depts = {}
    for name in dept_names:
        d = Department.query.filter_by(organization_id=org.id, name=name).first()
        if not d:
            d = Department(organization_id=org.id, name=name)
            db.session.add(d)
            db.session.flush()
        depts[name] = d

    admin = _get_or_create_user(
        org.id, full_name="Alice Admin", email="admin@workforceiq.com", role="admin"
    )

    managers = {}
    for name, email, dept in [
        ("Marcus Manager", "manager.eng@workforceiq.com", "Engineering"),
        ("Maya Manager", "manager.data@workforceiq.com", "Data & Analytics"),
        ("Mike Manager", "manager.cloud@workforceiq.com", "Cloud & Security"),
    ]:
        m = _get_or_create_user(
            org.id, full_name=name, email=email, role="manager",
            department_id=depts[dept].id,
        )
        managers[dept] = m

    employees = []
    emp_specs = [
        ("John Doe", "john@workforceiq.com", "Engineering"),
        ("Jane Smith", "jane@workforceiq.com", "Engineering"),
        ("Raj Patel", "raj@workforceiq.com", "Data & Analytics"),
        ("Sara Lee", "sara@workforceiq.com", "Data & Analytics"),
        ("Tom Wong", "tom@workforceiq.com", "Cloud & Security"),
        ("Nina Park", "nina@workforceiq.com", "Cloud & Security"),
    ]
    for name, email, dept in emp_specs:
        e = _get_or_create_user(
            org.id, full_name=name, email=email, role="employee",
            department_id=depts[dept].id, manager_id=managers[dept].id,
        )
        employees.append(e)

    # Skills catalog
    skill_defs = [
        ("Python", "full_stack"), ("JavaScript", "full_stack"), ("SQL", "data_analytics"),
        ("AWS", "cloud_computing"), ("Machine Learning", "machine_learning"),
        ("Cybersecurity", "cybersecurity"), ("Communication", "soft_skills"),
    ]
    skills = {}
    for sname, dom in skill_defs:
        s = Skill.query.filter_by(name=sname).first()
        if not s:
            s = Skill(name=sname, domain=dom)
            db.session.add(s)
            db.session.flush()
        skills[sname] = s

    # Learning modules
    module_defs = [
        ("Python Fundamentals", "full_stack", "youtube",
         "https://www.youtube.com/watch?v=rfscVS0vtbw", 240, "beginner"),
        ("Advanced SQL", "data_analytics", "youtube",
         "https://www.youtube.com/watch?v=HXV3zeQKqGY", 180, "intermediate"),
        ("AWS Cloud Practitioner", "cloud_computing", "youtube",
         "https://www.youtube.com/watch?v=3hLmDS179YE", 300, "beginner"),
        ("Intro to Machine Learning", "machine_learning", "youtube",
         "https://www.youtube.com/watch?v=ukzFI9rgwfU", 200, "intermediate"),
        ("Security Essentials", "cybersecurity", "youtube",
         "https://www.youtube.com/watch?v=inWWhr5tnEA", 150, "beginner"),
    ]
    modules = []
    for title, dom, ctype, url, dur, diff in module_defs:
        m = LearningModule.query.filter_by(title=title).first()
        if not m:
            m = LearningModule(
                title=title, domain=dom, content_type=ctype, content_url=url,
                duration_minutes=dur, difficulty=diff, created_by=admin.id,
                category=dom.replace("_", " ").title(),
            )
            db.session.add(m)
            db.session.flush()
        modules.append(m)

    # MCQ assessment
    assessment = Assessment.query.filter_by(title="Python Basics Quiz").first()
    if not assessment:
        assessment = Assessment(
            title="Python Basics Quiz", description="Fundamentals of Python.",
            type="mcq", grading_mode="auto", domain="full_stack",
            total_marks=3, pass_percentage=40, duration_minutes=15,
            max_attempts=3, created_by=admin.id,
        )
        db.session.add(assessment)
        db.session.flush()
        qs = [
            ("Which keyword defines a function in Python?", "func", "def", "function",
             "lambda", "B"),
            ("What data type is [1, 2, 3]?", "tuple", "set", "list", "dict", "C"),
            ("Which operator is used for exponent?", "^", "**", "%", "//", "B"),
        ]
        for text, a, b, c, d, correct in qs:
            db.session.add(
                AssessmentQuestion(
                    assessment_id=assessment.id, question_text=text,
                    option_a=a, option_b=b, option_c=c, option_d=d,
                    correct_option=correct, marks=1,
                )
            )

    # Manual (project) assessment
    project = Assessment.query.filter_by(title="Capstone Project Review").first()
    if not project:
        project = Assessment(
            title="Capstone Project Review", description="Submit your capstone repo.",
            type="project", grading_mode="manual", domain="full_stack",
            total_marks=100, pass_percentage=50, max_attempts=2, created_by=admin.id,
        )
        db.session.add(project)
        db.session.flush()
    db.session.commit()

    levels = ["beginner", "intermediate", "advanced", "expert"]
    today = date.today()

    for idx, emp in enumerate(employees):
        # assign + progress modules
        for j, module in enumerate(modules):
            if not ModuleAssignment.query.filter_by(
                module_id=module.id, employee_id=emp.id
            ).first():
                db.session.add(
                    ModuleAssignment(
                        module_id=module.id, employee_id=emp.id, assigned_by=admin.id
                    )
                )
            lp = LearningProgress.query.filter_by(
                employee_id=emp.id, module_id=module.id
            ).first()
            if not lp:
                done = (idx + j) % 3 != 0
                lp = LearningProgress(
                    employee_id=emp.id, module_id=module.id,
                    status="completed" if done else "in_progress",
                    watch_percentage=100 if done else random.randint(20, 80),
                    watch_seconds=random.randint(1800, 9000),
                    is_completed=done,
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow() if done else None,
                    last_activity_at=datetime.utcnow(),
                )
                db.session.add(lp)

        # learning activity (consistency)
        for back in range(0, 20, max(1, (idx % 3) + 1)):
            d = today - timedelta(days=back)
            if not LearningActivity.query.filter_by(
                employee_id=emp.id, activity_date=d
            ).first():
                db.session.add(
                    LearningActivity(employee_id=emp.id, activity_date=d,
                                     active_minutes=random.randint(15, 90))
                )

        # skills
        for k, (sname, _) in enumerate(skill_defs[: 3 + (idx % 3)]):
            if not EmployeeSkill.query.filter_by(
                employee_id=emp.id, skill_id=skills[sname].id
            ).first():
                lvl = levels[(idx + k) % 4]
                db.session.add(
                    EmployeeSkill(employee_id=emp.id, skill_id=skills[sname].id, level=lvl)
                )
                db.session.add(
                    SkillHistory(employee_id=emp.id, skill_id=skills[sname].id, level=lvl)
                )

        # goals
        if not Goal.query.filter_by(employee_id=emp.id).first():
            db.session.add(
                Goal(
                    employee_id=emp.id, title="Complete Python module", type="weekly",
                    status="completed" if idx % 2 == 0 else "in_progress",
                    start_date=today - timedelta(days=5), due_date=today + timedelta(days=2),
                    completed_at=datetime.utcnow() if idx % 2 == 0 else None,
                )
            )
            db.session.add(
                Goal(
                    employee_id=emp.id, title="Earn AWS certification", type="monthly",
                    status="completed" if idx % 3 == 0 else "pending",
                    start_date=today - timedelta(days=10), due_date=today + timedelta(days=20),
                    completed_at=datetime.utcnow() if idx % 3 == 0 else None,
                )
            )

        # MCQ attempts (reattempt improvement)
        if not AssessmentAttempt.query.filter_by(
            assessment_id=assessment.id, employee_id=emp.id
        ).first():
            if not AssessmentAssignment.query.filter_by(
                assessment_id=assessment.id, employee_id=emp.id
            ).first():
                db.session.add(
                    AssessmentAssignment(
                        assessment_id=assessment.id, employee_id=emp.id,
                        assigned_by=admin.id, status="graded",
                    )
                )
            base = 50 + idx * 5
            for attempt_no, pct in enumerate([base, min(base + 20, 100)], start=1):
                db.session.add(
                    AssessmentAttempt(
                        assessment_id=assessment.id, employee_id=emp.id,
                        attempt_number=attempt_no, started_at=datetime.utcnow(),
                        submitted_at=datetime.utcnow(), time_taken_seconds=300,
                        score=round(pct / 100 * 3, 2), percentage=pct,
                        result="pass" if pct >= 40 else "fail", status="graded",
                    )
                )

    db.session.commit()

    for emp in employees:
        evaluate_badges(emp.id)
    recompute_all("monthly")
    db.session.commit()
