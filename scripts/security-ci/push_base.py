"""Resolve a verified prior successful Gitleaks push or pinned full audit."""
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request


WORKFLOW = '.github/workflows/security-audit.yml'
PUSH_STEP = 'Run Gitleaks push range'
FULL_STEPS = {'Run pinned source audit', 'Run Gitleaks on automatic events'}


def resolve(context, api, is_ancestor, bootstrap, project_bootstrap=lambda sha: None):
    current = api(f"/actions/runs/{context['run_id']}")
    repo = context['repository']

    def same_repo(run):
        return (run.get('repository', {}).get('full_name') == repo
                and run.get('head_repository', {}).get('full_name') == repo)

    if (current.get('id') != context['run_id'] or current.get('path') != WORKFLOW
            or current.get('event') != 'push' or not same_repo(current)
            or current.get('head_branch') != context['branch']
            or current.get('head_sha') != context['sha']
            or type(current.get('workflow_id')) is not int
            or type(current.get('run_number')) is not int):
        raise ValueError('current run does not match push checkout')

    def verified(run, allowed_steps, branch_required, project=False):
        sha = run.get('head_sha', '')
        if (run.get('id') == context['run_id'] or run.get('workflow_id') != current['workflow_id']
                or run.get('path') != WORKFLOW or run.get('event') != 'push'
                or not same_repo(run) or run.get('status') != 'completed'
                or run.get('conclusion') != 'success'
                or type(run.get('run_number')) is not int or run['run_number'] >= current['run_number']
                or type(run.get('id')) is not int or type(run.get('run_attempt')) is not int
                or run['run_attempt'] < 1 or not re.fullmatch(r'[0-9a-f]{40}', sha)
                or branch_required and run.get('head_branch') != context['branch']):
            return None
        jobs = api(f"/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs?per_page=100")
        audits = [job for job in jobs if job.get('name') == 'audit']
        if len(audits) != 1:
            return None
        job = audits[0]
        steps = [step for step in job.get('steps', []) if step.get('name') in allowed_steps
                 and step.get('status') == 'completed' and step.get('conclusion') == 'success']
        if (job.get('status') != 'completed' or job.get('conclusion') != 'success'
                or len(steps) != 1):
            return None
        if is_ancestor(sha):
            return sha
        return project_bootstrap(sha) if project else None

    # Incomplete listings or API failures must never lead to an unverified base.
    try:
        branch = urllib.parse.quote(context['branch'], safe='')
        runs = api(f"/actions/workflows/{current['workflow_id']}/runs"
                   f"?branch={branch}&event=push&status=success&per_page=30")
        for run in sorted(runs, key=lambda row: row.get('run_number', 0) if type(row.get('run_number')) is int else 0, reverse=True):
            if sha := verified(run, {PUSH_STEP}, True):
                return sha
    except (OSError, ValueError, KeyError, TypeError):
        pass
    historical = api(f'/actions/runs/{bootstrap}')
    sha = verified(historical, FULL_STEPS, False, project=True) if historical.get('id') == bootstrap else None
    if not sha:
        raise ValueError('no verified ancestor audit')
    return sha


def project_bootstrap(base, head):
    result = subprocess.run(['git', 'merge-base', '--all', base, head],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    bases = result.stdout.splitlines()
    if result.returncode != 0 or len(bases) != 1 or not re.fullmatch(r'[0-9a-f]{40}', bases[0]):
        return None
    check = subprocess.run(['git', 'merge-base', '--is-ancestor', bases[0], head],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return bases[0] if check.returncode == 0 else None


def main():
    env = os.environ
    token = env.get('SECURITY_PUSH_TOKEN', '')
    raw_bootstrap = env.get('SECURITY_PUSH_BOOTSTRAP', '')
    if (not re.fullmatch(r'[1-9][0-9]*', raw_bootstrap) or not token
            or env.get('SECURITY_STAGE') != 'secrets' or env.get('SECURITY_BASE_SHA')
            or env.get('GITHUB_EVENT_NAME') != 'push' or env.get('GITHUB_REF_TYPE') != 'branch'):
        raise ValueError('invalid push audit configuration')
    repo = env['GITHUB_REPOSITORY']
    sha = env['GITHUB_SHA']
    branch = env['GITHUB_REF_NAME']
    event = json.loads(open(env['GITHUB_EVENT_PATH'], encoding='utf-8').read())
    if (not re.fullmatch(r'[0-9a-f]{40}', sha) or event.get('deleted') is not False
            or event.get('ref') != 'refs/heads/' + branch or event.get('after') != sha
            or event.get('repository', {}).get('full_name') != repo):
        raise ValueError('invalid push event')
    def git(*args):
        return subprocess.run(['git', *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              text=True, check=True).stdout.strip()
    if git('rev-parse', '--is-shallow-repository') != 'false' or git('rev-parse', 'HEAD') != sha:
        raise ValueError('checkout must be full and at push SHA')

    api_root = env.get('GITHUB_API_URL', 'https://api.github.com').rstrip('/')
    def api(path):
        request = urllib.request.Request(api_root + '/repos/' + repo + path,
            headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                     'X-GitHub-Api-Version': '2022-11-28'})
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
        if '?' not in path:
            return payload
        if '/jobs?' in path:
            jobs = payload['jobs']
            if not isinstance(jobs, list) or len(jobs) != payload.get('total_count'):
                raise ValueError('incomplete workflow job listing')
            return jobs
        runs = payload['workflow_runs']
        if not isinstance(runs, list):
            raise ValueError('invalid workflow run listing')
        return runs

    def ancestor(base):
        return subprocess.run(['git', 'merge-base', '--is-ancestor', base, sha],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    base = resolve({'repository': repo, 'run_id': int(env['GITHUB_RUN_ID']), 'sha': sha, 'branch': branch},
                   api, ancestor, int(raw_bootstrap), lambda base: project_bootstrap(base, sha))
    with open(env['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write('base_sha=' + base + '\n')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print('push audit coverage could not be verified', file=sys.stderr)
        sys.exit(1)
