# employee/urls.py
from django.urls import path, re_path
from . import views

urlpatterns = [
    path('dashboard', views.dashboard, name="dashboard"),
    path('attendance', views.attendance, name="attendance"),
    #path('notice', views.notice, name="notice"),
    path('hr-dashboard/', views.hr_dashboard, name="hr_dashboard"),
    #re_path(r'noticedetail/(?P<id>\d+)/', views.noticedetail, name="noticedetail"),
    path('assignwork', views.assignwork, name="assignwork"),
    path('mywork', views.mywork, name="mywork"),
    path('workdetails/<str:wid>/', views.workdetails, name='workdetails'),
    path('editAW', views.assignedWorkList, name="assignedworklist"),
    path('deletework/<str:wid>/', views.deleteWork, name="deletework"),
    path('updatework/<str:wid>/', views.updateWork, name='updatework'),
    path('makeRequest', views.makeRequest, name="makeRequest"),
    path('viewRequest/', views.viewRequest, name="viewRequest"),
    path('requestdetails/<str:rid>/', views.requestdetails, name="requestdetails"),
    path('profile', views.profile, name="profile"),
    path('manage-roles/', views.manage_roles, name="manage_roles"),
    path('employee-requests/', views.employee_requests, name='employee_requests'),
    path('notifications/', views.notifications, name='notifications'),
    path('productivity/', views.productivity_dashboard, name='productivity_dashboard'),
    path('approve_work/<str:work_id>/', views.approve_work, name='approve_work'),
    path('managerial-requests/', views.managerial_requests, name='managerial_requests'),
    path('review-role-changes/', views.review_role_changes, name="review_role_changes"),
    path('role-change-history/', views.role_change_history, name="role_change_history"),
    path('system-settings/', views.system_settings, name='system_settings'),
    path('audit-logs/', views.audit_logs, name='audit_logs'),
    path('employee-management/', views.employee_management, name='employee_management'),
    path('leave-request-details/<str:rid>/', views.leave_request_details, name='leave_request_details'),
    path('notice', views.notice, name="notice"),
    path('ems/noticedetail/<str:id>/', views.noticedetail, name='noticedetail'),
    path('create-notice/', views.create_notice, name='create_notice'),
    re_path(r'edit-notice/(?P<id>\w+)/', views.edit_notice, name='edit_notice'),
    path('delete-notice/<str:id>/', views.delete_notice, name='delete_notice'),
    path('manage-notices/', views.manage_notices, name='manage_notices'),
    path('leave-request/', views.leave_request, name='leave_request'),
    path('issue-compulsory-leave/', views.issue_compulsory_leave, name='issue_compulsory_leave'),
    path('employee_database/', views.employee_database, name='employee_database'),

    # --- CHANGE THIS LINE ---
    # path('employee/<str:eID>/', views.employee_detail, name='employee_detail'),
    path('employee/<path:eID>/', views.employee_detail, name='employee_detail'), # Use path converter
    # --- END CHANGE ---

    path('export_employee_data/', views.export_employee_data, name='export_employee_data'),

    # --- ALSO CHANGE THIS LINE ---
    # path('employee/<str:eID>/export/', views.export_employee_detail, name='export_employee_detail'),
    path('employee/<path:eID>/export/', views.export_employee_detail, name='export_employee_detail'), # Use path converter here too
    # --- END CHANGE ---
    path('manage-review-templates/', views.manage_review_templates, name='manage_review_templates'),
    path('create-review-template/', views.create_review_template, name='create_review_template'),
    path('schedule-performance-review/', views.schedule_performance_review, name='schedule_performance_review'),
    path('submit-performance-review/<int:review_id>/', views.submit_performance_review, name='submit_performance_review'),
    path('view-performance-reviews/', views.view_performance_reviews, name='view_performance_reviews'),
    path('performance-review/<int:review_id>/', views.performance_review_detail, name='performance_review_detail'),
    path('view-submitted-reviews/', views.view_submitted_reviews, name='view_submitted_reviews'),
    path('standard-hr-reports/', views.standard_hr_reports, name='standard_hr_reports'),
    path('custom-report-builder/', views.custom_report_builder, name='custom_report_builder'),
    path('templates/<int:template_id>/', views.view_template_details, name='view_template_details'),
    path('reviews/submitted/', views.view_submitted_reviews, name='view_submitted_reviews'),
]