"""Isolated real HTTP tests for workspace tool and logical artwork contracts."""
import json
from pathlib import Path
import unittest
import test_physical_special_notes_http as isolated
from test_visual_customization import png,b64

class WorkspaceToolsHTTPTests(unittest.TestCase):
    setUpClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["setUpClass"]
    tearDownClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["tearDownClass"]
    setUp=isolated.PhysicalSpecialNotesHTTPTests.setUp
    request=isolated.PhysicalSpecialNotesHTTPTests.request
    # Reuse the isolated server fixture; inherited Section 22 tests also regress
    # compatibility with the extended saved-lab format.
    def tool(self,**body):return self.request('/api/workspace-tools/action',body)
    def test_template_crud_and_history(self):
        self.request('/api/command',{'command':'add pc A'})
        status,data=self.tool(action='template_capture',name='Host',kind='device',source='A')
        self.assertEqual(status,200,data)
        template=data['state']['workspace_tools']['templates']['Host']
        status,data=self.tool(action='template_import',name='Other',template=template)
        self.assertEqual(status,200,data)
        status,data=self.tool(action='template_instantiate',name='Other',location='building0',x=300,y=240)
        self.assertEqual(status,200,data);self.assertEqual(len(data['state']['devices']),2)
        status,data=self.tool(action='undo');self.assertEqual(status,200);self.assertEqual(len(data['state']['devices']),1)
        status,data=self.tool(action='redo');self.assertEqual(status,200);self.assertEqual(len(data['state']['devices']),2)
        status,data=self.tool(action='template_delete',name='Host');self.assertEqual(status,200)
        from netsim.model import NetworkLab
        lab=NetworkLab();lab.load(str(self.app.STATE));self.assertIn('Other',lab.workspace_tools['templates'])
    def test_viewport_accessibility_schema_and_atomic_bad_requests(self):
        code,data=self.request('/api/workspace-tools/schema');self.assertEqual(code,200);self.assertIn('template_capture',data['actions'])
        for action in ({'action':'viewport','visible':True,'mode':'workspace','x':1200,'y':900},
                       {'action':'accessibility','contrast':'high','scale':2}):
            code,data=self.request('/api/workspace-tools/action',action);self.assertEqual(code,200,data)
        code,read=self.request('/api/workspace-tools?workspace=physical&location=city0&mode=workspace')
        self.assertEqual(code,200);self.assertEqual(read['settings']['accessibility']['scale'],2)
        before=self.app.LAB.to_dict();raw=self.app.STATE.read_bytes()
        for action in ({'action':'viewport','visible':1},{'action':'template_capture','kind':'device','source':'no','name':'No'},
                       {'action':'template_import','name':'No','template':{}},{'action':'template_delete','name':'no'},
                       {'action':'accessibility','scale':100}):
            code,data=self.request('/api/workspace-tools/action',action);self.assertEqual(code,400,data)
            self.assertEqual(self.app.LAB.to_dict(),before);self.assertEqual(self.app.STATE.read_bytes(),raw)
        code,data=self.request('/api/workspace-tools?workspace=logical&location=missing');self.assertEqual(code,400)
    def test_logical_artwork_through_existing_visual_api(self):
        self.request('/api/command',{'command':'cluster add Room none'})
        code,image=self.request('/api/visuals/action',{'action':'upload_image','mime':'image/png','data_base64':b64(png())})
        self.assertEqual(code,200,image)
        asset=next(iter(image['state']['visual_assets']))
        for body in ({'action':'set_background','location':'logical:root','asset_id':asset,'tiled':True,'color':'#123456'},
                     {'action':'set_cluster_icon','cluster':'Cluster0','asset_id':asset}):
            code,result=self.request('/api/visuals/action',body);self.assertEqual(code,200,result)
        code,view=self.request('/api/visuals');self.assertEqual(view['cluster_icons']['Cluster0'],asset)
        code,result=self.request('/api/visuals/action',{'action':'delete_image','asset_id':asset});self.assertEqual(code,400)

    def test_diagram_preview_actions_stale_errors_and_persistence(self):
        from urllib.parse import quote
        from netsim.model import NetworkLab
        self.request('/api/command', {'command':'add router R1 500 400'})
        self.request('/api/command', {'command':'add pc Host 750 400'})
        raw=self.app.STATE.read_bytes()
        code,plan=self.request('/api/topology-layout')
        self.assertEqual(code,200,plan)
        self.assertEqual(raw,self.app.STATE.read_bytes())
        code,result=self.tool(action='layout_apply',names=plan['names'],signature=plan['signature'])
        self.assertEqual(code,200,result)
        self.assertEqual(result['state']['devices']['R1']['x'],plan['positions']['R1']['x'])
        self.tool(action='undo')
        self.assertEqual(self.app.LAB.devices['R1'].x,500)
        self.request('/api/command',{'command':'move R1 501 400'})
        code,result=self.tool(action='layout_apply',names=plan['names'],signature=plan['signature'])
        self.assertEqual(code,400,result)
        self.assertEqual(self.app.LAB.devices['R1'].x,501)
        for query in ['not-json',quote('["Missing"]'),quote('["R1","R1"]')]:
            code,result=self.request('/api/topology-layout?names='+query)
            self.assertEqual(code,400,result)
        for body in [dict(action='diagram_group',name='Site',members=['R1','Host']),
                     dict(action='diagram_collapse',name='Site',collapsed=True),
                     dict(action='diagram_preferences',labels='none',semantic_zoom=False)]:
            code,result=self.tool(**body);self.assertEqual(code,200,result)
        loaded=NetworkLab();loaded.load(str(self.app.STATE))
        self.assertTrue(loaded.workspace_tools['diagram']['groups']['Site']['collapsed'])
        self.assertEqual(loaded.workspace_tools['diagram']['labels'],'none')
        code,read=self.request('/api/workspace-tools')
        self.assertEqual(read['settings']['diagram'],loaded.workspace_tools['diagram'])
        code,schema=self.request('/api/workspace-tools/schema')
        self.assertIn('layout_preview',schema)
