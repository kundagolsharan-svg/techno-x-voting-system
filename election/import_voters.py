import csv
from election.models import Student

def import_voters_from_csv(file_path):
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            Student.objects.update_or_create(
                usn=row['usn'].strip().upper(),
                defaults={
                    'name': row['name'].strip(),
                    'semester': int(row['semester']),
                    'division': row['division'].strip().upper(),
                    'gender': 'Not Specified'  # Optional fallback
                }
            )
