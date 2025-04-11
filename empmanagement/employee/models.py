# employee/models.py
from django.utils import timezone
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

designations_opt = (
    ('Team Leader', 'Team Leader'),
    ('Project Manager', 'Project Manager'),
    ('Senior Developer', 'Senior Developer'),
    ('Junior Developer', 'Junior Developer'),
    ('Intern', 'Intern'),
    ('QA Tester', 'QA Tester'),
    ('HR', 'HR'),
    ('Admin', 'Admin'),
)

role_choices = (
    ('admin', 'Admin'),
    ('hr', 'HR'),
    ('manager', 'Manager'),
    ('employee', 'Employee'),
)

months = (
    ('January', 'January'), ('February', 'February'), ('March', 'March'),
    ('April', 'April'), ('May', 'May'), ('June', 'June'),
    ('July', 'July'), ('August', 'August'), ('September', 'September'),
    ('October', 'October'), ('November', 'November'), ('December', 'December')
)

days = tuple((str(i), str(i)) for i in range(32))

# New Department Model
class Department(models.Model):
    dept_id = models.CharField(max_length=10, primary_key=True)  # e.g., "HR", "ENG", "SALES"
    name = models.CharField(max_length=50, unique=True)  # e.g., "Human Resources"
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

from django.core.exceptions import ValidationError

class Employee(models.Model):
    eID = models.CharField(primary_key=True, max_length=20)
    firstName = models.CharField(max_length=50)
    middleName = models.CharField(max_length=50)
    lastName = models.CharField(max_length=50)
    phoneNo = models.CharField(max_length=12, unique=True)
    email = models.EmailField(max_length=70, unique=True)
    addharNo = models.CharField(max_length=20, unique=True)
    dOB = models.DateField()
    designation = models.CharField(max_length=50, choices=designations_opt)
    salary = models.CharField(max_length=20)
    joinDate = models.DateField()
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name="employees")
    role = models.CharField(max_length=20, choices=role_choices, default='employee')
    can_assign_cross_department = models.BooleanField(
        default=False,
        help_text="Indicates whether this employee can assign tasks to employees in other departments."
    )

    def clean(self):
        # Ensure can_assign_cross_department is False if role is 'employee'
        if self.role == 'employee' and self.can_assign_cross_department:
            raise ValidationError({
                'can_assign_cross_department': "Employees with the 'employee' role cannot assign tasks across departments."
            })

    def save(self, *args, **kwargs):
        # Only set role and can_assign_cross_department if this is a new instance
        if self.pk is None:  # Check if this is a creation (not an update)
            # Set role based on designation
            if self.designation == 'HR':
                self.role = 'hr'
            elif self.designation == 'Admin':
                self.role = 'admin'
            elif self.designation in ['Project Manager', 'Team Leader']:
                self.role = 'manager'
            else:
                self.role = 'employee'

            # Set can_assign_cross_department based on role
            if self.role in ['admin', 'hr']:
                self.can_assign_cross_department = True
            else:
                self.can_assign_cross_department = False

        # Run validation before saving
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return "%s %s %s" % (self.firstName, self.lastName, self.designation)

class Attendance(models.Model):
    eId = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()  # Date of attendance
    status = models.CharField(max_length=10, choices=[
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('leave', 'Leave'),
    ], default='present')  # Attendance status
    check_in_time = models.DateTimeField(null=True, blank=True)  # Check-in time
    check_out_time = models.DateTimeField(null=True, blank=True)  # Check-out time
    check_in_latitude = models.FloatField(null=True, blank=True)  # Latitude at check-in
    check_in_longitude = models.FloatField(null=True, blank=True)  # Longitude at check-in
    check_out_latitude = models.FloatField(null=True, blank=True)  # Latitude at check-out
    check_out_longitude = models.FloatField(null=True, blank=True)  # Longitude at check-out

    class Meta:
        unique_together = ('eId', 'date')  # Ensure one record per employee per day

    def __str__(self):
        return f"{self.eId} - {self.date} - {self.status}"

# employee/models.py
from django.db import models
from django.utils import timezone

class Notice(models.Model):
    Id = models.CharField(primary_key=True, max_length=20)
    title = models.CharField(max_length=250)
    description = models.TextField()
    publishDate = models.DateTimeField(default=timezone.now)
    posted_by = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='posted_notices', null=True, blank=True)
    departments = models.ManyToManyField('Department', blank=True, related_name="notices")
    is_urgent = models.BooleanField(default=False)  # To mark urgent notices
    expires_on = models.DateField(blank=True, null=True)  # Optional expiration date
    is_active = models.BooleanField(default=True)  # To archive notices

    def __str__(self):
        return f"{self.title} - {self.publishDate}"

class NoticeView(models.Model):
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name='views')
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('notice', 'employee')  # Prevent duplicate views

# employee/models.py
from django.db import models
from django.utils import timezone

class WorkAssignments(models.Model):
    Id = models.CharField(primary_key=True, max_length=20)
    assignerId = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name="assigned_works")
    work = models.TextField()
    assignDate = models.DateTimeField()
    dueDate = models.DateTimeField()
    taskerId = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name="assigned_tasks")
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
        ],
        default='pending'
    )
    progress_report = models.TextField(blank=True, null=True)
    progress_file = models.FileField(upload_to='work_files/', blank=True, null=True)
    manager_feedback = models.TextField(blank=True, null=True)
    feedback_satisfactory = models.BooleanField(default=False)  # New field
    is_locked = models.BooleanField(default=False)
    approval_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        default='approved'  # Default to approved for same-department assignments
    )

    def __str__(self):
        return f"{self.Id} - {self.work[:50]}"


class Requests(models.Model):
    REQUEST_TYPES = [
        ('resource', 'Resource Request'),
        ('support', 'Support Request'),
        ('approval', 'Approval Request'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    Id = models.CharField(primary_key=True, max_length=20)
    requester = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="requests_made")
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES, default='other')
    request_message = models.TextField()
    request_date = models.DateTimeField(default=timezone.now)
    destination_employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="requests_received")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Request {self.Id} - {self.request_type} - {self.status}"

# employee/models.py
# ... (existing imports and models) ...

class Notification(models.Model):
    recipient = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="notifications")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    request_type = models.CharField(max_length=50, null=True, blank=True)  # e.g., 'leave_request', 'managerial_request'
    request_id = models.CharField(max_length=50, null=True, blank=True)  # New field to store the ID of the related object

    def __str__(self):
        return f"Notification for {self.recipient.eID} - {self.message[:50]}"
    

class WorkAssignmentLog(models.Model):
    work_assignment = models.ForeignKey(WorkAssignments, on_delete=models.CASCADE, related_name="logs")
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
        ]
    )
    updated_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.work_assignment.Id} - {self.status} at {self.updated_at}"
    
class LeaveRequest(models.Model):
    Id = models.CharField(primary_key=True, max_length=20)
    requester = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests_made")
    request_message = models.TextField()
    request_date = models.DateTimeField(default=timezone.now)
    destination_employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests_received")
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending')
    start_date = models.DateField()
    end_date = models.DateField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Leave Request {self.Id} - {self.status}"
    

class RoleChangeLog(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="role_changes")
    old_role = models.CharField(max_length=20, choices=role_choices)
    new_role = models.CharField(max_length=20, choices=role_choices)
    changed_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, related_name="role_changes_made")
    changed_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.employee.eID}: {self.old_role} -> {self.new_role} by {self.changed_by.eID}"
    

# employee/models.py
from django.db import models
from django.utils import timezone

# ... (existing models) ...

class PendingRoleChange(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="pending_role_changes")
    old_role = models.CharField(max_length=20, choices=role_choices)
    new_role = models.CharField(max_length=20, choices=role_choices)
    requested_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, related_name="role_change_requests")
    request_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="role_change_reviews")
    review_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.employee.eID}: {self.old_role} -> {self.new_role} ({self.status})"
    

# employee/models.py
# employee/models.py
class AuditLog(models.Model):
    ACTION_TYPES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('other', 'Other'),
    ]
    
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES, default='other')
    action = models.CharField(max_length=100)
    performed_by = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.action} by {self.performed_by} at {self.timestamp}"