(function() {
    'use strict';
    
    // Устанавливаем высоту баров для графика активности
    function initBarChart() {
        const bars = document.querySelectorAll('.bar[data-height]');
        if (!bars.length) return;
        
        const counts = Array.from(bars).map(b => parseInt(b.dataset.height) || 0);
        const maxCount = Math.max(...counts, 1);
        
        bars.forEach(bar => {
            const count = parseInt(bar.dataset.height) || 0;
            const percent = (count / maxCount) * 100;
            bar.style.height = Math.max(percent, 4) + '%';
        });
    }
    
    // Инициализация при загрузке
    document.addEventListener('DOMContentLoaded', function() {
        initBarChart();
    });
    
})();
