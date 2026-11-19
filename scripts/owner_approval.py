"""Preview exact owner-author policy. No check writes or protection mutations."""
import argparse
import base64
import json
import os
import re
import urllib.request
import urllib.parse


def pattern_regex(pattern):
    # Deliberately reject unsupported syntax rather than silently misassign ownership.
    if not pattern or any(c in pattern for c in '![]\\'):
        raise ValueError('Unsupported CODEOWNERS pattern; manual review required')
    anchored = pattern.startswith('/') or '/' in pattern.rstrip('/')
    pattern = pattern.lstrip('/')
    directory = pattern.endswith('/')
    pattern = pattern.rstrip('/')
    out = ''
    i = 0
    while i < len(pattern):
        if pattern[i:i+3] == '**/':
            out += '(?:.*/)?'; i += 3
        elif pattern[i:i+2] == '**':
            out += '.*'; i += 2
        elif pattern[i] == '*':
            out += '[^/]*'; i += 1
        elif pattern[i] == '?':
            out += '[^/]'; i += 1
        else:
            out += re.escape(pattern[i]); i += 1
    return re.compile(('^' if anchored else r'^(?:.*/)?') + out + (r'(?:/.*)?$' if directory else r'(?:/.*)?$'))


def parse_owners(text):
    rules = []
    for line in text.splitlines():
        fields = line.split('#', 1)[0].split()
        if not fields:
            continue
        owners = fields[1:]
        if any(not re.fullmatch(r'@[A-Za-z0-9-]+(?:/[A-Za-z0-9_-]+)?', o) for o in owners):
            raise ValueError('Unsupported owner identity')
        rules.append((pattern_regex(fields[0]), [o.lower() for o in owners]))
    if not rules:
        raise ValueError('Missing ownership rules')
    return rules


def evaluate(author, head, branch, files, ownership, reviews, members):
    """members maps validated owner tokens to eligible users with repository write access."""
    if branch not in ('beta', 'main', 'release') or not isinstance(files, list):
        raise ValueError('Expected a protected branch and complete file inventory')
    author = author.lower()
    latest = {}
    for review in sorted(reviews, key=lambda r: r['id']):
        if review['state'] in ('APPROVED', 'CHANGES_REQUESTED', 'DISMISSED'):
            latest[review['user']['login'].lower()] = review
    approvals = {user for user, r in latest.items() if user != author and
                 r['state'] == 'APPROVED' and r.get('commit_id') == head and
                 user in members.get('__writers__', set())}
    if any(r['state'] == 'CHANGES_REQUESTED' for u, r in latest.items()
           if u != author and u in members.get('__writers__', set())):
        return False, ['Outstanding changes requested']
    rules = parse_owners(ownership)
    failures = []
    for path in sorted(set(files)):
        owners = []
        for pattern, identities in rules:
            if pattern.fullmatch(path):
                owners = identities
        eligible = set().union(*(set(members.get(o, ())) for o in owners)) if owners else set()
        if not eligible.intersection(approvals | {author}):
            failures.append('Missing owner authorization: ' + path)
    if branch == 'release' and not approvals:
        failures.append('Release needs a current non-author approval')
    return not failures, failures


def preview(repo, number, api):
    if repo.split('/')[0] != 'Meitou-Modding-Ecosystem':
        raise ValueError('Repository outside authorized organization')
    metadata = api('repos/' + repo)
    if metadata['owner']['id'] != 357134506 or metadata.get('private'):
        raise ValueError('Unexpected repository identity/visibility')
    root = 'repos/' + repo
    def pages(path):
        result = []
        for page in range(1, 101):
            batch = api(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
            result.extend(batch)
            if len(batch) < 100:
                return result
        raise ValueError('Pagination limit reached')
    pr = api(f'{root}/pulls/{number}')
    if pr['state'] != 'open':
        raise ValueError('PR must be open')
    base = pr['base']['sha']; head = pr['head']['sha']
    content = None
    for path in ('.github/CODEOWNERS', 'CODEOWNERS', 'docs/CODEOWNERS'):
        try:
            content = api(f'{root}/contents/{path}?ref={base}')
            break
        except Exception as error:
            if getattr(error, 'code', None) != 404:
                raise
    if content is None:
        raise ValueError('Missing target-branch CODEOWNERS')
    errors = api(f'{root}/codeowners/errors?ref={base}')
    if errors.get('errors'):
        raise ValueError('GitHub reports invalid target-branch CODEOWNERS')
    ownership = base64.b64decode(content['content']).decode('utf-8')
    files = pages(f'{root}/pulls/{number}/files')
    if len(files) != pr['changed_files']:
        raise ValueError('Incomplete changed file inventory')
    paths = [f['filename'] for f in files] + [f['previous_filename'] for f in files if 'previous_filename' in f]
    reviews = pages(f'{root}/pulls/{number}/reviews')
    members = {'__writers__': set()}
    tokens = {o for _, owners in parse_owners(ownership) for o in owners}
    for token in tokens:
        if '/' in token:
            org, slug = token[1:].split('/')
            if org.lower() != 'meitou-modding-ecosystem':
                raise ValueError('Owner team outside organization')
            team = api(f'orgs/{org}/teams/{slug}')
            assigned = pages(f'{root}/teams')
            if team.get('privacy') == 'secret' or not any(t['id'] == team['id'] and t.get('permission') in ('push', 'maintain', 'admin') for t in assigned):
                raise ValueError('Code-owner team must be visible with explicit repository write access')
            users = [u['login'].lower() for u in pages(f'orgs/{org}/teams/{slug}/members')]
        else:
            users = [token[1:]]
        eligible = set()
        for user in users:
            permission = api(f'{root}/collaborators/{user}/permission')['permission']
            if permission in ('write', 'maintain', 'admin'):
                eligible.add(user); members['__writers__'].add(user)
        members[token] = eligible
    for review in reviews:
        user = review['user']['login'].lower()
        if api(f'{root}/collaborators/{user}/permission')['permission'] in ('write', 'maintain', 'admin'):
            members['__writers__'].add(user)
    ok, reasons = evaluate(pr['user']['login'], head, pr['base']['ref'], paths, ownership, reviews, members)
    current = api(f'{root}/pulls/{number}')
    if (current['head']['sha'], current['base']['sha']) != (head, base):
        raise ValueError('PR changed during evaluation; retry')
    return {'repository': repo, 'pr': number, 'head': head, 'base': base,
            'policy_passed': ok, 'reasons': reasons, 'enforced': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('repository'); parser.add_argument('pr', type=int)
    args = parser.parse_args()
    token = os.environ['OWNER_POLICY_TOKEN']
    def api(path):
        request = urllib.request.Request('https://api.github.com/' + path,
            headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    print(json.dumps(preview(args.repository, args.pr, api), indent=2))


if __name__ == '__main__':
    main()
