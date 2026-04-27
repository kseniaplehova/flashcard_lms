(function() {
    'use strict';
    
    var langColors = {
        'en': '#3b82f6',
        'es': '#f59e0b',
        'fr': '#8b5cf6',
        'de': '#ef4444',
        'it': '#10b981',
        'pt': '#10b981',
        'ja': '#ef4444',
        'ko': '#3b82f6',
        'zh': '#ef4444',
        'ru': '#6366f1'
    };
    
    function initLanguageFlags() {
        var flags = document.querySelectorAll('.language-flag[data-lang]');
        flags.forEach(function(el) {
            var lang = el.getAttribute('data-lang');
            el.style.background = langColors[lang] || '#6366f1';
        });
    }
    
    function initLangTags() {
        var tags = document.querySelectorAll('.lang-tag[data-lang]');
        tags.forEach(function(el) {
            var lang = el.getAttribute('data-lang');
            el.style.background = langColors[lang] || '#6366f1';
        });
    }
    
    document.addEventListener('DOMContentLoaded', function() {
        initLanguageFlags();
        initLangTags();
    });
})();