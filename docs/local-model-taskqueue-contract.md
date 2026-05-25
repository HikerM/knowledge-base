# Local Model TaskQueue Contract

v2.7.2 only designs the future TaskQueue contract for local model operations. It does not enqueue or execute real tasks.

## Future Task Types

Future task types:

- `model_download_plan`
- `model_download`
- `model_verify`
- `model_register`
- `model_health_check`
- `model_uninstall`

Only the plan-only service is implemented now. `model_download`, `model_verify`, `model_register`, `model_health_check`, and `model_uninstall` remain future work.

## Plan-only Flow

The current flow is:

```text
catalog YAML -> catalog validation -> policy validation -> ModelDownloadPlan -> user review
```

There is no TaskQueue record in v2.7.2. A future GUI may render the plan, blockers, warnings, and validation steps, but it must not start a download.

## Future Execution Gates

Before any real model download execution exists, the future task must require:

- Valid `ModelDownloadPlan`.
- User confirmation.
- TaskQueue execution boundary.
- Path safety validation.
- Single-file `.gguf` target.
- No repository download.
- No shell script.
- No arbitrary command.
- Expected size and available disk check.
- Non-pending sha256 for verified install.
- Checksum verification before registry update.

## Progress Events

Future progress events must be structured and monotonic:

- `schema_version`
- `task_id`
- `sequence`
- `phase`
- `progress_percent`
- `bytes_expected`
- `bytes_received`
- `message`
- `cancel_requested`
- `error`

Suggested phases:

- `planned`
- `waiting_for_confirmation`
- `queued`
- `downloading`
- `verifying_checksum`
- `registering`
- `completed`
- `failed`
- `cancelled`
- `cleanup_pending`

## Cancel Behavior

Cancellation must be cooperative. A running task may only check cancellation at safe checkpoints:

- Before network request.
- Between download chunks.
- Before checksum verification.
- Before registry write.

On cancellation, future execution should delete partial files or mark cleanup pending. The active catalog and registry must not mark the model installed.

## Retry Behavior

Retry may only apply to failed or cancelled future tasks. Retry must keep lineage:

- `retry_of`
- `retry_root`
- original model id
- original target file
- original plan hash

Retry must not bypass confirmation, TaskQueue, path safety, sha256, disk, or no-shell gates.

## Checksum Failure

Checksum failure must:

- Fail the task.
- Delete or quarantine the partial file.
- Keep the model unregistered.
- Preserve error detail for the user.
- Require a new confirmed task for retry.

`sha256=pending` cannot produce a verified install.

## Partial Download Cleanup

Future downloads should write to a temporary suffix such as `.partial` and only atomically move into place after checksum verification. If cleanup fails, the task should return `cleanup_pending` with a visible path and remediation hint.

## Resume Policy

Resume is deferred. First execution should prefer deterministic cleanup and retry over partial resume. Range requests, ETags, and source validation need a separate design and tests before enabling resume.

## UI Boundary

GUI must not block on long-running model operations. Future execution must run through TaskQueue. The UI may poll progress and logs, but the UI thread must not perform download, checksum, registration, health check, or uninstall work.
