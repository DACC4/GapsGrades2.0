FROM python:3.9-alpine

WORKDIR /app

ENV HESSO_USERNAME=your_username \
    HESSO_PASSWORD=your_password \
    TELEGRAM_API_KEY=telergam_api_key \
    TELEGRAM_CHAT_ID=telegram_chat_id

COPY . /app
COPY crontab /var/spool/cron/crontabs/

RUN cd /app && pip3 install -r requirements.txt

# Executing crontab command
CMD ["crond", "-f"]