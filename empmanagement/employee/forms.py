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

class makeRequestForm(forms.ModelForm):
    destination_employee = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=True,
        label="Recipient"
    )

    class Meta:
        model = Requests
        fields = ["request_type", "request_message", "request_date", "destination_employee", "request_file"]
        widgets = {
            "request_date": forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            "request_message": forms.Textarea(attrs={'rows': 4, 'class': 'w-full p-2 border rounded-md'}),
            "request_type": forms.Select(attrs={'class': 'w-full p-2 border rounded-md'}),
            "request_file": forms.FileInput(attrs={'class': 'w-full p-2 border rounded-md'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if self.request and self.request.user.is_authenticated:
            employee = Employee.objects.get(eID=self.request.user.username)
            # Use the form's data if available (POST), otherwise use initial data (GET)
            request_type = self.data.get('request_type') if self.is_bound else self.initial.get('request_type', 'other')
            
            if employee.role == 'employee':
                if request_type in ['resource', 'support', 'approval']:
                    self.fields['destination_employee'].queryset = Employee.objects.filter(
                        models.Q(department=employee.department, role='manager') |  # Department manager
                        models.Q(department=employee.department, role='employee')  # Department members
                    ).exclude(eID=employee.eID)
                else:  # 'other' request type
                    self.fields['destination_employee'].queryset = Employee.objects.filter(
                        models.Q(role='hr') | models.Q(role='admin')
                    )
            elif employee.role == 'manager':
                if request_type in ['resource', 'support', 'approval']:
                    self.fields['destination_employee'].queryset = Employee.objects.filter(
                        department=employee.department,
                        role='employee'
                    )
                else:  # 'other' request type
                    self.fields['destination_employee'].queryset = Employee.objects.filter(
                        models.Q(role='manager') | models.Q(role='hr') | models.Q(role='admin')
                    ).exclude(eID=employee.eID)
            elif employee.role == 'hr':
                self.fields['destination_employee'].queryset = Employee.objects.all().exclude(eID=employee.eID)
            elif employee.role == 'admin':
                self.fields['destination_employee'].queryset = Employee.objects.filter(
                    models.Q(role='manager') | models.Q(role='employee')
                ).exclude(eID=employee.eID)

    def clean(self):
        cleaned_data = super().clean()
        destination_employee = cleaned_data.get('destination_employee')
        request_type = cleaned_data.get('request_type')

        if self.request and self.request.user.is_authenticated:
            employee = Employee.objects.get(eID=self.request.user.username)

            # Validate that destination_employee is not None
            if not destination_employee:
                raise forms.ValidationError("Please select a recipient for your request.")

            if employee == destination_employee:
                raise forms.ValidationError("You cannot send a request to yourself.")

            # Validate recipient based on request type and role
            if employee.role == 'employee':
                if request_type in ['resource', 'support', 'approval']:
                    # Must be within the same department (manager or employee)
                    if destination_employee.department != employee.department:
                        raise forms.ValidationError("For this request type, the recipient must be your department manager or a fellow department member.")
                    if destination_employee.role not in ['manager', 'employee']:
                        raise forms.ValidationError("For this request type, the recipient must be your department manager or a fellow department member.")
                else:  # 'other' request type
                    if destination_employee.role not in ['hr', 'admin']:
                        raise forms.ValidationError("Special requests can only be sent to HR or Admin.")
            elif employee.role == 'manager':
                if request_type in ['resource', 'support', 'approval']:
                    # Must be a department member (role='employee')
                    if destination_employee.department != employee.department or destination_employee.role != 'employee':
                        raise forms.ValidationError("For this request type, the recipient must be a department member with the 'employee' role.")
                else:  # 'other' request type
                    if destination_employee.role not in ['manager', 'hr', 'admin']:
                        raise forms.ValidationError("Special requests can only be sent to other managers, HR, or Admins.")
            elif employee.role == 'hr':
                # HR can send to anyone, so no additional validation needed
                pass
            elif employee.role == 'admin':
                if destination_employee.role not in ['manager', 'employee']:
                    raise forms.ValidationError("Admins can only send requests to managers or employees.")

        return cleaned_data



# employee/forms.py
from django import forms
from .models import Employee, Department, EmergencyContact, Document
import re

class EmployeeForm(forms.ModelForm):
    inferred_role = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'readonly': 'readonly', 'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-100'}),
        label="Inferred Role"
    )

    class Meta:
        model = Employee
        fields = [
            'eID','firstName', 'middleName', 'lastName', 'phoneNo', 'email',
            'addharNo', 'dOB', 'designation', 'salary', 'joinDate',
            'department', 'can_assign_cross_department'
        ]
        widgets = {
            'dOB': forms.DateInput(attrs={'type': 'date'}),
            'joinDate': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['eID'].required = False
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

        phone_no = cleaned_data.get('phoneNo')
        if phone_no:
            phone_pattern = r'^\+?\d{10,12}$'
            if not re.match(phone_pattern, phone_no):
                raise forms.ValidationError({
                    'phoneNo': "Phone number must be 10-12 digits, optionally starting with a '+'."
                })

        dob = cleaned_data.get('dOB')
        if dob and dob > timezone.now().date():
            raise forms.ValidationError({
                'dOB': "Date of birth cannot be in the future."
            })

        join_date = cleaned_data.get('joinDate')
        if join_date and join_date > timezone.now().date():
            raise forms.ValidationError({
                'joinDate': "Join date cannot be in the future."
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

class ReviewQuestionForm(forms.ModelForm):
    class Meta:
        model = ReviewQuestion
        fields = ['question_text', 'question_type', 'order']
        widgets = {
            'question_text': forms.TextInput(attrs={'class': 'w-full'}),
            'question_type': forms.Select(attrs={'class': 'w-full'}),
            'order': forms.NumberInput(attrs={'class': 'w-full'}),
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
        ('Attendance', 'Attendance'),
        ('LeaveRequest', 'Leave Request'),
        ('PerformanceReview', 'Performance Review'),
        ('WorkAssignments', 'Work Assignments'),
        ('RoleChangeLog', 'Role Change Log'),
        ('Notice', 'Notices'),
        ('Document', 'Documents'),  # Added Document model
    ]

    AGGREGATION_CHOICES = [
        ('', 'None'),
        ('count', 'Count'),
        ('avg', 'Average'),
        ('sum', 'Sum'),
        ('min', 'Minimum'),
        ('max', 'Maximum'),
    ]

    model = forms.ChoiceField(choices=MODEL_CHOICES, label="Select Model")
    fields = forms.MultipleChoiceField(choices=[], label="Select Fields to Display", widget=forms.CheckboxSelectMultiple)
    date_field = forms.ChoiceField(choices=[], label="Date Field for Filtering", required=False)
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)
    status_field = forms.ChoiceField(choices=[], label="Status Field for Filtering", required=False)
    status_value = forms.ChoiceField(choices=[], label="Status Value", required=False)
    aggregation = forms.ChoiceField(choices=AGGREGATION_CHOICES, label="Aggregation", required=False)
    aggregation_field = forms.ChoiceField(choices=[], label="Field to Aggregate", required=False)
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        label="Filter by Department",
        required=False
    )
    is_urgent = forms.BooleanField(label="Urgent Notices Only", required=False)
    feedback_satisfactory = forms.BooleanField(label="Satisfactory Feedback Only", required=False)

    def __init__(self, *args, request=None, **kwargs):
        self.request = request  # Store request to access user role
        super().__init__(*args, **kwargs)
        model_name = self.data.get('model') if self.data else self.initial.get('model', 'Employee')
        if model_name:
            model = apps.get_model('employee', model_name)
            
            # Dynamically set field choices, excluding sensitive fields for non-HR/admin
            current_employee = Employee.objects.get(eID=self.request.user.username) if self.request else None
            field_choices = []
            for f in model._meta.fields:
                # Skip sensitive fields for non-HR/admin users
                if model_name == 'Document' and f.name == 'file' and current_employee and current_employee.role not in ['hr', 'admin']:
                    continue
                field_choices.append((f.name, f.verbose_name or f.name.replace('_', ' ').title()))
            self.fields['fields'].choices = field_choices

            # Date fields for filtering
            date_fields = [(f.name, f.verbose_name or f.name.replace('_', ' ').title()) for f in model._meta.fields if isinstance(f, (models.DateField, models.DateTimeField))]
            self.fields['date_field'].choices = [('', 'None')] + date_fields

            # Status fields for filtering (CharField with choices)
            status_fields = [(f.name, f.verbose_name or f.name.replace('_', ' ').title()) for f in model._meta.fields if isinstance(f, models.CharField) and f.choices]
            self.fields['status_field'].choices = [('', 'None')] + status_fields

            # Update status value choices based on selected status field
            status_field_name = self.data.get('status_field') if self.data else None
            if status_field_name:
                field = model._meta.get_field(status_field_name)
                self.fields['status_value'].choices = field.choices

            # Aggregation field choices
            numeric_fields = [(f.name, f.verbose_name or f.name.replace('_', ' ').title()) for f in model._meta.fields if isinstance(f, (models.IntegerField, models.FloatField))]
            self.fields['aggregation_field'].choices = [('', 'None')] + numeric_fields

            # Show/hide filters based on model
            self.fields['department'].widget.attrs['class'] = 'department-filter hidden' if model_name not in ['Employee', 'Attendance', 'LeaveRequest', 'PerformanceReview', 'WorkAssignments'] else 'department-filter'
            self.fields['is_urgent'].widget.attrs['class'] = 'is-urgent-filter hidden' if model_name != 'Notice' else 'is-urgent-filter'
            self.fields['feedback_satisfactory'].widget.attrs['class'] = 'feedback-satisfactory-filter hidden' if model_name != 'WorkAssignments' else 'feedback-satisfactory-filter'


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