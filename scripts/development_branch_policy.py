"""Approved development and production branch policy, revision 6."""
import copy
from scripts.apply_release_policy import discover_repositories, optional, GitHubFailure
from scripts.branch_policy import ORG, TEAM, ruleset
from scripts.interim_review_policy import TEAM_ID, CUSTOM_CHECKS, review, capability_probe
from scripts.release_gate import RELEASE_TEAM, RELEASE_TEAM_ID, release_bypass

SAFETY = 'Meitou mandatory PR and CI'
BETA = 'Meitou beta maintainer review'
STABLE = 'Meitou main and release approval'
NAMES = {SAFETY, BETA, STABLE, 'Meitou production compatibility'}
BRANCHES = ('beta', 'main', 'release')
VERSION = 6


def policies(checks, release_team_id):
    """Development CI on beta/main; production compatibility on release."""
    if not checks:
        raise ValueError('A mandatory CI context is required')
    required=[]
    for check in checks:
        item={'context':check,'integration_id':15368} if isinstance(check,str) else copy.deepcopy(check)
        if item['context'] not in CUSTOM_CHECKS and item not in required:
            required.append(item)
    if not required: raise ValueError('No non-pilot CI checks')
    pr={'type':'pull_request','parameters':{
        'required_approving_review_count':0,'require_code_owner_review':False,
        'dismiss_stale_reviews_on_push':False,'require_last_push_approval':False,
        'required_review_thread_resolution':False,'require_extra_approval_for_unattributed_changes':False}}
    required = [c for c in required if c['context'] not in ('Release readiness', 'Development readiness')]
    required.append({'context': 'Development readiness', 'integration_id': 15368})
    stable_review = copy.deepcopy(pr)
    stable_review['parameters'].update(required_approving_review_count=2,
        require_code_owner_review=True, dismiss_stale_reviews_on_push=True)
    return [ruleset(SAFETY,list(BRANCHES),[
        {'type':'deletion'},{'type':'non_fast_forward'},pr,
        {'type':'required_status_checks','parameters':{'strict_required_status_checks_policy':False,
          'required_status_checks':required}}]),
        ruleset(BETA,['beta'],[copy.deepcopy(pr)]),
        ruleset(STABLE,['main','release'],[stable_review]),
        ruleset('Meitou production compatibility',['release'],[
            {'type':'required_status_checks','parameters':{'strict_required_status_checks_policy':True,
             'required_status_checks':[{'context':'Release readiness','integration_id':15368}]}}])]


def validate_policy(actual, wanted):
    for field in ('name','target','enforcement','bypass_actors','conditions'):
        if actual.get(field)!=wanted[field]:raise ValueError('Policy read-back mismatch: '+field)
    for rule in wanted['rules']:
        candidate=next((r for r in actual['rules'] if r['type']==rule['type']),None)
        if candidate is None:raise ValueError('Missing required rule')
        for key,value in rule.get('parameters',{}).items():
            if candidate.get('parameters',{}).get(key)!=value:raise ValueError('Required rule parameter not retained: '+key)


def synchronize(api, plan, apply=False):
    if plan.get('policy_version')!=VERSION:raise ValueError(f'Explicit permanent policy revision {VERSION} required')
    if plan.get('release_bypass_team')!=RELEASE_TEAM:raise ValueError('Plan must name the release bypass team')
    team=api(f'orgs/{ORG}/teams/{TEAM}')
    if team['id']!=TEAM_ID:raise ValueError('Unexpected super-maintainers team')
    members=api(f'orgs/{ORG}/teams/{TEAM}/members?per_page=100')
    if not members or len(members)>=100:raise ValueError('Incomplete team member inventory')
    release_team=api(f'orgs/{ORG}/teams/{RELEASE_TEAM}')
    release_team_id=release_team.get('id')
    if release_team_id!=RELEASE_TEAM_ID or RELEASE_TEAM_ID==TEAM_ID:
        raise ValueError('Unexpected release bypass team')
    release_members=api(f'orgs/{ORG}/teams/{RELEASE_TEAM}/members?per_page=100')
    if not release_members or len(release_members)>=100:raise ValueError('Incomplete release team member inventory')
    configured={r['repository']:r for r in plan['repositories']}
    selected=discover_repositories(api,[])
    for item in selected:
        if item['repository'] in configured:
            item['checks']=configured[item['repository']]['checks']
    prepared=[]
    for item in selected:
        repo=item['repository']
        meta=api(f'repos/{repo}')
        if meta['owner']['id']!=357134506 or meta.get('private'):raise ValueError('Unexpected owner or private repository')
        api(f'repos/{repo}/actions/permissions')
        assigned=api(f'repos/{repo}/teams?per_page=100')
        if len(assigned)>=100:raise ValueError('Incomplete team assignment inventory')
        writers={t['id'] for t in assigned if t.get('permission') in ('push','maintain','admin')}
        grants=[slug for slug,tid in ((TEAM,TEAM_ID),(RELEASE_TEAM,release_team_id)) if tid not in writers]
        listing=api(f'repos/{repo}/rulesets?includes_parents=true&per_page=100')
        if len(listing)>=100:raise ValueError('Incomplete ruleset inventory')
        if any(r.get('source_type')=='Organization' for r in listing):
            raise ValueError('Inherited org rules require coordinated migration before per-repo changes')
        existing=[api(f'repos/{repo}/rulesets/{r["id"]}') for r in listing]
        checks=[]
        # Preserve existing build/security checks; bootstrap new repos with their configured CI contexts.
        for rule in [r for rs in existing for r in rs['rules'] if r['type']=='required_status_checks']:
            checks.extend(c for c in rule['parameters']['required_status_checks'] if c['context'] not in CUSTOM_CHECKS)
        if not checks:checks=item['checks']
        desired=policies(checks,release_team_id)
        operations=[]
        for slug in grants:operations.append(('PUT',f'orgs/{ORG}/teams/{slug}/repos/{repo}',{'permission':'push'}))
        for wanted in desired:
            matches=[r for r in existing if r['name']==wanted['name']]
            if len(matches)>1:raise ValueError('Duplicate permanent policy')
            old=matches[0] if matches else None
            operations.append(('PUT' if old else 'POST',f'repos/{repo}/rulesets'+('/'+str(old['id']) if old else ''),wanted))
        # New safety/review rules go first; remove old overlapping review/check constraints afterward.
        for old in existing:
            if old['name'] in NAMES:continue
            if old.get('target')!='branch':raise ValueError('Non-branch ruleset needs separate review')
            refs=old.get('conditions',{}).get('ref_name',{})
            include=[('refs/heads/'+meta['default_branch']) if b=='~DEFAULT_BRANCH' else b for b in refs.get('include',[])]
            if refs.get('exclude') or not set(include).issubset({'refs/heads/'+b for b in BRANCHES}):
                raise ValueError('Custom scope needs explicit migration to leave ordinary branches unprotected')
            remaining=[r for r in old['rules'] if r['type'] not in ('pull_request','required_status_checks','deletion','non_fast_forward')]
            replacement={k:copy.deepcopy(old[k]) for k in ('name','target','enforcement','conditions')}
            replacement.update(rules=remaining,bypass_actors=[])
            operations.append(('PUT' if remaining else 'DELETE',f'repos/{repo}/rulesets/{old["id"]}',replacement if remaining else None))
        branches=api(f'repos/{repo}/branches?per_page=100')
        if len(branches)>=100:raise ValueError('Incomplete branch inventory')
        for b in branches:
            if b.get('protected') and optional(api,f'repos/{repo}/branches/{b["name"]}/protection'):
                raise ValueError('Classic protection requires migration to isolate review bypass from CI')
        prepared.append((repo,operations,desired))
    if apply and prepared:capability_probe(api,prepared[0][0])
    report=[]
    for repo,operations,desired in prepared:
        for method,path,body in operations:
            if apply:
                result=api(path,method=method,body=body)
                if body and body.get('name') in NAMES:
                    validate_policy(api(f'repos/{repo}/rulesets/{result["id"]}'),body)
        report.append({'repository':repo,'applied':apply,'checks':desired[0]['rules'][-1]['parameters']['required_status_checks'],
                       'operations':operations})
    # Templates do not inherit repository settings. Daily discovery provides the free-tier fallback.
    try:
        org_rules=api(f'orgs/{ORG}/rulesets?per_page=100')
        org_status='Organization rules readable; per-repository CI differs, so authoritative rollout uses repository reconciliation.'
    except GitHubFailure as error:
        if error.status not in (403,404):raise
        org_status='Org rules API unavailable; scheduled discovery applies the same policy to new public repositories.'
    return {'policy_version':VERSION,'team':{'id':TEAM_ID,'members':[m['login'] for m in members]},
            'release_team':{'slug':RELEASE_TEAM,'id':release_team_id,'members':[m['login'] for m in release_members]},
            'excluded_repositories':[],'organization_policy':org_status,'repositories':report}
