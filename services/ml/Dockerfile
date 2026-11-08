FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY scripts ./scripts
COPY data ./data
# The scam classifier is trained at build from the committed synthetic set (a few seconds), outside the models
# volume so a rebuild always ships the model that matches the code.
RUN python -W ignore scripts/train_classifier.py
RUN mkdir -p /app/models
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
