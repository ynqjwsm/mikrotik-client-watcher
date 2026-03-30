# MikroTik Client Watcher

一个用于监控 MikroTik RouterOS DHCP 客户端在线状态的工具，支持通过飞书机器人推送状态变更通知。

## 功能特性

### 核心功能
- **多路由器管理**：支持监控多台 MikroTik RouterOS 设备
- **客户端监控**：通过 IP 地址、MAC 地址、主机名或组合条件监控指定客户端
- **灵活的推送规则**：
  - 客户端上线推送
  - 客户端下线推送
  - 存活推送（可配置间隔）
- **消息模板**：支持自定义消息模板，可使用占位符
- **实时状态展示**：Web 界面展示所有监控客户端的实时状态
- **手动刷新**：可手动触发状态刷新和消息推送
- **启用/禁用控制**：可单独启用/禁用路由器或客户端的监控

### 技术特性
- **FastAPI 后端**：高性能异步 Web 服务
- **Bootstrap 5 前端**：美观的响应式界面
- **配置持久化**：配置保存在 JSON 文件中
- **完整的日志**：支持多种日志级别，日志文件滚动保存
- **Docker 支持**：提供 Dockerfile，支持容器化部署

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DATA_DIR` | 数据目录（存储日志和配置） | `.` |
| `WEB_HOST` | Web 服务监听地址 | `0.0.0.0` |
| `WEB_PORT` | Web 服务监听端口 | `8000` |
| `LOGIN_KEY` | 登录密钥 | `admin123` |
| `LOG_LEVEL` | 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL） | `INFO` |

## 快速开始

### 环境要求
- Python 3.10+
- uv（用于依赖管理）

### 本地运行

1. 克隆项目
```bash
git clone <repository-url>
cd mikrotik-client-watcher
```

2. 安装依赖
```bash
uv pip install --system .
```

3. 配置环境变量（可选）
```bash
cp .env.example .env
# 编辑 .env 文件，修改配置
```

4. 启动服务
```bash
python main.py
```

5. 访问 Web 界面
打开浏览器访问 `http://your-server-ip:8000`

### Docker 部署

#### 方式一：使用 docker compose（推荐）

1. 创建环境变量文件（可选）
```yml
services:
  mikrotik-watcher:
    image: brantwang/mikrotik-client-watcher:v0.0.6
    container_name: mikrotik-watcher
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
    environment:
      - LOGIN_KEY=${LOGIN_KEY:-admin123}
      - WEB_HOST=0.0.0.0
      - WEB_PORT=8000
      - DATA_DIR=/data
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
```

#### 方式二：使用纯 Docker

```bash
docker run -d \
  --name mikrotik-watcher \
  -p 8000:8000 \
  -v ./data:/data \
  -e LOGIN_KEY=your-secret-key \
  --restart unless-stopped \
  brantwang/mikrotik-client-watcher:v0.0.6
```

## 使用说明

### 1. 登录
使用配置的 `LOGIN_KEY` 登录系统。

### 2. 配置飞书 Webhook
在"飞书配置"选项卡中配置飞书机器人的 Webhook URL，可以发送测试消息验证配置。

### 3. 添加 ROS 路由器
在"ROS 路由器管理"选项卡中：
- 点击"添加 ROS 路由器"
- 填写路由器信息：名称、主机地址、端口、用户名、密码、轮询间隔
- 保存后可以启用/禁用路由器的监控

### 4. 添加客户端
在路由器卡片上点击"添加客户端"：
- 填写客户端名称
- 配置监控条件：IP 地址、MAC 地址、主机名（可单独或组合使用）
- 配置推送规则：上线推送、下线推送、存活推送（可设置间隔）
- 配置消息模板（可选，支持 Markdown 格式和占位符）
- 保存后可以启用/禁用客户端的监控

### 5. 查看状态
在"状态"选项卡中可以查看所有客户端的实时状态，包括：
- 在线状态
- IP 地址
- MAC 地址
- 主机名
- 最后在线时间

点击"刷新"按钮可以手动触发状态刷新和消息推送。

## 消息模板占位符

自定义消息模板时可以使用以下占位符：

| 占位符 | 说明 |
|--------|------|
| `{router_name}` | 路由器名称 |
| `{client_name}` | 客户端名称 |
| `{event_type}` | 事件类型（上线/下线/存活） |
| `{address}` | IP 地址 |
| `{mac_address}` | MAC 地址 |
| `{hostname}` | 主机名 |
| `{timestamp}` | 时间戳 |

## 项目结构

```
mikrotik-client-watcher/
├── .github/
│   └── workflows/
│       └── release.yml     # GitHub Actions 发布流程
├── html/
│   ├── static/             # 静态文件
│   └── templates/          # HTML 模板
├── config.py               # 配置管理
├── feishu_notifier.py      # 飞书通知模块
├── main.py                 # 主程序入口
├── mikrotik_client.py      # MikroTik API 客户端
├── models.py               # 数据模型
├── monitor.py              # 监控逻辑
├── scheduler.py            # 定时任务调度
├── Dockerfile              # Docker 镜像构建文件
├── docker-compose.yml      # Docker Compose 配置
├── pyproject.toml          # 项目配置
└── uv.lock                 # 依赖锁定文件
```

## 许可证

MIT License
