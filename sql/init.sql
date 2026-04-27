-- Создание таблицы пользователей
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(150) UNIQUE NOT NULL,
    email VARCHAR(254),
    password VARCHAR(128) NOT NULL,
    first_name VARCHAR(150) DEFAULT '',
    last_name VARCHAR(150) DEFAULT '',
    is_staff BOOLEAN DEFAULT 0,
    is_superuser BOOLEAN DEFAULT 0,
    is_teacher BOOLEAN DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    date_joined DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
);

-- Создание таблицы колод
CREATE TABLE IF NOT EXISTS decks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    owner_id INTEGER NOT NULL,
    target_language VARCHAR(50) DEFAULT 'en',
    native_language VARCHAR(50) DEFAULT 'ru',
    visibility VARCHAR(10) DEFAULT 'private' CHECK(visibility IN ('private', 'public')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_decks_owner ON decks(owner_id);
CREATE INDEX IF NOT EXISTS idx_decks_visibility ON decks(visibility);

-- Создание таблицы флеш-карточек
CREATE TABLE IF NOT EXISTS flashcards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id INTEGER NOT NULL,
    term VARCHAR(255) NOT NULL,
    definition TEXT NOT NULL,
    part_of_speech VARCHAR(50) DEFAULT '',
    example_sentence TEXT DEFAULT '',
    base_difficulty INTEGER DEFAULT 3 CHECK(base_difficulty BETWEEN 1 AND 5),
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_flashcards_deck ON flashcards(deck_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_term ON flashcards(term);

-- Создание таблицы прогресса пользователя по карточкам
CREATE TABLE IF NOT EXISTS user_card_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    flashcard_id INTEGER NOT NULL,
    repetition_number INTEGER DEFAULT 0,
    easiness_factor REAL DEFAULT 2.5 CHECK(easiness_factor >= 1.3),
    inter_repetition_interval INTEGER DEFAULT 0,
    consecutive_correct INTEGER DEFAULT 0,
    total_attempts INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    average_response_time_ms INTEGER DEFAULT 0,
    last_reviewed_at DATETIME,
    next_review_at DATETIME,
    last_quality_response INTEGER DEFAULT 0 CHECK(last_quality_response BETWEEN 0 AND 5),
    requires_context_refresh BOOLEAN DEFAULT 0,
    UNIQUE(user_id, flashcard_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (flashcard_id) REFERENCES flashcards(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_progress_user_next ON user_card_progress(user_id, next_review_at);

-- Создание таблицы прогресса по колодам
CREATE TABLE IF NOT EXISTS deck_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    deck_id INTEGER NOT NULL,
    cards_mastered INTEGER DEFAULT 0,
    cards_learning INTEGER DEFAULT 0,
    cards_struggling INTEGER DEFAULT 0,
    last_session_at DATETIME,
    total_time_spent_seconds INTEGER DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, deck_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE
);

-- Создание таблицы лайков
CREATE TABLE IF NOT EXISTS deck_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(deck_id, user_id),
    FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Создание таблицы активности пользователей
CREATE TABLE IF NOT EXISTS user_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action VARCHAR(50) NOT NULL,
    deck_id INTEGER,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_activities_user ON user_activities(user_id);
CREATE INDEX IF NOT EXISTS idx_activities_date ON user_activities(created_at);

-- Создание таблицы логов ИИ-генерации
CREATE TABLE IF NOT EXISTS ai_generation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    flashcard_id INTEGER,
    request_prompt TEXT NOT NULL,
    response_content TEXT DEFAULT '',
    model_used VARCHAR(100) DEFAULT 'gpt-4o-mini',
    tokens_used INTEGER DEFAULT 0,
    latency_ms INTEGER DEFAULT 0,
    was_successful BOOLEAN DEFAULT 0,
    error_message TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (flashcard_id) REFERENCES flashcards(id) ON DELETE SET NULL
);