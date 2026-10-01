from django.shortcuts import render
# views.py


import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Student, Nominee, Position, Vote
from .forms import NominationForm, NomineeEditForm

# election/views.py

def landing_page(request):
    return render(request, 'election/landing.html')

def nominate(request):
    # 1. Build semester -> positions mapping for your JS-driven dropdown
    positions_by_sem = {}
    for pos in Position.objects.all():
        for sem in pos.semester_eligibility:  # e.g., [3, 5, 7]
            key = str(sem)
            positions_by_sem.setdefault(key, []).append({
                "id":    pos.id,
                "title": pos.title
            })
            if key == "general":
                positions_by_sem.setdefault("7", []).append({
                    "id":    pos.id,
                    "title": pos.title
                })
    positions_json = json.dumps(positions_by_sem)

    # 2. Handle form submission
    if request.method == "POST":
        form = NominationForm(request.POST, request.FILES)
        form.fields['position'].queryset = Position.objects.all()

        if form.is_valid():
            data = form.cleaned_data
            usn = data['usn'].strip().upper()
            print("  USN:", usn)

            try:
                student = Student.objects.get(usn=usn)
            except Student.DoesNotExist:
                messages.error(request, "USN not found in the voter list.")
            else:
                position = data['position']
                raw = position.semester_eligibility
                if isinstance(raw, str):
                    try:
                        elig = json.loads(raw)
                    except json.JSONDecodeError:
                        elig = [raw]
                else:
                    elig = raw
                elig = [str(s) for s in elig]


                if "general" in elig and student.semester != '7':
                    messages.error(request, "Only 7th semester students can be nominated for general positions.")
                    return render(request, 'election/nominate.html', {
                        'form': form,
                        'positions_json': positions_json,
                    })

                if Nominee.objects.filter(student=student, position=position).exists():
                    messages.error(request, "You have already nominated for this position.")
                else:
                    Nominee.objects.create(
                        student=student,
                        position=position,
                        photo=data.get('photo')
                    )
                    next_url = request.GET.get('next') or request.POST.get('next')
                    if next_url:
                        messages.success(request, f"Nominee '{student.name}' added successfully for '{position.title}'.")
                        return redirect(next_url)
                    return redirect('nomination_success')

    # 3. Initial form display on GET or re-render with errors
    else:
        form = NominationForm()
        form.fields['position'].queryset = Position.objects.none()

    return render(request, 'election/nominate.html', {
        'form':           form,
        'positions_json': positions_json,
    })

def home(request):
    import json
    import csv
    import os
    from django.db.models import Count
    from django.conf import settings
    from election.models import Vote, Student, Position

    total_votes_cast = Vote.objects.values('voter_usn').distinct().count()

    positions = Position.objects.all().order_by('title')
    position_names = []
    votes_per_position = []
    for pos in positions:
        position_names.append(pos.title)
        votes = Vote.objects.filter(position=pos).count()
        votes_per_position.append(votes)

    # Read semester counts directly from voterlist.csv
    csv_path = os.path.join(settings.BASE_DIR, 'voterlist.csv')
    sem_counts = {'3': 0, '5': 0, '7': 0}
    total_students = 0
    try:
        with open(csv_path, encoding='utf-8-sig') as f:
            for row in csv.reader(f):
                if len(row) >= 3 and row[0].strip():
                    sem = row[2].strip()
                    if sem in sem_counts:
                        sem_counts[sem] += 1
                    total_students += 1
    except Exception:
        total_students = Student.objects.count()

    semesters = ['3', '5', '7']
    voters_per_semester = [sem_counts[s] for s in semesters]
    not_voted = total_students - total_votes_cast

    context = {
        'total_students': total_students,
        'total_votes_cast': total_votes_cast,
        'position_names': json.dumps(position_names),
        'votes_per_position': json.dumps(votes_per_position),
        'semesters': json.dumps(semesters),
        'voters_per_semester': json.dumps(voters_per_semester),
        'voted_count': total_votes_cast,
        'not_voted_count': not_voted,
    }
    return render(request, 'election/home.html', context)
# election/views.py

from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Student, Vote

def voter_login(request):
    """
    1. GET: Show a simple form to enter USN.
    2. POST: 
       - Verify student exists.
       - Check they haven't already voted (any position).
       - Store USN in session for next step.
       - Redirect to cast_vote view.
    """
    if request.method == 'POST':
        usn = request.POST.get('usn').strip().upper()
        try:
            student = Student.objects.get(usn=usn)
        except Student.DoesNotExist:
            messages.error(request, "USN not found. Please register before voting.")
            return redirect('voter_login')

        # Optional: Validate semester/division if needed
        valid_sems = [choice[0] for choice in Student.SEMESTER_CHOICES]
        if student.semester not in valid_sems:  # or your allowed semesters
            messages.error(request, "Invalid semester for voting.")
            return redirect('voter_login')

        if Vote.objects.filter(voter_usn=usn).exists():
            messages.error(request, "You have already cast your vote.")
            return redirect('voter_login')

        request.session['voter_usn'] = usn
        return redirect('cast_vote')

    return render(request, 'election/vote_login.html')

# election/views.py

from django.db.models import Count
from .models import Position, Nominee, Vote

def cast_vote(request):
    usn = request.session.get('voter_usn')
    # student=Student.objects.get(usn=usn)
    # print("Voter:",usn,"sem=", student.semester,"div=",student.division)
    if not usn:
        return redirect('voter_login')

    # 1. Lookup voter and ensure division/semester are correct types
    try:
        student = Student.objects.get(usn=usn)
    except Student.DoesNotExist:
        return redirect('voter_login')

    # 2. Determine eligible positions (handle JSONField type mismatch)
    sem = student.semester
    div = student.division
    all_positions = Position.objects.all()
    eligible_positions = []
    for pos in all_positions:
        raw = pos.semester_eligibility
        elig = raw if isinstance(raw, list) else json.loads(raw)
        elig = [str(s) for s in elig]
    
        if "general" in elig and str(sem) == '7':
            eligible_positions.append(pos)
        elif str(sem) in elig:
            eligible_positions.append(pos)
    
    print("Eligible positions:", [p.title for p in eligible_positions])
    # 3. Handle form submit
    if request.method == 'POST':
        voted_for = []
        for pos in eligible_positions:
            key = f"position_{pos.id}"
            nominee_id = request.POST.get(key)
            if nominee_id:
                nominee = Nominee.objects.get(id=nominee_id)
                Vote.objects.create(
                    voter_usn=usn,
                    position=pos,
                    nominee=nominee
                )
                voted_for.append((pos, nominee))

        # end session and show success
        request.session.pop('voter_usn', None)
        return render(request, 'election/vote_success.html', {
            'student': student,
            'voted_for': voted_for
        })

    # 4. Build ballot for GET
    ballot = []
    for pos in eligible_positions:
        raw = pos.semester_eligibility
        elig = raw if isinstance(raw, list) else json.loads(raw)
        elig = [str(s) for s in elig]

        if "general" in elig:
            # Show nominees from all divisions for general positions
            noms = Nominee.objects.filter(
                position=pos,
                student__semester__in=['7',7]
            )
        else:
            # Show only division-specific nominees
            noms = Nominee.objects.filter(
                position=pos,
                student__division=student.division,
                student__semester=student.semester
            )

        print(f"General nominees for {pos.title}:", [(n.student.usn, n.student.semester, n.student.division) for n in noms])
        ballot.append((pos, noms))
        
    return render(request, 'election/cast_vote.html', {
        'student': student,
        'ballot': ballot
    })

# election/views.py

def vote_success(request):
    """Confirms to the voter that their votes have been recorded."""
    return render(request, 'election/vote_success.html')

# election/views.py

from django.shortcuts import render
from django.db.models import Count
from .models import Position, Vote


# election/views.py

def elected_members(request):
    """
    1. Iterate every Position in the system.
    2. Aggregate votes per nominee, order descending.
    3. Pick the top `max_winners` as the final elected members.
    4. Render a unified list of (position, [winners]).
    """
    all_results = []
    for pos in Position.objects.all():
        vote_counts = (
            Vote.objects
            .filter(position=pos)
            .values('nominee')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        top_ids = [vc['nominee'] for vc in vote_counts[:pos.max_winners]]
        winners = pos.nominee_set.filter(id__in=top_ids)
        all_results.append((pos, winners, vote_counts))

    return render(request, 'election/elected_members.html', {
        'all_results': all_results
    })

def nomination_success(request):
    """
    Renders a simple confirmation page after a successful nomination.
    """
    return render(request, 'election/nomination_success.html')

def nominee_list(request):
    sem = request.GET.get('semester')
    semesters = ['3', '5', '7', 'general']

    results = []
    all_positions = Position.objects.all().prefetch_related('nominee_set__student')

    for pos in all_positions:
        elig = [str(s) for s in pos.semester_eligibility]

        if not sem or sem == 'all':
            show_pos = True
        elif sem == 'general':
            show_pos = 'general' in elig
        else:
            show_pos = str(sem) in elig

        if not show_pos:
            continue

        if not sem or sem == 'all':
            noms = list(pos.nominee_set.all())
        elif sem == 'general':
            noms = [n for n in pos.nominee_set.all() if n.student.semester == '7' or 'general' in elig]
        else:
            noms = [n for n in pos.nominee_set.all() if n.student.semester == sem]

        if noms:
            results.append((pos, noms))

    return render(request, 'election/nominee_list.html', {
        'semesters': semesters,
        'selected_semester': sem or '',
        'results': results,
    })


def edit_nominee(request, nominee_id):
    nominee = get_object_or_404(Nominee.objects.select_related('student', 'position'), id=nominee_id)
    sem_filter = request.GET.get('semester', '') or request.POST.get('semester', '')

    if request.method == 'POST':
        form = NomineeEditForm(request.POST, request.FILES)
        if form.is_valid():
            student = nominee.student
            student.name = form.cleaned_data['student_name'].strip()
            student.division = form.cleaned_data['student_division']
            student.semester = form.cleaned_data['student_semester']
            student.save()

            nominee.position = form.cleaned_data['position']
            if request.FILES.get('photo'):
                nominee.photo = request.FILES['photo']
            nominee.save()

            messages.success(request, f"Nominee '{student.name}' updated successfully.")
            if sem_filter:
                return redirect(f"/nominees/?semester={sem_filter}")
            return redirect('nominee_list')
    else:
        initial_data = {
            'student_name': nominee.student.name,
            'student_usn': nominee.student.usn,
            'student_semester': nominee.student.semester,
            'student_division': nominee.student.division,
            'position': nominee.position,
        }
        form = NomineeEditForm(initial=initial_data)

    return render(request, 'election/edit_nominee.html', {
        'form': form,
        'nominee': nominee,
        'semester_filter': sem_filter,
    })


def delete_nominee(request, nominee_id):
    nominee = get_object_or_404(Nominee, id=nominee_id)
    name = nominee.student.name
    pos_title = nominee.position.title
    sem_filter = request.GET.get('semester', '') or request.POST.get('semester', '')

    # Delete any votes associated with this nominee
    Vote.objects.filter(nominee=nominee).delete()
    nominee.delete()

    messages.success(request, f"Nominee '{name}' for '{pos_title}' deleted successfully.")
    if sem_filter:
        return redirect(f"/nominees/?semester={sem_filter}")
    return redirect('nominee_list')

import csv
from django.http import HttpResponse
from election.models import Position, Nominee, Vote
from django.db import models
def download_all_results(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="all_results.csv"'
    writer = csv.writer(response)
    writer.writerow(['Position', 'Winner Name', 'USN', 'Semester', 'Division', 'Votes'])

    for position in Position.objects.all():
        nominees = Nominee.objects.filter(position=position).select_related('student')
        vote_counts = (
            Vote.objects.filter(position=position)
            .values('nominee')
            .annotate(count=models.Count('id'))
        )
        vote_map = {vc['nominee']: vc['count'] for vc in vote_counts}
        max_votes = max(vote_map.values(), default=0)
        winners = [n for n in nominees if vote_map.get(n.id, 0) == max_votes and max_votes > 0]

        for winner in winners:
            writer.writerow([
                position.title,
                winner.student.name,
                winner.student.usn,
                winner.student.semester,
                winner.student.division,
                vote_map.get(winner.id, 0)
            ])

    return response

def download_all_results_excel(request):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Election Results'
    headers = ['Position', 'Winner Name', 'USN', 'Semester', 'Division', 'Votes']
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for position in Position.objects.all():
        nominees = Nominee.objects.filter(position=position).select_related('student')
        vote_counts = (
            Vote.objects.filter(position=position)
            .values('nominee')
            .annotate(count=models.Count('id'))
        )
        vote_map = {vote_count['nominee']: vote_count['count'] for vote_count in vote_counts}
        max_votes = max(vote_map.values(), default=0)
        winners = [
            nominee for nominee in nominees
            if vote_map.get(nominee.id, 0) == max_votes and max_votes > 0
        ]

        for winner in winners:
            sheet.append([
                position.title,
                winner.student.name,
                winner.student.usn,
                winner.student.semester,
                winner.student.division,
                vote_map.get(winner.id, 0),
            ])

    for column in sheet.columns:
        column_letter = column[0].column_letter
        sheet.column_dimensions[column_letter].width = min(
            max(len(str(cell.value or '')) for cell in column) + 2,
            30,
        )

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="all_results.xlsx"'
    workbook.save(response)
    return response

from django.shortcuts import render
from django.db.models import Count
from election.models import Position, Vote, Student

from django.shortcuts import render
from django.db.models import Count
from election.models import Position, Vote, Student

# def semester_results(request):
#     sem = request.GET.get('semester')
#     division = request.GET.get('division')

#     raw_semesters = {str(s) for p in Position.objects.all() for s in p.semester_eligibility}
#     semesters = sorted([s for s in raw_semesters if s != "general"], key=int)
#     if "general" in raw_semesters:
#         semesters.append("general")

#     divisions = sorted(set(Student.objects.values_list('division', flat=True)))

#     results = []
#     positions = []

#     if sem:
#         for pos in Position.objects.all():
#             elig = [str(s) for s in pos.semester_eligibility]
#             if str(sem) == "general":
#                 if "general" in elig:
#                     positions.append(pos)
#             else:
#                 if str(sem) in elig:
#                     positions.append(pos)

#         for pos in positions:
#             vote_counts = (
#                 Vote.objects
#                 .filter(position=pos)
#                 .values('nominee')
#                 .annotate(count=Count('id'))
#                 .order_by('-count')
#             )

#             top_nominees = []
#             for vc in vote_counts:
#                 try:
#                     nominee = pos.nominee_set.select_related('student').get(id=vc['nominee'])
#                     if nominee.student.semester == int(sem) and (not division or nominee.student.division == division):
#                         top_nominees.append(nominee)
#                 except:
#                     continue

#             top_nominees = top_nominees[:pos.max_winners]
#             if top_nominees:
#                 results.append((pos, top_nominees, vote_counts))

#     return render(request, 'election/semester_results.html', {
#         'semesters': semesters,
#         'divisions': divisions,
#         'selected_semester': sem,
#         'selected_division': division,
#         'results': results,
#     })
from django.shortcuts import render
from django.db.models import Count
from election.models import Position, Vote, Student

from django.shortcuts import render
from django.db.models import Count
from election.models import Position, Vote, Student

def semester_view(request):
    sem = request.GET.get('semester')
    division = request.GET.get('division')

    # Build dropdown options
    raw_semesters = {str(s) for p in Position.objects.all() for s in p.semester_eligibility}
    semesters = sorted([s for s in raw_semesters if s != "general"], key=int)
    if "general" in raw_semesters:
        semesters.append("general")

    divisions = sorted(set(Student.objects.values_list('division', flat=True)))

    results = []

    if sem:
        eligible_positions = []
        for pos in Position.objects.all():
            elig = [str(s) for s in pos.semester_eligibility]
            if sem == "general":
                if "general" in elig:
                    eligible_positions.append(pos)
            else:
                if sem in elig:
                    eligible_positions.append(pos)

        for pos in eligible_positions:
            vote_counts = (
                Vote.objects
                .filter(position=pos)
                .values('nominee')
                .annotate(count=Count('id'))
                .order_by('-count')
            )

            top_nominees = []
            for vc in vote_counts:
                try:
                    nominee = pos.nominee_set.select_related('student').get(id=vc['nominee'])
                    if (
                        (sem == "general" and nominee.student.semester == "7") or
                        (sem != "general" and nominee.student.semester == sem)
                    ) and (not division or nominee.student.division == division):
                        top_nominees.append(nominee)
                except Nominee.DoesNotExist:
                    continue
                

            top_nominees = top_nominees[:pos.max_winners]
            if top_nominees:
                results.append((pos, top_nominees, vote_counts))

    return render(request, 'election/semester_view.html', {
        'semesters': semesters,
        'divisions': divisions,
        'selected_semester': sem,
        'selected_division': division,
        'results': results,
    })

def download_semester_results(request):
    semester = request.GET.get('semester', '7')  # default to 7th semester
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="semester_{semester}_results.csv"'
    writer = csv.writer(response)
    writer.writerow(['Position', 'Winner Name', 'USN', 'Division', 'Votes'])

    for position in Position.objects.all():
        nominees = Nominee.objects.filter(position=position, student__semester=semester).select_related('student')
        vote_counts = (
            Vote.objects.filter(position=position)
            .values('nominee')
            .annotate(count=models.Count('id'))
        )
        vote_map = {vc['nominee']: vc['count'] for vc in vote_counts}
        max_votes = max(vote_map.values(), default=0)
        winners = [n for n in nominees if vote_map.get(n.id, 0) == max_votes and max_votes > 0]

        for winner in winners:
            writer.writerow([
                position.title,
                winner.student.name,
                winner.student.usn,
                winner.student.division,
                vote_map.get(winner.id, 0)
            ])

    return response

def download_semester_results_excel(request):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    semester = request.GET.get('semester', '3')
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = f'Semester {semester} Results'
    headers = ['Position', 'Winner Name', 'USN', 'Division', 'Votes']
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for position in Position.objects.all():
        nominees = Nominee.objects.filter(
            position=position,
            student__semester=semester,
        ).select_related('student')
        vote_counts = (
            Vote.objects.filter(position=position)
            .values('nominee')
            .annotate(count=models.Count('id'))
        )
        vote_map = {vote_count['nominee']: vote_count['count'] for vote_count in vote_counts}
        max_votes = max(vote_map.values(), default=0)
        winners = [
            nominee for nominee in nominees
            if vote_map.get(nominee.id, 0) == max_votes and max_votes > 0
        ]

        for winner in winners:
            sheet.append([
                position.title,
                winner.student.name,
                winner.student.usn,
                winner.student.division,
                vote_map.get(winner.id, 0),
            ])

    for column in sheet.columns:
        column_letter = column[0].column_letter
        sheet.column_dimensions[column_letter].width = min(
            max(len(str(cell.value or '')) for cell in column) + 2,
            30,
        )

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="semester_{semester}_results.xlsx"'
    )
    workbook.save(response)
    return response

def download_semester_results_pdf(request):
    semester = request.GET.get('semester', '3')
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    def draw_header():
        pdf.setFont('Helvetica-Bold', 16)
        pdf.drawString(50, height - 50, f'Semester {semester} Election Results')
        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(50, height - 80, 'Position')
        pdf.drawString(190, height - 80, 'Winner')
        pdf.drawString(350, height - 80, 'USN')
        pdf.drawString(450, height - 80, 'Division')
        pdf.drawString(510, height - 80, 'Votes')
        return height - 100

    y = draw_header()
    pdf.setFont('Helvetica', 10)
    for position in Position.objects.all():
        nominees = Nominee.objects.filter(
            position=position,
            student__semester=semester,
        ).select_related('student')
        vote_counts = (
            Vote.objects.filter(position=position)
            .values('nominee')
            .annotate(count=models.Count('id'))
        )
        vote_map = {vote_count['nominee']: vote_count['count'] for vote_count in vote_counts}
        max_votes = max(vote_map.values(), default=0)
        winners = [
            nominee for nominee in nominees
            if vote_map.get(nominee.id, 0) == max_votes and max_votes > 0
        ]

        for winner in winners:
            if y < 50:
                pdf.showPage()
                y = draw_header()
                pdf.setFont('Helvetica', 10)
            pdf.drawString(50, y, position.title[:22])
            pdf.drawString(190, y, winner.student.name[:25])
            pdf.drawString(350, y, winner.student.usn[:15])
            pdf.drawString(450, y, winner.student.division)
            pdf.drawString(510, y, str(vote_map.get(winner.id, 0)))
            y -= 20

    pdf.save()
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="semester_{semester}_results.pdf"'
    })

def download_voter_details_excel(request):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    voter_usn = request.GET.get('voter_usn', '').strip().upper()
    if not voter_usn:
        return HttpResponse('Please select a voter USN.', status=400)

    votes = Vote.objects.filter(voter_usn=voter_usn).select_related(
        'position', 'nominee__student'
    ).order_by('position__title')
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Voter Details'
    sheet.append(['Voter USN', 'Position', 'Candidate', 'Candidate USN', 'Vote Time'])
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for vote in votes:
        sheet.append([
            vote.voter_usn,
            vote.position.title,
            vote.nominee.student.name,
            vote.nominee.student.usn,
            vote.timestamp.replace(tzinfo=None) if vote.timestamp else '',
        ])

    for column in sheet.columns:
        column_letter = column[0].column_letter
        sheet.column_dimensions[column_letter].width = min(
            max(len(str(cell.value or '')) for cell in column) + 2,
            32,
        )

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="voter_{voter_usn}_details.xlsx"'
    workbook.save(response)
    return response

def download_voter_details_pdf(request):
    voter_usn = request.GET.get('voter_usn', '').strip().upper()
    if not voter_usn:
        return HttpResponse('Please select a voter USN.', status=400)

    votes = Vote.objects.filter(voter_usn=voter_usn).select_related(
        'position', 'nominee__student'
    ).order_by('position__title')
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawString(50, y, f'Voting Details for {voter_usn}')
    y -= 35
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(50, y, 'Position')
    pdf.drawString(190, y, 'Candidate')
    pdf.drawString(350, y, 'Candidate USN')
    pdf.drawString(460, y, 'Vote Time')
    y -= 20
    pdf.setFont('Helvetica', 9)

    for vote in votes:
        if y < 50:
            pdf.showPage()
            y = height - 50
            pdf.setFont('Helvetica', 9)
        pdf.drawString(50, y, vote.position.title[:22])
        pdf.drawString(190, y, vote.nominee.student.name[:24])
        pdf.drawString(350, y, vote.nominee.student.usn[:15])
        timestamp = vote.timestamp.strftime('%Y-%m-%d %H:%M') if vote.timestamp else ''
        pdf.drawString(460, y, timestamp)
        y -= 18

    pdf.save()
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="voter_{voter_usn}_details.pdf"'
    })


from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from django.db.models import Count
from election.models import Position, Vote, Nominee
import io, os

from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from django.db.models import Count
from election.models import Position, Vote, Nominee, Student
import io, os

def download_all_results_pdf(request):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    p.setFont("Helvetica-Bold", 16)
    p.drawString(180, y, "TECHNO-X Office Bearers Election Results")  
    y -= 40

    semesters = ['3', '5', '7']
    divisions = ['A', 'B']

    for sem in semesters:
        for div in divisions:
            p.setFont("Helvetica-Bold", 14)
            p.drawString(50, y, f"Semester {sem} - Division {div}")
            y -= 25

            positions = [pos for pos in Position.objects.all() if str(sem) in map(str, pos.semester_eligibility)]
            for pos in positions:
                vote_counts = (
                    Vote.objects.filter(position=pos)
                    .values('nominee')
                    .annotate(count=Count('id'))
                )
                vote_map = {vc['nominee']: vc['count'] for vc in vote_counts}

                nominees = pos.nominee_set.select_related('student')
                filtered_nominees = [
                    n for n in nominees
                    if n.student.semester == sem and n.student.division == div
                ]

                if not filtered_nominees:
                    continue

                max_votes = max([vote_map.get(n.id, 0) for n in filtered_nominees], default=0)
                winners = [n for n in filtered_nominees if vote_map.get(n.id, 0) == max_votes and max_votes > 0]

                if not winners:
                    continue

                p.setFont("Helvetica-Bold", 12)
                p.drawString(60, y, f"Position: {pos.title}")
                y -= 20

                for winner in winners:
                    student = winner.student
                    votes = vote_map.get(winner.id, 0)

                    if winner.photo and os.path.exists(winner.photo.path):
                        try:
                            img = ImageReader(winner.photo.path)
                            p.drawImage(img, 60, y - 60, width=50, height=50, mask='auto')
                        except Exception as e:
                            print("Image error:", e)

                    p.setFont("Helvetica", 11)
                    p.drawString(120, y - 10, f"{student.name} ({student.usn})")
                    # p.drawString(120, y - 25, f"Votes: {votes}")
                    y -= 80

                    if y < 100:
                        p.showPage()
                        y = height - 50

            y -= 20  # spacing between divisions

    # Add general positions (only for semester 7)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y, "General Positions - Semester 7")
    y -= 25

    general_positions = [
    pos for pos in Position.objects.all()
    if "general" in map(str, pos.semester_eligibility)
]

    for pos in general_positions:
        vote_counts = (
            Vote.objects.filter(position=pos)
            .values('nominee')
            .annotate(count=Count('id'))
        )
        vote_map = {vc['nominee']: vc['count'] for vc in vote_counts}

        nominees = pos.nominee_set.select_related('student')
        filtered_nominees = [n for n in nominees if n.student.semester == '7']

        if not filtered_nominees:
            continue

        max_votes = max([vote_map.get(n.id, 0) for n in filtered_nominees], default=0)
        winners = [n for n in filtered_nominees if vote_map.get(n.id, 0) == max_votes and max_votes > 0]

        if not winners:
            continue

        p.setFont("Helvetica-Bold", 12)
        p.drawString(60, y, f"Position: {pos.title}")
        y -= 20

        for winner in winners:
            student = winner.student
            votes = vote_map.get(winner.id, 0)

            if winner.photo and os.path.exists(winner.photo.path):
                try:
                    img = ImageReader(winner.photo.path)
                    p.drawImage(img, 60, y - 60, width=50, height=50, mask='auto')
                except Exception as e:
                    print("Image error:", e)

            p.setFont("Helvetica", 11)
            p.drawString(120, y - 10, f"{student.name} ({student.usn})")
            # p.drawString(120, y - 25, f"Votes: {votes}")
            y -= 80

            if y < 100:
                p.showPage()
                y = height - 50

    p.save()
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf', headers={
        'Content-Disposition': 'attachment; filename="complete_election_results.pdf"'
    })

from django.http import HttpResponse
from django.db.models import Count
from election.models import Position, Vote, Nominee
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from django.http import HttpResponse
from django.db.models import Count
from election.models import Position, Vote, Nominee
from docx import Document
from docx.shared import Pt, Inches
import os

def download_all_results_docx(request):
    document = Document()
    document.add_heading("Complete Election Results", level=1)

    semesters = ['3', '5', '7']
    divisions = ['A', 'B']

    for sem in semesters:
        for div in divisions:
            document.add_heading(f"Semester {sem} - Division {div}", level=2)

            positions = [
                pos for pos in Position.objects.all()
                if str(sem) in map(str, pos.semester_eligibility)
            ]

            for pos in positions:
                vote_counts = (
                    Vote.objects.filter(position=pos)
                    .values('nominee')
                    .annotate(count=Count('id'))
                )
                vote_map = {vc['nominee']: vc['count'] for vc in vote_counts}

                nominees = pos.nominee_set.select_related('student')
                filtered_nominees = [
                    n for n in nominees
                    if n.student.semester == sem and n.student.division == div
                ]

                if not filtered_nominees:
                    continue

                max_votes = max([vote_map.get(n.id, 0) for n in filtered_nominees], default=0)
                winners = [n for n in filtered_nominees if vote_map.get(n.id, 0) == max_votes and max_votes > 0]

                if not winners:
                    continue

                document.add_paragraph(f"Position: {pos.title}", style='Intense Quote')

                for winner in winners:
                    student = winner.student
                    votes = vote_map.get(winner.id, 0)

                    # Add photo if available and accessible
                    if winner.photo and os.path.exists(winner.photo.path):
                        try:
                            document.add_picture(winner.photo.path, width=Inches(1.0))
                        except Exception as e:
                            print("Image error:", e)

                    para = document.add_paragraph()
                    para.add_run(f"{student.name} ({student.usn})\n").bold = True
                    para.add_run(f"Semester: {student.semester}, Division: {student.division}, Votes: {votes}")
                    para.paragraph_format.space_after = Pt(12)

    # General positions (only for semester 7)
    document.add_heading("General Positions - Semester 7", level=2)
    general_positions = [
        pos for pos in Position.objects.all()
        if "general" in map(str, pos.semester_eligibility)
    ]

    for pos in general_positions:
        vote_counts = (
            Vote.objects.filter(position=pos)
            .values('nominee')
            .annotate(count=Count('id'))
        )
        vote_map = {vc['nominee']: vc['count'] for vc in vote_counts}

        nominees = pos.nominee_set.select_related('student')
        filtered_nominees = [n for n in nominees if n.student.semester == '7']

        if not filtered_nominees:
            continue

        max_votes = max([vote_map.get(n.id, 0) for n in filtered_nominees], default=0)
        winners = [n for n in filtered_nominees if vote_map.get(n.id, 0) == max_votes and max_votes > 0]

        if not winners:
            continue

        document.add_paragraph(f"Position: {pos.title}", style='Intense Quote')

        for winner in winners:
            student = winner.student
            votes = vote_map.get(winner.id, 0)

            if winner.photo and os.path.exists(winner.photo.path):
                try:
                    document.add_picture(winner.photo.path, width=Inches(1.0))
                except Exception as e:
                    print("Image error:", e)

            para = document.add_paragraph()
            para.add_run(f"{student.name} ({student.usn})\n").bold = True
            para.add_run(f"Semester: {student.semester}, Division: {student.division}, Votes: {votes}")
            para.paragraph_format.space_after = Pt(12)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = 'attachment; filename="complete_election_results.docx"'
    document.save(response)
    return response

def add_voter(request):
    import csv
    import io
    from django.contrib import messages
    from .models import Student
    from django.shortcuts import render, redirect

    if request.method == 'POST':
        action = request.POST.get('action', 'single')

        # ── BULK CSV UPLOAD ──────────────────────────────────────────────
        if action == 'bulk_csv':
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                messages.error(request, 'Please select a CSV file to upload.')
                return redirect('add_voter')

            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'File must be a .csv file.')
                return redirect('add_voter')

            created, updated, skipped, errors = 0, 0, 0, []
            try:
                decoded = csv_file.read().decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(decoded))
                required_cols = {'name', 'usn', 'semester', 'gender', 'division'}
                if not required_cols.issubset(set(c.strip().lower() for c in (reader.fieldnames or []))):
                    messages.error(request,
                        'CSV must have columns: name, usn, semester, gender, division')
                    return redirect('add_voter')

                for i, row in enumerate(reader, start=2):
                    name     = row.get('name', '').strip()
                    usn      = row.get('usn', '').strip().upper()
                    semester = str(row.get('semester', '')).strip()
                    gender   = row.get('gender', '').strip()
                    division = row.get('division', '').strip().upper()

                    if not all([name, usn, semester, division]):
                        skipped += 1
                        errors.append(f'Row {i}: Missing fields — skipped.')
                        continue

                    if semester not in ['3', '5', '7', 'general']:
                        skipped += 1
                        errors.append(f'Row {i} ({usn}): Invalid semester "{semester}".')
                        continue

                    if division not in ['A', 'B']:
                        skipped += 1
                        errors.append(f'Row {i} ({usn}): Invalid division "{division}".')
                        continue

                    student, was_created = Student.objects.get_or_create(
                        usn=usn,
                        defaults={'name': name, 'semester': semester,
                                  'gender': gender, 'division': division}
                    )
                    if was_created:
                        created += 1
                    else:
                        skipped += 1

            except Exception as e:
                messages.error(request, f'Error processing CSV: {e}')
                return redirect('add_voter')

            messages.success(request,
                f'✅ CSV Import Done! Created: {created} | Skipped (duplicates/errors): {skipped}')
            for err in errors[:10]:   # show max 10 row-level errors
                messages.warning(request, err)
            return redirect('add_voter')

        # ── SINGLE VOTER ─────────────────────────────────────────────────
        name     = request.POST.get('name', '').strip()
        usn      = request.POST.get('usn', '').strip().upper()
        semester = request.POST.get('semester', '').strip()
        division = request.POST.get('division', '').strip()
        gender   = request.POST.get('gender', '').strip()

        if Student.objects.filter(usn=usn).exists():
            messages.error(request, f'Voter with USN {usn} already exists.')
        else:
            try:
                Student.objects.create(
                    name=name, usn=usn,
                    semester=semester, division=division, gender=gender
                )
                messages.success(request, f'Voter {name} ({usn}) added successfully.')
            except Exception as e:
                messages.error(request, f'Error adding voter: {e}')
        return redirect('add_voter')

    return render(request, 'election/add_voter.html')

def admin_dashboard(request):
    import json
    import csv
    import os
    from django.db.models import Count
    from django.conf import settings
    from election.models import Vote, Student, Position
    from django.shortcuts import render

    total_votes_cast = Vote.objects.values('voter_usn').distinct().count()

    positions = Position.objects.all()
    position_names = []
    votes_per_position = []
    for pos in positions:
        position_names.append(pos.title)
        votes = Vote.objects.filter(position=pos).count()
        votes_per_position.append(votes)

    # Read semester counts directly from voterlist.csv
    csv_path = os.path.join(settings.BASE_DIR, 'voterlist.csv')
    sem_counts = {'3': 0, '5': 0, '7': 0}
    total_students = 0
    try:
        with open(csv_path, encoding='utf-8-sig') as f:
            for row in csv.reader(f):
                if len(row) >= 3 and row[0].strip():
                    sem = row[2].strip()
                    if sem in sem_counts:
                        sem_counts[sem] += 1
                    total_students += 1
    except Exception:
        total_students = Student.objects.count()

    semesters = ['3', '5', '7']
    voters_per_semester = [sem_counts[s] for s in semesters]
    not_voted = total_students - total_votes_cast
    selected_position_id = request.GET.get('position', '').strip()
    detail_positions = positions
    if selected_position_id.isdigit() and positions.filter(id=selected_position_id).exists():
        detail_positions = positions.filter(id=selected_position_id)

    vote_records = Vote.objects.select_related(
        'nominee__student', 'position'
    ).order_by('-timestamp')
    votes_by_position = {}
    for vote in vote_records:
        votes_by_position.setdefault(vote.position_id, []).append(vote)
    vote_details_by_position = [
        {
            'position': position,
            'votes': votes_by_position.get(position.id, []),
        }
        for position in sorted(
            detail_positions,
            key=lambda position: bool(votes_by_position.get(position.id)),
            reverse=True,
        )
    ]

    # ── Nominee vote leaderboard (per position) ───────────────────────
    from election.models import Nominee
    nominee_vote_data = []
    for pos in positions:
        nom_counts = (
            Vote.objects.filter(position=pos)
            .values('nominee')
            .annotate(count=Count('id'))
        )
        vote_map = {vc['nominee']: vc['count'] for vc in nom_counts}
        nominees = Nominee.objects.filter(position=pos).select_related('student')
        entries = sorted(
            [
                {
                    'name': n.student.name,
                    'usn': n.student.usn,
                    'semester': n.student.semester,
                    'division': n.student.division,
                    'votes': vote_map.get(n.id, 0),
                }
                for n in nominees
            ],
            key=lambda x: x['votes'],
            reverse=True,
        )
        if entries:
            nominee_vote_data.append({'position': pos, 'entries': entries})

    context = {
        'total_students': total_students,
        'total_votes_cast': total_votes_cast,
        'position_names': json.dumps(position_names),
        'votes_per_position': json.dumps(votes_per_position),
        'semesters': json.dumps(semesters),
        'voters_per_semester': json.dumps(voters_per_semester),
        'voted_count': total_votes_cast,
        'not_voted_count': not_voted,
        'vote_details_by_position': vote_details_by_position,
        'positions': positions,
        'selected_position_id': selected_position_id,
        'semester_options': ['3', '5', '7'],
        'voter_usns': Vote.objects.values_list(
            'voter_usn', flat=True
        ).distinct().order_by('voter_usn'),
        'nominee_vote_data': nominee_vote_data,
    }
    
    return render(request, 'election/admin_dashboard.html', context)
