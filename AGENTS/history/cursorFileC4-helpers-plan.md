C4 — Public 8-BALL End-User Readiness Pass

Purpose

This C4 task is focused only on making the public 8ball repository fully reliable for an end user running the free 8-BALL installer.

Do not work on the future paid 9.sh upgrade path yet.

The goal is simple:

A user should be able to run the public 8-BALL installer, get Ollama installed, have a right-sized local model selected and tested, receive a useful login/MOTD experience, and have clear commands for using or repairing the trial install.

Scope

This task applies to the public 8-BALL trial installer flow:

trial-install.sh
  -> 8.1.sh
  -> 8.2.sh
  -> 8.3.sh

The public installer must remain clean, straightforward, and supportable.

Core Rule

Do not overbuild.

8-BALL should stay a simple public trial installer that proves the machine can run local AI.

The trial system should:

1. Install the foundation.
2. Install and verify Ollama.
3. Select a conservative local model.
4. Pull and test the selected model.
5. Fall back to a smaller model if needed.
6. Install simple helper commands.
7. Install a clean terminal.glass MOTD.
8. Give the user a fun, memorable, useful first experience.

Do Not Add Yet

Do not implement or stub the future paid upgrade system yet.

Do not add:

9.sh
paid OpenWebUI skins
Passport entitlement checks
RecordsCore integration
S3 paid artifact downloads
license activation
pro install logic
private paid bundles

Those belong to a later phase.

C4 is only about making the public 8-BALL repo excellent for the end user.

Desired End-User Experience

The user should be able to run:

sudo ./trial-install.sh

or:

sudo ./trial-install.sh --model qwen3:4b

The installer should:

1. Show the terminal.glass / 8-BALL branding cleanly.
2. Validate Ubuntu/Debian and root access.
3. Install only minimal required packages.
4. Install Ollama safely.
5. Start and verify Ollama on localhost.
6. Select a model based on RAM, CPU, GPU, and disk.
7. Pull the selected model.
8. Test the model with a real inference call.
9. If the model fails, remove only the newly pulled failed model and try the next smaller candidate.
10. Write the final result to /opt/philosopher/8ball-result.txt.
11. Install the 8balljets helper.
12. Install the remember helper.
13. Install a compact MOTD that shows status and next commands.
14. Leave the user with working local AI.

8.1 Requirements

8.1.sh should remain the foundation script.

It should handle:

/opt/philosopher creation
trial logging
minimal HTTPS prerequisites
conservative optional swap
Ollama installation
Ollama systemd startup
local API verification

It should not configure:

Nginx
TLS
domains
public ports
firewall rules
Passport
S3
paid licensing
customer secrets
OpenWebUI

8.1 must be safe to re-run.

It should reuse an existing Ollama install when present.

It should not make unnecessary public networking changes.

8.2 Requirements

8.2.sh is the model-selection and 8-BALL JETS script.

It should:

1. Verify Ollama is installed and responding.
2. Read hardware capacity:
    * RAM
    * CPU threads
    * free disk
    * GPU name if available
    * GPU VRAM if available
3. Build a conservative candidate model list.
4. Prefer larger models only when the system reasonably supports them.
5. Pull one model at a time.
6. Run a real inference test.
7. Accept the first model that successfully answers.
8. If a newly pulled model fails, remove that model and try the next smaller one.
9. If a requested --model fails, fail clearly instead of silently selecting something else unless the existing logic intentionally supports fallback.
10. Write a clear result file.

The result file should remain stable and easy for later scripts to parse.

Suggested minimum fields:

Model: qwen3:1.7b
Profile: qwen3-1-7b
Tier: LOCAL LITE
Model test: PASSED
Jets status: READY_AFTER_SIGNIN
RAM MB: <value>
CPU threads: <value>
Free disk MB: <value>
GPU: <value>
GPU VRAM MB: <value>

8.2 should also install or refresh the 8balljets helper.

The helper should make it easy for a user to understand cloud-model/Jets options without breaking the local trial.

8.3 Requirements

8.3.sh owns the end-user terminal experience.

It should install:

compact terminal.glass / 8-BALL MOTD
persistent local health alerts
temporary public repo alerts if supported
weekly bulletin refresh if supported
remember helper

Login must not:

contact the network
run model inference
pull models
slow down SSH
require cloud access

The MOTD should be compact, useful, and fun.

It should show:

terminal.glass
😎 Private AI with no more guesswork 😎
SYSTEM STATUS
Ollama ............. RUNNING
Local Model ........ READY
8-BALL JETS ........ READY AFTER SIGN-IN
Local:    ollama run <selected-model>
Status:   cat /opt/philosopher/8ball-result.txt
Upgrade:  sudo remember

If something is wrong, it should show only a short actionable warning.

Examples:

ERROR: Ollama is not responding.
Run: sudo systemctl restart ollama

or:

NOTICE: Only 8 GB of disk remains; future models may not fit.
Review: ollama list | Remove: ollama rm <model>

remember Helper Requirements

The public remember helper is allowed because it is a simple sales/support helper.

It should not activate paid features.

It should simply explain the persistent chat upgrade offer.

It should use the customer-facing email:

8ball@terminal.glass

Do not use:

jonathan@nocloudgpt.com

The helper should tell the user to include the contents of:

/opt/philosopher/8ball-result.txt

when contacting support.

trial-install.sh Requirements

trial-install.sh should remain the public entrypoint.

It should:

1. Parse --model.
2. Parse --no-motd.
3. Parse --raw-base.
4. Validate that the public source is HTTPS.
5. Prefer local bundled scripts when present.
6. Otherwise download public scripts from the configured raw base.
7. Run syntax checks before installing downloaded scripts.
8. Execute 8.1, then 8.2, then 8.3 unless --no-motd is used.
9. Show clear progress messages.
10. Fail cleanly with the log path.

Expected flow:

[1/4] Loading the public 8-BALL components
[2/4] Preparing Ubuntu/Debian and installing Ollama
[3/4] Selecting and testing the local model
[4/4] Installing the terminal.glass login experience

Public Repo Quality Checks

Cursor should inspect the public repo for simple breakage before making design changes.

Check for:

syntax errors
bad characters accidentally pasted into shell variables
missing chmod
wrong helper paths
inconsistent filenames
hardcoded old brand references
wrong customer-facing email
commands that require interactive input
network calls during login
unsafe rm usage
scripts that fail when re-run
scripts that assume GPU exists
model fallback logic that deletes pre-existing user models
MOTD too large or noisy

Pay special attention to accidental non-shell characters in scripts.

For example, remove any stray characters like:

åç

from shell variable lines or version declarations.

Acceptance Criteria

C4 is complete when all of the following are true:

1. bash -n trial-install.sh 8.1.sh 8.2.sh 8.3.sh passes.
2. shellcheck issues are either fixed or documented if intentionally ignored.
3. sudo ./trial-install.sh --no-motd can run through 8.1 and 8.2 on a clean Ubuntu/Debian host.
4. sudo ./trial-install.sh can run through 8.1, 8.2, and 8.3.
5. Ollama is installed and responding locally.
6. A selected model is pulled and tested.
7. /opt/philosopher/8ball-result.txt is written.
8. The MOTD reads the selected model from the result file.
9. The MOTD does not perform network calls.
10. sudo remember works.
11. sudo 8balljets works or gives a clear next-step message.
12. Failed model pulls or failed inference tests do not leave the installer in a confusing state.
13. Re-running the installer does not destroy working user state.
14. The public repo remains free-trial only.
15. No paid 9.sh implementation is added in this task.

Testing Suggestions

Use at least these test paths:

bash -n trial-install.sh
bash -n 8.1.sh
bash -n 8.2.sh
bash -n 8.3.sh

Run a clean default install:

sudo ./trial-install.sh

Run without MOTD:

sudo ./trial-install.sh --no-motd

Run with an explicit model:

sudo ./trial-install.sh --model qwen3:0.6b

Inspect the result:

cat /opt/philosopher/8ball-result.txt

Inspect the installed helpers:

command -v remember
command -v 8balljets
sudo remember
sudo 8balljets

Inspect login output:

run-parts /etc/update-motd.d

Inspect Ollama:

systemctl status ollama --no-pager
curl -fsS http://127.0.0.1:11434/api/tags
ollama list

Final Instruction to Cursor

Focus only on making the public 8-BALL trial installer work cleanly for a real end user.

Do not expand architecture.

Do not add the paid upgrade path.

Do not touch Passport, RecordsCore, S3, Stripe, or 9.sh in this task.

Make the public repo boringly reliable, fun to use, and easy to support.
