"""Prepare the approved development/production gates without replacing repository build jobs."""
import copy
import re
import yaml


class WorkflowLoader(yaml.SafeLoader):
    pass


# YAML 1.1 treats GitHub's `on` key as a boolean.
WorkflowLoader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in values if tag != 'tag:yaml.org,2002:bool']
    for key, values in WorkflowLoader.yaml_implicit_resolvers.items()
}
WorkflowLoader.add_implicit_resolver(
    'tag:yaml.org,2002:bool', re.compile(r'^(?:true|false|True|False|TRUE|FALSE)$'), list('tTfF'))


def aggregate(name, dependencies, production=False):
    script = "import json, os\nresults = json.loads(os.environ['RESULTS'])\n"
    if production:
        script += "target = os.environ['TARGET']\nrequired = list(results) if target == 'release' else ['development-readiness']\n"
    else:
        script += "required = list(results)\n"
    script += "if not required or any(results[key]['result'] != 'success' for key in required):\n    raise SystemExit('A prerequisite failed, was cancelled, or was skipped')\n"
    return {
        'name': name, 'if': 'always()', 'needs': dependencies,
        'runs-on': 'ubuntu-latest', 'timeout-minutes': 5,
        'steps': [{'name': 'Require prerequisite checks',
                   'env': {'RESULTS': '${{ toJSON(needs) }}',
                           'TARGET': '${{ github.base_ref || github.ref_name }}'},
                   'run': "python - <<'PYCODE'\n" + script + 'PYCODE\n'}],
    }


def migrate_ci(content, central_sha, engine_mod=True, package=None):
    if not re.fullmatch('[a-f0-9]{40}', central_sha):
        raise ValueError('Central workflows require an immutable commit')
    workflow = yaml.load(content, Loader=WorkflowLoader)
    jobs = workflow['jobs']
    if 'development-readiness' in jobs:
        raise ValueError('Already migrated; inspect before updating')
    existing_gate = jobs.pop('release-readiness', None)
    required = existing_gate.get('needs', []) if existing_gate else list(jobs)
    if isinstance(required, str):
        required = [required]
    development = [key for key in required if key != 'engine-references']
    if not development or any(key not in jobs for key in development):
        raise ValueError('Cannot determine development prerequisites')
    jobs['development-readiness'] = aggregate('Development readiness', development)
    release_needs = ['development-readiness']
    if engine_mod:
        jobs['upstream-compatibility'] = {
            'uses': f'TheIvoryDisaster/GutenStructure/.github/workflows/upstream-compatibility.yml@{central_sha}'
        }
        release_needs.append('upstream-compatibility')
    if package:
        jobs['package-validation'] = {
            'uses': f'TheIvoryDisaster/GutenStructure/.github/workflows/package-validation.yml@{central_sha}',
            'with': copy.deepcopy(package),
        }
        release_needs.append('package-validation')
    jobs['release-readiness'] = aggregate('Release readiness', release_needs, production=True)
    triggers = workflow.setdefault('on', {})
    for event in ('pull_request', 'push'):
        settings = triggers.setdefault(event, {}) or {}
        branches = settings.get('branches', [])
        settings['branches'] = list(dict.fromkeys([*branches, 'beta', 'main', 'release']))
        triggers[event] = settings
    return yaml.safe_dump(workflow, sort_keys=False, width=120)
