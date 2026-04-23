(function() {
    'use strict';
    
    function getCSRFToken() {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfInput ? csrfInput.value : '';
    }
    
    async function toggleLike(deckId, btn) {
        try {
            const response = await fetch(`/decks/${deckId}/like/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken(),
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                btn.classList.toggle('liked', data.liked);
                const countSpan = btn.querySelector('.likes-count');
                if (countSpan) {
                    countSpan.textContent = data.likes_count;
                }
            }
        } catch (error) {
            console.error('Like error:', error);
        }
    }
    
    // Делаем функцию глобальной для onclick
    window.toggleLike = toggleLike;
})();