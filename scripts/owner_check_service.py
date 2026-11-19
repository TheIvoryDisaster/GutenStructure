"""Trusted GitHub App check service; never executes or checks out organization code."""
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request
from scripts.owner_approval import preview

ORG_ID = 357134506
CHECK = 'Meitou owner authorization'
BRANCHES = ('beta', 'main', 'release')


def verify_webhook(body, signature, secret):
    if not secret or len(body) > 2 * 1024 * 1024:
        raise ValueError('Missing webhook secret or oversized payload')
    expected = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature or ''):
        raise ValueError('Invalid webhook signature')
    return json.loads(body)


def token_request(path, token, method='GET', data=None):
    if not path or path.startswith('/') or '..' in path:
        raise ValueError('Invalid GitHub API path')
    request = urllib.request.Request('https://api.github.com/' + path,
        data=json.dumps(data).encode() if data is not None else None, method=method,
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'Meitou-owner-check'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def app_jwt():
    # Imported only by the deployed adapter; pure policy tests require no cryptography dependency.
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    def encode(value):
        return base64.urlsafe_b64encode(value).rstrip(b'=')
    now = int(time.time())
    unsigned = b'.'.join(encode(json.dumps(value, separators=(',', ':')).encode()) for value in
                        ({'alg': 'RS256', 'typ': 'JWT'},
                         {'iat': now - 30, 'exp': now + 300, 'iss': os.environ['OWNER_APP_ID']}))
    key = serialization.load_pem_private_key(os.environ['OWNER_APP_PRIVATE_KEY'].encode(), password=None)
    signature = key.sign(unsigned, padding.PKCS1v15(), hashes.SHA256())
    return (unsigned + b'.' + encode(signature)).decode()


def installation_api():
    installation = os.environ['OWNER_APP_INSTALLATION_ID']
    if not installation.isdigit():
        raise ValueError('Invalid installation ID')
    jwt = app_jwt()
    info = token_request('app/installations/' + installation, jwt)
    if info['account']['id'] != ORG_ID or info.get('suspended_at'):
        raise ValueError('App installation outside the approved organization')
    result = token_request('app/installations/' + installation + '/access_tokens', jwt, 'POST', {
        'permissions': {'contents': 'read', 'pull_requests': 'read', 'checks': 'write', 'members': 'read', 'metadata': 'read', 'administration': 'read'}})
    token = result['token']
    return lambda path, method='GET', data=None: token_request(path, token, method, data)


def paged(api, path, key=None):
    values = []
    for page in range(1, 101):
        result = api(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
        batch = result[key] if key else result
        values.extend(batch)
        if len(batch) < 100:
            return values
    raise ValueError('Incomplete pagination')


def evaluate_pr(api, repo, number):
    metadata = api('repos/' + repo)
    if metadata['owner']['id'] != ORG_ID or metadata.get('private'):
        raise ValueError('Only approved public organization repositories are supported')
    root = 'repos/' + repo
    pr = api(f'{root}/pulls/{number}')
    if pr['state'] != 'open' or pr['base']['ref'] not in BRANCHES:
        return None
    head = pr['head']['sha']
    check = api(root + '/check-runs', 'POST', {'name': CHECK, 'head_sha': head,
        'status': 'in_progress', 'external_id': f'{number}:{pr["base"]["sha"]}',
        'output': {'title': 'Evaluating current owner authorization',
                   'summary': 'Target-branch ownership and current-head reviews; no PR code execution.'}})
    try:
        # GitHub checks attach to commits, not PR numbers. A commit can be in beta AND release PRs.
        # Require every protected PR at this head so a beta success cannot authorize a release PR.
        related = [p for p in paged(api, root + '/pulls?state=open')
                   if p['head']['sha'] == head and p['base']['ref'] in BRANCHES]
        if not related:
            raise ValueError('PR inventory changed')
        results = [preview(repo, p['number'], api) for p in related]
        for result in results:
            current = api(f'{root}/pulls/{result["pr"]}')
            if (current['head']['sha'], current['base']['sha']) != (head, result['base']):
                raise ValueError('PR changed during evaluation')
        passed = all(r['policy_passed'] for r in results)
        summary = '\n'.join(f'PR #{r["pr"]}: {reason}' for r in results for reason in r['reasons']) if not passed else 'Every protected PR at this head is authorized, including independent release review where required.'
    except Exception:
        passed = False
        # API failures may contain sensitive resource details: do not echo raw exceptions.
        summary = 'Evaluation unavailable or ownership unsupported. Check trusted service health and ownership configuration; no authorization granted.'
    api(f'{root}/check-runs/{check["id"]}', 'PATCH', {'status': 'completed',
        'conclusion': 'success' if passed else 'failure',
        'output': {'title': 'Owner authorization passed' if passed else 'Owner authorization required',
                   'summary': summary[:60000]}})
    return passed


def scan(api, repository=None):
    repos = [api('repos/' + repository)] if repository else paged(api, 'installation/repositories', 'repositories')
    for repo in repos:
        if repo['owner']['id'] != ORG_ID:
            raise ValueError('Unexpected repository owner')
        if repo.get('private') or repo.get('archived') or repo.get('disabled'):
            continue
        for pr in paged(api, 'repos/' + repo['full_name'] + '/pulls?state=open'):
            if pr['base']['ref'] in BRANCHES:
                evaluate_pr(api, repo['full_name'], pr['number'])


def handle(payload, event, api):
    installation = payload.get('installation', {}).get('id')
    if str(installation) != os.environ['OWNER_APP_INSTALLATION_ID']:
        raise ValueError('Unexpected installation')
    repo = payload.get('repository')
    if repo and (repo['owner']['id'] != ORG_ID or repo.get('private')):
        raise ValueError('Unexpected webhook repository')
    if event in ('pull_request', 'pull_request_review'):
        evaluate_pr(api, repo['full_name'], payload['pull_request']['number'])
    elif event == 'push' and payload.get('ref') in ('refs/heads/beta', 'refs/heads/main', 'refs/heads/release'):
        scan(api, repo['full_name'])
    elif event in ('membership', 'member', 'team', 'team_add', 'installation_repositories', 'installation'):
        scan(api)
