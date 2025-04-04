from django.contrib.auth.models import AnonymousUser
from employee.models import Employee, Notification, WorkAssignments

def get_employee(request):
    """Helper function to fetch the Employee object for the current user."""
    if request.user and not isinstance(request.user, AnonymousUser) and request.user.is_authenticated:
        try:
            return Employee.objects.get(eID=request.user.username)
        except Employee.DoesNotExist:
            return None
    return None

def employee_context(request):
    employee = get_employee(request)
    return {'employee': employee}

def notifications(request):
    unread_notifications_count = 0
    employee = get_employee(request)
    if employee:
        unread_notifications_count = Notification.objects.filter(recipient=employee, is_read=False).count()
    return {'unread_notifications_count': unread_notifications_count}

def sidebar_context(request):
    pending_approvals_count = 0
    employee = get_employee(request)
    if employee and employee.role in ['manager', 'admin']:
        pending_approvals_count = WorkAssignments.objects.filter(
            taskerId__department=employee.department,
            approval_status='pending'
        ).count()
    return {'pending_approvals_count': pending_approvals_count}