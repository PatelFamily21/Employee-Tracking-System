from django.contrib import admin
from employee.models import Employee,Attendance,Notice, Requests, Department

# Customize Admin Titles
admin.site.site_header = "Employee Tracking System Admin"
admin.site.site_title = "ETS Admin Panel"
admin.site.index_title = "Welcome to the Employee Tracking System Dashboard"


# Register your models here.

class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('eID', 'firstName', 'lastName', 'phoneNo', 'email', 'addharNo','designation', 'joinDate','department')
    list_filter = ('designation', 'department')
    search_fields = ('eID', 'firstName', 'lastName', 'email')
    ordering = ('eID',)
    fieldsets = (
        (None, {
            'fields': ('eID', 'firstName', 'middleName', 'lastName', 'phoneNo', 'email', 'addharNo', 'dOB', 'designation', 'salary', 'joinDate', 'department')
        }),
    )

class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('eId', 'month', 'days')
    list_filter = ('month',)
    search_fields = ('eId__eID', 'month')
    ordering = ('eId',)
    fieldsets = (
        (None, {
            'fields': ('eId', 'month', 'days')
        }),
    )
admin.site.register(Employee, EmployeeAdmin)
admin.site.register(Attendance, AttendanceAdmin)
admin.site.register(Notice)
admin.site.register(Requests)
admin.site.register(Department)