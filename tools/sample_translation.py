#!/usr/bin/env python3
"""Create or validate a UTF-8 JSON translation for the sample library."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from netsim.samples import translation_template,validate_translation

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('action',choices=('template','validate'));parser.add_argument('file',nargs='?')
 args=parser.parse_args()
 if args.action=='template':print(json.dumps(translation_template(),ensure_ascii=False,indent=2));return
 if not args.file:parser.error('validate requires a JSON file')
 try:pack=validate_translation(json.loads(Path(args.file).read_text(encoding='utf-8')))
 except (ValueError,RuntimeError,TypeError) as exc:raise SystemExit('Invalid translation: '+str(exc))
 print('Valid sample translation:',pack['id'],pack['name'])
if __name__=='__main__':main()
