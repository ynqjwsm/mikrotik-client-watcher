# 1. 选择基础镜像（匹配项目的Python版本，slim版体积较小）
FROM python:3.14-slim

# 2. 设置工作目录（后续命令都在该目录执行）
WORKDIR /app

# 3. 安装uv（官方推荐的一键安装脚本）
RUN apt-get update && apt-get install -y curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*  # 清理缓存，减少镜像体积

# 4. 将uv加入系统PATH（关键：确保能全局调用uv命令）
ENV PATH="/root/.local/bin:$PATH"

# 5. 复制依赖配置文件（优先复制，利用Docker缓存：依赖不变时，无需重新安装）
COPY pyproject.toml uv.lock* ./

# 6. 安装项目依赖（--system：安装到系统Python环境，容器中无需虚拟环境）
RUN uv pip install --system .

# 7. 复制项目源码（依赖安装后再复制源码，源码变更不触发依赖重装）
COPY . .

# 设置环境变量
# 数据目录（存储日志和config.json）
ENV DATA_DIR=/data
# Web服务监听地址
ENV WEB_HOST=0.0.0.0
# Web服务监听端口
ENV WEB_PORT=8000
# 登录密钥（请修改为强密码）
ENV LOGIN_KEY=admin123
# 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
ENV LOG_LEVEL=INFO

# 创建数据目录
RUN mkdir -p /data

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "main.py"]
