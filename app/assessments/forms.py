from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    DateTimeLocalField,
    DecimalField,
    IntegerField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.learning.forms import DOMAIN_CHOICES

TYPE_CHOICES = [
    ("mcq", "MCQ (auto-graded)"),
    ("coding", "Coding Test (manual)"),
    ("practical", "Practical Assignment (manual)"),
    ("project", "Project Review (manual)"),
]


class AssessmentForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Instructions", validators=[Optional(), Length(max=4000)])
    type = SelectField("Type", choices=TYPE_CHOICES, validators=[DataRequired()])
    domain = SelectField(
        "Domain", choices=[("", "— None —")] + DOMAIN_CHOICES, validators=[Optional()]
    )
    total_marks = IntegerField(
        "Total marks", default=100, validators=[DataRequired(), NumberRange(min=1)]
    )
    pass_percentage = DecimalField(
        "Pass %", default=40, places=2, validators=[DataRequired(), NumberRange(min=0, max=100)]
    )
    duration_minutes = IntegerField(
        "Duration (minutes)", validators=[Optional(), NumberRange(min=1)]
    )
    max_attempts = IntegerField(
        "Max attempts", default=3, validators=[DataRequired(), NumberRange(min=1, max=20)]
    )
    scheduled_at = DateTimeLocalField(
        "Scheduled at", format="%Y-%m-%dT%H:%M", validators=[Optional()]
    )
    submit = SubmitField("Save assessment")


class QuestionForm(FlaskForm):
    question_text = TextAreaField("Question", validators=[DataRequired(), Length(max=2000)])
    option_a = StringField("Option A", validators=[DataRequired(), Length(max=500)])
    option_b = StringField("Option B", validators=[DataRequired(), Length(max=500)])
    option_c = StringField("Option C", validators=[Optional(), Length(max=500)])
    option_d = StringField("Option D", validators=[Optional(), Length(max=500)])
    correct_option = SelectField(
        "Correct option",
        choices=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")],
        validators=[DataRequired()],
    )
    marks = IntegerField("Marks", default=1, validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField("Add question")


class AssignAssessmentForm(FlaskForm):
    employees = SelectMultipleField("Assign to", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Assign")


class SubmissionForm(FlaskForm):
    submission_url = StringField(
        "Submission link (repo / demo)", validators=[Optional(), Length(max=500)]
    )
    upload = FileField(
        "Upload file",
        validators=[
            Optional(),
            FileAllowed(
                ["pdf", "zip", "doc", "docx", "txt", "py", "ipynb", "md"],
                "Unsupported file type.",
            ),
        ],
    )
    submit = SubmitField("Submit")


class GradeForm(FlaskForm):
    score = DecimalField(
        "Score", places=2, validators=[DataRequired(), NumberRange(min=0)]
    )
    feedback = TextAreaField("Feedback", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Save grade")
