"""Stable application catalog IDs, separate from checkpoint-specific class indices."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

from ai_engine.config import TAXONOMY


def json_hash(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
                                    separators=(',',':'),allow_nan=False).encode()).hexdigest()


class SignCatalog:
    def __init__(self,items=None):
        items=deepcopy(TAXONOMY if items is None else items)
        if not isinstance(items,list) or not 1 <= len(items) <= 1000:
            raise ValueError('Catalog requires 1..1000 entries')
        by_id={};codes=set()
        for item in items:
            if (not isinstance(item,dict) or type(item.get('new_id')) is not int or
                not 0 <= item['new_id'] <= 1000000 or
                any(not isinstance(item.get(k),str) or not item[k].strip() or len(item[k])>limit
                    for k,limit in (('qcvn_code',20),('name_vi',255)))):
                raise ValueError('Invalid catalog entry')
            if item['new_id'] in by_id or item['qcvn_code'] in codes:
                raise ValueError('Duplicate catalog ID or code')
            by_id[item['new_id']]=item;codes.add(item['qcvn_code'])
        for legacy in TAXONOMY:
            existing=by_id.get(legacy['new_id'])
            if existing is None or any(existing[k]!=legacy[k] for k in ('qcvn_code','name_vi')):
                raise ValueError('Catalog must preserve legacy IDs, codes and names; use an explicit data migration to revise them')
        self.items=tuple(MappingProxyType(by_id[key]) for key in sorted(by_id))
        self.by_id=MappingProxyType({item['new_id']:item for item in self.items})
        self.sha256=json_hash([dict(item) for item in self.items])

    @classmethod
    def from_file(cls,path=None):
        return cls() if path is None else cls(json.loads(Path(path).read_text(encoding='utf-8-sig')))

    def public_items(self):
        return [{key:item[key] for key in ('new_id','qcvn_code','name_vi')} for item in self.items]


DEFAULT_CATALOG=SignCatalog()


class ModelClassMapping:
    def __init__(self,document,catalog,checkpoint):
        if not isinstance(document,dict) or document.get('schema_version')!=1:
            raise ValueError('Unsupported model mapping schema')
        if document.get('catalog_sha256')!=catalog.sha256:
            raise ValueError('Mapping catalog hash mismatch')
        with Path(checkpoint).open('rb') as stream:
            checksum=hashlib.file_digest(stream,'sha256').hexdigest()
        if document.get('checkpoint_sha256')!=checksum:
            raise ValueError('Mapping checkpoint hash mismatch')
        entries=document.get('classes')
        if not isinstance(entries,list) or not 1 <= len(entries) <= 1000:
            raise ValueError('Mapping requires an entry for every model class')
        names=[];targets=[]
        for index,item in enumerate(entries):
            if (not isinstance(item,dict) or type(item.get('model_class_id')) is not int or
                item['model_class_id']!=index or item.get('reviewed') is not True or
                not isinstance(item.get('model_name'),str) or not item['model_name'].strip() or
                type(item.get('catalog_id')) is not int or item['catalog_id'] not in catalog.by_id):
                raise ValueError('Mapping entries must be ordered, reviewed and reference known catalog IDs')
            names.append(item['model_name']);targets.append(item['catalog_id'])
        if len(set(names))!=len(names) or len(set(targets))!=len(targets):
            raise ValueError('Duplicate model name or catalog target in mapping')
        self.names=names;self.targets=tuple(targets);self.sha256=json_hash(document)

    def catalog_id(self,model_class_id):
        if type(model_class_id) is not int or not 0 <= model_class_id < len(self.targets):
            raise ValueError('Unsupported model class index')
        return self.targets[model_class_id]
