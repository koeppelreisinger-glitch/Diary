# Echo 日记补写功能 — 后端改造实施清单

> 基于对现有代码的完整阅读（models、services、routes），不写代码，只做设计。

---

## 1. 改造目标

### 1.1 要解决的核心问题

当前 Echo 的会话是**一次性闭合**的：`recording → completing → completed`，一旦 complete 便锁死，summary 已生成、五子表已写入，再无写入通道。

新需求要实现的是**日记可持续演进**：

- 用户可以在事后**手动改写**已生成的日记正文（Path A）
- 用户可以继续**通过 AI 对话追加**新内容（Path B）
- 两种路径都必须最终触发五子表和摘要的刷新

### 1.2 为什么不是"多加一个编辑接口"

当前的 `PUT /daily-records/{id}` 只支持 `user_note / keywords / tags_to_add / tags_to_remove`，即**轻量元数据编辑**，不触及日记正文，也不重建结构化子表。

新需求与之本质不同：

| 维度 | 现有轻量编辑 | 新需求 |
|------|------------|--------|
| 修改对象 | 标注/元数据 | 日记正文（body） |
| 是否重建五子表 | 否 | 是 |
| 是否触发 AI | 否 | Path B 是 |
| 是否重新生成摘要 | 否 | 是 |

### 1.3 为什么必须严格区分两种路径

Path A（手动改正文）和 Path B（AI 追加）在语义上完全不同：
- Path A 是**用户主权操作**，不应触发 AI，避免用 AI 覆盖用户手动写的文字
- Path B 是**AI 辅助操作**，不应触发结构化重建时把手动的旧正文丢弃
- 混淆两者会导致"用户改了正文→AI 追加时又覆盖了"这类数据一致性灾难

---

## 2. 现状与冲突点

基于代码阅读，以下是具体冲突：

### 2.1 `Conversation.status` 锁死后续消息

```python
# conversation_service.py L154
if conv.status in ("completing", "completed"):
    raise ErrorResponseAPIException(409, "会话已结束或正在结算中，不允许继续发送消息")
```

**冲突**：Path B 需要在 `completed` 之后继续发消息。

### 2.2 `SummaryGenerationService` 有防重校验，且只创建不更新

```python
# summary_generation_service.py L55-61
existing_record_id = (await db.execute(stmt_dup)).scalar_one_or_none()
if existing_record_id:
    raise ConflictException("该会话已生成日记录")
```

**冲突**：无论 Path A 还是 Path B，重新生成结构化内容时都需要**更新现有记录**而非创建新记录。

### 2.3 `summary_text` 定位模糊：既是摘要又是正文

```python
# daily_record.py L33
summary_text: Mapped[str] = mapped_column(Text, nullable=False)
```

当前没有专门的"正文"字段。`summary_text` 在生成时扮演的角色实际上是 AI 写的日记正文，但语义上它叫"摘要"。前端现有的 `detail.html` 已经把它当作完整日记正文展示了。

**冲突**：Path A 需要一个可以被用户**完整覆写**的正文字段，而 `summary_text` 目前是 AI 产物，用户改了之后重新生成会覆盖。

### 2.4 会话与日记记录的 1:1 关系约束

```python
# daily_record.py L22
conversation_id: Mapped[uuid.UUID] = mapped_column(UUID, unique=True, nullable=False)
```

**不冲突**：Path B 方案中我们继续使用同一个 conversation（只是让它能再次接收消息），所以这个约束不用动。

---

## 3. 数据模型改造建议

### 3.1 推荐方案：在 `daily_records` 增加 `body_text` 字段

**新字段**：

```
body_text: Text, nullable=True
```

**语义定位**：

| 字段 | 新定位 |
|------|--------|
| `body_text` | **日记正文（可编辑主文本）**。初始由 AI 填充，用户可完整覆写（Path A），AI 追加后也会追加到这里（Path B）。这是结构化提取的"源文本"。 |
| `summary_text` | **摘要/标题**。字数更短，供历史列表、今日总结头部概要展示。可由 `body_text` 自动派生，也可保持当前 AI 首次生成的值不变（MVP 阶段可不立即重新生成摘要）。 |
| `user_note` | 保持原定位：用户手写的私密备注，不参与结构化提取。 |

**理由**：
1. 完全增量，不改现有字段的类型或约束
2. 新旧接口可以同时运行：旧 history 接口继续读 `summary_text`（摘要）；新日记页读 `body_text`（正文）
3. 将来如果需要版本历史，`body_text` 是最自然的 diff 目标

**MVP 简化选项**（如果不想加新字段）：  
把 `summary_text` 直接当 `body_text` 用——用户改 `summary_text` 即等于改正文。但这样摘要和正文混为一谈，将来很难拆分，不推荐。

### 3.2 `Conversation` 状态机扩展

新增状态 `"open"`（可补写中）：

```
recording → completing → completed → open → completing_supplement → completed
```

或更简洁的方案（推荐）：**直接放开 `completed` 状态下的消息发送**，靠 Path 类型参数区分，避免引入新状态值：

```
POST /conversations/{id}/messages
  body: { content, content_type, supplement: true }
```

当 `supplement=true` 时，服务层跳过 status 校验，允许 `completed` 会话继续接收消息。

---

## 4. 行为分流设计

### 4.1 Path A — 手动编辑正文

**前端操作**：用户在日记页面直接编辑正文文本框，点击"保存"。

**后端处理流程**：
```
用户提交新正文
→ PUT /api/v1/daily-records/{id}/body   (新接口，见第 5 节)
→ 更新 daily_records.body_text
→ 触发结构化重建（重新从 body_text 提取五子表）
→ 更新 daily_records.summary_text（可选：MVP 阶段跳过，保留原摘要）
→ 返回更新后的 DailyRecord 完整对象
```

**不触发 AI**，无需访问 conversation，服务层完全独立。

**后端如何识别**：调用的接口路径决定，没有歧义。

### 4.2 Path B — 追加补充内容

**前端操作**：用户在日记页面的"继续补充"对话框里输入新内容，AI 回复，完成后点击"保存本次补充"。

**后端处理流程**：
```
用户发送补充消息（supplement=true）
→ POST /api/v1/conversations/{id}/messages?supplement=true
→ 跳过 completed 状态校验，正常写入消息
→ AI 生成回复，写入消息
→ （可选：每轮消息后不自动重建，等用户点"保存本次补充"时才重建）

用户点击"保存本次补充"
→ POST /api/v1/daily-records/{id}/rebuild   (新接口，见第 5 节)
→ 从 conversations.messages 读取所有用户消息（含本次补充）
→ 把提取出的新事件/情绪/消费/地点软删旧子表记录，写入新的
→ 把新 AI 生成的日记追加到 body_text 后面
→ 返回更新后的 DailyRecord
```

**触发 AI**，需要访问 conversation 消息历史。

---

## 5. 接口设计脚本

### 5.1 获取今天的"日记状态"（含正文）

```
GET /api/v1/daily-records/today
```

**现有接口**，只需把响应中加入 `body_text` 字段。不改路径，不改语义，已有 frontend 兼容。

新增响应字段：
```json
{
  "body_text": "今天工作很忙...",  // 新增，可为 null（旧记录）
  "can_supplement": true           // 新增：今天是否可以继续补写
}
```

`can_supplement` 判断逻辑：今天有 conversation 且不在 completing 中。

---

### 5.2 手动编辑正文并触发重建（Path A）

```
PUT /api/v1/daily-records/{record_id}/body
```

请求体：
```json
{
  "body_text": "用户修改后的完整日记正文..."
}
```

处理逻辑：
1. 鉴权：`record.user_id == current_user.id`
2. 校验：`body_text` 不能为空（允许空白字符 strip 后为空则拒绝）
3. 更新 `daily_records.body_text`
4. 调用 `DiaryRebuildService.rebuild_from_text(record, body_text)`（见第 6 节）
5. 返回完整 `DailyRecordDetailResponse`

---

### 5.3 提交补充消息（Path B，每一轮对话）

```
POST /api/v1/conversations/{conversation_id}/messages
```

**改造现有接口**，新增请求字段：
```json
{
  "content": "下午还去了趟超市买了些蔬菜",
  "content_type": "text",
  "is_supplement": true    // 新增：标记这是补充消息
}
```

处理变化：
- 当 `is_supplement=true` 时，跳过 `completed` 状态的 409 报错
- 其余逻辑（AI 回复、写入消息）完全不变

---

### 5.4 保存本次补充并触发重建（Path B，最终确认）

```
POST /api/v1/daily-records/{record_id}/supplement
```

请求体：
```json
{
  "append_text": "（可选）用户最终确认追加的文字摘要，留空则由后端从新增消息中自动提取"
}
```

处理逻辑：
1. 鉴权
2. 读取 conversation 中所有消息（含补充部分），提取**增量**事件/情绪/消费/地点
3. 增量写入五子表（软删再写，或只写新的）
4. 把新提取的日记正文追加至 `body_text`
5. 返回完整 `DailyRecordDetailResponse`

---

### 5.5 现有 complete 接口

```
POST /api/v1/conversations/{conversation_id}/complete
```

**保留原语义不变**：第一次记录结束时调用，生成初版 `body_text` 和五子表。  
唯一变化：`SummaryGenerationService` 要写入 `body_text`（原来只写 `summary_text`）。

---

## 6. Service 设计脚本

### 现有 Service 改造

| Service | 改造内容 |
|---------|---------|
| `ConversationService.send_message` | 新增 `is_supplement` 参数，跳过 `completed` 状态校验 |
| `SummaryGenerationService.generate_for_conversation` | 首次生成时同时写 `body_text`（值与 `summary_text` 初始相同或来自 AI 全文） |
| `DailyRecordService.update_record` | 保持现有逻辑不动（只管 note/keywords/tags） |

### 新增 Service

#### `DiaryRebuildService`

**职责**：给定源文本（`body_text` 或最新消息），重新提取结构化数据并写入五子表。

核心方法：

```python
async def rebuild_from_text(
    db: AsyncSession,
    record: DailyRecord,
    new_body_text: str,
    mode: Literal["replace", "append"] = "replace"
) -> DailyRecord:
    """
    replace: 软删全部旧子表数据，重新提取写入（Path A 用）
    append: 只软删 source=="ai" 的旧子表数据，追加新提取结果（Path B 用）
    """
```

步骤：
1. 根据 mode 软删目标子表记录
2. 调用现有 `_extract_*` 规则层（与 SummaryGenerationService 共享）
3. 写入新子表记录
4. 更新 `body_text`（和可选的 `summary_text`）
5. 返回刷新后的 record

#### `DiaryContinuationService`（Path B 专用）

**职责**：路由追加请求。判断今天是否可以继续，协调消息发送和最终重建。

核心方法：
```python
async def check_can_supplement(session, user_id) -> bool
async def rebuild_from_supplement(session, record_id, user_id) -> DailyRecord
```

---

## 7. 重新生成与一致性策略

### 7.1 源文本（Source of Truth）

```
body_text  ←  是唯一权威源
```

- 五子表（events/emotions/expenses/locations/tags）都是从 `body_text` 派生的
- `summary_text` 是 `body_text` 的摘要，是 `body_text` 的副产物
- `user_note` 独立，不参与派生链

### 7.2 刷新顺序

```
1. 写入新 body_text（事务保护）
2. 软删目标子表旧记录（同一事务）
3. 从 body_text 提取结构化数据
4. 写入新子表记录（同一事务）
5. （可选）重新生成 summary_text
6. commit
```

**关键原则**：步骤 1-4 必须在同一个数据库事务内，避免部分写入导致数据不一致。

### 7.3 history 模块的变化

history 模块读的是 `daily_records` 和五子表，只要每次 rebuild 后数据是最新的，**history 接口完全不需要修改**。

---

## 8. 与现有 history 模块的关系

**结论：history 模块不需要改动。**

history 接口读的数据链条：
```
GET /history/events     → record_events
GET /history/emotions   → record_emotions
...
GET /history/daily-records/{date} → daily_records + 五子表 JOIN
```

只要 `DiaryRebuildService` 每次重建后，五子表和 `body_text` 都是最新的，history 接口自然反映最新状态。这是最大化复用的核心优势。

唯一可选改动：history 详情接口增加 `body_text` 字段响应（调用方选读）。

---

## 9. 参数与校验规则

| 场景 | 处理方式 |
|------|---------|
| 今天没有 daily_record | GET today 返回 `has_record=false`；PUT body 返回 404 |
| 今天没有 conversation | `can_supplement=false`；调 supplement 接口返回 409 |
| 追加内容为空 | `is_supplement=true` 但 content 为空 → 400，与现有逻辑一致 |
| 手动正文为空（strip 后）| PUT body 返回 400，不允许清空 body_text |
| 同一天多次补写 | 每次 supplement 都 append 到 body_text 尾部，五子表增量追加，不限次数 |
| 已 completed 仍可追加 | `is_supplement=true` 时跳过 completed 校验 |
| completing 状态追加 | 返回 409（正在生成中，禁止并发写入） |

---

## 10. 安全与软删除规则

### 10.1 用户绑定

所有新接口都必须：
```python
if record.user_id != current_user.id:
    raise ForbiddenException("无权修改该记录")
```

### 10.2 子表重建时的软删除策略

**推荐方案：软删除 + 重写（不物理删除）**

理由：
- 与现有 `deleted_at` 机制一致，不破坏审计链
- 历史版本可追溯（如果将来需要）
- 软删 + 重写比物理删除更安全，不会因事务失败留下脏空洞

Path A（replace 模式）软删目标：
- `source IN ("ai", "user")` 的所有子表记录（全量替换）
- 例外：`tags` 保留 `source="user"` 的记录（用户手动加的标签不因正文重写而丢失）

Path B（append 模式）软删目标：
- 只软删 `source="ai"` 的旧子表记录，保留用户确认过的（`is_user_confirmed=true`）
- 追加新提取的记录（`source="ai"`）

---

## 11. 联调顺序

```
Step 1: 用户第一次聊天并 complete
        → conversation.status = "completed"
        → daily_record 创建，body_text 初始化

Step 2: 打开日记页（GET /daily-records/today）
        → 展示 body_text（初版正文）
        → 展示 AI 提示语 "还有什么要补充的吗？"
        → can_supplement=true

Step 3: 用户手动修改正文（Path A）
        → PUT /daily-records/{id}/body
        → 检查 body_text 已更新
        → 检查五子表已重建（record_events 等）
        → 检查 GET /history/daily-records/{date} 返回最新内容
        → 检查今日总结页（GET /daily-records/today）反映最新

Step 4: 用户追加一段新内容（Path B）
        → POST /conversations/{id}/messages?is_supplement=true
        → AI 回复返回正常
        → POST /daily-records/{id}/supplement
        → 检查 body_text 已追加
        → 检查五子表已更新

Step 5: 刷新历史详情页、历史五表
        → 确认所有数据与最新 body_text 一致
```

---

## 12. 风险提醒

> [!CAUTION]
> **把 `summary_text` 和 `body_text` 混为一谈**  
> 如果继续用 `summary_text` 当正文，Path A 改写后触发重建时 AI 会生成新 `summary_text` 把用户改的内容覆盖掉。必须用独立的 `body_text` 字段隔离。

> [!WARNING]
> **Path B 追加后覆盖 Path A 的手动编辑**  
> 如果 Path B 的 rebuild 用 `replace` 模式而非 `append` 模式，会把用户在 Path A 里手动写的内容冲掉。`DiaryRebuildService` 必须区分 mode。

> [!WARNING]
> **结构化子表重建时的脏数据**  
> 如果软删和新写不在同一个事务里，崩溃时会同时存在旧记录（未删除）和新记录（部分写）。务必事务包裹。

> [!WARNING]
> **conversation 和 daily_record 不同步**  
> Path B 追加了消息但没有调 supplement 接口（用户关掉了页面），会导致消息里有新内容但 body_text 未更新。解决方案：在 GET today 时检测是否有未处理的 supplement 消息，提示用户"有未保存的补充内容"。

> [!NOTE]
> **前端接口路由混淆**  
> 前端必须明确：编辑正文用 `PUT /body`；追加 AI 内容用 `POST /supplement`；轻量标注编辑（tags/note/keywords）继续用现有 `PUT /daily-records/{id}`，三者不可混用。

---

## 13. 最终开发顺序建议

### 第一阶段（数据层 + Path A，最高价值）

1. Alembic migration：给 `daily_records` 加 `body_text TEXT` 字段
2. 修改 `SummaryGenerationService.generate_for_conversation`：首次生成时同时写 `body_text`
3. 实现 `DiaryRebuildService`（replace 模式，Path A 用）
4. 新增路由 `PUT /daily-records/{id}/body`
5. 修改 `GET /daily-records/today` 响应，增加 `body_text` 和 `can_supplement`

**验证点**：第一次 complete 后能看到 body_text；手动改正文后五子表同步更新。

### 第二阶段（Path B，AI 追加）

6. 修改 `ConversationService.send_message`：accepted `is_supplement=True` 时跳过 completed 校验
7. 实现 `DiaryContinuationService.rebuild_from_supplement`（append 模式）
8. 新增路由 `POST /daily-records/{id}/supplement`
9. 修改 `GET /daily-records/today`：增加"有未保存补充消息"检测逻辑

**验证点**：completed 后能继续发消息；supplement 后 body_text 追加正确；五子表仅更新 AI 部分。

### 第三阶段（前端联调）

10. 日记页新增正文编辑器（textarea），调 `PUT /body`
11. 日记页新增"继续补充"对话区，调 `POST /conversations/messages?is_supplement=true`
12. "保存本次补充"按钮，调 `POST /supplement`
13. 端到端验收：Path A + Path B 独立运行，history 页面自动更新
