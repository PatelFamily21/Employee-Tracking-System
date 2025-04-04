from django.shortcuts import render, redirect
from django.http import HttpResponse
from employee.models import Employee
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

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
            messages.error(request, "Invalid Credentials")
            return redirect("/")

    return render(request, "employee/login.html")

def logout_user(request):
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
                    # Optionally set initial role here if needed
                    # employee = Employee.objects.get(eID=id)
                    # employee.role = 'employee'  # Already default in model, so not strictly necessary
                    # employee.save()
                    messages.success(request, "Registered Successfully! Please log in.")
                    return redirect("login_user")
            else:
                messages.error(request, "Invalid Employee ID")
                return redirect("/signup")
        else:
            messages.error(request, "Passwords Don't Match")
            return redirect("/signup")
            
    return render(request, "employee/signup.html")