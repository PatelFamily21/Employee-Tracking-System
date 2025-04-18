# employee/models.py
# employee/models.py
from django.utils import timezone
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, FileExtensionValidator
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max

# Existing choices (unchanged)
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

# Department Model (unchanged)
class Department(models.Model):
    dept_id = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

# Emergency Contact Model
class EmergencyContact(models.Model):
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='emergency_contacts')
    name = models.CharField(max_length=100)
    relationship = models.CharField(max_length=50, help_text="e.g., Parent, Spouse, Friend")
    phone_no = models.CharField(
        max_length=12,
        validators=[RegexValidator(r'^\+?\d{10,12}$', "Phone number must be 10-12 digits, optionally starting with a '+'.")]
    )
    email = models.EmailField(max_length=70, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.relationship}) for {self.employee.eID}"

# Document Model
class Document(models.Model):
    DOCUMENT_TYPES = [
        ('contract', 'Contract'),
        ('id_card', 'ID Card'),
        ('certificate', 'Certificate'),
        ('other', 'Other'),
    ]

    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='other')
    title = models.CharField(max_length=100)
    file = models.FileField(
        upload_to='employee_documents/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'])],
        help_text="Allowed formats: PDF, JPG, JPEG, PNG, DOC, DOCX"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_sensitive = models.BooleanField(
        default=False,
        help_text="Mark as sensitive to restrict access to HR/Admins only."
    )

    def __str__(self):
        return f"{self.title} ({self.document_type}) for {self.employee.eID}"

# Employee Model (unchanged)
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
    is_active = models.BooleanField(
        default=True,
        help_text="Indicates whether the employee's account is active. Deactivated accounts cannot log in."
    )
    is_archived = models.BooleanField(
        default=False,
        help_text="Indicates whether the employee is archived (e.g., resigned)."
    )
    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the employee was archived."
    )
    has_completed_signup = models.BooleanField(
        default=False,
        help_text="Indicates whether the employee has completed the signup process."
    )

    def clean(self):
        if self.role == 'employee' and self.can_assign_cross_department:
            raise ValidationError({
                'can_assign_cross_department': "Employees with the 'employee' role cannot assign tasks across departments."
            })

    def save(self, *args, **kwargs):
        if not self.eID and self.joinDate:
            with transaction.atomic():
                year_suffix = f"/{str(self.joinDate.year)[-3:]}"
                last_employee = Employee.objects.filter(
                    eID__iendswith=year_suffix,
                    eID__istartswith='EMP'
                ).order_by('eID').last()
                
                if last_employee:
                    try:
                        last_number = int(last_employee.eID[3:6])
                        new_number = last_number + 1
                        self.eID = f"EMP{new_number:03d}{year_suffix}"
                    except (ValueError, IndexError):
                        max_number = Employee.objects.filter(
                            eID__iendswith=year_suffix,
                            eID__istartswith='EMP'
                        ).aggregate(Max('eID'))['eID__max']
                        if max_number:
                            try:
                                last_number = int(max_number[3:6])
                                new_number = last_number + 1
                                self.eID = f"EMP{new_number:03d}{year_suffix}"
                            except (ValueError, IndexError):
                                self.eID = f"EMP001{year_suffix}"
                        else:
                            self.eID = f"EMP001{year_suffix}"
                else:
                    self.eID = f"EMP001{year_suffix}"

        if self.pk is None:
            designation_normalized = self.designation.strip().title()
            if designation_normalized == 'Hr':
                self.role = 'hr'
            elif designation_normalized == 'Admin':
                self.role = 'admin'
            elif designation_normalized in ['Project Manager', 'Team Leader', 'Senior Developer']:
                self.role = 'manager'
            else:
                self.role = 'employee'

            if self.role in ['admin', 'hr']:
                self.can_assign_cross_department = True
            else:
                self.can_assign_cross_department = False
        else:
            if self.role == 'employee':
                self.can_assign_cross_department = False
            elif self.role in ['admin', 'hr']:
                self.can_assign_cross_department = True

        if self.is_archived and not self.archived_at:
            self.archived_at = timezone.now()
            self.is_active = False
        elif not self.is_archived:
            self.archived_at = None

        if self.has_completed_signup:
            try:
                user = User.objects.get(username=self.eID)
                user.is_active = self.is_active
                user.email = self.email
                user.save()
            except User.DoesNotExist:
                self.has_completed_signup = False

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.firstName} {self.lastName} ({self.designation})"

# Other existing models (Attendance, Notice, etc.) remain unchanged
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
    request_file = models.FileField(upload_to='request_files/', null=True, blank=True, help_text="Optional file attachment for the request.")
    request_date = models.DateTimeField(default=timezone.now)
    destination_employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="requests_received")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    feedback = models.TextField(null=True, blank=True, help_text="Feedback from the recipient.")
    requester_feedback = models.TextField(null=True, blank=True, help_text="Feedback from the requester in response to the recipient's clarification.")
    response_file = models.FileField(upload_to='request_response_files/', null=True, blank=True, help_text="Optional file uploaded by the requester in response to feedback.")
    is_locked = models.BooleanField(default=False, help_text="Indicates if the requester has locked the request after being satisfied with the feedback.")
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Ensure feedback is not provided if the request is rejected
        if self.status == 'rejected' and self.feedback:
            raise ValidationError({
                'feedback': "Feedback cannot be provided for a rejected request."
            })
        # Ensure the request can only be locked if it is approved and feedback exists
        if self.is_locked and (self.status != 'approved' or not self.feedback or not self.feedback.strip()):
            raise ValidationError({
                'is_locked': "Request can only be locked if it is approved and meaningful feedback has been provided."
            })
        # Ensure response_file and requester_feedback are only provided if feedback exists and the request is pending
        if (self.response_file or self.requester_feedback) and (not self.feedback or not self.feedback.strip() or self.status != 'pending'):
            raise ValidationError({
                'response_file': "A response file or feedback can only be provided for a pending request with meaningful feedback.",
                'requester_feedback': "A response file or feedback can only be provided for a pending request with meaningful feedback."
            })

    def save(self, *args, **kwargs):
        self.full_clean()  # Run validation before saving
        super().save(*args, **kwargs)

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
    is_compulsory = models.BooleanField(default=False)  # Indicates if leave is issued by HR/admin

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
    

class PerformanceReviewTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, related_name='created_templates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class ReviewQuestion(models.Model):
    template = models.ForeignKey(PerformanceReviewTemplate, on_delete=models.CASCADE, related_name='questions')
    question_text = models.CharField(max_length=255)
    question_type = models.CharField(max_length=20, choices=[
        ('rating', 'Rating (1-5)'),
        ('text', 'Text Response'),
    ])
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.question_text} ({self.template.name})"

class PerformanceReview(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='performance_reviews')
    template = models.ForeignKey(PerformanceReviewTemplate, on_delete=models.SET_NULL, null=True)
    scheduled_date = models.DateField()
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('employee_submitted', 'Employee Submitted'),
        ('manager_submitted', 'Manager Submitted'),
        ('completed', 'Completed'),
    ], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review for {self.employee} on {self.scheduled_date}"

class ReviewResponse(models.Model):
    review = models.ForeignKey(PerformanceReview, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(ReviewQuestion, on_delete=models.CASCADE)
    respondent = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, related_name='review_responses')
    response_type = models.CharField(max_length=20, choices=[
        ('employee', 'Employee Self-Assessment'),
        ('manager', 'Manager Feedback'),
    ])
    rating = models.IntegerField(null=True, blank=True)  # For rating-type questions (1-5)
    text_response = models.TextField(blank=True)  # For text-type questions
    submitted_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Response to {self.question} by {self.respondent} for {self.review}"
    
from django.db import models
from django.utils import timezone

class IssueReport(models.Model):
    CATEGORY_CHOICES = [
        ('SAFETY', 'Safety'),
        ('EQUIPMENT', 'Equipment'),
        ('INTERPERSONAL', 'Interpersonal'),
        ('OTHER', 'Other'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
    ]

    reporter = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='reported_issues')
    recipient = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, related_name='received_issues')
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    attachment = models.FileField(upload_to='issue_attachments/', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.reporter.firstName} ({self.get_category_display()})"
    
