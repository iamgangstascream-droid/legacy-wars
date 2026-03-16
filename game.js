// Telegram Mini App инициализация
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();
tg.setHeaderColor('#1a1a2e');
tg.setBackgroundColor('#16213e');

// Глобальные переменные
let currentUser = null;
let currentCharacter = null;
let currentEnemy = null;
let battleInterval = null;

// Показать экран
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    document.getElementById(screenId).classList.add('active');
    
    if (screenId === 'profile') {
        loadProfile();
    }
}

// Загрузка данных пользователя
async function loadUserData() {
    try {
        document.getElementById('loading').classList.add('active');
        
        // Получаем данные из Telegram
        const initData = tg.initDataUnsafe;
        const userId = initData.user?.id;
        
        // Отправляем запрос в бота
        tg.sendData(JSON.stringify({
            action: 'get_profile',
            user_id: userId
        }));
        
        // Тут будет обработка ответа от бота
        setTimeout(() => {
            document.getElementById('loading').classList.remove('active');
            showScreen('main-menu');
        }, 1000);
        
    } catch (error) {
        console.error('Ошибка загрузки:', error);
    }
}

// Выбор класса
function selectClass(className) {
    document.getElementById('name-input').style.display = 'block';
    window.selectedClass = className;
}

// Создание персонажа
function createCharacter() {
    const name = document.getElementById('character-name').value.trim();
    if (!name) {
        tg.showAlert('Введи имя героя!');
        return;
    }
    
    if (name.length < 2 || name.length > 20) {
        tg.showAlert('Имя должно быть от 2 до 20 символов!');
        return;
    }
    
    // Отправляем данные в бота
    tg.sendData(JSON.stringify({
        action: 'create_character',
        class: window.selectedClass,
        name: name,
        user_id: tg.initDataUnsafe.user?.id
    }));
    
    tg.showAlert(`✅ Герой ${name} создан! Возвращайся в бота.`);
    showScreen('main-menu');
}

// Загрузка профиля
async function loadProfile() {
    tg.sendData(JSON.stringify({
        action: 'get_profile',
        user_id: tg.initDataUnsafe.user?.id
    }));
}

// Начало битвы
function startBattle() {
    // Создаем врага
    const enemies = [
        { name: 'Гоблин', emoji: '👾', hp: 50, attack: 8, defense: 3 },
        { name: 'Орк', emoji: '👹', hp: 80, attack: 12, defense: 5 },
        { name: 'Скелет', emoji: '💀', hp: 60, attack: 10, defense: 4 }
    ];
    
    currentEnemy = enemies[Math.floor(Math.random() * enemies.length)];
    currentEnemy.hp = currentEnemy.hp;
    currentEnemy.maxHp = currentEnemy.hp;
    
    document.getElementById('enemy-char').textContent = currentEnemy.emoji;
    updateEnemyHp();
    
    document.getElementById('battle-log').innerHTML = '⚔️ Битва началась!';
    showScreen('game');
}

// Атака игрока
function playerAttack() {
    if (!currentEnemy) {
        startBattle();
        return;
    }
    
    // Анимация
    document.querySelector('.player-area .battle-char').classList.add('shake');
    setTimeout(() => {
        document.querySelector('.player-area .battle-char').classList.remove('shake');
    }, 500);
    
    // Урон
    const damage = Math.floor(Math.random() * 20) + 10;
    currentEnemy.hp -= damage;
    
    // Лог
    addBattleLog(`⚔️ Ты нанес ${damage} урона!`);
    updateEnemyHp();
    
    // Проверка победы
    if (currentEnemy.hp <= 0) {
        victory();
        return;
    }
    
    // Ход врага
    setTimeout(enemyAttack, 1000);
}

// Атака врага
function enemyAttack() {
    document.querySelector('.enemy-area .battle-char').classList.add('shake');
    setTimeout(() => {
        document.querySelector('.enemy-area .battle-char').classList.remove('shake');
    }, 500);
    
    const damage = Math.floor(Math.random() * 15) + 5;
    addBattleLog(`👾 Враг нанес ${damage} урона!`);
    
    // TODO: уменьшать HP игрока
}

// Победа
function victory() {
    addBattleLog('🎉 ПОБЕДА! +50 опыта, +100 золота');
    currentEnemy = null;
    
    // Отправляем результат в бота
    tg.sendData(JSON.stringify({
        action: 'battle_result',
        result: 'victory',
        reward: { exp: 50, gold: 100 }
    }));
}

// Бегство
function runFromBattle() {
    addBattleLog('🏃 Ты сбежал с поля боя');
    currentEnemy = null;
    showScreen('main-menu');
}

// Обновление HP врага
function updateEnemyHp() {
    const percent = (currentEnemy.hp / currentEnemy.maxHp) * 100;
    document.getElementById('enemy-hp').style.setProperty('--hp-width', percent + '%');
}

// Добавление в лог
function addBattleLog(text) {
    const log = document.getElementById('battle-log');
    log.innerHTML = text + '<br>' + log.innerHTML;
    if (log.children.length > 5) {
        log.removeChild(log.lastChild);
    }
}

// Обработка данных от бота
tg.onEvent('web_app_data_sent', function() {
    console.log('Данные отправлены в бота');
});

// Загрузка при старте
window.onload = () => {
    loadUserData();
};
