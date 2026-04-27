(function() {
    'use strict';
    
    function getCSRFToken() {
        var csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfInput ? csrfInput.value : '';
    }
    
    function toggleLike(deckId, btn) {
        fetch('/decks/' + deckId + '/like/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            }
        })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            if (d.success) {
                btn.classList.toggle('liked', d.liked);
                var countSpan = btn.querySelector('.likes-count');
                if (countSpan) {
                    countSpan.textContent = d.likes_count;
                }
            }
        })
        .catch(function(error) {
            console.error('Like error:', error);
        });
    }
    
    document.addEventListener('DOMContentLoaded', function() {
        var buttons = document.querySelectorAll('.like-btn');
        console.log('Like buttons found:', buttons.length);
        
        buttons.forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('Like clicked!', this.dataset.deckId);
                toggleLike(this.dataset.deckId, this);
            });
        });
    });
})();