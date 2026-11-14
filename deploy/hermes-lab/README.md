# Remote Hermes test lab

A private Fly Machine for the MindGraph plugin. It has no HTTP service, gateway,
public listener, automatic model runs or scheduled evaluations. Use Fly SSH.
The image contains the exact released plugin and Hermes commit used by the host
CI gate. Change the Docker build arguments deliberately when qualifying another
candidate; the runtime source is root-owned and tests run as UID 10000.

See [the initial deployment receipt](VALIDATION.md) for the deployed machine,
image digest, checks, live conversation evidence and remaining validation gaps.

## Deployment

Run from `deploy/hermes-lab`:

```sh
fly apps create mindgraph-hermes-lab --org personal
fly volumes create hermes_data -a mindgraph-hermes-lab -r iad --size 3 --snapshot-retention 3
fly deploy -c fly.toml --remote-only --ha=false --strategy immediate
```

The app and volume already exist after initial provisioning; do not recreate
them on an update. Configuration selects one shared CPU and 1 GB RAM in `iad`.
`/data/profile` is the persistent Hermes home, `/data/workspace` its working
directory, and `/data/runs` stores diagnostic evidence. The Dockerfile-specific
ignore file limits the build context to this directory, excluding local secrets,
profiles and unrelated workspace files.

The base image is pinned by digest. Hermes is installed from its pinned lockfile,
with SDK 0.17.0 and pytest 9.2.0. SQLite 3.53.4 uses the same source checksum as
Hermes's Dockerfile, including the upstream WAL-reset fix. Reports record actual
Python, SQLite, SDK and source revisions. Base OS package resolution is not fully
hermetic; retain the resulting Fly image digest for each deployed environment.

## Checks and interactive use

```sh
fly ssh console -a mindgraph-hermes-lab -C 'hermes-lab doctor'
fly ssh console -a mindgraph-hermes-lab -C 'hermes-lab unit-checks'
fly ssh console -a mindgraph-hermes-lab -C 'hermes-lab host-checks'
fly ssh console -a mindgraph-hermes-lab -C 'hermes-lab offline-checks'
fly ssh console -a mindgraph-hermes-lab --pty -C 'hermes-lab hermes'
```

`doctor` makes no API/model calls and only reports whether named environment
credentials are present. It does not inspect credentials saved by interactive
Hermes setup. Checks use new profiles and clear model/MindGraph credentials from
the child environment, with a separate `HOME` as well as `HERMES_HOME`. Their logs and version provenance are retained beneath
`/data/runs/<timestamp>-<mode>-<unique suffix>`, with the process exit status.
A nonzero test result remains nonzero through the wrapper and SSH command.

Unit/host/offline checks use a scripted local API; passing them establishes
integration behavior, not live memory quality or improved agent answers.

## Live acceptance prerequisites

Prefer a dedicated MindGraph test organization. This lab's initial operator
explicitly authorized the existing benchmark key for synthetic test writes;
the shared graph means these runs do not establish fresh-world evaluation
results. Install secrets directly through Fly's secret commands or Hermes's
interactive setup; do not commit them or put their values into command history:

```sh
# Enter NAME=value records over stdin, then EOF; do not paste values into chat.
fly secrets import -a mindgraph-hermes-lab
```

For interactive sessions, use `MINDGRAPH_API_KEY` for the dedicated org and the
model provider's credential. Set `MINDGRAPH_BASE_URL` if testing a non-default
backend. New profiles select OpenAI `gpt-6-luna` via the Responses transport,
with reasoning disabled, at most eight tool iterations and a 120-second run
budget. `OPENAI_API_KEY` is resolved from the environment. The model is an alias,
not an immutable snapshot; retain each run's usage record. Run
`hermes-lab hermes setup` to change the model/provider. Existing profile settings
survive image updates. The plugin is selected with in-process isolation.

The six-scenario provider harness separately uses `MINDGRAPH_EVAL_API_KEY` and
optional `MINDGRAPH_EVAL_BASE_URL`; see `evals/README.md`. A live run writes to
that org and invokes server extraction. Before running it, record the backend,
model, candidate and a cost limit. There is no live-evaluation command scheduled
by this lab, and no measured live outcome is implied by its installation.

## Restart, stop and evidence

```sh
fly machines list -a mindgraph-hermes-lab
fly machine restart <machine-id> -a mindgraph-hermes-lab
fly machine stop <machine-id> -a mindgraph-hermes-lab
fly machine start <machine-id> -a mindgraph-hermes-lab
fly ssh sftp shell -a mindgraph-hermes-lab
```

Stop the machine when not using it; the persistent volume remains and still
incurs storage charges. Nothing autostarts it through HTTP. Re-run `doctor`
after starting it. A machine restart preserves `/data`, including capture.db;
a profile reset is a separate deliberate action. No cleanup command here deletes
profiles or failed-run evidence. Retrieve reports with SFTP and remove only
specific runs when no longer needed.
