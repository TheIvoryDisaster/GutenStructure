"""Fetch a public reviewed release ZIP; no platform credentials or uploaded code execution."""
import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from scripts.distribution_plan import MAX_ARCHIVE, inspect_archive, workshop_vdf
from scripts.release_gate import ALLOWED, MissingResource, check


def validate_context(context):
    if (context.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'
            or context.get('GITHUB_REPOSITORY_OWNER') != context.get('GITHUB_ACTOR')
            or context.get('GITHUB_REPOSITORY_OWNER_ID') != context.get('GITHUB_ACTOR_ID')
            or context.get('OWNER_TYPE') != 'User'
            or context.get('GITHUB_REF') != 'refs/heads/' + context.get('DEFAULT_BRANCH', '')):
        raise ValueError('Only the personal repository owner may dispatch from its default branch')


def validate_inputs(repository, tag, commit, asset_id, digest, version, destination, nexus_file, steam_item):
    if repository not in ALLOWED or not repository.startswith('Meitou-Modding-Ecosystem/'):
        raise ValueError('Source repository is outside the reviewed organization allowlist')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,127}', tag):
        raise ValueError('Invalid release tag')
    if not re.fullmatch(r'[a-f0-9]{40}', commit) or not re.fullmatch(r'[a-f0-9]{64}', digest):
        raise ValueError('An exact source commit and SHA-256 are required')
    if not re.fullmatch(r'[1-9][0-9]{0,19}', asset_id):
        raise ValueError('Positive GitHub asset ID required')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}', version):
        raise ValueError('Invalid version')
    if destination not in ('nexus', 'steam', 'both'):
        raise ValueError('Invalid destination')
    for value, needed in ((nexus_file, destination in ('nexus', 'both')), (steam_item, destination in ('steam', 'both'))):
        if needed and not re.fullmatch(r'[1-9][0-9]{0,19}', value):
            raise ValueError('Positive existing destination ID required')


def verify_source(api, repository, tag, commit, asset_id, digest):
    metadata = api(f'repos/{repository}')
    if metadata.get('private') or metadata.get('owner', {}).get('id') != 357134506:
        raise ValueError('Only public repositories under the verified organization are supported')
    release = api(f'repos/{repository}/releases/tags/{tag}')
    if release.get('draft') or release.get('prerelease') or release.get('tag_name') != tag:
        raise ValueError('A published stable GitHub release is required')
    ref = api(f'repos/{repository}/git/ref/tags/{tag}')['object']
    for _ in range(4):
        if ref.get('type') == 'commit':
            break
        if ref.get('type') != 'tag' or not re.fullmatch(r'[a-f0-9]{40}', ref.get('sha', '')):
            raise ValueError('Invalid tag object')
        ref = api(f'repos/{repository}/git/tags/{ref["sha"]}')['object']
    if ref.get('type') != 'commit' or ref.get('sha') != commit:
        raise ValueError('Release tag does not resolve to the approved source commit')
    check(api, repository, 'refs/tags/' + tag, commit)
    # Fetch by ID and separately bind the asset to this release (the release list can paginate).
    asset = api(f'repos/{repository}/releases/assets/{asset_id}')
    found = False
    for page in range(1, 11):
        assets = api(f'repos/{repository}/releases/{release["id"]}/assets?per_page=100&page={page}')
        if any(str(item.get('id')) == asset_id for item in assets):
            found = True
            break
        if len(assets) < 100:
            break
    if not found or str(asset.get('id')) != asset_id or asset.get('state') != 'uploaded':
        raise ValueError('Asset does not belong to the selected release or is not fully uploaded')
    if not asset.get('name', '').lower().endswith('.zip') or not 0 < asset.get('size', 0) <= MAX_ARCHIVE:
        raise ValueError('Release asset must be a bounded ZIP')
    if asset.get('digest') != 'sha256:' + digest:
        raise ValueError('GitHub asset digest must match the author-approved SHA-256')
    expected = f'https://github.com/{repository}/releases/download/{tag}/'
    url = asset.get('browser_download_url', '')
    if not url.startswith(expected) or urllib.parse.urlsplit(url).query or urllib.parse.urlsplit(url).fragment:
        raise ValueError('Unexpected release asset URL')
    return asset


class DownloadRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme != 'https' or target.hostname not in ('github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com') or target.username or target.password or target.port not in (None, 443):
            raise ValueError('Release download redirected outside approved GitHub hosts')
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def fetch_payload(asset, digest, output, opener=None):
    opener = opener or urllib.request.build_opener(DownloadRedirects())
    hasher, count = hashlib.sha256(), 0
    # No Authorization header on release asset requests, including redirects.
    with opener.open(asset['browser_download_url'], timeout=60) as response, Path(output).open('xb') as destination:
        while chunk := response.read(1024 * 1024):
            count += len(chunk)
            if count > MAX_ARCHIVE or count > asset['size']:
                raise ValueError('Release download exceeds its approved size')
            hasher.update(chunk)
            destination.write(chunk)
    if count != asset['size'] or hasher.hexdigest() != digest:
        raise ValueError('Release download size or digest mismatch')
    return inspect_archive(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='publish-payload')
    args = parser.parse_args()
    try:
        validate_context(os.environ)
        names = ['SOURCE_REPOSITORY', 'RELEASE_TAG', 'SOURCE_SHA', 'ASSET_ID', 'EXPECTED_SHA256', 'VERSION', 'DESTINATION', 'NEXUS_FILE_ID', 'STEAM_ITEM_ID']
        values = [os.environ.get(name, '') for name in names]
        validate_inputs(*values)
        repository, tag, commit, asset_id, digest, version, destination, nexus_file, steam_item = values
        def api(path):
            request = urllib.request.Request('https://api.github.com/' + path, headers={
                'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'GutenStructure-author-publisher'})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    raise MissingResource('Required public release resource is missing') from None
                raise ValueError(f'GitHub release verification failed (HTTP {error.code})') from None
        asset = verify_source(api, repository, tag, commit, asset_id, digest)
        output = Path(args.output)
        output.mkdir(mode=0o700, parents=True, exist_ok=False)
        payload = fetch_payload(asset, digest, output / 'release.zip')
        receipt = {'source_repository':repository, 'source_sha':commit, 'release_tag':tag, 'asset_id':asset_id,
                   'version':version, 'sha256':payload['sha256'], 'destination':destination,
                   'nexus_file_id':nexus_file, 'steam_item_id':steam_item, 'uploaded':False}
        (output / 'plan.json').write_text(json.dumps(receipt, indent=2) + '\n')
        if destination in ('steam', 'both'):
            (output / 'workshop-preview.vdf').write_text(workshop_vdf(
                {'app_id':233860, 'published_file_id':int(steam_item)}, '/tmp/verified-mod-content', version))
        print(json.dumps(receipt, indent=2))
    except (ValueError, RuntimeError, KeyError, OSError) as error:
        parser.exit(2, f'Publishing preparation blocked: {type(error).__name__}: {error}\n')


if __name__ == '__main__':
    main()
