from tkinter import Widget
from django import forms
from .models import WorkAssignments, Requests, Employee
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

class makeRequestForm(forms.ModelForm):
    destination_employee = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=False,
        label="Recipient (optional)"
    )

    class Meta:
        model = Requests
        fields = ["request_type", "request_message", "request_date", "destination_employee"]
        widgets = {
            "request_date": forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            "request_message": forms.Textarea(attrs={'rows': 4, 'class': 'w-full p-2 border rounded-md'}),
            "request_type": forms.Select(attrs={'class': 'w-full p-2 border rounded-md'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if self.request and self.request.user.is_authenticated:
            employee = Employee.objects.get(eID=self.request.user.username)
            if employee.role == 'employee':
                # Limit employees to their department's manager
                self.fields['destination_employee'].queryset = Employee.objects.filter(
                    department=employee.department, role='manager'
                )
            elif employee.role == 'manager':
                # Managers can choose HR or other managers
                self.fields['destination_employee'].queryset = Employee.objects.filter(
                    models.Q(role='hr') | models.Q(role='manager', department__ne=employee.department)
                )
            elif employee.role == 'hr':
                # HR can choose managers
                self.fields['destination_employee'].queryset = Employee.objects.filter(role='manager')


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['eID', 'firstName', 'middleName', 'lastName', 'phoneNo', 'email', 'addharNo', 'dOB', 'designation', 'salary', 'joinDate', 'department']


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