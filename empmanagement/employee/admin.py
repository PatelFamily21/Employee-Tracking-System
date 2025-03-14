from django.contrib import admin
from employee.models import Employee,Attendance,Notice, Requests, Department

# Customize Admin Titles
admin.site.site_header = "Employee Tracking System Admin"
admin.site.site_title = "ETS Admin Panel"
admin.site.index_title = "Welcome to the Employee Tracking System Dashboard"


# Register your models here.
admin.site.register(Employee)
admin.site.register(Attendance)
admin.site.register(Notice)
admin.site.register(Requests)
admin.site.register(Department)