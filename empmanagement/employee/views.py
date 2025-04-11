# employee/views.py
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from .forms import workform, makeRequestForm, EmployeeForm 
from .models import Employee, Attendance, Notice, WorkAssignments, Department, Requests, Notification, WorkAssignmentLog, NoticeView
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import datetime, time
from itertools import chain
import csv
from django.http import HttpResponse
from django.db.models.functions import TruncMonth
from .decorators import role_required
from datetime import timedelta
from datetime import datetime, time, timezone, timedelta, date
# employee/views.py
from django.shortcuts import redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Employee, Attendance, LeaveRequest, Notification  # Add LeaveRequest and Notification
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import datetime, time
import csv
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Employee, Requests, Notice, Department, LeaveRequest
from .decorators import role_required
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import AuditLog, PendingRoleChange
from datetime import datetime
import csv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
import os
from django.conf import settings
from .decorators import role_required

from django.shortcuts import render
from django.http import HttpResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import AuditLog, PendingRoleChange
from datetime import datetime
import csv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
import os
from django.conf import settings
from .decorators import role_required

from django.shortcuts import render
from django.http import HttpResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import AuditLog, PendingRoleChange
from datetime import datetime
import csv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
import os
from django.conf import settings
from .decorators import role_required


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



def attendance(request):
    employee = Employee.objects.get(eID=request.user.username)
    today = timezone.now().date()
    attendance_record = Attendance.objects.filter(eId=employee, date=today).first()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'check_in':
            if not attendance_record:
                Attendance.objects.create(
                    eId=employee,
                    date=today,
                    status='present',
                    check_in_time=timezone.now()
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
            else:
                messages.error(request, "You have already checked in today.")
        elif action == 'check_out':
            if attendance_record and attendance_record.check_in_time and not attendance_record.check_out_time:
                attendance_record.check_out_time = timezone.now()
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
            elif not attendance_record:
                messages.error(request, "You need to check in first.")
            else:
                messages.error(request, "You have already checked out today.")
        return redirect('attendance')

    context = {
        'employee': employee,
        'attendance_record': attendance_record,
        'today': today,
    }
    return render(request, 'employee/attendance.html', context)



from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import redirect
from django.contrib import messages

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
    

# Notice detail view (accessible to all authenticated employees)
# employee/views.py
from django.shortcuts import get_object_or_404
from django.http import Http404

@role_required('employee', 'manager', 'hr', 'admin')
def noticedetail(request, id):
    employee = Employee.objects.get(eID=request.user.username)
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
    if not NoticeView.objects.filter(notice=notice, employee=employee).exists():
        NoticeView.objects.create(notice=notice, employee=employee)

    context = {
        'noticedetail': notice,  # Keep the context variable name consistent with your template
    }
    return render(request, "employee/noticedetail.html", context)

# employee/views.py
# employee/views.py
from .forms import NoticeForm  # Ensure NoticeForm is imported

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

# employee/views.py
# employee/views.py
from .models import AuditLog

# employee/views.py
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from .decorators import role_required
from .models import Notice, AuditLog
from .context_processors import get_employee  # Import get_employee

# employee/views.py
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from .decorators import role_required
from .models import Notice, AuditLog
from .context_processors import get_employee  # Import get_employee

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


# employee/views.py
from django.shortcuts import redirect
from django.contrib import messages
from .forms import NoticeForm  # We'll create this form next

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



# Assign Work view (restricted to managers and admins)

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
# My Work view (accessible to all authenticated employees)
# employee/views.py


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

# Work Details view (accessible to all authenticated employees)
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


# Make Request view (accessible to all authenticated employees)
@role_required('employee', 'manager', 'hr', 'admin')
def makeRequest(request):
    employee = Employee.objects.get(eID=request.user.username)
    flag = ""

    if request.method == 'POST':
        form = makeRequestForm(request.POST)
        if form.is_valid():
            # Create the request
            request_obj = form.save(commit=False)
            request_obj.Id = f"REQ{timezone.now().strftime('%Y%m%d%H%M%S')}"
            request_obj.requester = employee
            request_obj.status = 'pending'

            # Determine the destination_employee based on the requester's role
            if employee.role == 'employee':
                # Non-manager employees: Direct to their department's manager
                destination_employee = Employee.objects.filter(
                    department=employee.department,
                    role='manager'
                ).first()
            elif employee.role == 'manager':
                # Managers: Direct to HR
                destination_employee = Employee.objects.filter(role='hr').first()
            elif employee.role == 'hr':
                # HR: Direct to an Admin
                destination_employee = Employee.objects.filter(role='admin').first()
            else:  # employee.role == 'admin'
                # Admins: Direct to another Admin (or self if no other Admin exists)
                destination_employee = Employee.objects.filter(role='admin').exclude(eID=employee.eID).first()
                if not destination_employee:
                    destination_employee = employee  # Self-directed if no other Admin

            if not destination_employee:
                messages.error(request, "No suitable recipient found for this request.")
                return redirect('makeRequest')

            request_obj.destination_employee = destination_employee
            request_obj.save()

            # Send a notification to the destination employee
            view_url = '/ems/viewRequest/' if destination_employee.role in ['manager', 'hr', 'admin'] else '/ems/requestdetails/{request_obj.Id}/'
            Notification.objects.create(
                recipient=destination_employee,
                message=f"New request from {employee.firstName} {employee.lastName}: {request_obj.request_message[:50]}... <a href='{view_url}' class='text-blue-600 hover:underline'>View</a>",
                request_type='general_request',
                request_id=request_obj.Id  # Link to the Requests
            )

            flag = "Request Submitted"
            messages.success(request, "Request submitted successfully!")
            return redirect('makeRequest')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = makeRequestForm(initial={'request_type': 'other'})

    # Display the user's existing requests
    user_requests = Requests.objects.filter(requester=employee).order_by('-request_date')
    
    return render(request, "employee/request.html", {
        'requestForm': form,
        'flag': flag,
        'user_requests': user_requests,
    })


# View Requests view (accessible to all authenticated employees)
from django.core.paginator import Paginator

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
                req.save()
            except Requests.DoesNotExist:
                messages.error(request, "Request not found.")
        return redirect('viewRequest')

    context = {
        'page_obj': page_obj,
    }
    return render(request, 'employee/viewRequest.html', context)

# Request Details view (accessible to all authenticated employees)
@role_required('employee', 'manager', 'hr', 'admin')
def requestdetails(request, rid):
    requestdetail = get_object_or_404(Requests, Id=rid)
    employee = Employee.objects.get(eID=request.user.username)

    # Restrict access to requester or destination employee
    if requestdetail.requester != employee and requestdetail.destination_employee != employee:
        messages.error(request, "You are not authorized to view this request.")
        return redirect('dashboard')

    if request.method == 'POST' and requestdetail.destination_employee == employee:
        action = request.POST.get('action')
        if action == 'approve':
            requestdetail.status = 'approved'
            messages.success(request, "Request approved successfully!")
            Notification.objects.create(
                recipient=requestdetail.requester,
                message=f"Your request (ID: {requestdetail.Id}) has been approved by {employee.firstName} {employee.lastName}. <a href='/ems/requestdetails/{requestdetail.Id}/' class='text-blue-600 hover:underline'>View</a>",
                request_type='general_request_status',
                request_id=requestdetail.Id  # Link to the Requests
            )
        elif action == 'reject':
            requestdetail.status = 'rejected'
            messages.success(request, "Request rejected successfully!")
            Notification.objects.create(
                recipient=requestdetail.requester,
                message=f"Your request (ID: {requestdetail.Id}) has been rejected by {employee.firstName} {employee.lastName}. <a href='/ems/requestdetails/{requestdetail.Id}/' class='text-blue-600 hover:underline'>View</a>",
                request_type='general_request_status',
                request_id=requestdetail.Id  # Link to the Requests
            )
        requestdetail.save()
        return redirect('viewRequest')

    return render(request, "employee/requestdetails.html", {
        "requestdetail": requestdetail,
        "can_process": requestdetail.destination_employee == employee and requestdetail.status == 'pending',
    })


# Assigned Work List view (restricted to managers and admins)
@role_required('hr','manager', 'admin')
def assignedWorkList(request):
    assigner = Employee.objects.get(eID=request.user.username)
    works = WorkAssignments.objects.filter(assignerId=assigner).order_by('-assignDate')
    return render(request, "employee/assignedworklist.html", {"works": works})

# Delete Work view (restricted to managers and admins)
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

# Update Work view (restricted to managers and admins)
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


# Profile view (accessible to all authenticated employees)
@role_required('employee', 'manager', 'hr', 'admin')
def profile(request):
    try:
        employee = Employee.objects.get(eID=request.user.username)
    except Employee.DoesNotExist:
        messages.error(request, "Employee profile not found.")
        return redirect('dashboard')

    if request.method == "POST":
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
        return redirect('profile')

    return render(request, 'employee/profile.html', {'employee': employee})


@role_required('hr', 'admin')
def hr_dashboard(request):
    # Total number of employees
    total_employees = Employee.objects.count()

    # Recent notices (last 5, ordered by publish date)
    recent_notices = Notice.objects.order_by('-publishDate')[:5]

    # Attendance summary: Count days by status (present, absent, leave) per month
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

    # Employee attendance history
    attendance_records = Attendance.objects.select_related('eId').order_by('-date')
    
    # Date filter for attendance history
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date and end_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            attendance_records = attendance_records.filter(date__range=[start_date, end_date])
        except ValueError:
            messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")

    # Employee filter (optional)
    employee_id = request.GET.get('employee_id')
    if employee_id:
        attendance_records = attendance_records.filter(eId__eID=employee_id)

    # Pagination
    paginator = Paginator(attendance_records, 10)  # 10 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # List of employees for filter dropdown
    employees = Employee.objects.all().order_by('firstName', 'lastName')

    context = {
        'total_employees': total_employees,
        'recent_notices': recent_notices,
        'attendance_summary': formatted_summary,
        'page_obj': page_obj,
        'employees': employees,
        'selected_employee_id': employee_id,
    }
    return render(request, 'employee/hr_dashboard.html', context)


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

# employee/views.py
from django.shortcuts import redirect, render
from django.contrib import messages
from django.core.paginator import Paginator
from .models import LeaveRequest  # Ensure LeaveRequest is imported
from .decorators import role_required

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
            messages.error(request, "Request not found.")
        return redirect('employee_requests')

    context = {
        'page_obj': page_obj,
    }
    return render(request, 'employee/employee_requests.html', context)

# employee/views.py
from django.db.models import Count, Q
from django.utils import timezone

@role_required('manager', 'admin')
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

# employee/views.py
from django.shortcuts import redirect, render
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Employee, RoleChangeLog, Notification  # Add RoleChangeLog and Notification
from .decorators import role_required

# employee/views.py
from django.shortcuts import redirect, render
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import models
from .models import Employee, RoleChangeLog, Notification, PendingRoleChange, role_choices  # Add PendingRoleChange
from .decorators import role_required

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

from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Department
from .decorators import role_required

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

@role_required('admin')
def audit_logs(request):
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
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
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
        employee = get_employee(request)
        if action == 'add':
            form = EmployeeForm(request.POST)
            if form.is_valid():
                new_employee = form.save()
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
                messages.success(request, "Employee added successfully.")
                return redirect('employee_management')
        elif action == 'delete':
            eID = request.POST.get('eID')
            Employee.objects.filter(eID=eID).delete()
            if employee:
                try:
                    AuditLog.objects.create(
                        action_type='delete',
                        action="Employee Deleted",
                        performed_by=employee
                    )
                except Exception as e:
                    messages.warning(request, f"Employee deleted, but failed to log action: {str(e)}")
            messages.success(request, "Employee deleted successfully.")
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

# employee/views.py
# employee/views.py
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
