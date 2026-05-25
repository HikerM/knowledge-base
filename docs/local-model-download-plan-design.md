# Local Model Download Plan Design

v2.7.2 defines a plan-only contract for future local model downloads. It does not download models, contact ModelScope, write model files, create model directories, start runtimes, register providers, open local HTTP, or enqueue real TaskQueue jobs.

## Scope

Implemented in this stage:

- `knowledge_app/ai/local_model_download_models.py`
- `knowledge_app/ai/local_model_download_plan_service.py`
- `tests/local_model_download_plan_test.py`

The service accepts a validated `LocalModelCatalog`, a `model_id`, a user-selected `target_dir`, and an optional `available_disk_gb` hint. It returns a dry-run `ModelDownloadPlan`.

## ModelDownloadPlan Schema

Required fields:

- `schema_version`
- `plan_id`
- `model_id`
- `display_name`
- `tier`
- `filename`
- `source_kind`
- `source_ref`
- `target_dir`
- `target_file`
- `expected_size`
- `install_size`
- `sha256`
- `verified_install_allowed`
- `blockers`
- `warnings`
- `requires_confirmation`
- `requires_task_queue`
- `dry_run`
- `would_modify`
- `would_download`
- `would_create_dirs`
- `validation_steps`
- `estimated_disk_required`
- `cleanup_policy`
- `rollback_hint`
- `elapsed_ms`

Invariant fields:

- `dry_run=true`
- `would_modify=false`
- `would_download=false`
- `requires_confirmation=true`
- `requires_task_queue=true`

`would_create_dirs` lists directories that a future execution flow may need. The plan service does not create them.

## Validation Rules

The plan service must:

- Load and validate catalog data through the local model catalog contract.
- Validate storage, download, and verification policies.
- Resolve exactly one model by `model_id`.
- Build `target_file` from `target_dir` and the catalog filename.
- Preserve `source_kind` and `source_ref` as reference-only metadata.
- Estimate disk requirements from `expected_size` and `install_size`.
- Add a blocker when `sha256=pending`.
- Add a blocker when `target_dir` is under workspace, install directory, `knowledge/`, or `.kb/`.
- Add a blocker when `available_disk_gb` is below the estimate.
- Add a blocker for 30GB+ models unless a future explicit advanced flow exists.

Invalid model ids are caller errors and should raise a controlled service error. Unsafe but parseable plans should return blockers so GUI and future services can show a clear reason.

## Non-goals

v2.7.2 must not:

- Download any model file.
- Access ModelScope or any network endpoint.
- Write `target_dir` or `target_file`.
- Create model directories.
- Write registry records.
- Create TaskQueue records.
- Start `llama.cpp`, a local model server, or any runtime.
- Implement an AI provider.
- Modify `knowledge/**/*.md`, `.kb/index.sqlite`, or search/index/audit behavior.

## Acceptance

Required checks:

```bash
python tests/local_model_download_plan_test.py
python -m compileall knowledge_app tests
```

Release validation should also run the existing governance and local model catalog/policy tests.
