"""Offline active-learning review queue; proposals never become accepted labels."""
import argparse
from collections import Counter
import csv
import io
import json
import math
from pathlib import Path
import random
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image, ImageOps

from training.data.common import CAR35, digest_file
from training.data.finetune import REVIEW_FIELDS, _review_entries

BASELINE_SHA256 = '0d1f9b2feb2711189aa59b90db1d32c4f436940ab3ec98412c58ffe4289e4ea1'
EXTENSIONS = {'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}


def _image_bytes(path,preserve):
    with Image.open(path) as source:
        if source.width*source.height>40_000_000:raise ValueError('Oversized pixels')
        if preserve:return source.convert('RGB'),path.read_bytes(),path.suffix.lower()
        image=ImageOps.exif_transpose(source).convert('RGB')
        data=io.BytesIO();image.save(data,format='JPEG',quality=90,exif=b'',icc_profile=None)
        return image,data.getvalue(),'.jpg'


def _iou(a,b):
    x=max(0,min(a[2],b[2])-max(a[0],b[0]));y=max(0,min(a[3],b[3])-max(a[1],b[1]))
    intersection=x*y
    return intersection/((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection)


def _proposals(predictions,width,height):
    kept=[]
    for row in sorted(predictions,key=lambda r:-r['confidence']):
        if not any(_iou(row['bbox'],other['bbox'])>.5 for other in kept):kept.append(row)
    lines=[]
    for row in kept:
        x1,y1,x2,y2=row['bbox']
        lines.append(f"{row['class_id']} {(x1+x2)/2/width:.10f} {(y1+y2)/2/height:.10f} {(x2-x1)/width:.10f} {(y2-y1)/height:.10f}")
    return '\n'.join(lines)+('\n' if lines else '')


def build_active_review_pack(pool,review_pack,base_manifest,checkpoint,output,*,expected_checkpoint_sha256,
                             limit=100,seed=42,device='cpu',groups=None,yolo_factory=None):
    pool,review_pack,base_manifest,checkpoint,output=map(lambda p:Path(p).resolve(),
        (pool,review_pack,base_manifest,checkpoint,output))
    if output.exists():raise FileExistsError(output)
    if not pool.is_dir() or output.is_relative_to(pool):raise ValueError('Choose a pool directory and output outside it')
    if type(limit) is not int or not 1<=limit<=1000:raise ValueError('Selection limit must be 1..1000')
    if not checkpoint.is_file() or digest_file(checkpoint)!=expected_checkpoint_sha256.lower():
        raise ValueError('Initial checkpoint SHA-256 mismatch')
    manifest=json.loads(base_manifest.read_text(encoding='utf-8'))
    if manifest['names']!=CAR35:raise ValueError('Base taxonomy differs from CAR35')
    known={r['sha256']:r for r in manifest['images']}
    excluded=Counter();candidates=[];seen=set()
    with ZipFile(review_pack) as original:
        prefix=_review_entries(original)
        metadata=json.loads(original.read(prefix+'review.json'))
        if metadata!=dict(schema_version=1,names=CAR35,base_manifest_sha256=digest_file(base_manifest)):
            raise ValueError('Review pack belongs to a different base manifest')
        table=csv.DictReader(io.StringIO(original.read(prefix+'review.csv').decode('utf-8-sig')))
        if table.fieldnames!=list(REVIEW_FIELDS):raise ValueError('Invalid review.csv columns')
        existing=list(table)
        import hashlib
        for row in existing:
            seen.add(hashlib.sha256(original.read(prefix+row['image'])).hexdigest())
        if yolo_factory is None:
            from ultralytics import YOLO
            yolo_factory=YOLO
        detector=yolo_factory(str(checkpoint))
        names=detector.names
        names=[names[i] for i in range(len(names))] if isinstance(names,dict) else list(names)
        if detector.task!='detect' or names!=CAR35:raise ValueError('Checkpoint taxonomy differs from CAR35')
        files=sorted(p for p in pool.rglob('*') if p.suffix.lower() in EXTENSIONS and p.is_file())
        for path in files:
            if path.is_symlink() or not path.resolve().is_relative_to(pool):
                excluded['unsafe_path']+=1;continue
            if path.stat().st_size>64*1024**2:excluded['oversized_image']+=1;continue
            source_sha=digest_file(path)
            prior=known.get(source_sha)
            if prior and prior['split']!='train':excluded['heldout_exact_duplicate']+=1;continue
            if source_sha in seen:excluded['pool_exact_duplicate']+=1;continue
            seen.add(source_sha)
            try:
                image,data,suffix=_image_bytes(path,prior is not None)
            except (OSError,ValueError,Image.DecompressionBombError):
                excluded['unreadable_image']+=1;continue
            digest=hashlib.sha256(data).hexdigest()
            normalized_prior=known.get(digest)
            if normalized_prior and normalized_prior['split']!='train':
                excluded['heldout_exact_duplicate']+=1;continue
            if digest!=source_sha and digest in seen:excluded['pool_exact_duplicate']+=1;continue
            seen.add(digest)
            result=detector.predict(image,imgsz=640,conf=.05,device=device,verbose=False,max_det=25)[0]
            predictions=[]
            for box in result.boxes:
                cls=int(box.cls.item());confidence=float(box.conf.item());bbox=list(map(float,box.xyxy[0].tolist()))
                if (not 0<=cls<35 or not math.isfinite(confidence) or not 0<=confidence<=1 or
                    len(bbox)!=4 or not all(math.isfinite(v) for v in bbox) or
                    not 0<=bbox[0]<bbox[2]<=image.width or not 0<=bbox[1]<bbox[3]<=image.height):
                    raise ValueError('Detector returned invalid review proposals')
                predictions.append(dict(class_id=cls,name=CAR35[cls],confidence=confidence,bbox=bbox))
            predictions.sort(key=lambda r:-r['confidence'])
            confidence=predictions[0]['confidence'] if predictions else 0
            reason='no_detection' if not predictions else 'low_confidence' if confidence<.35 else 'confident_prediction'
            score=1-confidence
            if len(predictions)>1 and _iou(predictions[0]['bbox'],predictions[1]['bbox'])>.5 and confidence-predictions[1]['confidence']<.1:
                reason='competing_labels';score=max(score,.95)
            relative=path.relative_to(pool).as_posix()
            prior=prior or normalized_prior
            group=prior['group'] if prior else (groups or {}).get(relative,'')
            candidates.append(dict(source=relative,source_sha256=source_sha,sha256=digest,reason=reason,score=score,
                predictions=predictions,image=f'images/{digest}{suffix}',label=f'labels/{digest}.txt',
                group=group,preserve=source_sha in known,label_data=_proposals(predictions,image.width,image.height)))
        rng=random.Random(seed);rng.shuffle(candidates)
        ranked=sorted(candidates,key=lambda r:-r['score'])
        count=min(limit,len(ranked));explore=min(count-1,max(1,math.ceil(count*.25))) if count>1 else 0
        selected=ranked[:count-explore]
        exploration=rng.sample(ranked[count-explore:],explore)
        for row in selected:row['selection']='uncertainty'
        for row in exploration:row['selection']='exploration'
        selected+=exploration
        rows=existing+[dict(image=r['image'],label=r['label'],split='train',group=r['group'],reviewed='no') for r in selected]
        if len(rows)>10000:raise ValueError('Review pack exceeds 10000 rows')
        summary=dict(schema_version=1,scanned=len(candidates),selected=len(selected),excluded=dict(excluded),
            checkpoint_sha256=digest_file(checkpoint),base_manifest_sha256=digest_file(base_manifest),seed=seed,
            selected_images=[{k:v for k,v in r.items() if k not in ('preserve','label_data')} for r in selected],
            limitations='Heuristic uncertainty plus 25% random exploration. No automatic ground truth. '
                        'Exact holdout duplicates excluded here; near-duplicate screening runs during fine-tune preparation. '
                        'New images require real capture groups and human label review. These are development images, not independent tests.')
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('xb') as stream:
            try:
                with ZipFile(stream,'w',compression=ZIP_DEFLATED) as target:
                    generated={'review.csv','active_learning.json','ACTIVE_REVIEW.txt'}
                    for member in original.infolist():
                        if member.is_dir() or not member.filename.startswith(prefix):continue
                        name=member.filename[len(prefix):]
                        if name and name not in generated:target.writestr(name,original.read(member))
                    total_size=sum(m.file_size for m in original.infolist())
                    for row in selected:
                        path=pool/row['source']
                        if digest_file(path)!=row['source_sha256']:raise ValueError('Pool image changed during selection')
                        _,data,_=_image_bytes(path,row['preserve'])
                        if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Normalized image changed')
                        total_size+=len(data)
                        if total_size>16*1024**3:raise ValueError('Review ZIP exceeds 16 GiB; select fewer images')
                        target.writestr(row['image'],data);target.writestr(row['label'],row['label_data'])
                    table=io.StringIO(newline='');writer=csv.DictWriter(table,fieldnames=REVIEW_FIELDS)
                    writer.writeheader();writer.writerows(rows)
                    target.writestr('review.csv',table.getvalue())
                    target.writestr('active_learning.json',json.dumps(summary,indent=2))
                    target.writestr('ACTIVE_REVIEW.txt','AI boxes are proposals. Correct all visible CAR35 signs, including missed signs.\n'
                        'Fill real group/session IDs for new images; keep a capture/physical sign in one split.\n'
                        'Set reviewed=yes only after checking. Empty AI labels do not mean verified background.\n')
            except BaseException:
                stream.close();output.unlink(missing_ok=True);raise
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('pool','review-pack','base-manifest','checkpoint','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--checkpoint-sha256',default=BASELINE_SHA256)
    parser.add_argument('--limit',type=int,default=100)
    parser.add_argument('--device',default='cpu')
    parser.add_argument('--groups-csv',type=Path)
    args=parser.parse_args()
    groups=None
    if args.groups_csv:
        with args.groups_csv.open(newline='',encoding='utf-8-sig') as stream:
            rows=list(csv.DictReader(stream))
        groups={r['path']:r['group'] for r in rows}
        if len(groups)!=len(rows):parser.error('Duplicate capture paths')
    summary=build_active_review_pack(args.pool,args.review_pack,args.base_manifest,args.checkpoint,args.output,
        expected_checkpoint_sha256=args.checkpoint_sha256,limit=args.limit,device=args.device,groups=groups)
    print(json.dumps({k:v for k,v in summary.items() if k!='selected_images'},indent=2))
    print('Review pack:',args.output)


if __name__=='__main__':main()
