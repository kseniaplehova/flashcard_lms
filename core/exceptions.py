class DeckAccessDenied(Exception):
    """Доступ к колоде запрещен."""
    pass


class CardGenerationError(Exception):
    """Ошибка генерации карточки."""
    pass


class AIAPIError(Exception):
    """Ошибка API искусственного интеллекта."""
    pass