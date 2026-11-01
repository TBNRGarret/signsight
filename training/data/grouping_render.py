"""Offline grouping tables and bounded image evidence; no runtime dependencies."""
import csv
from html import escape
import textwrap

from PIL import Image, ImageDraw, ImageOps


def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _contact_sheet(root, path, rows, *, columns=3, captions=None):
    width, height = 320, 270
    sheet = Image.new('RGB', (columns*width, ((len(rows)+columns-1)//columns)*height), '#15202b')
    draw = ImageDraw.Draw(sheet)
    for i, row in enumerate(rows):
        x, y = (i % columns)*width, (i // columns)*height
        with Image.open(root/row['image']) as source:
            image = source.convert('RGB')
        annotated = ImageDraw.Draw(image)
        for line in (root/row['label']).read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            cls, cx, cy, w, h = map(float, line.split())
            annotated.rectangle(((cx-w/2)*image.width, (cy-h/2)*image.height,
                                 (cx+w/2)*image.width, (cy+h/2)*image.height), outline='yellow', width=2)
        image = ImageOps.contain(image, (width-12, 190))
        sheet.paste(image, (x+(width-image.width)//2, y+4))
        title = f"{row['sha256'][:10]} | {row['split']}"
        description = ', '.join(row['classes']) or 'NEGATIVE (selected taxonomy)'
        lines = [title, *textwrap.wrap(description, 44)[:3]]
        if captions:
            lines.append(captions[i])
        for j, line in enumerate(lines):
            draw.text((x+7, y+198+j*13), line, fill='white')
    sheet.save(path)


def _table(rows, fields):
    return '<div class="scroll"><table><thead><tr>'+''.join(f'<th>{escape(k)}</th>' for k in fields)+\
        '</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{escape(str(r[k]))}</td>' for k in fields)+\
                                     '</tr>' for r in rows)+'</tbody></table></div>'


def render_review(root, output, summary, group_rows, coverage, members, edges, max_groups, samples):
    """Return preview inventory and write HTML + contact sheets for largest groups."""
    preview_dir = output/'previews'
    preview_dir.mkdir()
    by_hash = {r['sha256']: r for rows in members.values() for r in rows}
    edge_groups = {}
    for edge in edges:
        edge_groups.setdefault(edge['left_group'], []).append(edge)
    previews, cards = [], []
    for index, stats in enumerate(group_rows[:max_groups]):
        group = stats['group']
        ordered = sorted(members[group], key=lambda r: (r['source_path'], r['sha256']))
        count = min(samples, len(ordered))
        positions = [round(i*(len(ordered)-1)/(count-1)) for i in range(count)] if count > 1 else [0]
        chosen = [ordered[i] for i in positions]
        sheet = f'previews/group_{index:04d}.png'
        _contact_sheet(root, output/sheet, chosen)
        # At most three joining edges per group: show namespace collisions first,
        # then one example of each reason, then high-distance dHash joins.
        candidates = sorted(edge_groups.get(group, []), key=lambda e: (
            not e['namespace_collision'], e['reason'], -(e['distance'] or 0), e['left'], e['right']))
        selected, reasons = [], set()
        for edge in candidates:
            if edge['namespace_collision'] or edge['reason'] not in reasons:
                selected.append(edge)
                reasons.add(edge['reason'])
            if len(selected) == 3:
                break
        if len(selected) < 3:
            for edge in candidates:
                if edge not in selected:
                    selected.append(edge)
                if len(selected) == 3:
                    break
        inventory = dict(group=group, contact_sheet=sheet, images=[r['image'] for r in chosen],
                         source_paths=[r['source_path'] for r in chosen], edge_examples=selected)
        detail = '<h2>'+escape(str(group))+f" · {stats['split']} · {stats['images']:,} images</h2>"
        detail += f'<img src="{sheet}" alt="Sampled group images with bounding boxes">'
        detail += '<details><summary>Sample source paths / labels</summary><ul>'+''.join(
            '<li>'+escape(r['source_path'])+'<br>'+escape(', '.join(r['classes']) or 'NEGATIVE')+
            '<br>Aliases: '+escape(' | '.join(r['aliases']))+'</li>' for r in chosen)+'</ul></details>'
        if selected:
            edge_sheet = f'previews/group_{index:04d}_edges.png'
            pairs = [by_hash[e[key]] for e in selected for key in ('left', 'right')]
            captions = [f"{e['reason']} | distance={e['distance']}" for e in selected for _ in range(2)]
            _contact_sheet(root, output/edge_sheet, pairs, columns=2, captions=captions)
            inventory['edge_sheet'] = edge_sheet
            detail += '<h3>Direct joining edges (one pair per row)</h3>'
            detail += f'<img src="{edge_sheet}" alt="Pairs explaining direct joins">'
            detail += _table(selected, ['reason', 'distance', 'left_alias', 'right_alias', 'namespace_collision', 'cross_split'])
        previews.append(inventory)
        cards.append('<section>'+detail+'</section>')
    warnings = ''.join('<li>'+escape(w)+'</li>' for w in summary['warnings']) or '<li>No automatic concentration flags.</li>'
    split_rows = [dict(split=split, **values) for split, values in summary['splits'].items()]
    page = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SignSight · grouping review</title><style>
body{font:16px/1.5 system-ui,sans-serif;color:#e6edf3;background:#101820;max-width:1200px;margin:auto;padding:24px}
h1,h2,h3{line-height:1.2}a{color:#89c5ff}section{border-top:1px solid #526070;margin-top:32px;padding-top:16px}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:8px;border:1px solid #526070;text-align:left}
th{background:#243140}td{overflow-wrap:anywhere}.scroll{overflow:auto}img{max-width:100%;height:auto}
code,li{overflow-wrap:anywhere}details{margin:16px 0}.notice{background:#273746;padding:16px;border-radius:8px}
</style><h1>SupSign grouping review</h1>'''
    page += f"<p>{summary['images']:,} images · {summary['groups']:,} stored groups · {summary['edge_count']:,} joining edges</p>"
    page += '<div class="notice"><b>Replay agreement: '+escape(str(summary['partition_matches']))+'</b><p>'+escape(summary['limitations'])+'</p></div>'
    page += '<p>Read: flags → split concentration → largest-group samples → direct joins → class coverage. '
    page += 'Review labels in the images before changing grouping; preserve the existing cache.</p>'
    page += '<h2>Review flags</h2><ul>'+warnings+'</ul>'
    page += '<p><a href="grouping_summary.json">JSON</a> · <a href="groups.csv">All groups CSV</a> · '
    page += '<a href="grouping_edges.csv">All forest edges CSV</a> · <a href="group_members.csv">All members / source aliases CSV</a> · <a href="class_coverage.csv">Class coverage CSV</a></p>'
    page += '<h2>Splits</h2>'+_table(split_rows, ['split', 'images', 'groups', 'largest_group_images', 'largest_group_fraction'])
    page += '<h2>All stored groups</h2>'+_table(group_rows, ['group', 'split', 'images', 'boxes', 'negative_images', 'source_namespaces'])
    page += ''.join(cards)
    page += '<section><h2>Class coverage</h2><p>Zero holdout counts mean unevaluated, not successful recognition. '
    page += 'Group counts are heuristic support, not verified independent trips.</p>'
    page += _table(coverage, ['class_id', 'name', 'split', 'boxes', 'images', 'groups'])+'</section>'
    page += '<p>Manifest SHA-256: <code>'+escape(summary['manifest_sha256'])+'</code></p></html>'
    (output/'index.html').write_text(page, encoding='utf-8')
    return previews
