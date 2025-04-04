# employee/decorators.py
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Employee

def role_required(*roles):
    def decorator(view_func):
        @login_required(login_url='/')
        def wrapper(request, *args, **kwargs):
            try:
                employee = Employee.objects.get(eID=request.user.username)
            except Employee.DoesNotExist:
                messages.error(request, "Employee profile not found.")
                return redirect('dashboard')
            if employee.role not in roles:
                messages.error(request, "Access denied. Insufficient permissions.")
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator