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

from app.models import DOMAINS, LEVELS, RESOURCE_TYPES

DOMAIN_CHOICES = [(d, d.replace("_", " ").title()) for d in DOMAINS]
LEVEL_CHOICES = [(l, l.title()) for l in LEVELS]
CONTENT_CHOICES = [
    ("youtube", "YouTube Video"),
    ("pdf", "PDF Document"),
    ("ppt", "PPT File"),
    ("internal", "Internal Training Content"),
]
RESOURCE_CHOICES = [
    ("youtube", "YouTube Video"),
    ("mp4", "MP4 Video"),
    ("pdf", "PDF Document"),
    ("ppt", "PPT / Slides"),
    ("assignment", "Assignment / Exercise"),
    ("link", "External Link"),
]


class ModuleForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    category = StringField("Category", validators=[Optional(), Length(max=100)])
    domain = SelectField("Skill Domain", choices=DOMAIN_CHOICES, validators=[DataRequired()])
    domain_id = SelectField("Learning Domain (optional)", coerce=int, validators=[Optional()])
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
    thumbnail = FileField(
        "Thumbnail image",
        validators=[
            Optional(),
            FileAllowed(["jpg", "jpeg", "png", "webp"], "Images only."),
        ],
    )
    duration_minutes = IntegerField(
        "Duration (minutes)", validators=[Optional(), NumberRange(min=1, max=100000)]
    )
    difficulty = SelectField("Difficulty", choices=LEVEL_CHOICES, validators=[DataRequired()])
    submit = SubmitField("Save module")


class DomainForm(FlaskForm):
    name = StringField("Domain name", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=1000)])
    banner_image = FileField(
        "Banner image (wide, 1280×400)",
        validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "webp"], "Images only.")],
    )
    thumbnail = FileField(
        "Thumbnail (square, 400×400)",
        validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "webp"], "Images only.")],
    )
    submit = SubmitField("Save domain")


class ResourceForm(FlaskForm):
    title = StringField("Resource title", validators=[DataRequired(), Length(max=200)])
    resource_type = SelectField(
        "Type", choices=RESOURCE_CHOICES, validators=[DataRequired()]
    )
    video_url = StringField("URL (YouTube / external link)", validators=[Optional(), Length(max=500)])
    upload = FileField(
        "Upload file",
        validators=[
            Optional(),
            FileAllowed(
                ["pdf", "ppt", "pptx", "mp4", "doc", "docx", "zip", "txt"],
                "Unsupported file type.",
            ),
        ],
    )
    duration_minutes = IntegerField(
        "Duration (minutes)", validators=[Optional(), NumberRange(min=1, max=100000)]
    )
    submit = SubmitField("Add resource")


class AssignModuleForm(FlaskForm):
    employees = SelectMultipleField("Assign to", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Assign")
