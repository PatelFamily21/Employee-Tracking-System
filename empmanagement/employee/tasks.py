# employee/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import WorkAssignments, WorkAssignmentLog, Notification, Employee

@shared_task
def check_overdue_and_inactive_tasks():
    # Check overdue tasks
    overdue_tasks = WorkAssignments.objects.filter(
        dueDate__lt=timezone.now(),
        status__in=['pending', 'in_progress']
    )
    for task in overdue_tasks:
        Notification.objects.create(
            recipient=task.assignerId,
            message=f"Task '{task.work[:50]}' assigned to {task.taskerId} is overdue! Due date: {task.dueDate}"
        )

    # Check for tasks with no status updates in the last 3 days
    three_days_ago = timezone.now() - timedelta(days=3)
    inactive_tasks = WorkAssignments.objects.filter(
        status__in=['pending', 'in_progress']
    )
    for task in inactive_tasks:
        last_update = WorkAssignmentLog.objects.filter(
            work_assignment=task
        ).order_by('-updated_at').first()
        if not last_update or last_update.updated_at < three_days_ago:
            Notification.objects.create(
                recipient=task.assignerId,
                message=f"Task '{task.work[:50]}' assigned to {task.taskerId} has had no status updates since {last_update.updated_at if last_update else task.assignDate}"
            )