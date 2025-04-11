from django.shortcuts import render, redirect
from django.http import HttpResponse
from employee.models import Employee, AuditLog  # Import AuditLog
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils import timezone

# Create your views here.
def landing_page(request):
    return render(request, "employee/landingpage.html")

def login_user(request):
    if request.method == "POST":
        id = request.POST["id"]
        password = request.POST["password"]
        user = authenticate(request, username=id, password=password)
        if user is not None:
            login(request, user)
            # Log the login action
            try:
                employee = Employee.objects.get(eID=user.username)
                AuditLog.objects.create(
                    action_type='login',
                    action=f"User logged in: {employee.firstName} {employee.lastName}",
                    performed_by=employee,
                    timestamp=timezone.now(),
                    details=f"Employee ID: {employee.eID}"
                )
            except Employee.DoesNotExist:
                messages.warning(request, "Employee profile not found, login logged without employee details.")
                AuditLog.objects.create(
                    action_type='login',
                    action=f"User logged in: {id}",
                    performed_by=None,
                    timestamp=timezone.now(),
                    details=f"Username: {id}"
                )
            # Check employee's role and redirect accordingly
            try:
                employee = Employee.objects.get(eID=user.username)
                if employee.role == 'hr':
                    return redirect("/ems/hr-dashboard")  # HR goes to HR Dashboard
                elif employee.role == 'admin':
                    return redirect("/ems/hr-dashboard")  # Admin can also go to HR Dashboard
                else:
                    return redirect("/ems/dashboard")  # Others go to regular dashboard
            except Employee.DoesNotExist:
                messages.error(request, "Employee profile not found.")
                return redirect("/ems/dashboard")
        else:
            # Log failed login attempt
            AuditLog.objects.create(
                action_type='other',
                action="Failed login attempt",
                performed_by=None,
                timestamp=timezone.now(),
                details=f"Username: {id}"
            )
            messages.error(request, "Invalid Credentials")
            return redirect("/")

    return render(request, "employee/login.html")

def logout_user(request):
    # Log the logout action
    try:
        employee = Employee.objects.get(eID=request.user.username)
        AuditLog.objects.create(
            action_type='other',
            action=f"User logged out: {employee.firstName} {employee.lastName}",
            performed_by=employee,
            timestamp=timezone.now(),
            details=f"Employee ID: {employee.eID}"
        )
    except Employee.DoesNotExist:
        AuditLog.objects.create(
            action_type='other',
            action=f"User logged out: {request.user.username}",
            performed_by=None,
            timestamp=timezone.now(),
            details=f"Username: {request.user.username}"
        )
    logout(request)
    return redirect("/")

def signup(request):
    if request.method == "POST":
        id = request.POST["id"]
        password = request.POST["password"]
        cnfpass = request.POST["cnfpass"]
        
        if password == cnfpass:
            if Employee.objects.filter(eID=id).exists():
                if User.objects.filter(username=id).exists():
                    messages.error(request, "Employee Already Registered")
                    return redirect("/signup")
                else:
                    user = User.objects.create_user(username=id, password=password)
                    user.save()
                    # Log the signup action
                    try:
                        employee = Employee.objects.get(eID=id)
                        AuditLog.objects.create(
                            action_type='create',
                            action=f"User signed up: {employee.firstName} {employee.lastName}",
                            performed_by=employee,
                            timestamp=timezone.now(),
                            details=f"Employee ID: {employee.eID}"
                        )
                    except Employee.DoesNotExist:
                        AuditLog.objects.create(
                            action_type='create',
                            action=f"User signed up: {id}",
                            performed_by=None,
                            timestamp=timezone.now(),
                            details=f"Username: {id}"
                        )
                    messages.success(request, "Registered Successfully! Please log in.")
                    return redirect("login_user")
            else:
                messages.error(request, "Invalid Employee ID")
                return redirect("/signup")
        else:
            messages.error(request, "Passwords Don't Match")
            return redirect("/signup")
            
    return render(request, "employee/signup.html")