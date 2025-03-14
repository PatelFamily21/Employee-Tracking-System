from tkinter import Widget
from django import forms
from .models import WorkAssignments, Requests

class workform(forms.ModelForm):
    class Meta:
        model=WorkAssignments
        widgets={
            "assignDate" : forms.DateInput(attrs={'type':'datetime-local'}),
            "dueDate" : forms.DateInput(attrs={'type':'datetime-local'}),
            }
        labels={"assignerId" : "Select Your Id"}
        
        fields=[
            "assignerId",
            "work",
            "assignDate",
            "dueDate",
            "taskerId",

        ]
        
class makeRequestForm(forms.ModelForm):
    class Meta:
        model=Requests
        widgets={
            "requestDate" : forms.DateInput(attrs={'type':'datetime-local'}),
            }
        labels={"requesterId" : "Select Your Id"}
        
        fields=[
            "requesterId",
            "requestMessage",
            "requestDate",
            "destinationEmployeeId",
        ]