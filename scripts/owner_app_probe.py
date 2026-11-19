"""Read-only probe for the dedicated App; never posts checks or changes protections."""
import json
import os
from scripts.owner_check_service import app_jwt, token_request, installation_api, paged, ORG_ID


def probe(api, expected_app_id):
    repositories = paged(api, 'installation/repositories', 'repositories')
    public = []
    private_count = 0
    for repo in repositories:
        if repo['owner']['id'] != ORG_ID:
            raise ValueError('Installation contains an unexpected organization')
        if repo.get('private'):
            private_count += 1
            continue
        public.append({'repository': repo['full_name'], 'id': repo['id'], 'archived': repo.get('archived', False)})
    if not public:
        raise ValueError('No public repository access; check installation permission approval')
    return {'app_id': expected_app_id, 'public_repositories': public,
            'private_repositories_skipped': private_count, 'checks_written': 0, 'rules_changed': 0}


def main():
    if os.environ.get('GITHUB_REPOSITORY') != 'TheIvoryDisaster/GutenStructure':
        raise ValueError('Trusted personal repository required')
    app = token_request('app', app_jwt())
    if app['id'] != 5828227 or app['slug'] != 'meitou-owner-authorization':
        raise ValueError('Unexpected App identity')
    installation = token_request('app/installations/' + os.environ['OWNER_APP_INSTALLATION_ID'], app_jwt())
    if installation['account']['id'] != ORG_ID or installation.get('repository_selection') != 'all':
        raise ValueError('Expected all-repository Meitou organization installation')
    permissions = installation['permissions']
    for key in ('contents', 'pull_requests', 'administration', 'members'):
        if permissions.get(key) not in ('read', 'write'):
            raise ValueError('Installation missing required read permission')
    if permissions.get('checks') != 'write':
        raise ValueError('Installation missing Checks write permission')
    result = probe(installation_api(read_only=True), app['id'])
    report = json.dumps(result, indent=2)
    print(report)
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
        summary.write('## Owner App credential probe\n\nRead-only: no checks or protections changed.\n\n```json\n' + report + '\n```\n')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('App probe failed: check key, App/installation IDs and approved permissions. Raw authentication errors are withheld.')
