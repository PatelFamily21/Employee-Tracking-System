from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from employee.models import Employee

class EmployeeAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        try:
            # First, get the User object
            user = UserModel.objects.get(username=username)
            # Check if the User is active (Django's default check)
            if not user.is_active:
                return None
            # Check if the password is correct
            if user.check_password(password):
                # Now check the Employee's is_active status
                try:
                    employee = Employee.objects.get(eID=username)
                    if not employee.is_active:
                        return None  # Deny login if the Employee is deactivated
                    return user
                except Employee.DoesNotExist:
                    return None  # Employee does not exist, deny login
            return None  # Password incorrect
        except UserModel.DoesNotExist:
            return None  # User does not exist

    def user_can_authenticate(self, user):
        """
        Check if the user can authenticate based on both User and Employee is_active status.
        """
        if not user.is_active:
            return False
        try:
            employee = Employee.objects.get(eID=user.username)
            return employee.is_active
        except Employee.DoesNotExist:
            return False