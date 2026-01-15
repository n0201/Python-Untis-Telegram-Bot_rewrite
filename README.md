# Python-Untis-Telegram-Bot_rewrite

## Features
### 1. Keep track of cancelled lessons using Untis
- This feature can be disabled, look at Setup for instructions

### 2. Add/remove/show exams (+ reminders!)
- The bot that automatically gets started once the docker image runs (or the main.py in general) will send you reminders for the added exams
- this feature saves all currently saved exams in a file to make exams (and the reminder jobs) persist crashes or reboots!

### 3. One instance per user
- to ensure full user safety and privacy, this bot only allows ONE user to use it per instance. The owner of the bot instance should provide his Telegram token (and Untis login if enabled)

## Setup
The bot loads all info that has to be provided from the environment. This is why it is highly recommended to use the bot with its docker image.

If using Untis, you'll need to get the school's name and its untis domain. you can do so by heading to the untis search side, seach and click on your school and looking for the domain (e.g. `yourschool.untis.com`) and the school name (eg. `?school=ThisIsTheSchoolName`)

If you don't want to use Untis functionality, leave all the untis vars blank except for UNTIS_BOT_TOKEN. This is your telegram bot token!

<details>
<summary>Standalone</summary>

  First install required pip packages: `pip install -r requirements.txt`
  
  ### Then run the bot
  with untis enabled: `UNTIS_BOT_TOKEN=<your telegram bot token> TELEGRAM_USER_ID=<your telegram id> UNTIS_ENABLED=true UNTIS_USER=<your Untis username> UNTIS_PASSWORD=<your Untis password> UNTIS_SCHOOL=<your school name> UNTIS_SERVER=<the domain of the untis page> UNTIS_VERTRAETUNGSTEXT=<the subsitude text getting used if a lesson gets cancelled> python3 main.py`

  with untis disabled: `UNTIS_BOT_TOKEN=<your telegram bot token> TELEGRAM_USER_ID=<your telegram id> python3 main.py`
</details>

<details>
<summary>With Docker</summary>
    Set all the env vars in docker-compose.yml (you can skip all the untis vars except for the UNTIS_BOT_TOKEN) in [docker-compose.yml](docker-compose.yml).

    Then run `docker compose up -d`.

  
    To view logs: `docker compose up logs`
  
    To rebuild: `docker compose up --force-recreate --build -d`
  
</details>


## Download
[DOWNLOAD](https://github.com/n0201/python-untis-telegram-bot_rewrite/releases/latest)

## INFO
I'm a pupil from Germany doing this project for a skilled workpaper. Please don't judge me too hard, but I'll try to keep this bot updated and match all of your feature requests. Enjoy the bot and make sure to star this repo if you like it!


