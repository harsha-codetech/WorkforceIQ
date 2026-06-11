from flask_wtf import FlaskForm
from wtforms import (
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, Email, Length, Optional


class DepartmentForm(FlaskForm):
    name = StringField("Department name", validators=[DataRequired(), Length(max=150)])
    submit = SubmitField("Save")


class UserForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=150)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=190)])
    role = SelectField(
        "Role",
        choices=[("employee", "Employee"), ("manager", "Manager"), ("admin", "Admin")],
        validators=[DataRequired()],
    )
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    manager_id = SelectField("Manager", coerce=int, validators=[Optional()])
    status = SelectField(
        "Status", choices=[("active", "Active"), ("inactive", "Inactive")]
    )
    password = PasswordField("Password", validators=[Optional(), Length(min=8, max=128)])
    submit = SubmitField("Save")
