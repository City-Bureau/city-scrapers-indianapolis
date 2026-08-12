---
name: refresh-staging-scraped-data
description: Refresh the staging Documenters site with the latest scraper output from open PRs. Merges reviewed PRs into the staging branch, crawls into the staging-only Azure feed container, then resets and re-imports that program's meetings on documenters-stg. Use when City Bureau needs to manually QA in-progress scrapers on staging.documenters.org, when asked to "refresh staging scraper data", or when a scraper fix is ready to integrate to staging.
---

# Refresh staging scraped data

Puts the newest scraper output in front of City Bureau reviewers on
staging.documenters.org without publishing it to the live site.

## The invariant this skill exists to protect

Production `documenters.org` and staging `staging.documenters.org` each import a
program's meetings from an Azure blob URL stored on the program row
(`accounts_program.meetings_feed_endpoint`). **If both point at the same
container, there is no such thing as a staging-only refresh** — cleaning the
container or crawling into it changes what the live site imports.

So before anything else, prove the staging program reads from a `-stg` container
that production does not read from. Step 0 does this and refuses to continue
otherwise.

Two more hard rules:

- The Heroku app is **always `documenters-stg`**. Never pass `documenters-prod`.
- Reviewed PRs are merged into the **`staging` branch only**. Merging to `main`
  publishes to production, which is not what this workflow is for.

## Prerequisites

`gh`, `heroku`, `az`, `pipenv`, and `jq` on PATH; `gh auth status` and
`heroku auth:whoami` both authenticated; repo cloned with a `staging` branch and
a `.github/workflows/staging.yml`.

No `.env` file and no pasted secrets. The Azure key is read at run time from the
staging app's own config:

```bash
export AZURE_ACCOUNT_NAME=cityscrapers
export AZURE_ACCOUNT_KEY=$(heroku config:get AZURE_SCRAPER_ACCOUNT_KEY -a documenters-stg)
```

Set the program you are refreshing once, then reuse it:

```bash
export PROGRAM_SLUG=indianapolis
```

## Step 0 — Preflight: prove staging is isolated

Read both feed endpoints and refuse to proceed if they match.

```bash
heroku pg:psql -a documenters-stg -c \
  "select slug, meetings_feed_endpoint from accounts_program where slug = '$PROGRAM_SLUG';"
heroku pg:psql -a documenters-prod -c \
  "select slug, meetings_feed_endpoint from accounts_program where slug = '$PROGRAM_SLUG';"
```

Derive the staging container from the staging endpoint and assert it is distinct
and `-stg`-suffixed:

```bash
export STAGING_CONTAINER=$(heroku pg:psql -a documenters-stg -qtAX -c \
  "select meetings_feed_endpoint from accounts_program where slug = '$PROGRAM_SLUG';" \
  | sed -E 's#.*windows\.net/([^/]+)/.*#\1#')
export PROD_CONTAINER=$(heroku pg:psql -a documenters-prod -qtAX -c \
  "select meetings_feed_endpoint from accounts_program where slug = '$PROGRAM_SLUG';" \
  | sed -E 's#.*windows\.net/([^/]+)/.*#\1#')

echo "staging: $STAGING_CONTAINER"
echo "prod:    $PROD_CONTAINER"

case "$STAGING_CONTAINER" in
  *-stg) ;;
  *) echo "ABORT: staging container '$STAGING_CONTAINER' is not a -stg container"; exit 1 ;;
esac
[ "$STAGING_CONTAINER" != "$PROD_CONTAINER" ] || \
  { echo "ABORT: staging and prod share container '$STAGING_CONTAINER'"; exit 1; }
```

If this aborts, the program has no staging isolation yet. Stop and set it up
first (see **Bootstrapping a program that has no staging container** below).
Do not "just this once" clean or crawl the shared container.

Also confirm the repo secret the staging workflow reads exists:

```bash
gh api repos/City-Bureau/$(basename $(git rev-parse --show-toplevel))/actions/secrets \
  -q '.secrets[].name' | grep -x AZURE_STAGING_CONTAINER
```

## Step 1 — Clean the staging container

Only after Step 0 passed. Show what will be deleted, get explicit confirmation
from the human, then delete.

```bash
az storage blob list --account-name "$AZURE_ACCOUNT_NAME" --account-key "$AZURE_ACCOUNT_KEY" \
  --container-name "$STAGING_CONTAINER" --query "length(@)" -o tsv
az storage blob list --account-name "$AZURE_ACCOUNT_NAME" --account-key "$AZURE_ACCOUNT_KEY" \
  --container-name "$STAGING_CONTAINER" --delimiter '/' -o table
```

Pause here. Report the count and the top-level layout, and ask the human to
confirm before deleting. Then:

```bash
az storage blob delete-batch --account-name "$AZURE_ACCOUNT_NAME" \
  --account-key "$AZURE_ACCOUNT_KEY" --source "$STAGING_CONTAINER"
az storage blob list --account-name "$AZURE_ACCOUNT_NAME" --account-key "$AZURE_ACCOUNT_KEY" \
  --container-name "$STAGING_CONTAINER" --query "length(@)" -o tsv   # expect 0
```

Cleaning matters when spider names change: a renamed or removed spider leaves a
stale `<old_name>.json` behind, and `combinefeeds` folds every `*.json` in the
container into `latest.json`, so the old meetings would be re-imported forever.

## Step 2 — Select the PRs to merge

```bash
gh pr list --state open --json number,title,headRefName,author,isDraft,mergeable \
  | jq '[.[] | select(.author.is_bot == false and .isDraft == false)]'
```

Show the human a table (PR #, title, branch, author, mergeable) and ask which to
merge. Default to all, but **only merge PRs that have actually been reviewed**.
This skill is the deploy step, not the review step.

Check each PR's CI honestly — do not treat a green CodeRabbit check as CI:

```bash
gh pr checks <PR_NUMBER>
```

Fork PRs from first-time contributors sit in `action_required` and never run CI,
so a PR can look unblocked while its tests have never executed. Assume nothing;
Step 4 runs the tests locally and is the real gate.

## Step 3 — Merge into the staging branch

Pin each merge to the PR's explicit head SHA. A bare branch name or `FETCH_HEAD`
can race a push and silently merge a different commit than the one reviewed.

```bash
git fetch origin --prune
git checkout staging
git pull origin staging

for PR in <PR_NUMBERS>; do
  SHA=$(gh pr view "$PR" --json headRefOid -q .headRefOid)
  git fetch origin "refs/pull/$PR/head:pr-$PR"
  git merge "$SHA" --no-edit -m "Merge PR #$PR into staging"
done
```

On a conflict: stop, list the conflicting files, and ask the human whether to
resolve, skip the PR, or abort. Never resolve a scraper parsing conflict by
guessing.

## Step 4 — Lint and test locally: this is the real gate

```bash
pipenv sync --dev
pipenv run isort . --check-only
pipenv run black . --check
pipenv run flake8 .
pipenv run pytest -q
```

Lint may be auto-fixed (`pipenv run black .`, `pipenv run isort .`) and committed
as a follow-up commit. **Test failures may not be waved through.** If a test
fails, read it: the common case in this repo is that the *test* encodes the wrong
expectation, not that the spider is broken. Fix whichever is actually wrong,
commit it with an explanation, and leave a review comment on the source PR so the
fix lands upstream too.

Then confirm every spider still loads and nothing vanished in a refactor:

```bash
pipenv run scrapy list | sort
git ls-tree HEAD city_scrapers/spiders/ --name-only
```

If a PR replaced standalone spiders with a mixin plus spider factory, verify the
spider `name` attributes are unchanged. Meeting identity downstream is
`<spider_name>/<YYYYMMDDHHMM>/x/<slugified_title>`, so a changed spider name or
meeting title creates **duplicate** meetings on the site and orphans existing
Documenter assignments rather than updating rows in place.

Optionally validate against the live sites the way CI does:

```bash
pipenv run scrapy validate <spider_name>
```

## Step 5 — Push and run the staging crawl

```bash
git push origin staging
```

`staging.yml` triggers on push to `staging`. Watch it:

```bash
gh run list --workflow=staging.yml --limit 5
gh run watch $(gh run list --workflow=staging.yml --limit 1 --json databaseId -q '.[0].databaseId')
```

The crawl takes roughly 20 to 30 minutes. It must reach the **Combine output
feeds** step, which is what writes `latest.json`. A crawl that scraped fine but
died before `combinefeeds` leaves the feed unchanged and the import in Step 7
will silently do nothing.

If the workflow does not appear at all, dispatch it manually:

```bash
gh workflow run staging.yml --ref staging
```

Then verify real output landed, and sanity-check the per-spider file sizes:

```bash
curl -sI "https://cityscrapers.blob.core.windows.net/$STAGING_CONTAINER/latest.json" \
  | grep -i 'last-modified\|content-length'
az storage blob list --account-name "$AZURE_ACCOUNT_NAME" --account-key "$AZURE_ACCOUNT_KEY" \
  --container-name "$STAGING_CONTAINER" --delimiter '/' \
  --query "[].{name:name, bytes:properties.contentLength}" -o table
```

A `0`-byte `<spider>.json` means that spider scraped nothing. That is a broken
scraper, not a successful refresh — report it instead of proceeding.

## Step 6 — Reset the program's meetings on staging

Delete stale rows so the import cannot leave orphans behind. Two constraints,
both of which the naive "delete every meeting in this program" version violates:

**Only delete meetings the feed will actually re-create.** A program's meetings
usually come from more than one scraper generation. Indianapolis on staging has
three, distinguished by the prefix of `scraper_id`
(`<spider_name>/<YYYYMMDDHHMM>/x/<slug>`):

| prefix | source | re-created by this feed? |
| --- | --- | --- |
| `ind_*` | this repo's current spiders | yes |
| `indianapolis_*` | older generation of scrapers | **no** |
| `reworkd` | Reworkd AI scrapers | **no** |

Deleting a `reworkd` or `indianapolis_*` row destroys it permanently: nothing in
`latest.json` will bring it back. So scope the delete to the spider names the
crawl actually produced. Get that list from the repo, not from memory:

```bash
pipenv run scrapy list | sort
```

**Only delete meetings without assignments**, so Documenter assignments and the
work attached to them survive.

Check first, delete second. Confirm the counts look sane before running the
delete:

```bash
heroku run -a documenters-stg --no-tty -- python manage.py shell <<'EOF'
from documenters.meetings.models import Meeting

SLUG = "indianapolis"
# The spider names `scrapy list` printed. Keep this explicit: a LIKE 'ind_%'
# pattern would ALSO match indianapolis_* rows, because _ is a single-character
# wildcard in SQL.
SPIDERS = [
    "ind_city_county", "ind_iia", "ind_indygo", "ind_indygo_finance",
    "ind_indygo_gov_audit", "ind_indygo_service", "ind_public_library",
    "ind_school_board",
]
prefixes = [f"{name}/" for name in SPIDERS]

qs = Meeting.objects.filter(programs__slug=SLUG)
mine = qs.none()
for p in prefixes:
    mine = mine | qs.filter(scraper_id__startswith=p)
mine = mine.distinct()

drop = mine.filter(assignments__isnull=True).distinct()
print(f"program_total={qs.count()} from_these_spiders={mine.count()}")
print(f"  will_delete={drop.count()} kept_for_assignments={mine.count() - drop.count()}")
print(f"  untouched_other_generations={qs.count() - mine.count()}")
EOF
```

Report those numbers, get confirmation, then delete by swapping the last line for
`deleted, _ = drop.delete(); print(f"deleted={deleted}")`.

The rows from other generations stay behind and can read as near-duplicates next
to freshly imported meetings. That is usually acceptable because they are all in
the past while CB reviews upcoming meetings. Say so in the handoff rather than
deleting them to make the list look tidy.

## Step 7 — Point the program at the staging feed and import

Only needed if Step 0 showed the endpoint pointing somewhere else, but always
re-read it afterward.

```bash
heroku pg:psql -a documenters-stg -c \
  "update accounts_program set meetings_feed_endpoint = 'https://cityscrapers.blob.core.windows.net/$STAGING_CONTAINER/latest.json' where slug = '$PROGRAM_SLUG';"
heroku pg:psql -a documenters-stg -c \
  "select slug, meetings_feed_endpoint from accounts_program where slug = '$PROGRAM_SLUG';"
```

Queue the import:

```bash
heroku run -a documenters-stg --no-tty -- python manage.py shell <<'EOF'
from documenters.accounts.models import Program
from documenters.meetings.tasks import handle_meetings_feed_endpoint

SLUG = "indianapolis"
program = Program.objects.get(slug=SLUG)
print(f"importing from {program.meetings_feed_endpoint}")
handle_meetings_feed_endpoint.send(program.meetings_feed_endpoint)
EOF
```

This enqueues a dramatiq task; it returns immediately and the work happens on a
worker. Follow it:

```bash
heroku logs --tail -a documenters-stg
```

`SKIP_AZURE_BLOB_DATA_CHECK` is already `true` on `documenters-stg`, so the
importer will not refuse a feed it considers suspiciously small. Confirm rather
than assume, and do not set it on any other app:

```bash
heroku config:get SKIP_AZURE_BLOB_DATA_CHECK -a documenters-stg
```

## Step 8 — Verify what City Bureau will actually see

Counts, then the specific agencies CB asked to QA.

```bash
heroku pg:psql -a documenters-stg -c \
  "select count(*) from meetings_meeting m join meetings_meeting_programs mp on mp.meeting_id = m.id join accounts_program p on p.id = mp.program_id where p.slug = '$PROGRAM_SLUG';"

heroku pg:psql -a documenters-stg -c \
  "select m.title, count(*) as n, min(m.start_time) as earliest, max(m.start_time) as latest
   from meetings_meeting m
   join meetings_meeting_programs mp on mp.meeting_id = m.id
   join accounts_program p on p.id = mp.program_id
   where p.slug = '$PROGRAM_SLUG'
   group by m.title order by n desc limit 40;"
```

Check the columns against the app's real schema first if a query errors; table
and column names drift.

Then open the staging site for the agencies named in the Airtable request and
confirm dates, times, locations, and agenda links look right:
`https://www.staging.documenters.org/`

Finally, reply on the originating Airtable record and Slack thread with the
counts and anything CB should know (for example a hardcoded start time that
needs a human eye).

## Bootstrapping a program that has no staging container

Do this once per program, then the steps above apply. Mirror an existing
program that already has staging isolation.

1. Create the container, matching its siblings' public access level:
   ```bash
   az storage container create --account-name cityscrapers --account-key "$AZURE_ACCOUNT_KEY" \
     --name meetings-feed-<code>-stg --public-access container
   ```
2. Set the repo secret the staging workflow reads:
   ```bash
   printf '%s' 'meetings-feed-<code>-stg' | gh secret set AZURE_STAGING_CONTAINER
   ```
3. Add `city_scrapers/settings/staging.py` reading `AZURE_STAGING_CONTAINER`
   instead of `AZURE_CONTAINER`, and omitting the status-badge extension so
   badges keep tracking the production crawl.
4. Add `.github/workflows/staging.yml` with `SCRAPY_SETTINGS_MODULE:
   city_scrapers.settings.staging`, triggered on push to `staging` plus
   `workflow_dispatch`.
5. Create the `staging` branch from `main` and push it.
6. Update the staging program's `meetings_feed_endpoint` (Step 7).

## Reporting

Close out with: PRs merged (numbers and head SHAs), lint/test result, any test or
spider fix made and why, workflow run URL and duration, per-spider feed sizes
with zero-byte spiders called out, meetings deleted, meetings imported, and what
still needs a human decision.

Report what the commands actually printed. If a step was skipped or a scraper
came back empty, say so plainly rather than reporting a clean refresh.

## Known trip hazards in this repo

- **Scheduled workflows currently fail at startup.** `cron.yml` has produced no
  runs since 2026-07-08 and now records `startup_failure` twice daily, so the
  production Indianapolis feed is stale and `staging.yml` deliberately has no
  `schedule` trigger yet.
- **The production feed has zero-byte spiders.** `ind_indygo*.json` and
  `ind_public_library.json` were 0 bytes as of 2026-07-08, which is what the
  scraper-fix PRs are addressing. Expect a large jump in meeting counts.
- **`gh pr checks` can look green when CI never ran.** See Step 2.
- **The `ruff` PostToolUse hook reformats Python on edit** and disagrees with
  `black` in places. After any Python edit, run `pipenv run black .` and
  `pipenv run isort .` and re-check the diff before committing.
