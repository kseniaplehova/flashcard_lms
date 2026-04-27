-- ============================================
-- СХЕМА БАЗЫ ДАННЫХ FLASHCARD LMS
-- ============================================

-- 1. ПОЛЬЗОВАТЕЛИ
-- Хранит учетные записи
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(150) UNIQUE NOT NULL,
    email VARCHAR(254),
    password VARCHAR(128) NOT NULL,
    date_joined DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
);

-- 2. КОЛОДЫ
-- Группы карточек, созданные пользователями
CREATE TABLE decks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    target_language VARCHAR(50) DEFAULT 'en',
    native_language VARCHAR(50) DEFAULT 'ru',
    visibility VARCHAR(10) DEFAULT 'private',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. ФЛЕШ-КАРТОЧКИ
-- Отдельные карточки со словами и переводами
CREATE TABLE flashcards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id INTEGER NOT NULL REFERENCES decks(id),
    term VARCHAR(255) NOT NULL,
    definition TEXT NOT NULL,
    example_sentence TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 4. ПРОГРЕСС ПОЛЬЗОВАТЕЛЯ
-- Хранит состояние обучения каждой карточки (алгоритм SM-2)
CREATE TABLE user_card_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    flashcard_id INTEGER NOT NULL REFERENCES flashcards(id),
    easiness_factor REAL DEFAULT 2.5,
    consecutive_correct INTEGER DEFAULT 0,
    total_attempts INTEGER DEFAULT 0,
    next_review_at DATETIME,
    UNIQUE(user_id, flashcard_id)
);

-- 5. ЛАЙКИ КОЛОД
-- Пользователи могут лайкать публичные колоды
CREATE TABLE deck_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id INTEGER NOT NULL REFERENCES decks(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(deck_id, user_id)
);

-- 6. АКТИВНОСТЬ ПОЛЬЗОВАТЕЛЕЙ
-- Логирование действий для аналитики
CREATE TABLE user_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    action VARCHAR(50) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- СВЯЗИ МЕЖДУ ТАБЛИЦАМИ
-- ============================================
-- users 1──N decks         (один пользователь создает много колод)
-- users 1──N user_card_progress (один пользователь учит много карточек)
-- users 1──N deck_likes    (один пользователь лайкает много колод)
-- decks 1──N flashcards    (одна колода содержит много карточек)
-- flashcards 1──N user_card_progress (одну карточку учат много пользователей)