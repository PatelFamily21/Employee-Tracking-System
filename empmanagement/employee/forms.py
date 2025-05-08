from tkinter import Widget
from django import forms
from .models import WorkAssignments, Requests, Employee

from datetime import datetime, timezone, time
from django.utils import timezone
# employee/forms.py
from django import forms
from .models import PerformanceReviewTemplate, ReviewQuestion, PerformanceReview, ReviewResponse

from django import forms
from .models import PerformanceReviewTemplate, ReviewQuestion, PerformanceReview, ReviewResponse, Department, Employee

from django import forms
from django.core.exceptions import ValidationError
from .models import PerformanceReviewTemplate, ReviewQuestion, PerformanceReview, ReviewResponse, Department, Employee


class workform(forms.ModelForm):
    department = forms.ChoiceField(choices=[], required=False)

    class Meta:
        model = WorkAssignments
        widgets = {
            "assignDate": forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            "dueDate": forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
        labels = {"assignerId": "Select Your ID"}
        fields = [
            "assignerId",
            "work",
            "assignDate",
            "dueDate",
            "taskerId",
            "status",
        ]

    def __init__(self, *args, **kwargs):
        # Extract request from kwargs (we'll pass it from the view)
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.fields['assignerId'].disabled = False

        # Populate department choices
        departments = Employee.objects.values_list('department', flat=True).distinct()
        self.fields['department'].choices = [('', 'All Departments')] + [(dept, dept) for dept in departments]

        # Get the selected department from self.data (POST) or self.initial (GET)
        selected_dept = None
        if 'department' in self.data:
            selected_dept = self.data.get('department')
        elif 'department' in self.initial:
            selected_dept = self.initial.get('department')

        # Filter taskerId based on the selected department
        if selected_dept:
            self.fields['taskerId'].queryset = Employee.objects.filter(department=selected_dept)
        else:
            self.fields['taskerId'].queryset = Employee.objects.all()

        # Exclude the currently logged-in user from taskerId
        if self.request and self.request.user.is_authenticated:
            current_user_eid = self.request.user.username
            self.fields['taskerId'].queryset = self.fields['taskerId'].queryset.exclude(eID=current_user_eid)

from django import forms
from django.db import models
from .models import Requests, Employee

from django import forms
from django.db import models
from .models import Requests, Employee

from django import forms
from .models import Employee, Department, Requests
from django.utils import timezone
import django.db.models as models

from django import forms
from .models import Employee, Department, Requests
from django.utils import timezone
import django.db.models as models

class makeRequestForm(forms.ModelForm):
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        label="Department (optional)",
        empty_label="Select Department or Choose Specific Recipient",
        to_field_name="dept_id"  # Use dept_id as the value
    )
    destination_employee = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=False,
        label="Recipient",
        empty_label="Select Recipient (or leave blank to send to all in department)"
    )

    class Meta:
        model = Requests
        fields = ["request_type", "request_message", "request_date", "department", "destination_employee", "request_file"]
        widgets = {
            "request_date": forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            "request_message": forms.Textarea(attrs={'rows': 4, 'class': 'w-full p-2 border rounded-md'}),
            "request_type": forms.Select(attrs={'class': 'w-full p-2 border rounded-md'}),
            "request_file": forms.FileInput(attrs={'class': 'w-full p-2 border rounded-md'}),
            "department": forms.Select(attrs={'class': 'w-full p-2 border rounded-md'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if self.request and self.request.user.is_authenticated:
            employee = Employee.objects.get(eID=self.request.user.username)
            request_type = self.data.get('request_type') if self.is_bound else self.initial.get('request_type', 'other')
            department = self.data.get('department') if self.is_bound else self.initial.get('department')

            if employee.role == 'employee':
                self.fields['department'].widget = forms.HiddenInput()
                if request_type in ['resource', 'support', 'approval']:
                    self.fields['destination_employee'].queryset = Employee.objects.filter(
                        department=employee.department, role='manager'
                    ).exclude(eID=employee.eID)
                else:  # 'other'
                    self.fields['destination_employee'].queryset = Employee.objects.filter(role='hr')
            elif employee.role == 'manager':
                if request_type in ['resource', 'support', 'approval']:
                    self.fields['destination_employee'].queryset = Employee.objects.filter(
                        department=employee.department, role='employee'
                    ).exclude(eID=employee.eID)
                    self.fields['department'].widget = forms.HiddenInput()
                else:  # 'other'
                    self.fields['department'].queryset = Department.objects.all()
                    if department:
                        dept = Department.objects.filter(dept_id=department).first()
                        if dept:
                            self.fields['destination_employee'].queryset = Employee.objects.filter(
                                department=dept, role='manager'
                            ).exclude(eID=employee.eID)
                        else:
                            self.fields['destination_employee'].queryset = Employee.objects.filter(
                                models.Q(role='manager') | models.Q(role='hr') | models.Q(role='admin')
                            ).exclude(eID=employee.eID)
                    else:
                        self.fields['destination_employee'].queryset = Employee.objects.filter(
                            models.Q(role='manager') | models.Q(role='hr') | models.Q(role='admin')
                        ).exclude(eID=employee.eID)
            elif employee.role in ['hr', 'admin']:
                self.fields['department'].queryset = Department.objects.all()
                if department:
                    dept = Department.objects.filter(dept_id=department).first()
                    if dept:
                        self.fields['destination_employee'].queryset = Employee.objects.filter(
                            department=dept
                        ).exclude(eID=employee.eID)
                    else:
                        self.fields['destination_employee'].queryset = Employee.objects.all().exclude(eID=employee.eID)
                else:
                    self.fields['destination_employee'].queryset = Employee.objects.all().exclude(eID=employee.eID)
            else:
                self.fields['destination_employee'].queryset = Employee.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        destination_employee = cleaned_data.get('destination_employee')
        request_type = cleaned_data.get('request_type')
        department = cleaned_data.get('department')
        employee = Employee.objects.get(eID=self.request.user.username)

        # Validate department exists - this is now a model instance if it exists
        # No need to do another filter check since ModelChoiceField already ensures it exists
        
        if employee.role == 'employee':
            if department:
                raise forms.ValidationError("Employees cannot select a department for requests.")
            if not destination_employee:
                raise forms.ValidationError("Please select a recipient for your request.")
            if employee == destination_employee:
                raise forms.ValidationError("You cannot send a request to yourself.")
            if request_type in ['resource', 'support', 'approval']:
                if destination_employee.department != employee.department or destination_employee.role != 'manager':
                    raise forms.ValidationError("For this request type, the recipient must be your department manager.")
                if request_type == 'approval':
                    cleaned_data['escalate_to_hr'] = True
            else:  # 'other'
                if destination_employee.role != 'hr':
                    raise forms.ValidationError("Special requests must be sent to HR initially.")
        elif employee.role == 'manager':
            if request_type in ['resource', 'support', 'approval']:
                if department:
                    raise forms.ValidationError("Department selection is not allowed for this request type.")
                if destination_employee and (destination_employee.department != employee.department or destination_employee.role != 'employee'):
                    raise forms.ValidationError("For this request type, the recipient must be a department member with the 'employee' role.")
            else:  # 'other'
                if destination_employee:
                    if employee == destination_employee:
                        raise forms.ValidationError("You cannot send a request to yourself.")
                    if destination_employee.role == 'manager':
                        if not department:
                            raise forms.ValidationError("Please select a department when sending to a fellow manager.")
                        # No need to check if department exists again
                        if destination_employee.department != department:
                            raise forms.ValidationError("The selected manager must be from the chosen department.")
                    elif destination_employee.role not in ['hr', 'admin']:
                        raise forms.ValidationError("Special requests can only be sent to other managers, HR, or Admins.")
        elif employee.role in ['hr', 'admin']:
            # No need to check if department exists again
            if department and destination_employee and destination_employee.department != department:
                raise forms.ValidationError("The selected recipient must be from the chosen department.")
            if not department and not destination_employee:
                raise forms.ValidationError("Please select a department or a specific recipient.")
            if employee == destination_employee:
                raise forms.ValidationError("You cannot send a request to yourself.")

        return cleaned_data



from django import forms
from .models import Employee, Department, EmergencyContact, Document
import re
from django.utils import timezone

class EmployeeForm(forms.ModelForm):
    inferred_role = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'readonly': 'readonly', 'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-100'}),
        label="Inferred Role"
    )

    class Meta:
        model = Employee
        fields = [
            'firstName', 'middleName', 'lastName', 'phoneNo', 'email',
            'addharNo', 'dOB', 'designation', 'salary', 'joinDate',
            'department', 'can_assign_cross_department'
        ]
        widgets = {
            'dOB': forms.DateInput(attrs={'type': 'date'}),
            'joinDate': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'designation' in self.data:
            designation = self.data.get('designation', '').strip().title()
            if designation == 'HR':
                self.fields['inferred_role'].initial = 'hr'
            elif designation == 'Admin':
                self.fields['inferred_role'].initial = 'admin'
            elif designation in ['Project Manager', 'Team Leader', 'Senior Developer']:
                self.fields['inferred_role'].initial = 'manager'
            else:
                self.fields['inferred_role'].initial = 'employee'
        else:
            self.fields['inferred_role'].initial = 'employee'

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        can_assign_cross_department = cleaned_data.get('can_assign_cross_department', False)
        designation = cleaned_data.get('designation')
        if designation:
            designation_normalized = designation.strip().title()
            if designation_normalized == 'HR':
                inferred_role = 'hr'
            elif designation_normalized == 'Admin':
                inferred_role = 'admin'
            elif designation_normalized in ['Project Manager', 'Team Leader', 'Senior Developer']:
                inferred_role = 'manager'
            else:
                inferred_role = 'employee'
        else:
            inferred_role = 'employee'

        if inferred_role == 'employee' and can_assign_cross_department:
            raise forms.ValidationError({
                'can_assign_cross_department': "Employees with the 'employee' role cannot assign tasks across departments."
            })

        # Validate phone number
        phone_no = cleaned_data.get('phoneNo')
        if phone_no:
            phone_pattern = r'^\+?\d{10,12}$'
            if not re.match(phone_pattern, phone_no):
                raise forms.ValidationError({
                    'phoneNo': "Phone number must be 10-12 digits, optionally starting with a '+'."
                })

        # Validate date of birth
        dob = cleaned_data.get('dOB')
        if dob and dob > timezone.now().date():
            raise forms.ValidationError({
                'dOB': "Date of birth cannot be in the future."
            })

        # Validate join date
        join_date = cleaned_data.get('joinDate')
        if join_date and join_date > timezone.now().date():
            raise forms.ValidationError({
                'joinDate': "Join date cannot be in the future."
            })

        # Validate salary (must be numeric and less than 1,000,000)
        salary = cleaned_data.get('salary')
        if salary:
            # Ensure salary is numeric
            try:
                salary_value = int(salary.replace(',', ''))  # Handle comma-separated input (e.g., "123,456")
                if salary_value >= 1000000:
                    raise forms.ValidationError({
                        'salary': "Salary cannot exceed 6 figures (1,000,000 Kenyan Shillings)."
                    })
            except ValueError:
                raise forms.ValidationError({
                    'salary': "Salary must be a valid number."
                })

        # Validate email (must end with @gmail.com or @yahoo.com)
        email = cleaned_data.get('email')
        if email:
            if not (email.lower().endswith('@gmail.com') or email.lower().endswith('@yahoo.com')):
                raise forms.ValidationError({
                    'email': "Email must end with @gmail.com or @yahoo.com."
                })

        return cleaned_data

# employee/forms.py (update EmergencyContactForm)
class EmergencyContactForm(forms.ModelForm):
    class Meta:
        model = EmergencyContact
        fields = ['name', 'relationship', 'phone_no', 'email']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
        }

    def __init__(self, *args, **kwargs):
        self.employee = kwargs.pop('employee', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        if self.employee and not self.instance.pk:  # New contact
            contact_count = EmergencyContact.objects.filter(employee=self.employee).count()
            if contact_count >= 2:
                raise forms.ValidationError("You can only add up to two emergency contacts.")
        return cleaned_data

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['document_type', 'title', 'file', 'is_sensitive']
        widgets = {
            'file': forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'}),
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file and file.size > 5 * 1024 * 1024:  # 5MB limit
            raise forms.ValidationError("File size must be under 5MB.")
        return file


# employee/forms.py
from django import forms
from .models import Notice, Department

class NoticeForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = ['title', 'description', 'publishDate', 'departments', 'is_urgent', 'expires_on', 'is_active']
        widgets = {
            'publishDate': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'expires_on': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 5}),
            'departments': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['publishDate'].input_formats = ['%Y-%m-%dT%H:%M']  # For datetime-local input



from django import forms
from .models import PerformanceReviewTemplate, ReviewQuestion, PerformanceReview, ReviewResponse, Department, Employee

class PerformanceReviewTemplateForm(forms.ModelForm):
    class Meta:
        model = PerformanceReviewTemplate
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

from django import forms
from .models import ReviewQuestion

class ReviewQuestionForm(forms.ModelForm):
    class Meta:
        model = ReviewQuestion
        fields = ['question_text', 'question_type']  # Removed 'order'
        widgets = {
            'question_text': forms.TextInput(attrs={'class': 'w-full'}),
            'question_type': forms.Select(attrs={'class': 'w-full'}),
        }

class PerformanceReviewScheduleForm(forms.ModelForm):
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,  # Make department optional to allow "All Departments"
        widget=forms.Select(attrs={'class': 'w-full', 'id': 'id_department'}),
        empty_label="All Departments",  # Allow selecting "All Departments"
        help_text="Select a department to schedule reviews for its employees. Select 'All Departments' to schedule for all employees."
    )
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_active=True, is_archived=False),
        required=False,
        widget=forms.Select(attrs={'class': 'w-full', 'id': 'id_employee'}),
        help_text="Optionally select a specific employee after choosing a department."
    )

    class Meta:
        model = PerformanceReview
        fields = ['employee', 'department', 'template', 'scheduled_date']
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        employee = cleaned_data.get('employee')
        department = cleaned_data.get('department')

        # Validate that the selected employee belongs to the selected department
        if employee and department:  # Only validate if both are selected
            if employee.department != department:
                raise forms.ValidationError("The selected employee does not belong to the selected department.")

        return cleaned_data

class ReviewResponseForm(forms.ModelForm):
    class Meta:
        model = ReviewResponse
        fields = ['rating', 'text_response']
        widgets = {
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5, 'class': 'w-full'}),
            'text_response': forms.Textarea(attrs={'rows': 3, 'class': 'w-full'}),
        }

    def __init__(self, *args, **kwargs):
        self.question = kwargs.pop('question', None)
        super().__init__(*args, **kwargs)
        if self.question:
            if self.question.question_type == 'rating':
                self.fields['text_response'].widget = forms.HiddenInput()
            else:
                self.fields['rating'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        rating = cleaned_data.get('rating')
        text_response = cleaned_data.get('text_response')

        if not self.question:
            raise forms.ValidationError("No question associated with this response.")

        if self.question.question_type == 'rating':
            if rating is None:
                self.add_error('rating', "A rating is required for this question.")
            elif not (1 <= rating <= 5):
                self.add_error('rating', "Rating must be between 1 and 5.")
        else:  # question_type == 'text'
            if not text_response or text_response.strip() == '':
                self.add_error('text_response', "A text response is required for this question.")

        return cleaned_data


from django import forms
from django.apps import apps
from django.db import models
from .models import Department

class CustomReportForm(forms.Form):
    MODEL_CHOICES = [
        ('Employee', 'Employee'),
        ('Document', 'Document'),
        ('Attendance', 'Attendance'),
        ('LeaveRequest', 'Leave Request'),
        ('PerformanceReview', 'Performance Review'),
        ('WorkAssignments', 'Work Assignments'),
        ('RoleChangeLog', 'Role Change Log'),
        ('Notice', 'Notice'),
        ('EmergencyContact', 'Emergency Contact'),
        ('Notification', 'Notification'),
        ('IssueReport', 'Issue Report'),
        ('Requests', 'Requests'),
        ('WorkAssignmentLog', 'Work Assignment Log'),
        ('PendingRoleChange', 'Pending Role Change'),
        ('IssueComment', 'Issue Comment'),
    ]

    AGGREGATION_CHOICES = [
        ('', 'None'),
        ('count', 'Count'),
        ('avg', 'Average'),
        ('sum', 'Sum'),
        ('min', 'Minimum'),
        ('max', 'Maximum'),
    ]

    model = forms.ChoiceField(choices=MODEL_CHOICES, label="Model")
    fields = forms.MultipleChoiceField(choices=[], label="Fields to Display", widget=forms.CheckboxSelectMultiple)
    date_field = forms.ChoiceField(choices=[], label="Date Field", required=False)
    start_date = forms.DateField(label="Start Date", required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(label="End Date", required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    status_field = forms.ChoiceField(choices=[], label="Status Field", required=False)
    status_value = forms.CharField(label="Status Value", required=False)
    aggregation = forms.ChoiceField(choices=AGGREGATION_CHOICES, label="Aggregation", required=False)
    aggregation_field = forms.ChoiceField(choices=[], label="Aggregation Field", required=False)
    department = forms.ModelChoiceField(queryset=Department.objects.all(), label="Department", required=False)
    is_urgent = forms.BooleanField(label="Urgent Notices Only", required=False)
    feedback_satisfactory = forms.BooleanField(label="Satisfactory Feedback Only", required=False)

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        # Get the selected model from POST data or default to the first model
        model_name = self.data.get('model') if self.data else self.MODEL_CHOICES[0][0]
        model = apps.get_model('employee', model_name)

        # Populate fields choices
        field_choices = []
        for field in model._meta.get_fields():
            if field.name not in ['id', 'password'] and not field.is_relation:
                field_choices.append((field.name, field.verbose_name or field.name.replace('_', ' ').title()))
        self.fields['fields'].choices = field_choices

        # Populate date_field choices (only DateField and DateTimeField)
        date_field_choices = [('', 'None')]
        for field in model._meta.get_fields():
            if isinstance(field, (models.DateField, models.DateTimeField)):
                date_field_choices.append((field.name, field.verbose_name or field.name.replace('_', ' ').title()))
        self.fields['date_field'].choices = date_field_choices

        # Populate status_field choices (only CharField that might represent status)
        status_field_choices = [('', 'None')]
        for field in model._meta.get_fields():
            if isinstance(field, models.CharField) and 'status' in field.name.lower():
                status_field_choices.append((field.name, field.verbose_name or field.name.replace('_', ' ').title()))
        self.fields['status_field'].choices = status_field_choices

        # Populate aggregation_field choices (numeric fields for avg/sum, any field for count/min/max)
        aggregation_field_choices = [('', 'None')]
        for field in model._meta.get_fields():
            if not field.is_relation and field.name not in ['id', 'password']:
                aggregation_field_choices.append((field.name, field.verbose_name or field.name.replace('_', ' ').title()))
        self.fields['aggregation_field'].choices = aggregation_field_choices

    def clean(self):
        cleaned_data = super().clean()
        model_name = cleaned_data.get('model')
        status_field = cleaned_data.get('status_field')
        status_value = cleaned_data.get('status_value')
        date_field = cleaned_data.get('date_field')
        aggregation = cleaned_data.get('aggregation')
        aggregation_field = cleaned_data.get('aggregation_field')

        if not model_name:
            return cleaned_data

        model = apps.get_model('employee', model_name)

        # Validate status_field
        if status_field:
            try:
                field = model._meta.get_field(status_field)
                if not isinstance(field, models.CharField):
                    self.add_error('status_field', f"{status_field} is not a valid status field for {model_name}.")
            except models.FieldDoesNotExist:
                self.add_error('status_field', f"{status_field} does not exist in {model_name}.")

        # Validate status_value
        if status_field and not status_value:
            self.add_error('status_value', "Please provide a status value when a status field is selected.")

        # Validate date_field
        if date_field:
            try:
                field = model._meta.get_field(date_field)
                if not isinstance(field, (models.DateField, models.DateTimeField)):
                    self.add_error('date_field', f"{date_field} is not a valid date field for {model_name}.")
            except models.FieldDoesNotExist:
                self.add_error('date_field', f"{date_field} does not exist in {model_name}.")

        # Validate aggregation_field
        if aggregation and aggregation_field:
            try:
                field = model._meta.get_field(aggregation_field)
                if aggregation in ['avg', 'sum'] and not isinstance(field, (models.IntegerField, models.FloatField)):
                    self.add_error('aggregation_field', f"{aggregation_field} is not a numeric field for {aggregation}.")
            except models.FieldDoesNotExist:
                self.add_error('aggregation_field', f"{aggregation_field} does not exist in {model_name}.")

        return cleaned_data


from django import forms
from .models import IssueReport

class IssueReportForm(forms.ModelForm):
    class Meta:
        model = IssueReport
        fields = ['title', 'description', 'category', 'attachment']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'w-full border rounded p-2'}),
            'category': forms.Select(attrs={'class': 'w-full border rounded p-2'}),
            'attachment': forms.ClearableFileInput(attrs={'class': 'w-full border rounded p-2'}),
            'title': forms.TextInput(attrs={'class': 'w-full border rounded p-2'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        title = cleaned_data.get('title')
        description = cleaned_data.get('description')

        if not title or len(title.strip()) < 5:
            raise forms.ValidationError("Title must be at least 5 characters long.")
        if not description or len(description.strip()) < 10:
            raise forms.ValidationError("Description must be at least 10 characters long.")

        return cleaned_data