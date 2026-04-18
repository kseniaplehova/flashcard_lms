(function() {
    'use strict';
    
    const container = document.querySelector('.study-container');
    if (!container) return;
    
    const STUDY_DATA = {
        cardId: parseInt(container.dataset.cardId) || 0,
        totalCards: parseInt(container.dataset.totalCards) || 0,
        deckId: parseInt(container.dataset.deckId) || 0,
        exerciseType: container.dataset.exerciseType || 'multiple_choice',
        correctAnswer: container.dataset.correctAnswer || '',
        currentCardNum: 1
    };
    
    let answerSubmitted = false;
    let lastAnswerWasCorrect = false;
    
    function init() {
        console.log('Study session initialized:', STUDY_DATA);
        updateProgress();
        bindEvents();
        ensureFormHasCardId();
    }
    
    function ensureFormHasCardId() {
        const cardIdInput = document.getElementById('card-id-input');
        if (cardIdInput && STUDY_DATA.cardId) {
            cardIdInput.value = STUDY_DATA.cardId;
        }
    }
    
    function updateProgress() {
        const progressFill = document.getElementById('progress-fill');
        const cardNumSpan = document.getElementById('current-card-num');
        
        if (progressFill && STUDY_DATA.totalCards > 0) {
            const percent = (STUDY_DATA.currentCardNum / STUDY_DATA.totalCards) * 100;
            progressFill.style.width = percent + '%';
        }
        
        if (cardNumSpan) {
            cardNumSpan.textContent = STUDY_DATA.currentCardNum;
        }
    }
    
    function bindEvents() {
        // Множественный выбор
        const optionBtns = document.querySelectorAll('.option-btn');
        optionBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                if (answerSubmitted) return;
                const selected = this.dataset.option || this.textContent.trim();
                handleMultipleChoice(selected);
            });
        });
        
        // Ввод текста
        const submitTyping = document.getElementById('submit-typing');
        if (submitTyping) {
            submitTyping.addEventListener('click', handleTyping);
        }
        
        const submitReverse = document.getElementById('submit-reverse');
        if (submitReverse) {
            submitReverse.addEventListener('click', handleTyping);
        }
        
        const submitFill = document.getElementById('submit-fill');
        if (submitFill) {
            submitFill.addEventListener('click', handleTyping);
        }
        
        // Enter в поле ввода
        const answerInput = document.getElementById('answer-input');
        if (answerInput) {
            answerInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && !answerSubmitted) {
                    e.preventDefault();
                    handleTyping();
                }
            });
        }
        
        // Кнопка "Следующая карточка"
        const nextBtn = document.getElementById('next-card-btn');
        if (nextBtn) {
            nextBtn.addEventListener('click', function() {
                if (answerSubmitted) {
                    submitForm();
                }
            });
        }
    }
    
    function handleMultipleChoice(selected) {
        if (answerSubmitted) return;
        
        lastAnswerWasCorrect = (selected === STUDY_DATA.correctAnswer);
        const buttons = document.querySelectorAll('.option-btn');
        
        buttons.forEach(btn => {
            btn.disabled = true;
            const option = btn.dataset.option || btn.textContent.trim();
            if (option === STUDY_DATA.correctAnswer) {
                btn.classList.add('correct');
            } else if (option === selected && !lastAnswerWasCorrect) {
                btn.classList.add('wrong');
            }
        });
        
        showFeedback(lastAnswerWasCorrect);
        answerSubmitted = true;
    }
    
    function handleTyping() {
        if (answerSubmitted) return;
        
        const input = document.getElementById('answer-input');
        if (!input || !input.value.trim()) {
            alert('Введите ответ');
            return;
        }
        
        const userAnswer = input.value.trim().toLowerCase();
        const correctAnswer = STUDY_DATA.correctAnswer.toLowerCase();
        
        lastAnswerWasCorrect = userAnswer === correctAnswer;
        
        if (!lastAnswerWasCorrect && userAnswer.length > 2 && correctAnswer.length > 2) {
            lastAnswerWasCorrect = correctAnswer.includes(userAnswer) || userAnswer.includes(correctAnswer);
        }
        
        showFeedback(lastAnswerWasCorrect);
        answerSubmitted = true;
        
        // Блокируем кнопки
        const submitBtn = document.querySelector('#submit-typing, #submit-reverse, #submit-fill');
        if (submitBtn) submitBtn.disabled = true;
        if (input) input.disabled = true;
    }
    
    function showFeedback(isCorrect) {
        const feedback = document.getElementById('feedback');
        const nextSection = document.getElementById('next-card-section');
        
        if (feedback) {
            feedback.style.display = 'block';
            feedback.className = 'feedback ' + (isCorrect ? 'correct' : 'wrong');
            feedback.innerHTML = isCorrect 
                ? '✅ Правильно! Отличная работа!'
                : `❌ Неправильно. Правильный ответ: <strong>${STUDY_DATA.correctAnswer}</strong>`;
        }
        
        if (nextSection) {
            nextSection.style.display = 'block';
        }
    }
    
    function submitForm() {
        const form = document.getElementById('answer-form');
        if (!form) {
            console.error('Form not found');
            window.location.reload();
            return;
        }
        
        const cardIdInput = document.getElementById('card-id-input');
        const isCorrectInput = document.getElementById('is-correct-input');
        
        if (!cardIdInput) {
            console.error('Card ID input not found');
            return;
        }
        
        cardIdInput.value = STUDY_DATA.cardId;
        if (isCorrectInput) {
            isCorrectInput.value = lastAnswerWasCorrect;
        }
        
        console.log('Submitting answer:', {
            cardId: STUDY_DATA.cardId,
            isCorrect: lastAnswerWasCorrect
        });
        
        form.submit();
    }
    
    init();
})();