# AI Memory Algorithm Review

本文定义 v2.4.0 AI 助手 memory 和 context 的算法设计边界。当前阶段只做设计，不实现真实 ConversationStore，不实现持久化 MemoryService，不保存真实长期记忆，不接真实 AI，不接 OpenAI、本地模型或 ModelScope，不下载模型，不做 RSS/vector，不执行 mutation，不修改 `knowledge/**/*.md`，不修改 SQLite schema，也不改变 `search` / `index` / `audit` 行为。

本设计的核心目标是：先用可解释、低风险、可审计的规则和用户显式意图生成 MemoryCandidate，再通过 policy filter 和人工确认决定是否保存。任何评分、排序或候选生成都不能自动保存长期记忆。

## 1. Algorithm Principles

- MemoryCandidate 不是 saved memory。
- Score 只用于排序、去重和提示优先级。
- 高分也不能自动保存。
- 用户确认是唯一保存条件。
- Sensitive / forbidden 内容必须在候选阶段被阻断。
- Memory 不得作为 formal knowledge。
- Memory 不得绕过 `SearchService` formal 层边界。
- Memory 不得用于 mutation approval、snapshot、plan hash、reviewer identity 或安全执行门禁。
- LLM-based extraction、embedding similarity 和 automatic clustering 都是后置能力，不属于 v2.4.0 实现范围。

## 2. Memory Candidate Detection

候选检测只产生 `MemoryCandidateCard`，不产生 saved memory。

### Explicit User Signal

最高优先级信号来自用户明确表达：

- “记住”
- “以后默认”
- “下次都”
- “以后请”
- “我习惯”
- “默认用”
- “后续都按”

Rules:

- 显式信号可以生成 candidate。
- 显式信号仍必须经过 policy filter。
- 显式信号不能覆盖 sensitive block。
- 用户说“不要记住”“别保存”“只这次”时必须抑制候选。

### Repeated Preference

重复偏好是跨多轮或多会话出现的稳定倾向，例如多次要求同一种输出语言、验收格式或工作流程。

Rules:

- 重复偏好可以提高排序分。
- 当前阶段只设计检测，不实现跨会话统计。
- 重复偏好必须保留来源消息 ids。
- 重复偏好不能从敏感内容或未审核 raw 原文中推断。

### Future Usefulness

候选应有未来可复用价值：

- 输出格式偏好。
- 工作流偏好。
- 项目内稳定规则。
- 长期目标。
- 常用约束，例如“提交前先跑指定测试”。

低复用价值内容不应生成候选：

- 一次性任务细节。
- 临时路径。
- 临时 debug 信息。
- 当前对话中的普通事实。

### Stability

Stability 表示该偏好是否可能跨会话稳定。

High stability examples:

- “默认用中文总结。”
- “以后所有设计阶段先写边界再写实现。”

Low stability examples:

- “这次先不要跑完整测试。”
- “今天只看这个文件。”

Rules:

- Low stability 不应生成长期记忆候选，除非用户显式要求。
- 会话摘要不等于长期稳定偏好。

### Sensitivity Risk

敏感性风险会降低分数或直接 block。

Block examples:

- secrets / tokens / passwords.
- customer privacy data.
- quarantine / rejected content.
- sensitive inferred preference.

### Uncertainty

不确定性来自含糊表达、反讽、上下文不足或 AI 推断。

Rules:

- 高不确定性应降低分数。
- 无法判断时不生成候选，或生成需要更明确确认的候选。
- AI 不得把自己推断出的敏感偏好保存为候选。

### Source Review Penalty

候选如果依赖 raw、distilled、research、archived 或 `review_required=true` 内容，必须加 source review penalty。

Rules:

- 未审核内容不能作为正式项目规则。
- 未审核内容默认不生成长期记忆候选。
- 如果用户明确要求记录一个与未审核内容有关的个人偏好，候选必须显示“未经审核，不能作为正式项目规则”。
- Quarantine / rejected 来源直接 block。

## 3. Recommended Algorithm

v2.4.0 推荐顺序：

```text
User message / UI event
  ↓
Rule-based explicit intent detector
  ↓
Candidate type classifier
  ↓
Policy filter
  ↓
Sensitive content filter
  ↓
Deduplication check
  ↓
Candidate scoring
  ↓
MemoryCandidateCard
  ↓
Human confirmation
  ↓
Future MemoryService save
```

先采用：

- rule-based + explicit user intent.
- policy filter.
- human confirmation.

后置能力：

- LLM-based extraction.
- embedding similarity.
- automatic clustering.

Rationale:

- Rule-based explicit intent is auditable and predictable.
- Policy filter prevents memory pollution before candidate display.
- Human confirmation is the only acceptable persistence gate.
- LLM extraction can increase recall later, but it must not be the first baseline because false memory candidates and sensitive inference risks are higher.

## 4. Candidate Type Classification

Candidate type must be one of:

- `preference`
- `format`
- `workflow`
- `personal_rule`
- `long_term_goal`

Classification rules:

- `format`: output shape, language, summary style, checklist shape.
- `workflow`: repeated task sequence or validation flow.
- `preference`: general user preference that is not a workflow or format.
- `personal_rule`: user-approved working rule, not a project formal rule.
- `long_term_goal`: stable direction or priority.

Anything outside these types should not become a saved memory in v2.4.0 design.

## 5. Memory Candidate Scoring

Suggested scoring model:

```text
score =
  explicit_user_signal
  + repeated_preference
  + future_usefulness
  + stable_across_sessions
  - sensitivity_risk
  - uncertainty
  - source_unreviewed_penalty
```

Field intent:

| Field | Direction | Meaning |
| --- | --- | --- |
| `explicit_user_signal` | positive | User explicitly asked to remember or set a default |
| `repeated_preference` | positive | Same preference appears repeatedly |
| `future_usefulness` | positive | Candidate will likely help future sessions |
| `stable_across_sessions` | positive | Candidate is not one-off |
| `sensitivity_risk` | negative / block | Candidate may include private or sensitive content |
| `uncertainty` | negative | Meaning or user intent is unclear |
| `source_unreviewed_penalty` | negative / block | Candidate depends on unreviewed source |

Rules:

- Score only ranks pending candidates.
- Score can decide whether to show now, defer or suppress.
- Score cannot save memory.
- Score cannot override sensitivity block.
- Score cannot override user rejection.
- Score cannot turn raw/distilled/research into formal knowledge.

Recommended decision bands for future implementation:

| Band | Behavior |
| --- | --- |
| blocked | Do not show as candidate; show privacy/error notice if useful |
| low | Suppress by default unless explicit user signal exists |
| medium | Show candidate only when low sensitivity and useful |
| high | Show candidate prominently, still requiring confirmation |

## 6. Deduplication

Deduplication happens before showing a repeated candidate and before accepting a candidate.

Required checks:

- Normalize text.
- Compare type.
- Compare source.
- Similarity threshold.
- Rejection fingerprint.
- Accepted memory merge suggestion.

### Normalize Text

Normalization should:

- trim whitespace.
- normalize punctuation.
- collapse repeated spaces.
- lowercase ASCII tokens.
- remove conversational filler.
- preserve user meaning and language.

### Compare Type

Memory candidates with different types should not be merged automatically.

Examples:

- `format`: “默认输出 Markdown 表格。”
- `workflow`: “提交前先跑 audit 和 smoke tests。”

These can both mention “默认”, but they are different memory types.

### Compare Source

Compare:

- `conversation_id`
- `source_message_ids`
- originating UI action.
- whether the source was explicit user intent or inferred repeated preference.

Source comparison prevents a weak inference from overwriting explicit user memory.

### Similarity Threshold

Future implementations can use rule-based string similarity first.

Suggested behavior:

- exact normalized match: duplicate.
- high similarity same type: suggest merge.
- medium similarity: show possible duplicate warning.
- low similarity: allow separate candidate.

Embedding similarity is a future enhancement and must still obey privacy and local/cloud policy.

### Rejection Fingerprint

Rejected candidates should create a suppression fingerprint:

```text
fingerprint = hash(normalized_type + normalized_text + sensitivity_band)
```

Rules:

- Rejected candidate should not repeatedly bother the user.
- A materially changed user statement can create a new candidate.
- Suppression should expire according to retention policy.

### Accepted Memory Merge Suggestion

When an accepted memory resembles an existing memory:

- show merge suggestion.
- preserve original memory until user confirms merge.
- do not silently overwrite.
- keep source conversation references.

## 7. Sensitive Content Filter

Sensitive filter runs before scoring and before cloud context preview.

Block:

- secrets / tokens / passwords.
- private keys.
- customer data.
- raw unreviewed content.
- quarantine / rejected content.
- sensitive inferred preference.
- credential-like strings.
- private business identifiers when marked sensitive.

Rules:

- Blocked candidate cannot be accepted.
- Error or privacy notice must not echo the sensitive value.
- Secret-scan / sensitive marker should block cloud send.
- Sensitive content cannot be moved into conversation summary as a workaround.
- User confirmation cannot override quarantine / rejected source block in v2.4.0 design.

## 8. Context Selection Algorithm

Context selection must remain service-layer controlled. It must not read Markdown, SQLite, `.kb/tasks/` or backup zip directly.

Priority:

1. 当前打开文档。
2. 用户选中搜索结果。
3. formal `SearchService` top-k.
4. 用户确认的长期记忆。
5. 当前任务 / 当前 plan.
6. 用户明确允许的 archived/raw/distilled，必须 warning.

Algorithm:

```text
Intent request
  ↓
Resolve capability and policy
  ↓
Collect explicit UI context
  ↓
Add selected document/result metadata
  ↓
Call SearchService for formal top-k when needed
  ↓
Add confirmed memory only if allowed
  ↓
Add task/plan references through service
  ↓
Apply denied-source filter
  ↓
Apply token budget and ranking
  ↓
Build context preview for cloud provider
  ↓
Record context source ids for citations/audit
```

Forbidden:

- `entire_workspace`
- `all_markdown`
- direct sqlite
- direct filesystem
- `.kb/tasks` direct read
- backup zip direct read
- unbounded conversation history
- all raw / all distilled

Rules:

- Knowledge-backed answers require citations.
- If no citation exists, the assistant cannot claim the answer came from the knowledge base.
- Raw/distilled/research/unconfirmed context must show warning: `未经审核，不能作为正式项目规则`.
- Context source ids must be recorded for audit.
- Cloud context must require preview and confirmation.

## 9. Short-term Context Algorithm

Short-term memory should use:

- sliding window of recent turns.
- current UI context.
- explicit selected documents/results.
- current plan/task references.
- token budget.

Recommended future defaults:

- recent conversation window: last 6 to 10 turns.
- selected search results: user-selected ids only, otherwise service top-k.
- formal search top-k: default 5 to 10.
- memory items: top 3 to 5 confirmed memories by relevance and policy.
- archived/raw/distilled: none by default.

Rules:

- Sliding window cannot include all conversation history.
- Conversation summary can compress older turns, but it remains conversation context, not memory.
- Current page/document context outranks older conversation turns.

## 10. Performance Constraints

Required constraints:

- `top_k` limits for formal search.
- token budget for context build.
- pagination for search results.
- summary cache for long conversations.
- no startup scan.
- no full workspace context.
- conversation load limit.
- memory list pagination.

Performance rules:

- Assistant panel open must not scan conversations or memory directories.
- Startup must not scan `ai/conversations/`, `ai/memory/`, `knowledge/` or `.kb/tasks/`.
- Search uses `SearchService`; it must not read Markdown bodies.
- Document body loads only through `DocumentService.open_document` for one explicit document.
- Memory list view must page results and avoid loading all memory at once.
- Conversation history view must page conversations and messages.
- Context build must stop at budget and surface omitted context in metadata.

## 11. Accuracy Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| False memory candidate | Require explicit signal first; use human confirmation |
| Sensitive preference inference | Block sensitive inferred preference |
| Duplicate memory prompts | Normalize, fingerprint rejection, merge suggestion |
| Raw content pollution | Source review penalty and warning |
| Context overreach | Deny entire workspace / all markdown / direct filesystem |
| Citation gaps | Require citations for knowledge-backed answers |
| LLM extraction hallucination | Keep LLM extraction future-only until golden tests exist |

## 12. Acceptance Criteria

- Detection covers explicit user signal, repeated preference, future usefulness, stability, sensitivity risk, uncertainty and source review penalty.
- Recommended algorithm starts with rule-based explicit intent, policy filter and human confirmation.
- LLM extraction, embedding similarity and automatic clustering are explicitly future/posterior.
- Scoring formula is documented and cannot auto-save memory.
- Deduplication covers normalization, type/source comparison, similarity threshold, rejection fingerprint and merge suggestion.
- Sensitive content filter blocks secrets, customer data, raw unreviewed content, quarantine/rejected content and sensitive inferred preferences.
- Context selection priority and forbidden scopes are explicit.
- Performance constraints cover top-k, token budget, pagination, summary cache, no startup scan, no full workspace context, conversation load limits and memory pagination.
