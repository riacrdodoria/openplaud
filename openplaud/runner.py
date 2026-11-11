"""Bounded executor; deliberately disabled until operator provisions isolation and usage."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from .control import Store


def command(argv, cwd, log, timeout):
    # argv is constructed by this module, never accepted from the panel.
    with open(log, 'ab') as out:
        env = {k:v for k,v in os.environ.items() if k in ('PATH','HOME','CODEX_HOME','LANG','TMPDIR')}
        p = subprocess.Popen(argv, cwd=cwd, stdout=out, stderr=subprocess.STDOUT,
                             start_new_session=True, env=env)
        try:
            return p.wait(timeout=timeout)
        except BaseException:
            os.killpg(p.pid, signal.SIGTERM)
            try: p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            raise


def tick(store, repo, state, config):
    claimed = store.claim()
    if not claimed: return False
    task, run = claimed
    if not config.get('subscription_usage_authorized') or not config.get('isolated_account_verified'):
        store.block(task['id'],run,'Provision isolated service account and authorize subscription usage; no paid API budget configured')
        return True
    with store.db() as c:
        count = c.execute('SELECT count(*) FROM runs WHERE before_sha IS NOT NULL').fetchone()[0]
    if count >= min(int(config.get('max_invocations',0)),10):
        store.block(task['id'],run,'Invocation allowance exhausted')
        return True
    if shutil.disk_usage(state).free < 10 * 1024**3:
        store.block(task['id'],run,'Less than 10 GiB free disk')
        return True
    status = subprocess.run(['codex','login','status'], capture_output=True, text=True)
    if status.returncode or 'Logged in using ChatGPT' not in status.stdout + status.stderr:
        store.block(task['id'],run,'ChatGPT subscription authentication unavailable; reauthenticate isolated account')
        return True
    tree = state / 'trees' / str(run)
    log = state / 'logs' / f'{run}.log'
    log.parent.mkdir(parents=True,exist_ok=True)
    tree.parent.mkdir(parents=True,exist_ok=True)
    before = subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    # A new branch per attempt keeps incomplete changes recoverable.
    subprocess.run(['git','worktree','add','-b',f'work/task-{run}',str(tree),before],cwd=repo,check=True,capture_output=True)
    with store.db() as c:
        c.execute('UPDATE runs SET before_sha=?,log=? WHERE id=?',(before,str(log),run))
    try:
        if (tree/'.codex').exists():
            raise RuntimeError('Project Codex configuration needs operator audit')
        prompt = ('Implement only this task, read AGENTS.md first. No paid APIs, deploy, host changes, '
                  'secrets, production data or destructive commands. If permission needed stop and report. '
                  'Do not edit control plane, acceptance checks, or security configuration. '
                  'Do not commit. Task: '+json.dumps(task,ensure_ascii=False))
        result = command(['codex','exec','--ignore-user-config','--sandbox','workspace-write','--json',prompt],tree,log,
                         min(int(config.get('timeout_seconds',900)),900))
        if result: raise RuntimeError(f'Codex exit {result}; inspect private log')
        with store.db() as c:
            c.execute("UPDATE tasks SET state='TESTING' WHERE id=?",(task['id'],))
        # Generic suite is necessary but insufficient; human review checks task-specific acceptance.
        result = command([sys.executable,'-m','unittest','discover','-s','tests','-v'],tree,log,120)
        if result: raise RuntimeError('Validation failed')
        subprocess.run(['git','add','--all'],cwd=tree,check=True)
        subprocess.run(['git','commit','--allow-empty','-m',f"checkpoint: {task['id']} awaiting acceptance review"],cwd=tree,check=True,capture_output=True)
        after = subprocess.check_output(['git','rev-parse','HEAD'],cwd=tree,text=True).strip()
        store.finish(task['id'],run,'REVIEW',before=before,after=after,log=str(log))
    except Exception as e:
        store.finish(task['id'],run,'FAILED',str(e),before=before,log=str(log))
    return True


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--state',type=Path,required=True)
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--once',action='store_true')
    a=p.parse_args()
    a.state=a.state.resolve(); a.repo=a.repo.resolve()
    a.state.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.umask(0o077)
    with open(a.state/'executor.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        store=Store(a.state/'control.sqlite')
        store.recover()
        store.seed(json.loads((a.repo/'roadmap.json').read_text()))
        while True:
            config=json.loads(a.config.read_text())
            tick(store,a.repo,a.state,config)
            if a.once: break
            time.sleep(5)

if __name__=='__main__': main()
