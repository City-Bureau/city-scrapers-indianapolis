---
name: merge-staging
description: Merge reviewed open PRs into the staging branch and gate the result on lint and tests. Use when asked to merge PRs to staging, integrate scraper PRs for staging QA, or update the staging branch. This is the code half of refresh-staging-scraped-data; use that skill instead when the goal is to also re-import the data onto staging.documenters.org.
---

# Merge PRs into staging

Merges reviewed, non-draft, non-bot PRs into the `staging` branch and refuses to
push unless lint and tests pass.

Scope: code only. It does not clean Azure, reset the staging database, or trigger
an import. For the whole refresh use `refresh-staging-scraped-data`, which calls
these same steps as its Steps 2 through 5.

**Never merge to `main`.** `main` is what the production crawl runs from.

## Step 1 — List candidates

```bash
gh pr list --state open --json number,title,headRefName,author,isDraft,mergeable \
  | jq '[.[] | select(.author.is_bot == false and .isDraft == false)]'
```

Show a table (PR #, title, branch, author, mergeable) and ask which to merge.
Default to all listed, but only merge PRs that have been reviewed — merging is not
reviewing.

Check CI per PR, and read the result skeptically:

```bash
gh pr checks <PR_NUMBER>
```

A green CodeRabbit check is not CI. Fork PRs from first-time contributors sit in
`action_required` and never execute, so a PR can appear unblocked while its tests
have never run. Step 4 is the real gate.

## Step 2 — Prepare the branch

```bash
git fetch origin --prune
git checkout staging
git pull origin staging
```

If `staging` does not exist yet, create it from `main` and say so explicitly:

```bash
git checkout -B staging origin/main
```

## Step 3 — Merge, pinned to explicit SHAs

Pin every merge to the PR's head SHA. A bare branch name or `FETCH_HEAD` can race
a concurrent push and merge a commit nobody reviewed.

```bash
for PR in <PR_NUMBERS>; do
  SHA=$(gh pr view "$PR" --json headRefOid -q .headRefOid)
  git fetch origin "refs/pull/$PR/head:pr-$PR"
  echo "merging PR #$PR at $SHA"
  git merge "$SHA" --no-edit -m "Merge PR #$PR into staging"
done
```

On a conflict: stop, list the conflicting files, and ask whether to resolve, skip
that PR, or abort. Do not guess at a resolution inside scraper parsing logic.

## Step 4 — Lint and test

```bash
pipenv sync --dev
pipenv run isort . --check-only
pipenv run black . --check
pipenv run flake8 .
pipenv run pytest -q
```

Lint may be auto-fixed and committed:

```bash
pipenv run black . && pipenv run isort .
git add -A && git commit -m "Fix lint after merge"
```

Test failures may not be waved through. Read the failure before assuming the
spider is at fault — in this repo the frequent cause is a test that encodes the
wrong expected value. Fix whichever side is actually wrong, explain it in the
commit message, and leave a review comment on the source PR so the fix also lands
upstream.

Note: the `ruff` PostToolUse hook reformats Python on edit and disagrees with
`black` in places. After any Python edit, re-run `pipenv run black .` and
`pipenv run isort .`, then re-read the diff so an unrelated reformat does not ride
along.

## Step 5 — Verify nothing disappeared

```bash
pipenv run scrapy list | sort
git diff origin/main...HEAD --stat
```

Account for every changed file. If a PR replaced standalone spiders with a mixin
plus spider factory, confirm each spider `name` is unchanged: meeting identity
downstream is `<spider_name>/<YYYYMMDDHHMM>/x/<slugified_title>`, so a renamed
spider or retitled meeting produces duplicates on documenters.org and orphans
existing Documenter assignments.

Confirm each merge is fully contained:

```bash
for PR in <PR_NUMBERS>; do
  echo "PR #$PR unmerged commits:"; git log "HEAD..pr-$PR" --oneline
done
```

Empty output for each means the merge is complete.

## Step 6 — Push

Ask for confirmation, then:

```bash
git push origin staging
```

If the repo has a `staging.yml` workflow, this push starts a full staging crawl
(roughly 20 to 30 minutes). Say so before pushing, since it consumes the staging
feed container.

On rejection, `git pull --rebase origin staging` and re-verify before retrying.

## Reporting

PRs merged with their head SHAs, PRs skipped and why, lint fixes applied, test
result, any spider or test change you made and the reason, and push status.
