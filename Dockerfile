FROM python

RUN apt-get update && apt-get -y install cron

ENV HESSO_USERNAME=your_username \
    HESSO_PASSWORD=your_password \
    TELEGRAM_API_KEY=telergam_api_key \
    TELEGRAM_CHAT_ID=telegram_chat_id

COPY . /app

WORKDIR /app

RUN cd /app && pip3 install -r requirements.txt

ENTRYPOINT [ "cron", "-f", "-c", "/app/crontab" ]