"""Group-level split balancing for a new development benchmark, not V3."""
from collections import Counter, defaultdict
import random

from training.data.common import SPLITS


def choose_folder_splits(rows, names, seed=42):
    """Retain each class's strongest group in train, then balance whole groups.

    The largest source of a rare class must not be moved wholesale to holdout
    merely to make that class present there. Missing holdout coverage is reported.
    Image ratios and mean per-class box ratios share equal objective weight;
    missing holdout classes have a bounded penalty, never the V3 million-point
    priority that could overwhelm the available learning support.
    """
    grouped=defaultdict(list)
    for row in rows:grouped[row['group']].append(row)
    keys=sorted(grouped)
    gc={k:Counter(int(line.split()[0]) for r in grouped[k] for line in r['lines']) for k in keys}
    total=sum(gc.values(),Counter())
    absent=[names[c] for c in range(len(names)) if not total[c]]
    if absent:raise ValueError(f'No usable training annotations for classes: {absent}')
    anchors={min((k for k in keys if gc[k][c]),key=lambda k:(-gc[k][c],k)) for c in range(len(names))}
    eligible=[k for k in keys if k not in anchors]
    if len(eligible)<2:
        raise ValueError('Cannot preserve train class coverage and strongest groups with non-empty val/test; provide more groups')
    ratios=dict(train=.7,val=.15,test=.15)
    def image_cost(sizes):return sum(abs(sizes[s]/len(rows)-ratios[s]) for s in SPLITS)
    def class_cost(counts):
        return sum(abs(counts[s][c]/total[c]-ratios[s]) for c in range(len(names)) for s in SPLITS)/len(names)
    best=None
    for trial in range(8):
        rng=random.Random(seed+trial)
        assignments=dict.fromkeys(keys,'train')
        sizes=Counter(train=len(rows));counts=dict(train=total.copy(),val=Counter(),test=Counter())
        order=eligible.copy();rng.shuffle(order)
        order.sort(key=lambda k:len(grouped[k]))
        # Small seed groups avoid locking most of the dataset into one holdout.
        for key,split in zip(order[:2],('val','test')):
            assignments[key]=split;sizes['train']-=len(grouped[key]);sizes[split]+=len(grouped[key])
            counts['train'].subtract(gc[key]);counts[split].update(gc[key])
        missing=sum(not counts[s][c] for s in ('val','test') for c in range(len(names)))
        score=image_cost(sizes)+class_cost(counts)+.05*missing
        # Scarce/large class contributions first, with seeded tie order.
        rng.shuffle(order)
        order.sort(key=lambda k:(-max((n/total[c] for c,n in gc[k].items()),default=0),-len(grouped[k])))
        for key in order:
            if assignments[key]!='train':continue
            choices=[]
            for split in ('val','test'):
                proposed=sizes.copy();proposed['train']-=len(grouped[key]);proposed[split]+=len(grouped[key])
                delta=0
                for c,n in gc[key].items():
                    delta+=(abs((counts['train'][c]-n)/total[c]-.7)-abs(counts['train'][c]/total[c]-.7)
                            +abs((counts[split][c]+n)/total[c]-ratios[split])-abs(counts[split][c]/total[c]-ratios[split]))/len(names)
                filled=sum(not counts[split][c] for c in gc[key])
                cost=score+image_cost(proposed)-image_cost(sizes)+delta-.05*filled
                choices.append((cost,split,proposed,filled))
            cost,split,proposed,filled=min(choices,key=lambda v:v[0])
            if cost<score-1e-12:
                assignments[key]=split;sizes=proposed;score=cost;missing-=filled
                counts['train'].subtract(gc[key]);counts[split].update(gc[key])
        if best is None or score<best[0]:best=score,assignments,counts
    _,assignments,counts=best
    for row in rows:row['split']=assignments[row['group']]
    return counts,{s:[name for c,name in enumerate(names) if not counts[s][c]] for s in SPLITS}
