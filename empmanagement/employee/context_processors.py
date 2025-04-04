# employee/context_processors.py
from django.contrib.auth.models import AnonymousUser
from employee.models import Employee, Notification, WorkAssignments, Notice, NoticeView, PendingRoleChange  # Add PendingRoleChange
from django.utils import timezone
from django.db.models import Q

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

def sidebar_counts(request):
    if not request.user.is_authenticated:
        return {
            'employee': None,
            'unread_notifications_count': 0,
            'unread_notices_count': 0,
            'pending_approvals_count': 0,
            'pending_role_changes_count': 0,
            'total_notices_count': 0,
        }

    employee = get_employee(request)
    if not employee:
        return {
            'employee': None,
            'unread_notifications_count': 0,
            'unread_notices_count': 0,
            'pending_approvals_count': 0,
            'pending_role_changes_count': 0,
            'total_notices_count': 0,
        }

    today = timezone.now().date()

    unread_notifications_count = Notification.objects.filter(
        recipient=employee,
        is_read=False
    ).count()

    dept_filter = Q(departments__isnull=True)
    if employee.department:
        dept_filter |= Q(departments=employee.department)

    relevant_notices = Notice.objects.filter(
        dept_filter,
        Q(is_active=True),
        Q(expires_on__isnull=True) | Q(expires_on__gte=today)
    ).distinct()

    viewed_notice_ids = NoticeView.objects.filter(employee=employee).values_list('notice__Id', flat=True)
    unread_notices_count = relevant_notices.exclude(Id__in=viewed_notice_ids).count()

    pending_approvals_count = 0
    if employee.role in ['manager', 'admin'] and employee.department:
        pending_approvals_count = WorkAssignments.objects.filter(
            taskerId__department=employee.department,
            approval_status='pending'
        ).count()

    pending_role_changes_count = 0
    if employee.role in ['hr', 'admin']:
        pending_role_changes_count = PendingRoleChange.objects.filter(status='pending').count()

    total_notices_count = Notice.objects.count()

    return {
        'employee': employee,
        'unread_notifications_count': unread_notifications_count,
        'unread_notices_count': unread_notices_count,
        'pending_approvals_count': pending_approvals_count,
        'pending_role_changes_count': pending_role_changes_count,
        'total_notices_count': total_notices_count,
    }