"""Post non-required, App-owned Husbandry pilot checks from trusted personal automation."""
import json
import os
from scripts import owner_check_service as service

REPO = 'Meitou-Modding-Ecosystem/Husbandry'
REPO_ID = 1462282676


def run(api):
    repo = api('repos/' + REPO)
    if repo.get('id') != REPO_ID or repo.get('owner', {}).get('id') != service.ORG_ID or repo.get('private'):
        raise ValueError('Husbandry pilot repository identity mismatch')
    # Deliberately distinct from the eventual required check until webhook enforcement is live.
    service.CHECK = 'Meitou owner authorization (pilot)'
    prs = service.paged(api, 'repos/' + REPO + '/pulls?state=open')
    results = []
    for pr in prs:
        if pr['base']['ref'] in service.BRANCHES:
            results.append({'pr': pr['number'], 'passed': service.evaluate_pr(api, REPO, pr['number'])})
    return {'repository': REPO, 'repository_id': REPO_ID, 'results': results,
            'enforced': False, 'rules_changed': 0,
            'note': 'Pilot checks only. Refresh after every commit/review until the webhook service is deployed.'}


def main():
    if os.environ.get('GITHUB_REPOSITORY') != 'TheIvoryDisaster/GutenStructure' or os.environ.get('GITHUB_REF') not in ('refs/heads/beta', 'refs/heads/main'):
        raise ValueError('Trusted personal beta/main automation required')
    result = run(service.installation_api())
    report = json.dumps(result, indent=2)
    print(report)
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
        summary.write('## Husbandry custom-owner pilot\n\n```json\n' + report + '\n```\n')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Husbandry pilot failed; inspect trusted App configuration. Raw errors withheld.')
