# employee/templatetags/request_tags.py
from django import template
from employee.models import LeaveRequest

register = template.Library()

@register.filter
def is_leave_request(request):
    return isinstance(request, LeaveRequest)