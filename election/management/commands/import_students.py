"""
Management command: import_students
Usage:
    python manage.py import_students path/to/students.csv

CSV format (with header row):
    name,usn,semester,gender,division

Example rows:
    Rahul Sharma,2TG24CS001,3,Male,A
    Priya Naik,2TG24CS002,3,Female,B
"""

import csv
from django.core.management.base import BaseCommand
from election.models import Student


class Command(BaseCommand):
    help = 'Bulk import students from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing students if USN already exists',
        )

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        update = options['update']

        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0

        try:
            with open(csv_path, newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader, start=2):  # start=2 because row 1 is header
                    try:
                        name     = row.get('name', '').strip()
                        usn      = row.get('usn', '').strip().upper()
                        semester = str(row.get('semester', '')).strip()
                        gender   = row.get('gender', '').strip()
                        division = row.get('division', '').strip().upper()

                        if not name or not usn or not semester or not division:
                            self.stdout.write(
                                self.style.WARNING(f'  Row {i}: Skipped — missing required field(s). Row: {dict(row)}')
                            )
                            skipped_count += 1
                            continue

                        # Validate semester
                        valid_semesters = ['3', '5', '7', 'general']
                        if semester not in valid_semesters:
                            self.stdout.write(
                                self.style.WARNING(f'  Row {i}: Invalid semester "{semester}" for USN {usn}. Must be 3, 5, 7 or general.')
                            )
                            skipped_count += 1
                            continue

                        # Validate division
                        if division not in ['A', 'B']:
                            self.stdout.write(
                                self.style.WARNING(f'  Row {i}: Invalid division "{division}" for USN {usn}. Must be A or B.')
                            )
                            skipped_count += 1
                            continue

                        student, created = Student.objects.get_or_create(
                            usn=usn,
                            defaults={
                                'name': name,
                                'semester': semester,
                                'gender': gender,
                                'division': division,
                            }
                        )

                        if created:
                            created_count += 1
                        elif update:
                            student.name = name
                            student.semester = semester
                            student.gender = gender
                            student.division = division
                            student.save()
                            updated_count += 1
                        else:
                            skipped_count += 1

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  Row {i}: Error — {e}'))
                        error_count += 1

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {csv_path}'))
            return

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✅ Import complete!'))
        self.stdout.write(self.style.SUCCESS(f'   Created : {created_count}'))
        self.stdout.write(self.style.SUCCESS(f'   Updated : {updated_count}'))
        self.stdout.write(self.style.WARNING(f'   Skipped : {skipped_count}'))
        if error_count:
            self.stdout.write(self.style.ERROR(f'   Errors  : {error_count}'))
