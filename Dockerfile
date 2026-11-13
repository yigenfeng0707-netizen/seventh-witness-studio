# 《第七位证人》创空间镜像：纯 Gradio 应用，无 torch / 大模型依赖
FROM python:3.10-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    no_proxy=127.0.0.1,localhost \
    NO_PROXY=127.0.0.1,localhost

COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt \
    || pip install --no-cache-dir -r requirements.txt

COPY app.py game_data.py llm_client.py npc_engine.py ./

EXPOSE 7860
ENTRYPOINT ["python", "app.py"]
