from django.contrib import admin
from .models import Student, Nominee, Vote, Position

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('name', 'usn', 'semester', 'gender')
    search_fields = ('name', 'usn')
    list_filter = ('semester', 'gender')

@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('title', 'max_winners', 'gender_specific')
    list_filter = ('gender_specific',)

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = (
        'student_name',
        'student_usn',
        'position_title',
        'nominee_name'
    )
    list_filter = ('position',)  # Removed student__semester
    search_fields = ('student__name', 'student__usn')

    def student_name(self, obj):
        return obj.nominee.student.name

    def student_usn(self, obj):
        return obj.nominee.student.usn

    def position_title(self, obj):
        return obj.position.title

    def nominee_name(self, obj):
        return obj.nominee.student.name

@admin.register(Nominee)
class NomineeAdmin(admin.ModelAdmin):
    list_display = (
        'student_name',
        'student_usn',
        'student_semester',
        'student_gender',
        'position_title'
    )
    search_fields = ('student__name', 'student__usn')
    list_filter = ('student__semester', 'student__gender', 'position')

    def student_name(self, obj):
        return obj.student.name
    def student_usn(self, obj):
        return obj.student.usn
    def student_semester(self, obj):
        return obj.student.semester
    def student_gender(self, obj):
        return obj.student.gender
    def position_title(self, obj):
        return obj.position.title
