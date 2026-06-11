from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField
from wtforms.validators import DataRequired, Optional


class ReportForm(FlaskForm):
    report_type = SelectField(
        "Report",
        choices=[
            ("employee", "Employee report"),
            ("team", "Team report"),
            ("organization", "Organization report"),
        ],
        validators=[DataRequired()],
    )
    employee_id = SelectField("Employee", coerce=int, validators=[Optional()])
    format = SelectField(
        "Format",
        choices=[("pdf", "PDF"), ("excel", "Excel"), ("csv", "CSV")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Generate")
