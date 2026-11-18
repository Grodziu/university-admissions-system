"""Concurrent real HTTPS clients against an isolated demonstration server."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import os
import sys
import time
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from portable import DATA,ROOT,config
from networking import connection_profile,import_profile
from desktop.client import Client,ApiError

port=int(os.environ.get('PK_TEST_PORT','58433'))
profile=DATA/'test-connection.json'
profile.write_text(json.dumps(connection_profile('127.0.0.1',port)),'utf-8')
url,trust,public=import_profile(profile)
assert not any(k in public for k in ['password','owner_password','app_password','secret'])
try:
    requests.get(url+'/health',timeout=5)
    raise AssertionError('Private CA was unexpectedly trusted without pairing')
except requests.exceptions.SSLError:
    pass
def login(role):
    c=Client(url,verify=trust)
    c.token=c.request('/login',{'email':role+'@demo.local','password':config()['demo_password']})['token']
    return c
with ThreadPoolExecutor(max_workers=12) as pool:
    clients=list(pool.map(login,['kandydat']*4+['komisja']*4+['admin']*4))
candidate,commission,admin=clients[0],clients[4],clients[8]
catalog=admin.request('/catalog')
offer=next(o for o in catalog if o['name']=='Informatyka' and o['degree']=='I' and o['mode']=='N')
with ThreadPoolExecutor(max_workers=4) as pool:
    ids=list(pool.map(lambda c:c.request('/action',{'action':'create_application','offer_id':offer['id']})['id'],clients[:4]))
assert len(set(ids))==1
campaign=admin.request('/workspace')['campaign']
admin.request('/action',{'action':'demo_scenario','campaign_id':campaign['id'],'scenario':'ready'})
old=candidate.request('/state')['revision']
cutoff=next(r['application_end'] for r in campaign['rounds'] if r['degree']=='I' and r['number']==1)
admin.request('/action',{'action':'clock','campaign_id':campaign['id'],'target':cutoff})
with ThreadPoolExecutor(max_workers=12) as pool:
    states=list(pool.map(lambda c:c.request('/state'),clients))
assert all(s['revision']>old and s['now']==cutoff for s in states)
try:
    candidate.request('/action',{'action':'submit','id':ids[0]})
    raise AssertionError('Stale form bypassed server deadline')
except ApiError as e:
    assert 'Termin' in str(e) or 'zakończ' in str(e) or 'zamknię' in str(e)
target=next(o for o in catalog if o['name']=='Informatyka' and o['degree']=='I' and o['mode']=='S')
with ThreadPoolExecutor(max_workers=4) as pool:
    pubs=list(pool.map(lambda c:c.request('/action',{'action':'publish','offer_id':target['id']}),clients[4:8]))
assert len({p['id'] for p in pubs})==1
assert len(commission.request(f"/publications/{target['id']}"))==1
preview=commission.request(f"/ranking/{target['id']}")
assert preview['overflow']>0
admin.request('/action',{'action':'demo_scenario','campaign_id':campaign['id'],'scenario':'final'})
anna=next(a for a in candidate.request('/workspace')['applications'] if a['offer_id']==target['id'])
assert anna['can_oath']
candidate.request('/action',{'action':'oath','id':anna['id'],'accepted':True})
assert next(a for a in candidate.request('/workspace')['applications'] if a['id']==anna['id'])['sworn_at']
old_count=len(admin.request('/workspace')['applications'])
with ThreadPoolExecutor(max_workers=2) as pool:
    editions=list(pool.map(lambda c:c.request('/action',{'action':'restart','campaign_id':campaign['id']})['campaign_id'],clients[8:10]))
assert len(set(editions))==1
assert not admin.request('/workspace')['applications']
assert len(admin.request(f"/workspace?campaign_id={campaign['id']}")['applications'])==old_count
result={'result':'PASS','simultaneous_https_clients':12,'private_ca_verified':True,'shared_clock':True,'stale_submission_blocked':True,
        'concurrent_publication_once':True,'tie_overflow':preview['overflow'],'oath_after_final':True,'new_edition_retains_history':True,
        'network_scope':'loopback, separate HTTP clients; second physical laptop still requires acceptance'}
(ROOT/'tmp/network-results.json').write_text(json.dumps(result,indent=2),'utf-8')
print(json.dumps(result))
