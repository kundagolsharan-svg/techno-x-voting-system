from django.db import models

# Create your models here.
class Student(models.Model):
    SEMESTER_CHOICES = [
        ('3',       '3rd Semester'),
        ('5',       '5th Semester'),
        ('7',       '7th Semester'),
        ('general', 'General'),
    ]

    name     = models.CharField(max_length=100)
    usn      = models.CharField(max_length=20, unique=True)
    semester = models.CharField(
        max_length=10,
        choices=SEMESTER_CHOICES,
        default='3'
    )
    gender   = models.CharField(max_length=10)
    division = models.CharField(
        max_length=1,
        choices=[('A','A'), ('B','B')],
        default='A'
    )

    def __str__(self):
        return f"{self.name} ({self.usn})"

class Position(models.Model):
    title = models.CharField(max_length=100)
    semester_eligibility = models.JSONField()  # e.g., [3, 5, 7]
    gender_specific = models.BooleanField(default=False)
    max_winners = models.IntegerField(default=1)

    def __str__(self):
        return self.title

class Nominee(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    position = models.ForeignKey(Position, on_delete=models.CASCADE)
    photo = models.ImageField(upload_to='nominee_photos/', null=True, blank=True)

    def __str__(self):
        return f"{self.student.name} for {self.position.title}"

class Vote(models.Model):
    voter_usn = models.CharField(max_length=20)
    position = models.ForeignKey(Position, on_delete=models.CASCADE)
    nominee = models.ForeignKey(Nominee, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.voter_usn} voted for {self.nominee.student.name}"
    
    class Meta:
        unique_together = ('voter_usn', 'position')
