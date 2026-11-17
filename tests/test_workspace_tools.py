"""Sections 23–32: portable artwork/templates and authoritative navigation/settings."""
import base64,json,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from netsim.model import NetworkLab,LabError
from netsim.cli import CommandProcessor
from netsim.workspace_tools import command,view,validate,defaults
from netsim.visual_customization import add_asset,set_background,set_cluster_icon,discard_asset,image_info
from test_visual_customization import png,b64

class WorkspaceToolsTests(unittest.TestCase):
    def setUp(self):self.lab=NetworkLab();self.cp=CommandProcessor(self.lab)
    def action(self,**body):return command(self.lab,body)
    def load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'lab.json';self.lab.save(str(path));other=NetworkLab();other.load(str(path));return other
    def test_artwork_independent_scopes_cleanup_and_portability(self):
        self.lab.add_device('pc','A');cluster=self.lab.add_cluster('Room',['A'])
        asset=add_asset(self.lab,'image/png',b64(png()))
        for loc in ('logical:root','logical:'+cluster,'building0'):set_background(self.lab,loc,asset,True,'#123456')
        set_cluster_icon(self.lab,cluster,asset)
        loaded=self.load();self.assertEqual(loaded.cluster_icons,self.lab.cluster_icons)
        self.assertEqual(loaded.location_backgrounds,self.lab.location_backgrounds)
        with self.assertRaises(LabError):discard_asset(self.lab,asset)
        self.lab.delete_cluster(cluster)
        self.assertNotIn(cluster,self.lab.cluster_icons);self.assertNotIn('logical:'+cluster,self.lab.location_backgrounds)
        self.assertIn('logical:root',self.lab.location_backgrounds)
    def test_gif_and_corrupt_gif(self):
        data=base64.b64decode('R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==')
        self.assertEqual(image_info('image/gif',b64(data))[1:3],(1,1))
        for raw in (data[:-1],data+b'extra',b'GIF89a',data[:20]):
            with self.assertRaises(LabError):image_info('image/gif',b64(raw))
    def test_viewport_scoping_modes_and_validation(self):
        self.lab.add_device('pc','A',500,400);self.lab.add_device('pc','B',2000,1500)
        cluster=self.lab.add_cluster('Hidden',['B'])
        root=view(self.lab);self.assertEqual({i['id'] for i in root['items']},{'A',cluster})
        scoped=view(self.lab,'logical',cluster);self.assertEqual([i['id'] for i in scoped['items']],['B'])
        self.assertEqual(view(self.lab,'physical','building0')['items'][0]['type'],'device')
        self.lab.add_device('generic','AP1',model='AccessPoint-PT')
        self.assertEqual(view(self.lab,'physical','building0')['radios'][0]['radius_m'],140)
        self.action(action='viewport',visible=True,mode='workspace',x=1000,y=2000)
        self.assertEqual(self.load().workspace_tools,self.lab.workspace_tools)
        for change in ({'x':float('nan')},{'x':True},{'mode':[]},{'location':'missing'},{'visible':'true'}):
            before=deepcopy(self.lab.__dict__)
            with self.assertRaises((LabError,TypeError)):self.action(action='viewport',**change)
            self.assertEqual(before,self.lab.__dict__)
    def test_accessibility_save_undo_and_negative(self):
        import shlex
        cmd='workspace-tool '+shlex.quote(json.dumps({'action':'accessibility','contrast':'high','scale':1.8}))
        self.assertFalse(self.cp.execute(cmd).startswith('ERROR:'))
        self.assertEqual(self.load().workspace_tools['accessibility'],{'contrast':'high','scale':1.8})
        self.cp.execute('undo');self.assertEqual(self.lab.workspace_tools['accessibility'],defaults()['accessibility'])
        self.cp.execute('redo');self.assertEqual(self.lab.workspace_tools['accessibility']['scale'],1.8)
        for change in ({'scale':False},{'scale':9},{'contrast':'blue'},{'extra':1}):
            before=self.lab.to_dict()
            with self.assertRaises(LabError):self.action(action='accessibility',**change)
            self.assertEqual(before,self.lab.to_dict())
    def test_device_template_survives_source_removal_and_fresh_macs(self):
        self.lab.add_device('router','R1');self.lab.set_ip('R1','g0/0','192.0.2.1/24')
        self.lab.set_power('R1',False);self.lab.set_module('R1','slot0','PT-ETH-1')
        original=self.lab.devices['R1'].interfaces['g0/0'].mac
        self.action(action='template_capture',name='Router',kind='device',source='R1',description='Modular router')
        self.lab.remove_device('R1');self.action(action='template_instantiate',name='Router',location='closet0')
        router=next(iter(self.lab.devices.values()))
        self.assertEqual(router.modules,{'slot0':'PT-ETH-1'});self.assertEqual(router.interfaces['g0/0'].ip,'192.0.2.1/24')
        self.assertNotEqual(router.interfaces['g0/0'].mac,original)
        self.assertEqual(self.load().workspace_tools['templates'],self.lab.workspace_tools['templates'])
    def test_cluster_template_closure_internal_links_and_repeat_instances(self):
        for name in ('A','B','Outside'):self.lab.add_device('router',name)
        parent=self.lab.add_cluster('Parent',['A']);child=self.lab.add_cluster('Child',['B'],parent)
        self.lab.connect('A','g0/0','B','g0/0');self.lab.connect('A','g0/1','Outside','g0/0')
        self.action(action='template_capture',name='Group',kind='cluster',source=parent)
        template=self.lab.workspace_tools['templates']['Group']
        self.assertEqual(len(template['lab']['links']),1)
        self.assertEqual(set(template['lab']['devices']),{'A','B'})
        for _ in range(2):self.action(action='template_instantiate',name='Group')
        self.assertEqual(len(self.lab.devices),7);self.assertEqual(len(self.lab.links),4);self.assertEqual(len(self.lab.clusters),6)
        self.load()
    def test_physical_template_preserves_subtree_shelves_and_images(self):
        self.lab.add_device('router','R1');self.lab.set_power('R1',False)
        self.lab.physical_shelf_add('closet0');self.lab.physical_mount_device('R1','shelf',0)
        self.action(action='template_capture',name='Closet',kind='physical',source='building0')
        self.action(action='template_instantiate',name='Closet',location='city0')
        self.assertEqual(len(self.lab.devices),2)
        copy=next(n for n in self.lab.devices if n!='R1')
        self.assertEqual(self.lab.physical_device_details[copy]['surface'],'shelf')
        self.assertEqual(self.lab.physical_shelves[self.lab.device_locations[copy]],1)
        self.load()
        before=self.lab.to_dict()
        with self.assertRaises(LabError):self.action(action='template_instantiate',name='Closet',location='closet0')
        self.assertEqual(before,self.lab.to_dict())
    def test_physical_template_translates_cable_routes(self):
        from netsim.cable_manipulation import add_bend
        from netsim.physical_distance import device_world_position,cable_length
        for name in ('A','B'):
            self.lab.add_device('pc',name);self.lab.place_physical_device(name,'closet0')
        self.lab.physical_device_position('A',100,100);self.lab.physical_device_position('B',200,100)
        self.lab.connect('A','eth0','B','eth0')
        point=device_world_position(self.lab,'A');add_bend(self.lab,'A','eth0',point['x_m']+1,point['y_m']+2)
        original=cable_length(self.lab,self.lab.links[0])['total_length_m']
        self.action(action='template_capture',name='Cabled closet',kind='physical',source='closet0')
        other=self.lab.add_physical_location('building','Other building','city0')
        self.lab.move_physical_location(other,500,400)
        self.action(action='template_instantiate',name='Cabled closet',location=other)
        self.assertAlmostEqual(cable_length(self.lab,self.lab.links[-1])['total_length_m'],original,places=4)
        self.load()

    def test_template_export_import_invalid_and_delete_undo(self):
        self.lab.add_device('pc','A');self.action(action='template_capture',name='Host',kind='device',source='A')
        exported=deepcopy(self.lab.workspace_tools['templates']['Host'])
        self.action(action='template_import',name='Imported',template=exported)
        self.action(action='template_delete',name='Host');self.assertNotIn('Host',self.lab.workspace_tools['templates'])
        exported['lab']['workspace_tools']=defaults()
        before=self.lab.to_dict()
        with self.assertRaises(LabError):self.action(action='template_import',name='Invalid',template=exported)
        self.assertEqual(before,self.lab.to_dict())
    def test_200_device_template(self):
        for i in range(200):self.lab.add_device('pc','PC'+str(i))
        group=self.lab.add_cluster('Large',list(self.lab.devices))
        self.action(action='template_capture',name='Large',kind='cluster',source=group)
        self.action(action='template_instantiate',name='Large')
        self.assertEqual(len(self.lab.devices),400);self.load()

if __name__=='__main__':unittest.main()
