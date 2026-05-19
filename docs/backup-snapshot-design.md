# Backup Snapshot Design

本文件定义未来 Windows EXE / GUI 的本地备份、操作前快照、恢复和可选 Git 同步设计。当前阶段只做文档和服务边界设计，不实现 GUI，不修改 SQLite schema，不改变 search/index/audit 行为。

## 1. Design Principles

- Git is optional, not required.
- Local Only mode 是默认模式。
- 普通用户没有 Git、没有 GitHub 账号、没有命令行时，也必须能完整使用知识库。
- Local snapshot / backup 是默认回滚机制。
- Optional Git Sync 只是额外同步、远端备份和高级用户版本管理方式。
- public repo 不等于 backup。公开仓库不能替代本地备份，也不能保证包含用户全部私有 workspace 数据。
- `.kb/index.sqlite` 是可重建索引，不是备份核心。

正确架构：

```text
Desktop GUI
  ↓
Service Layer
  ↓
knowledge_core
  ↓
Markdown + SQLite + Local Backup/Snapshot
  ↓
Optional Git Sync
```

## 2. Future Service Layout

未来服务模块建议放在：

```text
knowledge_app/services/
  backup_service.py
  snapshot_service.py
  versioning_service.py
  optional_git_service.py
```

这些 service 是 GUI/API 层的应用服务边界，不应绕过 `knowledge_core` 的 schema 校验、生命周期规则和索引边界。

### BackupService

职责：

- 创建用户主动触发的本地 zip 备份。
- 支持定期备份策略，但不在启动时扫描全库。
- 生成 backup manifest，记录文件数量、总大小、hash 摘要、创建时间、工具版本和是否包含 `.kb`。
- 校验备份包结构和 manifest。
- 管理备份保留策略。
- 支持 restore 前 dry-run。
- 在备份前运行 secret-scan 或至少提示 secret/privacy 风险。

BackupService 默认备份：

- `knowledge/`
- `config/`
- `templates/`
- `reports/`
- `docs/`
- `README.md`
- `AGENTS.md`
- 未来 workspace manifest 或 service 配置文件

BackupService 默认不把 `.kb/index.sqlite` 当作核心资产。它可以提供“包含 `.kb` 以加快恢复”的选项，但恢复后仍应允许重新 `index` 和 `doctor`。

### SnapshotService

职责：

- 在高风险写操作前创建短期本地 snapshot。
- 记录触发操作、操作者、时间、影响范围和恢复提示。
- 为 restore 提供候选快照列表。
- 支持快照保留策略，避免无限增长。
- 快照创建失败时阻止高风险写操作，除非用户显式确认继续。

自动 snapshot 触发操作：

- promote
- archive
- restore
- bulk import
- schema migration
- destructive maintenance
- workspace upgrade

SnapshotService 不负责 Git commit，不要求 Git 存在。

### VersioningService

职责：

- 统一呈现 workspace 的本地恢复状态和可选远端同步状态。
- 默认依赖 BackupService 和 SnapshotService。
- 汇总最近 backup、最近 snapshot、restore dry-run 结果、workspace upgrade 状态和 index rebuild 建议。
- 当 OptionalGitService 可用且用户启用时，附加展示 Git branch、commit、remote、push/pull 状态。
- 对 GUI 提供统一的“Backup & Sync”页面数据模型。

VersioningService 不得把 Git 状态作为 promote、audit、index、archive、restore 的前置条件。

### OptionalGitService

职责：

- 作为高级用户可选同步模块，提供 Git status、diff、commit、tag、pull、push 和冲突提示。
- 在 Git 不存在、仓库未初始化或用户未配置远端时优雅降级。
- 在 push/public repo 前要求 secret-scan clean 或明确风险确认。
- 不执行 destructive Git 操作，除非用户二次确认。
- 不参与普通用户 Local Only mode 的必需流程。

OptionalGitService 不能成为 EXE 的必需依赖，也不能成为 BackupService 或 SnapshotService 的底层实现。

## 3. Local Zip Backup

本地 zip 备份是普通用户默认备份方式。它应是可复制、可校验、可离线保存的单文件或分卷文件。

建议备份内容：

```text
backup-root/
  manifest.json
  knowledge/
  config/
  templates/
  reports/
  docs/
  README.md
  AGENTS.md
```

可选内容：

```text
backup-root/
  .kb/index.sqlite
```

默认不包含 `.kb`，因为 SQLite 索引可删除重建。用户可选择包含 `.kb` 来加快大 workspace 恢复，但恢复后仍应运行：

```bash
python scripts/kb.py index
python scripts/kb.py doctor
```

## 4. Backup Naming

备份文件名必须可排序、可读、避免覆盖。

建议格式：

```text
pkb-backup-{workspace_slug}-{YYYYMMDD-HHMMSS}-{reason}-{short_hash}.zip
```

示例：

```text
pkb-backup-personal-knowledge-base-20260519-143012-manual-a1b2c3d4.zip
pkb-backup-personal-knowledge-base-20260519-144500-before-promote-b8c9d0e1.zip
pkb-backup-personal-knowledge-base-20260519-150100-before-upgrade-91ab23cd.zip
```

`reason` 应使用稳定枚举，例如：

- `manual`
- `scheduled`
- `before-promote`
- `before-archive`
- `before-restore`
- `before-bulk-import`
- `before-schema-migration`
- `before-destructive-maintenance`
- `before-workspace-upgrade`

## 5. Snapshot Naming

snapshot 是操作前回滚点，命名应体现触发操作和影响范围。

建议目录或 zip 命名：

```text
snapshots/{YYYYMMDD-HHMMSS}-{operation}-{short_hash}/
snapshots/{YYYYMMDD-HHMMSS}-{operation}-{short_hash}.zip
```

示例：

```text
snapshots/20260519-143500-promote-a1b2c3d4.zip
snapshots/20260519-151000-archive-b8c9d0e1.zip
```

snapshot manifest 至少包含：

- `created_at`
- `operation`
- `workspace_path`
- `tool_version`
- `included_paths`
- `excluded_paths`
- `include_kb_index`
- `file_count`
- `total_bytes`
- `content_hash`
- `secret_scan_status`
- `restore_notes`

## 6. Retention Policy

备份和 snapshot 必须有保留策略，避免长期无限增长。

建议默认策略：

- 手动 backup：默认永久保留，用户手动删除。
- scheduled backup：保留最近 30 个，或最近 90 天。
- pre-operation snapshot：保留最近 20 个，或最近 30 天。
- before schema migration / workspace upgrade：保留至少最近 5 个，建议用户导出到外部位置。
- destructive maintenance snapshot：保留至少最近 10 个。

删除旧备份或 snapshot 是破坏性操作，GUI 必须显示文件名、大小、创建时间和删除数量，并要求确认。

## 7. Restore Flow

恢复流程必须可预览、可取消、可验证。

建议流程：

1. 用户选择 backup 或 snapshot。
2. BackupService 校验 zip、manifest、hash 和必要目录。
3. 执行 restore dry-run，显示将新增、覆盖、删除或跳过的文件。
4. 恢复前对当前 workspace 创建 `before-restore` snapshot。
5. 用户确认恢复。
6. 写入文件时使用临时目录和原子替换，避免半恢复状态。
7. 恢复后运行 `python scripts/kb.py index`。
8. 恢复后运行 `python scripts/kb.py doctor`。
9. 显示 result summary、log path 和后续建议。

restore 不应要求 Git checkout。Git 可作为高级用户额外恢复路径，但不能替代本地 restore。

## 8. Operations Requiring Automatic Snapshot

以下操作需要自动 snapshot：

- promote
- archive
- restore
- bulk import
- schema migration
- destructive maintenance
- workspace upgrade

说明：

- `audit`、`search`、`index` 默认不是破坏性操作，不需要自动 snapshot。
- `reindex` 只重建 `.kb/index.sqlite`，通常不需要备份 Markdown，但 GUI 可在用户选择 destructive maintenance 时触发 snapshot。
- `vacuum` 只作用于 SQLite 索引，必须显式触发，但不应被包装成 Markdown 数据备份需求。
- schema migration 如果会影响 Markdown/frontmatter，必须先 snapshot。

## 9. `.kb` Backup Policy

默认策略：

- 不包含 `.kb/index.sqlite`。
- 恢复后从 Markdown 重建 SQLite index。

可选策略：

- 用户可勾选“include index for faster restore”。
- 备份 manifest 必须记录 `include_kb_index=true`。
- 恢复后仍应运行 `doctor`，必要时提示重新 `index`。

原因：

- Markdown 是事实来源。
- SQLite 是索引层。
- `.kb/index.sqlite` 可以删除重建。
- 备份核心应优先保护 Markdown、config、templates、reports 和文档。

## 10. Secret And Privacy

备份与安全的关系：

- 备份前应运行 secret-scan，或至少显示“备份可能包含私密内容”的明确提醒。
- 备份文件可能包含私有笔记、客户信息、源码摘录或内部经验，默认不应上传到公开位置。
- public repo 不等于 backup。公开 Git 仓库不能替代私有本地备份，也不能保证包含所有用户数据。
- Optional Git Sync push 前必须提示 public/private repo 风险。
- 备份 manifest 不应记录真实 secret 值。
- secret-scan 报告可记录风险摘要和检查时间，但不应把敏感原文复制进 manifest。

## 11. GUI Boundary

未来 GUI 页面应叫 `Backup & Sync`，而不是只叫 `Git Sync`。

页面默认能力：

- 创建本地 backup。
- 查看最近 backups。
- 创建手动 snapshot。
- 查看自动 snapshots。
- restore dry-run。
- restore。
- 配置备份目录和保留策略。
- 查看 secret/privacy 提醒。

可选能力：

- 启用 Optional Git Sync。
- 查看 Git status。
- commit/tag/pull/push。
- 显示 Git 冲突和远端同步错误。

Git 不存在时，`Backup & Sync` 页面仍应完整可用。

## 12. Acceptance Boundary

本设计不改变当前 CLI 行为：

- 不修改 `knowledge/**/*.md`。
- 不修改 SQLite schema。
- 不改变 search/index/audit 行为。
- 不实现 GUI。
- 不实现 RSS、向量检索、MCP、Codex Skill 或 EXE 打包。

未来实现时，应先补 service 层和测试，再接 GUI。实现完成前，文档只定义边界，不作为已交付功能声明。
