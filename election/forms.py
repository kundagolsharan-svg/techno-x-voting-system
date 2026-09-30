from django import forms
from .models import Student, Position
import json
import re
# election/forms.py

# SEMESTER_CHOICES = [('3', 'Semester 3'),
#                     ('5', 'Semester 5'),
#                     ('7', 'Semester 7'),
#                     ('general', 'General Voter'),
#                     ]


class NominationForm(forms.Form):
    name     = forms.CharField(max_length=100)
    usn      = forms.CharField(max_length=20)
    semester = forms.ChoiceField(
        choices=Student.SEMESTER_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"})
    )
    gender   = forms.ChoiceField(
        choices=[("Male", "Male"), ("Female", "Female")],
        widget=forms.Select(attrs={"class": "form-control"})
    )
    division = forms.ChoiceField(
        choices=[("A", "A"), ("B", "B")],
        widget=forms.Select(attrs={"class": "form-control"})
    )
    position = forms.ModelChoiceField(
        queryset=Position.objects.none(),  # you populate it via JS
        widget=forms.Select(attrs={"class": "form-control"})
    )
    photo    = forms.ImageField(required=False)

    # def clean_semester(self):
    #     sem = self.cleaned_data["semester"]
    #     try:
    #         return int(sem)
    #     except ValueError:
    #         raise forms.ValidationError("Select a valid semester.")


    # def clean_usn(self):
    #     usn = self.cleaned_data.get('usn', '').upper()
    #     pattern = r'^\d{2}[A-Z]{2}\d{2}[A-Z]{2}\d{3}$'
    #     if not re.match(pattern, usn):
    #         raise forms.ValidationError("Invalid USN format. Example: 2XX21CS001")
    #     return usn
    

    def clean(self):
        cleaned = super().clean()
        sem = str(cleaned.get('semester', ''))
        gen = cleaned.get('gender')
        pos = cleaned.get('position')

        if pos:
            raw = pos.semester_eligibility
            elig = raw if isinstance(raw, list) else json.loads(raw)
            elig = [str(s) for s in elig]

            is_eligible = (sem in elig) or (sem == '7' and 'general' in elig) or (sem == 'general' and '7' in elig)
            if not is_eligible:
                raise forms.ValidationError(
                    f"{pos.title} is not open to semester {sem}."
                )

        if pos and pos.title == 'Ladies Representative' and gen != 'Female':
            raise forms.ValidationError(
                "Only female students may nominate for Ladies Representative."
            )

        return cleaned


class NomineeEditForm(forms.Form):
    student_name = forms.CharField(
        max_length=100,
        label="Student Name",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    student_usn = forms.CharField(
        max_length=20,
        label="USN",
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "readonly": "readonly"})
    )
    student_semester = forms.ChoiceField(
        choices=Student.SEMESTER_CHOICES,
        label="Semester",
        widget=forms.Select(attrs={"class": "form-control"})
    )
    student_division = forms.ChoiceField(
        choices=[("A", "A"), ("B", "B")],
        label="Division",
        widget=forms.Select(attrs={"class": "form-control"})
    )
    position = forms.ModelChoiceField(
        queryset=Position.objects.all(),
        label="Position",
        widget=forms.Select(attrs={"class": "form-control"})
    )
    photo = forms.ImageField(
        required=False,
        label="Update Photo (optional)",
        widget=forms.FileInput(attrs={"class": "form-control"})
    )

