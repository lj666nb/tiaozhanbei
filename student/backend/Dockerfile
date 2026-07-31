FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制源码
COPY . .

# Fail the image build if resource configuration points at an SVG that was
# not committed. This prevents a successful deploy with silent placeholders.
RUN python scripts/validate_resource_images.py

# 创建数据目录
RUN mkdir -p /app/data

# 暴露端口
EXPOSE 8000

# 启动服务（生产模式，无热重载）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
