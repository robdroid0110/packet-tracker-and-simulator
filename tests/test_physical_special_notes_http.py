"""Live HTTP contract tests for §22, with autosaves isolated in a temp directory."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from netsim.model import NetworkLab
from netsim.cli import CommandProcessor


class PhysicalSpecialNotesHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        cls.app=server
        cls.temp=tempfile.TemporaryDirectory(prefix='packet-tracker-section22-')
        cls.previous=(server.LAB,server.PROC,server.STATE,server.BACKUPS)
        server.LAB=NetworkLab();server.PROC=CommandProcessor(server.LAB)
        server.STATE=Path(cls.temp.name)/'autosave.json'
        server.BACKUPS=Path(cls.temp.name)/'backups'
        class Quiet(server.Handler):
            def log_message(self,*args):pass
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),Quiet)
        cls.port=cls.http.server_address[1]
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join(timeout=5)
        cls.app.LAB,cls.app.PROC,cls.app.STATE,cls.app.BACKUPS=cls.previous
        cls.temp.cleanup()

    def setUp(self):
        with self.app.LOCK:
            self.app.LAB=NetworkLab();self.app.PROC=CommandProcessor(self.app.LAB)
            self.app.STATE.unlink(missing_ok=True)

    def request(self,path,body=None):
        request=Request(f'http://127.0.0.1:{self.port}'+path,
                        data=None if body is None else json.dumps(body).encode(),
                        headers={'content-type':'application/json'})
        try:
            with urlopen(request,timeout=5) as response:return response.status,json.load(response)
        except HTTPError as error:
            try:return error.code,json.load(error)
            finally:error.close()

    def action(self,**body):return self.request('/api/physical-workspace/action',body)

    def test_discover_schema_grid_geometry_and_preview(self):
        status,schema=self.request('/api/physical-workspace/schema')
        self.assertEqual(status,200);self.assertEqual(schema['version'],2)
        for action in ('set_grid','delete_location'):
            self.assertIn(action,schema['write']['actions'])
        status,registry=self.request('/api/capabilities')
        self.assertEqual(status,200)
        ids={action['id'] for action in registry['actions']}
        self.assertIn('workspace.physical_grid',ids);self.assertIn('workspace.physical_delete',ids)
        status,view=self.request('/api/physical-workspace?location=building0')
        self.assertEqual(status,200)
        self.assertEqual(view['grid']['spacing_x_px'],50)
        self.assertEqual(set(view['grid_profiles']),{'intercity','city','building','generic'})
        self.assertEqual(view['delete_preview']['removed_locations'],['building0','closet0'])
        self.assertFalse(self.app.STATE.exists())  # GET is read-only.
        status,root=self.request('/api/physical-workspace')
        self.assertEqual(status,200);self.assertIsNone(root['delete_preview'])

    def test_grid_edit_autosave_history_and_legacy_roundtrip(self):
        status,result=self.action(action='set_grid',container_type='building',enabled=False,
                                  spacing_m=2.5,color='#abc123',view_location='building0')
        self.assertEqual(status,200,result)
        self.assertFalse(result['workspace']['grid']['enabled'])
        self.assertEqual(result['workspace']['grid']['spacing_x_px'],25)
        saved=NetworkLab();saved.load(str(self.app.STATE))
        self.assertEqual(saved.physical_grids['building'],result['state']['physical_grids']['building'])
        status,undo=self.action(action='undo',view_location='building0')
        self.assertEqual(status,200);self.assertTrue(undo['workspace']['grid']['enabled'])
        status,redo=self.action(action='redo',view_location='building0')
        self.assertEqual(status,200);self.assertFalse(redo['workspace']['grid']['enabled'])

    def test_delete_viewing_current_location_returns_usable_projection(self):
        status,pc=self.action(action='add_device',model='pc',name='PC1',location='closet0',x=100,y=100)
        self.assertEqual(status,200,pc)
        status,result=self.action(action='delete_location',location='closet0',view_location='closet0')
        self.assertEqual(status,200,result)
        self.assertEqual(result['state']['device_locations']['PC1'],'building0')
        self.assertEqual(result['workspace']['location'],'intercity')
        status,missing=self.request('/api/physical-workspace?location=closet0')
        self.assertEqual(status,400);self.assertFalse(missing['ok'])
        status,undo=self.action(action='undo')
        self.assertEqual(status,200)
        self.assertEqual(undo['state']['device_locations']['PC1'],'closet0')
        saved=NetworkLab();saved.load(str(self.app.STATE))
        self.assertIn('closet0',saved.physical_locations)

    def test_bad_actions_do_not_change_state_or_saved_bytes(self):
        self.action(action='set_grid',container_type='city',enabled=True,spacing_m=100,color='#123456')
        before=self.app.LAB.to_dict();saved=self.app.STATE.read_bytes()
        cases=[{'action':'set_grid','container_type':'city','enabled':'true','spacing_m':100,'color':'#123456'},
               {'action':'set_grid','container_type':'city','enabled':True,'spacing_m':True,'color':'#123456'},
               {'action':'set_grid','container_type':[],'enabled':True,'spacing_m':1,'color':'#123456'},
               {'action':'set_grid','container_type':'city','enabled':True,'spacing_m':1,'color':'red'},
               {'action':'delete_location','location':'intercity'},
               {'action':'delete_location','location':'unknown'},
               {'action':'delete_location','location':False},
               {'action':'delete_location','location':'city0','view_location':'unknown'},
               {'action':'delete_location','location':'city0','view_location':[]},
               {'action':'delete_location'}]
        for body in cases:
            with self.subTest(body=body):
                status,result=self.request('/api/physical-workspace/action',body)
                self.assertEqual(status,400,result);self.assertFalse(result['ok'])
                self.assertEqual(self.app.LAB.to_dict(),before)
                self.assertEqual(self.app.STATE.read_bytes(),saved)

    def test_delete_then_recreate_via_authoritative_command_endpoint(self):
        status,result=self.action(action='delete_location',location='city0')
        self.assertEqual(status,200,result)
        for command in ('add router R1','add pc PC1','connect PC1 eth0 R1 g0/0',
                        'ip PC1 eth0 10.10.10.2/24','ip R1 g0/0 10.10.10.1/24',
                        'ping PC1 10.10.10.1'):
            status,result=self.request('/api/command',{'command':command})
            self.assertEqual(status,200,result);self.assertTrue(result['ok'])
        self.assertIn('PING success',result['output'])
        status,tree=self.request('/api/physical-workspace/tree')
        self.assertEqual(status,200);self.assertEqual(tree['device_count'],2)
        self.assertEqual(tree['tree']['children'],[])
        self.assertEqual(len(tree['tree']['devices']),2)
        saved=NetworkLab();saved.load(str(self.app.STATE))
        self.assertEqual(saved.device_locations,{'R1':'intercity','PC1':'intercity'})


if __name__=='__main__':unittest.main()
