from django import forms
from .models import GroupInquiry

class GroupInquiryForm(forms.ModelForm):
    class Meta:
        model = GroupInquiry
        fields = ['group_name', 'contact_email', 'passenger_count', 'travel_date']
        widgets = {
            'travel_date': forms.DateInput(attrs={'type': 'date'}),
        }
