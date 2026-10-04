# Резервный канал звонков на одном сервере

Подготовлена **необязательная** конфигурация TURN/TLS. Добавление этих файлов само по себе ничего на сервере не включает. Активировать её нужно отдельно, после DNS, сертификата, резервной копии и проверок ниже, в окно без занятий. Миграции и замена базы не нужны.

Браузер сохраняет прямые соединения `7882/udp` и `7881/tcp`. LiveKit дополнительно выдаёт ему короткоживущие авторизованные TURN-учётные данные и адрес `turns:turn.coursemc.ru:443?transport=tcp`. ICE выбирает доступный путь; принудительный режим `relay` для всех пользователей не включается. Это помогает сетям, где закрыты UDP и нестандартные TCP-порты, но не гарантирует обход любого VPN: некоторые сети блокируют сам TURN, SNI или весь WebRTC.

## Устройство

- `compose.yaml` + `compose.media.yaml` — существующий сайт и LiveKit, без изменений.
- `compose.turn.yaml` — дополнительный маленький Nginx-маршрутизатор `media-edge`. Только он занимает публичный TCP/443.
- По SNI обычный HTTPS передаётся существующему Nginx **без расшифровки**. Для TURN TLS завершается на edge с отдельным доверенным сертификатом; далее трафик идёт к встроенному TURN LiveKit по выделенной сети Docker.
- Исходный IP передаётся через PROXY protocol. Сайт и TURN доверяют только фиксированному адресу edge `172.30.249.2`; его внутренний слушатель не публикуется наружу. Не добавляйте в доверенные сети `0.0.0.0/0`.
- Внутренняя сеть: `172.30.249.0/29`. До запуска проверяется отсутствие пересечений с существующими сетями Docker.
- Relay-порты: `40000–40199/udp`, одинаковые внутри и снаружи контейнера. Это участок **серверной** передачи; от клиента до TURN используется защищённый TCP/443. Нельзя произвольно изменить одну сторону диапазона.
- Секрет LiveKit остаётся только на сервере. Анонимные TURN allocation запрещены, доступ к private/loopback peers не разрешается. Квота — 12 allocation на участника. Продолжительные звонки используют refresh; срок выдаваемых учётных данных не ограничивает сам урок пятью минутами.
- Certbot обновляет оба сертификата через HTTP/80. Edge мягко перечитывает сертификаты раз в шесть часов: перезапуск LiveKit для продления не требуется. При отдельном ручном обновлении: `docker compose exec -T media-edge nginx -t` и затем `docker compose exec -T media-edge nginx -s reload`.

Основа: [развёртывание LiveKit и TURN/TLS](https://docs.livekit.io/transport/self-hosting/deployment/), [Nginx ssl_preread](https://nginx.org/en/docs/stream/ngx_stream_ssl_preread_module.html). Для замены host-портов используется `!override`, поэтому необходим [Docker Compose ≥ 2.24.4](https://docs.docker.com/reference/compose-file/merge/#replace-value).

## 1. DNS в REG.RU

Сервер сайта — `201.51.5.223`, но DNS меняется там, где обслуживается домен:

1. REG.RU → «Мои домены» → `coursemc.ru` → «DNS-серверы и зона».
2. Если используется DNS REG.RU (`ns1.reg.ru`/`ns2.reg.ru`), откройте управление зоной. Если там указаны DNS **хостинга** (`*.hosting.reg.ru`), зона редактируется в панели соответствующего хостинга, например ispmanager → «Управление DNS» → `coursemc.ru` → «DNS-записи».
3. Добавьте **A**: имя `turn` (в панели, требующей полное имя, `turn.coursemc.ru.`), значение `201.51.5.223`. TTL можно оставить стандартным.
4. Основные записи домена, MX и DNS-серверы не менять. Для TURN не создавать AAAA, если IPv6 сервера отдельно не настроен. DNS-проксирование/CDN для TURN не включать.

Проверить после распространения:

```bash
dig +short A turn.coursemc.ru
dig +short AAAA turn.coursemc.ru
```

Первая команда должна вернуть только `201.51.5.223`, вторая — пустой ответ. [Инструкция REG.RU для DNS хостинга](https://help.reg.ru/support/dns-servery-i-nastroyka-zony/nastroyka-resursnykh-zapisey/nastroyka-resursnykh-zapisey-na-khostinge).

Если выбран DNS хостинга, но самого хостинга в аккаунте нет, **не менять NS вслепую**. REG.RU предоставляет бесплатные `ns1.reg.ru`/`ns2.reg.ru` для зарегистрированных у него доменов, однако переход требует переноса зоны. Сначала получить полный список/экспорт старых записей (при недоступной панели — через поддержку REG.RU), подготовить новую зону и проверить её до смены делегирования. Публичные запросы A/MX/TXT не гарантируют полный список поддоменов, DKIM и записей проверки сервисов. Покупать новый хостинг для DNS не нужно. У `coursemc.ru` на момент проверки присутствуют также MX и SPF старого хостинга: уточнить у владельца, используются ли они, а не удалять автоматически. [Бесплатные DNS REG.RU](https://help.reg.ru/support/dns-servery-i-nastroyka-zony/rabota-s-dns-serverami/kak-privyazat-domen-k-ip-adresu).

## 2. Подготовка на сервере

Сначала новые файлы должны быть доставлены в `/opt/coursemc` как проверенная версия кода. Ниже команды выполняются **на сервере**, не на ноутбуке. Не выполнять `down`, не удалять тома, не подменять SQLite из Git.

```bash
cd /opt/coursemc
docker compose version
docker compose -f compose.yaml -f compose.media.yaml ps
df -h /opt/coursemc
```

Далее отдельная защищённая копия конфигурации и базы. В том же терминале:

```bash
set -euo pipefail
umask 077
mkdir -p /opt/coursemc/data/backups
turn_backup_dir=$(mktemp -d /opt/coursemc/data/backups/turn-XXXXXXXX)
cp .env compose.yaml compose.media.yaml compose.turn.yaml "$turn_backup_dir/"
git rev-parse HEAD > "$turn_backup_dir/code-ref.txt"
tar -czf "$turn_backup_dir/runtime-and-certificates.tar.gz" runtime data/certbot/conf
docker compose -f compose.yaml -f compose.media.yaml exec -T web python -c '
import os, sqlite3
assert not os.path.exists("/backups/turn-db.sqlite3"), "Choose a new backup filename first"
with sqlite3.connect("/data/db.sqlite3") as source, sqlite3.connect("/backups/turn-db.sqlite3") as target:
    source.backup(target)
    result = target.execute("PRAGMA integrity_check").fetchone()[0]
    assert result == "ok", result
    print("SQLite backup integrity: ok")
'
mv data/backups/turn-db.sqlite3 "$turn_backup_dir/db.sqlite3"
docker image save nginx:1.28-alpine livekit/livekit-server:v1.13.7 | gzip > "$turn_backup_dir/media-images.tar.gz"
gzip -t "$turn_backup_dir/media-images.tar.gz"
tar -tzf "$turn_backup_dir/runtime-and-certificates.tar.gz" >/dev/null
printf 'Копия: %s\n' "$turn_backup_dir"
```

Блок рассчитан на Bash. При ошибке любого шага остановиться. `turn-db.sqlite3` — промежуточное имя: если такой файл уже существует, не перезаписывать, выбрать другое. Для сохранения образов нужна свободная память на диске; не очищать чужие контейнеры/тома ради копии. Путь копии сохранить. Если серверное имя базы отличается, сначала уточнить `COURSEMC_DB_PATH` и заменить **только источник** этой копии.

В `.env` добавить одну публичную настройку, не изменяя секретов:

```dotenv
LIVEKIT_TURN_DOMAIN=turn.coursemc.ru
```

Пока **не** добавлять `COMPOSE_FILE`. Сформировать отдельные конфиги; исходная папка `runtime/nginx` остаётся основой отката:

```bash
python3 deploy/render_turn.py
docker compose -f compose.yaml -f compose.media.yaml -f compose.turn.yaml config --quiet
```

Без `--quiet` Compose выводит секреты, поэтому такой вывод не присылать в чат.

## 3. Сертификат TURN без переключения портов

Подготовленный HTTP-блок нужен для выпуска и автоматического продления сертификата. Сайт продолжает обслуживаться старым Nginx:

```bash
cp runtime/turn/acme.conf runtime/nginx/turn-acme.conf
docker compose -f compose.yaml -f compose.media.yaml exec -T nginx nginx -t
docker compose -f compose.yaml -f compose.media.yaml exec -T nginx nginx -s reload
docker compose -f compose.yaml -f compose.media.yaml run --rm --entrypoint certbot certbot certonly --webroot --webroot-path=/var/www/certbot --non-interactive --cert-name turn.coursemc.ru -d turn.coursemc.ru
```

Используется существующий аккаунт Certbot. Если он отсутствует или Certbot просит принять новые условия, остановиться: согласие на условия владелец подтверждает отдельно. Не добавлять `--agree-tos` автоматически, не использовать самоподписанный сертификат в production, не обходить проверку TLS.

## 4. Проверка и переключение

В firewall Timeweb/сервера сохранить `80/tcp`, `443/tcp`, `7881/tcp`, `7882/udp`; дополнительно разрешить `40000–40199/udp` к этому серверу. Публичные `7880/tcp`, внутренние TURN `443` контейнера и `8443` edge **не открывать** отдельно.

```bash
python3 deploy/turn_preflight.py --public-ip 201.51.5.223
docker compose -f compose.yaml -f compose.media.yaml -f compose.turn.yaml run --rm --no-deps nginx nginx -t
docker compose -f compose.yaml -f compose.media.yaml -f compose.turn.yaml run --rm --no-deps media-edge nginx -t
```

Проверка блокирует переключение при активных участниках, плохом DNS/сертификате, занятом relay-диапазоне, старом Compose или пересекающейся сети. Проверки контейнеров создают и удаляют только временные контейнеры, текущие сервисы не останавливают. Если любой шаг не прошёл — дальше не идти. Переключение пересоздаёт LiveKit: ещё раз убедиться, что никто не вошёл после проверки. Между снятием старого 443 и запуском edge возможна краткая пауза сайта.

```bash
python3 deploy/turn_preflight.py --public-ip 201.51.5.223
docker compose -f compose.yaml -f compose.media.yaml -f compose.turn.yaml up -d --no-deps livekit nginx
docker compose -f compose.yaml -f compose.media.yaml -f compose.turn.yaml up -d --no-deps media-edge
docker compose -f compose.yaml -f compose.media.yaml -f compose.turn.yaml --profile https up -d --no-deps certbot
docker compose -f compose.yaml -f compose.media.yaml -f compose.turn.yaml ps
curl --fail --silent --show-error https://coursemc.ru/ready/
python3 deploy/check_turn.py
```

Если запуск, HTTPS, авторизация или relay не прошли — откат ниже. Не объявлять TURN готовым по одному `200` от сайта или успешному TLS handshake.

После успешной проверки добавить в `.env`:

```dotenv
COMPOSE_FILE=compose.yaml:compose.media.yaml:compose.turn.yaml
```

Теперь `docker compose ps/up/logs` без `-f` выбирают полный стек. При явных `-f` **всегда** указывать все три файла. Не запускать `render_nginx.sh https`/`enable_https.sh` для обновления активного TURN-конфига: используется `python3 deploy/render_turn.py` и проверки/reload **обоих** Nginx. Сайт, планировщик и база остаются существующими.

## 5. Приёмка звонка

`check_turn.py` проверяет сертификат, отказ неавторизованному клиенту, две временные авторизованные allocation, запрет loopback peers и передачу случайных данных через relay в обе стороны. Учётные данные не выводятся; allocation освобождаются, а при обрыве истекают максимум через 60 секунд. Реальные уроки и Django-база не затрагиваются. Диагностика рассчитана на встроенный TURN **LiveKit v1.13.7**; при смене версии проверить совместимость.

Следом нужен реальный браузерный звонок: преподаватель на обычной сети, ученик на iPhone/мобильной сети с проблемным VPN. Проверить вход, звук в обе стороны, демонстрацию 720p/1080p, повторный вход, затем тот же сценарий без VPN. Для доказательства fallback на диагностическом стенде временно ограничить клиент только relay и убедиться в выбранном ICE candidate `relay` + `tcp`; в основной интерфейс такой принудительный режим не сохранять. Не блокировать порты production ради теста. Записать браузер/ОС/VPN и фактический тип соединения. Проверка с самого сервера не подтверждает проходимость пользовательского VPN.

## Откат без восстановления рабочей базы

Если переключение не прошло, порт 443 сначала освобождается от edge, затем возвращается старому Nginx. `stop` сохраняет контейнер, тома и сертификаты; не использовать `down -v`:

```bash
docker compose -f compose.yaml -f compose.media.yaml -f compose.turn.yaml stop media-edge
docker compose -f compose.yaml -f compose.media.yaml up -d --no-deps livekit nginx
docker compose -f compose.yaml -f compose.media.yaml exec -T nginx nginx -t
curl --fail --silent --show-error https://coursemc.ru/ready/
```

Если уже задан `COMPOSE_FILE`, убрать только эту строку из `.env` (либо вернуть сохранённую конфигурацию после проверки, что с тех пор не менялись другие настройки). Исходный `runtime/nginx/default.conf` не перезаписывался. Базу и материалы из копии **не восстанавливать** для сетевого отката: это потеряет новые данные и здесь не требуется. DNS TURN/сертификат можно оставить; резервный канал отключён, прямые звонки работают как раньше. При отдельном изменении firewall закрыть только добавленный диапазон, не трогая сайт/SSH/прямые медиа-порты.

## Локальные проверки кода

```bash
python3 -m unittest discover -s deploy/tests -v
LIVEKIT_API_KEY=test LIVEKIT_API_SECRET=only-test-not-a-production-secret-32-chars LIVEKIT_TURN_DOMAIN=turn.coursemc.ru docker compose --env-file .env.example -f compose.yaml -f compose.media.yaml -f compose.turn.yaml config --quiet
```

Эти проверки не запускают production-сервисы, не меняют базу и не заменяют TLS/relay-тест после развёртывания. Для локального звонка остаётся прежний `scripts/run_live_lessons_local.sh`: публичный TURN и сертификаты там не нужны.
