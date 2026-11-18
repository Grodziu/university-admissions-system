from django.urls import path
from admissions import api

urlpatterns = [
    path('api/health', api.health), path('api/login', api.login),
    path('api/register', api.register), path('api/recover', api.recover),
    path('api/catalog', api.catalog), path('api/thresholds', api.thresholds),
    path('api/lecturers', api.lecturers),
    path('api/workspace', api.workspace), path('api/state', api.state), path('api/action', api.action),
    path('api/upload/<int:application_id>', api.upload),
    path('api/profile/photo', api.upload_profile_photo),
    path('api/profile/photo/<int:photo_id>', api.download_profile_photo),
    path('api/profile/document', api.upload_profile_document),
    path('api/profile/document/<int:document_id>', api.download_profile_document),
    path('api/profile/locate', api.locate_residence),
    path('api/document/<int:document_id>', api.download), path('api/export', api.export),
    path('api/publications/<int:offer_id>', api.publications),
    path('api/ranking/<int:offer_id>', api.ranking),
    path('api/history/<int:application_id>', api.history), path('api/backup', api.backup),
]
