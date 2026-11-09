# DeepLit on aiforthai

DeepLit with MedicalReviewerAgent at **https://deeplit.aiforthai.in.th**, deployed from
**gitlab.nectec.or.th/10service/deeplit** by `.gitlab-ci.yml` on the `ai4thai-gpu1`
runner. Follows the aiforthai administrators' guide (GitLab CI/CD, ENV_FILE, host
paths, `0.0.0.0` ports) and the pipeline of `10service/sansarndeep` on the same runner.

| | |
|---|---|
| Public address | https://deeplit.aiforthai.in.th/ (the aiforthai reverse proxy, 203.185.132.210, terminates TLS) |
| Host port | `0.0.0.0:10370` → DeepLit's web container, port 80 |
| Data | `/home/search/Thoughtmind/deeplit/data` (`DATA_PATH`; every project on the machine keeps its data in `<project>/data`) |
| Runner | `ai4thai-gpu1` (its jobs drive the host's Docker; `hackathon-siamai1` in the guide is stale) |
| Secrets | the `ENV_FILE` CI variable, from `env.example` |

## What runs

One Compose project, `deeplit` (`compose.yml`):

- **DeepLit**: `db`, `api`, `worker`, `web` (the only published port), `searxng`.
- **MRA**: `mra` (its one address, a small Caddy), `mra-api`, `mra-worker`, `mra-web`,
  `mra-postgres`, `mra-redis`, `mra-searxng`; `mra-migrate` once per `up`.
- **Links, once per `up`**: `mra-link` adds `MRA_SERVICE_API_KEY` to MRA's keys,
  `deeplit-link` sets DeepLit's Medical Review to `http://mra` with it, unless an
  administrator has set it up already.

MRA has no public address (one port was given): it is configured through `ENV_FILE`
only, and its console is not reachable.

Data folders under `DATA_PATH` (`prepare` makes the missing ones and gives `runs` to
uid 10001, the api and worker user):

| Folder | Holds |
|---|---|
| `postgres/` | DeepLit's database |
| `runs/` | DeepLit's reports, files and search cache |
| `redis/` | MRA's queue and caches |
| `mra-postgres/` | MRA's database |

Images are built on the host from this commit and from GitHub at the commits
`stack/engines.lock.json` pins (the Engine forks, MRA, MRA's SearXNG fork); `pins.sh`
reads them. Nothing is bind-mounted from the checkout: config is built into images.

## First deploy

1. **ENV_FILE**: Settings → CI/CD → Variables → Add variable. Key `ENV_FILE`, type
   **File**, **Protected**, environments **All** (`*`: build, smoke test and stop read
   it too, and only `deploy_app` is in `production`), **Expand variable reference
   off**. Value: `env.example` with every `CHANGE_ME` replaced. Keep a copy
   of `LITSTORM_SECRET_KEY` off the machine.
2. **Merge to main** (main is protected, no force push): push a branch, open a merge
   request. On the branch, `check_host` already shows which machine the runner
   reaches and lists `DATA_PATH`.
3. On main, `build_images` runs by itself. Then press **deploy_app** (Build →
   Pipelines). It prepares the folders, starts the stack and waits until every
   container is healthy; `smoke_test` follows.
4. Open https://deeplit.aiforthai.in.th/setup and type `LITSTORM_BOOTSTRAP_CODE` to
   create the first administrator.

## Later deploys

Merge to main, wait for `build_images`, press `deploy_app`. `up` replaces only what
changed; data stays in `DATA_PATH`. A database migration runs when `api` starts.

Moving an Engine or MRA: commit a new sha in `stack/engines.lock.json`.

## When something fails

- **`check-env.sh` stops the job**: it names the key (never a value) that is empty,
  still `CHANGE_ME`, quoted, or has swallowed the next line.
- **`ENV_FILE is not set`**: the job ran on an unprotected branch; ENV_FILE is
  Protected, so only main sees it.
- **`wait-healthy.sh` names a container**: its last 60 log lines are in the job log.
- **`stop_app`** runs `down` (no `-v`; the data is in host folders anyway).

The job log is readable by every project member: never `cat .env`, and never
`docker compose config` without `--quiet`.

## Rehearsing on a laptop

```sh
. deploy/aiforthai/pins.sh
C="docker compose -f deploy/aiforthai/compose.yml --env-file /path/to/test.env"
$C build && $C run --rm prepare && $C up -d && sh deploy/aiforthai/wait-healthy.sh "$C"
sh deploy/aiforthai/smoke-test.sh "$C"
```

`test.env` as `env.example`, with `DATA_PATH` an existing empty folder.
