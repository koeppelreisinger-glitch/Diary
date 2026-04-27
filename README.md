# Echo AI 日记应用使用与联调教程

Echo 现在分成两套入口：

- **正式用户版 App**：给真实用户使用，只保留注册、登录、写日记、回忆、寻迹等产品功能。
- **联调版 App**：给开发/测试使用，保留接口联调台、原始响应、快捷入口和调试能力。

两套入口共用同一个后端、同一个数据库、同一套登录态。区别只在前端入口和可见功能。

## 1. 入口区分

### 正式用户版

本地访问：

```text
http://localhost:8000/frontend/login.html
```

线上访问：

```text
https://你的域名/frontend/login.html
```

正式版包含：

- 注册账号
- 登录账号
- 今日记录
- 回忆
- 寻迹
- 我的

正式版不包含：

- 联调台
- 原始接口响应
- 测试账号生成
- 后端调试按钮

### 联调版

本地访问：

```text
http://localhost:8000/frontend/debug.html
```

线上访问：

```text
https://你的域名/frontend/debug.html
```

联调版入口包含：

- 进入正式 App
- 打开后端联调台
- 进入今日页
- 进入回忆页

后端联调台：

```text
http://localhost:8000/frontend/test-console.html
```

联调台适合：

- 注册测试账号
- 登录测试账号
- 查看 token
- 跑今日会话闭环
- 查看每个接口的原始响应
- 排查 400 / 401 / 409 / 500 错误

## 2. 本地启动

安装依赖：

```powershell
pip install -r requirements.txt
```

配置 `.env`：

```env
DATABASE_URL=你的数据库连接串
SECRET_KEY=一个安全随机字符串
TOKENHUB_AUTHORIZATION=你的 AI 授权
TOKENHUB_API_KEY=你的 AI Key
TOKENHUB_MODEL=glm-4-flash
```

启动后端：

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

健康检查：

```text
http://localhost:8000/health
```

API 文档：

```text
http://localhost:8000/docs
```

## 3. 正式用户版怎么用

1. 打开：

```text
http://localhost:8000/frontend/login.html
```

2. 点击“注册”。

3. 输入手机号、昵称、密码。

4. 点击“注册并进入”。

5. 系统会自动登录并进入今日页。

6. 在今日页和 Echo 对话，记录当天发生的事情。

7. 点击“结束今日记录”。

8. 等待日记生成。

9. 进入“回忆”查看日记时间流、摘录和照片。

10. 进入“寻迹”查看结构化线索。

## 4. 联调推荐流程

打开联调入口：

```text
http://localhost:8000/frontend/debug.html
```

点击“打开后端联调台”。

### 第一步：注册测试账号

在“认证与用户”区域：

1. 点击“生成测试手机号”。
2. 填写密码，例如：

```text
Password123!
```

3. 填写昵称，例如：

```text
联调用户
```

4. 点击“注册”。

注册成功后，联调台会自动登录并保存 token。

### 第二步：设置时区

在“用户设置”区域：

1. 时区填：

```text
Asia/Shanghai
```

2. 点击“保存设置”。

这样今日记录的日期不会因为默认时区偏移。

### 第三步：创建今日会话

在“会话与聊天”区域：

1. 点击“查询今日会话”。
2. 如果没有会话，点击“创建今日会话”。
3. 会话 ID 会自动回填。

### 第四步：发送消息

在消息输入框里填测试内容，例如：

```text
今天早上起得有点晚，出门的时候很匆忙，连早饭都没有好好吃。上午主要在处理手头的任务，中间被几件小事打断，效率没有想象中高。
```

点击“发送消息”。

可以继续补充：

```text
午饭花了 15 元，在饵丝店吃的。下午状态比上午好一些，把之前没整理完的内容重新看了一遍。生命短暂，珍惜当下。
```

### 第五步：结束记录

点击：

```text
结束今日记录
```

注意：结束接口通常会先返回“生成中”，不是马上返回完整日记。

### 第六步：查询今日记录

在“日记录”区域点击：

```text
查询今日记录
```

如果返回：

```json
{
  "has_record": false,
  "is_generating": true
}
```

说明 AI 还在生成，等几秒后再点一次。

如果返回：

```json
{
  "has_record": true,
  "is_generating": false,
  "record": {}
}
```

说明日记已生成成功。

### 第七步：回到正式 App 验证

打开：

```text
http://localhost:8000/frontend/today.html
```

或：

```text
http://localhost:8000/frontend/index.html
```

确认：

- 今日页能看到完成状态。
- 回忆页能看到最近日记。
- 搜索框能搜到日记正文、关键词、事件、灵感、地点、消费描述。
- 点击“点击查看”能进入搜索结果页。

## 5. 搜索功能联调

正式回忆页：

```text
http://localhost:8000/frontend/index.html
```

搜索示例：

```text
饵丝店
```

或：

```text
生命短暂
```

命中后会显示：

```text
找到 X 段和“关键词”有关的记忆。点击查看
```

点击后进入：

```text
http://localhost:8000/frontend/search.html?q=关键词
```

该页面调用后端：

```http
GET /api/v1/history/daily-records?keyword=关键词&page=1&page_size=10
```

当前搜索范围：

- 日记正文 `body_text`
- 摘要 `summary_text`
- 备注 `user_note`
- 关键词 `keywords`
- 事件 `events.content`
- 灵感 `inspirations.content`
- 地点 `locations.name`
- 消费描述和分类 `expenses.description / expenses.category`

## 6. 常见问题

### 1. 打开页面后跳回登录页

说明本地没有 token，先去正式登录页或联调台登录。

正式登录：

```text
/frontend/login.html
```

联调登录：

```text
/frontend/test-console.html
```

### 2. 结束今日记录后没有日记

先查：

```http
GET /api/v1/daily-records/today
```

如果 `is_generating=true`，继续等待。

如果长时间不结束，检查：

- AI TokenHub 配置是否正确。
- 后端日志是否有 AI 调用失败。
- 数据库表是否完整。

### 3. 今日页或回忆页 500

优先检查生产数据库结构：

- 是否存在 `record_inspirations`
- 是否仍停留在旧表 `record_tags`
- `daily_records.body_text` 是否已迁移
- 图片相关表是否存在

### 4. 注册失败

检查：

- 手机号是否已经注册。
- 密码是否至少 8 位。
- 手机号格式是否只包含数字、空格、短横线或 `+`。

### 5. 图片本地可以，线上不行

Vercel 这类 serverless 环境没有长期持久文件系统。线上图片要接对象存储，或确认部署环境有持久化上传目录。

## 7. 推荐使用方式

给真实用户或演示时，只打开：

```text
/frontend/login.html
```

自己开发、排错、演示接口时，打开：

```text
/frontend/debug.html
```

需要看原始接口响应时，打开：

```text
/frontend/test-console.html
```

一句话区分：

> `login.html` 是产品，`debug.html` 是开发入口，`test-console.html` 是接口工具。
