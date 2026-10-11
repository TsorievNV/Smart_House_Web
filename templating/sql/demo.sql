-- Скриншот 11: карточка остаётся в БД после DELETE.
SELECT id, title, status, creator_id, created_at, formed_at, completed_at,
       image_key, video_key, traffic_mean, traffic_variance
FROM smart_devices ORDER BY id DESC;

-- Скриншот 12: лайк сохраняется после soft delete карточки.
SELECT l.id, l.user_id, u.username, l.device_id, d.title, d.status
FROM likes l JOIN users u ON u.id = l.user_id
JOIN smart_devices d ON d.id = l.device_id ORDER BY l.id DESC;

-- Скриншот 13: регистрация (пароль и хеш не показываются).
SELECT id, username, created_at, password_hash IS NOT NULL AS has_password
FROM users ORDER BY id DESC;
