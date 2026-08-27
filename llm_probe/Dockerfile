FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./llm_probe

EXPOSE 8000
CMD ["uvicorn", "llm_probe.main:app", "--host", "0.0.0.0", "--port", "8000"]
