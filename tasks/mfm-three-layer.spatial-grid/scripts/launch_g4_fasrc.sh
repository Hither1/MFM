#!/usr/bin/env bash
# The FASRC (SLURM) twin of launch_g4.sh for the two direct baselines, on the same gen-4
# code (MCU worktree MCU-gen4-vista, branch gen4-min-vista = gen4-cc + vista, 6dd70f44)
# and the same OpenRouter route, models and frames. One job per arm; ports and display
# come from the job id (slurm/arm.sbatch); the wall cap is arm_wall.sbatch.
#   bash launch_g4_fasrc.sh direct  dragon    # gpt-5.6-sol high via codex 0.153.4, ender_dragon 100000 steps, WALL 14h
#   bash launch_g4_fasrc.sh direct  diamond   # ... mine_diamond_from_scratch 12000 steps, WALL 24h
#   bash launch_g4_fasrc.sh directc dragon    # claude-opus-5 high via Claude Code 2.1.266
#   bash launch_g4_fasrc.sh directc diamond
#   bash launch_g4_fasrc.sh mfm     diamond   # the MFM arm as gen-4 MIN ran it (launch_g4.sh min): gpt-6-astra high via
#                                             #   codex 0.153.4, the full flag set, one codex thread compacted
#                                             #   (--session-turns 0 --compact), mfm package from MFM main; NO carry
#                                             #   unless SEEDS="/abs/.../episode_001/memory ..." (EXTRA_ONLY semantics)
#   SEEDS="<of3r memory> <of3m memory>" MCU_ROOT=$U/MCU-gen4-carry MFM_ROOT=$U/MFM-sg WALL=24h MEM=100G \
#     bash launch_g4_fasrc.sh mfm nether    # the nether start (task ender_dragon_nether: 1-16 given, of3m's kit),
#                                           #   arm g4_mfm_gpt6_nether_carry; MCU_ROOT/MFM_ROOT/STEPS/WALL/MEM override
#                                           #   the defaults (2026-09-11); a WALL of <N>h sets the job limit to N h + 90 min
#   bash launch_g4_fasrc.sh mfmc    diamond   # the MFM arm on claude-opus-5 high via Claude Code (the directc route
#                                             #   under the mfm flag set); MID=gpt-5.6-sol bash ... mfm diamond runs
#                                             #   the mfm arm on sol (the arm's tag and context window follow MID)
#   SMOKE=150 bash launch_g4_fasrc.sh direct|directc|mfm|mfmc dragon|diamond|nether   # g4smoke_* 150 steps, WALL 40m
#   SUFFIX=v2 ... appends _v2 to the arm name (a second life; the bare name would erase the first)
#   ACCOUNT=nyu bash launch_g4_fasrc.sh mfm|direct ...   # the codex arms through the NYU ChatGPT-plan login
#   ACCOUNT=claude bash launch_g4_fasrc.sh mfmc|directc ...  # the Claude Code arms through this host's logged-in
#                                             #   Claude subscription (MCU_CLAUDE_OAUTH_TOKEN preferred over the live file)
#                                             #   (~/.codex/runtime-home/auth.json, codex 0.153 directly, no OpenRouter);
#                                             #   the default ACCOUNT=openrouter is unchanged (2026-09-12)
#   ABL=noimg|flat|nocons|noprocs bash launch_g4_fasrc.sh mfm|mfmc diamond|dragon   # ONE ablation of the MFM arm (2026-09-19),
#                                             #   the full flag set otherwise; the arm is tagged g4_mfm_<model>_<task>_<abl>:
#                                             #   noimg  = --no-history-images  (without historical images)
#                                             #   flat   = --flat-retrieval     (without structured episode retrieval;
#                                             #            --retrieval is dropped from the flag set, [RECALL] needs the index)
#                                             #   nocons = --no-consolidation   (without long-term consolidation)
#                                             #   noprocs = --no-own-procedures (without agent-written procedures, 2026-09-23:
#                                             #            mine/ kept, no script under mine/procedures/ ever runs)
#                                             #   a comma list (ABL=noimg,flat) stacks them; see worldmodel_purple_agent.py --help
#   MID=... overrides the model id; EXCLUDE=node1,node2 keeps the job off those nodes (two
#   arms on one node share the engine's xvfb-run -a display: never co-schedule); DRY=1 prints.
# Differences from the collab host, all infrastructure: no egress proxy (MCU_OPENROUTER_PROXY
# empty), the CLIs are the FASRC installs (MCU_CODEX_REAL / MCU_CLAUDE_REAL), bwrap+socat are
# system binaries (/usr/bin), and the key file is ~/.codex-eval/openrouter.env.
set -euo pipefail
KIND="${1:?usage: launch_g4_fasrc.sh <direct|directc|mfm|mfmc> <dragon|diamond|nether>}"
TASK_KIND="${2:?usage: launch_g4_fasrc.sh <direct|directc|mfm|mfmc> <dragon|diamond|nether>}"
U="${LAB_USER_ROOT:-/n/holylfs06/LABS/sham_lab/Users/$USER}"
export MCU_ROOT="${MCU_ROOT:-$U/MCU-gen4-vista}" MFM_ROOT="${MFM_ROOT:-$U/MFM}"
KEYFILE="${MCU_OPENROUTER_ENV:-$HOME/.codex-eval/openrouter.env}"
need_key() { [ -r "$KEYFILE" ] || { echo "no readable OpenRouter key file at $KEYFILE" >&2; exit 1; }; }
git -C "$MCU_ROOT" merge-base --is-ancestor 33709cca HEAD || { echo "$MCU_ROOT is not at the gen-4 cc code" >&2; exit 1; }
[ -z "$(git -C "$MCU_ROOT" status --porcelain -- mcu_worldmodel scripts slurm)" ] || { echo "$MCU_ROOT has uncommitted changes under mcu_worldmodel/, scripts/ or slurm/" >&2; exit 1; }
FS="${FRAME_SIZE:-320x180}"; EFF=high
export MCU_OPENROUTER_PROXY=""
AGENT=direct; SESS=(--session-turns 1); BASE="--frame-size $FS"; SEEDARGS=()
# The arm's tag and the codex context window follow the model id (2026-09-12): before, MID=gpt-6-astra
# under `direct` was still tagged sol and would have rm -rf'd g4_direct_sol_<task>'s output.
tag_of() { case "$1" in gpt-5.6-sol) echo sol;; gpt-6-astra) echo gpt6;; claude-opus-5) echo opus;; *) echo "$1" | tr -c 'a-z0-9\n' _;; esac; }
cw_of()  { case "$1" in gpt-5.6-sol) echo 400000;; gpt-6-astra) echo 1050000;; *) echo 400000;; esac; }
MFM_BASE="--expect --frames --retrieval --no-event-sheet --frame-size $FS --thin --minimal --atoms --own --own-reflexes --no-harness-reflexes --skills"
# The codex arms' model channel, by ACCOUNT (2026-09-12): openrouter (default; the key by auth.command
# through the wrapper, openai/<model> at the OpenRouter base URL, the context window by cw_of) or nyu
# (the ChatGPT-plan login every arm's codex home symlinks -- of3r's route on the collab host -- the 0.153
# binary itself, the model by its plain id, no --base-url; codex knows the window). Added when the
# OpenRouter workspace hit its $5000 lifetime budget and every arm on the key stalled at 07:04.
# The Claude Code arms' channel, by ACCOUNT (2026-09-12): openrouter (default; the key by
# apiKeyHelper) or claude (this host's logged-in Claude subscription -- no base_url, the CLI's
# own account). MCU_CLAUDE_OAUTH_TOKEN (from `claude setup-token`) is preferred when set: it is
# immune to the refresh chain the developer's own interactive session also writes to.
claude_route() {
  export MCU_CLAUDE_ROOT="${MCU_CLAUDE_ROOT:-$U/claude-homes}"
  export MCU_CLAUDE_BIN="$MCU_ROOT/scripts/claude-openrouter.sh"
  export MCU_CLAUDE_REAL="${MCU_CLAUDE_REAL:-$HOME/.nvm/versions/node/v24.19.0/bin/claude}"
  export MCU_CLAUDE_SANDBOX_TOOLS=/usr/bin
  case "${ACCOUNT:-openrouter}" in
    openrouter)
      need_key
      export MCU_CLAUDE_ACCOUNT=openrouter MCU_OPENROUTER_ENV="$KEYFILE"
      MODEL="--model anthropic/$MID --reasoning-effort $EFF --base-url https://openrouter.ai/api";;
    claude|nyu)
      unset MCU_CLAUDE_ACCOUNT
      if [ -z "${MCU_CLAUDE_OAUTH_TOKEN:-}" ]; then
        export MCU_CLAUDE_AUTH="${MCU_CLAUDE_AUTH:-$HOME/.claude/.credentials.json}"
        [ -e "$MCU_CLAUDE_AUTH" ] || { echo "no Claude credential at $MCU_CLAUDE_AUTH (claude login, or set MCU_CLAUDE_OAUTH_TOKEN from 'claude setup-token')" >&2; exit 1; }
      fi
      MODEL="--model $MID --reasoning-effort $EFF";;
    *) echo "ACCOUNT must be openrouter, nyu or claude" >&2; exit 2;;
  esac
}
codex_route() {
  case "${ACCOUNT:-openrouter}" in
    openrouter)
      need_key
      export CODEX_BIN="$MCU_ROOT/scripts/codex-openrouter.sh"
      export MCU_CODEX_REAL="$U/codex-node-0.153/bin/codex" MCU_CODEX_AUTH=none
      export CODEX_LOCAL_AUTH_COMMAND="[\"sed\", \"-n\", \"s/^OPENROUTER_API_KEY=//p\", \"$KEYFILE\"]"
      export CODEX_MODEL_CONTEXT_WINDOW="${CODEX_MODEL_CONTEXT_WINDOW:-$(cw_of "$MID")}"
      MODEL="--model openai/$MID --reasoning-effort $EFF --base-url https://openrouter.ai/api/v1";;
    nyu)
      AUTH="${MCU_CODEX_AUTH:-$HOME/.codex/runtime-home/auth.json}"
      [ -e "$AUTH" ] || { echo "no codex login at $AUTH (codex login, then symlink runtime-home/auth.json)" >&2; exit 1; }
      export CODEX_BIN="$U/codex-node-0.153/bin/codex" MCU_CODEX_AUTH="$AUTH"
      unset MCU_CODEX_REAL CODEX_LOCAL_AUTH_COMMAND CODEX_MODEL_CONTEXT_WINDOW
      MODEL="--model $MID --reasoning-effort $EFF";;
    *) echo "ACCOUNT must be openrouter or nyu" >&2; exit 2;;
  esac
}
case "$KIND" in
  mfm)
    AGENT=mfm; CLI=codex; MID="${MID:-gpt-6-astra}"; TAG="$(tag_of "$MID")"
    codex_route
    # launch_g4.sh's BASE for the min arm, verbatim; one thread for the life, compacted by codex.
    BASE="$MFM_BASE"
    SESS=(--session-turns 0 --compact)
    for d in ${SEEDS:-}; do [ -d "$d" ] || { echo "missing seed $d" >&2; exit 1; }; SEEDARGS+=(--seed-memory "$d"); done
    [ -d "$MFM_ROOT/mfm" ] || { echo "$MFM_ROOT carries no mfm package" >&2; exit 1; };;
  mfmc)
    # The MFM arm through Claude Code (the "Opus through Claude Code" rule the logbook/direct opus
    # arms follow, user decision 2026-09-10): directc's route under mfm's flag set and session policy.
    AGENT=mfm; CLI=claude; MID="${MID:-claude-opus-5}"; TAG="$(tag_of "$MID")"
    BASE="$MFM_BASE"
    SESS=(--session-turns 0 --compact)
    for d in ${SEEDS:-}; do [ -d "$d" ] || { echo "missing seed $d" >&2; exit 1; }; SEEDARGS+=(--seed-memory "$d"); done
    [ -d "$MFM_ROOT/mfm" ] || { echo "$MFM_ROOT carries no mfm package" >&2; exit 1; }
    claude_route;;
  direct)
    CLI=codex; MID="${MID:-gpt-5.6-sol}"; TAG="$(tag_of "$MID")"
    codex_route;;
  directc)
    CLI=claude; MID="${MID:-claude-opus-5}"; TAG="$(tag_of "$MID")"
    claude_route;;
  *) echo "kind must be direct, directc, mfm or mfmc" >&2; exit 2;;
esac
case "$TASK_KIND" in
  dragon)  TASK=ender_dragon;             STEPS="${STEPS:-100000}"; WALL="${WALL:-14h}"; TLIM=15:30:00;;
  diamond) TASK=mine_diamond_from_scratch; STEPS="${STEPS:-12000}";  WALL="${WALL:-24h}"; TLIM=25:30:00;;
  # The nether start (2026-09-11, MCU branch gen4-carry-nether): ender_dragon's 24 rules with milestones
  # 1-16 given and of3m_mfm's kit at reset; meant to be run with SEEDS (of3r + of3m records).
  nether)  TASK=ender_dragon_nether;      STEPS="${STEPS:-100000}"; WALL="${WALL:-14h}"; TLIM=15:30:00;;
  *) echo "task must be dragon, diamond or nether" >&2; exit 2;;
esac
# A WALL of the form <N>h gets a job limit of N h + 90 min (the default TLIMs above are 14h/24h + 90 min);
# MEM overrides arm_wall.sbatch's --mem=48G. (Until 2026-09-12 the green's RecordCallback kept every
# 640x360 frame in RAM until the episode ended, ~0.69 MB/step, and every gpt dragon arm died OOM near
# 70k steps; MCU-gen4-vista's recorder now streams the mp4, so 48G holds for a 100k-step life.)
case "$WALL" in *h) H="${WALL%h}"; case "$H" in ''|*[!0-9]*) ;; *) TLIM="$(( (H*60+90)/60 )):$(printf %02d $(( (H*60+90)%60 ))):00";; esac;; esac
ARM="g4_${KIND}_${TAG}_${TASK_KIND}"
# ABL: the MFM ablations, appended to the full flag set (mfm/mfmc only). `flat` also
# removes --retrieval: the [RECALL] block is computed from the index it takes away.
if [ -n "${ABL:-}" ]; then
  case "$KIND" in mfm|mfmc) ;; *) echo "ABL applies to the mfm/mfmc kinds only" >&2; exit 2;; esac
  for a in ${ABL//,/ }; do
    case "$a" in
      noimg)  BASE="$BASE --no-history-images";;
      flat)   BASE="${BASE/--retrieval /}"; BASE="$BASE --flat-retrieval";;
      nocons) BASE="$BASE --no-consolidation";;
      noprocs) BASE="$BASE --no-own-procedures";;
      *) echo "ABL must be a comma list of noimg, flat, nocons, noprocs (got $a)" >&2; exit 2;;
    esac
    ARM="${ARM}_$a"
  done
fi
[ -n "${SEEDS:-}" ] && ARM="${ARM}_carry"
# ARM_SUFFIX=_v2: a second launch of the same arm kind while the first still runs (its output/
# and logs/ are named by ARM, and a codex home too).
ARM="${ARM}${ARM_SUFFIX:-}"
# SUFFIX=v2 names a second life of the same kind: run-arm.sh rm -rfs output/<arm>, so a relaunch
# under the bare name would erase the earlier run.
ARM="${ARM}${SUFFIX:+_$SUFFIX}"
if [ -n "${SMOKE:-}" ]; then STEPS="$SMOKE"; ARM="g4smoke_${KIND}_${TAG}_${TASK_KIND}"; WALL=40m; TLIM=01:30:00; fi
[ -x "${MCU_CODEX_REAL:-/bin/true}" ] && [ -x "${MCU_CLAUDE_REAL:-/bin/true}" ] || { echo "CLI binary missing" >&2; exit 1; }
mkdir -p "$MCU_ROOT/slurm/logs"
SB=(sbatch -J "$ARM" -t "$TLIM" -o "$MCU_ROOT/slurm/logs/%x-%j.out" -e "$MCU_ROOT/slurm/logs/%x-%j.err"
    ${EXCLUDE:+--exclude="$EXCLUDE"} ${MEM:+--mem="$MEM"}
    "$(cd "$(dirname "$0")" && pwd)/arm_wall.sbatch" "$AGENT" "$ARM" "$TASK" "$STEPS" "$WALL"
    --cli "$CLI" "${SESS[@]}" --wm-extra "$MODEL $BASE" "${SEEDARGS[@]}")
echo "arm=$ARM agent=$AGENT cli=$CLI route=${ACCOUNT:-openrouter} model=$MID task=$TASK steps=$STEPS wall=$WALL tlim=$TLIM mcu=$MCU_ROOT @ $(git -C "$MCU_ROOT" rev-parse --short HEAD) mfm=$MFM_ROOT @ $(git -C "$MFM_ROOT" rev-parse --short HEAD)"
echo "  ${SB[*]}"
[ -n "${DRY:-}" ] && exit 0
# The submitting shell is often a Claude Code session; its CLAUDE* identity must not ride
# into the job (the backend scrubs it too, belt and braces).
env -u CLAUDECODE -u CLAUDE_CONFIG_DIR -u CLAUDE_CODE_SESSION_ID "${SB[@]}"
