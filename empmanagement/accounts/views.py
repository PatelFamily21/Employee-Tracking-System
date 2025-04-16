from django.shortcuts import render, redirect
from django.http import HttpResponse
from employee.models import Employee, AuditLog
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils import timezone

def landing_page(request):
    return render(request, "employee/landingpage.html")

def login_user(request):
    if request.method == "POST":
        id = request.POST["id"]
        password = request.POST["password"]
        user = authenticate(request, username=id, password=password)
        if user is not None:
            try:
                employee = Employee.objects.get(eID=user.username)
                if not employee.is_active:
                    # Log the failed login attempt due to deactivation
                    AuditLog.objects.create(
                        action_type='other',
                        action="Failed login attempt: Account deactivated",
                        performed_by=None,
                        timestamp=timezone.now(),
                        details=f"Username: {id}"
                    )
                    messages.error(request, "Your account is deactivated. Please contact an admin.")
                    return redirect("/")
                # Proceed with login
                login(request, user)
                # Log the login action
                AuditLog.objects.create(
                    action_type='login',
                    action=f"User logged in: {employee.firstName} {employee.lastName}",
                    performed_by=employee,
                    timestamp=timezone.now(),
                    details=f"Employee ID: {employee.eID}"
                )
                # Redirect based on role
                if employee.role == 'hr':
                    return redirect("/ems/hr-dashboard")  # HR goes to HR Dashboard
                elif employee.role == 'admin':
                    return redirect("/ems/hr-dashboard")  # Admin can also go to HR Dashboard
                else:
                    return redirect("/ems/dashboard")  # Others go to regular dashboard
            except Employee.DoesNotExist:
                # Log the failed login attempt
                AuditLog.objects.create(
                    action_type='other',
                    action="Failed login attempt: Employee profile not found",
                    performed_by=None,
                    timestamp=timezone.now(),
                    details=f"Username: {id}"
                )
                messages.error(request, "Employee profile not found.")
                return redirect("/ems/dashboard")
        else:
            # Log failed login attempt
            AuditLog.objects.create(
                action_type='other',
                action="Failed login attempt: Invalid credentials",
                performed_by=None,
                timestamp=timezone.now(),
                details=f"Username: {id}"
            )
            messages.error(request, "Invalid credentials or account may be deactivated.")
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
        
        try:
            employee = Employee.objects.get(eID=id)
            if employee.has_completed_signup:
                messages.error(request, "This Employee ID has already been registered.")
                return redirect("/signup")
            if password != cnfpass:
                messages.error(request, "Passwords don't match.")
                return redirect("/signup")
            user = User.objects.create_user(
                username=id,
                password=password,
                email=employee.email,
                is_active=employee.is_active
            )
            employee.has_completed_signup = True
            employee.save()
            AuditLog.objects.create(
                action_type='create',
                action=f"User signed up: {employee.firstName} {employee.lastName}",
                performed_by=employee,
                timestamp=timezone.now(),
                details=f"Employee ID: {employee.eID}"
            )
            messages.success(request, "Registered successfully! Please log in.")
            return redirect("login_user")
        except Employee.DoesNotExist:
            messages.error(request, "Invalid Employee ID.")
            return redirect("/signup")
        except IntegrityError:
            messages.error(request, "An error occurred during registration. Please try again.")
            return redirect("/signup")
            
    return render(request, "employee/signup.html")