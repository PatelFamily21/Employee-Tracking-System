# employee/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Requests, Attendance, Notification

@receiver(post_save, sender=Requests)
def update_attendance_and_notify(sender, instance, **kwargs):
    if instance.request_type == 'leave':
        if instance.status == 'approved':
            # Update attendance records
            current_date = instance.start_date
            while current_date <= instance.end_date:
                Attendance.objects.get_or_create(
                    eId=instance.requesterId,
                    date=current_date,
                    defaults={'status': 'leave'}
                )
                current_date += timezone.timedelta(days=1)
            # Notify employee
            Notification.objects.create(
                recipient=instance.requesterId,
                message=f"Your leave request ({instance.Id}) from {instance.start_date} to {instance.end_date} has been approved."
            )
        elif instance.status == 'rejected':
            # Remove any 'leave' records
            Attendance.objects.filter(
                eId=instance.requesterId,
                date__range=[instance.start_date, instance.end_date],
                status='leave'
            ).delete()
            # Notify employee
            Notification.objects.create(
                recipient=instance.requesterId,
                message=f"Your leave request ({instance.Id}) from {instance.start_date} to {instance.end_date} has been rejected."
            )