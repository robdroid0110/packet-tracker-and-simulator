"""Read-only factual reference index, independent of the vendor help installation."""
import json
from pathlib import Path
from .model import LabError

def view(profile=None):
 data=json.loads((Path(__file__).parent/'data/command_reference.json').read_text())
 modes=data.pop('mode_records')
 for record in data['profiles']:record['modes']=[modes[i] for i in record.pop('mode_refs')]
 if profile:
  found=next((p for p in data['profiles'] if p['profile']==profile),None)
  if found is None:raise LabError('unknown command-reference profile')
  return {'version':1,'notice':data['notice'],**found}
 return data
