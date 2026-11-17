"""Saved diagram preferences and deterministic, previewable logical layouts."""
import hashlib, json
from collections import deque
from .model import LabError

def defaults():
    return {'routing':True,'labels':'smart','focus':True,'semantic_zoom':True,'groups':{}}

def validate(raw):
    d=defaults()
    if not isinstance(raw,dict) or set(raw)-set(d):raise LabError('invalid diagram settings')
    d.update(raw)
    if any(type(d[k]) is not bool for k in ('routing','focus','semantic_zoom')) or d['labels'] not in ('smart','all','none'):raise LabError('invalid diagram preferences')
    if not isinstance(d['groups'],dict) or len(d['groups'])>100:raise LabError('maximum 100 diagram groups')
    used=set()
    for name,g in d['groups'].items():
        if not isinstance(name,str) or not name.strip() or len(name)>64 or not isinstance(g,dict) or set(g)!={'members','collapsed'} or type(g['collapsed']) is not bool:raise LabError('invalid diagram group')
        members=g['members']
        if not isinstance(members,list) or not members or any(not isinstance(n,str) for n in members) or len(set(members))!=len(members) or used.intersection(members):raise LabError('group members must be unique and disjoint')
        used.update(members)
    return d

def layout(lab,names=None):
    names=sorted(lab.devices) if names is None else names
    if not isinstance(names,list) or any(not isinstance(n,str) or n not in lab.devices for n in names) or len(set(names))!=len(names):raise LabError('invalid layout device list')
    names=sorted(names);adj={n:set() for n in names}
    for l in lab.links:
        if l.a_device in adj and l.b_device in adj:
            adj[l.a_device].add(l.b_device);adj[l.b_device].add(l.a_device)
    # Include stationary devices so partial layouts cannot overwrite a changed preview.
    signature=hashlib.sha256(json.dumps([names,[(n,d.x,d.y,d.kind) for n,d in sorted(lab.devices.items())],[(n,sorted(adj[n])) for n in names]]).encode()).hexdigest()
    remaining=set(names);rows={};base=0
    while remaining:
        root=min(remaining,key=lambda n:({'router':0,'switch':1}.get(lab.devices[n].kind,2),-len(adj[n]),n))
        queue=deque([(root,base)]);remaining.remove(root);last=base
        while queue:
            n,depth=queue.popleft();rows.setdefault(depth,[]).append(n);last=max(last,depth)
            for other in sorted(adj[n],key=lambda k:(-len(adj[k]),k)):
                if other in remaining:remaining.remove(other);queue.append((other,depth+1))
        base=0
    positions={};row=0
    columns=min(40,max((len(m) for m in rows.values()),default=0))
    stationary=[(d.x,d.y) for n,d in lab.devices.items() if n not in adj]
    for depth,members in sorted(rows.items()):
        for start in range(0,len(members),40):
            for col,n in enumerate(members[start:start+40]):
                x,y=80+(columns-len(members[start:start+40]))*105+col*210,60+row*150
                # Reserve enough space for icons and their name/model labels.
                while any(abs(x-a)<110 and abs(y-b)<95 for a,b in stationary):
                    x+=210
                    if x>9600:x=80;y+=150
                    if y>9800:raise LabError('Layout exceeds canvas bounds; select a smaller portion')
                positions[n]={'x':x,'y':y};stationary.append((x,y))
            row+=1
        row+=1 if depth+1 not in rows else 0
    if any(p['y']>9800 for p in positions.values()):raise LabError('Layout exceeds canvas bounds; select a smaller portion')
    return {'ok':True,'positions':positions,'names':names,'signature':signature}

def apply(lab,body):
    action=body['action'];d=lab.workspace_tools.setdefault('diagram',defaults())
    if action=='diagram_preferences':
        if set(body)-{'action','routing','labels','focus','semantic_zoom'}:raise LabError('unknown diagram preference')
        lab.workspace_tools['diagram']=validate({**d,**{k:v for k,v in body.items() if k!='action'}})
    elif action=='layout_apply':
        plan=layout(lab,body.get('names'))
        if body.get('signature')!=plan['signature']:raise LabError('Topology changed; preview the layout again')
        for n,p in plan['positions'].items():lab.devices[n].x=p['x'];lab.devices[n].y=p['y']
        return plan
    elif action in ('diagram_group','diagram_collapse','diagram_ungroup'):
        name=body.get('name')
        if not isinstance(name,str):raise LabError('group name required')
        if action=='diagram_group':
            if name in d['groups']:raise LabError('group already exists')
            members=body.get('members')
            if not isinstance(members,list) or any(not isinstance(n,str) or n not in lab.devices for n in members):raise LabError('unknown group member')
            d['groups'][name]={'members':members,'collapsed':False}
        else:
            if name not in d['groups']:raise LabError('unknown group')
            if action=='diagram_ungroup':del d['groups'][name]
            else:d['groups'][name]['collapsed']=body.get('collapsed')
        validate(d)
    else:raise LabError('unknown diagram action')
