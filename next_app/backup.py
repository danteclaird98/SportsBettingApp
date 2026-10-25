"""SQLite-aware backups, verification, and restore into a new directory only."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time

DATABASES=('workspace.sqlite3','research.sqlite3','edgeodds.sqlite3')


def digest(path):
    result=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1048576),b''): result.update(block)
    return result.hexdigest()


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)


def check_database(path):
    with closing(readonly(path)) as db:
        if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:
            raise ValueError('SQLite integrity check failed: '+path.name)


def verify_backup(directory):
    directory=Path(directory)
    manifest_path=directory/'manifest.json'
    if manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size>1048576:
        raise ValueError('Missing or invalid backup manifest')
    manifest=json.loads(manifest_path.read_text())
    if not isinstance(manifest,dict) or manifest.get('formatVersion')!=1 or not isinstance(manifest.get('databases'),list):
        raise ValueError('Unsupported backup manifest')
    seen=set()
    for entry in manifest['databases']:
        if not isinstance(entry,dict) or entry.get('name') not in DATABASES or entry['name'] in seen:
            raise ValueError('Invalid or duplicate backup database name')
        seen.add(entry['name'])
        path=directory/entry['name']
        if path.is_symlink() or not path.is_file(): raise ValueError('Missing backup database: '+entry['name'])
        if path.stat().st_size!=entry.get('sizeBytes') or digest(path)!=entry.get('sha256'):
            raise ValueError('Backup checksum mismatch: '+entry['name'])
        check_database(path)
    if 'workspace.sqlite3' not in seen: raise ValueError('Workspace database is required')
    return manifest


def create_backup(data_dir,destination):
    data_dir=Path(data_dir); destination=Path(destination)
    if not (data_dir/'workspace.sqlite3').is_file(): raise ValueError('Workspace database is required')
    destination.mkdir(mode=0o700,parents=True,exist_ok=False)
    entries=[]; missing=[]
    for name in DATABASES:
        source=data_dir/name
        if source.is_symlink(): raise ValueError('Database symlinks are not supported: '+name)
        if not source.exists(): missing.append(name); continue
        target=destination/name
        deadline=time.monotonic()+30
        def progress(status,remaining,total):
            if time.monotonic()>deadline: raise TimeoutError('Database snapshot timed out: '+name)
        with closing(readonly(source)) as live, closing(sqlite3.connect(target)) as snapshot:
            os.chmod(target,0o600)
            live.backup(snapshot,pages=128,progress=progress,sleep=.01)
        check_database(target)
        entries.append({'name':name,'sizeBytes':target.stat().st_size,'sha256':digest(target)})
    manifest={'formatVersion':1,'createdAt':datetime.now(timezone.utc).isoformat(),'databases':entries,'missing':missing,
              'consistency':'Individual SQLite snapshots; no cross-database transaction guarantee'}
    path=destination/'manifest.json'
    path.write_text(json.dumps(manifest,indent=2)+'\n'); os.chmod(path,0o600)
    return verify_backup(destination)


def restore_backup(directory,destination):
    directory=Path(directory); destination=Path(destination)
    manifest=verify_backup(directory)
    # mkdir is exclusive: an existing data directory is never overwritten.
    destination.mkdir(mode=0o700,parents=True,exist_ok=False)
    for entry in manifest['databases']:
        target=destination/entry['name']
        shutil.copyfile(directory/entry['name'],target); os.chmod(target,0o600)
        if digest(target)!=entry['sha256']: raise ValueError('Restored checksum mismatch: '+entry['name'])
        check_database(target)
    provenance=destination/'restore-manifest.json'
    provenance.write_text(json.dumps(manifest,indent=2)+'\n'); os.chmod(provenance,0o600)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    backup=commands.add_parser('create')
    backup.add_argument('--data-dir',type=Path,required=True); backup.add_argument('--destination',type=Path,required=True)
    verify=commands.add_parser('verify'); verify.add_argument('directory',type=Path)
    restore=commands.add_parser('restore'); restore.add_argument('directory',type=Path); restore.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.command=='create': result=create_backup(args.data_dir,args.destination)
        elif args.command=='verify': result=verify_backup(args.directory)
        else: result=restore_backup(args.directory,args.destination)
    except (OSError,ValueError,sqlite3.Error,TimeoutError) as exc: parser.exit(1,f'{exc}\n')
    print(json.dumps({'status':'ok','databases':[entry['name'] for entry in result['databases']],
                      'missing':result.get('missing',[])},indent=2))


if __name__=='__main__': main()
