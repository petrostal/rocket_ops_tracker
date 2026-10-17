# OpsTracker

Внутренний трекер операционных задач для Rocket.Chat: FastAPI, React, PostgreSQL и private Apps Engine app. Rocket.Chat не требует патчей или пересборки.

Лицензия: [MIT](LICENSE).

## Возможности

- Kanban со стадиями `TODO`, `IN_PROGRESS`, `WAITING`, `REVIEW`, `DONE`.
- Мои задачи, общий список, поиск, теги и сохраняемые фильтры.
- Комментарии, история, вложения и предпросмотр изображений.
- Создание задачи из сообщения, room/message actions и `/task`.
- OAuth-вход через Rocket.Chat; app-кнопка переводит пользователя в обычный OAuth flow.
- Настраиваемая видимость задач и полный доступ для подтверждённых администраторов.
- Кнопка «Завершить» отправляет работу на проверку; перевод в `DONE` разрешается отдельным правом в настройках доступа.
- Уведомления создателю и исполнителю только в личные сообщения.

Архитектура и границы доверия описаны в [docs/architecture.md](docs/architecture.md) и [docs/security.md](docs/security.md).

## Требования

- Docker Engine и Docker Compose v2.
- Два HTTPS origin: Rocket.Chat и OpsTracker.
- Rocket.Chat с разрешёнными private apps и OAuth applications.
- Traefik с внешней Docker-сетью либо отдельный Nginx.

Все адреса, имена сетей и параметры TLS задаются окружением. В репозитории используются только зарезервированные домены `example.com`.

## Конфигурация

```bash
cp .env.example .env
chmod 600 .env
openssl rand -base64 48
openssl rand -base64 48
openssl rand -base64 36
```

Запишите три независимых результата соответственно в `APP_SECRET`, `ROCKETCHAT_APP_SECRET` и `POSTGRES_PASSWORD`. Затем заполните:

| Переменная | Назначение |
|---|---|
| `PUBLIC_URL` | HTTPS origin OpsTracker без path |
| `ROCKETCHAT_URL` | HTTPS origin Rocket.Chat без path |
| `ROCKETCHAT_CLIENT_ID`, `ROCKETCHAT_CLIENT_SECRET` | OAuth application |
| `ROCKETCHAT_BOT_USER_ID`, `ROCKETCHAT_BOT_TOKEN` | server-side REST credentials для личных уведомлений |
| `ALLOWED_ORIGINS` | явный список browser origins |
| `ALLOWED_FRAME_ORIGIN` | единственный origin, которому разрешено встраивание UI |
| `TASK_ADMIN_USERNAMES` | необязательный allowlist; предпочтительнее роли `admin`/`owner`, подтверждённые OAuth |
| `TASKS_DOMAIN` | hostname для Traefik router |
| `TRAEFIK_NETWORK` | имя существующей внешней proxy-сети |
| `TRAEFIK_ENTRYPOINT`, `TRAEFIK_CERTRESOLVER` | локальные имена Traefik |
| `CSP_EXTERNAL_IMAGE_SOURCES` | необязательные внешние image origins для предпросмотра |
| `ATTACHMENT_MAX_PER_TASK`, `ATTACHMENT_TOTAL_MAX_BYTES_PER_TASK`, `ATTACHMENT_TOTAL_MAX_BYTES_PER_USER` | квоты вложений |
| `COMMENT_MAX_PER_TASK` | максимальное число комментариев в задаче |

`APP_ENV=production` включает fail-closed проверки: опубликованные placeholder-значения, слабые секреты, SQLite, HTTP origins и URL с credentials/path/query отклоняются.

## Rocket.Chat

1. Создайте OAuth application с callback `${PUBLIC_URL}/api/auth/callback`.
2. Создайте отдельного service account с минимальными REST permissions и Personal Access Token.
3. Соберите private app:

   ```bash
   cd rocketchat/app
   npm ci
   npm run package
   ```

4. Загрузите созданный ZIP из `rocketchat/app/dist/` и задайте в настройках приложения:
   - `Backend URL` — значение `PUBLIC_URL`;
   - `Integration secret` — значение `ROCKETCHAT_APP_SECRET`.

`Backend URL` должен использовать HTTPS; HTTP разрешён только для loopback-разработки. `dist/` является генерируемым каталогом и не публикуется в Git.

## Запуск с Traefik

После заполнения `.env`:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
curl -fsS "${PUBLIC_URL}/api/health"
```

PostgreSQL и worker находятся во внутренней сети. Frontend подключается к указанной `TRAEFIK_NETWORK` и дополнительно слушает только `TASKS_BIND_ADDRESS:TASKS_HTTP_PORT`.

## Nginx вместо Traefik

Сгенерируйте site-файл из [nginx/opstracker.conf.template](nginx/opstracker.conf.template):

```bash
export TASKS_DOMAIN=tasks.example.com
export OPSTRACKER_UPSTREAM=127.0.0.1:8088
export TLS_CERTIFICATE_PATH=/path/to/fullchain.pem
export TLS_CERTIFICATE_KEY_PATH=/path/to/privkey.pem
export ALLOWED_FRAME_ORIGIN=https://chat.example.com
export CSP_EXTERNAL_IMAGE_SOURCES=https://i.gyazo.com
envsubst '${TASKS_DOMAIN} ${OPSTRACKER_UPSTREAM} ${TLS_CERTIFICATE_PATH} ${TLS_CERTIFICATE_KEY_PATH} ${ALLOWED_FRAME_ORIGIN} ${CSP_EXTERNAL_IMAGE_SOURCES}' \
  < nginx/opstracker.conf.template > /tmp/opstracker.conf
sudo cp /tmp/opstracker.conf /etc/nginx/sites-available/opstracker.conf
sudo nginx -t
```

Установите проверенный файл по правилам вашей системы; шаблон не содержит hostname, certificate path или proxy topology конкретного сервера.

## Тесты и сборка

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
PYTHONPATH=backend .venv/bin/pytest -q backend/tests

cd frontend && npm ci && npm run build
cd ../rocketchat/app && npm ci && npm run package
```

Перед публикацией запустите:

```bash
scripts/check-public-release.sh
PUBLIC_RELEASE_DENY_PATTERN='private-domain|private-user|private-host' scripts/check-public-release.sh
```

Подробный checklist: [docs/public-release.md](docs/public-release.md).

## Backup

```bash
docker compose exec -T tasks-postgres pg_dump \
  -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc > opstracker-$(date +%F).dump
```

Файлы `.env`, ключи, дампы, локальные базы, логи, вложения и build artifacts исключены через `.gitignore`.
