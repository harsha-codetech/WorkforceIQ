from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError


class GoalForm(FlaskForm):
    title = StringField("Goal", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Details", validators=[Optional(), Length(max=1000)])
    type = SelectField(
        "Type",
        choices=[("weekly", "Weekly"), ("monthly", "Monthly")],
        validators=[DataRequired()],
    )
    start_date = DateField("Start date", validators=[DataRequired()])
    due_date = DateField("Due date", validators=[DataRequired()])
    submit = SubmitField("Save goal")

    def validate_due_date(self, field):
        if self.start_date.data and field.data and field.data < self.start_date.data:
            raise ValidationError("Due date cannot be before the start date.")
