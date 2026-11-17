"""Authoritative workspace navigation, portable templates and accessibility settings."""
from copy import deepcopy
import json, math, tempfile
from pathlib import Path
from .model import LabError, NetworkLab, _mac

def defaults():
    from .topology_presentation import defaults as diagram_defaults
    return {'viewport':{'visible':False,'mode':'contents','workspace':'logical','location':'root','x':0.0,'y':0.0},
            'accessibility':{'contrast':'auto','scale':1.0},'templates':{},'diagram':diagram_defaults()}

def number(value,low,high):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
        raise LabError(f'number must be finite in {low}..{high}')
    return float(value)

def read_lab(data):
    with tempfile.TemporaryDirectory(prefix='pt-template-') as folder:
        path=Path(folder)/'lab.json';path.write_text(json.dumps(data))
        lab=NetworkLab();lab.load(str(path));return lab

def validate(raw):
    if not isinstance(raw,dict) or set(raw)-set(defaults()):raise LabError('invalid workspace tools state')
    state=defaults()
    if 'viewport' in raw:
        v=raw['viewport']
        if not isinstance(v,dict) or set(v)!=set(state['viewport']):raise LabError('invalid viewport')
        if not isinstance(v['visible'],bool) or v['mode'] not in ('contents','workspace') or v['workspace'] not in ('logical','physical') or not isinstance(v['location'],str):raise LabError('invalid viewport settings')
        state['viewport']={**v,'x':number(v['x'],0,10000),'y':number(v['y'],0,10000)}
    if 'accessibility' in raw:
        a=raw['accessibility']
        if not isinstance(a,dict) or set(a)!={'contrast','scale'} or a['contrast'] not in ('auto','high','normal'):raise LabError('invalid accessibility settings')
        state['accessibility']={'contrast':a['contrast'],'scale':number(a['scale'],1,2)}
    from .topology_presentation import validate as validate_diagram
    state['diagram']=validate_diagram(raw.get('diagram',{}))
    templates=raw.get('templates',{})
    if not isinstance(templates,dict) or len(templates)>40:raise LabError('maximum 40 templates')
    if len(json.dumps(templates))>16_000_000:raise LabError('template library exceeds 16MB')
    for key,t in templates.items():
        if not isinstance(key,str) or not key or len(key)>64 or not isinstance(t,dict) or t.get('kind') not in ('device','cluster','physical') or not isinstance(t.get('description'),str) or len(t['description'])>500:raise LabError('invalid template')
        data=t.get('lab')
        if not isinstance(data,dict) or data.get('workspace_tools'):raise LabError('template must not contain nested libraries')
        src=read_lab(data)
        origin=t.get('origin_m')
        if origin is not None:
            if not isinstance(origin,list) or len(origin)!=2:raise LabError('invalid template origin')
            for value in origin:number(value,-10000000,10000000)
        if len(src.devices)>200:raise LabError('template supports at most 200 devices')
        if t['kind']=='device' and (set(src.devices)!={t.get('root')} or src.clusters or src.physical_locations):raise LabError('device template must contain one device')
        root=t.get('root')
        if t['kind']=='device':src._device(root)
        elif t['kind']=='cluster' and root not in src.clusters:raise LabError('missing template cluster')
        elif t['kind']=='physical':src._physical_location(root)
        if t['kind']=='cluster':
            if descendants(src.clusters,root)!=set(src.clusters) or src.physical_locations:raise LabError('template contains unrelated containers')
            if {n for c in src.clusters.values() for n in c['devices']}!=set(src.devices):raise LabError('template contains unrelated devices')
        if t['kind']=='physical' and (descendants(src.physical_locations,root)!=set(src.physical_locations) or src.clusters or any(loc not in src.physical_locations for loc in src.device_locations.values())):raise LabError('template contains unrelated locations')
    state['templates']=deepcopy(templates)
    return state

def descendants(items,root):
    selected={root}
    while True:
        more={key for key,item in items.items() if item['parent'] in selected}
        if more<=selected:return selected
        selected|=more

def capture(lab,body):
    kind=body.get('kind');root=body.get('source')
    src=deepcopy(lab)
    if kind=='device':lab._device(root);names={root};clusters=set();locations=set()
    elif kind=='cluster':
        if root not in lab.clusters:raise LabError('unknown cluster')
        clusters=descendants(lab.clusters,root);locations=set()
        names={n for c in clusters for n in lab.clusters[c]['devices']}
    elif kind=='physical':
        lab._physical_location(root);locations=descendants(lab.physical_locations,root);clusters=set()
        names={n for n,loc in lab.device_locations.items() if loc in locations}
    else:raise LabError('template kind must be device, cluster or physical')
    if len(names)>200:raise LabError('template supports at most 200 devices')
    for name in set(src.devices)-names:src.remove_device(name)
    src.clusters={k:v for k,v in src.clusters.items() if k in clusters}
    if clusters:src.clusters[root]['parent']=None
    src.cluster_icons={k:v for k,v in src.cluster_icons.items() if k in clusters}
    src.physical_locations={k:v for k,v in src.physical_locations.items() if k in locations}
    if locations:src.physical_locations[root]['parent']=None
    else:
        for name in names:
            src.device_locations[name]='intercity'
            src.physical_device_details[name].update(surface='floor',shelf=None)
    src.physical_shelves={k:v for k,v in src.physical_shelves.items() if k in locations}
    src.icp_panels={k:v for k,v in src.icp_panels.items() if k in locations}
    src.location_backgrounds={k:v for k,v in src.location_backgrounds.items() if k in locations or k.removeprefix('logical:') in clusters}
    used={ident for views in src.device_icons.values() for ident in views.values()}|set(src.cluster_icons.values())|{v['asset_id'] for v in src.location_backgrounds.values() if v['asset_id']}
    src.visual_assets={k:v for k,v in src.visual_assets.items() if k in used}
    from .simulation import defaults as simulation_defaults
    src.simulation=simulation_defaults()
    src.workspace_tools=defaults()
    data=src.to_dict();data.pop('workspace_tools');data['events']=[];data['packet_events']=[];data['packet_counter']=0
    from .physical_distance import location_origin_m
    return {'kind':kind,'root':root,'description':body.get('description',''),'lab':data,
            'origin_m':list(location_origin_m(lab,root)) if kind=='physical' else None}

def unique(prefix,occupied):
    i=1
    while prefix+str(i) in occupied:i+=1
    result=prefix+str(i);occupied.add(result);return result

def instantiate(lab,t,body):
    src=read_lab(t['lab'])
    destination=body.get('location','intercity')
    if destination!='intercity':lab._physical_location(destination)
    target=body.get('cluster','root')
    if target!='root' and target not in lab.clusters:raise LabError('unknown target cluster')
    x=number(body.get('x',200),0,10000);y=number(body.get('y',160),0,10000)
    minx=min((d.x for d in src.devices.values()),default=0);miny=min((d.y for d in src.devices.values()),default=0)
    occupied=set(lab.devices)
    names={n:unique(n[:22]+'_',occupied) for n in src.devices}
    occupied=set(lab.physical_locations);places={n:unique('templateLoc',occupied) for n in src.physical_locations}
    occupied=set(lab.clusters);clusters={n:unique('Cluster',occupied) for n in src.clusters}
    for ident,loc in src.physical_locations.items():
        copy=deepcopy(loc);copy['id']=places[ident];copy['parent']=places.get(loc['parent'],None if destination=='intercity' else destination)
        parent=lab.physical_locations.get(destination) if loc['parent'] is None else src.physical_locations[loc['parent']]
        lab._location_fits(copy['type'],tuple(copy[k] for k in ('width','length','height')),parent)
        lab.physical_locations[copy['id']]=copy
    for name,d in src.devices.items():
        copy=deepcopy(d);copy.name=names[name];copy.x=number(x+d.x-minx,0,10000);copy.y=number(y+d.y-miny,0,10000)
        copy.arp_table.clear();copy.mac_table.clear();copy.nat_sessions.clear()
        for interface in copy.interfaces.values():interface.mac=_mac()
        for pool in copy.dhcp_pools.values():pool.leases.clear()
        lab.devices[copy.name]=copy
        loc=places.get(src.device_locations[name],destination)
        lab.device_locations[copy.name]=loc
        lab.physical_device_details[copy.name]=deepcopy(src.physical_device_details[name]) if places else lab._physical_placement_default(copy.kind,loc)
        if name in src.device_icons:lab.device_icons[copy.name]=deepcopy(src.device_icons[name])
        if name in src.radio_ranges:lab.radio_ranges[copy.name]=src.radio_ranges[name]
    for old,c in src.clusters.items():
        lab.clusters[clusters[old]]={**deepcopy(c),'id':clusters[old],'parent':clusters.get(c['parent'],None if target=='root' else target),'devices':[names[n] for n in c['devices']]}
    if not src.clusters and target!='root':lab.clusters[target]['devices'].extend(names.values())
    for link in src.links:
        copy=deepcopy(link);copy.a_device=names[link.a_device];copy.b_device=names[link.b_device];lab.links.append(copy)
    for k,v in src.physical_shelves.items():lab.physical_shelves[places[k]]=v
    for k,v in src.icp_panels.items():
        panel=deepcopy(v)
        for field in ('mounts','anchors'):panel[field]={names[n]:value for n,value in panel[field].items() if n in names}
        lab.icp_panels[places[k]]=panel
    for k,v in src.cluster_icons.items():lab.cluster_icons[clusters[k]]=v
    for k,v in src.location_backgrounds.items():lab.location_backgrounds[places[k] if k in places else 'logical:'+clusters[k.removeprefix('logical:')]]=deepcopy(v)
    from .visual_customization import load_visuals
    load_visuals(lab,{**lab.visual_assets,**src.visual_assets})
    offset=(0,0)
    if t['kind']=='physical':
        from .physical_distance import location_origin_m
        origin=t.get('origin_m') or location_origin_m(src,t['root'])
        destination_origin=location_origin_m(lab,places[t['root']])
        offset=(destination_origin[0]-origin[0],destination_origin[1]-origin[1])
    for key,route in src.cable_routes.items():
        endpoints=json.loads(key);newkey=json.dumps(sorted([[names[n],port] for n,port in endpoints]),separators=(',',':'),ensure_ascii=False)
        copy=deepcopy(route)
        # Independent instances must not accidentally share cable group IDs.
        for bend in copy['bends']:
            import uuid
            bend['x_m']+=offset[0];bend['y_m']+=offset[1]
            bend['id']='bend_'+uuid.uuid4().hex[:16]
            if bend['group']:bend['group']=next(iter(names.values()),'empty')+'_'+bend['group']
        lab.cable_routes[newkey]=copy
    lab.recompute_ospf()
    return names

def apply(lab,body):
    if not isinstance(body,dict):raise LabError('expected object')
    action=body.get('action');s=lab.workspace_tools
    if action in ('diagram_preferences','diagram_group','diagram_collapse','diagram_ungroup','layout_apply'):
        from .topology_presentation import apply as diagram_apply
        return diagram_apply(lab,body)
    if action=='viewport':
        allowed=set(s['viewport'])
        if set(body)-allowed-{'action'}:raise LabError('unknown viewport field')
        v={**s['viewport'],**{k:v for k,v in body.items() if k!='action'}}
        settings=validate({'viewport':v})['viewport']
        if settings['workspace']=='physical':
            if settings['location']!='intercity':lab._physical_location(settings['location'])
        elif settings['location']!='root' and settings['location'] not in lab.clusters:raise LabError('unknown viewport cluster')
        s['viewport']=settings
    elif action=='accessibility':s['accessibility']=validate({'accessibility':{**s['accessibility'],**{k:v for k,v in body.items() if k!='action'}}})['accessibility']
    elif action in ('template_capture','template_import'):
        name=body.get('name')
        if not isinstance(name,str) or not name.strip() or len(name)>64:raise LabError('template name must be 1..64 characters')
        if name in s['templates']:raise LabError('template name already exists')
        t=capture(lab,body) if action=='template_capture' else body.get('template')
        s['templates']=validate({'templates':{**s['templates'],name:t}})['templates']
    elif action=='template_delete':
        if body.get('name') not in s['templates']:raise LabError('unknown template')
        del s['templates'][body['name']]
    elif action=='template_instantiate':
        if body.get('name') not in s['templates']:raise LabError('unknown template')
        return instantiate(lab,s['templates'][body['name']],body)
    else:raise LabError('unsupported workspace tool action')

def command(lab,body):
    # Validate and execute on an isolated candidate, then publish as one edit.
    candidate=deepcopy(lab);result=apply(candidate,body)
    lab.__dict__.clear();lab.__dict__.update(candidate.__dict__)
    return result

def view(lab,workspace='logical',location='root',mode='contents'):
    if workspace not in ('logical','physical') or mode not in ('contents','workspace'):raise LabError('invalid viewport projection')
    if workspace=='logical':
        if location!='root' and location not in lab.clusters:raise LabError('unknown cluster')
        members={n for c in lab.clusters.values() for n in c['devices']}
        names=lab.clusters[location]['devices'] if location!='root' else [n for n in lab.devices if n not in members]
        items=[{'id':n,'label':n,'type':'device','x':lab.devices[n].x,'y':lab.devices[n].y} for n in names]
        items.extend({'id':c['id'],'label':c['name'],'type':'cluster','x':36+i%5*165,'y':45+i//5*112} for i,c in enumerate(c for c in lab.clusters.values() if c['parent']==(None if location=='root' else location)))
    else:
        from .physical_workspace import physical_view
        p=physical_view(lab,location)
        items=[{'id':d['name'],'label':d['name'],'type':'device','x':d['x'],'y':d['y']} for d in p['devices']]
        items.extend({'id':c['id'],'label':c['name'],'type':'location','x':c['x'],'y':c['y']} for c in p['children'])
    xs=[i['x'] for i in items];ys=[i['y'] for i in items]
    bounds={'x':min(xs,default=0) if mode=='contents' else 0,'y':min(ys,default=0) if mode=='contents' else 0,
            'right':max(1000 if mode=='workspace' else 300,max(xs,default=0)+180),
            'bottom':max(700 if mode=='workspace' else 240,max(ys,default=0)+150)}
    radios=[]
    if workspace=='physical':
        from .physical_distance import radio_sources
        radios=[r for r in radio_sources(lab,location) if r['location']==location and r['powered']]
    return {'ok':True,'settings':deepcopy(lab.workspace_tools),'items':items,'radios':radios,'bounds':bounds,'workspace':workspace,'location':location,'mode':mode}

def schema():
    return {'version':1,'read':'GET /api/workspace-tools?workspace=logical&location=root&mode=contents',
            'layout_preview':'GET /api/topology-layout?names=<JSON array; omit for all devices>',
            'diagram_limits':{'groups':100,'group_name_characters':64,'nested_groups':False,'routing':'separate parallel straight cables; unrelated crossings may remain'},
            'write':'POST /api/workspace-tools/action','actions':{
            'diagram_preferences':{'routing':True,'labels':'smart|all|none','focus':True,'semantic_zoom':True},
            'diagram_group':{'name':'Building A','members':['R1']},'diagram_collapse':{'name':'Building A','collapsed':True},'diagram_ungroup':{'name':'Building A'},
            'layout_apply':{'names':['R1'],'signature':'GET /api/topology-layout preview signature'},
            'viewport':defaults()['viewport'],'accessibility':defaults()['accessibility'],
            'template_capture':{'name':'Example','kind':'device|cluster|physical','source':'R1','description':''},
            'template_import':{'name':'Example','template':'exported template object'},
            'template_delete':{'name':'Example'},'template_instantiate':{'name':'Example','location':'intercity','cluster':'root','x':200,'y':160},'undo':{},'redo':{}}}
