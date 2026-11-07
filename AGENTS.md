# Working in this repository

Guidance for anyone, human or agent, running builds and tests on a local
checkout of Retro Trivia. The README covers what the door is and how to run
it.

## Local disk hygiene

In November 2026, scratch left by test runs, proofs and captures grew to
several million files on the shared development host and took it down.
Every run wrote a new folder and nothing ever removed one, and the repos
were in OneDrive, which made it much worse. Recovery took a full day,
including an offline disk check. The first fix moved the scratch to the
system temp folder, which then passed half a million entries and had to be
cleared by hand. These rules keep scratch bounded:

- **Run `pytest` without `--basetemp`.** pytest then uses the system temp
  folder and, as set in `pyproject.toml`, keeps only failed tests'
  directories from the last run. If your sandbox can write only inside
  the checkout, use exactly `--basetemp=.test-tmp/pytest`, which every
  run replaces. The suite refuses any other `--basetemp` inside the
  checkout.
- **One fixed folder per kind of scratch, never one per run.** Captures,
  renders, downloaded releases, venvs and clones go in
  `retro-trivia/<kind>` in the system temp folder, or `.test-tmp/<kind>`
  in the checkout, reused by every run. Never a new folder per run, per
  head or per PR. Delete it when you are done, including anything you
  downloaded to verify.
- **The system temp folder is not storage.** Evidence worth keeping is
  committed under `docs/` or attached to the PR. Never cite a temp path as
  where something is kept.
- **The suite refuses to start above 50,000 scratch files**, counting
  `.test-tmp` and `.pytest_cache` in the checkout, and separately the
  project's own `retro-trivia*` entries in the temp folder
  (`tests/scratch_guard.py`). `RETROTRIVIA_SCRATCH_LIMIT` raises the limit
  for one run; fix the cause instead of raising it routinely.
- **Clean up with `tools/clean_scratch.py`.**
  - No flags: removes the checkout's ignored scratch (`.test-tmp`,
    `.pytest_cache`, `__pycache__`, `build`, `*.egg-info`). It never
    touches `.venv` or tracked files.
  - `--temp`: removes the project's `retro-trivia*` temp entries with
    nothing written for 24 hours. `--older-than 0` removes all of them,
    once you've checked that no run is active.
  - `--report`: lists file counts for the checkout, every worktree and the
    project's temp entries, and flags any over the limit or already merged
    into `origin/main`. It deletes nothing.
- **One worktree per active branch.** Remove it with `git worktree remove`
  once its PR merges, and clean scratch before going idle.
- **Run the full suite one at a time.** Don't start a full run while
  another session's run is going (`-n auto` within a single run is fine),
  and never kill another session's processes.
- **Keep checkouts outside OneDrive** or any other synced folder. This
  repo lives under `C:\Users\Thiesi\Local\Dev`.

## Git

- Never force-push, `--force-with-lease` included. Reconcile with a merge.
- Never use a bare `git stash`: the stash is shared by every worktree of
  the repo. Commit to a branch instead.
- Branch from `origin/main`. Merge through a PR.
