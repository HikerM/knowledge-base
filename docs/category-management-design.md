# Category Management Design

本文详细定义通用 workspace/template 系统中的分类管理模型。当前阶段只做设计，不实现命令，不修改 `knowledge/**/*.md`，不改变现有 `search`、`index`、`audit` 行为。

## 1. 分类稳定 ID 模型

分类必须使用稳定身份模型：

- `id` / `category_id` 是稳定身份。
- `display_name` 可编辑，只用于 UI、报告标题和用户可读展示。
- `slug` / `path` 可迁移，但不能随便改。
- SQLite 和 frontmatter 应使用 `category_id`。
- `display_name` 不能作为内部 ID。

建议配置：

```yaml
categories:
  frontend:
    id: "frontend"
    category_id: "frontend"
    display_name: "Frontend"
    slug: "frontend"
    path: "knowledge/01-frontend"
    status: "active" # active | disabled | archived | merged
    description: "Frontend engineering knowledge."
    merged_into: ""
    archived_at: ""
    restored_at: ""
    updated_at: "2026-05-19T00:00:00+08:00"
```

身份边界：

- `category_id` 不随翻译、大小写、显示名称、排序前缀或目录迁移改变。
- `display_name` 可从 `Frontend` 改为 `前端工程`，不影响搜索过滤、frontmatter、报告引用和 SQLite 记录。
- `path` 从 `knowledge/01-frontend` 迁移到 `knowledge/frontend` 是高风险操作，需要 migration plan。
- 现有 `category` frontmatter 字段未来应明确承载 `category_id`，而不是显示名称。

这样可以避免分类重命名导致历史卡片、索引、报告、来源配置和模板引用全部失效。

## 2. 编辑分类名称

分类名称编辑分为两种完全不同的动作。

### Edit display_name

安全操作：

- 只修改配置中的 `display_name`。
- 不移动文件。
- 不改 Markdown frontmatter。
- 不重建索引。
- 不改变 `category_id`。
- 不影响 source_url/source_file/promoted_from/supersedes/superseded_by 链路。

示例：

```text
category_id: frontend
display_name: Frontend -> 前端工程
```

输出应包含：

- old display_name。
- new display_name。
- 受影响的 UI/report 展示项。
- 不移动文件、不修改卡片的确认。

### Rename slug/path

危险操作：

- 可能移动目录。
- 可能更新 config references。
- 可能要求更新 frontmatter 中的 path-derived metadata。
- 需要重建 index。
- 可能影响 reports、backup manifest、source references、template references。

Rename slug/path 必须先生成 migration plan，不得直接执行。

计划至少包含：

- current `category_id`。
- old slug/path。
- new slug/path。
- affected files。
- affected reports。
- affected config references。
- expected frontmatter changes。
- source chain impact。
- index rebuild requirement。
- snapshot requirement。
- rollback plan。
- validation commands。

`display_name` 编辑不等于 path rename。未来 GUI 必须把这两个操作分开展示。

## 3. 删除分类

永久 delete 默认禁止。分类包含历史知识、来源链路、报告引用和未来恢复语义，直接删除容易破坏治理闭环。

替代方式：

- `disable`：禁止新增或默认显示，但保留现有文件和索引可见性策略。
- `archive`：把分类标记为归档或移入 archive workspace，默认 search 不包含。
- `merge`：把源分类合并到目标分类，必须 plan-first。
- `restore`：从 disabled/archived 状态恢复。

只有同时满足以下条件时，才允许 advanced delete empty category：

- 分类为空。
- 无 Markdown files。
- 无 source references。
- 无 reports 依赖。
- 无 templates 引用。
- 无 config references。
- 无 `promoted_from`、`supersedes`、`superseded_by`、`source_file` 等历史链路指向该分类。
- 已生成 delete plan。
- 用户人工确认。

非空分类不能直接 delete。删除不能依赖 Git，也不能把 Git history 当作普通用户唯一恢复机制。删除前应优先 local snapshot / backup。

## 4. 合并分类

分类 merge 是高风险治理动作，必须输出 merge plan，不得自动执行。

Merge plan 必须包含：

| field | 内容 |
| --- | --- |
| `source_category` | 被合并的分类 `category_id`、display_name、path、status |
| `target_category` | 目标分类 `category_id`、display_name、path、status |
| `affected_files` | 需要迁移或更新 frontmatter 的 Markdown 文件 |
| `frontmatter_changes` | `category` / `category_id` / topic/canonical 相关变更 |
| `config_references` | categories、sources、learning-radar、extract-rules、quality-rules、templates 中的引用 |
| `source_references` | source_url、source_file、promoted_from、supersedes、superseded_by 链路影响 |
| `report_impact` | reports 中可能失效的历史路径、分类摘要、maintenance 记录 |
| `index_rebuild_requirement` | 是否需要 reindex，是否可增量 index |
| `rollback_plan` | 如何恢复配置、文件路径、frontmatter 和索引 |

Merge plan 还应输出风险：

- source 和 target 是否存在同名文件冲突。
- source 和 target 是否存在相同 `topic_id` 的多个 active formal knowledge。
- source 中是否有 deprecated/rejected/quarantine 历史不能丢失。
- target 分类的 quality rules 是否与 source 不兼容。
- reports 是否需要保留旧路径作为历史引用。

合并后的源分类不应直接删除。推荐将源分类标记为：

```yaml
status: "merged"
merged_into: "target_category_id"
```

这样可以保留历史语义并支持未来 restore 或审计。

## 5. 归档分类

Archive 不是 delete。分类归档用于降低 active working set 和默认搜索噪音，同时保留历史、来源链路和恢复能力。

归档规则：

- archive 后默认 search 不包含该分类。
- archive 可 restore。
- archive 前建议 snapshot。
- archive 后 index 需要更新。
- archive 不能破坏 `source_url`、`source_file`、`promoted_from`、`supersedes`、`superseded_by`。
- quarantine 不能被普通 archive 掩盖，风险隔离语义必须保留。

Archive plan 至少包含：

- category_id、display_name、path、status。
- files count。
- raw/distilled/formal/deprecated/rejected/quarantine count。
- source references。
- reports impact。
- search default impact。
- target archive location 或 archive workspace。
- index update strategy。
- snapshot recommendation。
- restore plan。

归档执行后，应保留可追溯状态：

```yaml
status: "archived"
archived_at: "2026-05-19T00:00:00+08:00"
archive_reason: "low-frequency historical workspace split"
restore_hint: "Use category restore plan before reactivating."
```

恢复分类时必须检查：

- 目标 path 是否被占用。
- 是否有同名 category_id 冲突。
- 是否有多个 active canonical rules。
- 是否需要 reindex。
- 是否需要更新 dashboard/search filters。

## 6. 未来 GUI 分类设置

未来 Category Settings 页面必须显示：

- `id`
- `category_id`
- `display_name`
- `path`
- `status`
- `files count`
- `raw count`
- `distilled count`
- `formal count`
- `sources references`
- `last updated`

Formal count 应至少覆盖：

- `rules`
- `checklists`
- `snippets`

操作：

- edit display name
- disable
- archive
- merge
- restore
- advanced delete empty category

页面约束：

- 默认显示安全操作，危险操作折叠到 advanced 区域。
- edit display name 不应显示成 rename path。
- archive、merge、advanced delete 必须先生成 plan。
- 非空分类 delete 按钮默认禁用，并显示阻塞原因。
- index stale 时仍可显示 metadata，但影响分析必须提示计数可能过期。
- source references 和 report impact 需要显式展示，避免用户误以为分类只是一个目录。

空状态：

- 无分类：提示创建分类或应用模板。
- index missing：只显示配置层分类，提示运行 index 后才能看到准确 counts。
- config invalid：显示 schema 错误和修复入口，不尝试猜测分类。

错误状态：

- path 不存在。
- path 指向 workspace 外部。
- category_id 重复。
- display_name 重复但 category_id 不同。
- merged_into 指向不存在分类。
- archived category 仍被 active source 默认引用。

## 7. Command Planning Boundary

未来分类命令应先提供 plan，再提供 apply。

首批只规划：

```bash
python scripts/kb.py category-list
python scripts/kb.py category-update-display-name
python scripts/kb.py category-archive-plan
python scripts/kb.py category-merge-plan
python scripts/kb.py category-delete-plan
```

其中：

- `category-list` 只读，不写文件，不需要 snapshot，不需要人工确认。
- `category-update-display-name` 会写配置，不移动文件，不需要 snapshot，但需要人工确认。
- `category-archive-plan` 只读，不写文件，不需要 snapshot，不需要确认，输出归档影响分析。
- `category-merge-plan` 只读，不写文件，不需要 snapshot，不需要确认，输出合并影响分析和回滚计划。
- `category-delete-plan` 只读，不写文件，不需要 snapshot，不需要确认，输出阻塞原因和是否满足 empty delete 条件。

未来 apply 命令必须要求人工确认；archive、merge、delete 前应优先 local snapshot / backup。
