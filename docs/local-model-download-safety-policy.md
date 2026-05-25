# Local Model Download Safety Policy

This policy locks the safety boundaries for local model download planning. v2.7.2 is plan-only and must not perform any real download or runtime operation.

## Hard Deny in v2.7.2

The implementation must not:

- Download models.
- Access ModelScope network APIs.
- Open arbitrary URLs.
- Write model files.
- Create model directories.
- Execute shell scripts.
- Run arbitrary commands.
- Use `subprocess`, `cmd`, PowerShell, or OS shell execution.
- Start `llama.cpp`, local model servers, or model runtime processes.
- Open local HTTP endpoints.
- Implement a real AI provider.
- Modify `knowledge/**/*.md`.
- Modify SQLite schema.
- Change search/index/audit behavior.
- Create TaskQueue tasks.

## Source Policy

Allowed `source_kind` values remain reference-only:

- `modelscope_reference`
- `manual_reference`

Catalog references are not download instructions. A future downloader must translate an approved reference into a controlled single-file `.gguf` request only after user confirmation and TaskQueue setup.

## Storage Policy

Default model directory:

```text
%LOCALAPPDATA%\PersonalKnowledgeBase\models\
```

Forbidden target locations:

- workspace root or descendants
- software install directory
- `knowledge/`
- `.kb/`

Custom directories require future confirmation and path safety validation. Uninstall must not delete model files by default. Deleting a model must require explicit user confirmation.

## Download Policy

Future download execution must keep:

- `no_auto_download=true`
- `confirmation_required=true`
- `task_queue_required=true`
- `single_file_gguf_only=true`
- `no_repository_download=true`
- `no_shell_script=true`
- `no_arbitrary_command=true`

Repository clone/download is forbidden. Shell snippets from catalog, docs, ModelScope, or user input are forbidden.

## Verification Policy

Verified install requires:

- Non-pending `sha256`.
- Expected size.
- Checksum verification before registry update.
- Failure on checksum mismatch.
- License review gate.

`sha256=pending` must remain a blocker for verified install.

## Disk and Cleanup Policy

Plan-only estimates disk from catalog `expected_size` and `install_size`. Future execution must check available disk before download, use partial files, and avoid marking a model installed until checksum verification and registration both succeed.

Cleanup behavior:

- Cancelled future task deletes partial file or reports cleanup pending.
- Failed checksum deletes or quarantines partial file.
- Registry remains unchanged on failure.
- Retry requires a fresh confirmed TaskQueue path.

## Provider Boundary

Local model download planning is separate from provider execution. The plan service must not call ContextBuilder, AIProvider, AssistantService, ModelRuntimeManager, ModelProcessManager, health check runtime code, or any local server.
