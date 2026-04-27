-- ============================================
-- ЗАПРОСЫ ДЛЯ FLASHCARD LMS
-- ============================================

-- 1. Получить все колоды пользователя
-- Используется в: DeckListView.get_queryset()
SELECT * FROM decks WHERE owner_id = ? ORDER BY created_at DESC;

-- 2. Получить публичные колоды с лайками
-- Используется в: PublicDeckListView.get_queryset()
SELECT d.*, COUNT(dl.id) AS likes_count
FROM decks d
LEFT JOIN deck_likes dl ON d.id = dl.deck_id
WHERE d.visibility = 'public'
GROUP BY d.id
ORDER BY likes_count DESC, d.created_at DESC;

-- 3. Получить карточки для повторения сегодня
-- Используется в: SRSEngine.get_due_cards()
SELECT f.*
FROM flashcards f
JOIN user_card_progress ucp ON f.id = ucp.flashcard_id
WHERE ucp.user_id = ?
  AND f.deck_id = ?
  AND f.is_active = 1
  AND ucp.next_review_at <= DATETIME('now')
ORDER BY ucp.next_review_at ASC;

-- 4. Обновить прогресс после ответа
-- Используется в: SRSEngine.process_review()
UPDATE user_card_progress
SET repetition_number = ?,
    easiness_factor = ?,
    inter_repetition_interval = ?,
    consecutive_correct = ?,
    total_attempts = total_attempts + 1,
    total_errors = total_errors + CASE WHEN ? < 4 THEN 1 ELSE 0 END,
    last_reviewed_at = DATETIME('now'),
    next_review_at = DATETIME('now', '+' || ? || ' days'),
    last_quality_response = ?
WHERE user_id = ? AND flashcard_id = ?;

-- 5. Получить статистику по колоде
-- Используется в: SRSEngine.get_statistics()
SELECT 
    COUNT(DISTINCT f.id) AS total_cards,
    COUNT(DISTINCT CASE WHEN ucp.next_review_at <= DATETIME('now') THEN f.id END) AS due_today,
    COUNT(DISTINCT CASE WHEN ucp.easiness_factor >= 2.0 AND ucp.consecutive_correct >= 1 THEN f.id END) AS mastered,
    COUNT(DISTINCT CASE WHEN ucp.easiness_factor < 1.7 OR ucp.consecutive_correct = 0 THEN f.id END) AS struggling
FROM flashcards f
LEFT JOIN user_card_progress ucp ON f.id = ucp.flashcard_id AND ucp.user_id = ?
WHERE f.deck_id = ? AND f.is_active = 1;

-- 6. Копировать колоду со всеми карточками
-- Используется в: CopyDeckView
INSERT INTO decks (name, description, owner_id, target_language, native_language, visibility)
SELECT 'Копия: ' || name, description, ?, target_language, native_language, 'private'
FROM decks WHERE id = ?;

INSERT INTO flashcards (deck_id, term, definition, part_of_speech, example_sentence, base_difficulty, is_active)
SELECT last_insert_rowid(), term, definition, part_of_speech, example_sentence, base_difficulty, 1
FROM flashcards WHERE deck_id = ? AND is_active = 1;

-- 7. Поставить/убрать лайк
-- Используется в: ToggleLikeView
-- Проверка:
SELECT id FROM deck_likes WHERE deck_id = ? AND user_id = ?;
-- Если есть — удалить:
DELETE FROM deck_likes WHERE deck_id = ? AND user_id = ?;
-- Если нет — добавить:
INSERT INTO deck_likes (deck_id, user_id) VALUES (?, ?);

-- 8. Получить неповторяющиеся термины при генерации
-- Используется в: FlashcardBulkCreateView
SELECT term FROM flashcards WHERE deck_id = ? AND is_active = 1;

-- 9. Прогресс пользователя за 7 дней
-- Используется в: ProfileView
SELECT DATE(last_reviewed_at) AS review_date, COUNT(*) AS count
FROM user_card_progress
WHERE user_id = ? AND last_reviewed_at >= DATE('now', '-7 days')
GROUP BY review_date
ORDER BY review_date;

-- 10. Топ популярных колод
-- Используется в: AdminDashboardView
SELECT d.*, 
       COUNT(DISTINCT ucp.id) AS study_count, 
       COUNT(DISTINCT dl.id) AS likes_count
FROM decks d
LEFT JOIN user_card_progress ucp ON d.id = ucp.flashcard_id
LEFT JOIN deck_likes dl ON d.id = dl.deck_id
GROUP BY d.id
ORDER BY study_count DESC
LIMIT 10;