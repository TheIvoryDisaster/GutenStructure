"""Publish a checked package; never execute caller source in the write-token job."""
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from scripts.release_gate import MissingResource, check as check_release


def resolve_tag(api, repository, tag):
    value=api(f'repos/{repository}/git/ref/tags/{tag}')['object']
    for _ in range(4):
        if value['type']=='commit' and re.fullmatch(r'[a-f0-9]{40}',value['sha']): return value['sha']
        if value['type']!='tag' or not re.fullmatch(r'[a-f0-9]{40}',value['sha']): break
        value=api(f'repos/{repository}/git/tags/{value["sha"]}')['object']
    raise ValueError('Tag does not resolve to a commit')


def optional(api,path):
    try:return api(path)
    except MissingResource:return None


def verify_existing(api,repository,release,tag,commit,filename,digest,beta):
    if release.get('tag_name')!=tag or release.get('draft') or release.get('prerelease') is not beta:
        raise ValueError('Existing release channel or identity mismatch')
    if resolve_tag(api,repository,tag)!=commit:
        raise ValueError('Existing release points at another source commit')
    assets=[]
    for page in range(1,11):
        rows=api(f'repos/{repository}/releases/{release["id"]}/assets?per_page=100&page={page}')
        assets.extend(rows)
        if len(rows)<100:break
    else:raise ValueError('Incomplete existing asset inventory')
    matches=[asset for asset in assets if asset.get('name')==filename]
    if len(matches)!=1 or matches[0].get('state')!='uploaded' or matches[0].get('digest')!='sha256:'+digest:
        raise ValueError('Existing snapshot differs from rebuilt bytes; reuse its canonical artifact/hash instead of retrying or overwriting it')
    if not any(asset.get('name')==filename+'.sha256' and asset.get('state')=='uploaded' for asset in assets):
        raise ValueError('Existing release checksum sidecar is missing')


def publish(api,command,repository,commit,ref,folder,slug,channel,label,digest,dist):
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository)
        or not re.fullmatch(r'[a-f0-9]{40}',commit)
        or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}',folder)
        or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',slug)
        or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?',label)
        or channel not in ('beta','release') or not re.fullmatch(r'[a-f0-9]{64}',digest)):
        raise ValueError('Invalid publishing identity/input')
    beta=channel=='beta'
    tag=slug+'-'+label if beta else slug+'-v'+label
    if beta:
        if ref!='refs/heads/beta' or not label.endswith('-beta.'+commit[:7]):
            raise ValueError('Beta publishing requires beta and the current commit label')
        relation=api(f'repos/{repository}/compare/{commit}...beta')
        if relation.get('status') not in ('ahead','identical'):
            raise ValueError('Snapshot commit is outside beta history')
    else:
        # A push to release tags its own head (the publisher creates the tag); a pushed tag must name this version.
        if ref not in ('refs/tags/'+tag,'refs/heads/release'):raise ValueError('Production tag mismatch')
        check_release(api,repository,ref,commit)  # Recheck after build, before any write.
    path=Path(dist)
    filename=f'{folder}-{label}.zip'
    zip_path=path/filename
    if not zip_path.is_file() or hashlib.sha256(zip_path.read_bytes()).hexdigest()!=digest:
        raise ValueError('Package bytes do not match declared SHA-256')
    sidecar=path/(filename+'.sha256')
    if sidecar.read_text().strip()!=digest+'  '+filename:
        raise ValueError('Package sidecar does not describe these bytes')
    notes=path/'notes.md'
    if not notes.is_file():raise ValueError('Release notes missing')
    existing=optional(api,f'repos/{repository}/releases/tags/{tag}')
    if existing:
        verify_existing(api,repository,existing,tag,commit,filename,digest,beta)
    else:
        # A pre-existing tag must also match; --target does not retarget existing tags.
        if optional(api,f'repos/{repository}/git/ref/tags/{tag}') and resolve_tag(api,repository,tag)!=commit:
            raise ValueError('Pre-existing tag points elsewhere')
        flags=['--target',commit,'--title',folder+' '+label,'--notes-file',str(notes)]
        if beta:flags+=['--prerelease','--latest=false']
        command(['gh','release','create',tag,str(zip_path),str(sidecar),*flags])
    rolling=False
    if beta:
        rolling_tag=slug+'-beta'
        previous=optional(api,f'repos/{repository}/releases/tags/{rolling_tag}')
        advance=True
        if previous:
            previous_sha=resolve_tag(api,repository,rolling_tag)
            relation=api(f'repos/{repository}/compare/{previous_sha}...{commit}').get('status')
            if relation=='behind': advance=False
            elif relation not in ('ahead','identical'):
                raise ValueError('Rolling beta has divergent history; inspect before replacing it')
        if advance:
            alias=f'{folder}-beta.zip'
            shutil.copyfile(zip_path,path/alias)
            (path/(alias+'.sha256')).write_text(digest+'  '+alias+'\n')
            if previous:
                command(['gh','release','delete',rolling_tag,'--cleanup-tag','--yes'])
            command(['gh','release','create',rolling_tag,str(path/alias),str(path/(alias+'.sha256')),
                str(zip_path),str(sidecar),'--target',commit,'--prerelease','--latest=false',
                '--title',folder+' beta ('+label+')','--notes-file',str(notes)])
            rolling=True
    result={'tag':tag,'sha256':digest,'source_sha':commit,'existing_verified':bool(existing),'rolling_updated':rolling}
    print(json.dumps(result))
    return result


def main():
    def api(path):
        result=subprocess.run(['gh','api',path],text=True,capture_output=True)
        if result.returncode:
            if 'HTTP 404' in result.stderr:raise MissingResource('GitHub resource missing')
            raise RuntimeError('GitHub metadata verification failed; no unverified publication is allowed')
        return json.loads(result.stdout)
    def command(args):
        subprocess.run(args,check=True)  # GH_REPO is fixed to the validated caller repository below.
    repository=os.environ['GITHUB_REPOSITORY']
    os.environ['GH_REPO']=repository
    publish(api,command,repository,os.environ['GITHUB_SHA'],os.environ['GITHUB_REF'],
        os.environ['MOD_FOLDER'],os.environ['SLUG'],os.environ['CHANNEL'],os.environ['LABEL'],os.environ['SHA256'],'dist')


if __name__=='__main__':main()
