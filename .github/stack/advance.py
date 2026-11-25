"""Put the next part of the video production stack up for review when the part before it is merged upstream.

Run by .github/workflows/stack-advance.yml (every 30 minutes, or by hand). One part per run:
  1. Find the first part whose upstream PR is not merged. Open: wait. Closed without a merge: stop; a person decides.
  2. No PR yet: put the part's own commit (the tip of its fork branch) on upstream main.
  3. Run upstream's test steps on it; count tests and tools on upstream main and on the part.
  4. Push the branch to the fork (only if it still has the old tip) and open the upstream PR with NN.md,
     with the test and tool counts set to the measured numbers.
A step that fails stops the run with an error, and GitHub emails the repo owner.
DRY_RUN=1: steps 1-3 only. PRETEND_MERGED="1 2": these parts count as merged; their commits go on the base first.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
UPSTREAM = "magichourhq/magic-hour-mcp"
FORK_OWNER = "101011101"
DRY = os.environ.get("DRY_RUN") == "1"
PRETEND = {int(x) for x in os.environ.get("PRETEND_MERGED", "").replace(",", " ").split()}
WORK = Path(os.environ.get("STACK_WORK") or tempfile.mkdtemp(prefix="stack-"))
SUMMARY = os.environ.get("GITHUB_STEP_SUMMARY")
SECRET_ENV = ("MAGIC_HOUR_API_KEY", "OPENAI_API_KEY", "BLOB_READ_WRITE_TOKEN", "KEPT_BLOB_READ_WRITE_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")
TEST_ENV = {k: v for k, v in os.environ.items() if k not in SECRET_ENV}

COUNT = """
import asyncio, json, sys, unittest
sys.path.insert(0, '.')
tests = unittest.defaultTestLoader.discover('tests').countTestCases()
from mcp_magichour.openapi_server import create_mcp
m = create_mcp()
async def n():
    try:
        return len(await m.list_tools())
    except AttributeError:
        return len(await m.get_tools())
print(json.dumps({'tests': tests, 'tools': asyncio.run(n())}))
"""


def run(*cmd, cwd=None, check=True, env=None):
    r = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, env=env)
    if check and r.returncode:
        stop(f"`{' '.join(cmd)}` failed (exit {r.returncode}):\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    return r


def git(*a, cwd=None):
    return run("git", *a, cwd=cwd).stdout.strip()


def say(line=""):
    print(line, flush=True)
    if SUMMARY:
        with open(SUMMARY, "a") as f:
            f.write(line + "\n")


def stop(why):
    say(f"STOPPED: {why}")
    sys.exit(1)


def load_parts():
    out = []
    for t in sorted(HERE.glob("[0-9][0-9].title")):
        n = t.stem
        out.append(dict(k=int(n), title=t.read_text().strip(), branch=(HERE / f"{n}.branch").read_text().strip(),
                        body=(HERE / f"{n}.md").read_text()))
    return out


def upstream_pr(branch):
    """The newest upstream PR from the fork's branch, or None."""
    rows = json.loads(run("gh", "pr", "list", "-R", UPSTREAM, "--head", branch, "--state", "all", "--limit", "20",
                          "--json", "number,state,url,createdAt,headRepositoryOwner").stdout)
    rows = [r for r in rows if (r.get("headRepositoryOwner") or {}).get("login") == FORK_OWNER]
    return max(rows, key=lambda r: r["createdAt"]) if rows else None


def tip(part):
    return git("rev-parse", f"origin/{part['branch']}")


def put_on(base, part):
    """Cherry-pick the part's own commit (its branch tip) onto base; return the new commit."""
    t = tip(part)
    msg = git("log", "-1", "--format=%B", t)
    if f"Part {part['k']} of " not in msg:
        stop(f"origin/{part['branch']} ends in {t[:7]}, which is not the Part {part['k']} commit:\n{msg[:300]}")
    name, email = git("log", "-1", "--format=%an%x00%ae", t).split("\0")
    d = tree(base, "pick")
    r = run("git", "-c", f"user.name={name}", "-c", f"user.email={email}", "cherry-pick", t, cwd=d, check=False)
    if r.returncode:
        run("git", "cherry-pick", "--abort", cwd=d, check=False)
        stop(f"Part {part['k']} ({t[:7]}) does not apply cleanly on {base[:7]}:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}"
             "\nUpstream changed lines this part touches. Rebase it by hand, push it, and run this again.")
    return git("rev-parse", "HEAD", cwd=d)


def tree(commit, name):
    d = WORK / name
    if d.exists():
        run("git", "worktree", "remove", "--force", str(d), check=False)
        shutil.rmtree(d, ignore_errors=True)
    git("worktree", "add", "-q", "--detach", str(d), commit)
    return d


def counts(d):
    r = run(sys.executable, "-c", COUNT, cwd=d, env=TEST_ENV)
    return json.loads(r.stdout.strip().splitlines()[-1])


def test(d):
    """Upstream's CI steps (.github/workflows/test.yml) on the tree in d."""
    run("npm", "--prefix", "web", "ci", cwd=d)
    run("npm", "--prefix", "web", "run", "build", cwd=d)
    run(sys.executable, "-m", "pip", "install", "-q", "-e", ".", cwd=d)
    tests = run(sys.executable, "-m", "unittest", "discover", "-s", "tests", cwd=d, env=TEST_ENV, check=False)
    ran = re.findall(r"^Ran (\d+) tests?", tests.stderr, re.M)
    if tests.returncode or not ran:
        stop(f"Upstream's tests fail on the part:\n{tests.stderr[-4000:]}")
    scripts = run(sys.executable, "-m", "unittest", "discover", "-s", "scripts", "-p", "test_*.py", cwd=d, env=TEST_ENV, check=False)
    if scripts.returncode:
        stop(f"Upstream's script tests fail on the part:\n{scripts.stderr[-4000:]}")
    return int(ran[-1])


def set_counts(body, k, ran, new_tests, base_tools, tools):
    """Put the measured counts in the PR text. A tool change other than the part's own is an error."""
    m = re.search(r"(\d+) tests OK, (\d+) new", body)
    if not m:
        stop(f"Part {k} text has no 'N tests OK, M new' line.")
    if int(m.group(2)) != new_tests:
        say(f"Note: the text said {m.group(2)} new tests; measured {new_tests}.")
    body = body[:m.start()] + f"{ran} tests OK, {new_tests} new" + body[m.end():]
    m = re.search(r"Tools: (\d+)(?: → (\d+))?", body)
    if not m:
        stop(f"Part {k} text has no 'Tools:' line.")
    said = int(m.group(2)) - int(m.group(1)) if m.group(2) else 0
    if tools - base_tools != said:
        stop(f"Part {k} should change the tool count by {said}; it changes it by {tools - base_tools} ({base_tools} → {tools}).")
    return body[:m.start()] + (f"Tools: {base_tools} → {tools}" if m.group(2) else f"Tools: {tools}") + body[m.end():]


def advance(part, parts):
    k = part["k"]
    if not DRY and os.environ.get("STACK_TOKEN_SET") != "true":
        stop(f"Part {k} is next, but the STACK_TOKEN secret is not set, so this run cannot push or open a PR.")
    git("fetch", "-q", "upstream", "main")
    base = git("rev-parse", "upstream/main")
    for p in parts:
        if p["k"] in PRETEND:
            base = put_on(base, p)
    old = tip(part)
    new = put_on(base, part)
    say(f"Part {k}: {old[:7]} put on {base[:7]} as {new[:7]}.")
    say("```\n" + git("diff", "--stat", base, new).splitlines()[-1].strip() + "\n```")
    d_new, d_base = tree(new, "part"), tree(base, "base")
    ran = test(d_new)
    shutil.copytree(d_new / "mcp_magichour/static/project-result", d_base / "mcp_magichour/static/project-result", dirs_exist_ok=True)
    c_base, c_new = counts(d_base), counts(d_new)
    if c_new["tests"] != ran:
        say(f"Note: {c_new['tests']} tests counted, {ran} ran.")
    body = set_counts(part["body"], k, ran, ran - c_base["tests"], c_base["tools"], c_new["tools"])
    say(f"Tests: {ran} OK ({ran - c_base['tests']} new). Tools: {c_base['tools']} → {c_new['tools']}.")
    (WORK / "body.md").write_text(body)
    say(f"<details><summary>PR text</summary>\n\n{body}\n</details>")
    if DRY:
        say("Dry run: nothing pushed, no PR opened.")
        return
    git("push", f"--force-with-lease=refs/heads/{part['branch']}:{old}", "origin", f"{new}:refs/heads/{part['branch']}")
    url = run("gh", "pr", "create", "-R", UPSTREAM, "--base", "main", "--head", f"{FORK_OWNER}:{part['branch']}",
              "--title", part["title"], "--body-file", str(WORK / "body.md")).stdout.strip()
    say(f"Opened Part {k}: {url}")


def main():
    if "upstream" not in git("remote").split():
        git("remote", "add", "upstream", f"https://github.com/{UPSTREAM}.git")
    git("fetch", "-q", "origin")
    parts = load_parts()
    for part in parts:
        k = part["k"]
        if k in PRETEND:
            say(f"Part {k}: counted as merged (dry run).")
            continue
        pr = upstream_pr(part["branch"])
        if pr and pr["state"] == "MERGED":
            continue
        if pr and pr["state"] == "OPEN":
            say(f"Part {k} is open for review: {pr['url']}. Nothing to do.")
            return
        if pr:
            stop(f"Part {k} ({pr['url']}) was closed without a merge. A person must decide what comes next.")
        advance(part, parts)
        return
    say(f"All {len(parts)} parts are merged.")


if __name__ == "__main__":
    main()
