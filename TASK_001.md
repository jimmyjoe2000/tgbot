# 任务：到期提醒系统开发

## 需求描述

开发客户到期提醒系统，包括：
1. 客户数据表（customers）
2. 催款话术模板表（reminder_templates）
3. 提醒日志表（reminder_logs）
4. 客户自助查询功能（/my 命令）
5. 定时扫描提醒脚本

## 数据库表结构

### 1. customers 表

```sql
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    server_ip TEXT,
    domain_name TEXT,
    expires_on TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    telegram_id TEXT,
    created_at TEXT,
    updated_at TEXT,
    note TEXT
)
```

### 2. reminder_templates 表

```sql
CREATE TABLE reminder_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    days_before INTEGER NOT NULL,
    template TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT
)
```

默认模板（4 条）：
- 7 天提醒
- 3 天提醒
- 1 天提醒
- 已到期通知（0 天）

### 3. reminder_logs 表

```sql
CREATE TABLE reminder_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    days_before INTEGER,
    sent_at TEXT,
    status TEXT,
    message TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
)
```

## 需要修改的文件

1. `app/db/models.py` - 添加 Customer 模型（包含 telegram_id 字段）
2. `app/bot/handlers.py` - 添加 /my 和 /help 命令
3. `app/services/customers.py` - 添加客户相关服务函数
4. 创建 `scripts/expiration_reminder.py` - 定时扫描提醒脚本

## 功能要求

### /my 命令
- 客户查询自己的服务信息
- 显示到期时间、剩余天数
- 显示服务器 IP、域名

### /help 命令
- 显示客户可用的命令列表

### 定时提醒
- 每天 9:00 自动扫描
- 提前 7/3/1/0 天发送提醒
- 使用预存的话术模板（不接入 AI）
- 记录提醒日志

## 测试数据

添加测试客户：
- 客户 A：7 天后到期
- 客户 B：3 天后到期
- 客户 C：1 天后到期
- 客户 D：今天到期

## 验收标准

1. ✅ 数据库表创建成功
2. ✅ /my 命令可以查询客户信息
3. ✅ /help 命令显示帮助
4. ✅ 定时脚本可以扫描到期客户
5. ✅ 生成催款话术（预存模板）
6. ✅ 记录提醒日志
