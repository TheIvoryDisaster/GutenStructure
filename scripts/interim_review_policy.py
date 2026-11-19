"""Temporary native team-review policy; Husbandry remains untouched for the custom pilot."""
import copy
from scripts.apply_release_policy import optional, discover_repositories
from scripts.branch_policy import ruleset, TEAM, ORG

NAME = 'Interim super-maintainer approval'
PILOT = ORG + '/Husbandry'
TEAM_ID = 20738063
CUSTOM_CHECKS = {'Meitou owner authorization', 'Meitou owner authorization (pilot)'}


def review(team_id=TEAM_ID):
    return {'type':'pull_request', 'parameters':{
        'required_approving_review_count':1, 'require_code_owner_review':False,
        'dismiss_stale_reviews_on_push':True, 'require_last_push_approval':False,
        'required_review_thread_resolution':False,
        'required_reviewers':[{'file_patterns':['**'], 'minimum_approvals':1,
                               'reviewer':{'id':team_id,'type':'Team'}}]}}


def validate_native(rule):
    actual = next((r for r in rule.get('rules',[]) if r['type']=='pull_request'),None)
    expected = review()['parameters']
    if not actual or any(actual.get('parameters',{}).get(k) != v for k,v in expected.items()):
        raise ValueError('GitHub did not retain the native team-review requirement; do not relax existing rules')


def capability_probe(api, repo):
    desired=ruleset('Temporary team review capability probe',['__team_review_probe__'],[review()])
    desired['enforcement']='disabled'
    result=api(f'repos/{repo}/rulesets',method='POST',body=desired)
    try:
        validate_native(api(f'repos/{repo}/rulesets/{result["id"]}'))
    finally:
        api(f'repos/{repo}/rulesets/{result["id"]}',method='DELETE')


def synchronize(api, plan, apply=False):
    if plan.get('policy_version') != 3:
        raise ValueError('Explicit interim policy revision required')
    team=api(f'orgs/{ORG}/teams/{TEAM}')
    if team['id'] != TEAM_ID: raise ValueError('Selected team identity mismatch')
    members=api(f'orgs/{ORG}/teams/{TEAM}/members?per_page=100')
    if not members or len(members)>=100: raise ValueError('Incomplete/empty team inventory')
    repos=discover_repositories(api,[r for r in plan['repositories'] if r['repository'].startswith(ORG+'/')])
    prepared=[]
    for item in repos:
        repo=item['repository']
        if repo == PILOT: continue
        meta=api(f'repos/{repo}')
        if meta['owner']['id'] != 357134506 or meta.get('private'): raise ValueError('Unexpected repository identity')
        # Prove admin scope before any changes across the selected inventory.
        api(f'repos/{repo}/actions/permissions')
        assigned=api(f'repos/{repo}/teams?per_page=100')
        if len(assigned)>=100 or not any(t['id']==TEAM_ID and t.get('permission') in ('push','maintain','admin') for t in assigned):
            raise ValueError(f'{repo}: super-maintainers needs repository write access')
        listing=api(f'repos/{repo}/rulesets?includes_parents=true&per_page=100')
        if len(listing)>=100: raise ValueError('Incomplete ruleset inventory')
        if any(r.get('source_type')=='Organization' for r in listing):
            raise ValueError('Inherited organization rules need inspection before an interim rollout')
        existing=[api(f'repos/{repo}/rulesets/{r["id"]}') for r in listing]
        classic=[]
        branches=api(f'repos/{repo}/branches?per_page=100')
        if len(branches)>=100: raise ValueError('Incomplete branch inventory')
        for b in branches:
            if b.get('protected'):
                rule=optional(api,f'repos/{repo}/branches/{b["name"]}/protection')
                if rule: classic.append((b['name'],rule))
        target=ruleset(NAME,['beta','main','release'],[review()])
        found=[r for r in existing if r['name']==NAME]
        if len(found)>1: raise ValueError('Duplicate interim policy')
        operations=[('PUT' if found else 'POST',f'repos/{repo}/rulesets'+('/'+str(found[0]['id']) if found else ''),target)]
        for old in existing:
            if old['name']==NAME: continue
            refs=old.get('conditions',{}).get('ref_name',{})
            includes=[('refs/heads/'+meta['default_branch']) if b=='~DEFAULT_BRANCH' else b for b in refs.get('include',[])]
            if not set(includes).issubset({'refs/heads/beta','refs/heads/main','refs/heads/release'}) or refs.get('exclude'):
                raise ValueError(f'{repo}: unexpected ruleset scope requires inspection')
            replacement={k:copy.deepcopy(old[k]) for k in ('name','target','enforcement','conditions','rules')}
            replacement['bypass_actors']=[]
            replacement['rules']=[r for r in replacement['rules'] if r['type']!='pull_request']
            for rule in replacement['rules']:
                if rule['type']=='required_status_checks':
                    rule['parameters']['required_status_checks']=[c for c in rule['parameters']['required_status_checks'] if c['context'] not in CUSTOM_CHECKS]
                    rule['parameters']['strict_required_status_checks_policy']=False
            operations.append(('PUT' if replacement['rules'] else 'DELETE',f'repos/{repo}/rulesets/{old["id"]}',replacement if replacement['rules'] else None))
        for branch,old in classic:
            if branch not in ('beta','main','release'): raise ValueError('Unexpected classic protection scope')
            if old.get('required_pull_request_reviews'):
                operations.append(('PATCH',f'repos/{repo}/branches/{branch}/protection/required_pull_request_reviews',{
                    'required_approving_review_count':1,'require_code_owner_review':False,'require_last_push_approval':False,
                    'dismiss_stale_reviews':True,'bypass_pull_request_allowances':{'users':[],'teams':[],'apps':[]}}))
        prepared.append((repo,operations))
    if apply and prepared:
        capability_probe(api,prepared[0][0])
    report=[]
    for repo,operations in prepared:
        for method,path,body in operations:
            if apply:
                result=api(path,method=method,body=body)
                if body and body.get('name')==NAME:
                    validate_native(api(f'repos/{repo}/rulesets/{result["id"]}'))
        report.append({'repository':repo,'applied':apply,'operations':operations})
    return {'policy_version':3,'excluded_pilot':PILOT,'team_members':[m['login'] for m in members], 'repositories':report}
