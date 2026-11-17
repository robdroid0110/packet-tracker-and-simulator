"""Section 22 behaviour: calibrated grids and lossless container extraction."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from netsim.model import NetworkLab, LabError
from netsim.cli import CommandProcessor
from netsim.physical_grid import view as grid_view, defaults
from netsim.physical_workspace import physical_view, physical_tree, action_command
from netsim.cable_manipulation import add_bend, set_color, group_bends


class PhysicalSpecialNotesTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab()
        self.cp=CommandProcessor(self.lab)

    def cmd(self,command):
        result=self.cp.execute(command)
        self.assertFalse(result.startswith('ERROR:'),result)
        return result

    def roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'lab.json'
            self.lab.save(str(file))
            loaded=NetworkLab();loaded.load(str(file))
            return loaded

    def test_metric_grid_scale_and_dimensions(self):
        self.cmd('physical grid city on 125 #124AbC')
        grid=physical_view(self.lab,'city0')['grid']
        self.assertEqual(grid['spacing_m'],125)
        self.assertEqual(grid['spacing_x_px'],25)
        self.assertEqual(grid['spacing_y_px'],17.5)
        self.assertEqual(grid['color'],'#124abc')
        self.cmd('physical dimensions city0 2500 1250 500')
        new=grid_view(self.lab,'city0')
        self.assertEqual(new['spacing_x_px'],50)
        self.assertEqual(new['spacing_y_px'],70)

    def test_type_profiles_are_shared_and_independent(self):
        other=self.lab.add_physical_location('city','Other city')
        self.cmd('physical grid city off 50 #010203')
        a,b=grid_view(self.lab,'city0'),grid_view(self.lab,other)
        self.assertFalse(a['enabled']);self.assertFalse(b['enabled'])
        self.assertEqual(a['spacing_m'],b['spacing_m'])
        self.assertTrue(grid_view(self.lab,'building0')['enabled'])
        self.assertEqual(grid_view(self.lab,'intercity')['spacing_x_px'],25)
        box=self.lab.add_physical_location('generic','Box','closet0')
        self.assertTrue(grid_view(self.lab,box)['supported'])
        self.assertFalse(grid_view(self.lab,'closet0')['supported'])
        panel=self.lab.add_physical_location('icp','Panel','closet0')
        self.assertFalse(grid_view(self.lab,panel)['supported'])

    def test_grid_has_no_network_or_placement_side_effects(self):
        self.cmd('add pc A');self.cmd('add pc B')
        self.cmd('connect A eth0 B eth0');self.cmd('ip A eth0 10.0.0.1/24');self.cmd('ip B eth0 10.0.0.2/24')
        before=self.lab.to_dict()
        self.cmd('physical grid building on 0.01 #abcdef')
        after=self.lab.to_dict();before.pop('physical_grids');after.pop('physical_grids')
        self.assertEqual(before,after)
        self.assertIn('PING success',self.cmd('ping A 10.0.0.2'))

    def test_grid_and_deletion_undo_redo(self):
        baseline=self.lab.to_dict()
        self.cmd('physical grid building off 7.5 #112233')
        changed=self.lab.to_dict()
        self.cmd('undo');self.assertEqual(self.lab.to_dict(),baseline)
        self.cmd('redo');self.assertEqual(self.lab.to_dict(),changed)
        self.cmd('add router R1');self.cmd('power R1 off');self.cmd('physical shelf-add closet0')
        self.cmd('physical mount R1 shelf 0')
        before=self.lab.to_dict()
        self.cmd('physical delete closet0')
        after=self.lab.to_dict()
        self.assertEqual(self.lab.physical_device_details['R1']['surface'],'floor')
        self.assertEqual(self.lab.device_locations['R1'],'building0')
        self.cmd('undo');self.assertEqual(self.lab.to_dict(),before)
        self.cmd('redo');self.assertEqual(self.lab.to_dict(),after)
        self.assertEqual(self.roundtrip().device_locations['R1'],'building0')

    def test_grid_validation_is_atomic(self):
        before=self.lab.to_dict()
        for command in ('physical grid closet on 10 #aabbcc',
                        'physical grid city yes 10 #aabbcc',
                        'physical grid city on nan #aabbcc',
                        'physical grid city on inf #aabbcc',
                        'physical grid city on 0 #aabbcc',
                        'physical grid city on 1000001 #aabbcc',
                        'physical grid city on 10 red'):
            with self.subTest(command=command):
                self.assertTrue(self.cp.execute(command).startswith('ERROR:'))
                self.assertEqual(self.lab.to_dict(),before)
        self.assertFalse(self.cp._undo_stack)

    def test_typed_validation(self):
        base={'action':'set_grid','container_type':'city','enabled':True,'spacing_m':1,'color':'#abcdef'}
        for change in ({'container_type':[]},{'enabled':'yes'},{'enabled':1},
                       {'spacing_m':True},{'spacing_m':float('nan')},{'color':'url(bad)'},
                       {'spacing_m':None}):
            with self.subTest(change=change),self.assertRaises(LabError):
                action_command({**base,**change})
        self.assertEqual(action_command(base),'physical grid city on 1.0 #abcdef')

    def test_saved_grid_roundtrip_and_legacy_defaults(self):
        self.cmd('physical grid generic off 2.75 #987654')
        self.assertEqual(self.roundtrip().physical_grids,self.lab.physical_grids)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'old.json';raw=self.lab.to_dict();raw.pop('physical_grids')
            path.write_text(json.dumps(raw));loaded=NetworkLab();loaded.load(str(path))
            self.assertEqual(loaded.physical_grids,defaults())
            for bad in (None,[],{'city':[]},{'nope':{}},{'city':{'enabled':True,'spacing_m':True,'color':'#abcdef'}}):
                raw['physical_grids']=bad;path.write_text(json.dumps(raw))
                with self.subTest(bad=bad),self.assertRaises(LabError):loaded.load(str(path))

    def test_delete_closet_then_building_preserves_live_ping(self):
        for command in ('add pc PC1','add router R1','connect PC1 eth0 R1 g0/0',
                        'ip PC1 eth0 192.0.2.2/24','ip R1 g0/0 192.0.2.1/24'):
            self.cmd(command)
        links=deepcopy(self.lab.links)
        self.assertIn('PING success',self.cmd('ping PC1 192.0.2.1'))
        # Learned ARP is expected to survive extraction as well.
        devices=deepcopy(self.lab.to_dict()['devices'])
        self.cmd('physical delete closet0')
        self.assertEqual(self.lab.device_locations['R1'],'building0')
        self.assertEqual(self.lab.physical_device_details['R1']['surface'],'floor')
        self.cmd('physical delete building0')
        self.assertEqual(self.lab.device_locations,{'PC1':'city0','R1':'city0'})
        self.assertEqual(self.lab.to_dict()['devices'],devices)
        self.assertEqual(self.lab.links,links)
        self.assertIn('PING success',self.cmd('ping PC1 192.0.2.1'))
        loaded=self.roundtrip()
        self.assertEqual(loaded.device_locations,self.lab.device_locations)
        self.assertTrue(loaded.link_operational(loaded.links[0]))

    def test_recursive_delete_cleans_furniture_panels_backgrounds(self):
        self.cmd('add router R1');self.cmd('add pc PC1')
        box=self.lab.add_physical_location('generic','Box','closet0')
        panel=self.lab.add_physical_location('icp','Panel',box)
        self.cmd(f'physical place PC1 {panel}')
        self.cmd('physical shelf-add closet0')
        self.lab.location_backgrounds={k:{'color':'#eeeeee','asset_id':None,'tiled':False}
                                      for k in ('building0','closet0',box,panel,'city0')}
        plan=self.lab.physical_delete_preview('building0')
        self.assertEqual(set(plan['removed_locations']),{'building0','closet0',box,panel})
        self.assertEqual(plan['extracted_devices'],['PC1','R1'])
        before=deepcopy(self.lab.__dict__)
        self.assertEqual(json.loads(self.cmd('physical delete-preview building0')),plan)
        self.assertEqual(self.lab.__dict__,before)
        self.cmd('physical delete building0')
        self.assertEqual(set(self.lab.physical_locations),{'city0'})
        self.assertEqual(self.lab.physical_shelves,{})
        self.assertEqual(self.lab.icp_panels,{})
        self.assertEqual(set(self.lab.location_backgrounds),{'city0'})
        for detail in self.lab.physical_device_details.values():
            self.assertEqual(detail['surface'],'floor');self.assertIsNone(detail['shelf'])
        self.assertEqual(physical_tree(self.lab)['device_count'],2)
        self.assertEqual(self.roundtrip().device_locations,self.lab.device_locations)

    def test_deletion_preserves_cable_bends_groups_and_colors(self):
        self.cmd('add pc A');self.cmd('add pc B');self.cmd('add router R1')
        self.cmd('connect A eth0 R1 g0/0');self.cmd('connect B eth0 R1 g0/1')
        first=add_bend(self.lab,'A','eth0',3000,2000)
        second=add_bend(self.lab,'B','eth0',3100,2100)
        group_bends(self.lab,'A','eth0',first,'B','eth0',second)
        set_color(self.lab,'A','eth0','#112233')
        routes=deepcopy(self.lab.cable_routes)
        self.cmd('physical delete city0')
        self.assertEqual(self.lab.cable_routes,routes)
        self.assertEqual(self.roundtrip().cable_routes,routes)
        self.assertTrue(self.lab.link_operational(self.lab.links[0]))

    def test_extraction_recalculates_opt_in_distance_effects(self):
        for command in ('add pc A','add pc B','physical place A closet0',
                        'physical place B closet0','physical device-position A 100 100',
                        'physical device-position B 110 100','connect A eth0 B eth0',
                        'physical cable-effects on'):
            self.cmd(command)
        self.assertTrue(self.lab.link_operational(self.lab.links[0]))
        self.cmd('physical delete building0')
        # Extraction onto a city map separates the devices by 550 metres.
        self.assertFalse(self.lab.link_operational(self.lab.links[0]))
        self.assertEqual(self.lab.link_status(self.lab.links[0])['reason'],'cable length exceeds 100m')
        self.cmd('undo')
        self.assertTrue(self.lab.link_operational(self.lab.links[0]))

    def test_200_device_extraction_retains_every_configuration(self):
        for index in range(200):
            name=f"PC{index}"
            self.lab.add_device('pc',name)
            self.lab.set_ip(name,'eth0',f'10.0.0.{index+1}/24')
            if index%2:self.lab.place_physical_device(name,'closet0')
        configs=deepcopy(self.lab.to_dict()['devices'])
        self.cmd('physical delete city0')
        self.assertEqual(len(self.lab.devices),200)
        self.assertEqual(set(self.lab.device_locations.values()),{'intercity'})
        self.assertEqual(self.lab.to_dict()['devices'],configs)
        loaded=self.roundtrip()
        self.assertEqual(len(physical_view(loaded,'intercity')['devices']),200)
        self.assertEqual(loaded.to_dict()['devices'],configs)

    def test_invalid_delete_has_no_side_effects(self):
        before=self.lab.to_dict()
        for location in ('intercity','missing'):
            self.assertTrue(self.cp.execute('physical delete '+location).startswith('ERROR:'))
            self.assertEqual(self.lab.to_dict(),before)
        self.assertFalse(self.cp._undo_stack)

    def test_delete_all_then_create_from_logical_and_physical(self):
        self.cmd('physical delete city0')
        self.assertEqual(self.lab.physical_locations,{})
        for kind in ('router','switch','pc','server','generic'):
            self.cmd('add '+kind+' '+kind)
            self.assertEqual(self.lab.device_locations[kind],'intercity')
        self.cmd('physical add-device pc PC2 100 100 intercity 250 250')
        self.assertEqual(self.lab.device_locations['PC2'],'intercity')
        self.assertEqual(physical_tree(self.lab)['device_count'],6)
        self.assertEqual(self.roundtrip().device_locations,self.lab.device_locations)
        self.cmd('physical add city NewCity')
        self.assertEqual(len(self.lab.physical_locations),1)
        self.cmd('reset');self.assertEqual(self.lab.physical_grids,defaults())
        self.assertIn('closet0',self.lab.physical_locations)


if __name__=='__main__':unittest.main()
