"""Regression of file evidence and public academic profiles."""
import io
from collections import Counter
from django.test import TestCase, SimpleTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from pypdf import PdfWriter
from .models import Application, Document, ProfileDocument
from .tests import Fixture


def pdf(name, width=72):
    writer=PdfWriter()
    writer.add_blank_page(width=width,height=72)
    stream=io.BytesIO(); writer.write(stream)
    return SimpleUploadedFile(name,stream.getvalue(),content_type='application/pdf')


class DocumentEvidenceTests(Fixture,TestCase):
    def setUp(self):
        self.setup_data()

    def draft(self,degree='I'):
        reply=self.client.post('/api/action',{'action':'create_application','offer_id':self.offers[degree].pk},format='json')
        self.assertEqual(reply.status_code,200,reply.data)
        return reply.data['id']

    def upload_profile(self,kind,name,width=72):
        result=self.client.post('/api/profile/document',{'kind':kind,'file':pdf(name,width)},format='multipart')
        self.assertEqual(result.status_code,200,result.data)
        return result.data

    def test_missing_payment_does_not_report_existing_education_as_missing(self):
        ident=self.draft()
        revision=self.client.get('/api/workspace').json()['revision']
        proof=self.upload_profile('education','swiadectwo.pdf')
        self.assertEqual(proof['workspace_revision'],revision+1)
        response=self.client.post('/api/action',{'action':'submit','id':ident},format='json')
        self.assertEqual(response.status_code,400)
        self.assertIn('potwierdzenie przelewu',str(response.data))
        self.assertNotIn('Dodaj świadectwo',str(response.data))
        self.assertEqual(ProfileDocument.objects.get(pk=proof['id']).original_name,'swiadectwo.pdf')
        self.assertFalse(Document.objects.filter(application_id=ident).exists())
        Application.objects.get(pk=ident).refresh_from_db()

    def test_uploaded_files_are_attached_and_replacements_preserve_submitted_evidence(self):
        ident=self.draft()
        self.upload_profile('education','pierwsze.pdf')
        current=self.upload_profile('education','poprawione.pdf',73)
        payment=self.client.post(f'/api/upload/{ident}',{'kind':'fee','file':pdf('przelew.pdf')},format='multipart')
        self.assertEqual(payment.status_code,200,payment.data)
        submitted=self.client.post('/api/action',{'action':'submit','id':ident},format='json')
        self.assertEqual(submitted.status_code,200,submitted.data)
        evidence=Document.objects.get(application_id=ident,kind='education')
        self.assertEqual(evidence.profile_source_id,current['id'])
        digest=evidence.sha256
        self.upload_profile('education','nastepne.pdf',74)
        evidence.refresh_from_db()
        self.assertEqual(evidence.sha256,digest)
        workspace=self.client.get('/api/workspace').json()
        app=next(a for a in workspace['applications'] if a['id']==ident)
        education=next(d for d in app['documents'] if d['kind']=='education')
        self.assertEqual(education['profile_source_id'],current['id'])
        self.assertEqual(education['name'],'poprawione.pdf')

    def test_master_uses_the_diploma_and_invalid_replacement_keeps_valid_file(self):
        ident=self.draft('II')
        diploma=self.upload_profile('diploma','dyplom.pdf')
        rejected=self.client.post('/api/profile/document',{'kind':'diploma',
            'file':SimpleUploadedFile('dyplom.pdf',b'invalid PDF')},format='multipart')
        self.assertEqual(rejected.status_code,400)
        self.assertEqual(ProfileDocument.objects.filter(user=self.candidate,kind='diploma').count(),1)
        paid=self.client.post(f'/api/upload/{ident}',{'kind':'fee','file':pdf('przelew.pdf')},format='multipart')
        self.assertEqual(paid.status_code,200,paid.data)
        sent=self.client.post('/api/action',{'action':'submit','id':ident},format='json')
        self.assertEqual(sent.status_code,200,sent.data)
        self.assertEqual(Document.objects.get(application_id=ident,kind='education').profile_source_id,diploma['id'])


class AcademicStaffTests(SimpleTestCase):
    def test_public_profiles_have_valid_faculty_programme_mapping_and_are_explicit_demo(self):
        from .catalog_data import PROGRAMS,FACULTIES
        response=self.client.get('/api/lecturers')
        self.assertEqual(response.status_code,200)
        data=response.json()
        self.assertTrue(data['illustrative'])
        self.assertFalse(data['repository']['synchronized'])
        self.assertEqual({f['code'] for f in data['faculties']},{f[0] for f in FACULTIES})
        self.assertEqual(len({p['id'] for p in data['people']}),len(data['people']))
        per_faculty = Counter(person['faculty'] for person in data['people'])
        self.assertEqual(set(per_faculty), {faculty[0] for faculty in FACULTIES})
        self.assertTrue(all(2 <= count <= 3 for count in per_faculty.values()))
        for person in data['people']:
            self.assertTrue(person['illustrative'])
            self.assertIsNone(person['external_person_id'])
            self.assertIn(person['program'],[p[0] for p in PROGRAMS[person['faculty']]])
        self.assertEqual(self.client.post('/api/lecturers',{}).status_code,405)
