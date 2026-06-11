from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from app.learning.forms import DOMAIN_CHOICES, LEVEL_CHOICES


class SkillCatalogForm(FlaskForm):
    name = StringField("Skill name", validators=[DataRequired(), Length(max=120)])
    domain = SelectField(
        "Domain", choices=[("", "— None —")] + DOMAIN_CHOICES, validators=[Optional()]
    )
    submit = SubmitField("Add skill")


class EmployeeSkillForm(FlaskForm):
    skill_id = SelectField("Skill", coerce=int, validators=[DataRequired()])
    level = SelectField("Level", choices=LEVEL_CHOICES, validators=[DataRequired()])
    submit = SubmitField("Save")
