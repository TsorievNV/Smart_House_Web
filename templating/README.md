устройства. `status` устройства не передаётся в JSON. Поля с отсутствующим значением остаются в ответе как `null`; пустая строка остаётся строкой. Если записи нет, возвращается пустой 404. Пустой список возвращается как `[]` с кодом 200.

## Таблицы и все поля

### `users` — модель User

| Поле | Тип | Назначение |
|---|---|---|
| id | integer PK | Серверный идентификатор |
| username | varchar(100), NOT NULL, UNIQUE | Имя пользователя |
| password_hash | varchar(256), NULL допустим | scrypt-хеш; у старых демо-пользователей может отсутствовать |
| created_at | timestamp, NOT NULL | Дата создания UTC, назначается сервером |

### `smart_devices` — модель SmartDevice

| Поле | Тип | Назначение |
|---|---|---|
| id | integer PK | Серверный ID |
| title | varchar(255), NOT NULL | Название |
| type_label | varchar(100), NOT NULL | Тип устройства |
| model | varchar(100), NULL | Модель устройства |
| description | text, NULL | Описание; API новых записей требует заполнение |
| status | varchar(20), NOT NULL | draft / published / deleted; CHECK |
| image_key | varchar(500), NULL | Имя объекта изображения в MinIO |
| video_key | varchar(500), NULL | Имя объекта видео в MinIO |
| traffic_mean | double precision, NULL | E(X), >= 0; API требует значение |
| traffic_variance | double precision, NULL | D(X), >= 0; API требует значение |
| created_at | timestamp, NOT NULL | Создание, UTC |
| formed_at | timestamp, NULL | Публикация, UTC |
| completed_at | timestamp, NULL | Логическое удаление, UTC |
| creator_id | integer FK users.id, NOT NULL | Автор |

Индекс `uq_device_creator_draft`: UNIQUE (`creator_id`) WHERE `status = 'draft'`. CHECK `ck_device_status` ограничивает значения статуса, `ck_device_traffic` — неотрицательные значения трафика. Разрешённые переходы между статусами контролирует API.

### `likes` — модель Like

| Поле | Тип | Назначение |
|---|---|---|
| id | integer PK | ID лайка |
| user_id | integer FK users.id, NOT NULL | Пользователь |
| device_id | integer FK smart_devices.id, NOT NULL | Устройство |

UNIQUE (`user_id`, `device_id`). Связи без каскадного удаления. Отмена лайка удаляет строку связи; устройства удаляются исключительно логически.

Связи: `users` 1 → 0..* `smart_devices` (авторство), `users` 1 → 0..* `likes`, `smart_devices` 1 → 0..* `likes`. Таблица `likes` связывает пользователей и понравившиеся устройства отношением многие ко многим.

### `alembic_version` — служебная таблица

| Поле | Тип | Назначение |
|---|---|---|
| version_num | varchar(32), PK | Текущая ревизия структуры БД |
