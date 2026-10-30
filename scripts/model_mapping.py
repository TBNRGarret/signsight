"""Draft and validate checkpoint-specific mappings; never relabel or deploy data."""
import argparse
import hashlib
import json
from pathlib import Path

from ai_engine.catalog import ModelClassMapping, SignCatalog


def checkpoint_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def draft_mapping(names,catalog,checkpoint=None):
    if (not isinstance(names,list) or not names or len(names)>1000 or
        any(not isinstance(name,str) or not name.strip() for name in names) or len(set(names))!=len(names)):
        raise ValueError('Names must be a nonempty ordered list of unique strings')
    return {'schema_version':1,'catalog_sha256':catalog.sha256,
            'checkpoint_sha256':checkpoint_hash(checkpoint) if checkpoint else None,
            'classes':[{'model_class_id':index,'model_name':name,'catalog_id':None,'reviewed':False}
                       for index,name in enumerate(names)]}


def write_new(path,document):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(document,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    draft=commands.add_parser('draft',help='Create an unreviewed mapping, optionally before weights arrive')
    source=draft.add_mutually_exclusive_group(required=True)
    source.add_argument('--supsign-car35',action='store_true')
    source.add_argument('--names-json',type=Path,help='JSON list in exact model output order')
    draft.add_argument('--checkpoint',type=Path)
    draft.add_argument('--output',type=Path,required=True)
    for name in ('validate','bind'):
        command=commands.add_parser(name,help='Validate a reviewed mapping'+(' and bind a new artifact to weights' if name=='bind' else ''))
        command.add_argument('--mapping',type=Path,required=True)
        command.add_argument('--checkpoint',type=Path,required=True)
        if name=='bind':command.add_argument('--output',type=Path,required=True)
    for command in (draft,*[commands.choices[name] for name in ('validate','bind')]):
        command.add_argument('--catalog',type=Path,help='Append-only catalog JSON; defaults to legacy catalog')
    args=parser.parse_args(argv)
    catalog=SignCatalog.from_file(args.catalog)
    if args.command=='draft':
        if args.supsign_car35:
            from scripts.supsign_training import CAR35
            names=list(CAR35)
        else:names=json.loads(args.names_json.read_text(encoding='utf-8-sig'))
        write_new(args.output,draft_mapping(names,catalog,args.checkpoint))
        print('Unreviewed mapping:',args.output)
    else:
        document=json.loads(args.mapping.read_text(encoding='utf-8-sig'))
        if args.command=='bind':
            document['catalog_sha256']=catalog.sha256
            document['checkpoint_sha256']=checkpoint_hash(args.checkpoint)
        mapping=ModelClassMapping(document,catalog,args.checkpoint)
        if args.command=='bind':write_new(args.output,document)
        print('Validated class count:',len(mapping.names))
        print('Mapping SHA256:',mapping.sha256)
        print('Checkpoint names and semantic label review still require independent verification.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
