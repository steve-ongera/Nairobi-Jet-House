from django import forms
from .models import GroupInquiry

class GroupInquiryForm(forms.ModelForm):
    class Meta:
        model = GroupInquiry
        fields = ['group_name', 'contact_email', 'passenger_count', 'travel_date']
        widgets = {
            'group_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Group Name'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contact Email'
            }),
            'passenger_count': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Passenger Count',
                'min': 10
            }),
            'travel_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'Travel Date(s)'
            }),
        }