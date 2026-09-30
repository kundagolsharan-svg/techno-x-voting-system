from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('dashboard/', views.home, name='home'),
    path('nominate/', views.nominate, name='nominate'),
    path('nomination-success/', views.nomination_success, name='nomination_success'),
    path('vote-login/', views.voter_login, name='voter_login'),
    path('cast-vote/', views.cast_vote, name='cast_vote'),
    path('vote-success/', views.vote_success, name='vote_success'),
    path('nominees/', views.nominee_list, name='nominee_list'),
    path('nominees/edit/<int:nominee_id>/', views.edit_nominee, name='edit_nominee'),
    path('nominees/delete/<int:nominee_id>/', views.delete_nominee, name='delete_nominee'),
    path('results/', views.semester_view, name='results'),
    path('elected-members/', views.elected_members, name='elected_members'),
    path('download/all/', views.download_all_results, name='download_all_results'),
    path('download/semester/', views.download_semester_results, name='download_semester_results'),
    path('download/pdf/', views.download_all_results_pdf, name='download_all_results_pdf'),
    path('download/docx/', views.download_all_results_docx, name='download_all_results_docx'),
    path('add-voter/', views.add_voter, name='add_voter'),

    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),

    # Results URLs will go here next
]
# election/urls.py

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)