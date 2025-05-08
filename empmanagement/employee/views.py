# employee/views.py

# Standard library imports
from datetime import date, datetime, time, timedelta
from collections import defaultdict
from io import BytesIO
import csv
import os
import datetime

# Third-party imports (Django)
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Q
from django.db.models.functions import TruncMonth
from django.forms import formset_factory
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.timezone import make_naive

# Third-party imports (reportlab)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image

# Local application imports
from .context_processors import get_employee
from .decorators import role_required
from .forms import (
    CustomReportForm,
    DocumentForm,
    EmergencyContactForm,
    EmployeeForm,
    makeRequestForm,
    NoticeForm,
    PerformanceReviewTemplateForm,
    ReviewQuestionForm,
    workform,
)
from .models import (
    Attendance,
    AuditLog,
    Department,
    Document,
    EmergencyContact,
    Employee,
    LeaveRequest,
    Notice,
    NoticeView,
    Notification,
    PendingRoleChange,
    PerformanceReview,
    PerformanceReviewTemplate,
    Requests,
    ReviewQuestion,
    ReviewResponse,
    RoleChangeLog,
    WorkAssignments,
    WorkAssignmentLog,
    role_choices,
)
import io
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import Count, Q, F, Avg
from django.utils import timezone
from datetime import timedelta
import csv
from collections import defaultdict
from django.utils.timezone import make_naive
from .decorators import role_required
from .forms import CustomReportForm, PerformanceReviewTemplateForm, ReviewQuestionForm, PerformanceReviewScheduleForm, ReviewResponseForm
from .models import Employee, Attendance, LeaveRequest, PerformanceReview, ReviewResponse, WorkAssignments, RoleChangeLog, PendingRoleChange, AuditLog, PerformanceReviewTemplate, ReviewQuestion, Notification, Department
from django.apps import apps
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from django.contrib import messages
from django.forms import formset_factory

@role_required('employee', 'manager', 'hr', 'admin')
def dashboard(request):
    employee = Employee.objects.get(eID=request.user.username)
    context = {
        'info': [employee],
        'recent_notices': Notice.objects.order_by('-publishDate')[:5],
        'employee': employee,
        'pending_role_changes_count': PendingRoleChange.objects.filter(status='pending').count(),
    }
    if employee.role in ['hr', 'admin']:
        context.update({
            'total_employees': Employee.objects.count(),
            'pending_requests': (
                Requests.objects.filter(status='pending').count() + 
                LeaveRequest.objects.filter(status='pending').count()
            ),
            'departments': Department.objects.count(),
        })
    elif employee.role == 'manager':
        dept_employees = Employee.objects.filter(department=employee.department).count()
        dept_requests = (
            Requests.objects.filter(destination_employee=employee, status='pending').count() + 
            LeaveRequest.objects.filter(requester__department=employee.department, status='pending').count()
        )
        context.update({
            'total_employees': dept_employees,
            'pending_requests': dept_requests,
        })
    return render(request, 'employee/index.html', context)


@role_required('employee', 'manager', 'hr', 'admin')
def notifications(request):
    employee = Employee.objects.get(eID=request.user.username)
    notification_list = Notification.objects.filter(recipient=employee).order_by('-created_at')

    paginator = Paginator(notification_list, 10)  # 10 notifications per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mark_read':
            notification_id = request.POST.get('notification_id')
            notification = Notification.objects.get(id=notification_id, recipient=employee)
            notification.is_read = True
            notification.save()
            messages.success(request, "Notification marked as read.")
        elif action == 'mark_all_read':
            notification_list.update(is_read=True)
            messages.success(request, "All notifications marked as read.")
        return redirect('notifications')

    context = {
        'page_obj': page_obj,
        'unread_notifications_count': Notification.objects.filter(recipient=employee, is_read=False).count(),
    }
    return render(request, 'employee/notifications.html', context)

from django.utils import timezone
from datetime import datetime as dt, time

@role_required('employee', 'manager', 'hr', 'admin')
def attendance(request):
    employee = Employee.objects.get(eID=request.user.username)
    today = timezone.now().date()
    current_time = timezone.now()  # Timezone-aware datetime in EAT (Africa/Nairobi)
    
    # Define time windows
    check_in_start = timezone.make_aware(dt.combine(today, time(0, 0)))  # 00:00
    check_in_end = timezone.make_aware(dt.combine(today, time(9, 30)))   # 09:30
    check_out_start = timezone.make_aware(dt.combine(today, time(16, 0))) # 16:00
    check_out_end = timezone.make_aware(dt.combine(today, time(17, 0)))  # 17:00
    
    # Check if employee is on approved leave today
    is_on_leave_today = LeaveRequest.objects.filter(
        requester=employee,
        start_date__lte=today,
        end_date__gte=today,
        status='approved'
    ).exists()
    
    # Get today's attendance record for the current employee
    attendance_record = Attendance.objects.filter(eId=employee, date=today).first()
    
    # Initialize selected_employee_id as None
    selected_employee_id = None
    employees = None
    
    # Determine attendance history based on role
    if employee.role in ['hr', 'admin']:
        # HR and admin can see all employees' attendance
        attendance_history = Attendance.objects.all().order_by('-date')
        employees = Employee.objects.all()  # For filtering by employee
        # Filter by employee if selected
        selected_employee_id = request.GET.get('employee_id')
        if selected_employee_id:
            attendance_history = attendance_history.filter(eId__eID=selected_employee_id)
    else:
        # Employees and managers see only their own history
        attendance_history = Attendance.objects.filter(eId=employee).order_by('-date')
    
    # Date filter for attendance history
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date and end_date:
        try:
            start_date = dt.strptime(start_date, '%Y-%m-%d').date()
            end_date = dt.strptime(end_date, '%Y-%m-%d').date()
            attendance_history = attendance_history.filter(date__range=[start_date, end_date])
        except ValueError:
            messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")
    
    # Paginate attendance history
    paginator = Paginator(attendance_history, 10)  # 10 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate monthly summary for the current employee
    current_month = today.month
    current_year = today.year
    monthly_records = Attendance.objects.filter(
        eId=employee,
        date__year=current_year,
        date__month=current_month
    )
    summary = {
        'present': monthly_records.filter(status='present').count(),
        'absent': monthly_records.filter(status='absent').count(),
        'leave': monthly_records.filter(status='leave').count(),
    }
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'check_in':
            if is_on_leave_today:
                messages.error(request, "You are on approved leave today and cannot check in.")
            elif attendance_record:
                messages.error(request, "You have already checked in today.")
            elif not (check_in_start <= current_time <= check_in_end):
                messages.error(request, "Check-in is only allowed between 00:00 and 09:30 EAT.")
            else:
                Attendance.objects.create(
                    eId=employee,
                    date=today,
                    status='present',
                    check_in_time=current_time
                )
                try:
                    AuditLog.objects.create(
                        action_type='update',
                        action=f"Checked in: {employee.firstName} {employee.lastName}",
                        performed_by=employee,
                        details=f"Employee ID: {employee.eID}, Date: {today}"
                    )
                except Exception as e:
                    messages.warning(request, f"Check-in recorded, but failed to log action: {str(e)}")
                messages.success(request, "Checked in successfully!")
        
        elif action == 'check_out':
            if is_on_leave_today:
                messages.error(request, "You are on approved leave today and cannot check out.")
            elif not attendance_record:
                messages.error(request, "You need to check in first.")
            elif attendance_record.check_out_time:
                messages.error(request, "You have already checked out today.")
            elif not (check_out_start <= current_time <= check_out_end):
                messages.error(request, "Check-out is only allowed between 16:00 and 17:00 EAT.")
            else:
                attendance_record.check_out_time = current_time
                attendance_record.save()
                try:
                    AuditLog.objects.create(
                        action_type='update',
                        action=f"Checked out: {employee.firstName} {employee.lastName}",
                        performed_by=employee,
                        details=f"Employee ID: {employee.eID}, Date: {today}"
                    )
                except Exception as e:
                    messages.warning(request, f"Check-out recorded, but failed to log action: {str(e)}")
                messages.success(request, "Checked out successfully!")
        
        elif action == 'export_csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="attendance_history_{employee.eID}.csv"'
            writer = csv.writer(response)
            writer.writerow(['Employee ID', 'Date', 'Status', 'Check-In Time', 'Check-Out Time'])
            for record in attendance_history:
                writer.writerow([
                    record.eId.eID,
                    record.date,
                    record.status,
                    record.check_in_time.strftime('%Y-%m-%d %H:%M:%S') if record.check_in_time else '—',
                    record.check_out_time.strftime('%Y-%m-%d %H:%M:%S') if record.check_out_time else '—'
                ])
            return response
        
        return redirect('attendance')
    
    context = {
        'employee': employee,
        'attendance_record': attendance_record,
        'today': today,
        'is_on_leave_today': is_on_leave_today,
        'page_obj': page_obj,
        'summary': summary,
        'employees': employees,
        'selected_employee_id': selected_employee_id,
    }
    return render(request, 'employee/attendance.html', context)


@role_required('employee', 'manager', 'hr', 'admin')
def notice(request):
    # Fetch the employee with error handling
    try:
        employee = Employee.objects.get(eID=request.user.username)
    except Employee.DoesNotExist:
        messages.error(request, "Employee profile not found. Please contact HR.")
        return redirect('dashboard')

    today = timezone.now().date()
    # Use Q objects for all conditions to avoid keyword arguments in filter()
    notices = Notice.objects.filter(
        Q(is_active=True) & (Q(expires_on__isnull=True) | Q(expires_on__gte=today))
    ).prefetch_related('departments').order_by('-is_urgent', '-publishDate')

    # Filter notices by department in Python
    filtered_notices = []
    for notice in notices:
        notice_depts = notice.departments.all()
        # Handle case where employee.department is None
        if not notice_depts or (employee.department and employee.department in notice_depts):
            filtered_notices.append(notice)

    # Paginate the filtered notices
    paginator = Paginator(filtered_notices, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Optimize NoticeView creation to avoid N+1 queries
    notice_ids = [notice.Id for notice in page_obj]
    viewed_notice_ids = set(
        NoticeView.objects.filter(
            employee=employee,
            notice__Id__in=notice_ids
        ).values_list('notice__Id', flat=True)
    )
    for notice in page_obj:
        if notice.Id not in viewed_notice_ids:
            NoticeView.objects.create(notice=notice, employee=employee)

    context = {
        'page_obj': page_obj,
    }
    return render(request, "employee/notice.html", context)
    


@role_required('employee', 'manager', 'hr', 'admin')
def noticedetail(request, id):
    try:
        employee = Employee.objects.get(eID=request.user.username)
    except Employee.DoesNotExist:
        raise Http404("Employee profile not found.")

    notice = get_object_or_404(Notice, Id=id)

    # Check if the employee can view the notice
    today = timezone.now().date()
    can_view = (
        (not notice.departments.exists() or employee.department in notice.departments.all()) and
        notice.is_active and
        (notice.expires_on is None or notice.expires_on >= today)
    )
    if not can_view:
        raise Http404("You do not have permission to view this notice or it is no longer available.")

    # Mark the notice as viewed
    NoticeView.objects.get_or_create(notice=notice, employee=employee)

    context = {
        'noticedetail': notice,
    }
    return render(request, "employee/noticedetail.html", context)

@role_required('hr', 'admin')
def edit_notice(request, id):
    notice = get_object_or_404(Notice, Id=id)
    if request.method == 'POST':
        form = NoticeForm(request.POST, instance=notice)
        if form.is_valid():
            # Capture departments before the update
            old_departments = list(notice.departments.values_list('name', flat=True))
            form.save()
            employee = get_employee(request)
            if employee:
                max_title_length = 100 - len("Edited notice: ")
                truncated_title = notice.title[:max_title_length]
                action = f"Edited notice: {truncated_title}"
                new_departments = list(notice.departments.values_list('name', flat=True))
                try:
                    AuditLog.objects.create(
                        action_type='update',
                        action=action,
                        performed_by=employee,
                        timestamp=timezone.now(),
                        details=f"Notice ID: {notice.Id}, Departments changed from {old_departments} to {new_departments}"
                    )
                except Exception as e:
                    messages.warning(request, f"Notice updated, but failed to log action: {str(e)}")
            else:
                messages.warning(request, "Could not log the edit action to audit log: Employee not found.")
            messages.success(request, "Notice updated successfully!")
            return redirect('notice')
    else:
        form = NoticeForm(instance=notice)
    
    context = {
        'form': form,
        'action': 'Edit',
    }
    return render(request, 'employee/notice_form.html', context)


@role_required('hr', 'admin')
def delete_notice(request, id):
    notice = get_object_or_404(Notice, Id=id)
    notice_title = notice.title
    notice_id = notice.Id
    notice.delete()
    employee = get_employee(request)
    if employee:
        max_title_length = 100 - len("Deleted notice: ")
        truncated_title = notice_title[:max_title_length]
        action = f"Deleted notice: {truncated_title}"
        try:
            AuditLog.objects.create(
                action_type='delete',
                action=action,
                performed_by=employee,
                timestamp=timezone.now(),
                details=f"Notice ID: {notice_id}"
            )
        except Exception as e:
            messages.warning(request, f"Notice deleted, but failed to log action: {str(e)}")
    else:
        messages.warning(request, "Could not log the deletion to audit log: Employee not found.")
    
    messages.success(request, "Notice deleted successfully!")
    return redirect('manage_notices')


@role_required('hr', 'admin')
def create_notice(request):
    if request.method == 'POST':
        form = NoticeForm(request.POST)
        if form.is_valid():
            notice = form.save(commit=False)
            employee = get_employee(request)
            notice.posted_by = employee
            notice.Id = f"NOTICE{timezone.now().strftime('%Y%m%d%H%M%S')}"
            notice.save()
            form.save_m2m()

            if employee:
                max_title_length = 100 - len("Created notice: ")
                truncated_title = notice.title[:max_title_length]
                action = f"Created notice: {truncated_title}"
                departments = list(notice.departments.values_list('name', flat=True))
                try:
                    AuditLog.objects.create(
                        action_type='create',
                        action=action,
                        performed_by=employee,
                        timestamp=timezone.now(),
                        details=f"Notice ID: {notice.Id}, Departments: {departments}"
                    )
                except Exception as e:
                    messages.warning(request, f"Notice created, but failed to log action: {str(e)}")

            employees_to_notify = Employee.objects.filter(
                Q(department__in=notice.departments.all()) | Q(department__isnull=True)
            ).distinct()
            for emp in employees_to_notify:
                if not notice.departments.exists() or emp.department in notice.departments.all():
                    Notification.objects.create(
                        recipient=emp,
                        message=f"New notice: {notice.title} <a href='/ems/noticedetail/{notice.Id}/' class='text-blue-600 hover:underline'>View</a>",
                        request_type='notice',
                        request_id=notice.Id
                    )

            messages.success(request, "Notice created successfully!")
            return redirect('notice')
    else:
        form = NoticeForm()
    
    context = {
        'form': form,
        'action': 'Create',
    }
    return render(request, 'employee/notice_form.html', context)


@role_required('manager', 'hr', 'admin')
def assignwork(request):
    assigner = Employee.objects.get(eID=request.user.username)
    if request.method == 'POST':
        form = workform(request.POST, request.FILES, request=request)
        if form.is_valid():
            work = form.save(commit=False)
            work.Id = f"WORK{timezone.now().strftime('%d%m%Y%H%M%S')}"
            tasker = work.taskerId
            if assigner.department != tasker.department:
                if not assigner.can_assign_cross_department:
                    messages.error(request, "You are not authorized to assign tasks to employees outside your department.")
                    return redirect('assignwork')
                work.approval_status = 'pending'
                tasker_manager = Employee.objects.filter(
                    department=tasker.department,
                    role='manager'
                ).first()
                if tasker_manager:
                    Notification.objects.create(
                        recipient=tasker_manager,
                        message=f"Approval needed: {assigner.firstName} {assigner.lastName} assigned a task to {tasker.firstName} {tasker.lastName} in your department: {work.work[:50]}... <a href='/ems/managerial-requests/' class='text-blue-600 hover:underline'>View</a>",
                        request_type='managerial_request',
                        request_id=work.Id
                    )
            work.save()
            try:
                AuditLog.objects.create(
                    action_type='create',
                    action=f"Assigned work to {tasker.firstName} {tasker.lastName}",
                    performed_by=assigner,
                    details=f"Work ID: {work.Id}, Tasker ID: {tasker.eID}"
                )
            except Exception as e:
                messages.warning(request, f"Work assigned, but failed to log action: {str(e)}")
            Notification.objects.create(
                recipient=work.taskerId,
                message=f"New work assigned to you: {work.work[:50]}... <a href='/ems/workdetails/{work.Id}/' class='text-blue-600 hover:underline'>View</a>",
                request_type='work_assignment',
                request_id=work.Id
            )
            messages.success(request, "Work assigned successfully!")
            return redirect('assignwork')
    else:
        selected_department = request.GET.get('department', '')
        initial_data = {
            'assignerId': assigner,
            'department': selected_department,
            'assignDate': timezone.now()
        }
        form = workform(initial=initial_data, request=request)
    return render(request, 'employee/workassign.html', {'form': form})


@role_required('employee', 'manager', 'hr', 'admin')
def mywork(request):
    employee = Employee.objects.get(eID=request.user.username)
    work_list = WorkAssignments.objects.filter(taskerId=employee).order_by('-assignDate')

    if request.method == 'POST':
        work_id = request.POST.get('work_id')
        work = get_object_or_404(WorkAssignments, Id=work_id, taskerId=employee)
        
        if work.approval_status != 'approved':
            messages.error(request, "This task is pending approval and cannot be updated yet.")
            return redirect('mywork')
        
        if work.is_locked:
            messages.error(request, "This task is locked by the assigner and cannot be updated.")
            return redirect('mywork')

        status = request.POST.get('status')
        progress_report = request.POST.get('progress_report')
        
        if 'progress_file' in request.FILES:
            work.progress_file = request.FILES['progress_file']
        
        if work.status != status:
            WorkAssignmentLog.objects.create(
                work_assignment=work,
                status=status,
                updated_by=employee
            )
        work.status = status
        work.progress_report = progress_report
        work.save()
        
        Notification.objects.create(
            recipient=work.assignerId,
            message=f"{employee.firstName} {employee.lastName} updated status of {work.work[:50]} to {status}. <a href='/ems/workdetails/{work.Id}/' class='text-blue-600 hover:underline'>View</a>",
            request_type='work_update',
            request_id=work.Id
        )
        messages.success(request, "Work status, report, and file updated successfully!")
        return redirect('mywork')

    context = {"work": work_list}
    return render(request, "employee/mywork.html", context)


@role_required('employee', 'manager', 'hr', 'admin')
def workdetails(request, wid):
    workdetails = WorkAssignments.objects.get(Id=wid)
    user = Employee.objects.get(eID=request.user.username)
    can_provide_feedback = (
        user.role in ['manager', 'hr', 'admin'] and
        user == workdetails.assignerId and
        not workdetails.is_locked
    )

    if request.method == 'POST' and can_provide_feedback:
        feedback = request.POST.get('manager_feedback')
        feedback_satisfactory = request.POST.get('feedback_satisfactory') == 'on'  # Checkbox value

        # Update the work assignment with feedback and satisfaction status
        workdetails.manager_feedback = feedback
        workdetails.feedback_satisfactory = feedback_satisfactory
        workdetails.save()

        # Lock the task only if status is 'completed', feedback is provided, and feedback is satisfactory
        if (
            workdetails.status == 'completed' and
            workdetails.manager_feedback and
            workdetails.feedback_satisfactory
        ):
            workdetails.is_locked = True
            workdetails.save()
            messages.success(request, "Feedback submitted successfully, and the task has been locked.")
        else:
            messages.success(request, "Feedback submitted successfully.")

        # Send notification to the tasker
        Notification.objects.create(
            recipient=workdetails.taskerId,
            message=f"Manager provided feedback on {workdetails.work[:50]}: {feedback[:50]}... <a href='/ems/workdetails/{workdetails.Id}/' class='text-blue-600 hover:underline'>View</a>",
            request_type='work_feedback',
            request_id=workdetails.Id
        )

        return redirect('workdetails', wid=wid)

    context = {
        "workdetails": workdetails,
        "can_provide_feedback": can_provide_feedback,
    }
    return render(request, "employee/workdetails.html", context)


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from django.conf import settings
import os
import csv
from datetime import datetime
from django.utils import timezone
from itertools import chain
from .models import AuditLog, PendingRoleChange, Requests, Employee, Department, Notification
from .decorators import role_required
from .forms import makeRequestForm

@role_required('employee', 'manager', 'hr', 'admin')
def makeRequest(request):
    employee = Employee.objects.get(eID=request.user.username)
    flag = ""

    if request.method == 'POST':
        # Check if this is a request type change (partial submission)
        if 'request_type_change' in request.POST:
            form = makeRequestForm(request.POST, request.FILES, request=request)
            user_requests = Requests.objects.filter(requester=employee).order_by('-request_date')
            return render(request, "employee/request.html", {
                'requestForm': form,
                'flag': flag,
                'user_requests': user_requests,
            })

        # Check if this is a department change request (partial submission)
        if 'department_change' in request.POST:
            form = makeRequestForm(request.POST, request.FILES, request=request)
            user_requests = Requests.objects.filter(requester=employee).order_by('-request_date')
            return render(request, "employee/request.html", {
                'requestForm': form,
                'flag': flag,
                'user_requests': user_requests,
            })

        # Full form submission (actual request submission)
        form = makeRequestForm(request.POST, request.FILES, request=request)
        if form.is_valid():
            request_type = form.cleaned_data['request_type']
            department = form.cleaned_data.get('department')
            destination_employee = form.cleaned_data.get('destination_employee')
            recipients = []

            if not destination_employee and (employee.role in ['hr', 'admin'] or (employee.role == 'manager' and request_type in ['resource', 'support', 'approval'])):
                if not department:
                    messages.error(request, "Department selection is required for sending to all employees.")
                    return redirect('makeRequest')
                recipients = Employee.objects.filter(department=department).exclude(eID=employee.eID)
            else:
                recipients = [destination_employee]

            if not recipients:
                messages.error(request, "No valid recipients found for this request.")
                return redirect('makeRequest')

            for recipient in recipients:
                request_obj = Requests(
                    Id=f"REQ{timezone.now().strftime('%y%m%d%H%M%S')}{recipient.eID[:4]}",
                    requester=employee,
                    request_type=request_type,
                    request_message=form.cleaned_data['request_message'],
                    request_date=form.cleaned_data['request_date'],
                    destination_employee=recipient,
                    status='pending',
                    request_file=form.cleaned_data['request_file']
                )
                request_obj.save()

                view_url = f"/ems/requestdetails/{request_obj.Id}/"
                Notification.objects.create(
                    recipient=recipient,
                    message=f"New request from {employee.firstName} {employee.lastName}: {request_obj.request_message[:50]}... <a href='{view_url}' class='text-blue-600 hover:underline'>View</a>",
                    request_type='general_request',
                    request_id=request_obj.Id
                )

                try:
                    AuditLog.objects.create(
                        action_type='create',
                        action="Request Created",
                        performed_by=employee,
                        details=f"Request ID: {request_obj.Id}, Recipient: {recipient.eID}"
                    )
                except Exception as e:
                    messages.warning(request, f"Request submitted, but failed to log action: {str(e)}")

            if employee.role == 'employee':
                if request_type in ['resource', 'support', 'approval']:
                    if request_type == 'approval':
                        escalate_to_hr = form.cleaned_data.get('escalate_to_hr', False)
                        if escalate_to_hr:
                            next_hr = Employee.objects.filter(role='hr').first()
                            if next_hr:
                                Notification.objects.create(
                                    recipient=next_hr,
                                    message=f"Escalated request from {employee.firstName} {employee.lastName}: {request_obj.request_message[:50]}... <a href='/ems/requestdetails/{request_obj.Id}/' class='text-blue-600 hover:underline'>View</a>",
                                    request_type='general_request',
                                    request_id=request_obj.Id
                                )
                else:  # 'other'
                    if destination_employee.role != 'hr':
                        next_admin = Employee.objects.filter(role='admin').first()
                        if next_admin:
                            Notification.objects.create(
                                recipient=next_admin,
                                message=f"Escalated request from {employee.firstName} {employee.lastName}: {request_obj.request_message[:50]}... <a href='/ems/requestdetails/{request_obj.Id}/' class='text-blue-600 hover:underline'>View</a>",
                                request_type='general_request',
                                request_id=request_obj.Id
                            )

            flag = "Request Submitted"
            messages.success(request, f"Request submitted successfully to {len(recipients)} recipient(s)!")
            return redirect('makeRequest')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}" if field != '__all__' else error)
    else:
        form = makeRequestForm(request=request, initial={'request_type': 'other'})

    user_requests = Requests.objects.filter(requester=employee).order_by('-request_date')
    return render(request, "employee/request.html", {
        'requestForm': form,
        'flag': flag,
        'user_requests': user_requests,
    })

@role_required('manager', 'hr', 'admin')
def get_employees_by_department(request):
    department_id = request.GET.get('department')
    request_type = request.GET.get('request_type')
    role = request.GET.get('role')

    if not department_id:
        return JsonResponse({'employees': []})

    employee = Employee.objects.get(eID=request.user.username)
    employees = Employee.objects.filter(department__pk=department_id).exclude(eID=employee.eID)

    if role == 'manager' and request_type == 'other':
        employees = employees.filter(role='manager')

    employee_list = [
        {'id': emp.eID, 'name': f"{emp.firstName} {emp.lastName} ({emp.role.title()})"}
        for emp in employees
    ]
    return JsonResponse({'employees': employee_list})



@role_required('manager', 'hr', 'admin')
def viewRequest(request):
    employee = Employee.objects.get(eID=request.user.username)
    request_list = Requests.objects.filter(destination_employee=employee).order_by('-request_date')
    leave_requests = LeaveRequest.objects.filter(destination_employee=employee).order_by('-request_date')

    paginator = Paginator(list(chain(request_list, leave_requests)), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.method == 'POST':
        action = request.POST.get('action')
        request_id = request.POST.get('request_id')
        request_type = request.POST.get('request_type')
        feedback = request.POST.get('feedback', '')

        if request_type == 'leave_request':
            try:
                leave_request = LeaveRequest.objects.get(Id=request_id, destination_employee=employee)
                if action == 'approve':
                    leave_request.status = 'approved'
                    leave_request.save()

                    current_date = leave_request.start_date
                    while current_date <= leave_request.end_date:
                        attendance_record = Attendance.objects.filter(
                            eId=leave_request.requester,
                            date=current_date
                        ).first()
                        if attendance_record:
                            attendance_record.status = 'leave'
                            attendance_record.check_in_time = None
                            attendance_record.check_out_time = None
                            attendance_record.save()
                        else:
                            Attendance.objects.create(
                                eId=leave_request.requester,
                                date=current_date,
                                status='leave',
                                check_in_time=None,
                                check_out_time=None
                            )
                        current_date += timedelta(days=1)

                    try:
                        AuditLog.objects.create(
                            action_type='update',
                            action=f"Approved leave request {request_id}",
                            performed_by=employee,
                            details=f"Leave Request ID: {request_id}, Requester ID: {leave_request.requester.eID}"
                        )
                    except Exception as e:
                        messages.warning(request, f"Leave request approved, but failed to log action: {str(e)}")
                    messages.success(request, f"Leave request {request_id} approved.")
                    Notification.objects.create(
                        recipient=leave_request.requester,
                        message=f"Your leave request (ID: {leave_request.Id}) has been approved by {employee.firstName} {employee.lastName}. <a href='/ems/leave-request-details/{leave_request.Id}/' class='text-blue-600 hover:underline'>View</a>",
                        request_type='leave_request_status',
                        request_id=leave_request.Id
                    )
                elif action == 'reject':
                    leave_request.status = 'rejected'
                    leave_request.save()
                    try:
                        AuditLog.objects.create(
                            action_type='other',
                            action=f"Rejected leave request {request_id}",
                            performed_by=employee,
                            details=f"Leave Request ID: {request_id}, Requester ID: {leave_request.requester.eID}"
                        )
                    except Exception as e:
                        messages.warning(request, f"Leave request rejected, but failed to log action: {str(e)}")
                    messages.success(request, f"Leave request {request_id} rejected.")
                    Notification.objects.create(
                        recipient=leave_request.requester,
                        message=f"Your leave request (ID: {leave_request.Id}) has been rejected by {employee.firstName} {employee.lastName}. <a href='/ems/leave-request-details/{leave_request.Id}/' class='text-blue-600 hover:underline'>View</a>",
                        request_type='leave_request_status',
                        request_id=leave_request.Id
                    )
            except LeaveRequest.DoesNotExist:
                messages.error(request, "Leave request not found.")
        else:
            try:
                req = Requests.objects.get(Id=request_id, destination_employee=employee)
                if action == 'approve':
                    req.status = 'approved'
                    if feedback:
                        req.feedback = feedback
                    req.save()
                    try:
                        AuditLog.objects.create(
                            action_type='update',
                            action=f"Approved request {request_id}",
                            performed_by=employee,
                            details=f"Request ID: {request_id}, Requester ID: {req.requester.eID}"
                        )
                    except Exception as e:
                        messages.warning(request, f"Request approved, but failed to log action: {str(e)}")
                    messages.success(request, f"Request {request_id} approved.")
                    Notification.objects.create(
                        recipient=req.requester,
                        message=f"Your request (ID: {req.Id}) has been approved by {employee.firstName} {employee.lastName}. <a href='/ems/requestdetails/{req.Id}/' class='text-blue-600 hover:underline'>View</a>",
                        request_type='general_request_status',
                        request_id=req.Id
                    )
                elif action == 'reject':
                    req.status = 'rejected'
                    req.feedback = None  # Clear feedback on rejection
                    req.save()
                    try:
                        AuditLog.objects.create(
                            action_type='other',
                            action=f"Rejected request {request_id}",
                            performed_by=employee,
                            details=f"Request ID: {request_id}, Requester ID: {req.requester.eID}"
                        )
                    except Exception as e:
                        messages.warning(request, f"Request rejected, but failed to log action: {str(e)}")
                    messages.success(request, f"Request {request_id} rejected.")
                    Notification.objects.create(
                        recipient=req.requester,
                        message=f"Your request (ID: {req.Id}) has been rejected by {employee.firstName} {employee.lastName}. <a href='/ems/requestdetails/{req.Id}/' class='text-blue-600 hover:underline'>View</a>",
                        request_type='general_request_status',
                        request_id=req.Id
                    )
                elif action == 'feedback':
                    if not feedback:
                        messages.error(request, "Feedback is required when seeking clarification.")
                    else:
                        req.feedback = feedback
                        req.save()
                        messages.success(request, "Feedback submitted successfully.")
                        Notification.objects.create(
                            recipient=req.requester,
                            message=f"{employee.firstName} {employee.lastName} has provided feedback on your request (ID: {req.Id}): {feedback[:50]}... <a href='/ems/requestdetails/{req.Id}/' class='text-blue-600 hover:underline'>View</a>",
                            request_type='general_request_feedback',
                            request_id=req.Id
                        )
            except Requests.DoesNotExist:
                messages.error(request, "Request not found.")
        return redirect('viewRequest')

    context = {
        'page_obj': page_obj,
    }
    return render(request, 'employee/viewRequest.html', context)


@role_required('employee', 'manager', 'hr', 'admin')
def requestdetails(request, rid):
    requestdetail = get_object_or_404(Requests, Id=rid)
    employee = Employee.objects.get(eID=request.user.username)

    # Restrict access to requester or destination employee
    if requestdetail.requester != employee and requestdetail.destination_employee != employee:
        messages.error(request, "You are not authorized to view this request.")
        return redirect('dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')
        feedback = request.POST.get('feedback', '').strip()

        if requestdetail.destination_employee == employee:
            # Actions for the recipient
            if action == 'approve':
                if requestdetail.status != 'pending':
                    messages.error(request, "This request has already been processed.")
                else:
                    requestdetail.status = 'approved'
                    if feedback:
                        requestdetail.feedback = feedback
                    requestdetail.save()
                    messages.success(request, "Request approved successfully!")
                    Notification.objects.create(
                        recipient=requestdetail.requester,
                        message=f"Your request (ID: {requestdetail.Id}) has been approved by {employee.firstName} {employee.lastName}. <a href='/ems/requestdetails/{requestdetail.Id}/' class='text-blue-600 hover:underline'>View</a>",
                        request_type='general_request_status',
                        request_id=requestdetail.Id
                    )
                    try:
                        AuditLog.objects.create(
                            action_type='update',
                            action=f"Approved request {requestdetail.Id}",
                            performed_by=employee,
                            details=f"Request ID: {requestdetail.Id}, Requester ID: {requestdetail.requester.eID}"
                        )
                    except Exception as e:
                        messages.warning(request, f"Request approved, but failed to log action: {str(e)}")
            elif action == 'reject':
                if requestdetail.status != 'pending':
                    messages.error(request, "This request has already been processed.")
                else:
                    requestdetail.status = 'rejected'
                    requestdetail.feedback = None  # Clear feedback on rejection
                    requestdetail.requester_feedback = None  # Clear requester feedback on rejection
                    requestdetail.response_file = None  # Clear response file on rejection
                    requestdetail.save()
                    messages.success(request, "Request rejected successfully!")
                    Notification.objects.create(
                        recipient=requestdetail.requester,
                        message=f"Your request (ID: {requestdetail.Id}) has been rejected by {employee.firstName} {employee.lastName}. <a href='/ems/requestdetails/{requestdetail.Id}/' class='text-blue-600 hover:underline'>View</a>",
                        request_type='general_request_status',
                        request_id=requestdetail.Id
                    )
                    try:
                        AuditLog.objects.create(
                            action_type='other',
                            action=f"Rejected request {requestdetail.Id}",
                            performed_by=employee,
                            details=f"Request ID: {requestdetail.Id}, Requester ID: {requestdetail.requester.eID}"
                        )
                    except Exception as e:
                        messages.warning(request, f"Request rejected, but failed to log action: {str(e)}")
            elif action == 'feedback':
                if requestdetail.status != 'pending':
                    messages.error(request, "Cannot provide feedback for a processed request.")
                    return redirect('requestdetails', rid=rid)
                if not feedback or len(feedback) < 5:
                    messages.error(request, "Feedback must be at least 5 characters long to seek clarification.")
                    return redirect('requestdetails', rid=rid)
                
                requestdetail.feedback = feedback
                requestdetail.requester_feedback = None  # Clear requester feedback when new feedback is provided
                requestdetail.response_file = None  # Clear response file when new feedback is provided
                requestdetail.save()
                messages.success(request, "Feedback submitted successfully.")
                Notification.objects.create(
                    recipient=requestdetail.requester,
                    message=f"{employee.firstName} {employee.lastName} has provided feedback on your request (ID: {requestdetail.Id}): {feedback[:50]}... <a href='/ems/requestdetails/{requestdetail.Id}/' class='text-blue-600 hover:underline'>View</a>",
                    request_type='general_request_feedback',
                    request_id=requestdetail.Id
                )
                try:
                    AuditLog.objects.create(
                        action_type='update',
                        action=f"Feedback provided for request {requestdetail.Id}",
                        performed_by=employee,
                        details=f"Request ID: {requestdetail.Id}, Requester ID: {requestdetail.requester.eID}"
                    )
                except Exception as e:
                    messages.warning(request, f"Feedback submitted, but failed to log action: {str(e)}")
        elif requestdetail.requester == employee:
            # Actions for the requester
            if action == 'lock':
                if requestdetail.status != 'approved':
                    messages.error(request, "Only approved requests can be locked.")
                elif not requestdetail.feedback:
                    messages.error(request, "Cannot lock the request without feedback from the recipient.")
                elif requestdetail.is_locked:
                    messages.error(request, "This request is already locked.")
                else:
                    requestdetail.is_locked = True
                    requestdetail.save()
                    messages.success(request, "Request locked successfully.")
                    try:
                        AuditLog.objects.create(
                            action_type='update',
                            action=f"Locked request {requestdetail.Id}",
                            performed_by=employee,
                            details=f"Request ID: {requestdetail.Id}, Recipient: {requestdetail.destination_employee.eID}"
                        )
                    except Exception as e:
                        messages.warning(request, f"Request locked, but failed to log action: {str(e)}")
            elif action == 'respond':
                # Re-fetch the request to handle concurrency issues
                requestdetail = get_object_or_404(Requests, Id=rid)
                if requestdetail.status != 'pending':
                    messages.error(request, "Cannot respond to a processed request.")
                    return redirect('requestdetails', rid=rid)
                if not requestdetail.feedback or not requestdetail.feedback.strip():
                    messages.error(request, "Cannot respond until meaningful feedback is provided by the recipient.")
                    return redirect('requestdetails', rid=rid)

                requester_feedback = request.POST.get('requester_feedback', '').strip()
                if not requester_feedback and 'response_file' not in request.FILES:
                    messages.error(request, "Please provide feedback or attach a file to respond.")
                    return redirect('requestdetails', rid=rid)

                # Update the fields and save
                if requester_feedback:
                    requestdetail.requester_feedback = requester_feedback
                if 'response_file' in request.FILES:
                    requestdetail.response_file = request.FILES['response_file']
                try:
                    requestdetail.save()
                    messages.success(request, "Response submitted successfully.")
                    notification_message = f"{employee.firstName} {employee.lastName} has responded to your feedback on request (ID: {requestdetail.Id})."
                    if requester_feedback:
                        notification_message += f" Feedback: {requester_feedback[:50]}..."
                    if requestdetail.response_file:
                        notification_message += " A file has been attached."
                    notification_message += f" <a href='/ems/requestdetails/{requestdetail.Id}/' class='text-blue-600 hover:underline'>View</a>"
                    Notification.objects.create(
                        recipient=requestdetail.destination_employee,
                        message=notification_message,
                        request_type='general_request_response',
                        request_id=requestdetail.Id
                    )
                    try:
                        AuditLog.objects.create(
                            action_type='update',
                            action=f"Response submitted for request {requestdetail.Id}",
                            performed_by=employee,
                            details=f"Request ID: {requestdetail.Id}, Recipient: {requestdetail.destination_employee.eID}"
                        )
                    except Exception as e:
                        messages.warning(request, f"Response submitted, but failed to log action: {str(e)}")
                except ValidationError as e:
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            messages.error(request, f"{field}: {error}")

        return redirect('requestdetails', rid=rid)

    # Ensure can_respond aligns with model validation
    can_respond = (
        requestdetail.requester == employee and
        requestdetail.status == 'pending' and
        bool(requestdetail.feedback and requestdetail.feedback.strip())
    )

    return render(request, "employee/requestdetails.html", {
        "requestdetail": requestdetail,
        "can_process": requestdetail.destination_employee == employee and requestdetail.status == 'pending',
        "can_lock": requestdetail.requester == employee and requestdetail.status == 'approved' and bool(requestdetail.feedback and requestdetail.feedback.strip()) and not requestdetail.is_locked,
        "can_respond": can_respond,
    })


@role_required('hr','manager', 'admin')
def assignedWorkList(request):
    assigner = Employee.objects.get(eID=request.user.username)
    works = WorkAssignments.objects.filter(assignerId=assigner).order_by('-assignDate')
    return render(request, "employee/assignedworklist.html", {"works": works})


@role_required('hr','manager', 'admin')
def deleteWork(request, wid):
    assigner = Employee.objects.get(eID=request.user.username)
    obj = get_object_or_404(WorkAssignments, Id=wid, assignerId=assigner)
    work_id = obj.Id
    obj.delete()
    try:
        AuditLog.objects.create(
            action_type='delete',
            action=f"Deleted work assignment {work_id}",
            performed_by=assigner,
            details=f"Work ID: {work_id}"
        )
    except Exception as e:
        messages.warning(request, f"Work deleted, but failed to log action: {str(e)}")
    works = WorkAssignments.objects.filter(assignerId=assigner).order_by('-assignDate')
    return render(request, "employee/assignedworklist.html", {"works": works})


@role_required('manager', 'admin')
def updateWork(request, wid):
    assigner = Employee.objects.get(eID=request.user.username)
    work = get_object_or_404(WorkAssignments, Id=wid, assignerId=assigner)
    form = workform(request.POST or None, instance=work)
    flag = ""

    if request.method == 'POST' and form.is_valid():
        tasker = form.cleaned_data['taskerId']
        if tasker.eID == assigner.eID:
            flag = "Invalid ID Selected..."
        elif assigner.role == 'manager' and tasker.role in ('manager', 'admin'):
            flag = "Managers cannot assign work to managers or admins."
        else:
            old_tasker = work.taskerId
            form.save()
            try:
                AuditLog.objects.create(
                    action_type='update',
                    action=f"Updated work assignment {work.Id}",
                    performed_by=assigner,
                    details=f"Work ID: {work.Id}, Tasker changed from {old_tasker.eID} to {tasker.eID}"
                )
            except Exception as e:
                messages.warning(request, f"Work updated, but failed to log action: {str(e)}")
            Notification.objects.create(
                recipient=tasker,
                message=f"Work updated by {assigner.firstName} {assigner.lastName}: {work.work[:50]}... due {work.dueDate.strftime('%Y-%m-%d')}. <a href='/ems/workdetails/{work.Id}/' class='text-blue-600 hover:underline'>View</a>",
                request_type='work_update',
                request_id=work.Id
            )
            flag = "Work Updated Successfully!!"
            return redirect('assignedworklist')

    return render(request, "employee/updatework.html", {'currentWork': work, "filledForm": form, "flag": flag})


@role_required('employee', 'manager', 'hr', 'admin')
def profile(request):
    try:
        employee = Employee.objects.get(eID=request.user.username)
    except Employee.DoesNotExist:
        messages.error(request, "Employee profile not found.")
        return redirect('dashboard')

    password_form = PasswordChangeForm(user=request.user)
    emergency_form = EmergencyContactForm(employee=employee)
    document_form = DocumentForm()

    if request.method == "POST":
        if 'update_profile' in request.POST:
            employee.firstName = request.POST.get('firstName', employee.firstName)
            employee.middleName = request.POST.get('middleName', employee.middleName)
            employee.lastName = request.POST.get('lastName', employee.lastName)
            employee.phoneNo = request.POST.get('phoneNo', employee.phoneNo)
            employee.email = request.POST.get('email', employee.email)
            try:
                employee.save()
                messages.success(request, "Profile updated successfully!")
            except Exception as e:
                messages.error(request, f"Error updating profile: {e}")
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, "Your password was successfully updated!")
            else:
                for field, errors in password_form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field if field != '__all__' else 'Error'}: {error}")
        elif 'add_emergency_contact' in request.POST:
            emergency_form = EmergencyContactForm(request.POST, employee=employee)
            if emergency_form.is_valid():
                emergency_contact = emergency_form.save(commit=False)
                emergency_contact.employee = employee
                emergency_contact.save()
                messages.success(request, "Emergency contact added successfully.")
                return redirect('profile')
        elif 'add_document' in request.POST:
            document_form = DocumentForm(request.POST, request.FILES)
            if document_form.is_valid():
                document = document_form.save(commit=False)
                document.employee = employee
                document.save()
                messages.success(request, "Document uploaded successfully.")
                return redirect('profile')
        return redirect('profile')

    return render(request, 'employee/profile.html', {
        'employee': employee,
        'password_form': password_form,
        'emergency_form': emergency_form,
        'document_form': document_form,
    })


@role_required('hr', 'admin')
def hr_dashboard(request):
    total_employees = Employee.objects.count()
    recent_notices = Notice.objects.order_by('-publishDate')[:5]
    attendance_summary = (
        Attendance.objects
        .annotate(month=TruncMonth('date'))
        .values('month', 'status')
        .annotate(total_days=Count('id'))
        .order_by('month', 'status')
    )
    formatted_summary = {}
    for entry in attendance_summary:
        month_str = entry['month'].strftime('%B %Y')
        if month_str not in formatted_summary:
            formatted_summary[month_str] = {'present': 0, 'absent': 0, 'leave': 0}
        formatted_summary[month_str][entry['status']] = entry['total_days']

    attendance_records = Attendance.objects.select_related('eId').order_by('-date')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date and end_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            attendance_records = attendance_records.filter(date__range=[start_date, end_date])
        except ValueError:
            messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")

    employee_id = request.GET.get('employee_id')
    if employee_id:
        attendance_records = attendance_records.filter(eId__eID=employee_id)

    paginator = Paginator(attendance_records, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    employees = Employee.objects.all().order_by('firstName', 'lastName')
    departments = Department.objects.all()

    context = {
        'total_employees': total_employees,
        'recent_notices': recent_notices,
        'attendance_summary': formatted_summary,
        'page_obj': page_obj,
        'employees': employees,
        'selected_employee_id': employee_id,
        'departments': departments,
    }
    return render(request, 'employee/hr_dashboard.html', context)

@role_required('hr', 'admin')
def employee_database(request):
    employees = Employee.objects.select_related('department').order_by('eID')
    
    # Filters
    department_id = request.GET.get('department_id')
    role = request.GET.get('role')
    status = request.GET.get('status')
    
    if department_id:
        employees = employees.filter(department__dept_id=department_id)
    if role:
        employees = employees.filter(role=role)
    if status:
        if status == 'active':
            employees = employees.filter(is_active=True, is_archived=False)
        elif status == 'inactive':
            employees = employees.filter(is_active=False)
        elif status == 'archived':
            employees = employees.filter(is_archived=True)
    
    paginator = Paginator(employees, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    departments = Department.objects.all()
    role_choices = Employee._meta.get_field('role').choices
    status_choices = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('archived', 'Archived'),
    ]
    
    context = {
        'page_obj': page_obj,
        'departments': departments,
        'role_choices': role_choices,
        'status_choices': status_choices,
        'selected_department_id': department_id,
        'selected_role': role,
        'selected_status': status,
    }
    return render(request, 'employee/employee_database.html', context)


@role_required('hr', 'admin')
def employee_detail(request, eID):
    employee = get_object_or_404(Employee, eID=eID)
    document_form = DocumentForm()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        performed_by = Employee.objects.filter(eID=request.user.username).first()
        
        if action == 'add_document':
            document_form = DocumentForm(request.POST, request.FILES)
            if document_form.is_valid():
                document = document_form.save(commit=False)
                document.employee = employee
                document.save()
                AuditLog.objects.create(
                    action_type='create',
                    action="Added Document",
                    performed_by=performed_by,
                    details=f"Document: {document.title} for {employee.eID}"
                )
                messages.success(request, "Document uploaded successfully.")
                return redirect('employee_detail', eID=eID)
    
    # Fetch role change history
    role_history = RoleChangeLog.objects.filter(employee=employee).order_by('-changed_at')
    
    context = {
        'employee': employee,
        'document_form': document_form,
        'role_history': role_history,
    }
    return render(request, 'employee/employee_detail.html', context)

@login_required
@role_required('hr', 'admin')
def export_employee_data(request):
    """
    Export employee data as a PDF file with a properly formatted table.
    Only accessible to HR and admin roles.
    """
    current_employee = Employee.objects.get(eID=request.user.username)
    
    # Log the export action
    AuditLog.objects.create(
        action_type='other',
        action='Exported Employee Data as PDF',
        performed_by=current_employee,
        details='User exported employee data as PDF.'
    )

    # Fetch all active employees
    employees = Employee.objects.filter(is_active=True, is_archived=False).order_by('eID')

    # Create the PDF response
    buffer = io.BytesIO()
    # Use A4 landscape to accommodate more columns
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(A4[1], A4[0]),  # Landscape orientation (swap width and height)
        leftMargin=0.5*inch,
        rightMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    elements = []

    # Define styles
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=8,  # Smaller font size to fit content
        leading=9,
        alignment=TA_CENTER,
        wordWrap='CJK',  # Enable word wrapping
    )

    # Add title
    elements.append(Paragraph("Employee Data Export", title_style))
    elements.append(Spacer(1, 12))

    # Define column widths (total page width in landscape A4 is ~11.69 inches)
    # After margins (0.5 inch each side), usable width is ~10.69 inches
    # 8 columns: EID, Name, Department, Role, Email, Phone, Join Date, Status
    col_widths = [
        0.8*inch,  # EID
        1.5*inch,  # Name
        1.5*inch,  # Department
        1.0*inch,  # Role
        2.0*inch,  # Email (longer to accommodate email addresses)
        1.2*inch,  # Phone
        1.2*inch,  # Join Date
        0.8*inch,  # Status
    ]

    # Define row heights
    rows_per_page = 20  # Number of rows per page (including header)
    row_heights = [0.3*inch] + [0.5*inch] * (rows_per_page - 1)  # Header: 0.3 inch, Data rows: 0.5 inch

    # Prepare table data
    data = [['EID', 'Name', 'Department', 'Role', 'Email', 'Phone', 'Join Date', 'Status']]
    row_count = 1  # Start with header row

    for employee in employees:
        # Combine first and last name
        name = f"{employee.firstName} {employee.lastName}"
        # Get department name or default
        department = employee.department.name if employee.department else 'No Department'
        # Get status
        status = 'Active' if employee.is_active and not employee.is_archived else 'Inactive'
        # Prepare row data
        row = [
            Paragraph(str(employee.eID), cell_style),
            Paragraph(name, cell_style),
            Paragraph(department, cell_style),
            Paragraph(employee.role.title(), cell_style),
            Paragraph(employee.email or '', cell_style),
            Paragraph(employee.phoneNo or '', cell_style),
            Paragraph(str(employee.joinDate), cell_style),
            Paragraph(status, cell_style),
        ]
        data.append(row)
        row_count += 1

        # If we've reached the row limit for the page, create a table and start a new page
        if row_count >= rows_per_page:
            table = Table(data, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            elements.append(table)
            elements.append(PageBreak())
            # Reset data for the next page, starting with the header
            data = [['EID', 'Name', 'Department', 'Role', 'Email', 'Phone', 'Join Date', 'Status']]
            row_count = 1

    # Add the remaining rows (if any) to a final table
    if len(data) > 1:  # Check if there are rows beyond the header
        # Adjust row heights for the remaining rows
        remaining_rows = len(data)
        row_heights = [0.3*inch] + [0.5*inch] * (remaining_rows - 1)
        table = Table(data, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(table)

    # Build the PDF
    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="employee_data.pdf"'
    return response


@role_required('hr', 'admin')
def export_employee_detail(request, eID):
    employee = get_object_or_404(Employee, eID=eID)
    
    # Fetch the current user's Employee instance
    try:
        current_employee = Employee.objects.get(eID=request.user.username)
    except Employee.DoesNotExist:
        messages.error(request, "Employee profile not found for the current user.")
        return redirect('dashboard')
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(A4[1], A4[0]),  # Landscape orientation
        leftMargin=0.5*inch,
        rightMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    elements = []
    
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=8,
        leading=9,
        wordWrap='CJK',  # Enable text wrapping
    )
    elements.append(Paragraph(f"Employee Profile: {employee.eID}", styles['Title']))
    elements.append(Spacer(1, 12))
    
    # Personal Information
    elements.append(Paragraph("Personal Information", styles['Heading2']))
    personal_col_widths = [2.0*inch, 6.0*inch]  # Label: 2 inch, Value: 6 inch
    personal_data = [
        ['EID', Paragraph(employee.eID, cell_style)],
        ['Name', Paragraph(f"{employee.firstName} {employee.middleName} {employee.lastName}", cell_style)],
        ['Email', Paragraph(employee.email, cell_style)],
        ['Phone', Paragraph(employee.phoneNo, cell_style)],
        ['Aadhar No', Paragraph(employee.addharNo, cell_style)],
        ['Date of Birth', Paragraph(employee.dOB.strftime('%Y-%m-%d'), cell_style)],
        ['Designation', Paragraph(employee.designation, cell_style)],
        ['Department', Paragraph(employee.department.name if employee.department else '—', cell_style)],
        ['Role', Paragraph(dict(role_choices).get(employee.role, employee.role), cell_style)],
        ['Salary', Paragraph(str(employee.salary), cell_style)],
        ['Join Date', Paragraph(employee.joinDate.strftime('%Y-%m-%d'), cell_style)],
        ['Status', Paragraph('Active' if employee.is_active and not employee.is_archived else 'Inactive' if not employee.is_archived else 'Archived', cell_style)],
    ]
    personal_table = Table(personal_data, colWidths=personal_col_widths, rowHeights=[0.3*inch]*len(personal_data))
    personal_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.grey),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(personal_table)
    elements.append(Spacer(1, 12))
    
    # Emergency Contacts
    elements.append(Paragraph("Emergency Contacts", styles['Heading2']))
    emergency_col_widths = [2.0*inch, 1.5*inch, 1.5*inch, 3.0*inch]  # Name, Relationship, Phone, Email
    emergency_data = [['Name', 'Relationship', 'Phone', 'Email']]
    for contact in employee.emergency_contacts.all():
        emergency_data.append([
            Paragraph(contact.name, cell_style),
            Paragraph(contact.relationship, cell_style),
            Paragraph(contact.phone_no, cell_style),
            Paragraph(contact.email or '—', cell_style),
        ])
    if len(emergency_data) == 1:
        emergency_data.append(['No emergency contacts found.', '', '', ''])
    emergency_table = Table(emergency_data, colWidths=emergency_col_widths, rowHeights=[0.3*inch]*len(emergency_data))
    emergency_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(emergency_table)
    elements.append(Spacer(1, 12))
    
    # Documents
    elements.append(Paragraph("Documents", styles['Heading2']))
    document_col_widths = [3.0*inch, 2.0*inch, 2.0*inch]  # Title, Type, Uploaded At
    document_data = [['Title', 'Type', 'Uploaded At']]
    for document in employee.documents.all():
        if not document.is_sensitive or current_employee.role in ['hr', 'admin']:
            document_data.append([
                Paragraph(document.title, cell_style),
                Paragraph(document.get_document_type_display(), cell_style),
                Paragraph(document.uploaded_at.strftime('%Y-%m-%d %H:%M'), cell_style),
            ])
    if len(document_data) == 1:
        document_data.append(['No documents found.', '', ''])
    document_table = Table(document_data, colWidths=document_col_widths, rowHeights=[0.3*inch]*len(document_data))
    document_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(document_table)
    elements.append(Spacer(1, 12))
    
    # Role Change History
    elements.append(Paragraph("Role Change History", styles['Heading2']))
    role_col_widths = [2.0*inch, 2.0*inch, 2.0*inch, 2.0*inch]  # Old Role, New Role, Changed By, Changed At
    role_data = [['Old Role', 'New Role', 'Changed By', 'Changed At']]
    for log in RoleChangeLog.objects.filter(employee=employee).order_by('-changed_at'):
        role_data.append([
            Paragraph(log.old_role.title(), cell_style),
            Paragraph(log.new_role.title(), cell_style),
            Paragraph(f"{log.changed_by.firstName} {log.changed_by.lastName}", cell_style),
            Paragraph(log.changed_at.strftime('%Y-%m-%d %H:%M'), cell_style),
        ])
    if len(role_data) == 1:
        role_data.append(['No role changes found.', '', '', ''])
    role_table = Table(role_data, colWidths=role_col_widths, rowHeights=[0.3*inch]*len(role_data))
    role_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(role_table)
    
    # Build the PDF
    doc.build(elements)
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="employee_{employee.eID}_profile.pdf"'
    
    # Log the export action
    AuditLog.objects.create(
        action_type='other',
        action="Exported Employee Profile",
        performed_by=current_employee,
        details=f"Employee ID: {employee.eID}"
    )
    
    return response


# Manage Roles view (restricted to HR and admins)
@role_required('hr', 'admin')
def manage_roles(request):
    if request.method == "POST":
        employee_id = request.POST.get('employee_id')
        new_role = request.POST.get('role')
        employee = Employee.objects.get(eID=employee_id)
        employee.role = new_role
        employee.save()
        messages.success(request, f"Role updated for {employee.firstName} {employee.lastName}")
        return redirect('manage_roles')

    employees = Employee.objects.all()
    return render(request, 'employee/manage_roles.html', {'employees': employees})



@role_required('hr', 'admin')
def employee_requests(request):
    request_list = LeaveRequest.objects.all().order_by('-request_date')

    paginator = Paginator(request_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.method == 'POST':
        action = request.POST.get('action')
        request_id = request.POST.get('request_id')
        try:
            leave_request = LeaveRequest.objects.get(Id=request_id)
            employee = Employee.objects.get(eID=request.user.username)
            if action == 'approve':
                leave_request.status = 'approved'
                leave_request.save()

                current_date = leave_request.start_date
                while current_date <= leave_request.end_date:
                    attendance_record = Attendance.objects.filter(
                        eId=leave_request.requester,
                        date=current_date
                    ).first()
                    if attendance_record:
                        attendance_record.status = 'leave'
                        attendance_record.check_in_time = None
                        attendance_record.check_out_time = None
                        attendance_record.save()
                    else:
                        Attendance.objects.create(
                            eId=leave_request.requester,
                            date=current_date,
                            status='leave',
                            check_in_time=None,
                            check_out_time=None
                        )
                    current_date += timedelta(days=1)

                try:
                    AuditLog.objects.create(
                        action_type='update',
                        action=f"Approved leave request {request_id}",
                        performed_by=employee,
                        details=f"Leave Request ID: {request_id}, Requester ID: {leave_request.requester.eID}"
                    )
                except Exception as e:
                    messages.warning(request, f"Leave request approved, but failed to log action: {str(e)}")
                messages.success(request, f"Leave request {request_id} approved.")
                Notification.objects.create(
                    recipient=leave_request.requester,
                    message=f"Your leave request (ID: {leave_request.Id}) has been approved by {employee.firstName} {employee.lastName}. <a href='/ems/leave-request-details/{leave_request.Id}/' class='text-blue-600 hover:underline'>View</a>",
                    request_type='leave_request_status',
                    request_id=leave_request.Id
                )
            elif action == 'reject':
                leave_request.status = 'rejected'
                leave_request.save()
                try:
                    AuditLog.objects.create(
                        action_type='update',
                        action=f"Rejected leave request {request_id}",
                        performed_by=employee,
                        details=f"Leave Request ID: {request_id}, Requester ID: {leave_request.requester.eID}"
                    )
                except Exception as e:
                    messages.warning(request, f"Leave request rejected, but failed to log action: {str(e)}")
                messages.success(request, f"Leave request {request_id} rejected.")
                Notification.objects.create(
                    recipient=leave_request.requester,
                    message=f"Your leave request (ID: {leave_request.Id}) has been rejected by {employee.firstName} {employee.lastName}. <a href='/ems/leave-request-details/{leave_request.Id}/' class='text-blue-600 hover:underline'>View</a>",
                    request_type='leave_request_status',
                    request_id=leave_request.Id
                )
        except LeaveRequest.DoesNotExist:
            messages.error(request, "Request not found.")
        return redirect('employee_requests')

    context = {
        'page_obj': page_obj,
    }
    return render(request, 'employee/employee_requests.html', context)


@role_required('hr','manager', 'admin')
def productivity_dashboard(request):
    assigner = Employee.objects.get(eID=request.user.username)
    departments = Employee.objects.values_list('department', flat=True).distinct()

    # Default to the manager's department
    selected_department = request.GET.get('department', assigner.department)

    works = WorkAssignments.objects.filter(assignerId=assigner)
    if selected_department:
        works = works.filter(taskerId__department=selected_department)

    total_tasks = works.count()
    completed_tasks = works.filter(status__in=['completed']).count()
    in_progress_tasks = works.filter(status__in=['in_progress']).count()
    pending_tasks = works.filter(status__in=['pending']).count()
    
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    overdue_tasks = works.filter(dueDate__lt=timezone.now(), status__in=['pending', 'in_progress']).count()
    
    recent_logs = WorkAssignmentLog.objects.filter(work_assignment__assignerId=assigner)
    if selected_department:
        recent_logs = recent_logs.filter(work_assignment__taskerId__department=selected_department)
    recent_logs = recent_logs.order_by('-updated_at')[:10]

    context = {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'in_progress_tasks': in_progress_tasks,
        'pending_tasks': pending_tasks,
        'completion_rate': round(completion_rate, 2),
        'overdue_tasks': overdue_tasks,
        'recent_logs': recent_logs,
        'departments': departments,
        'selected_department': selected_department,
    }
    return render(request, 'employee/productivity_dashboard.html', context)


@role_required('hr','manager', 'admin')
def approve_work(request, work_id):
    work = get_object_or_404(WorkAssignments, Id=work_id)
    manager = Employee.objects.get(eID=request.user.username)
    
    if manager.department != work.taskerId.department:
        messages.error(request, "You are not authorized to approve tasks for this department.")
        return redirect('dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            work.approval_status = 'approved'
            try:
                AuditLog.objects.create(
                    action_type='update',
                    action=f"Approved work assignment {work.Id}",
                    performed_by=manager,
                    details=f"Work ID: {work.Id}, Tasker ID: {work.taskerId.eID}"
                )
            except Exception as e:
                messages.warning(request, f"Work approved, but failed to log action: {str(e)}")
            messages.success(request, "Task approved successfully!")
            Notification.objects.create(
                recipient=work.assignerId,
                message=f"Your task assignment to {work.taskerId.firstName} {work.taskerId.lastName} has been approved by {manager.firstName} {manager.lastName}. <a href='/ems/workdetails/{work.Id}/' class='text-blue-600 hover:underline'>View</a>",
                request_type='managerial_request_status',
                request_id=work.Id
            )
            Notification.objects.create(
                recipient=work.taskerId,
                message=f"Task assigned to you by {work.assignerId.firstName} {work.assignerId.lastName} has been approved: {work.work[:50]}... <a href='/ems/workdetails/{work.Id}/' class='text-blue-600 hover:underline'>View</a>",
                request_type='work_assignment',
                request_id=work.Id
            )
        elif action == 'reject':
            work.approval_status = 'rejected'
            try:
                AuditLog.objects.create(
                    action_type='other',
                    action=f"Rejected work assignment {work.Id}",
                    performed_by=manager,
                    details=f"Work ID: {work.Id}, Tasker ID: {work.taskerId.eID}"
                )
            except Exception as e:
                messages.warning(request, f"Work rejected, but failed to log action: {str(e)}")
            messages.success(request, "Task rejected.")
            Notification.objects.create(
                recipient=work.assignerId,
                message=f"Your task assignment to {work.taskerId.firstName} {work.taskerId.lastName} has been rejected by {manager.firstName} {manager.lastName}. <a href='/ems/workdetails/{work.Id}/' class='text-blue-600 hover:underline'>View</a>",
                request_type='managerial_request_status',
                request_id=work.Id
            )
        work.save()
        return redirect('approve_work', work_id=work_id)

    context = {'work': work}
    return render(request, 'employee/approve_work.html', context)



@role_required('hr','manager', 'admin')
def managerial_requests(request):
    manager = Employee.objects.get(eID=request.user.username)
    # Get tasks assigned to employees in the manager's department with approval_status='pending'
    pending_tasks = WorkAssignments.objects.filter(
        taskerId__department=manager.department,
        approval_status='pending'
    ).order_by('-assignDate')
    
    context = {
        'pending_tasks': pending_tasks,
        'pending_approvals_count': pending_tasks.count(),  # For the sidebar counter
    }
    return render(request, 'employee/managerial_requests.html', context)


@role_required('hr', 'admin')
def manage_roles(request):
    try:
        current_user = Employee.objects.get(eID=request.user.username)
    except Employee.DoesNotExist:
        messages.error(request, "Employee profile not found. Please contact support.")
        return redirect('dashboard')

    if request.method == "POST":
        employee_id = request.POST.get('employee_id')
        try:
            employee = Employee.objects.get(eID=employee_id)
            if employee == current_user:
                messages.error(request, "You cannot modify your own role or permissions.")
                return redirect('manage_roles')

            # Handle toggling can_assign_cross_department
            if 'action' in request.POST and request.POST['action'] == 'toggle_cross_department':
                new_value = 'can_assign_cross_department' in request.POST and request.POST['can_assign_cross_department'] == 'on'
                # Only allow setting can_assign_cross_department=True for manager, hr, or admin roles
                if new_value and employee.role == 'employee':
                    messages.error(request, f"Cannot enable cross-department assignment for {employee.firstName} {employee.lastName}. Employees with the 'employee' role are not allowed to assign work.")
                    return redirect('manage_roles')
                old_value = employee.can_assign_cross_department
                employee.can_assign_cross_department = new_value
                employee.save()
                try:
                    AuditLog.objects.create(
                        action_type='update',
                        action=f"Updated cross-department assignment permission for {employee.firstName} {employee.lastName}",
                        performed_by=current_user,
                        details=f"Employee ID: {employee.eID}, From {old_value} to {new_value}"
                    )
                except Exception as e:
                    messages.warning(request, f"Permission updated, but failed to log action: {str(e)}")
                messages.success(request, f"Cross-department assignment permission for {employee.firstName} {employee.lastName} updated to {new_value}.")
                return redirect('manage_roles')

            # Handle role change
            new_role = request.POST.get('role')
            if employee.role == 'admin' and new_role != 'admin':
                admin_count = Employee.objects.filter(role='admin').count()
                if admin_count <= 1:
                    messages.error(request, "Cannot change the role of the last Admin.")
                    return redirect('manage_roles')
            if employee.role == new_role:
                messages.info(request, f"No change: {employee.firstName} {employee.lastName} is already {new_role}.")
                return redirect('manage_roles')

            critical_roles = ['admin', 'hr']
            if new_role in critical_roles or employee.role in critical_roles:
                pending = PendingRoleChange.objects.create(
                    employee=employee,
                    old_role=employee.role,
                    new_role=new_role,
                    requested_by=current_user
                )
                for reviewer in Employee.objects.filter(role__in=['hr', 'admin']).exclude(eID=current_user.eID):
                    Notification.objects.create(
                        recipient=reviewer,
                        message=f"Role change request for {employee.firstName} {employee.lastName} from {employee.role} to {new_role} awaits your approval. <a href='/ems/review-role-changes/' class='text-blue-600 hover:underline'>Review</a>",
                        request_type='role_change_request',
                        request_id=str(pending.id)
                    )
                try:
                    AuditLog.objects.create(
                        action_type='create',
                        action=f"Requested role change for {employee.firstName} {employee.lastName}",
                        performed_by=current_user,
                        details=f"Employee ID: {employee.eID}, From {employee.role} to {new_role}"
                    )
                except Exception as e:
                    messages.warning(request, f"Role change requested, but failed to log action: {str(e)}")
                messages.success(request, f"Role change request for {employee.firstName} {employee.lastName} to {new_role} submitted for approval.")
            else:
                RoleChangeLog.objects.create(
                    employee=employee,
                    old_role=employee.role,
                    new_role=new_role,
                    changed_by=current_user
                )
                employee.role = new_role
                # Update can_assign_cross_department based on the new role
                if new_role == 'employee':
                    employee.can_assign_cross_department = False  # Ensure it's False for 'employee' role
                else:
                    # For manager, hr, or admin, retain the current value unless explicitly changed
                    # If the role is changing to hr or admin, set to True if not already set
                    if new_role in ['admin', 'hr'] and not employee.can_assign_cross_department:
                        employee.can_assign_cross_department = True
                employee.save()
                try:
                    AuditLog.objects.create(
                        action_type='update',
                        action=f"Changed role of {employee.firstName} {employee.lastName}",
                        performed_by=current_user,
                        details=f"Employee ID: {employee.eID}, From {employee.role} to {new_role}, Can Assign Cross-Department: {employee.can_assign_cross_department}"
                    )
                except Exception as e:
                    messages.warning(request, f"Role changed, but failed to log action: {str(e)}")
                Notification.objects.create(
                    recipient=employee,
                    message=f"Your role has been updated to {new_role} by {current_user.firstName} {current_user.lastName}.",
                    request_type='role_change',
                    request_id=None
                )
                if employee.role != 'manager':
                    manager = Employee.objects.filter(department=employee.department, role='manager').first()
                    if manager and manager != employee:
                        Notification.objects.create(
                            recipient=manager,
                            message=f"{employee.firstName} {employee.lastName}'s role changed to {new_role} by {current_user.firstName} {current_user.lastName}.",
                            request_type='role_change',
                            request_id=None
                        )
                messages.success(request, f"Role updated for {employee.firstName} {employee.lastName} to {new_role}.")
        except Employee.DoesNotExist:
            messages.error(request, "Employee not found.")
        return redirect('manage_roles')

    employees = Employee.objects.all().order_by('firstName', 'lastName')
    name_filter = request.GET.get('name', '')
    dept_filter = request.GET.get('department', '')
    role_filter = request.GET.get('role', '')
    if name_filter:
        employees = employees.filter(
            models.Q(firstName__icontains=name_filter) | 
            models.Q(lastName__icontains=name_filter) | 
            models.Q(eID__icontains=name_filter)
        )
    if dept_filter:
        employees = employees.filter(department__dept_id=dept_filter)
    if role_filter:
        employees = employees.filter(role=role_filter)

    paginator = Paginator(employees, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    departments = Department.objects.all()
    return render(request, 'employee/manage_roles.html', {
        'page_obj': page_obj,
        'role_choices': role_choices,
        'departments': departments,
        'name_filter': name_filter,
        'dept_filter': dept_filter,
        'role_filter': role_filter,
    })

@role_required('hr', 'admin')
def review_role_changes(request):
    try:
        current_user = Employee.objects.get(eID=request.user.username)
    except Employee.DoesNotExist:
        messages.error(request, "Employee profile not found. Please contact support.")
        return redirect('dashboard')

    if request.method == "POST":
        pending_id = request.POST.get('pending_id')
        action = request.POST.get('action')
        try:
            pending = PendingRoleChange.objects.get(id=pending_id, status='pending')
            
            if pending.requested_by == current_user:
                messages.error(request, "You cannot review your own role change request.")
                return redirect('review_role_changes')

            if action == 'approve':
                employee = pending.employee
                RoleChangeLog.objects.create(
                    employee=employee,
                    old_role=pending.old_role,
                    new_role=pending.new_role,
                    changed_by=current_user
                )
                employee.role = pending.new_role
                # Update can_assign_cross_department based on the new role
                if pending.new_role == 'employee':
                    employee.can_assign_cross_department = False  # Ensure it's False for 'employee' role
                else:
                    # For manager, hr, or admin, set to True for hr/admin, retain for manager
                    if pending.new_role in ['admin', 'hr'] and not employee.can_assign_cross_department:
                        employee.can_assign_cross_department = True
                employee.save()
                pending.status = 'approved'
                pending.reviewed_by = current_user
                pending.review_date = timezone.now()
                pending.save()
                try:
                    AuditLog.objects.create(
                        action_type='update',
                        action=f"Approved role change for {employee.firstName} {employee.lastName}",
                        performed_by=current_user,
                        details=f"Employee ID: {employee.eID}, From {pending.old_role} to {pending.new_role}, Can Assign Cross-Department: {employee.can_assign_cross_department}"
                    )
                except Exception as e:
                    messages.warning(request, f"Role change approved, but failed to log action: {str(e)}")
                Notification.objects.create(
                    recipient=employee,
                    message=f"Your role has been updated to {pending.new_role} after approval by {current_user.firstName} {current_user.lastName}.",
                    request_type='role_change',
                    request_id=None
                )
                Notification.objects.create(
                    recipient=pending.requested_by,
                    message=f"Your role change request for {employee.firstName} {employee.lastName} to {pending.new_role} has been approved by {current_user.firstName} {current_user.lastName}. <a href='/ems/role-change-history/' class='text-blue-600 hover:underline'>View History</a>",
                    request_type='role_change_request_status',
                    request_id=str(pending.id)
                )
                messages.success(request, f"Role change request for {employee.firstName} {employee.lastName} approved.")
            elif action == 'reject':
                pending.status = 'rejected'
                pending.reviewed_by = current_user
                pending.review_date = timezone.now()
                pending.save()
                try:
                    AuditLog.objects.create(
                        action_type='other',
                        action=f"Rejected role change for {pending.employee.firstName} {pending.employee.lastName}",
                        performed_by=current_user,
                        details=f"Employee ID: {pending.employee.eID}, From {pending.old_role} to {pending.new_role}"
                    )
                except Exception as e:
                    messages.warning(request, f"Role change rejected, but failed to log action: {str(e)}")
                Notification.objects.create(
                    recipient=pending.requested_by,
                    message=f"Your role change request for {pending.employee.firstName} {pending.employee.lastName} to {pending.new_role} has been rejected by {current_user.firstName} {current_user.lastName}. <a href='/ems/review-role-changes/' class='text-blue-600 hover:underline'>View</a>",
                    request_type='role_change_request_status',
                    request_id=str(pending.id)
                )
                messages.success(request, f"Role change request for {pending.employee.firstName} {pending.employee.lastName} rejected.")
        except PendingRoleChange.DoesNotExist:
            messages.error(request, "Pending role change not found.")
        return redirect('review_role_changes')

    pending_changes = PendingRoleChange.objects.filter(status='pending').order_by('-request_date')
    paginator = Paginator(pending_changes, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'employee/review_role_changes.html', {'page_obj': page_obj})

@role_required('hr', 'admin')
def role_change_history(request):
    logs = RoleChangeLog.objects.all().order_by('-changed_at')
    paginator = Paginator(logs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'employee/role_change_history.html', {'page_obj': page_obj})


@role_required('admin')
def system_settings(request):
    departments = Department.objects.all()
    if request.method == 'POST':
        action = request.POST.get('action')
        employee = get_employee(request)
        if action == 'add_department':
            dept_id = request.POST.get('dept_id')
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            if Department.objects.filter(dept_id=dept_id).exists():
                messages.error(request, "Department ID already exists.")
            else:
                Department.objects.create(dept_id=dept_id, name=name, description=description)
                if employee:
                    try:
                        AuditLog.objects.create(
                            action_type='create',
                            action=f"Added department {name}",
                            performed_by=employee,
                            details=f"Department ID: {dept_id}"
                        )
                    except Exception as e:
                        messages.warning(request, f"Department added, but failed to log action: {str(e)}")
                messages.success(request, f"Department {name} added successfully.")
        elif action == 'delete_department':
            dept_id = request.POST.get('dept_id')
            Department.objects.filter(dept_id=dept_id).delete()
            if employee:
                try:
                    AuditLog.objects.create(
                        action_type='delete',
                        action=f"Deleted department {dept_id}",
                        performed_by=employee,
                        details=f"Department ID: {dept_id}"
                    )
                except Exception as e:
                    messages.warning(request, f"Department deleted, but failed to log action: {str(e)}")
            messages.success(request, "Department deleted successfully.")
        return redirect('system_settings')

    context = {
        'departments': departments,
        'pending_role_changes_count': PendingRoleChange.objects.filter(status='pending').count(),
    }
    return render(request, 'employee/system_settings.html', context)


import datetime  # Explicitly import the datetime module
from django.shortcuts import render
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from django.conf import settings
import os
import csv
from .models import AuditLog, PendingRoleChange
from .decorators import role_required

@role_required('admin')
def audit_logs(request):
    # Debug: Inspect the datetime module
    print("Debug: datetime module:", datetime)
    print("Debug: dir(datetime):", dir(datetime))

    logs = AuditLog.objects.all()

    # Apply filters
    action_filter = request.GET.get('action', '')
    user_filter = request.GET.get('user', '')
    date_filter = request.GET.get('date', '')

    if action_filter:
        logs = logs.filter(action_type=action_filter)
    if user_filter:
        logs = logs.filter(
            Q(performed_by__firstName__icontains=user_filter) |
            Q(performed_by__lastName__icontains=user_filter) |
            Q(performed_by__eID__icontains=user_filter)
        )
    if date_filter:
        try:
            # Use fully qualified path to avoid import ambiguity
            filter_date = datetime.datetime.strptime(date_filter, '%Y-%m-%d').date()
            logs = logs.filter(timestamp__date=filter_date)
        except ValueError:
            messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")

    # Handle export
    export_format = request.GET.get('export', '')
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
        writer = csv.writer(response)
        writer.writerow(['Action Type', 'Action', 'Performed By', 'Timestamp', 'Details'])
        for log in logs:
            writer.writerow([
                log.action_type,
                log.action,
                log.performed_by if log.performed_by else 'System',
                log.timestamp,
                log.details or '—'
            ])
        return response
    elif export_format == 'pdf':
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=0.5*inch, rightMargin=0.5*inch)
        elements = []
        styles = getSampleStyleSheet()
        normal_style = styles['Normal']
        normal_style.fontSize = 8
        normal_style.leading = 10

        # Add the logo (adjust the path to your logo file)
        logo_path = os.path.join(settings.STATIC_ROOT, 'employee', 'logo.png')
        if os.path.exists(logo_path):
            logo = Image(logo_path, width=1*inch, height=1*inch)
            elements.append(logo)
        else:
            elements.append(Paragraph("Employee Tracking System", styles['Title']))

        # Add the title
        elements.append(Paragraph("Audit Log Report", styles['Title']))
        elements.append(Spacer(1, 0.2*inch))

        # Prepare table data
        data = [['Action Type', 'Action', 'Performed By', 'Timestamp', 'Details']]
        for log in logs:
            performed_by = f"{log.performed_by.firstName} {log.performed_by.lastName}" if log.performed_by else 'System'
            # Wrap Action Type, Action, and Details columns in Paragraphs to enable text wrapping
            action_type_paragraph = Paragraph(log.action_type, normal_style)
            action_paragraph = Paragraph(log.action, normal_style)
            details_paragraph = Paragraph(log.details or '—', normal_style)
            data.append([
                action_type_paragraph,
                action_paragraph,
                performed_by,
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                details_paragraph
            ])

        # Create the table with adjusted column widths
        table = Table(data, colWidths=[0.8*inch, 1.5*inch, 1.2*inch, 1.3*inch, 2.7*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),  # Center all cells except Action Type, Action, and Details
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Left-align the Action Type column
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Left-align the Action column
            ('ALIGN', (4, 1), (4, -1), 'LEFT'),  # Left-align the Details column
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)

        # Build the PDF
        doc.build(elements)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="audit_logs.pdf"'
        return response

    logs = logs.order_by('-timestamp')
    paginator = Paginator(logs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'pending_role_changes_count': PendingRoleChange.objects.filter(status='pending').count(),
        'action_filter': action_filter,
        'user_filter': user_filter,
        'date_filter': date_filter,
    }
    return render(request, 'employee/audit_logs.html', context)



@role_required('admin')
def employee_management(request):
    employees = Employee.objects.all().order_by('eID')
    form = EmployeeForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        employee = get_employee(request)  # Current logged-in admin

        if action == 'add':
            form = EmployeeForm(request.POST)
            if form.is_valid():
                try:
                    new_employee = form.save(commit=False)
                    new_employee.has_completed_signup = False  # Employee must sign up
                    new_employee.save()

                    if employee:
                        try:
                            AuditLog.objects.create(
                                action_type='create',
                                action="Employee Added",
                                performed_by=employee,
                                details=f"Employee ID: {new_employee.eID}, Role: {new_employee.role}, Can Assign Cross-Department: {new_employee.can_assign_cross_department}"
                            )
                        except Exception as e:
                            messages.warning(request, f"Employee added, but failed to log action: {str(e)}")
                    messages.success(request, f"Employee {new_employee.eID} added successfully. They must sign up to set their password.")
                    return redirect('employee_management')
                except ValidationError as e:
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            form.add_error(field if field != '__all__' else None, error)
                except IntegrityError as e:
                    form.add_error(None, f"Failed to add employee: {str(e)}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field if field != '__all__' else 'Error'}: {error}")
        elif action == 'deactivate':
            eID = request.POST.get('eID')
            try:
                target_employee = Employee.objects.get(eID=eID)
                if target_employee.role == 'admin' and target_employee.eID == employee.eID:
                    messages.error(request, "You cannot deactivate your own account.")
                else:
                    target_employee.is_active = False
                    target_employee.save()
                    try:
                        AuditLog.objects.create(
                            action_type='update',
                            action="Employee Deactivated",
                            performed_by=employee,
                            details=f"Employee ID: {eID}"
                        )
                    except Exception as e:
                        messages.warning(request, f"Employee deactivated, but failed to log action: {str(e)}")
                    messages.success(request, f"Employee {eID} has been deactivated.")
            except Employee.DoesNotExist:
                messages.error(request, f"Employee with ID {eID} does not exist.")
            return redirect('employee_management')
        elif action == 'activate':
            eID = request.POST.get('eID')
            try:
                target_employee = Employee.objects.get(eID=eID)
                if target_employee.is_archived:
                    messages.error(request, "You must unarchive the employee before activating their account.")
                else:
                    target_employee.is_active = True
                    target_employee.save()
                    try:
                        AuditLog.objects.create(
                            action_type='update',
                            action="Employee Activated",
                            performed_by=employee,
                            details=f"Employee ID: {eID}"
                        )
                    except Exception as e:
                        messages.warning(request, f"Employee activated, but failed to log action: {str(e)}")
                    messages.success(request, f"Employee {eID} has been activated.")
            except Employee.DoesNotExist:
                messages.error(request, f"Employee with ID {eID} does not exist.")
            return redirect('employee_management')
        elif action == 'archive':
            eID = request.POST.get('eID')
            try:
                target_employee = Employee.objects.get(eID=eID)
                if target_employee.role == 'admin' and target_employee.eID == employee.eID:
                    messages.error(request, "You cannot archive your own account.")
                else:
                    target_employee.is_archived = True
                    target_employee.is_active = False
                    target_employee.save()
                    try:
                        AuditLog.objects.create(
                            action_type='update',
                            action="Employee Archived",
                            performed_by=employee,
                            details=f"Employee ID: {eID}, Archived At: {target_employee.archived_at}"
                        )
                    except Exception as e:
                        messages.warning(request, f"Employee archived, but failed to log action: {str(e)}")
                    messages.success(request, f"Employee {eID} has been archived.")
            except Employee.DoesNotExist:
                messages.error(request, f"Employee with ID {eID} does not exist.")
            return redirect('employee_management')
        elif action == 'unarchive':
            eID = request.POST.get('eID')
            try:
                target_employee = Employee.objects.get(eID=eID)
                target_employee.is_archived = False
                target_employee.save()
                try:
                    AuditLog.objects.create(
                        action_type='update',
                        action="Employee Unarchived",
                        performed_by=employee,
                        details=f"Employee ID: {eID}"
                    )
                except Exception as e:
                    messages.warning(request, f"Employee unarchived, but failed to log action: {str(e)}")
                messages.success(request, f"Employee {eID} has been unarchived.")
            except Employee.DoesNotExist:
                messages.error(request, f"Employee with ID {eID} does not exist.")
            return redirect('employee_management')

    context = {
        'employees': employees,
        'form': form,
        'pending_role_changes_count': PendingRoleChange.objects.filter(status='pending').count(),
    }
    return render(request, 'employee/employee_management.html', context)

@role_required('employee', 'manager', 'hr', 'admin')
def leave_request_details(request, rid):
    leave_request = get_object_or_404(LeaveRequest, Id=rid)
    employee = Employee.objects.get(eID=request.user.username)

    # Restrict access to requester or destination employee
    if leave_request.requester != employee and leave_request.destination_employee != employee:
        messages.error(request, "You are not authorized to view this leave request.")
        return redirect('dashboard')

    return render(request, "employee/leave_request_details.html", {
        "leave_request": leave_request,
        "can_process": leave_request.destination_employee == employee and leave_request.status == 'pending',
    })


@role_required('hr', 'admin')
def manage_notices(request):
    notices = Notice.objects.all()
    # Add filtering by urgency
    is_urgent = request.GET.get('is_urgent')
    if is_urgent in ['true', 'false']:
        notices = notices.filter(is_urgent=(is_urgent == 'true'))

    # Add sorting
    sort_by = request.GET.get('sort_by', '-publishDate')
    notices = notices.order_by(sort_by)

    context = {
        'notices': notices,
    }
    return render(request, 'employee/manage_notices.html', context)


from django.core.paginator import Paginator
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from .models import Employee, LeaveRequest, AuditLog, Notification
from .decorators import role_required

@role_required('employee', 'manager')
def leave_request(request):
    employee = Employee.objects.get(eID=request.user.username)
    today = timezone.now().date()
    
    if request.method == 'POST':
        start_date_str = request.POST.get('leave_start_date')
        end_date_str = request.POST.get('leave_end_date')
        reason = request.POST.get('leave_reason')
        
        try:
            # Use datetime.datetime.strptime to parse the date strings
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            if start_date < today:
                messages.error(request, "Start date cannot be in the past.")
            elif end_date < start_date:
                messages.error(request, "End date cannot be before start date.")
            else:
                # Route leave request to HR, with admin as backup
                destination_employee = Employee.objects.filter(role='hr').first()
                if not destination_employee:
                    destination_employee = Employee.objects.filter(role='admin').first()
                
                if not destination_employee:
                    messages.error(request, "No HR or admin available to process this leave request.")
                else:
                    leave_request = LeaveRequest.objects.create(
                        Id=f"LEAVE{timezone.now().strftime('%Y%m%d%H%M%S')}",
                        requester=employee,
                        request_message=reason,
                        request_date=timezone.now(),
                        destination_employee=destination_employee,
                        status='pending',
                        start_date=start_date,
                        end_date=end_date,
                        is_compulsory=False
                    )
                    try:
                        AuditLog.objects.create(
                            action_type='create',
                            action=f"Submitted leave request {leave_request.Id}",
                            performed_by=employee,
                            details=f"Leave Request ID: {leave_request.Id}, Start Date: {start_date}, End Date: {end_date}"
                        )
                    except Exception as e:
                        messages.warning(request, f"Leave request submitted, but failed to log action: {str(e)}")
                    Notification.objects.create(
                        recipient=destination_employee,
                        message=f"New leave request from {employee.firstName} {employee.lastName}: {reason[:50]}... <a href='/ems/leave-request-details/{leave_request.Id}/' class='text-blue-600 hover:underline'>View</a>",
                        request_type='leave_request',
                        request_id=leave_request.Id
                    )
                    messages.success(request, "Leave request submitted successfully!")
        except ValueError:
            messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")
        
        return redirect('leave_request')
    
    # Display employee's past leave requests
    leave_requests = LeaveRequest.objects.filter(requester=employee).order_by('-request_date')
    paginator = Paginator(leave_requests, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'employee': employee,
        'page_obj': page_obj,
    }
    return render(request, 'employee/leave_request.html', context)


@role_required('hr', 'admin')
def issue_compulsory_leave(request):
    employee = Employee.objects.get(eID=request.user.username)
    today = timezone.now().date()
    
    if request.method == 'POST':
        target_employee_id = request.POST.get('employee_id')
        start_date_str = request.POST.get('leave_start_date')
        end_date_str = request.POST.get('leave_end_date')
        reason = request.POST.get('leave_reason')
        
        try:
            target_employee = Employee.objects.get(eID=target_employee_id)
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            if start_date < today:
                messages.error(request, "Start date cannot be in the past.")
            elif end_date < start_date:
                messages.error(request, "End date cannot be before start date.")
            else:
                # Create compulsory leave request (automatically approved)
                leave_request = LeaveRequest.objects.create(
                    Id=f"LEAVE{timezone.now().strftime('%Y%m%d%H%M%S')}",
                    requester=target_employee,
                    request_message=reason,
                    request_date=timezone.now(),
                    destination_employee=employee,  # Issued by HR/admin
                    status='approved',
                    start_date=start_date,
                    end_date=end_date,
                    is_compulsory=True
                )
                # Update attendance records for the leave period
                current_date = start_date
                while current_date <= end_date:
                    attendance_record = Attendance.objects.filter(
                        eId=target_employee,
                        date=current_date
                    ).first()
                    if attendance_record:
                        attendance_record.status = 'leave'
                        attendance_record.check_in_time = None
                        attendance_record.check_out_time = None
                        attendance_record.save()
                    else:
                        Attendance.objects.create(
                            eId=target_employee,
                            date=current_date,
                            status='leave',
                            check_in_time=None,
                            check_out_time=None
                        )
                    current_date += timedelta(days=1)
                
                try:
                    AuditLog.objects.create(
                        action_type='create',
                        action=f"Issued compulsory leave {leave_request.Id}",
                        performed_by=employee,
                        details=f"Leave Request ID: {leave_request.Id}, Employee ID: {target_employee.eID}, Start Date: {start_date}, End Date: {end_date}"
                    )
                except Exception as e:
                    messages.warning(request, f"Compulsory leave issued, but failed to log action: {str(e)}")
                Notification.objects.create(
                    recipient=target_employee,
                    message=f"You have been issued a compulsory leave by {employee.firstName} {employee.lastName} from {start_date} to {end_date}. Reason: {reason[:50]}... <a href='/ems/leave-request-details/{leave_request.Id}/' class='text-blue-600 hover:underline'>View</a>",
                    request_type='leave_request',
                    request_id=leave_request.Id
                )
                messages.success(request, f"Compulsory leave issued to {target_employee.firstName} {target_employee.lastName} successfully!")
        except Employee.DoesNotExist:
            messages.error(request, "Employee not found.")
        except ValueError:
            messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")
        
        return redirect('issue_compulsory_leave')
    
    # List all employees for HR/admin to select
    employees = Employee.objects.exclude(eID=employee.eID)
    
    context = {
        'employee': employee,
        'employees': employees,
    }
    return render(request, 'employee/issue_compulsory_leave.html', context)



from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import Count, Q, F, Avg
from django.utils import timezone
from datetime import timedelta
import csv
from collections import defaultdict
from django.utils.timezone import make_naive
from .decorators import role_required
from .forms import CustomReportForm, PerformanceReviewTemplateForm, ReviewQuestionForm, PerformanceReviewScheduleForm, ReviewResponseForm
from .models import Employee, Attendance, LeaveRequest, PerformanceReview, ReviewResponse, WorkAssignments, RoleChangeLog, PendingRoleChange, AuditLog, PerformanceReviewTemplate, ReviewQuestion, Notification, Department
from django.apps import apps
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from django.contrib import messages
from django.forms import formset_factory
import io

@login_required
@role_required('hr', 'admin')
def standard_hr_reports(request):
    # Log the access to standard reports
    current_employee = Employee.objects.get(eID=request.user.username)
    AuditLog.objects.create(
        action_type='other',
        action='Viewed Standard HR Reports',
        performed_by=current_employee,
        details='User accessed the Standard HR Reports page.'
    )

    # Headcount
    headcount = Employee.objects.filter(is_active=True, is_archived=False).count()
    headcount_by_dept = Employee.objects.filter(is_active=True, is_archived=False) \
        .values('department__name').annotate(count=Count('eID')).order_by('department__name')

    # Turnover Rate (last 12 months)
    one_year_ago = timezone.now().date() - timedelta(days=365)
    total_employees_start = Employee.objects.filter(
        joinDate__lte=one_year_ago,
        is_active=True
    ).count()
    turnovers = Employee.objects.filter(
        is_archived=True,
        archived_at__gte=one_year_ago,
        archived_at__lte=timezone.now().date()
    ).count()
    turnover_rate = (turnovers / total_employees_start * 100) if total_employees_start > 0 else 0

    # Attendance Summary (last 30 days)
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    attendance_summary = Attendance.objects.filter(
        date__gte=thirty_days_ago,
        date__lte=timezone.now().date()
    ).values('status').annotate(count=Count('id')).order_by('status')

    # Leave Taken
    leave_requests = LeaveRequest.objects.filter(
        status='approved',
        end_date__lte=timezone.now().date()
    ).select_related('requester')

    leave_data = {}
    for leave in leave_requests:
        employee_id = leave.requester.eID
        if employee_id not in leave_data:
            leave_data[employee_id] = {
                'requester__eID': leave.requester.eID,
                'requester__firstName': leave.requester.firstName,
                'requester__lastName': leave.requester.lastName,
                'days_taken': 0
            }
        days = (leave.end_date - leave.start_date).days + 1
        leave_data[employee_id]['days_taken'] += days

    leave_taken = list(leave_data.values())
    leave_taken.sort(key=lambda x: x['requester__eID'])

    # Performance Review Summary
    total_reviews = PerformanceReview.objects.count()
    completed_reviews = PerformanceReview.objects.filter(status='completed').count()
    completion_rate = (completed_reviews / total_reviews * 100) if total_reviews > 0 else 0

    avg_ratings = ReviewResponse.objects.filter(
        response_type='employee',
        rating__isnull=False,
        review__status='completed'
    ).values('review__employee__eID', 'review__employee__firstName', 'review__employee__lastName') \
     .annotate(avg_rating=Avg('rating')).order_by('review__employee__eID')

    avg_ratings_by_dept = ReviewResponse.objects.filter(
        response_type='employee',
        rating__isnull=False,
        review__status='completed'
    ).values('review__employee__department__name') \
     .annotate(avg_rating=Avg('rating')).order_by('review__employee__department__name')

    # Work Assignment Status
    work_assignments = WorkAssignments.objects.all()
    task_status_summary = work_assignments.values('status').annotate(count=Count('Id')).order_by('status')

    task_completion = work_assignments.values('taskerId__eID', 'taskerId__firstName', 'taskerId__lastName') \
        .annotate(
            total_tasks=Count('Id'),
            completed_tasks=Count('Id', filter=Q(status='completed'))
        ).order_by('taskerId__eID')
    for task in task_completion:
        task['completion_rate'] = (task['completed_tasks'] / task['total_tasks'] * 100) if task['total_tasks'] > 0 else 0

    # Role Change Audit
    role_changes = RoleChangeLog.objects.all()
    role_changes_by_month_dict = defaultdict(int)
    for change in role_changes:
        changed_at = make_naive(change.changed_at) if timezone.is_aware(change.changed_at) else change.changed_at
        month_key = changed_at.strftime('%Y-%m')
        role_changes_by_month_dict[month_key] += 1

    role_changes_by_month = [
        {'month': month, 'count': count}
        for month, count in sorted(role_changes_by_month_dict.items())
    ]

    pending_role_changes = PendingRoleChange.objects.filter(status='pending').count()

    role_transitions = role_changes.values('old_role', 'new_role') \
        .annotate(count=Count('id')).order_by('-count')[:5]

    # Export as PDF
    if 'export_pdf' in request.GET:
        AuditLog.objects.create(
            action_type='other',
            action='Exported Standard HR Reports as PDF',
            performed_by=current_employee,
            details='User exported Standard HR Reports as PDF.'
        )
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []

        styles = getSampleStyleSheet()
        elements.append(Paragraph("Standard HR Reports", styles['Title']))
        elements.append(Spacer(1, 12))

        # Headcount
        elements.append(Paragraph("Headcount", styles['Heading2']))
        elements.append(Paragraph(f"Total Active Employees: {headcount}", styles['Normal']))
        elements.append(Spacer(1, 12))
        headcount_data = [['Department', 'Count']]
        for dept in headcount_by_dept:
            headcount_data.append([dept['department__name'] or 'No Department', dept['count']])
        headcount_table = Table(headcount_data)
        headcount_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(headcount_table)
        elements.append(Spacer(1, 12))

        # Turnover Rate
        elements.append(Paragraph("Turnover Rate (Last 12 Months)", styles['Heading2']))
        elements.append(Paragraph(f"Turnover Rate: {turnover_rate:.2f}%", styles['Normal']))
        elements.append(Spacer(1, 12))

        # Attendance Summary
        elements.append(Paragraph("Attendance Summary (Last 30 Days)", styles['Heading2']))
        attendance_data = [['Status', 'Count']]
        for summary in attendance_summary:
            attendance_data.append([summary['status'].title(), summary['count']])
        attendance_table = Table(attendance_data)
        attendance_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(attendance_table)
        elements.append(Spacer(1, 12))

        # Leave Taken
        elements.append(Paragraph("Leave Taken", styles['Heading2']))
        leave_data_table = [['Employee ID', 'Name', 'Days Taken']]
        for leave in leave_taken:
            name = f"{leave['requester__firstName']} {leave['requester__lastName']}"
            leave_data_table.append([leave['requester__eID'], name, leave['days_taken']])
        leave_table = Table(leave_data_table)
        leave_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(leave_table)
        elements.append(Spacer(1, 12))

        # Performance Review Summary
        elements.append(Paragraph("Performance Review Summary", styles['Heading2']))
        elements.append(Paragraph(f"Completion Rate: {completion_rate:.2f}%", styles['Normal']))
        elements.append(Spacer(1, 12))
        ratings_data = [['Employee ID', 'Name', 'Average Rating']]
        for rating in avg_ratings:
            name = f"{rating['review__employee__firstName']} {rating['review__employee__lastName']}"
            ratings_data.append([rating['review__employee__eID'], name, f"{rating['avg_rating']:.2f}"])
        ratings_table = Table(ratings_data)
        ratings_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(ratings_table)
        elements.append(Spacer(1, 12))
        dept_ratings_data = [['Department', 'Average Rating']]
        for dept_rating in avg_ratings_by_dept:
            dept_ratings_data.append([dept_rating['review__employee__department__name'] or 'No Department', f"{dept_rating['avg_rating']:.2f}"])
        dept_ratings_table = Table(dept_ratings_data)
        dept_ratings_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(dept_ratings_table)
        elements.append(Spacer(1, 12))

        # Work Assignment Status
        elements.append(Paragraph("Work Assignment Status", styles['Heading2']))
        task_status_data = [['Status', 'Count']]
        for summary in task_status_summary:
            task_status_data.append([summary['status'].title(), summary['count']])
        task_status_table = Table(task_status_data)
        task_status_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(task_status_table)
        elements.append(Spacer(1, 12))
        task_completion_data = [['Employee ID', 'Name', 'Total Tasks', 'Completed Tasks', 'Completion Rate (%)']]
        for task in task_completion:
            name = f"{task['taskerId__firstName']} {task['taskerId__lastName']}"
            task_completion_data.append([
                task['taskerId__eID'], name, task['total_tasks'], task['completed_tasks'], f"{task['completion_rate']:.2f}"
            ])
        task_completion_table = Table(task_completion_data)
        task_completion_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(task_completion_table)
        elements.append(Spacer(1, 12))

        # Role Change Audit
        elements.append(Paragraph("Role Change Audit", styles['Heading2']))
        elements.append(Paragraph(f"Pending Role Changes: {pending_role_changes}", styles['Normal']))
        elements.append(Spacer(1, 12))
        role_changes_data = [['Month', 'Count']]
        for change in role_changes_by_month:
            role_changes_data.append([change['month'], change['count']])
        role_changes_table = Table(role_changes_data)
        role_changes_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(role_changes_table)
        elements.append(Spacer(1, 12))
        role_transitions_data = [['From Role', 'To Role', 'Count']]
        for transition in role_transitions:
            role_transitions_data.append([transition['old_role'].title(), transition['new_role'].title(), transition['count']])
        role_transitions_table = Table(role_transitions_data)
        role_transitions_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(role_transitions_table)

        doc.build(elements)
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="standard_hr_reports.pdf"'
        return response

    # Export as CSV
    if 'export' in request.GET:
        AuditLog.objects.create(
            action_type='other',
            action='Exported Standard HR Reports',
            performed_by=current_employee,
            details='User exported Standard HR Reports as CSV.'
        )
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="hr_reports.csv"'
        writer = csv.writer(response)

        writer.writerow(['Headcount'])
        writer.writerow(['Total Active Employees', headcount])
        writer.writerow(['Department', 'Count'])
        for dept in headcount_by_dept:
            writer.writerow([dept['department__name'] or 'No Department', dept['count']])
        writer.writerow([])

        writer.writerow(['Turnover Rate (Last 12 Months)'])
        writer.writerow(['Turnovers', turnovers])
        writer.writerow(['Total Employees at Start', total_employees_start])
        writer.writerow(['Turnover Rate (%)', f"{turnover_rate:.2f}"])
        writer.writerow([])

        writer.writerow(['Attendance Summary (Last 30 Days)'])
        writer.writerow(['Status', 'Count'])
        for summary in attendance_summary:
            writer.writerow([summary['status'].title(), summary['count']])
        writer.writerow([])

        writer.writerow(['Leave Taken'])
        writer.writerow(['Employee ID', 'Name', 'Days Taken'])
        for leave in leave_taken:
            name = f"{leave['requester__firstName']} {leave['requester__lastName']}"
            writer.writerow([leave['requester__eID'], name, leave['days_taken']])
        writer.writerow([])

        writer.writerow(['Performance Review Summary'])
        writer.writerow(['Completion Rate (%)', f"{completion_rate:.2f}"])
        writer.writerow(['Employee ID', 'Name', 'Average Rating'])
        for rating in avg_ratings:
            name = f"{rating['review__employee__firstName']} {rating['review__employee__lastName']}"
            writer.writerow([rating['review__employee__eID'], name, f"{rating['avg_rating']:.2f}"])
        writer.writerow(['Department', 'Average Rating'])
        for dept_rating in avg_ratings_by_dept:
            writer.writerow([dept_rating['review__employee__department__name'] or 'No Department', f"{dept_rating['avg_rating']:.2f}"])
        writer.writerow([])

        writer.writerow(['Work Assignment Status'])
        writer.writerow(['Status', 'Count'])
        for summary in task_status_summary:
            writer.writerow([summary['status'].title(), summary['count']])
        writer.writerow(['Employee ID', 'Name', 'Total Tasks', 'Completed Tasks', 'Completion Rate (%)'])
        for task in task_completion:
            name = f"{task['taskerId__firstName']} {task['taskerId__lastName']}"
            writer.writerow([task['taskerId__eID'], name, task['total_tasks'], task['completed_tasks'], f"{task['completion_rate']:.2f}"])
        writer.writerow([])

        writer.writerow(['Role Change Audit'])
        writer.writerow(['Pending Role Changes', pending_role_changes])
        writer.writerow(['Month', 'Count'])
        for change in role_changes_by_month:
            writer.writerow([change['month'], change['count']])
        writer.writerow(['From Role', 'To Role', 'Count'])
        for transition in role_transitions:
            writer.writerow([transition['old_role'].title(), transition['new_role'].title(), transition['count']])

        return response

    context = {
        'headcount': headcount,
        'headcount_by_dept': headcount_by_dept,
        'turnover_rate': turnover_rate,
        'attendance_summary': attendance_summary,
        'leave_taken': leave_taken,
        'avg_ratings': avg_ratings,
        'avg_ratings_by_dept': avg_ratings_by_dept,
        'completion_rate': completion_rate,
        'task_status_summary': task_status_summary,
        'task_completion': task_completion,
        'role_changes_by_month': role_changes_by_month,
        'pending_role_changes': pending_role_changes,
        'role_transitions': role_transitions,
    }
    return render(request, 'employee/standard_hr_reports.html', context)

def analyze_sentiment(text):
    if not text:
        return "Neutral"
    positive_words = ['good', 'great', 'excellent', 'positive', 'happy', 'satisfied']
    negative_words = ['bad', 'poor', 'terrible', 'negative', 'unhappy', 'dissatisfied']
    text_lower = text.lower()
    if any(word in text_lower for word in positive_words):
        return "Positive"
    if any(word in text_lower for word in negative_words):
        return "Negative"
    return "Neutral"

@login_required
@role_required('hr', 'admin')
def view_template_details(request, template_id):
    template = get_object_or_404(PerformanceReviewTemplate, id=template_id)
    reviews = PerformanceReview.objects.filter(template=template).order_by('-scheduled_date')
    questions = template.questions.all()

    # Calculate completion rate for this template
    total_reviews = reviews.count()
    completed_reviews = reviews.filter(status='completed').count()
    template_completion_rate = (completed_reviews / total_reviews * 100) if total_reviews > 0 else 0

    # Analyze responses
    analysis = {
        'avg_rating_per_question': [],
        'sentiment_summary': {'positive': 0, 'neutral': 0, 'negative': 0},
        'rating_summary': {'positive': 0, 'neutral': 0, 'negative': 0},
    }

    # Average rating per question
    for question in questions:
        responses = ReviewResponse.objects.filter(
            question=question,
            review__template=template,
            review__status='completed'
        )
        if question.question_type == 'rating':
            avg_rating = responses.filter(rating__isnull=False).aggregate(avg=Avg('rating'))['avg']
            analysis['avg_rating_per_question'].append({
                'question_text': question.question_text,
                'avg_rating': avg_rating if avg_rating is not None else 0,
                'total_responses': responses.count(),
            })

    # Sentiment and rating summary
    all_responses = ReviewResponse.objects.filter(
        review__template=template,
        review__status='completed'
    )
    for response in all_responses:
        if response.rating is not None:
            if response.rating >= 4:
                analysis['rating_summary']['positive'] += 1
            elif response.rating == 3:
                analysis['rating_summary']['neutral'] += 1
            else:
                analysis['rating_summary']['negative'] += 1
        if response.text_response:
            sentiment = analyze_sentiment(response.text_response)
            analysis['sentiment_summary'][sentiment.lower()] += 1

    # Prepare reviews with their responses
    reviews_with_responses = []
    for review in reviews:
        responses = review.responses.all()
        reviews_with_responses.append({
            'review': review,
            'responses': responses,
        })

    context = {
        'template': template,
        'reviews_with_responses': reviews_with_responses,
        'questions': questions,
        'template_completion_rate': template_completion_rate,
        'analysis': analysis,
    }
    return render(request, 'employee/template_details.html', context)

@login_required
@role_required('hr', 'admin')
def manage_review_templates(request):
    templates = PerformanceReviewTemplate.objects.all()
    return render(request, 'employee/manage_review_templates.html', {'templates': templates})

@login_required
@role_required('hr', 'admin')
def create_review_template(request):
    template_form = PerformanceReviewTemplateForm(request.POST or None)
    ReviewQuestionFormSet = formset_factory(ReviewQuestionForm, extra=3)

    if request.method == 'POST':
        formset = ReviewQuestionFormSet(request.POST)
        if template_form.is_valid() and formset.is_valid():
            template = template_form.save(commit=False)
            template.created_by = Employee.objects.get(eID=request.user.username)
            template.save()
            for form in formset:
                if form.cleaned_data:
                    question = form.save(commit=False)
                    question.template = template
                    question.save()
            messages.success(request, "Performance review template created successfully.")
            return redirect('manage_review_templates')
    else:
        formset = ReviewQuestionFormSet()

    return render(request, 'employee/create_review_template.html', {
        'template_form': template_form,
        'formset': formset,
    })

@login_required
@role_required('hr', 'admin')
def schedule_performance_review(request):
    form = PerformanceReviewScheduleForm(request.POST or None)
    departments = Department.objects.all()
    dept_employee_map = {
        dept.dept_id: list(Employee.objects.filter(department=dept, is_active=True, is_archived=False).values('eID', 'firstName', 'lastName'))
        for dept in departments
    }
    dept_employee_map["0"] = list(Employee.objects.filter(is_active=True, is_archived=False).values('eID', 'firstName', 'lastName'))

    if request.method == 'POST' and form.is_valid():
        department = form.cleaned_data.get('department')
        employee = form.cleaned_data.get('employee')
        template = form.cleaned_data['template']
        scheduled_date = form.cleaned_data['scheduled_date']

        if employee:
            review = PerformanceReview.objects.create(
                employee=employee,
                template=template,
                scheduled_date=scheduled_date,
                status='pending'
            )
            Notification.objects.create(
                recipient=review.employee,
                message=f"A new performance review has been scheduled for you on {scheduled_date}.",
                request_type='performance_review',
                request_id=str(review.id)
            )
            messages.success(request, f"Performance review scheduled for {review.employee}.")
        else:
            if department:
                employees = Employee.objects.filter(department=department, is_active=True, is_archived=False)
                message = f"Performance reviews scheduled for all employees in {department.name}."
            else:
                employees = Employee.objects.filter(is_active=True, is_archived=False)
                message = "Performance reviews scheduled for all employees across all departments."

            for emp in employees:
                review = PerformanceReview.objects.create(
                    employee=emp,
                    template=template,
                    scheduled_date=scheduled_date,
                    status='pending'
                )
                Notification.objects.create(
                    recipient=emp,
                    message=f"A new performance review has been scheduled for you on {scheduled_date}.",
                    request_type='performance_review',
                    request_id=str(review.id)
                )
            messages.success(request, message)

        return redirect('manage_review_templates')

    return render(request, 'employee/schedule_performance_review.html', {
        'form': form,
        'dept_employee_map': dept_employee_map,
    })

@login_required
def submit_performance_review(request, review_id):
    review = get_object_or_404(PerformanceReview, id=review_id)
    current_employee = get_object_or_404(Employee, eID=request.user.username)

    # Only allow the employee being reviewed to submit the review
    if current_employee != review.employee:
        messages.error(request, "You are not authorized to submit this review.")
        return redirect('dashboard')

    # Prevent resubmission if the review is already completed
    if review.status != 'pending':
        messages.error(request, "This performance review has already been submitted.")
        return redirect('dashboard')

    questions = review.template.questions.all()
    if not questions:
        messages.error(request, "This performance review has no questions to answer.")
        return redirect('dashboard')

    # Initialize forms for each question
    forms = [ReviewResponseForm(prefix=f"question-{question.id}", question=question) for question in questions]
    
    if request.method == 'POST':
        forms = [ReviewResponseForm(request.POST, prefix=f"question-{question.id}", question=question) for question in questions]
        all_valid = True
        for form in forms:
            if not form.is_valid():
                all_valid = False
                # Add a message for each invalid form to help the user
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"Error in response for '{form.question.question_text}' ({field}): {error}")

        if all_valid:
            # Save responses
            for question, form in zip(questions, forms):
                response = form.save(commit=False)
                response.review = review
                response.question = question
                response.respondent = current_employee
                response.response_type = 'employee'
                response.save()

            # Update review status to 'completed'
            review.status = 'completed'
            review.save()

            # Notify HR personnel
            hr_personnel = Employee.objects.filter(role='hr', is_active=True, is_archived=False)
            for hr in hr_personnel:
                Notification.objects.create(
                    recipient=hr,
                    message=f"Performance review for {review.employee} scheduled on {review.scheduled_date} has been completed.",
                    request_type='performance_review',
                    request_id=str(review.id)
                )

            messages.success(request, "Your performance review has been submitted successfully.")
            return redirect('dashboard')

    question_form_pairs = zip(questions, forms)

    return render(request, 'employee/submit_performance_review.html', {
        'review': review,
        'question_form_pairs': question_form_pairs,
        'response_type': 'employee',
    })

@login_required
def view_performance_reviews(request):
    current_employee = get_object_or_404(Employee, eID=request.user.username)
    reviews = PerformanceReview.objects.filter(employee=current_employee).order_by('-scheduled_date')
    return render(request, 'employee/view_performance_reviews.html', {'reviews': reviews})

@login_required
def performance_review_detail(request, review_id):
    review = get_object_or_404(PerformanceReview, id=review_id)
    current_employee = get_object_or_404(Employee, eID=request.user.username)

    if current_employee != review.employee and current_employee.role not in ['manager', 'hr', 'admin']:
        messages.error(request, "You are not authorized to view this review.")
        return redirect('dashboard')

    responses = review.responses.all()
    analysis = {
        'rating_summary': {'positive': 0, 'neutral': 0, 'negative': 0},
        'text_sentiments': [],
        'average_rating': None,
        'feedback_summary': [],
    }

    if current_employee.role in ['hr', 'admin']:
        ratings = [r.rating for r in responses if r.rating is not None]
        for rating in ratings:
            if rating >= 4:
                analysis['rating_summary']['positive'] += 1
            elif rating == 3:
                analysis['rating_summary']['neutral'] += 1
            else:
                analysis['rating_summary']['negative'] += 1
        analysis['average_rating'] = sum(ratings) / len(ratings) if ratings else None

        for response in responses:
            if response.text_response:
                sentiment = analyze_sentiment(response.text_response)
                analysis['text_sentiments'].append({
                    'question': response.question.question_text,
                    'response': response.text_response,
                    'sentiment': sentiment,
                })
                if response.response_type == 'employee':
                    analysis['feedback_summary'].append(response.text_response)

    return render(request, 'employee/performance_review_detail.html', {
        'review': review,
        'responses': responses,
        'analysis': analysis if current_employee.role in ['hr', 'admin'] else None,
    })

@login_required
@role_required('hr', 'admin')
def view_submitted_reviews(request):
    reviews = PerformanceReview.objects.filter(
        status='completed'
    ).order_by('-scheduled_date')
    return render(request, 'employee/view_submitted_reviews.html', {'reviews': reviews})


from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Avg, Sum, Min, Max, Count
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
import csv
import datetime
from .forms import CustomReportForm
from django.apps import apps
from django.db import models
from .models import Employee, Document, AuditLog, EmergencyContact, Notification, IssueReport, Requests, WorkAssignmentLog, RoleChangeLog, PendingRoleChange, LeaveRequest, WorkAssignments, Notice, IssueComment, Department

@login_required
@role_required('hr', 'admin')
def custom_report_builder(request):
    form = CustomReportForm(request.POST or None, request=request)
    results = None
    header_field_pairs = None
    aggregation_result = None
    current_employee = Employee.objects.get(eID=request.user.username)
    paginated_results = None

    # Helper function to generate the report queryset
    def generate_report(form_data, employee):
        # Convert string dates back to date objects if they exist
        start_date = form_data.get('start_date')
        if start_date and isinstance(start_date, str):
            start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = form_data.get('end_date')
        if end_date and isinstance(end_date, str):
            end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()

        # Retrieve Department instance from dept_id if stored in session
        department_id = form_data.get('department')
        department = None
        if department_id:
            try:
                department = Department.objects.get(dept_id=department_id)
            except Department.DoesNotExist:
                messages.error(request, f"Department with ID {department_id} does not exist.")
                return [], [], None, []

        model_name = form_data['model']
        selected_fields = form_data['fields']
        date_field = form_data['date_field']
        status_field = form_data['status_field']
        status_value = form_data['status_value']
        aggregation = form_data['aggregation']
        aggregation_field = form_data['aggregation_field']
        is_urgent = form_data.get('is_urgent', False)
        feedback_satisfactory = form_data.get('feedback_satisfactory', False)

        # Log the report generation
        filter_details = (
            f"Model: {model_name}, Fields: {', '.join(selected_fields)}, "
            f"Date Field: {date_field or 'None'}, Start Date: {start_date or 'None'}, End Date: {end_date or 'None'}, "
            f"Status Field: {status_field or 'None'}, Status Value: {status_value or 'None'}, "
            f"Department: {department.name if department else 'None'}, "
            f"Is Urgent: {is_urgent}, Feedback Satisfactory: {feedback_satisfactory}"
        )
        AuditLog.objects.create(
            action_type='other',
            action='Generated Custom Report',
            performed_by=employee,
            details=filter_details
        )

        model = apps.get_model('employee', model_name)
        queryset = model.objects.all()

        # Optimize queries
        if model_name == 'Employee':
            queryset = queryset.select_related('department')
        elif model_name == 'Attendance':
            queryset = queryset.select_related('eId__department')
        elif model_name == 'LeaveRequest':
            queryset = queryset.select_related('requester__department', 'destination_employee__department')
        elif model_name == 'PerformanceReview':
            queryset = queryset.select_related('employee__department', 'template')
        elif model_name == 'WorkAssignments':
            queryset = queryset.select_related('taskerId__department', 'assignerId__department')
        elif model_name == 'RoleChangeLog':
            queryset = queryset.select_related('employee__department', 'changed_by__department')
        elif model_name == 'Notice':
            queryset = queryset.select_related('posted_by__department').prefetch_related('departments')
        elif model_name in ['EmergencyContact', 'Notification', 'IssueReport', 'Requests', 'WorkAssignmentLog', 'PendingRoleChange']:
            queryset = queryset.select_related('employee__department')

        # Validate and apply date filter
        if date_field:
            field = model._meta.get_field(date_field)
            if not isinstance(field, (models.DateField, models.DateTimeField)):
                messages.error(request, f"{date_field} is not a valid date field for {model_name}.")
            else:
                if start_date:
                    queryset = queryset.filter(**{f"{date_field}__gte": start_date})
                if end_date:
                    queryset = queryset.filter(**{f"{date_field}__lte": end_date})

        # Validate and apply status filter
        if status_field and status_value:
            try:
                field = model._meta.get_field(status_field)
                if not isinstance(field, models.CharField):
                    messages.error(request, f"{status_field} is not a valid status field for {model_name}.")
                else:
                    queryset = queryset.filter(**{status_field: status_value})
            except models.FieldDoesNotExist:
                messages.error(request, f"{status_field} does not exist in {model_name}.")

        # Department filtering
        department_filter_map = {
            'Employee': {'field': 'department'},
            'Attendance': {'field': 'eId__department'},
            'LeaveRequest': {'field': 'requester__department'},
            'PerformanceReview': {'field': 'employee__department'},
            'WorkAssignments': {'field': 'taskerId__department'},
            'RoleChangeLog': {'field': 'employee__department'},
            'Notice': {'field': 'departments'},
            'EmergencyContact': {'field': 'employee__department'},
            'Notification': {'field': 'recipient__department'},
            'IssueReport': {'field': 'reporter__department'},
            'Requests': {'field': 'requester__department'},
            'WorkAssignmentLog': {'field': 'work_assignment__taskerId__department'},
            'PendingRoleChange': {'field': 'employee__department'},
        }
        if department and model_name in department_filter_map:
            if model_name == 'Notice':
                queryset = queryset.filter(departments=department)
            else:
                queryset = queryset.filter(**{department_filter_map[model_name]['field']: department})

        # Model-specific filters
        if is_urgent and model_name == 'Notice':
            queryset = queryset.filter(is_urgent=True)
        if feedback_satisfactory and model_name == 'WorkAssignments':
            queryset = queryset.filter(feedback_satisfactory=True)

        # Security for sensitive data
        if model_name == 'Document':
            if employee.role not in ['hr', 'admin']:
                queryset = queryset.filter(is_sensitive=False)
            AuditLog.objects.create(
                action_type='other',
                action='Accessed Document Report',
                performed_by=employee,
                details=f"Attempted access to {len(queryset)} documents with is_sensitive filter"
            )

        # Fetch results
        try:
            results = queryset.values(*selected_fields)
        except Exception as e:
            messages.error(request, f"Error fetching results: {str(e)}")
            results = []

        # Apply aggregation
        aggregation_result = None
        if aggregation and aggregation_field:
            try:
                field = model._meta.get_field(aggregation_field)
                if aggregation in ['avg', 'sum'] and not isinstance(field, (models.IntegerField, models.FloatField)):
                    messages.error(request, f"{aggregation_field} is not a numeric field for {aggregation}.")
                elif aggregation == 'count':
                    aggregation_result = {f"{aggregation_field} Count": queryset.count()}
                elif aggregation == 'avg':
                    agg = queryset.aggregate(avg=Avg(aggregation_field))['avg']
                    aggregation_result = {f"{aggregation_field} Average": agg if agg is not None else 0}
                elif aggregation == 'sum':
                    agg = queryset.aggregate(sum=Sum(aggregation_field))['sum']
                    aggregation_result = {f"{aggregation_field} Sum": agg if agg is not None else 0}
                elif aggregation == 'min':
                    agg = queryset.aggregate(min=Min(aggregation_field))['min']
                    aggregation_result = {f"{aggregation_field} Minimum": agg if agg is not None else 0}
                elif aggregation == 'max':
                    agg = queryset.aggregate(max=Max(aggregation_field))['max']
                    aggregation_result = {f"{aggregation_field} Maximum": agg if agg is not None else 0}
            except Exception as e:
                messages.error(request, f"Error calculating aggregation: {str(e)}")
                aggregation_result = {}

        header_field_pairs = []
        for field in selected_fields:
            try:
                verbose_name = model._meta.get_field(field).verbose_name or field.replace('_', ' ').title()
            except:
                verbose_name = field.replace('_', ' ').title()
            header_field_pairs.append((verbose_name, field))

        formatted_results = []
        for row in results:
            formatted_row = {}
            for field in selected_fields:
                value = row[field]
                if value is None:
                    formatted_row[field] = '—'
                elif isinstance(value, models.Model):
                    formatted_row[field] = str(value)
                elif isinstance(value, (datetime.date, datetime.datetime)):
                    formatted_row[field] = value.strftime('%Y-%m-%d')
                else:
                    formatted_row[field] = str(value)
            formatted_results.append(formatted_row)

        return results, header_field_pairs, aggregation_result, formatted_results

    # Handle POST request (report generation)
    if request.method == 'POST' and form.is_valid():
        # Convert date objects to ISO strings and Department to dept_id for session storage
        department = form.cleaned_data['department']
        form_data = {
            'model': form.cleaned_data['model'],
            'fields': form.cleaned_data['fields'],
            'date_field': form.cleaned_data['date_field'],
            'start_date': form.cleaned_data['start_date'].isoformat() if form.cleaned_data['start_date'] else None,
            'end_date': form.cleaned_data['end_date'].isoformat() if form.cleaned_data['end_date'] else None,
            'status_field': form.cleaned_data['status_field'],
            'status_value': form.cleaned_data['status_value'],
            'aggregation': form.cleaned_data['aggregation'],
            'aggregation_field': form.cleaned_data['aggregation_field'],
            'department': department.dept_id if department else None,  # Store dept_id instead of Department object
            'is_urgent': form.cleaned_data['is_urgent'],
            'feedback_satisfactory': form.cleaned_data['feedback_satisfactory'],
        }
        request.session['report_params'] = form_data

        results, header_field_pairs, aggregation_result, formatted_results = generate_report(form_data, current_employee)

        # Paginate results
        paginator = Paginator(formatted_results, 10)
        page_number = request.GET.get('page', 1)
        try:
            paginated_results = paginator.page(page_number)
        except PageNotAnInteger:
            paginated_results = paginator.page(1)
        except EmptyPage:
            paginated_results = paginator.page(paginator.num_pages)

    # Handle GET request with export
    if 'export' in request.GET or 'export_pdf' in request.GET:
        form_data = request.session.get('report_params')
        if not form_data:
            messages.error(request, "No report data available to export. Please generate a report first.")
            return redirect('custom_report_builder')

        results, header_field_pairs, aggregation_result, _ = generate_report(form_data, current_employee)

        if not results:
            messages.error(request, "No data available to export.")
            return redirect('custom_report_builder')

        model_name = form_data['model']
        department_id = form_data['department']
        department = Department.objects.get(dept_id=department_id) if department_id else None
        filter_details = (
            f"Model: {model_name}, Fields: {', '.join(form_data['fields'])}, "
            f"Date Field: {form_data['date_field'] or 'None'}, Start Date: {form_data['start_date'] or 'None'}, End Date: {form_data['end_date'] or 'None'}, "
            f"Status Field: {form_data['status_field'] or 'None'}, Status Value: {form_data['status_value'] or 'None'}, "
            f"Department: {department.name if department else 'None'}, "
            f"Is Urgent: {form_data['is_urgent']}, Feedback Satisfactory: {form_data['feedback_satisfactory']}"
        )

        if 'export_pdf' in request.GET:
            AuditLog.objects.create(
                action_type='other',
                action='Exported Custom Report as PDF',
                performed_by=current_employee,
                details=filter_details
            )
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=(letter[1], letter[0]),
                leftMargin=0.5*inch,
                rightMargin=0.5*inch,
                topMargin=0.5*inch,
                bottomMargin=0.5*inch
            )
            elements = []
            styles = getSampleStyleSheet()
            cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=9, wordWrap='CJK')
            elements.append(Paragraph(f"Custom Report: {model_name}", styles['Title']))
            elements.append(Spacer(1, 12))

            data = [[pair[0] for pair in header_field_pairs]]
            for row in results:
                row_data = []
                for _, field in header_field_pairs:
                    value = row[field]
                    if value is None:
                        row_data.append('—')
                    elif isinstance(value, (datetime.date, datetime.datetime)):
                        row_data.append(value.strftime('%Y-%m-%d'))
                    else:
                        row_data.append(Paragraph(str(value), cell_style))
                data.append(row_data)

            num_columns = len(header_field_pairs)
            total_width = 10 * inch
            col_width = total_width / num_columns
            col_widths = [col_width] * num_columns

            table = Table(data, colWidths=col_widths, rowHeights=[0.3*inch]*len(data))
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 12))

            if aggregation_result:
                elements.append(Paragraph("Aggregation Result", styles['Heading2']))
                for key, value in aggregation_result.items():
                    if isinstance(value, (int, float)):
                        formatted_value = f"{value:.2f}" if isinstance(value, float) else str(value)
                    else:
                        formatted_value = str(value)
                    elements.append(Paragraph(f"{key}: {formatted_value}", styles['Normal']))
                elements.append(Spacer(1, 12))

            doc.build(elements)
            buffer.seek(0)
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{model_name}_custom_report.pdf"'
            return response

        if 'export' in request.GET:
            AuditLog.objects.create(
                action_type='other',
                action='Exported Custom Report as CSV',
                performed_by=current_employee,
                details=filter_details
            )
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{model_name}_custom_report.csv"'
            writer = csv.writer(response)
            writer.writerow([pair[0] for pair in header_field_pairs])
            for row in results:
                row_data = []
                for _, field in header_field_pairs:
                    value = row[field]
                    if isinstance(value, (datetime.date, datetime.datetime)):
                        row_data.append(value.strftime('%Y-%m-%d'))
                    else:
                        row_data.append(value)
                writer.writerow(row_data)
            if aggregation_result:
                writer.writerow([])
                writer.writerow(['Aggregation'])
                for key, value in aggregation_result.items():
                    writer.writerow([key, value])
            return response

    if form.is_valid() and results is not None and not results:
        messages.info(request, "No data found for the selected filters. Try adjusting your criteria.")

    return render(request, 'employee/custom_report_builder.html', {
        'form': form,
        'results': paginated_results,
        'headers': header_field_pairs,
        'aggregation_result': aggregation_result,
    })

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
import csv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from .decorators import role_required
from .models import IssueReport, Employee, Notification, IssueComment, AuditLog
from .forms import IssueReportForm

@login_required
@role_required('employee', 'manager')
def report_issue(request):
    if request.method == 'POST':
        form = IssueReportForm(request.POST, request.FILES)
        if form.is_valid():
            issue = form.save(commit=False)
            issue.reporter = Employee.objects.get(eID=request.user.username)
            employee = issue.reporter

            if employee.role == 'manager':
                recipient = Employee.objects.filter(role='hr').first()
            else:  # employee role
                if issue.category == 'SAFETY':
                    recipient = Employee.objects.filter(role='hr').first()
                else:
                    recipient = Employee.objects.filter(department=employee.department, role='manager').first() or \
                               Employee.objects.filter(role='hr').first()

            if not recipient:
                messages.error(request, "No suitable recipient found for this report.")
                return redirect('report_issue')

            issue.recipient = recipient
            issue.save()

            Notification.objects.create(
                recipient=recipient,
                message=f"New issue reported by {issue.reporter.firstName} {issue.reporter.lastName}: {issue.title}. <a href='/ems/issue-detail/{issue.id}/' class='text-blue-600 hover:underline'>View</a>",
                request_type='Issue Report',
                request_id=str(issue.id)
            )

            AuditLog.objects.create(
                performed_by=issue.reporter,
                action_type='create',
                action='Issue Report Submitted',
                details=f"Issue '{issue.title}' submitted by {issue.reporter.firstName} {issue.reporter.lastName} to {recipient.firstName} {recipient.lastName}"
            )

            messages.success(request, "Issue reported successfully.")
            return redirect('my_issue_reports')
    else:
        form = IssueReportForm()
    return render(request, 'employee/report_issue.html', {'form': form})

@login_required
def my_issue_reports(request):
    employee = Employee.objects.get(eID=request.user.username)
    reports = IssueReport.objects.filter(reporter=employee).order_by('-created_at')
    paginator = Paginator(reports, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'employee/my_issue_reports.html', {'page_obj': page_obj})

@login_required
def my_issue_detail(request, id):
    issue = get_object_or_404(IssueReport, id=id)
    employee = Employee.objects.get(eID=request.user.username)

    if issue.reporter != employee:
        messages.error(request, "Access denied. Insufficient Permission")
        return redirect('my_issue_reports')

    comments = issue.comments.all()
    return render(request, 'employee/my_issue_detail.html', {'issue': issue, 'comments': comments})

@login_required
@role_required('manager', 'hr')
def manage_issue_reports(request):
    employee = Employee.objects.get(eID=request.user.username)
    reports = IssueReport.objects.filter(recipient=employee).order_by('-created_at')

    paginator = Paginator(reports, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'employee/manage_issue_reports.html', {'page_obj': page_obj})

@login_required
@role_required('manager', 'hr', 'admin')
def issue_detail(request, id):
    issue = get_object_or_404(IssueReport, id=id)
    employee = Employee.objects.get(eID=request.user.username)

    if employee.role != 'admin' and issue.recipient != employee:
        messages.error(request, "You do not have permission to view this report.")
        return redirect('manage_issue_reports')

    if request.method == 'POST':
        if 'status' in request.POST:
            status = request.POST.get('status')
            if status in [choice[0] for choice in IssueReport.STATUS_CHOICES]:
                old_status = issue.status
                issue.status = status
                issue.save()
                detail_url = f"/ems/my-issue-detail/{issue.id}/" if issue.reporter.role == 'employee' else f"/ems/issue-detail/{issue.id}/"
                Notification.objects.create(
                    recipient=issue.reporter,
                    message=f"Your issue '{issue.title}' has been updated to {issue.get_status_display()} by {employee.firstName} {employee.lastName}. <a href='{detail_url}' class='text-blue-600 hover:underline'>View</a>",
                    request_type='Issue Update',
                    request_id=str(issue.id)
                )
                AuditLog.objects.create(
                    performed_by=employee,
                    action_type='update',
                    action='Issue Status Updated',
                    details=f"Issue '{issue.title}' status updated from {old_status} to {issue.status} by {employee.firstName} {employee.lastName}"
                )
                messages.success(request, "Issue status updated successfully.")
            else:
                messages.error(request, "Invalid status selected.")
        elif 'comment' in request.POST:
            comment_text = request.POST.get('comment')
            if comment_text:
                comment = IssueComment.objects.create(
                    issue=issue,
                    commenter=employee,
                    comment=comment_text
                )
                detail_url = f"/ems/my-issue-detail/{issue.id}/" if issue.reporter.role == 'employee' else f"/ems/issue-detail/{issue.id}/"
                Notification.objects.create(
                    recipient=issue.reporter,
                    message=f"New comment on your issue '{issue.title}' by {employee.firstName} {employee.lastName}: {comment_text[:50]}... <a href='{detail_url}' class='text-blue-600 hover:underline'>View</a>",
                    request_type='Issue Comment',
                    request_id=str(issue.id)
                )
                AuditLog.objects.create(
                    performed_by=employee,
                    action_type='create',
                    action='Issue Comment Added',
                    details=f"Comment added to issue '{issue.title}' by {employee.firstName} {employee.lastName}: {comment_text[:50]}..."
                )
                messages.success(request, "Comment added successfully.")
            else:
                messages.error(request, "Comment cannot be empty.")

        return redirect('issue_detail', id=id)

    comments = issue.comments.all()
    return render(request, 'employee/issue_detail.html', {'issue': issue, 'comments': comments})