# employee/urls.py
from django.urls import path, re_path
from . import views

urlpatterns = [
    path('dashboard', views.dashboard, name="dashboard"),
    path('attendance', views.attendance, name="attendance"),
    path('notice', views.notice, name="notice"),
    path('hr-dashboard/', views.hr_dashboard, name="hr_dashboard"),
    re_path(r'noticedetail/(?P<id>\d+)/', views.noticedetail, name="noticedetail"),
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
    path('review-role-changes/', views.review_role_changes, name='review_role_changes'),
    path('role-change-history/', views.role_change_history, name='role_change_history'),
    path('leave-request-details/<str:rid>/', views.leave_request_details, name='leave_request_details'),

    path('notice', views.notice, name='notice'),
    re_path(r'noticedetail/(?P<id>\w+)/', views.noticedetail, name='noticedetail'),
    path('create-notice/', views.create_notice, name='create_notice'),
    re_path(r'edit-notice/(?P<id>\w+)/', views.edit_notice, name='edit_notice'),
    path('delete-notice/<str:id>/', views.delete_notice, name='delete_notice'),
    # employee/urls.py
    path('manage-notices/', views.manage_notices, name='manage_notices'),
]