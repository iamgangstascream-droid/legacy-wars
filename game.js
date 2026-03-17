/**
 * Legacy Wars RPG - Game Engine
 * Telegram WebApp Integration
 */

// Game State
const Game = {
    tg: window.Telegram.WebApp,
    player: null,
    inventory: [],
    equipment: {
        weapon: null,
        armor: null,
        accessory: null
    },
    currentEnemy: null,
    currentLocation: 'town',
    battleActive: false,
    config: {
        apiEndpoint: null, // Will be set from bot
        version: '1.0.0'
    }
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    Game.tg.expand();
    Game.tg.ready();
    Game.tg.enableClosingConfirmation();
    
    // Set theme colors
    applyTheme();
    
    // Initialize UI
    initStars();
    initEventListeners();
    
    // Load player data
    loadPlayerData();
    
    // Setup periodic updates
    setInterval(updateEnergy, 60000); // Every minute
});

// Theme Application
function applyTheme() {
    const root = document.documentElement;
    const theme = Game.tg.themeParams;
    
    if (theme.bg_color) root.style.setProperty('--bg-dark', theme.bg_color);
    if (theme.text_color) root.style.setProperty('--text', theme.text_color);
    if (theme.button_color) root.style.setProperty('--primary', theme.button_color);
    
    // Set header color
    Game.tg.setHeaderColor(Game.tg.backgroundColor);
}

// Star Background
function initStars() {
    const container = document.getElementById('stars');
    if (!container) return;
    
    for (let i = 0; i < 50; i++) {
        const star = document.createElement('div');
        star.className = 'star';
        star.style.cssText = `
            left: ${Math.random() * 100}%;
            top: ${Math.random() * 100}%;
            animation-delay: ${Math.random() * 3}s;
            animation-duration: ${2 + Math.random() * 3}s;
        `;
        container.appendChild(star);
    }
}

// Event Listeners
function initEventListeners() {
    // Tab switching
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', (e) => switchTab(e.target.dataset.tab));
    });
    
    // Back button handling
    Game.tg.onEvent('backButtonClicked', () => {
        if (Game.battleActive) {
            showConfirm('Покинуть бой?', 'Прогресс будет потерян', flee);
        } else {
            Game.tg.close();
        }
    });
    
    // Main button (if needed)
    Game.tg.MainButton.setText('Действие').onClick(() => {
        // Context-aware action
    });
}

// Tab Switching
function switchTab(tabName) {
    // Update nav
    document.querySelectorAll('.nav-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.tab === tabName);
    });
    
    // Update panels
    document.querySelectorAll('.panel').forEach(p => {
        p.classList.toggle('active', p.id === `panel-${tabName}`);
    });
    
    // Tab-specific initialization
    switch(tabName) {
        case 'inventory':
            renderInventory();
            break;
        case 'locations':
            renderLocations();
            break;
        case 'shop':
            renderShop('weapons');
            break;
        case 'battle':
            if (!Game.currentEnemy && Game.currentLocation !== 'town') {
                spawnEnemy();
            }
            break;
    }
    
    // Haptic feedback
    Game.tg.HapticFeedback.impactOccurred('light');
}

// Data Loading
async function loadPlayerData() {
    showLoading('profile');
    
    try {
        // Send request to bot
        sendToBot({action: 'get_profile'});
        
        // For demo/development - simulate data
        await simulateNetworkDelay();
        
        Game.player = {
            id: 1,
            name: 'Герой',
            class: 'warrior',
            level: 5,
            exp: 250,
            expMax: 500,
            hp: 120,
            hpMax: 150,
            atk: 25,
            def: 15,
            crit: 8,
            gold: 1250,
            gems: 5,
            energy: 100,
            energyMax: 100,
            wins: 12,
            deaths: 2,
            location: 'forest'
        };
        
        Game.currentLocation = Game.player.location;
        updateProfileUI();
        
    } catch (error) {
        showError('Не удалось загрузить данные');
        console.error(error);
    }
}

// Profile UI Update
function updateProfileUI() {
    if (!Game.player) return;
    
    const p = Game.player;
    const classData = getClassData(p.class);
    
    // Avatar and info
    document.getElementById('class-avatar').textContent = classData.emoji;
    document.getElementById('player-name').textContent = p.name;
    document.getElementById('player-class').textContent = classData.name;
    document.getElementById('player-level').textContent = p.level;
    
    // Resources
    document.getElementById('gold').textContent = formatNumber(p.gold);
    document.getElementById('gems').textContent = p.gems;
    document.getElementById('energy').textContent = p.energy;
    
    // HP Bar
    const hpPercent = (p.hp / p.hpMax) * 100;
    document.getElementById('hp-text').textContent = `${p.hp}/${p.hpMax}`;
    document.getElementById('hp-bar').style.width = `${hpPercent}%`;
    
    // EXP Bar
    const expPercent = (p.exp / p.expMax) * 100;
    document.getElementById('exp-text').textContent = `${p.exp}/${p.expMax}`;
    document.getElementById('exp-bar').style.width = `${expPercent}%`;
    
    // Stats
    document.getElementById('stat-atk').textContent = p.atk;
    document.getElementById('stat-def').textContent = p.def;
    document.getElementById('stat-crit').textContent = p.crit + '%';
    document.getElementById('stat-wins').textContent = p.wins;
    
    // Battle stats
    document.getElementById('battle-player-avatar').textContent = classData.emoji;
    document.getElementById('battle-player-name').textContent = p.name;
    updateBattleHP();
    
    // Heal button visibility
    const healBtn = document.getElementById('heal-btn');
    if (healBtn) {
        healBtn.style.display = p.location === 'town' ? 'flex' : 'none';
    }
}

// Battle System
function spawnEnemy() {
    const enemies = {
        forest: [
            {name: 'Крыса', emoji: '🐀', hp: 30, atk: 5, exp: 15, gold: 10},
            {name: 'Волк', emoji: '🐺', hp: 60, atk: 12, exp: 30, gold: 25}
        ],
        cave: [
            {name: 'Змей', emoji: '🐍', hp: 80, atk: 18, exp: 50, gold: 40},
            {name: 'Гоблин', emoji: '👺', hp: 100, atk: 15, exp: 60, gold: 50}
        ],
        mountain: [
            {name: 'Орк', emoji: '👹', hp: 200, atk: 35, exp: 120, gold: 100},
            {name: 'Паук', emoji: '🕷️', hp: 180, atk: 40, exp: 150, gold: 130}
        ],
        dungeon: [
            {name: 'Дракон', emoji: '🐉', hp: 500, atk: 60, exp: 500, gold: 1000},
            {name: 'Демон', emoji: '👿', hp: 800, atk: 80, exp: 1000, gold: 2000}
        ]
    };
    
    const locationEnemies = enemies[Game.currentLocation] || enemies.forest;
    const template = locationEnemies[Math.floor(Math.random() * locationEnemies.length)];
    
    Game.currentEnemy = {
        ...template,
        maxHp: template.hp,
        currentHp: template.hp
    };
    
    renderEnemy();
    Game.battleActive = true;
    
    addBattleLog(`⚔️ На тебя напал ${Game.currentEnemy.emoji} ${Game.currentEnemy.name}!`, 'system');
}

function renderEnemy() {
    const enemy = Game.currentEnemy;
    if (!enemy) return;
    
    document.getElementById('enemy-selection').style.display = 'none';
    document.getElementById('enemy-card').style.display = 'block';
    document.getElementById('battle-log').style.display = 'block';
    document.getElementById('battle-actions').style.display = 'grid';
    
    document.getElementById('enemy-avatar').textContent = enemy.emoji;
    document.getElementById('enemy-name').textContent = enemy.name;
    updateEnemyHP();
}

function updateBattleHP() {
    if (!Game.player) return;
    const percent = Math.max(0, (Game.player.hp / Game.player.hpMax) * 100);
    document.getElementById('battle-player-hp').style.width = percent + '%';
    document.getElementById('battle-player-hp-text').textContent = 
        `${Math.max(0, Game.player.hp)}/${Game.player.hpMax} HP`;
}

function updateEnemyHP() {
    if (!Game.currentEnemy) return;
    const percent = Math.max(0, (Game.currentEnemy.currentHp / Game.currentEnemy.maxHp) * 100);
    document.getElementById('enemy-hp').style.width = percent + '%';
    document.getElementById('enemy-hp-text').textContent = 
        `${Math.max(0, Game.currentEnemy.currentHp)}/${Game.currentEnemy.maxHp} HP`;
}

// Combat Actions
function attack() {
    if (!Game.battleActive || !Game.currentEnemy) return;
    
    const p = Game.player;
    const e = Game.currentEnemy;
    
    // Calculate damage
    const baseDamage = p.atk;
    const variance = 0.2;
    const damage = Math.floor(baseDamage * (1 - variance + Math.random() * variance * 2));
    const isCrit = Math.random() * 100 < p.crit;
    const finalDamage = isCrit ? Math.floor(damage * 1.5) : damage;
    
    // Apply damage
    e.currentHp -= finalDamage;
    updateEnemyHP();
    
    // Visual feedback
    showDamage(finalDamage, 'enemy', isCrit);
    document.querySelector('.fighter.enemy').classList.add('hit');
    setTimeout(() => document.querySelector('.fighter.enemy').classList.remove('hit'), 500);
    
    // Log
    const critText = isCrit ? ' 💥 КРИТИЧЕСКИЙ УДАР!' : '';
    addBattleLog(`🗡️ Ты нанёс ${finalDamage} урона${critText}`, isCrit ? 'crit' : 'damage');
    
    // Haptic
    Game.tg.HapticFeedback.impactOccurred(isCrit ? 'heavy' : 'medium');
    
    // Check win
    if (e.currentHp <= 0) {
        winBattle();
        return;
    }
    
    // Enemy turn
    setTimeout(enemyTurn, 800);
}

function enemyTurn() {
    if (!Game.battleActive || !Game.currentEnemy) return;
    
    const p = Game.player;
    const e = Game.currentEnemy;
    
    // Enemy damage
    const damage = Math.max(1, e.atk - Math.floor(p.def / 2));
    const variance = 0.2;
    const finalDamage = Math.floor(damage * (1 - variance + Math.random() * variance * 2));
    
    p.hp -= finalDamage;
    updateBattleHP();
    updateProfileUI();
    
    // Visual feedback
    showDamage(finalDamage, 'player');
    document.querySelector('.fighter.player').classList.add('hit');
    setTimeout(() => document.querySelector('.fighter.player').classList.remove('hit'), 500);
    
    addBattleLog(`💔 ${e.name} нанёс ${finalDamage} урона`, 'enemy');
    
    Game.tg.HapticFeedback.impactOccurred('light');
    
    // Check lose
    if (p.hp <= 0) {
        loseBattle();
    }
}

function usePotion() {
    // Check inventory
    const potion = Game.inventory.find(i => i.type === 'consumable');
    if (!potion) {
        showNotification('Нет зелий!', 'error');
        return;
    }
    
    const healAmount = 50;
    Game.player.hp = Math.min(Game.player.hpMax, Game.player.hp + healAmount);
    updateBattleHP();
    updateProfileUI();
    
    addBattleLog(`🧪 Использовано зелье! +${healAmount} HP`, 'heal');
    Game.tg.HapticFeedback.notificationOccurred('success');
}

function flee() {
    if (!Game.battleActive) return;
    
    const fleeChance = 0.5;
    if (Math.random() < fleeChance) {
        addBattleLog('🏃 Ты успешно сбежал!', 'system');
        endBattle(false);
        Game.tg.HapticFeedback.notificationOccurred('success');
    } else {
        addBattleLog('❌ Не удалось сбежать!', 'system');
        setTimeout(enemyTurn, 500);
        Game.tg.HapticFeedback.notificationOccurred('error');
    }
}

function winBattle() {
    Game.battleActive = false;
    const e = Game.currentEnemy;
    const p = Game.player;
    
    // Rewards
    p.exp += e.exp;
    p.gold += e.gold;
    p.wins++;
    
    // Check level up
    let leveled = false;
    while (p.exp >= p.expMax) {
        p.exp -= p.expMax;
        p.level++;
        p.expMax = Math.floor(p.expMax * 1.5);
        p.hpMax += 10;
        p.atk += 2;
        p.def += 1;
        p.hp = p.hpMax;
        leveled = true;
    }
    
    updateProfileUI();
    
    // Drop chance
    const dropChance = 0.3;
    let dropText = '';
    if (Math.random() < dropChance) {
        const drops = ['potion_small', 'gold_ore', 'crystal'];
        const drop = drops[Math.floor(Math.random() * drops.length)];
        dropText = `\n🎁 Добыча: ${getItemName(drop)}`;
        addToInventory(drop);
    }
    
    Game.tg.HapticFeedback.notificationOccurred('success');
    
    showModal(
        '🏆 Победа!',
        `Получено:\n⭐ ${e.exp} опыта\n🪙 ${e.gold} золота${dropText}`,
        [{text: 'Отлично!', action: () => {
            closeModal();
            if (leveled) showLevelUp();
            resetBattle();
        }}]
    );
    
    sendToBot({action: 'battle_win', enemy: e.name, exp: e.exp, gold: e.gold});
}

function loseBattle() {
    Game.battleActive = false;
    Game.player.deaths++;
    Game.player.hp = 1;
    Game.player.location = 'town';
    Game.currentLocation = 'town';
    
    updateProfileUI();
    Game.tg.HapticFeedback.notificationOccurred('error');
    
    showModal(
        '💀 Поражение',
        'Ты потерял сознание. Тебя отнесли в деревню.',
        [{text: 'Продолжить', action: () => {
            closeModal();
            resetBattle();
            switchTab('profile');
        }}]
    );
    
    sendToBot({action: 'battle_lose'});
}

function endBattle(won) {
    Game.battleActive = false;
    Game.currentEnemy = null;
    
    document.getElementById('enemy-selection').style.display = 'block';
    document.getElementById('enemy-card').style.display = 'none';
    document.getElementById('battle-log').style.display = 'none';
    document.getElementById('battle-actions').style.display = 'none';
    document.getElementById('battle-log').innerHTML = '';
}

function resetBattle() {
    endBattle(false);
}

// Battle Log
function addBattleLog(text, type = 'normal') {
    const log = document.getElementById('battle-log');
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    entry.textContent = text;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

// Damage Visuals
function showDamage(amount, target, isCrit = false) {
    const popup = document.createElement('div');
    popup.className = `damage-popup ${isCrit ? 'crit' : ''}`;
    popup.textContent = amount;
    popup.style.color = isCrit ? 'var(--accent-gold)' : 'var(--accent-red)';
    
    const arena = document.getElementById('battle-arena');
    const rect = arena.getBoundingClientRect();
    
    popup.style.left = target === 'enemy' ? '70%' : '30%';
    popup.style.top = '40%';
    
    arena.appendChild(popup);
    setTimeout(() => popup.remove(), 1000);
}

// Inventory System
function renderInventory() {
    const grid = document.getElementById('inventory-grid');
    grid.innerHTML = '';
    
    // Generate slots
    for (let i = 0; i < 20; i++) {
        const slot = document.createElement('div');
        const item = Game.inventory[i];
        
        slot.className = 'inventory-slot' + (item ? '' : ' empty');
        
        if (item) {
            slot.innerHTML = `
                <div class="item-icon">${item.emoji || '📦'}</div>
                ${item.quantity > 1 ? `<div class="item-qty">${item.quantity}</div>` : ''}
            `;
            slot.onclick = () => showItemDetails(item);
        } else {
            slot.innerHTML = '<span style="color: var(--text-muted);">+</span>';
        }
        
        grid.appendChild(slot);
    }
    
    // Update equipment display
    updateEquipmentDisplay();
}

function updateEquipmentDisplay() {
    const slots = {
        weapon: document.getElementById('eq-weapon'),
        armor: document.getElementById('eq-armor'),
        accessory: document.getElementById('eq-accessory')
    };
    
    for (const [type, element] of Object.entries(slots)) {
        const equipped = Game.equipment[type];
        if (equipped) {
            element.innerHTML = `
                <div class="item-icon">${equipped.emoji}</div>
                <div style="font-size: 10px;">${equipped.name}</div>
            `;
            element.classList.add('equipped');
        }
    }
}

function addToInventory(itemId) {
    const existing = Game.inventory.find(i => i.id === itemId);
    if (existing) {
        existing.quantity++;
    } else {
        Game.inventory.push({
            id: itemId,
            name: getItemName(itemId),
            emoji: getItemEmoji(itemId),
            quantity: 1,
            type: getItemType(itemId)
        });
    }
}

// Locations
function renderLocations() {
    const list = document.getElementById('location-list');
    list.innerHTML = '';
    
    const locations = [
        {id: 'town', name: 'Деревня', emoji: '🏘️', desc: 'Безопасная зона', level: 1, safe: true},
        {id: 'forest', name: 'Тёмный лес', emoji: '🌲', desc: 'Крысы и волки', level: 1, safe: false},
        {id: 'cave', name: 'Пещеры', emoji: '🕳️', desc: 'Гоблины и змеи', level: 5, safe: false},
        {id: 'mountain', name: 'Горы', emoji: '⛰️', desc: 'Орки и пауки', level: 10, safe: false},
        {id: 'dungeon', name: 'Подземелье', emoji: '🏰', desc: 'Драконы', level: 15, safe: false}
    ];
    
    locations.forEach(loc => {
        const locked = Game.player.level < loc.level;
        const card = document.createElement('div');
        card.className = 'location-card' + (locked ? ' locked' : '');
        
        card.innerHTML = `
            <div class="location-icon">${loc.emoji}</div>
            <div class="location-info">
                <div class="location-name">${loc.name}</div>
                <div class="location-desc">${loc.desc}</div>
            </div>
            <div class="location-level">${locked ? '🔒 ' + loc.level : (loc.safe ? '✅' : '⚔️')}</div>
        `;
        
        if (!locked) {
            card.onclick = () => travelTo(loc);
        }
        
        list.appendChild(card);
    });
}

function travelTo(location) {
    if (Game.battleActive) {
        showNotification('Сначала закончи бой!', 'error');
        return;
    }
    
    if (location.safe) {
        Game.currentLocation = location.id;
        Game.player.location = location.id;
        updateProfileUI();
        showNotification(`Ты в ${location.name}`, 'success');
        sendToBot({action: 'travel', location: location.id});
    } else {
        showConfirm(
            `Войти в ${location.name}?`,
            location.desc,
            () => {
                Game.currentLocation = location.id;
                Game.player.location = location.id;
                switchTab('battle');
                spawnEnemy();
                sendToBot({action: 'travel', location: location.id});
            }
        );
    }
}

// Shop
function renderShop(category) {
    // Update tabs
    document.querySelectorAll('.shop-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.category === category);
    });
    
    const container = document.getElementById('shop-items');
    container.innerHTML = '';
    
    const items = {
        weapons: [
            {id: 'sword_iron', name: 'Железный меч', emoji: '⚔️', stats: 'ATK +12', price: 200, atk: 12},
            {id: 'sword_steel', name: 'Стальной меч', emoji: '🗡️', stats: 'ATK +25', price: 800, atk: 25}
        ],
        armor: [
            {id: 'armor_leather', name: 'Кожаная броня', emoji: '🧥', stats: 'DEF +8', price: 180, def: 8},
            {id: 'armor_chain', name: 'Кольчуга', emoji: '⛓️', stats: 'DEF +15', price: 600, def: 15}
        ],
        consumables: [
            {id: 'potion_small', name: 'Малое зелье', emoji: '🧪', stats: 'HP +30', price: 25, heal: 30},
            {id: 'potion_medium', name: 'Среднее зелье', emoji: '🧪', stats: 'HP +80', price: 80, heal: 80}
        ]
    };
    
    (items[category] || []).forEach(item => {
        const div = document.createElement('div');
        div.className = 'shop-item';
        div.innerHTML = `
            <div class="shop-item-icon">${item.emoji}</div>
            <div class="shop-item-info">
                <div class="shop-item-name">${item.name}</div>
                <div class="shop-item-stats">${item.stats}</div>
            </div>
            <div class="shop-item-price">
                <div class="price-gold">${item.price} 🪙</div>
            </div>
        `;
        div.onclick = () => buyItem(item);
        container.appendChild(div);
    });
}

function buyItem(item) {
    if (Game.player.gold < item.price) {
        showNotification('Недостаточно золота!', 'error');
        return;
    }
    
    showConfirm(
        `Купить ${item.name}?`,
        `Цена: ${item.price} золота`,
        () => {
            Game.player.gold -= item.price;
            addToInventory(item.id);
            updateProfileUI();
            showNotification('Куплено!', 'success');
            sendToBot({action: 'buy', item: item.id, price: item.price});
        }
    );
}

// Utility Functions
function getClassData(className) {
    const classes = {
        warrior: {name: 'Воин', emoji: '⚔️'},
        mage: {name: 'Маг', emoji: '🔮'},
        rogue: {name: 'Разбойник', emoji: '🗡️'},
        paladin: {name: 'Паладин', emoji: '🛡️'}
    };
    return classes[className] || classes.warrior;
}

function getItemName(id) {
    const names = {
        potion_small: 'Малое зелье',
        sword_iron: 'Железный меч',
        gold_ore: 'Золотая руда',
        crystal: 'Кристалл'
    };
    return names[id] || id;
}

function getItemEmoji(id) {
    const emojis = {
        potion_small: '🧪',
        sword_iron: '⚔️',
        gold_ore: '⛏️',
        crystal: '💎'
    };
    return emojis[id] || '📦';
}

function getItemType(id) {
    if (id.includes('potion')) return 'consumable';
    if (id.includes('sword')) return 'weapon';
    return 'misc';
}

function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
    return num.toString();
}

function simulateNetworkDelay() {
    return new Promise(resolve => setTimeout(resolve, 300 + Math.random() * 400));
}

// Communication with Bot
function sendToBot(data) {
    try {
        Game.tg.sendData(JSON.stringify(data));
    } catch (e) {
        console.log('Bot communication:', data);
    }
}

// UI Helpers
function showLoading(elementId) {
    const el = document.getElementById(elementId);
    if (el) {
        el.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    }
}

function showNotification(message, type = 'info') {
    const notif = document.createElement('div');
    notif.className = `notification ${type}`;
    notif.textContent = message;
    document.body.appendChild(notif);
    
    setTimeout(() => {
        notif.style.opacity = '0';
        setTimeout(() => notif.remove(), 300);
    }, 3000);
}

function showModal(title, body, buttons) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = body;
    
    const actions = document.getElementById('modal-actions');
    actions.innerHTML = '';
    
    buttons.forEach(btn => {
        const button = document.createElement('button');
        button.className = 'btn ' + (btn.primary !== false ? 'btn-primary' : 'btn-secondary');
        button.textContent = btn.text;
        button.onclick = btn.action;
        actions.appendChild(button);
    });
    
    document.getElementById('modal').classList.add('active');
}

function closeModal() {
    document.getElementById('modal').classList.remove('active');
}

function showConfirm(title, body, onConfirm) {
    showModal(title, body, [
        {text: 'Отмена', action: closeModal, primary: false},
        {text: 'Подтвердить', action: () => {
            closeModal();
            onConfirm();
        }, primary: true}
    ]);
}

function showError(message) {
    showNotification(message, 'error');
}

function showLevelUp() {
    const div = document.createElement('div');
    div.className = 'level-up';
    div.innerHTML = `
        <div>🎉 LEVEL UP! 🎉</div>
        <div style="font-size: 18px; margin-top: 10px;">Уровень ${Game.player.level}</div>
    `;
    document.body.appendChild(div);
    setTimeout(() => div.remove(), 2000);
    Game.tg.HapticFeedback.notificationOccurred('success');
}

// Energy System
function updateEnergy() {
    if (Game.player && Game.player.energy < Game.player.energyMax) {
        Game.player.energy = Math.min(Game.player.energyMax, Game.player.energy + 1);
        document.getElementById('energy').textContent = Game.player.energy;
    }
}

// Heal in town
function healInTown() {
    if (!Game.player || Game.player.location !== 'town') {
        showError('Лечение доступно только в деревне!');
        return;
    }
    
    if (Game.player.hp >= Game.player.hpMax) {
        showNotification('Здоровье полное!', 'info');
        return;
    }
    
    sendToBot({action: 'heal'});
    Game.player.hp = Game.player.hpMax;
    updateProfileUI();
    showNotification('💚 Здоровье восстановлено!', 'success');
}

// Daily bonus
function claimDaily() {
    sendToBot({action: 'daily_bonus'});
    // Logic handled by bot response
    showNotification('🎁 Бонус получен!', 'success');
}

// Expose functions globally for HTML onclick
window.switchTab = switchTab;
window.attack = attack;
window.usePotion = usePotion;
window.flee = flee;
window.healInTown = healInTown;
window.claimDaily = claimDaily;
window.closeModal = closeModal;
window.switchShopTab = renderShop;
