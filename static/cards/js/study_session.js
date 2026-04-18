// Данные будут переданы через data-атрибуты
let STUDY_DATA = {
    cardId: 0,
    totalCards: 0,
    deckId: 0,
    currentCardNum: 1
};

function initStudySession(config) {
    STUDY_DATA = { ...STUDY_DATA, ...config };
    
    const progressFill = document.querySelector('.progress-fill');
    if (progressFill) {
        const progressPercent = (STUDY_DATA.currentCardNum / STUDY_DATA.totalCards) * 100;
        progressFill.style.width = progressPercent + '%';
    }
    
    document.getElementById('current-card-num').textContent = STUDY_DATA.currentCardNum;
    document.getElementById('total-cards').textContent = STUDY_DATA.totalCards;
}

function flipCard() {
    document.querySelector('.flashcard-front').style.display = 'none';
    document.querySelector('.flashcard-back').style.display = 'block';
}

function getCSRFToken() {
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    return csrfInput ? csrfInput.value : '';
}

async function submitAnswer(quality) {
    const response = await fetch(`/api/cards/${STUDY_DATA.cardId}/review/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify({ quality: quality })
    });
    
    const data = await response.json();
    
    if (data.success) {
        if (STUDY_DATA.currentCardNum < STUDY_DATA.totalCards) {
            window.location.reload();
        } else {
            window.location.href = `/decks/${STUDY_DATA.deckId}/`;
        }
    } else {
        alert('Ошибка при сохранении ответа');
    }
}

async function generateContext() {
    const btn = document.getElementById('generate-btn');
    const resultDiv = document.getElementById('generate-result');
    
    btn.disabled = true;
    btn.textContent = '⏳ Генерация...';
    resultDiv.innerHTML = '';
    
    try {
        const response = await fetch(`/api/cards/${STUDY_DATA.cardId}/generate-context/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('card-example').textContent = data.example;
            resultDiv.innerHTML = `
                <div class="success-message">
                    ✅ Новый пример сгенерирован!<br>
                    <small>Использовано токенов: ${data.tokens_used}</small>
                </div>
            `;
        } else {
            resultDiv.innerHTML = `
                <div class="error-message">
                    ❌ Ошибка: ${data.error}
                </div>
            `;
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="error-message">
                ❌ Ошибка соединения с сервером
            </div>
        `;
    } finally {
        btn.disabled = false;
        btn.textContent = '🤖 Сгенерировать новый пример через ИИ';
    }
}