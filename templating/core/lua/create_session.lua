-- KEYS[1]: новая сессия; KEYS[2]: предыдущая сессия (необязательно).
-- ARGV: user_id, username, TTL в секундах.
-- Все проверки выполняются до записи: ошибка не должна отзывать старую сессию.
local ttl = tonumber(ARGV[3])
if not ttl or ttl < 1 or ttl > 2147483647 or ttl ~= math.floor(ttl) then
    return redis.error_reply('Invalid session TTL')
end

-- Не перезаписываем существующую сессию при совпадении случайных ключей.
if redis.call('EXISTS', KEYS[1]) == 1 then
    return 0
end

redis.call('HSET', KEYS[1], 'user_id', ARGV[1], 'username', ARGV[2])
redis.call('EXPIRE', KEYS[1], ttl)
if KEYS[2] then
    redis.call('DEL', KEYS[2])
end
return 1
