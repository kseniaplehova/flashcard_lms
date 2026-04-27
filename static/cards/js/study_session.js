document.addEventListener('DOMContentLoaded', function() {
    var container = document.querySelector('.study-page');
    if (!container) return;
    
    var correctAnswer = container.dataset.correctAnswer || '';
    var cardId = parseInt(container.dataset.cardId) || 0;
    var totalCards = parseInt(container.dataset.totalCards) || 0;
    var answered = false;
    var lastAnswerCorrect = false;
    
    console.log('study_session.js LOADED. Correct:', correctAnswer, 'Card:', cardId);
    
    function setAnswer(isCorrect) {
        if (answered) return;
        answered = true;
        lastAnswerCorrect = isCorrect;
        
        document.getElementById('card-id-input').value = cardId;
        document.getElementById('is-correct-input').value = isCorrect;
        
        console.log('Answer set: isCorrect=' + isCorrect);
    }
    
    function showFeedback(isCorrect) {
        var fb = document.getElementById('feedback');
        if (fb) {
            fb.style.display = 'block';
            fb.className = 'feedback ' + (isCorrect ? 'ok' : 'err');
            fb.textContent = isCorrect ? 'Правильно!' : 'Неправильно! ' + correctAnswer;
        }
        var next = document.getElementById('next-card-section');
        if (next) next.style.display = 'block';
    }
    
    function submitForm() {
        console.log('Submitting: cardId=' + cardId + ', isCorrect=' + lastAnswerCorrect);
        document.getElementById('answer-form').submit();
    }
    
    // Кнопки выбора
    document.querySelectorAll('.option-btn').forEach(function(btn) {
        btn.onclick = function() {
            if (answered) return;
            var selected = this.dataset.option || this.textContent.trim();
            var isCorrect = (selected === correctAnswer);
            
            console.log('Selected:', selected, 'Match:', isCorrect);
            
            setAnswer(isCorrect);
            showFeedback(isCorrect);
            
            document.querySelectorAll('.option-btn').forEach(function(b) {
                b.disabled = true;
                var opt = b.dataset.option || b.textContent.trim();
                if (opt === correctAnswer) b.classList.add('correct');
                else if (opt === selected && !isCorrect) b.classList.add('wrong');
            });
            
            // Авто-отправка через 2 секунды
            setTimeout(submitForm, 2000);
        };
    });
    
    // Кнопка "Далее"
    var nextBtn = document.getElementById('next-card-btn');
    if (nextBtn) {
        nextBtn.onclick = function() {
            if (answered) submitForm();
        };
    }
    
    // Кнопки ввода текста
    ['submit-typing', 'submit-reverse', 'submit-fill'].forEach(function(id) {
        var btn = document.getElementById(id);
        if (btn) {
            btn.onclick = function() {
                if (answered) return;
                var input = document.getElementById('answer-input');
                if (!input || !input.value.trim()) return;
                
                var userAnswer = input.value.trim().toLowerCase();
                var correct = correctAnswer.toLowerCase();
                var isCorrect = (userAnswer === correct) || (userAnswer.length > 2 && correct.includes(userAnswer));
                
                console.log('Typed:', userAnswer, 'Match:', isCorrect);
                
                setAnswer(isCorrect);
                showFeedback(isCorrect);
                
                input.disabled = true;
                this.disabled = true;
                
                setTimeout(submitForm, 2000);
            };
        }
    });
    
    // Enter в поле ввода
    var input = document.getElementById('answer-input');
    if (input) {
        input.onkeypress = function(e) {
            if (e.key === 'Enter' && !answered) {
                e.preventDefault();
                var submitBtn = document.querySelector('#submit-typing, #submit-reverse, #submit-fill');
                if (submitBtn) submitBtn.click();
            }
        };
    }
    
    // Прогресс-бар
    var progressFill = document.getElementById('progress-fill');
    if (progressFill && totalCards > 0) {
        progressFill.style.width = (1 / totalCards * 100) + '%';
    }
});