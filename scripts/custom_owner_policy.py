"""Reviewable custom-policy builder. Not wired to scheduled apply until pilot succeeds."""
from scripts.branch_policy import ruleset, review
from scripts.owner_check_service import CHECK


def policies(checks, app_id):
    if not isinstance(app_id, int) or isinstance(app_id, bool) or app_id <= 0 or app_id == 15368:
        raise ValueError('Verified dedicated GitHub App integration ID required')
    status = {'type': 'required_status_checks', 'parameters': {
        'strict_required_status_checks_policy': True,
        'required_status_checks': [{'context': c, 'integration_id': 15368} for c in checks if c != CHECK]
                                 + [{'context': CHECK, 'integration_id': app_id}]}}
    return [ruleset('Meitou custom owner policy', branches, [
        {'type': 'deletion'}, {'type': 'non_fast_forward'}, review(count, False), status])
        for branches, count in [(['beta', 'main'], 0), (['release'], 1)]]
