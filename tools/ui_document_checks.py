"""Drive the actual Qt upload buttons against the test server."""
import time
from pathlib import Path
from unittest.mock import patch
from pypdf import PdfWriter
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QFileDialog,QLabel,QMessageBox,QPushButton
from admissions.identity import demo_pesel
from portable import DATA


def run(app,window,out):
    client=window.client
    suffix=str(time.time_ns())
    user=client.request('/register',{'email':'ui-files-'+suffix+'@example.com','password':'Gui-evidence-983!',
        'first_name':'Test','last_name':'Dokumentów','pesel':demo_pesel(198000),'phone':'123456789',
        'address':{'city':'Kraków','street':'Warszawska','building':'24','postal_code':'31-155'}})
    client.token=user['token']
    client.request('/action',{'action':'profile','first_name':'Test','last_name':'Dokumentów',
        'exams':[{'subject':'matematyka','level':'basic','value':'90'},
                 {'subject':'informatyka','level':'extended','value':'80'}]})
    client.request('/profile/photo',{},file=DATA/'demo-dokumenty/zdjecie-demo.png')
    window.data=client.request('/workspace')
    window.offers=client.request('/catalog')
    window.threshold_rows=client.request('/thresholds')
    window.current='profile'; window.shell()
    window.page_transition.finish()
    files=DATA/'gui-upload-test'; files.mkdir(exist_ok=True)
    for name,width in [('swiadectwo-ui.pdf',72),('swiadectwo-poprawione-ui.pdf',73),('przelew-ui.pdf',74)]:
        writer=PdfWriter(); writer.add_blank_page(width=width,height=72)
        with (files/name).open('wb') as stream: writer.write(stream)

    def pump(predicate,seconds=15):
        deadline=time.monotonic()+seconds
        while not predicate() and time.monotonic()<deadline:
            app.processEvents(); time.sleep(.015)
        assert predicate(),'GUI document operation did not finish.'

    upload=next(b for b in window.page.findChildren(QPushButton)
                if b.accessibleName()=='Dodaj plik… Świadectwo maturalne')
    with patch.object(QFileDialog,'getOpenFileName',return_value=(str(files/'swiadectwo-ui.pdf'),'PDF')):
        upload.click()
    pump(lambda:not window.busy)
    assert any('swiadectwo-ui.pdf' in l.text() for l in window.page.findChildren(QLabel))
    source=next(d for d in client.request('/workspace')['profile']['documents'] if d['kind']=='education')
    assert source['name']=='swiadectwo-ui.pdf'

    offer=next(o for o in window.offers if o['name']=='Informatyka' and o['degree']=='I' and o['mode']=='S')
    created=client.request('/action',{'action':'create_application','offer_id':offer['id']})
    window.data=client.request('/workspace')
    current=next(a for a in window.data['applications'] if a['id']==created['id'])
    state={'phase':'fee','finished':False}; errors=[]
    timer=QTimer(); timer.setInterval(60); deadline=time.monotonic()+20

    def inspect():
        modal=QApplication.activeModalWidget()
        try:
            if time.monotonic()>deadline:
                raise AssertionError('Upload dialog flow timed out: '+state['phase'])
            if isinstance(modal,QMessageBox):
                raise AssertionError('Unexpected document message: '+modal.text())
            if window.busy: return
            if state['phase']=='submitting' and modal is None:
                state['finished']=True; timer.stop(); return
            if modal is None: return
            texts=[l.text() for l in modal.findChildren(QLabel)]
            if state['phase']=='fee':
                assert any('swiadectwo-ui.pdf' in t for t in texts)
                assert 'Podpięto z profilu' in texts
                preview = next(button for button in modal.findChildren(QPushButton)
                               if button.accessibleName() == 'Podgląd: Świadectwo maturalne')
                add_payment = modal.findChild(QPushButton,'application-upload-fee')
                replace = modal.findChild(QPushButton,'application-upload-education')
                assert preview.size() == add_payment.size() == replace.size()
                state['phase']='replacement'
                add_payment.click()
            elif state['phase']=='replacement' and any('przelew-ui.pdf' in t for t in texts):
                state['phase']='submit'
                modal.findChild(QPushButton,'application-upload-education').click()
            elif state['phase']=='submit' and any('swiadectwo-poprawione-ui.pdf' in t for t in texts):
                assert any('przelew-ui.pdf' in t for t in texts)
                modal.grab().save(str(Path(out)/'dokumenty-szkic-podglad.png'))
                state['phase']='submitting'
                next(b for b in modal.findChildren(QPushButton) if b.text()=='Złóż zgłoszenie').click()
        except Exception as error:
            errors.append(str(error)); timer.stop()
            if modal: modal.reject()

    timer.timeout.connect(inspect); timer.start()
    with patch.object(QFileDialog,'getOpenFileName',side_effect=[
        (str(files/'przelew-ui.pdf'),'PDF'),(str(files/'swiadectwo-poprawione-ui.pdf'),'PDF')]):
        window.application_dialog(current)
        pump(lambda:state['finished'] or bool(errors),seconds=22)
    timer.stop()
    assert not errors,errors
    sent=next(a for a in client.request('/workspace')['applications'] if a['id']==created['id'])
    assert sent['status']=='submitted'
    education=next(d for d in sent['documents'] if d['kind']=='education')
    assert education['name']=='swiadectwo-poprawione-ui.pdf'
    assert next(d for d in sent['documents'] if d['kind']=='fee')['name']=='przelew-ui.pdf'
    assert client.request('/document/'+str(education['id']),binary=True).startswith(b'%PDF-')
    client.request('/action',{'action':'withdraw','id':created['id']})
    client.request('/action',{'action':'logout'})
    client.token=''; window.guest()
    pump(lambda:not window.busy)
    print('Qt document upload, replacement, preview and submission: PASS',flush=True)
