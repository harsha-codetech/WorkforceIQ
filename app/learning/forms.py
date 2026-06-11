from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    IntegerField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.models import DOMAINS, LEVELS

DOMAIN_CHOICES = [(d, d.replace("_", " ").title()) for d in DOMAINS]
LEVEL_CHOICES = [(l, l.title()) for l in LEVELS]
CONTENT_CHOICES = [
    ("youtube", "YouTube Video"),
    ("pdf", "PDF Document"),
    ("ppt", "PPT File"),
    ("internal", "Internal Training Content"),
]


class ModuleForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    category = StringField("Category", validators=[Optional(), Length(max=100)])
    domain = SelectField("Domain", choices=DOMAIN_CHOICES, validators=[DataRequired()])
    content_type = SelectField(
        "Content type", choices=CONTENT_CHOICES, validators=[DataRequired()]
    )
    content_url = StringField("YouTube URL", validators=[Optional(), Length(max=500)])
    upload = FileField(
        "Upload file",
        validators=[
            Optional(),
            FileAllowed(
                ["pdf", "ppt", "pptx", "doc", "docx", "zip", "txt", "md"],
                "Unsupported file type.",
            ),
        ],
    )
    duration_minutes = IntegerField(
        "Duration (minutes)", validators=[Optional(), NumberRange(min=1, max=100000)]
    )
    difficulty = SelectField("Difficulty", choices=LEVEL_CHOICES, validators=[DataRequired()])
    submit = SubmitField("Save module")


class AssignModuleForm(FlaskForm):
    employees = SelectMultipleField("Assign to", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Assign")
