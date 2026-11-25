import unittest
from scripts.development_branch_policy import policies
from scripts.migrate_branch_ci import migrate_ci, WorkflowLoader
import yaml


class DevelopmentPolicyTests(unittest.TestCase):
    def test_development_and_production_are_separate(self):
        safety, beta, stable, production = policies(['Release readiness'], 20828147)
        self.assertEqual(safety['rules'][-1]['parameters']['required_status_checks'],
                         [{'context': 'Development readiness', 'integration_id': 15368}])
        beta_review = next(r for r in beta['rules'] if r['type'] == 'pull_request')
        self.assertEqual(beta_review['parameters']['required_approving_review_count'], 0)
        self.assertEqual(stable['rules'][0]['parameters']['required_approving_review_count'], 2)
        self.assertTrue(stable['rules'][0]['parameters']['require_code_owner_review'])
        self.assertEqual(production['conditions']['ref_name']['include'], ['refs/heads/release'])
        for policy in (safety, stable, production):
            self.assertEqual(policy['bypass_actors'], [])

    def test_beta_keeps_ci_and_lets_actions_merge_through_a_pr(self):
        safety, beta, _, _ = policies(['build / build', 'Release readiness'], 20828147)
        self.assertEqual(safety['conditions']['ref_name']['include'], ['refs/heads/main', 'refs/heads/release'])
        self.assertEqual(beta['conditions']['ref_name']['include'], ['refs/heads/beta'])
        self.assertEqual([r['type'] for r in beta['rules']], [r['type'] for r in safety['rules']])
        self.assertEqual(beta['rules'][-1], safety['rules'][-1])
        self.assertEqual(beta['bypass_actors'], [{'actor_type': 'Integration', 'actor_id': 15368, 'bypass_mode': 'pull_request'}])

    def test_non_compatibility_checks_remain_required(self):
        safety = policies(['build / build', 'CodeQL', 'Release readiness'], 20828147)[0]
        self.assertEqual([c['context'] for c in safety['rules'][-1]['parameters']['required_status_checks']],
                         ['build / build', 'CodeQL', 'Development readiness'])

    def test_migration_preserves_builds_and_diagnostic(self):
        source = '''name: CI
on:
  pull_request:
    branches: [beta]
jobs:
  build:
    runs-on: ubuntu-latest
    steps: [{run: make}]
  engine-references:
    runs-on: ubuntu-latest
    steps: [{run: tools/refcheck.sh}]
  release-readiness:
    needs: [build, engine-references]
'''
        result = yaml.load(migrate_ci(source, 'a' * 40), Loader=WorkflowLoader)
        jobs = result['jobs']
        self.assertEqual(jobs['development-readiness']['needs'], ['build'])
        self.assertIn('engine-references', jobs)
        self.assertEqual(jobs['release-readiness']['needs'], ['development-readiness', 'upstream-compatibility'])
        self.assertEqual(result['on']['pull_request']['branches'], ['beta', 'main', 'release'])
        self.assertEqual(jobs['build']['steps'], [{'run': 'make'}])

    def test_workflow_booleans_keep_their_types(self):
        value = yaml.load('on: {push: null}\nconcurrency: {cancel-in-progress: true}\n', Loader=WorkflowLoader)
        self.assertIn('on', value)
        self.assertIs(value['concurrency']['cancel-in-progress'], True)

    def test_required_skips_fail_and_beta_ignores_upstream(self):
        from scripts.migrate_branch_ci import aggregate
        script = aggregate('Release readiness', [], True)['steps'][0]['run'].split('\n', 1)[1].rsplit('PYCODE', 1)[0]
        import os
        import json
        from unittest.mock import patch
        for target, dev, upstream, succeeds in [
            ('beta', 'success', 'failure', True),
            ('main', 'success', 'cancelled', True),
            ('release', 'success', 'failure', False),
            ('release', 'success', 'skipped', False),
            ('beta', 'skipped', 'success', False),
            ('release', 'success', 'success', True),
        ]:
            with self.subTest(target=target, dev=dev, upstream=upstream):
                values = {'development-readiness': {'result': dev}, 'upstream-compatibility': {'result': upstream}}
                with patch.dict(os.environ, {'TARGET': target, 'RESULTS': json.dumps(values)}):
                    if succeeds:
                        exec(script, {})
                    else:
                        with self.assertRaises(SystemExit):
                            exec(script, {})
