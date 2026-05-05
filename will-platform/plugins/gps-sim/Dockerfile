FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY plugin.py .

USER nobody

CMD ["python", "-u", "plugin.py"]
