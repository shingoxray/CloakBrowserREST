FROM cloakhq/cloakbrowser

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

EXPOSE 3412

ENV BROWSER_HEADLESS=false
ENV MAX_SESSIONS=100
ENV SESSION_TTL_MINUTES=10

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3412"]
