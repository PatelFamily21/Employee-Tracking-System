from django.contrib import admin
from .models import Employee,Attendance,Notice, Requests, Department, WorkAssignments, Notification, LeaveRequest, PendingRoleChange, RoleChangeLog

# Customize Admin Titles
admin.site.site_header = "Employee Tracking System Admin"
admin.site.site_title = "ETS Admin Panel"
admin.site.index_title = "Welcome to the Employee Tracking System Dashboard"


# Register your models here.
admin.site.register(Employee)
admin.site.register(Attendance)
admin.site.register(WorkAssignments)  # Assuming you want to register this model too
admin.site.register(Notice)
admin.site.register(Requests)
admin.site.register(Department)
admin.site.register(Notification)
admin.site.register(LeaveRequest)
admin.site.register(PendingRoleChange)
admin.site.register(RoleChangeLog)
