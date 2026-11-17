"""Reconcile explicit branch tiers without granting release bypass."""
import base64
import copy
from scripts.apply_release_policy import GitHubFailure, discover_repositories, optional, validate_plan

ORG = 'Meitou-Modding-Ecosystem'
TEAM = 'super-maintainers'
MANAGED = {'Stable branch protection', 'Release promotion', 'Meitou branch safety', 'Meitou owner review'}


def review(count, owner, last_push=False):
    return {'type':'pull_request','parameters':{'required_approving_review_count':count,
        'dismiss_stale_reviews_on_push':True, 'require_code_owner_review':owner,
        'require_last_push_approval':last_push, 'required_review_thread_resolution':True}}


def ruleset(name, branches, rules, bypass=None):
    return {'name':name,'target':'branch','enforcement':'active','bypass_actors':bypass or [],
        'conditions':{'ref_name':{'include':['refs/heads/'+branch for branch in branches],'exclude':[]}},'rules':rules}


def policies(checks, team_id):
    if not isinstance(team_id,int) or isinstance(team_id,bool) or team_id <= 0:
        raise ValueError('A verified super-maintainers team ID is required')
    status = {'type':'required_status_checks','parameters':{'strict_required_status_checks_policy':True,
        'required_status_checks':[{'context':check,'integration_id':15368} for check in checks]}}
    return [
        ruleset('Meitou branch safety',['beta','main'],[
            {'type':'deletion'},{'type':'non_fast_forward'},review(0,False),copy.deepcopy(status)]),
        ruleset('Meitou owner review',['beta','main'],[review(1,True)],
            [{'actor_type':'Team','actor_id':team_id,'bypass_mode':'pull_request'}]),
        ruleset('Stable branch protection',['release'],[
            {'type':'deletion'},{'type':'non_fast_forward'},review(2,True,True),copy.deepcopy(status)])]


def organization_templates(team_id):
    result = policies([], team_id)
    for policy in result:
        policy['conditions']['repository_name']={'include':['~ALL'],'exclude':[],'protected':False}
        policy['rules']=[r for r in policy['rules'] if r['type'] != 'required_status_checks']
    return result


def legacy_replacement(existing, default_branch):
    """Remove superseded review/bypass controls while retaining independent security rules."""
    desired={key:copy.deepcopy(existing[key]) for key in ('name','target','enforcement','bypass_actors','conditions','rules')}
    protected={'refs/heads/beta','refs/heads/main','refs/heads/release'}
    refs=desired['conditions']['ref_name']
    includes=refs.get('include',[])
    includes=['refs/heads/'+default_branch if ref=='~DEFAULT_BRANCH' else ref for ref in includes]
    if not set(includes).issubset(protected) or refs.get('exclude'):
        raise ValueError('Unexpected custom branch scope: inspect rather than silently remove it')
    # User explicitly replaced review tiers; keep code scanning/signatures/checks in a separate rule.
    desired['rules']=[r for r in desired['rules'] if r['type'] not in ('pull_request','deletion','non_fast_forward')]
    desired['bypass_actors']=[]
    refs['include']=includes
    return desired if desired['rules'] else None


def synchronize(api, plan, apply=False):
    validate_plan(plan)
    if plan.get('policy_version') != 2 or plan.get('codeowner_self_merge_team') != TEAM:
        raise ValueError('Explicit branch policy revision 2 and selected team are required')
    selected=discover_repositories(api,[r for r in plan['repositories'] if r['repository'].startswith(ORG+'/')])
    # Resolve the selected team using the environment credential, never a guessed numeric ID.
    try:
        team=api(f'orgs/{ORG}/teams/{TEAM}')
    except GitHubFailure as error:
        if error.status not in (403,404): raise
        team=None
        for item in selected:
            try: teams=api(f'repos/{item["repository"]}/teams?per_page=100')
            except GitHubFailure: continue
            team=next((t for t in teams if t.get('slug')==TEAM),None)
            if team: break
        if team is None:
            raise ValueError('Cannot resolve super-maintainers: token needs organization Members read, or repository Administration read access to the team assignment') from None
    if team.get('slug') != TEAM or not isinstance(team.get('id'),int):
        raise ValueError('Unexpected team identity')
    team_id=team['id']
    organization_available=True
    try: api(f'orgs/{ORG}/rulesets?per_page=100')
    except GitHubFailure as error:
        if error.status not in (403,404): raise
        organization_available=False
    prepared=[]
    # Inspect everything before mutation; default-branch and CODEOWNERS gaps are reported explicitly.
    for item in selected:
        repo=item['repository']
        metadata=api(f'repos/{repo}')
        if metadata.get('owner',{}).get('id') != 357134506 or metadata.get('private'):
            raise ValueError('Unexpected repository owner/visibility')
        # This endpoint requires repository Administration read, unlike public rule reads.
        # Catch excluded/new repositories before any settings are written.
        api(f'repos/{repo}/actions/permissions')
        existing=api(f'repos/{repo}/rulesets?includes_parents=false&per_page=100')
        if len(existing)>=100: raise ValueError('Incomplete ruleset inventory')
        details=[api(f'repos/{repo}/rulesets/{r["id"]}') for r in existing]
        desired=policies(item['checks'],team_id)
        gaps=[]
        for branch in ('beta','main','release'):
            if not optional(api,f'repos/{repo}/branches/{branch}'):
                gaps.append(branch+': branch missing (rule still targets future branch)')
                continue
            owners=None
            for path in ('.github/CODEOWNERS','CODEOWNERS','docs/CODEOWNERS'):
                owners=optional(api,f'repos/{repo}/contents/{path}?ref={branch}')
                if owners: break
            text=base64.b64decode(owners['content']).decode() if owners else ''
            if not text: gaps.append(branch+': CODEOWNERS missing; owner-review enforcement incomplete')
            elif f'@{ORG}/{TEAM}' not in text: gaps.append(branch+': selected team is not yet listed in CODEOWNERS')
            if owners and api(f'repos/{repo}/codeowners/errors?ref={branch}').get('errors'):
                gaps.append(branch+': CODEOWNERS errors')
        operations=[]
        for wanted in desired:
            matches=[r for r in details if r['name']==wanted['name'] or wanted['name']=='Stable branch protection' and r['name']=='Release promotion']
            if len(matches)>1: raise ValueError('Duplicate managed rulesets')
            old=matches[0] if matches else None
            # Retain independent additional controls from the old combined ruleset.
            if old:
                for rule in wanted['rules']:
                    if rule['type']=='required_status_checks':
                        old_status=next((r for r in old['rules'] if r['type']=='required_status_checks'),None)
                        if old_status:
                            current=rule['parameters']['required_status_checks']
                            for check in old_status['parameters']['required_status_checks']:
                                if check not in current: current.append(copy.deepcopy(check))
                extra=[r for r in old['rules'] if r['type'] not in {x['type'] for x in wanted['rules']}]
                if extra: wanted['rules'].extend(copy.deepcopy(extra))
            operations.append(('PUT' if old else 'POST',f'repos/{repo}/rulesets'+('/'+str(old['id']) if old else ''),wanted))
        for old in details:
            if old['name'] in MANAGED: continue
            replacement=legacy_replacement(old,metadata['default_branch'])
            operations.append(('PUT' if replacement else 'DELETE',f'repos/{repo}/rulesets/{old["id"]}',replacement))
        # Classic branch protections are separate from rulesets. Inventory first, never silently ignore them.
        classic=[]
        branches=api(f'repos/{repo}/branches?per_page=100')
        if len(branches)>=100: raise ValueError('Incomplete branch inventory')
        for branch in branches:
            if branch.get('protected'):
                protection=optional(api,f'repos/{repo}/branches/{branch["name"]}/protection')
                if protection: classic.append(branch['name'])
        if classic:
            raise ValueError(f'{repo}: classic branch protection also exists; migrate its independent controls before applying rulesets')
        prepared.append((repo,operations,gaps))
    organization_status='Unavailable to the current token; per-repository reconciliation and import templates are the fallback.'
    if apply and organization_available:
        try:
            existing_org=api(f'orgs/{ORG}/rulesets?per_page=100')
            if len(existing_org)>=100: raise ValueError('Incomplete organization ruleset inventory')
            for template in organization_templates(team_id):
                template=copy.deepcopy(template)
                template['name']='Organization '+template['name']
                found=[p for p in existing_org if p['name']==template['name']]
                if len(found)>1: raise ValueError('Duplicate managed organization rulesets')
                path=f'orgs/{ORG}/rulesets'+('/'+str(found[0]['id']) if found else '')
                api(path,method='PUT' if found else 'POST',body=template)
            organization_status='Applied three organization-wide rulesets to all current/future repositories; repository CI rules remain separately enforced.'
        except GitHubFailure as error:
            if error.status not in (403,404,422): raise
            organization_status=f'Organization API returned HTTP {error.status}; do not infer plan support. Per-repository policy remains the fallback; inspect any partially created organization rules.'
    elif organization_available:
        organization_status='Organization rules are readable; apply will attempt all-repository rulesets, subject to write permission and GitHub Team/Enterprise support.'
    report=[]
    for repo,operations,gaps in prepared:
        for method,path,body in operations:
            if apply: api(path,method=method,body=body)
        report.append({'repository':repo,'applied':apply,'operations':operations,'setup_required':gaps})
    return {'policy_version':2,'team':{'slug':TEAM,'id':team_id},
        'organization_rulesets_readable':organization_available,
        'organization_wide_status':organization_status,
        'organization_templates':organization_templates(team_id),'repositories':report}
