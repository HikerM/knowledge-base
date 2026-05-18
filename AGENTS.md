# Agent Rules

这个仓库是个人开发知识库，用来长期沉淀开发规则、模板、代码片段、检查清单和 Agent 可用上下文。

## 事实来源

- Markdown 是事实来源。
- SQLite 是索引层，不是事实来源。
- `.kb/index.sqlite` 可以删除重建，不应手工编辑。

## 默认信任顺序

1. rules
2. checklists
3. snippets
4. distilled
5. raw

Codex 默认只能把 `rules`、`checklists`、`snippets` 当作正式可执行知识。`raw` 只能作为参考，`distilled` 是 AI 或人工提炼层，仍需人工审核。

## 防污染规则

- Codex 不得把 raw 当正式规则。
- Codex 不得把 distilled 当正式规则。
- Codex 使用知识库时必须优先用 `python scripts/kb.py search` 检索正式层。
- 如果使用 raw 或 `research` 结果，必须明确标注“未经审核，不能作为正式项目规则”。
- Codex 不得自动 promote，除非用户明确要求。
- Codex 不得删除 rejected/deprecated 的历史记录，除非用户明确要求。
- Codex 不得把 `review_required=true` 的内容作为项目决策依据。
- Codex 不得使用 quarantine 中的内容指导项目实现。

## 必须遵守的治理闭环

```text
外部内容 -> raw -> distilled -> review-queue -> promote -> rules/snippets/checklists -> search -> 项目使用 -> 实践验证 -> audit/stale/conflicts/deprecate -> 更新、废弃、修正
```

Codex 在这个仓库内工作时必须维护这个闭环：外部内容先进入 raw；AI 提炼只能进入 distilled；正式知识只能通过人工 promote 进入 rules、snippets、checklists；项目使用默认只能通过 search 读取正式层；实践反馈必须通过 audit、stale、conflicts、deprecate 或后续修正回流。

## 写入规则

- 不要把网上内容无审核直接放入 rules。
- 新知识必须保留 `source_url`、`status`、`confidence`、`last_reviewed`、`reviewed_by`、`verification_method`、`review_required`。
- 如果生成给项目使用的规则，必须写清楚适用场景、不适用场景、验证方式。
- promote 是人工审核动作，必须记录 `reviewed_by`、`confidence`、`valid_for`、`verification_method`、`review_note`。
- 不要存真实密钥、密码、token、客户隐私数据。

## 冲突处理

如果内容过期或冲突，优先使用：

1. `status=active`
2. `review_required=false`
3. `last_reviewed` 更新
4. `source_type` 更权威
5. `confidence` 更高

仍无法判断时，保留冲突并要求人工审核。

## 使用方式

推荐正式检索：

```bash
python scripts/kb.py search --query "react state" --category frontend --top-k 10
python scripts/kb.py open --id 12
```

探索性检索必须用：

```bash
python scripts/kb.py research --query "react state" --category frontend
```

`research` 结果未经审核，只能用于学习和待审核提炼。

## 长期运维与 GUI / EXE 边界

- 后续 GUI 任务必须先设计 service boundary，再实现界面。
- GUI 不得直接读写 Markdown 或 SQLite；必须通过 service/core API 访问。
- GUI 不得通过拼接 CLI 命令字符串作为主要集成方式。
- 长任务必须后台化，提供 task_id、status、progress、cancellation、error detail、log path 和 result summary。
- UI 主线程不得执行 index、audit、secret-scan、reindex、dedupe、conflicts、benchmark、maintenance、Git sync 或 backup/export。
- 不得把 GUI 写成单文件巨型 `App.tsx`、`main.py` 或等价的大型入口文件。
- EXE 相关开发必须保护 workspace 数据；软件安装目录不存用户知识数据，workspace 中的 Markdown 始终优先保护。
- SQLite 索引可删除重建，不得把 `.kb/index.sqlite` 当作事实来源。
- 所有维护命令默认不得删除、不得 promote、不得修改 raw/distilled/rules。
- `vacuum`、`reindex`、cleanup、restore 等操作必须显式触发，并在 GUI 中要求确认。

## 学习雷达边界

- Codex 可以帮助生成 learning queue。
- Codex 可以帮助根据 raw 生成 distill-plan，或把 raw 提炼为 distilled 草稿。
- Codex 不得自动 promote 到 rules、snippets、checklists，除非用户明确要求并提供审核信息。
- Codex 不得把 learning queue 当正式知识。
- Codex 不得抓取不可控全网内容；学习源必须来自 `config/sources.yaml` 或用户明确提供。
- Codex 生成的提炼结果默认 `review_required=true`，只能进入 distilled。
