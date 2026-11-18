from django.db import migrations


def seed_catalogue_and_profiles(apps, schema_editor):
    from admissions.campus import DORMS
    from admissions.profiles import demo_residence

    Dormitory = apps.get_model('admissions', 'Dormitory')
    Residence = apps.get_model('admissions', 'Residence')
    Contact = apps.get_model('admissions', 'CandidateContact')
    ProfileDocument = apps.get_model('admissions', 'ProfileDocument')
    Document = apps.get_model('admissions', 'Document')
    User = apps.get_model('admissions', 'User')
    Dormitory.objects.bulk_create([
        Dormitory(code=code, name=name, address=address, description=details, seats=seats, latitude=lat, longitude=lon)
        for code, name, address, details, seats, lat, lon in DORMS
    ])
    demo_people = list(User.objects.filter(role='candidate', is_demo=True).values_list('pk', flat=True))
    Residence.objects.bulk_create([Residence(user_id=id_, **demo_residence(i)) for i,id_ in enumerate(demo_people)], batch_size=500)
    Contact.objects.bulk_create([Contact(user_id=id_, phone='000000000') for id_ in demo_people], ignore_conflicts=True, batch_size=500)
    Contact.objects.filter(user_id__in=demo_people, phone='').update(phone='000000000')
    seen = set()
    profiles = []
    docs = (Document.objects.filter(kind__in=['education','portfolio','bonus','qualification'])
            .select_related('application__offer').order_by('-uploaded_at','-pk'))
    for document in docs.iterator():
        user_id = document.application.candidate_id
        kind = 'diploma' if document.kind == 'education' and document.application.offer.degree != 'I' else document.kind
        if (user_id, kind) not in seen:
            seen.add((user_id,kind))
            profiles.append(ProfileDocument(user_id=user_id, kind=kind, version=1,
                             file=document.file.name, original_name=document.original_name, sha256=document.sha256,
                             uploaded_at=document.uploaded_at))
    ProfileDocument.objects.bulk_create(profiles,batch_size=500)


class Migration(migrations.Migration):
    dependencies = [('admissions','0008_candidate_documents_and_housing')]
    operations = [migrations.RunPython(seed_catalogue_and_profiles)]
