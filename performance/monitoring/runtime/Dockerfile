FROM python:3.12-slim
WORKDIR /runtime
RUN pip install --no-cache-dir prometheus-client==0.21.1 PyMySQL==1.1.1 cryptography==45.0.6
COPY receiver.py evidence.py order_snapshot.py ./
USER 65534:65534
CMD ["python", "receiver.py"]
