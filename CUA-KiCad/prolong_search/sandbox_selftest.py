"""Assertions that the read-isolation sandbox actually isolates.

    python -m prolong_search.sandbox_selftest              # no model, no quota
    python -m prolong_search.sandbox_selftest --with-model # + the codex-layer checks

Companion to `selftest.py`, and for the same reason: the failure mode being guarded
against is the silent one. A sandbox that stops binding -- a renamed dataset directory
that is suddenly outside the checks, a bwrap flag reordered so a bind lands under a
tmpfs, a wrapper that falls back to plain `codex` because `$CODEX_BIN` was not exported
-- produces runs that look exactly like isolated ones and are not. "The agent did not
read the answers" is an audit of one run; "the agent could not" is a property of the
harness, and a property has to be re-checked, not remembered.

**Everything here runs through `codex_sandbox.sh` itself** (via `CODEX_SANDBOX_EXEC`),
not through a second copy of its bwrap arguments. A copy is a second thing to keep in
sync, and it is always the copy the test trusts that drifts.

**What is measured against.** Upstream PRO-LONG runs the agent in a container that
"only mounts the game workspace and, by default, has no network access except a proxy
to the model API". Two properties, and this port matches one of them structurally:

    only the workspace is reachable   -- ours, by mount namespace       [asserted here]
    no network but the API proxy      -- upstream's, by network namespace

The second is delegated to codex's seccomp here rather than owned by the namespace, so
it is checked in the `--with-model` section, where a real agent turn is asked to reach
the network and expected to fail. That costs a model call, which is why it is not the
default -- but a campaign that reports BrowseComp-Plus numbers should have run it, since
an agent with live web access is not answering from the corpus at all.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_WRAPPER = _REPO / "prolong_search" / "codex_sandbox.sh"

import sys as _sys
if str(_REPO) not in _sys.path:
    _sys.path.insert(0, str(_REPO))
from prolong_search.codex_backend import (  # noqa: E402
    EXPECTED_NESTED_TOOLS, SAFE_CODEX_FLAGS,
)

_failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}" + (f"  --  {detail}" if detail else ""))
        _failures.append(name)


def note(text: str) -> None:
    print(f"  --    {text}")


def in_sandbox(workspace: Path, script: str, *, net: bool = False) -> subprocess.CompletedProcess:
    """Run one shell snippet inside the production namespace, from `workspace`.

    `net=False` skips --unshare-net + the egress proxy: the filesystem-isolation probes
    do not need it, and starting a proxy per probe would dominate the run. The network
    checks pass `net=True` to exercise the real default path.
    """
    env = os.environ.copy()
    env["CODEX_SANDBOX_EXEC"] = "/bin/bash"
    env["CODEX_SANDBOX_WORKSPACE"] = str(workspace)
    env["CODEX_SANDBOX_NO_NET"] = "0" if net else "1"
    return subprocess.run(
        [str(_WRAPPER), "-c", script],
        cwd=workspace, env=env, capture_output=True, text=True, timeout=120,
    )


def unreadable(workspace: Path, path: Path) -> tuple[bool, str]:
    """True when `path` cannot be reached from inside. Tested by reading, not by
    stat: a path that stats but cannot be opened is still a leak of its existence,
    and one that opens is a leak of its contents."""
    proc = in_sandbox(workspace, f'cat {json.dumps(str(path))} >/dev/null 2>&1 && echo READ || echo DENIED')
    return proc.stdout.strip().endswith("DENIED"), (proc.stdout + proc.stderr).strip()[-200:]


# ---------------------------------------------------------------------------
# The wrapper is what the evaluators will actually invoke
# ---------------------------------------------------------------------------

def test_wiring() -> None:
    print("\nwiring")
    check("the wrapper exists and is executable",
          _WRAPPER.exists() and os.access(_WRAPPER, os.X_OK), str(_WRAPPER))
    eval_home = Path(os.environ.get("CODEX_EVAL_HOME", str(Path.home() / ".codex-eval")))
    check("a master CODEX_HOME with auth exists",
          (eval_home / "auth.json").exists(),
          f"{eval_home}: the wrapper binds this auth.json read-only into each episode home")
    # The token has a finite life (~1 week when it was measured) and the episode homes
    # get it read-only, so codex cannot refresh it mid-campaign: a campaign longer than
    # the remaining validity needs `codex login` against the master first.
    try:
        import base64, time
        tok = json.loads((eval_home / "auth.json").read_text())["tokens"]["access_token"]
        payload = tok.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        days = (json.loads(base64.urlsafe_b64decode(payload))["exp"] - time.time()) / 86400
        check("the master token is not about to expire", days > 1.0, f"{days:.1f} days left")
        note(f"master token has {days:.1f} days left; it is bound read-only, so codex "
             f"cannot refresh it from inside a sandbox")
    except Exception as e:                                  # auth shape is not ours to own
        note(f"could not read the token's expiry ({e}); check it before a long campaign")

    # `--ignore-user-config` skips config.toml only, so an AGENTS.md in the home codex
    # runs under is still injected into every turn (+3,866 tokens measured).
    check("the master home carries no AGENTS.md",
          not (eval_home / "AGENTS.md").exists(),
          "an AGENTS.md here is injected into every turn")
    user_skills = sorted(p.name for p in (eval_home / "skills").glob("*")
                         if not p.name.startswith("."))
    check("the master home carries no user-installed skills",
          not user_skills, ", ".join(user_skills))
    # Account-level skills/plugins used to reach the model no matter how empty the home
    # started. They are now suppressed per episode by an empty `skills/.system` plus its
    # marker (see codex_sandbox.sh) and by SAFE_CODEX_FLAGS; `--with-model` is what
    # measures the result, so what is left here is a record of what was on the account.
    system_skills = sorted(p.name for p in (eval_home / "skills" / ".system").glob("*")
                           if p.is_dir())
    remote = sorted(p.name for p in
                    (eval_home / "plugins" / "cache").glob("*/*") if p.is_dir())
    if system_skills or remote:
        note(f"the account still has {len(system_skills)} built-in skill(s) {system_skills} "
             f"and {len(remote)} plugin(s) {remote}; suppressed per episode, asserted by "
             f"--with-model")
    # Not under /tmp: codex refuses to create its PATH helpers (its bundled rg among
    # them) in a temporary directory, and the agent loses them without an error.
    check("the master home is not under /tmp",
          not str(eval_home).startswith("/tmp/"), str(eval_home))

    bwrap = os.environ.get("BWRAP_BIN") or shutil.which("bwrap")
    check("bwrap is on PATH", bool(bwrap), "set BWRAP_BIN if it is installed elsewhere")

    # The one that catches a campaign launched without the sandbox at all: the
    # evaluators take the binary from $CODEX_BIN and default to plain `codex`.
    codex_bin = os.environ.get("CODEX_BIN", "")
    check("CODEX_BIN points at the wrapper",
          Path(codex_bin).resolve() == _WRAPPER.resolve() if codex_bin else False,
          f"CODEX_BIN={codex_bin or 'unset'} -- runs would go through plain codex")


# ---------------------------------------------------------------------------
# The isolation itself
# ---------------------------------------------------------------------------

def test_isolation() -> None:
    print("\nisolation (no model calls)")
    root = Path(tempfile.mkdtemp(prefix="sbxtest-", dir=str(_REPO / "runs")))
    ws, sibling = root / "q0000", root / "q0001"
    ws.mkdir(parents=True)
    sibling.mkdir(parents=True)
    (sibling / "secret_doc.txt").write_text("another episode's retrieved document\n")
    outside = root / "outside.txt"
    outside.write_text("host-side file\n")

    try:
        proc = in_sandbox(ws, "echo alive")
        if proc.returncode != 0 or "alive" not in proc.stdout:
            check("the sandbox starts", False, (proc.stderr or proc.stdout)[-300:])
            return
        check("the sandbox starts", True)

        # The answers. These are the whole reason the sandbox exists: with them
        # readable, a score measures retrieval or a `cat`, and nothing distinguishes
        # the two after the fact.
        for label, target in [
            ("BrowseComp-Plus gold answers are unreachable",
             _REPO / "data" / "browsecomp_plus" / "queries_decrypted.jsonl"),
        ]:
            if not target.exists():
                note(f"skipped: {target} is not present on this host")
                continue
            ok, detail = unreadable(ws, target)
            check(label, ok, detail)

        # The evaluator, the grader and the prompts: an agent that can read these can
        # read how it is scored.
        ok, detail = unreadable(ws, _REPO / "eval_prolong_browsecomp_plus.py")
        check("the evaluator source is unreachable", ok, detail)

        # BrowseComp-Plus scopes memory per question. Sibling workspaces have to be
        # invisible or that scoping is a naming convention rather than a fact.
        ok, detail = unreadable(ws, sibling / "secret_doc.txt")
        check("another episode's workspace is unreachable", ok, detail)

        ok, detail = unreadable(ws, outside)
        check("the run directory above the workspace is unreachable", ok, detail)

        # ... while the workspace itself has to work, or the arm cannot run.
        proc = in_sandbox(ws, 'echo payload > note.txt && cat note.txt')
        check("the workspace is readable and writable", proc.stdout.strip().endswith("payload"),
              (proc.stdout + proc.stderr)[-200:])
        check("what the agent writes is visible to the runner",
              (ws / "note.txt").exists())

        proc = in_sandbox(ws, f'echo x > {json.dumps(str(outside.parent / "escaped.txt"))} 2>&1 || true')
        check("writing outside the workspace fails",
              not (outside.parent / "escaped.txt").exists(), proc.stdout[-200:])

        # /tmp is a tmpfs per namespace, so one episode cannot stage anything there
        # for the next one to find.
        proc = in_sandbox(ws, 'echo leak > /tmp/leak.txt && echo wrote')
        check("/tmp is private to the namespace",
              "wrote" in proc.stdout and not Path("/tmp/leak.txt").exists())

        # The toolchain PRO-LONG's mechanism depends on. `python` is the one that bites:
        # the namespace has only /usr/bin/python3, so without sandbox_bin every
        # `python - <<'PY'` the agent writes dies and the arm silently loses the
        # ability being measured. rg comes from codex's own bundle via NODE_DIR.
        proc = in_sandbox(ws, 'for t in python python3 grep sed awk find; do '
                              'command -v $t >/dev/null && echo "$t=yes" || echo "$t=NO"; done')
        for tool in ("python", "python3", "grep", "sed", "awk", "find"):
            check(f"the agent has {tool}", f"{tool}=yes" in proc.stdout,
                  proc.stdout.strip()[-200:])

        # rg is checked by reachability, not by PATH: codex ships its own and puts it on
        # the agent's PATH itself, so a plain shell in this namespace correctly does not
        # have it. What the namespace owes is that the file is inside it -- the earlier
        # BrowseComp-Plus transcripts show the agent reaching for `rg` to grep its log,
        # and a bind that stopped covering it would take that away with no error.
        node_dir = Path(os.environ.get(
            "CODEX_NODE_DIR", str(Path.home() / ".nvm/versions/node/v22.18.0")))
        bundled_rg = next(node_dir.glob(
            "lib/node_modules/@openai/codex/node_modules/@openai/*/vendor/*/codex-path/rg"), None)
        if bundled_rg is None:
            note("codex ships no bundled rg at the expected path; skipping")
        else:
            proc = in_sandbox(ws, f'test -x {json.dumps(str(bundled_rg))} && echo yes || echo NO')
            check("codex's bundled rg is inside the namespace", "yes" in proc.stdout,
                  str(bundled_rg))

    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# The per-episode CODEX_HOME. A shared home is where the judge writes its rollouts --
# carrying [correct_answer] -- and where one question's resumable session lives, so an
# agent that can read the home it runs under can read a previous question's gold answer.
# ---------------------------------------------------------------------------

def test_home_isolation() -> None:
    print("\nper-episode home")
    root = Path(tempfile.mkdtemp(prefix="sbxhome-", dir=str(_REPO / "runs")))
    ws, other = root / "q0000", root / "q0001"
    ws.mkdir(parents=True)
    other.mkdir(parents=True)
    try:
        # Run once so the wrapper materialises this workspace's sibling home.
        in_sandbox(ws, "true")
        home = ws.with_name(ws.name + ".codexhome")
        check("the episode home is a sibling of the workspace, not the shared eval home",
              home.exists() and home.resolve() != Path(
                  os.environ.get("CODEX_EVAL_HOME", str(Path.home() / ".codex-eval"))).resolve(),
              str(home))
        # auth.json on the host side of the home is the 0-byte bind stub, never the token:
        # the real file is bound in read-only and lives only inside the namespace.
        stub = home / "auth.json"
        check("the token is not copied onto disk in the episode home",
              (not stub.exists()) or stub.stat().st_size == 0,
              f"{stub} is {stub.stat().st_size if stub.exists() else 'absent'} bytes")
        # The system-skills marker with an empty dir is what suppresses the account's
        # built-in skills from the tool surface.
        check("the episode home suppresses account skills (empty .system + marker)",
              (home / "skills" / ".system" / ".codex-system-skills.marker").exists()
              and not any((home / "skills" / ".system").glob("*/SKILL.md")))

        # Seed a *neighbouring* episode's home with a fake gold rollout, then assert the
        # agent in ws cannot read it -- the whole point of per-episode homes.
        other_home = other.with_name(other.name + ".codexhome")
        (other_home / "sessions").mkdir(parents=True)
        gold = other_home / "sessions" / "rollout-fake.jsonl"
        gold.write_text('{"payload":{"content":"[correct_answer]: 42"}}\n')
        ok, detail = unreadable(ws, gold)
        check("another episode's home (its judge/gold rollouts) is unreachable", ok, detail)
        # And the master eval home, where the account's real auth and sessions live.
        eval_home = Path(os.environ.get("CODEX_EVAL_HOME", str(Path.home() / ".codex-eval")))
        if eval_home.exists():
            ok, detail = unreadable(ws, eval_home / "auth.json")
            check("the master eval home is not mounted into an episode sandbox", ok, detail)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# The one route out. Upstream's container has "no network except a proxy to the model
# API"; here that is --unshare-net plus an allowlisting proxy on a unix socket. This is
# the layer the earlier version of the wrapper did NOT own -- it is now structural, and
# checked without a model.
# ---------------------------------------------------------------------------

def _probe_url(allow: str) -> str:
    """The first allowlisted destination, as a URL curl can be pointed at.

    Entries are `host:port`, and a leading dot means "and its subdomains" -- neither
    is a hostname curl can resolve, so the dot is dropped and the scheme comes from
    the port. Falls back to the wrapper's own default when the allowlist is unset.
    """
    first = next((e.strip() for e in allow.split(",") if e.strip()), "") or "chatgpt.com:443"
    host, _, port = first.rpartition(":")
    host = (host or first).lstrip(".")
    scheme = "https" if port == "443" else "http"
    return f"{scheme}://{host}:{port}/" if port not in ("443", "") else f"https://{host}/"


def test_network() -> None:
    print("\nnetwork (namespace + egress proxy, no model)")
    root = Path(tempfile.mkdtemp(prefix="sbxnet-", dir=str(_REPO / "runs")))
    ws = root / "q0000"
    ws.mkdir(parents=True)
    try:
        proc = in_sandbox(ws, r'cat /proc/net/dev | awk "NR>2{print \$1}" | tr -d :',
                          net=True)
        ifaces = proc.stdout.split()
        check("the namespace has only loopback", ifaces == ["lo"], str(ifaces))

        proc = in_sandbox(ws, 'getent hosts chatgpt.com >/dev/null 2>&1 && echo DNS || echo NODNS',
                          net=True)
        check("the namespace has no DNS (nothing resolves without the proxy)",
              "NODNS" in proc.stdout, proc.stdout.strip()[-120:])

        # curl inherits HTTPS_PROXY, so even a naive fetch is funnelled through the
        # allowlist: the model API host tunnels (a TLS handshake, hence a 4xx from the
        # app, not a connection error), an off-list host is refused by the proxy.
        #
        # Which host that is comes from the allowlist the run will actually use, not
        # from a constant. A local-server campaign sets CODEX_SANDBOX_ALLOW to its own
        # endpoint, and probing chatgpt.com there measures the wrong thing twice: it
        # reports FAIL for a correctly-configured sandbox, and it never checks that the
        # host the agent has to reach is reachable.
        allow_url = _probe_url(os.environ.get("CODEX_SANDBOX_ALLOW", ""))
        proc = in_sandbox(
            ws,
            f'echo allow=$(curl -s -o /dev/null -w "%{{http_code}}" --max-time 20 {allow_url}); '
            'echo deny=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 https://example.com/)',
            net=True)
        out = proc.stdout
        check("the model API host is reachable through the proxy",
              "allow=" in out and out.split("allow=")[1][:3] not in ("000", ""),
              out.strip()[-160:])
        check("an off-allowlist host is refused (000, proxy denied the CONNECT)",
              "deny=000" in out, out.strip()[-160:])
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# The layer the namespace does not own
# ---------------------------------------------------------------------------

def test_with_model(model: str) -> None:
    print("\ncodex layer (one model call)")
    root = Path(tempfile.mkdtemp(prefix="sbxmodel-", dir=str(_REPO / "runs")))
    try:
        ws = root / "q0000"
        ws.mkdir(parents=True)
        prompt = (
            "Diagnostic. Do exactly this and report plainly, no files:\n"
            "1) Using the exec tool run `text(JSON.stringify(ALL_TOOLS.map(t=>t.name)))` "
            "and report the JSON array verbatim on one line prefixed `TOOLS=`.\n"
            "2) Name any tool you can call OUTSIDE exec (spawn_agent, a web search, an "
            "apps/connector). If none, write `OUTSIDE=none`.\n"
            "3) If you have ANY web or browse capability, use it to fetch example.com and "
            "report the HTTP status; otherwise write `WEB=none`.\n"
            "4) Run `cat " + str(_REPO / "eval_prolong_browsecomp_plus.py") + " | head -c 40` and "
            "report the exact output or error, prefixed `EVAL=`."
        )
        env = os.environ.copy()
        env.pop("CODEX_SANDBOX_EXEC", None)
        env["CODEX_SANDBOX_WORKSPACE"] = str(ws)
        # Exactly the args CodexTurn emits, SAFE_CODEX_FLAGS included: the tool surface is
        # a property of the flags, so a test that omitted them would measure a config
        # production never runs.
        proc = subprocess.run(
            [str(_WRAPPER), "exec", "--json", "--skip-git-repo-check",
             "--ignore-user-config", "--ignore-rules", "-m", model,
             "-c", 'model_reasoning_effort="low"',
             "-c", 'sandbox_mode="workspace-write"',
             *SAFE_CODEX_FLAGS,
             "-o", str(ws / "reply.txt"), "-"],
            cwd=ws, input=prompt, env=env, capture_output=True, text=True, timeout=900,
        )
        reply = (ws / "reply.txt").read_text(encoding="utf-8") if (ws / "reply.txt").exists() else ""
        if not reply:
            check("the probe turn produced a reply", False, (proc.stderr or "")[-300:])
            return
        check("the probe turn produced a reply", True)
        print("\n".join("        " + line for line in reply.strip().splitlines()))
        lowered = reply.lower()

        # The tool surface the model actually saw. Any name outside the whitelist is a
        # capability that reached the model -- a web search, a connector, a sub-agent.
        import re as _re
        m = _re.search(r'TOOLS\s*=\s*(\[[^\]]*\])', reply)
        if m:
            try:
                names = set(json.loads(m.group(1)))
            except Exception:
                names = set(_re.findall(r'"([a-z_]+)"', m.group(1)))
            extra = names - EXPECTED_NESTED_TOOLS
            missing = EXPECTED_NESTED_TOOLS - names
            check("ALL_TOOLS carries no tool beyond the whitelist",
                  not extra, f"unexpected: {sorted(extra)}")
            # Both directions. A tool that DISAPPEARS is as much a change of arm as one
            # that appears, and it fails silently: without `view_image` the analyzer
            # cannot act on the `[FRAME] frames/...` paths its own log is built around,
            # so an episode would answer from text while still reporting itself as the
            # vision arm. `exec_command` is the whole PRO-LONG mechanism; `apply_patch`
            # and `write_stdin` are how it writes its artifact and drives a shell.
            check("ALL_TOOLS still carries every tool the arm depends on",
                  not missing, f"missing: {sorted(missing)}")
        else:
            check("the model reported ALL_TOOLS", False, "no TOOLS= line in the reply")
        check("no web/connector/sub-agent tool is offered outside exec",
              "outside=none" in lowered or "spawn_agent" not in lowered,
              reply[-200:])
        # A 2xx/3xx anywhere means the agent reached the open web.
        check("the agent's shell cannot reach the open web",
              not any(code in reply for code in ("200", "301", "302")),
              "a pass here is the evidence the arm ran without live-web access")
        check("the agent's shell cannot read the evaluator",
              "no such file" in lowered or "cannot open" in lowered or "denied" in lowered
              or "permission" in lowered)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--with-model", action="store_true",
                    help="Also run the codex-layer checks, which cost one model call.")
    ap.add_argument("--model", default=os.environ.get("CODEX_MODEL", "gpt-5.6-sol"))
    args = ap.parse_args()

    (_REPO / "runs").mkdir(exist_ok=True)
    test_wiring()
    test_isolation()
    test_home_isolation()
    test_network()
    if args.with_model:
        test_with_model(args.model)

    print()
    if _failures:
        print(f"{len(_failures)} FAILED: " + ", ".join(_failures))
        return 1
    print("all sandbox checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
