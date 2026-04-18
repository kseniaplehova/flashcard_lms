from django.contrib import admin
from apps.cards.models import Deck, Flashcard, UserCardProgress, DeckProgress, AIGenerationLog


@admin.register(Deck)
class DeckAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'owner', 'target_language', 'created_at']
    list_filter = ['target_language', 'created_at']
    search_fields = ['name', 'owner__username']
    raw_id_fields = ['owner']


@admin.register(Flashcard)
class FlashcardAdmin(admin.ModelAdmin):
    list_display = ['id', 'term', 'definition_preview', 'deck', 'base_difficulty', 'is_active']
    list_filter = ['base_difficulty', 'is_active', 'part_of_speech']
    search_fields = ['term', 'definition']
    raw_id_fields = ['deck']
    
    def definition_preview(self, obj: Flashcard) -> str:
        if obj.definition:
            return obj.definition[:50] + '...' if len(obj.definition) > 50 else obj.definition
        return '—'
    definition_preview.short_description = 'Определение'


@admin.register(UserCardProgress)
class UserCardProgressAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'flashcard_term', 'easiness_factor',
        'consecutive_correct', 'next_review_at', 'requires_context_refresh'
    ]
    list_filter = ['requires_context_refresh', 'easiness_factor']
    search_fields = ['user__username', 'flashcard__term']
    raw_id_fields = ['user', 'flashcard']
    readonly_fields = ['total_attempts', 'total_errors', 'average_response_time_ms']
    
    def flashcard_term(self, obj: UserCardProgress) -> str:
        if obj.pk and hasattr(obj, 'flashcard') and obj.flashcard:
            return obj.flashcard.term
        return '—'
    flashcard_term.short_description = 'Термин'
    flashcard_term.admin_order_field = 'flashcard__term'


@admin.register(DeckProgress)
class DeckProgressAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'deck_name', 'cards_mastered', 
        'cards_learning', 'cards_struggling', 'updated_at'
    ]
    raw_id_fields = ['user', 'deck']
    readonly_fields = ['total_time_spent_seconds']
    
    def deck_name(self, obj: DeckProgress) -> str:
        if obj.pk and hasattr(obj, 'deck') and obj.deck:
            return obj.deck.name
        return '—'
    deck_name.short_description = 'Колода'
    deck_name.admin_order_field = 'deck__name'


@admin.register(AIGenerationLog)
class AIGenerationLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'flashcard_preview', 'model_used', 
        'tokens_used', 'latency_ms', 'was_successful', 'created_at'
    ]
    list_filter = ['was_successful', 'model_used', 'created_at']
    readonly_fields = [
        'request_prompt', 'response_content', 'error_message',
        'tokens_used', 'latency_ms'
    ]
    raw_id_fields = ['user', 'flashcard']
    
    def flashcard_preview(self, obj: AIGenerationLog) -> str:
        if obj.pk and hasattr(obj, 'flashcard') and obj.flashcard:
            flashcard = obj.flashcard
            if hasattr(flashcard, 'deck') and flashcard.deck:
                return f"{flashcard.term} ({flashcard.deck.name})"
            return flashcard.term
        return '—'
    flashcard_preview.short_description = 'Карточка'