-- ============================================
-- ЗАПРОСЫ ДЛЯ КУРСОВОЙ РАБОТЫ
-- ============================================

-- 1. Количество пользователей
SELECT COUNT(*) FROM users;

-- 2. Количество публичных колод
SELECT COUNT(*) FROM decks WHERE visibility = 'public';

-- 3. Топ-5 популярных колод
SELECT d.name, COUNT(dl.id) as likes
FROM decks d
LEFT JOIN deck_likes dl ON d.id = dl.deck_id
GROUP BY d.id
ORDER BY likes DESC
LIMIT 5;

-- 4. Средний прогресс пользователей
SELECT u.username, 
       COUNT(ucp.id) as cards_studied,
       AVG(ucp.easiness_factor) as avg_ef
FROM users u
JOIN user_card_progress ucp ON u.id = ucp.user_id
GROUP BY u.id;

-- 5. Активность за последние 7 дней
SELECT DATE(created_at) as date, COUNT(*) as actions
FROM user_activities
WHERE created_at >= DATE('now', '-7 days')
GROUP BY date;