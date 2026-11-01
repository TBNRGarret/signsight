"""Read-only policy check for tracked public source. Never exports or prints secrets."""
import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess

SECRET_PATTERNS = [re.compile(p) for p in (
    r'gh[pousr]_[A-Za-z0-9]{30,}', r'github_pat_[A-Za-z0-9_]{30,}',
    r'(?:AKIA|ASIA)[A-Z0-9]{16}', r'sk-(?:proj-)?[A-Za-z0-9_-]{40,}',
    r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]

def is_public_path(name):
    p=PurePosixPath(name)
    if '\\' in name or p.is_absolute() or '..' in p.parts or not p.parts or any(':' in part for part in p.parts): return False
    if any(part in {'.git','.cache','__pycache__','node_modules','.venv','.venv-yolo'} for part in p.parts): return False
    if p.name in {'.env','credentials.json','kaggle.json','login.txt'}: return False
    if p.name.startswith('.env.') and p.name!='.env.example': return False
    if p.suffix.lower() in {'.db','.sqlite','.sqlite3','.pt','.pth','.onnx','.engine','.pem','.key','.p12','.pfx','.docx','.pdf','.zip'}: return False
    if any(name.endswith(suffix) for suffix in ('-wal','-shm','-journal')): return False
    if name.startswith('backend/uploads/'): return p.name=='.gitkeep'
    if p.parts[0]=='data':
        return name=='data/taxonomy.json' or (p.parent.as_posix()=='data/processed' and p.name in {'train.csv','val.csv','test.csv'})
    if name.startswith('ai_engine/checkpoints/'):
        return name in {'ai_engine/checkpoints/.gitkeep','ai_engine/checkpoints/detection/.gitkeep',
                        'ai_engine/checkpoints/detection/detection_report.json'}
    if name=='deploy/Caddyfile.example': return True
    if name.startswith(('docs/qa/','data/field/','data/vietnam_raw/','data/vietnam_yolo/')): return False
    if p.name in {'thinh_tasks.md','roadmap_12_weeks.md','implementation_plan.md'}: return False
    if 'worklog' in p.name.lower() or re.search(r'(?i)^(?:COS|EAT)\d{5}',p.name): return False
    root_files={'.gitattributes','.gitignore','.env.example','README.md','CONTRIBUTING.md','PRODUCT.md',
                'pytest.ini','package.json','package-lock.json','playwright.config.cjs','playwright.flutter.config.cjs'}
    return p.parts[0] in {'backend','frontend','mobile','ai_engine','training','scripts','tests','database','notebooks','docs','.github'} or name in root_files

def inspect_paths(root, paths):
    root=Path(root).resolve(); findings=[]
    for name in sorted(set(paths)):
        if not name: continue
        reason=None
        if not is_public_path(name): reason='private or unsafe path'
        else:
            p=root/name
            if p.is_symlink() or p.resolve()!=p.absolute(): reason='symbolic or redirected source'
            elif not p.is_file(): reason='missing tracked file'
            else:
                content=p.read_bytes()
                if b'\x00' not in content:
                    text=content.decode('utf-8',errors='replace')
                    if any(pattern.search(text) for pattern in SECRET_PATTERNS): reason='possible credential (value hidden)'
        if reason: findings.append(dict(path=name,reason=reason))
    return findings

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    names=subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode('utf-8').split('\0')
    findings=inspect_paths(root,names)
    for row in findings: print(row['path']+': '+row['reason'])
    print(f'Public-source policy: {len(findings)} finding(s); no files changed.')
    return int(bool(findings))

if __name__=='__main__': raise SystemExit(main())
