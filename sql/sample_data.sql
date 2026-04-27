-- Примеры данных для демонстрации
-- Пользователи
INSERT INTO users (username, email) VALUES ('admin', 'admin@example.com');
INSERT INTO users (username, email) VALUES ('student', 'student@example.com');

-- Колоды
INSERT INTO decks (name, owner_id, target_language, native_language, visibility) 
VALUES ('Английские слова', 1, 'en', 'ru', 'public');

-- Карточки
INSERT INTO flashcards (deck_id, term, definition, example_sentence) 
VALUES (1, 'apple', 'яблоко', 'I eat an apple every day');