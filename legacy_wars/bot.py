# bot.py - LEGACY WARS RPG - ПОЛНАЯ ВЕРСИЯ
import logging
import json
import random
import sqlite3
import asyncio
import threading
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes, ConversationHandler
)
from config import BOT_TOKEN, WEBAPP_URL, ADMIN_IDS, DATABASE_FILE

# Flask App Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
flask_app = Flask(__name__, static_folder=BASE_DIR)
CORS(flask_app)
application = flask_app # Это нужно для хостинга Beget

def run_flask():
    logger.info("=== FLASK SERVER STARTING ON PORT 5000 ===")
    # На хостинге Beget порт может назначаться автоматически
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host='0.0.0.0', port=port, threaded=True)

@flask_app.route('/')
def serve_index():
    logger.info("Request received for index.html")
    return send_from_directory(BASE_DIR, 'index.html')

@flask_app.route('/api/player/<int:user_id>', methods=['GET'])
def get_player_api(user_id):
    logger.info(f"API: Request profile for {user_id}")
    player = db.get_player(user_id)
    if player:
        stats = get_stats_with_equipment(player)
        inventory = db.get_inventory(user_id)
        return jsonify({
            'success': True,
            'player': player,
            'stats': stats,
            'inventory': inventory,
            'items_def': ITEMS,
            'classes_def': CLASSES,
            'monsters_def': MONSTERS,
            'locations_def': LOCATIONS
        })
    return jsonify({'success': False, 'error': 'Player not found'})

@flask_app.route('/api/create_player', methods=['POST'])
def create_player_api():
    try:
        data = request.json
        logger.info(f"API: Create player: {data}")
        user_id = data.get('user_id')
        username = data.get('username', 'Unknown')
        name = data.get('name')
        class_type = data.get('class_type')
        referred_by = data.get('referred_by')
        
        if not all([user_id, name, class_type]):
            return jsonify({'success': False, 'error': 'Данные неполные'})
        
        if db.get_player(user_id):
            return jsonify({'success': False, 'error': 'Герой уже есть'})
            
        db.create_player(user_id, username, name, class_type, referred_by)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"API Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@flask_app.route('/api/donate', methods=['POST'])
def handle_donation():
    try:
        data = request.json
        user_id = data.get('user_id')
        pack_id = data.get('pack_id')
        
        packs = {
            'crystals_small': {'amount': 50, 'price': 100},
            'crystals_medium': {'amount': 150, 'price': 250},
            'crystals_large': {'amount': 500, 'price': 700}
        }
        
        if pack_id not in packs:
            return jsonify({'success': False, 'error': 'Пакет не найден'})
            
        pack = packs[pack_id]
        player = db.get_player(user_id)
        if not player:
            return jsonify({'success': False, 'error': 'Игрок не найден'})
            
        current_crystals = player.get('crystals', 0)
        new_crystals = current_crystals + pack['amount']
        db.update_player(user_id, crystals=new_crystals)
        return jsonify({'success': True, 'crystals': new_crystals})
    except Exception as e:
        logger.error(f"Donate error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@flask_app.route('/api/exchange', methods=['POST'])
def handle_exchange():
    try:
        data = request.json
        user_id = data.get('user_id')
        amount = int(data.get('amount', 10))
        
        player = db.get_player(user_id)
        if not player:
            return jsonify({'success': False, 'error': 'Игрок не найден'})
            
        current_crystals = int(player.get('crystals', 0))
        if current_crystals < amount:
            return jsonify({'success': False, 'error': f'Недостаточно кристаллов. У вас {current_crystals}, нужно {amount}'})
            
        gold_gain = amount * 100
        new_crystals = current_crystals - amount
        new_gold = int(player.get('gold', 0)) + gold_gain
        
        db.update_player(user_id, crystals=new_crystals, gold=new_gold)
        return jsonify({'success': True, 'crystals': new_crystals, 'gold': new_gold})
    except Exception as e:
        logger.error(f"Exchange error: {e}")
        return jsonify({'success': False, 'error': str(e)})

RECIPES = {
    'sword_steel': {'gold_ore': 3, 'gold': 200},
    'staff_mage': {'crystal': 3, 'gold': 300},
    'dagger_shadow': {'dragon_scale': 1, 'gold': 500},
    'armor_plate': {'gold_ore': 5, 'gold': 400}
}

@flask_app.route('/api/action', methods=['POST'])
def handle_action():
    try:
        data = request.json
        user_id = data.get('user_id')
        action = data.get('action')
        params = data.get('params', {})
        logger.info(f"API: Action {action} for {user_id}")
        
        player = db.get_player(user_id)
        if not player:
            return jsonify({'success': False, 'error': 'Герой не найден'})
            
        if action == 'battle' or action == 'raid':
            if action == 'raid':
                monster_template = MONSTERS[4] # Дракон
            else:
                monster_idx = int(params.get('monster_idx', 0))
                if monster_idx >= len(MONSTERS): monster_idx = 0
                monster_template = MONSTERS[monster_idx]
            
            stats = get_stats_with_equipment(player)
            p_hp = int(player.get('hp', 100))
            m_hp = int(monster_template.get('hp', 100))
            log = []
            
            while p_hp > 0 and m_hp > 0:
                dmg = max(1, int(stats.get('atk', 10)) - int(monster_template.get('atk', 5)) // 2)
                if random.randint(1, 100) <= int(stats.get('crit', 5)):
                    dmg = int(dmg * 1.5)
                    log.append(f"💥 КРИТ! Вы нанесли {dmg} урона")
                else:
                    log.append(f"🗡️ Вы нанесли {dmg} урона")
                m_hp -= dmg
                if m_hp <= 0: break
                
                m_dmg = max(1, int(monster_template.get('atk', 5)) - int(stats.get('defense', 5)) // 2)
                p_hp -= m_dmg
                log.append(f"💔 {monster_template['name']} нанес {m_dmg} урона")
                
            if p_hp <= 0:
                db.update_player(user_id, hp=1, deaths=int(player.get('deaths', 0)) + 1)
                return jsonify({'success': True, 'win': False, 'log': log, 'hp': 1})
            else:
                gold_gain = int(monster_template.get('gold', 0))
                exp_gain = int(monster_template.get('exp', 0))
                new_exp = int(player.get('exp', 0)) + exp_gain
                new_level = int(player.get('level', 1))
                new_exp_max = int(player.get('exp_max', 100))
                
                if new_exp >= new_exp_max:
                    new_exp -= new_exp_max
                    new_level += 1
                    new_exp_max = get_level_up_exp(new_level)
                
                drop = None
                if random.random() < 0.4:
                    drop = random.choice(['gold_ore', 'crystal', 'dragon_scale'])
                    db.add_item(user_id, drop)

                db.update_player(user_id, hp=p_hp, gold=int(player.get('gold', 0)) + gold_gain, 
                                 exp=new_exp, level=new_level, exp_max=new_exp_max,
                                 wins=int(player.get('wins', 0)) + 1)
                return jsonify({
                    'success': True, 'win': True, 'log': log, 
                    'gold_gain': gold_gain, 'exp_gain': exp_gain, 
                    'drop': drop, 'drop_name': ITEMS[drop]['name'] if drop else None
                })
        
        if action == 'buy':
            item_id = params.get('item_id')
            item = ITEMS.get(item_id)
            if not item or player['gold'] < item['price']:
                return jsonify({'success': False, 'error': 'Недостаточно золота'})
            db.update_player(user_id, gold=player['gold'] - item['price'])
            db.add_item(user_id, item_id)
            return jsonify({'success': True})

        if action == 'use':
            item_id = params.get('item_id')
            item = ITEMS.get(item_id)
            if not item or item['type'] != 'consumable':
                return jsonify({'success': False, 'error': 'Нельзя использовать'})
            inventory = db.get_inventory(user_id)
            if inventory.get(item_id, 0) <= 0:
                return jsonify({'success': False, 'error': 'Нет предмета'})
            if item.get('heal'):
                stats = get_stats_with_equipment(player)
                new_hp = min(stats['hp_max'], player['hp'] + item['heal'])
                db.update_player(user_id, hp=new_hp)
                db.remove_item(user_id, item_id)
                return jsonify({'success': True, 'hp': new_hp})

        if action == 'craft':
            item_id = params.get('item_id')
            recipe = RECIPES.get(item_id)
            if not recipe: return jsonify({'success': False, 'error': 'Рецепт не найден'})
            
            inventory = db.get_inventory(user_id)
            for res_id, count in recipe.items():
                if res_id == 'gold':
                    if player['gold'] < count: return jsonify({'success': False, 'error': 'Недостаточно золота'})
                else:
                    if inventory.get(res_id, 0) < count: return jsonify({'success': False, 'error': f'Нужно больше {ITEMS[res_id]["name"]}'})
            
            for res_id, count in recipe.items():
                if res_id == 'gold':
                    db.update_player(user_id, gold=player['gold'] - count)
                else:
                    db.remove_item(user_id, res_id, count)
            
            db.add_item(user_id, item_id)
            return jsonify({'success': True, 'item_name': ITEMS[item_id]['name']})

        return jsonify({'success': False, 'error': 'Действие не найдено'})
    except Exception as e:
        logger.error(f"API Action Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@flask_app.route('/images/<path:path>')
def serve_images(path):
    return send_from_directory(os.path.join(BASE_DIR, 'images'), path)

(SELECT_CLASS, ENTER_NAME, CONFIRM_DELETE, TRADE_AMOUNT,
 TRADE_CONFIRM, MESSAGE_USER, SET_PRICE) = range(7)

CLASSES = {
    'warrior': {
        'name': '⚔️ Воин', 'hp': 150, 'atk': 15, 'def': 10, 'crit': 5,
        'endurance': 10, 'impact': 5, 'rage': 0, 'max_rage': 100
    },
    'mage': {
        'name': '🔮 Маг', 'hp': 80, 'atk': 25, 'def': 3, 'crit': 15,
        'mana': 100, 'max_mana': 100, 'cast_speed': 10,
        'spell_intensity': 10, 'cooldown_reduction': 0, 'spell_power': 20
    },
    'rogue': {
        'name': '🗡️ Разбойник', 'hp': 100, 'atk': 20, 'def': 5, 'crit': 25,
        'agility': 15, 'evasion': 10, 'stealth': 10, 'energy': 100, 'max_energy': 100
    },
    'paladin': {
        'name': '🛡️ Паладин', 'hp': 130, 'atk': 12, 'def': 15, 'crit': 3,
        'faith': 15, 'aura_radius': 10, 'aura_strength': 10,
        'self_heal': 5, 'magic_resist': 10, 'holy_power': 50, 'max_holy_power': 100
    }
}

ITEMS = {
    'sword_wood': {'name': '🗡️ Деревянный меч', 'type': 'weapon', 'atk': 5, 'price': 50},
    'sword_iron': {'name': '⚔️ Железный меч', 'type': 'weapon', 'atk': 12, 'price': 200},
    'sword_steel': {'name': '🗡️ Стальной меч', 'type': 'weapon', 'atk': 25, 'price': 800},
    'sword_berserker': {'name': '🗡️ Меч Берсерка', 'type': 'weapon', 'atk': 18, 'impact': 8, 'price': 600},
    'hammer_holy': {'name': '⚒️ Святой молот', 'type': 'weapon', 'atk': 15, 'faith': 10, 'aura_strength': 5, 'price': 700},
    'mace_blessed': {'name': '⚔️ Благословенная булава', 'type': 'weapon', 'atk': 20, 'faith': 15, 'self_heal': 3, 'price': 1200},
    'staff_apprentice': {'name': '🔮 Посох ученика', 'type': 'weapon', 'atk': 8, 'spell_power': 15, 'max_mana': 20, 'price': 60},
    'staff_mage': {'name': '🔯 Посох мага', 'type': 'weapon', 'atk': 22, 'spell_power': 35, 'spell_intensity': 8, 'price': 900},
    'dagger_iron': {'name': '🗡️ Железный кинжал', 'type': 'weapon', 'atk': 10, 'agility': 5, 'price': 150},
    'dagger_shadow': {'name': '🌑 Теневой клинок', 'type': 'weapon', 'atk': 30, 'agility': 10, 'stealth': 5, 'price': 1500},
    'armor_cloth': {'name': '👕 Тканевая броня', 'type': 'armor', 'def': 3, 'price': 40},
    'armor_leather': {'name': '🧥 Кожаная броня', 'type': 'armor', 'def': 8, 'agility': 3, 'price': 180},
    'armor_chain': {'name': '⛓️ Кольчуга', 'type': 'armor', 'def': 15, 'price': 600},
    'armor_plate': {'name': '🛡️ Латы', 'type': 'armor', 'def': 25, 'price': 2000},
    'armor_titan': {'name': '🛡️ Латы Титана', 'type': 'armor', 'def': 20, 'endurance': 10, 'hp': 50, 'price': 1200},
    'armor_paladin': {'name': '🛡️ Броня паладина', 'type': 'armor', 'def': 18, 'faith': 8, 'aura_radius': 5, 'magic_resist': 10, 'price': 1500},
    'armor_holy': {'name': '🛡️ Священные латы', 'type': 'armor', 'def': 25, 'faith': 15, 'aura_radius': 8, 'aura_strength': 8, 'price': 3000},
    'robe_mage': {'name': '🔮 Мантия мага', 'type': 'armor', 'def': 5, 'max_mana': 30, 'spell_intensity': 5, 'price': 500},
    'armor_shadow': {'name': '🌑 Теневая броня', 'type': 'armor', 'def': 10, 'evasion': 8, 'stealth': 5, 'price': 1000},
    'ring_hp': {'name': '💍 Кольцо здоровья', 'type': 'accessory', 'hp': 20, 'price': 300},
    'ring_atk': {'name': '💍 Кольцо силы', 'type': 'accessory', 'atk': 5, 'price': 400},
    'ring_rage': {'name': '💍 Кольцо Ярости', 'type': 'accessory', 'impact': 5, 'crit': 8, 'price': 700},
    'ring_agility': {'name': '💍 Кольцо ловкости', 'type': 'accessory', 'agility': 8, 'evasion': 5, 'price': 650},
    'ring_holy': {'name': '💍 Кольцо света', 'type': 'accessory', 'faith': 8, 'magic_resist': 10, 'aura_strength': 5, 'price': 850},
    'amulet_crit': {'name': '📿 Амулет крита', 'type': 'accessory', 'crit': 10, 'price': 800},
    'amulet_mana': {'name': '💎 Амулет маны', 'type': 'accessory', 'max_mana': 40, 'spell_intensity': 6, 'price': 600},
    'amulet_stealth': {'name': '🌙 Амулет тени', 'type': 'accessory', 'stealth': 10, 'evasion': 6, 'price': 950},
    'amulet_faith': {'name': '📿 Амулет веры', 'type': 'accessory', 'faith': 12, 'self_heal': 5, 'price': 900},
    'shield_holy': {'name': '🛡️ Святой щит', 'type': 'accessory', 'defense': 15, 'magic_resist': 15, 'faith': 10, 'price': 1800},
    'potion_small': {'name': '🧪 Малое зелье', 'type': 'consumable', 'heal': 30, 'price': 25},
    'potion_medium': {'name': '🧪 Среднее зелье', 'type': 'consumable', 'heal': 80, 'price': 80},
    'potion_large': {'name': '🧪 Большое зелье', 'type': 'consumable', 'heal': 200, 'price': 250},
    'gold_ore': {'name': '⛏️ Золотая руда', 'type': 'resource', 'price': 50},
    'crystal': {'name': '💎 Кристалл маны', 'type': 'resource', 'price': 150},
    'dragon_scale': {'name': '🐉 Чешуя дракона', 'type': 'resource', 'price': 500},
}

MONSTERS = [
    {'name': '🐀 Крыса', 'level': 1, 'hp': 30, 'atk': 5, 'exp': 10, 'gold': 5, 'drop': ['potion_small'], 'image': 'rat.png'},
    {'name': '🐺 Волк', 'level': 3, 'hp': 60, 'atk': 12, 'exp': 25, 'gold': 15, 'drop': ['potion_small', 'armor_cloth'], 'image': 'wolf.png'},
    {'name': '🐻 Медведь', 'level': 5, 'hp': 120, 'atk': 20, 'exp': 50, 'gold': 40, 'drop': ['potion_medium', 'armor_leather'], 'image': 'bear.png'},
    {'name': '👹 Орк', 'level': 10, 'hp': 200, 'atk': 35, 'exp': 120, 'gold': 100, 'drop': ['armor_chain', 'sword_steel'], 'image': 'orc.png'},
    {'name': '🐉 Дракон', 'level': 20, 'hp': 500, 'atk': 60, 'exp': 500, 'gold': 1000, 'drop': ['dragon_scale', 'armor_plate'], 'image': 'dragon.png'},
]

LOCATIONS = {
    'town': {'name': '🏘️ Деревня', 'safe': True, 'monsters': []},
    'forest': {'name': '🌲 Тёмный лес', 'safe': False, 'monsters': [0, 1], 'level_req': 1},
    'cave': {'name': '🕳️ Пещеры', 'safe': False, 'monsters': [2, 3], 'level_req': 5},
    'dungeon': {'name': '🏰 Подземелье', 'safe': False, 'monsters': [4], 'level_req': 15},
}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_file="game.db"):
        self.db_file = db_file
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            username TEXT, name TEXT, class TEXT,
            level INTEGER DEFAULT 1, exp INTEGER DEFAULT 0, exp_max INTEGER DEFAULT 100,
            hp INTEGER DEFAULT 100, hp_max INTEGER DEFAULT 100,
            atk INTEGER DEFAULT 10, defense INTEGER DEFAULT 5, crit INTEGER DEFAULT 5,
            gold INTEGER DEFAULT 100, crystals INTEGER DEFAULT 0,
            location TEXT DEFAULT 'town',
            referred_by INTEGER, referral_count INTEGER DEFAULT 0,
            created_at TEXT, last_daily TEXT,
            wins INTEGER DEFAULT 0, deaths INTEGER DEFAULT 0,
            equipped_weapon TEXT, equipped_armor TEXT, equipped_accessory TEXT,
            endurance INTEGER DEFAULT 0, impact INTEGER DEFAULT 0, rage INTEGER DEFAULT 0, max_rage INTEGER DEFAULT 100,
            mana INTEGER DEFAULT 100, max_mana INTEGER DEFAULT 100, cast_speed INTEGER DEFAULT 10,
            spell_intensity INTEGER DEFAULT 10, cooldown_reduction INTEGER DEFAULT 0, spell_power INTEGER DEFAULT 20,
            agility INTEGER DEFAULT 10, evasion INTEGER DEFAULT 5, stealth INTEGER DEFAULT 5,
            energy INTEGER DEFAULT 100, max_energy INTEGER DEFAULT 100,
            faith INTEGER DEFAULT 15, aura_radius INTEGER DEFAULT 10, aura_strength INTEGER DEFAULT 10,
            self_heal INTEGER DEFAULT 5, magic_resist INTEGER DEFAULT 10,
            holy_power INTEGER DEFAULT 50, max_holy_power INTEGER DEFAULT 100
        )''')
        
        # Check if columns exist (for existing databases)
        c.execute("PRAGMA table_info(players)")
        existing_columns = [column[1] for column in c.fetchall()]
        
        # Список всех необходимых колонок с их типами и значениями по умолчанию
        required_columns = [
            ('crystals', 'INTEGER DEFAULT 0'),
            ('referred_by', 'INTEGER'),
            ('referral_count', 'INTEGER DEFAULT 0'),
            ('wins', 'INTEGER DEFAULT 0'),
            ('deaths', 'INTEGER DEFAULT 0'),
            ('endurance', 'INTEGER DEFAULT 0'),
            ('impact', 'INTEGER DEFAULT 0'),
            ('rage', 'INTEGER DEFAULT 0'),
            ('max_rage', 'INTEGER DEFAULT 100'),
            ('mana', 'INTEGER DEFAULT 100'),
            ('max_mana', 'INTEGER DEFAULT 100'),
            ('cast_speed', 'INTEGER DEFAULT 10'),
            ('spell_intensity', 'INTEGER DEFAULT 10'),
            ('cooldown_reduction', 'INTEGER DEFAULT 0'),
            ('spell_power', 'INTEGER DEFAULT 20'),
            ('agility', 'INTEGER DEFAULT 10'),
            ('evasion', 'INTEGER DEFAULT 5'),
            ('stealth', 'INTEGER DEFAULT 5'),
            ('energy', 'INTEGER DEFAULT 100'),
            ('max_energy', 'INTEGER DEFAULT 100'),
            ('faith', 'INTEGER DEFAULT 15'),
            ('aura_radius', 'INTEGER DEFAULT 10'),
            ('aura_strength', 'INTEGER DEFAULT 10'),
            ('self_heal', 'INTEGER DEFAULT 5'),
            ('magic_resist', 'INTEGER DEFAULT 10'),
            ('holy_power', 'INTEGER DEFAULT 50'),
            ('max_holy_power', 'INTEGER DEFAULT 100')
        ]
        
        for col_name, col_def in required_columns:
            if col_name not in existing_columns:
                try:
                    c.execute(f"ALTER TABLE players ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Database: Added missing column {col_name}")
                except Exception as e:
                    logger.error(f"Database migration error for {col_name}: {e}")
        
        c.execute('''CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, item_id TEXT, quantity INTEGER DEFAULT 1
        )''')
        
        conn.commit()
        conn.close()

    def get_player(self, user_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            p = dict(row)
            numeric_fields = ['gold', 'crystals', 'level', 'exp', 'exp_max', 'hp', 'hp_max', 
                             'atk', 'defense', 'crit', 'wins', 'deaths', 'referral_count']
            for field in numeric_fields:
                if p.get(field) is None: p[field] = 0
            return p
        return None

    def update_player(self, user_id: int, **kwargs):
        if not kwargs: return
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        fields = ", ".join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values())
        values.append(user_id)
        c.execute(f"UPDATE players SET {fields} WHERE user_id = ?", values)
        conn.commit()
        conn.close()

    def create_player(self, user_id: int, username: str, name: str, class_type: str, referred_by: int = None):
        base_stats = CLASSES[class_type]
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        # Initial gold and crystals
        initial_gold = 100
        initial_crystals = 0
        if referred_by:
            initial_gold += 500
            initial_crystals += 10

        c.execute('''INSERT INTO players 
            (user_id, username, name, class, hp, hp_max, atk, defense, crit, gold, crystals, created_at, referred_by,
             endurance, impact, rage, max_rage, mana, max_mana, cast_speed, spell_intensity, cooldown_reduction, spell_power,
             agility, evasion, stealth, energy, max_energy, faith, aura_radius, aura_strength, self_heal, magic_resist, holy_power, max_holy_power)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, username, name, class_type, base_stats['hp'], base_stats['hp'],
             base_stats['atk'], base_stats['def'], base_stats['crit'], initial_gold, initial_crystals, datetime.now().isoformat(), referred_by,
             base_stats.get('endurance', 0), base_stats.get('impact', 0), base_stats.get('rage', 0), base_stats.get('max_rage', 100),
             base_stats.get('mana', 100), base_stats.get('max_mana', 100), base_stats.get('cast_speed', 10),
             base_stats.get('spell_intensity', 10), base_stats.get('cooldown_reduction', 0), base_stats.get('spell_power', 20),
             base_stats.get('agility', 10), base_stats.get('evasion', 5), base_stats.get('stealth', 5),
             base_stats.get('energy', 100), base_stats.get('max_energy', 100),
             base_stats.get('faith', 15), base_stats.get('aura_radius', 10), base_stats.get('aura_strength', 10),
             base_stats.get('self_heal', 5), base_stats.get('magic_resist', 10),
             base_stats.get('holy_power', 50), base_stats.get('max_holy_power', 100)))
        
        c.execute("INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, ?)", (user_id, 'sword_wood', 1))
        c.execute("INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, ?)", (user_id, 'armor_cloth', 1))
        c.execute("INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, ?)", (user_id, 'potion_small', 3))
        
        if referred_by:
            # Reward the referrer
            c.execute("UPDATE players SET gold = gold + 500, crystals = crystals + 10, referral_count = referral_count + 1 WHERE user_id = ?", (referred_by,))
        
        conn.commit()
        conn.close()

    def get_inventory(self, user_id: int) -> Dict[str, int]:
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT item_id, quantity FROM inventory WHERE user_id = ?", (user_id,))
        items = {row[0]: row[1] for row in c.fetchall()}
        conn.close()
        return items

    def add_item(self, user_id: int, item_id: str, quantity: int = 1):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id))
        row = c.fetchone()
        if row:
            c.execute("UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_id = ?", (row[0] + quantity, user_id, item_id))
        else:
            c.execute("INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, ?)", (user_id, item_id, quantity))
        conn.commit()
        conn.close()

    def remove_item(self, user_id: int, item_id: str, quantity: int = 1):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id))
        row = c.fetchone()
        if row:
            new_qty = row[0] - quantity
            if new_qty <= 0:
                c.execute("DELETE FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id))
            else:
                c.execute("UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_id = ?", (new_qty, user_id, item_id))
        conn.commit()
        conn.close()

db = Database(DATABASE_FILE)

def get_stats_with_equipment(player: Dict) -> Dict:
    stats = {
        'hp_max': int(player.get('hp_max', 100)), 
        'atk': int(player.get('atk', 10)), 
        'defense': int(player.get('defense', 5)), 
        'crit': int(player.get('crit', 5)),
        'endurance': int(player.get('endurance', 0)),
        'impact': int(player.get('impact', 0)),
        'rage': int(player.get('rage', 0)), 
        'max_rage': int(player.get('max_rage', 100)),
        'mana': int(player.get('mana', 100)), 
        'max_mana': int(player.get('max_mana', 100)),
        'cast_speed': int(player.get('cast_speed', 10)), 
        'spell_intensity': int(player.get('spell_intensity', 10)),
        'cooldown_reduction': int(player.get('cooldown_reduction', 0)), 
        'spell_power': int(player.get('spell_power', 20)),
        'agility': int(player.get('agility', 10)), 
        'evasion': int(player.get('evasion', 5)),
        'stealth': int(player.get('stealth', 5)), 
        'energy': int(player.get('energy', 100)),
        'max_energy': int(player.get('max_energy', 100)),
        'faith': int(player.get('faith', 15)), 
        'aura_radius': int(player.get('aura_radius', 10)),
        'aura_strength': int(player.get('aura_strength', 10)), 
        'self_heal': int(player.get('self_heal', 5)),
        'magic_resist': int(player.get('magic_resist', 10)),
        'holy_power': int(player.get('holy_power', 50)), 
        'max_holy_power': int(player.get('max_holy_power', 100))
    }
    
    if player.get('equipped_weapon') and player['equipped_weapon'] in ITEMS:
        w = ITEMS[player['equipped_weapon']]
        stats['atk'] += w.get('atk', 0); stats['crit'] += w.get('crit', 0)
        stats['impact'] += w.get('impact', 0); stats['spell_power'] += w.get('spell_power', 0)
        stats['spell_intensity'] += w.get('spell_intensity', 0); stats['max_mana'] += w.get('max_mana', 0)
        stats['agility'] += w.get('agility', 0); stats['stealth'] += w.get('stealth', 0)
        stats['faith'] += w.get('faith', 0); stats['aura_strength'] += w.get('aura_strength', 0)
    
    if player.get('equipped_armor') and player['equipped_armor'] in ITEMS:
        a = ITEMS[player['equipped_armor']]
        stats['defense'] += a.get('def', 0); stats['hp_max'] += a.get('hp', 0)
        stats['endurance'] += a.get('endurance', 0); stats['max_mana'] += a.get('max_mana', 0)
        stats['evasion'] += a.get('evasion', 0); stats['stealth'] += a.get('stealth', 0)
        stats['magic_resist'] += a.get('magic_resist', 0); stats['aura_radius'] += a.get('aura_radius', 0)
        stats['faith'] += a.get('faith', 0); stats['aura_strength'] += a.get('aura_strength', 0)
    
    if player.get('equipped_accessory') and player['equipped_accessory'] in ITEMS:
        acc = ITEMS[player['equipped_accessory']]
        stats['hp_max'] += acc.get('hp', 0); stats['atk'] += acc.get('atk', 0)
        stats['defense'] += acc.get('def', 0); stats['crit'] += acc.get('crit', 0)
        stats['impact'] += acc.get('impact', 0); stats['max_mana'] += acc.get('max_mana', 0)
        stats['cooldown_reduction'] += acc.get('cooldown_reduction', 0)
        stats['agility'] += acc.get('agility', 0); stats['evasion'] += acc.get('evasion', 0)
        stats['stealth'] += acc.get('stealth', 0); stats['faith'] += acc.get('faith', 0)
        stats['self_heal'] += acc.get('self_heal', 0); stats['magic_resist'] += acc.get('magic_resist', 0)
        stats['aura_strength'] += acc.get('aura_strength', 0)
    
    if stats['endurance'] > 0: stats['hp_max'] += int(stats['endurance'] * 5)
    if stats['spell_intensity'] > 0: stats['max_mana'] += int(stats['spell_intensity'] * 2)
    if stats['faith'] > 0:
        stats['max_holy_power'] += int(stats['faith'] * 2)
        stats['hp_max'] += int(stats['faith'] * 3)
    
    return stats

def get_level_up_exp(level: int) -> int:
    return int(100 * (1.5 ** (level - 1)))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Игрок"
    player = db.get_player(user_id)

    # Referral system
    ref_id = None
    if context.args and context.args[0].startswith('ref'):
        try:
            ref_id = int(context.args[0].replace('ref', ''))
            if ref_id == user_id:
                ref_id = None
        except:
            pass

    webapp_url_with_ref = f"{WEBAPP_URL}"
    if ref_id:
        webapp_url_with_ref += f"?ref={ref_id}"

    keyboard = [[InlineKeyboardButton("🎮 ИГРАТЬ", web_app=WebAppInfo(url=webapp_url_with_ref))]]
    
    if player:
        await update.message.reply_text(
            f"⚔️ *С возвращением, {player['name']}!*\n"
            f"Твой персонаж готов к новым битвам в Legacy War.\n\n"
            f"Нажми кнопку ниже, чтобы войти в игру:",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )
    else:
        welcome_text = (
            "⚔️ *LEGACY WARS*\n\n"
            "👋 Приветствуем тебя, искатель приключений!\n\n"
            "Legacy War — это эпическая RPG прямо в твоем Telegram.\n"
            "Создай героя, сражайся с монстрами и стань легендой!\n\n"
        )
        if ref_id:
            welcome_text += "🎁 *Ты пришел по приглашению!* При создании героя ты получишь 500 золота и 10 кристаллов.\n\n"
            
        welcome_text += "Нажми кнопку «ИГРАТЬ», чтобы создать персонажа и начать свой путь:"
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )

async def create_char_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("⚔️ Воин", callback_data='class_warrior')],
        [InlineKeyboardButton("🔮 Маг", callback_data='class_mage')],
        [InlineKeyboardButton("🗡️ Разбойник", callback_data='class_rogue')],
        [InlineKeyboardButton("🛡️ Паладин", callback_data='class_paladin')]
    ]
    await query.edit_message_text(
        "Выбери класс:\n\n"
        "*Воин* — выживаемость\n"
        "*Маг* — разрушительная магия\n"
        "*Разбойник* — криты и скорость\n"
        "*Паладин* — защита и поддержка",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def select_class_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    class_type = query.data.replace('class_', '')
    context.user_data['selected_class'] = class_type
    await query.edit_message_text(f"Выбран: *{CLASSES[class_type]['name']}*\n\nВведи имя:", parse_mode='Markdown')
    return ENTER_NAME

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text[:20]
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    class_type = context.user_data.get('selected_class', 'warrior')
    
    db.create_player(user_id, username, name, class_type)
    db.add_item(user_id, 'sword_wood')
    db.add_item(user_id, 'armor_cloth')
    db.add_item(user_id, 'potion_small', 3)
    
    keyboard = [[InlineKeyboardButton("🎮 НАЧАТЬ ИГРУ", web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text(
        f"✅ *Персонаж создан!*\n\n"
        f"Имя: {name}\n"
        f"Класс: {CLASSES[class_type]['name']}\n\n"
        f"🎁 *Стартовый набор:*\n"
        f"• Деревянный меч\n"
        f"• Тканевая броня\n"
        f"• 3 зелья",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )
    return ConversationHandler.END

async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    player = db.get_player(user_id)
    if not player: return
    
    stats = get_stats_with_equipment(player)
    class_info = CLASSES.get(player['class'], {})
    weapon = ITEMS.get(player['equipped_weapon'], {}).get('name', 'Нет')
    armor = ITEMS.get(player['equipped_armor'], {}).get('name', 'Нет')
    accessory = ITEMS.get(player['equipped_accessory'], {}).get('name', 'Нет')
    
    exp_percent = (player['exp'] / player['exp_max']) * 100
    bar_filled = int(exp_percent / 10)
    exp_bar = '█' * bar_filled + '░' * (10 - bar_filled)
    
    keyboard = [[InlineKeyboardButton("🎒 Инвентарь", callback_data='inventory'), InlineKeyboardButton("⚔️ Экипировка", callback_data='equipment')],
                [InlineKeyboardButton("🔙 Назад", callback_data='main_menu')]]
    
    text = (f"📊 *{player['name']}*\n{class_info.get('name', 'Unknown')} | Уровень {player['level']}\n"
            f"├─ Опыт: [{exp_bar}] {player['exp']}/{player['exp_max']}\n├─ ❤️ HP: {player['hp']}/{stats['hp_max']}\n"
            f"├─ ⚔️ Атака: {stats['atk']} | 🛡️ Защита: {stats['defense']}\n├─ 💥 Крит: {stats['crit']}%\n"
            f"├─ 🪙 Золото: {player['gold']}\n├─ 🏆 Побед: {player['wins']} | 💀 Смертей: {player['deaths']}\n\n"
            f"*Экипировка:*\n🗡️ {weapon}\n👕 {armor}\n💍 {accessory}")
    
    if player['class'] == 'warrior':
        text += f"\n\n*Воин:*\n💪 Выносливость: {stats['endurance']} (+{stats['endurance']*5} HP)\n💥 Сила удара: {stats['impact']}\n🔥 Гнев: {stats['rage']}/{stats['max_rage']}"
    elif player['class'] == 'mage':
        text += f"\n\n*Маг:*\n💧 Мана: {stats['mana']}/{stats['max_mana']}\n🔥 Интенсивность: {stats['spell_intensity']}\n⏰ CDR: {stats['cooldown_reduction']}%"
    elif player['class'] == 'rogue':
        double_chance = stats['agility'] * 2
        text += f"\n\n*Разбойник:*\n🏃 Ловкость: {stats['agility']} (двойная атака: {double_chance}%)\n💨 Уклонение: {stats['evasion']}%\n🌑 Скрытность: {stats['stealth']}"
    elif player['class'] == 'paladin':
        holy_bonus = stats['faith'] * 5
        text += f"\n\n*Паладин:*\n✨ Вера: {stats['faith']} (holy +{holy_bonus}%)\n💫 Аура: радиус {stats['aura_radius']}м, сила {stats['aura_strength']}\n💚 Самоисцеление: {stats['self_heal'] * 10} HP\n🔮 Сопротивление магии: {stats['magic_resist']}%"
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def inventory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    inventory = db.get_inventory(user_id)
    text = "🎒 *Инвентарь:*\n\n" + "\n".join([f"• {ITEMS.get(i, {'name': i})['name']} x{q}" for i, q in sorted(inventory.items())]) if inventory else "Пусто"
    keyboard = [[InlineKeyboardButton("⚔️ Экипировать", callback_data='equipment'), InlineKeyboardButton("💊 Использовать", callback_data='use_item')],
                [InlineKeyboardButton("🔙 Назад", callback_data='main_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def equipment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    inventory = db.get_inventory(user_id)
    weapons = [(k, v) for k, v in inventory.items() if ITEMS.get(k, {}).get('type') == 'weapon']
    armors = [(k, v) for k, v in inventory.items() if ITEMS.get(k, {}).get('type') == 'armor']
    accessories = [(k, v) for k, v in inventory.items() if ITEMS.get(k, {}).get('type') == 'accessory']
    
    keyboard = []
    text = "⚔️ *Экипировка:*\n\n"
    for item_id, qty in weapons:
        item = ITEMS[item_id]
        text += f"🗡️ {item['name']} (+{item.get('atk', 0)} ATK)\n"
        keyboard.append([InlineKeyboardButton(f"🗡️ {item['name']}", callback_data=f'equip_{item_id}')])
    for item_id, qty in armors:
        item = ITEMS[item_id]
        text += f"👕 {item['name']} (+{item.get('def', 0)} DEF)\n"
        keyboard.append([InlineKeyboardButton(f"👕 {item['name']}", callback_data=f'equip_{item_id}')])
    for item_id, qty in accessories:
        item = ITEMS[item_id]
        text += f"💍 {item['name']}\n"
        keyboard.append([InlineKeyboardButton(f"💍 {item['name']}", callback_data=f'equip_{item_id}')])
    
    if not keyboard: text = "⚔️ *Нет предметов*"
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='profile')])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def equip_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    item_id = query.data.replace('equip_', '')
    if item_id not in ITEMS:
        await query.edit_message_text("❌ Предмет не найден"); return
    item = ITEMS[item_id]
    player = db.get_player(user_id)
    slot_map = {'weapon': 'equipped_weapon', 'armor': 'equipped_armor', 'accessory': 'equipped_accessory'}
    slot = slot_map.get(item['type'])
    if not slot:
        await query.answer("❌ Нельзя экипировать!"); return
    old_item = player.get(slot)
    if old_item: db.add_item(user_id, old_item)
    db.remove_item(user_id, item_id)
    db.update_player(user_id, **{slot: item_id})
    await query.edit_message_text(f"✅ *Экипировано:* {item['name']}", parse_mode='Markdown')
    await asyncio.sleep(1)
    await profile_callback(update, context)

async def use_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    inventory = db.get_inventory(user_id)
    consumables = [(k, v) for k, v in inventory.items() if ITEMS.get(k, {}).get('type') == 'consumable']
    if not consumables:
        await query.edit_message_text("❌ Нет расходников"); return
    keyboard = [[InlineKeyboardButton(f"🧪 {ITEMS[i]['name']} ({q} шт.)", callback_data=f'use_{i}')] for i, q in consumables]
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='inventory')])
    await query.edit_message_text("💊 *Выбери зелье:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def use_consumable_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    item_id = query.data.replace('use_', '')
    if item_id not in ITEMS: return
    item = ITEMS[item_id]
    player = db.get_player(user_id)
    if item.get('heal'):
        new_hp = min(player['hp_max'], player['hp'] + item['heal'])
        db.update_player(user_id, hp=new_hp)
        db.remove_item(user_id, item_id)
        await query.edit_message_text(f"💚 *Использовано:* {item['name']}\nВосстановлено: +{item['heal']} HP\nHP: {new_hp}/{player['hp_max']}", parse_mode='Markdown')

async def battle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    player = db.get_player(user_id)
    location = LOCATIONS.get(player['location'], LOCATIONS['town'])
    keyboard = []
    text = f"⚔️ *Бой*\n\nЛокация: {location['name']}\nУровень: {player['level']} | HP: {player['hp']}/{player['hp_max']}\n\n"
    if location['safe']:
        text += "🏘️ *Безопасно*\nВыбери локацию:"
        for loc_id, loc in LOCATIONS.items():
            if not loc['safe']:
                keyboard.append([InlineKeyboardButton(f"{loc['name']} (ур. {loc['level_req']}+)", callback_data=f'goto_{loc_id}')])
    else:
        text += "*Монстры:*\n"
        for monster_idx in location['monsters']:
            monster = MONSTERS[monster_idx]
            if player['level'] >= monster['level'] - 5:
                keyboard.append([InlineKeyboardButton(f"{monster['name']} (ур. {monster['level']})", callback_data=f'fight_{monster_idx}')])
        keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data='battle_menu'), InlineKeyboardButton("🏃 В деревню", callback_data='goto_town')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='main_menu')])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def goto_location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    loc_id = query.data.replace('goto_', '')
    if loc_id not in LOCATIONS: return
    loc = LOCATIONS[loc_id]
    player = db.get_player(user_id)
    if loc.get('level_req', 0) > player['level']:
        await query.answer(f"❌ Требуется уровень {loc['level_req']}!"); return
    db.update_player(user_id, location=loc_id)
    await query.edit_message_text(f"🗺️ *Перемещение...*\n\nПрибыл в {loc['name']}", parse_mode='Markdown')
    await asyncio.sleep(1)
    await battle_menu_callback(update, context)

async def fight_monster_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    monster_idx = int(query.data.replace('fight_', ''))
    monster_template = MONSTERS[monster_idx]
    player = db.get_player(user_id)
    stats = get_stats_with_equipment(player)
    monster = {'name': monster_template['name'], 'hp': monster_template['hp'], 'atk': monster_template['atk'],
               'exp': monster_template['exp'], 'gold': monster_template['gold'], 'drop': monster_template['drop']}
    battle_log = f"⚔️ *БОЙ!*\n\nТы vs {monster['name']}\n\n"
    player_hp = player['hp']
    round_num = 0
    is_first_attack = stats['stealth'] > 0
    
    while player_hp > 0 and monster['hp'] > 0 and round_num < 50:
        round_num += 1
        if player['class'] == 'rogue' and stats['evasion'] > 0 and random.random() < (stats['evasion'] / 100):
            battle_log += "💨 Уклонился!\n"; continue
        
        dmg = max(1, stats['atk'] - monster['atk'] // 2)
        is_crit = random.randint(1, 100) <= stats['crit']
        if is_crit: dmg = int(dmg * 1.5)
        if is_first_attack and stats['stealth'] > 0:
            dmg *= 2
            battle_log += f"🌑 Скрытность! "
        is_first_attack = False
        
        is_double = False
        if player['class'] == 'rogue' and stats['agility'] > 0 and random.random() < (stats['agility'] * 0.02):
            is_double = True
        
        monster['hp'] -= dmg
        battle_log += f"🗡️ Нанёс {dmg} урона{' 💥КРИТ!' if is_crit else ''}{' ⚡x2!' if is_double else ''}\n"
        if is_double:
            monster['hp'] -= dmg
            battle_log += f"🗡️ Ещё {dmg} урона\n"
        if monster['hp'] <= 0: break
        
        monster_dmg = max(1, monster['atk'] - stats['defense'] // 2)
        if player['class'] == 'paladin' and stats['magic_resist'] > 0:
            monster_dmg = int(monster_dmg * (1 - stats['magic_resist'] / 200))
        player_hp -= monster_dmg
        
        heal_amount = 0
        if player['class'] == 'paladin' and stats['self_heal'] > 0:
            heal_amount = int(stats['self_heal'] * 10 * (1 + stats['faith'] * 0.05))
            actual_heal = min(heal_amount, stats['hp_max'] - player_hp)
            if actual_heal > 0:
                player_hp += actual_heal
                battle_log += f"💚 Самоисцеление: +{actual_heal} HP\n"
        
        battle_log += f"💔 {monster['name']} нанёс {monster_dmg} урона | HP: {max(0, player_hp)}/{stats['hp_max']}\n"
        
        if player['class'] == 'warrior':
            rage_gain = int(monster_dmg / 5)
            new_rage = min(stats['max_rage'], stats['rage'] + rage_gain)
            db.update_player(user_id, rage=new_rage)
            stats['rage'] = new_rage
            battle_log += f"🔥 Гнев: {new_rage}/{stats['max_rage']}\n"
        
        if player['class'] == 'rogue':
            new_energy = min(stats['max_energy'], stats['energy'] + 5)
            db.update_player(user_id, energy=new_energy)
            stats['energy'] = new_energy
        
        if player['class'] == 'paladin':
            new_holy = min(stats['max_holy_power'], stats['holy_power'] + 10)
            db.update_player(user_id, holy_power=new_holy)
            stats['holy_power'] = new_holy
    
    if player_hp <= 0:
        db.update_player(user_id, hp=1, deaths=player['deaths'] + 1, location='town', rage=0, energy=100, holy_power=50)
        await query.edit_message_text(battle_log + f"\n💀 *Поражение...*\n\nHP восстановлено до 1.", parse_mode='Markdown')
    else:
        exp_gain = monster['exp']; gold_gain = monster['gold']
        new_exp = player['exp'] + exp_gain; new_level = player['level']; new_exp_max = player['exp_max']
        level_up = False
        while new_exp >= new_exp_max:
            new_exp -= new_exp_max; new_level += 1; new_exp_max = get_level_up_exp(new_level); level_up = True
        updates = {'hp': max(1, player_hp), 'exp': new_exp, 'exp_max': new_exp_max, 'level': new_level,
                   'gold': player['gold'] + gold_gain, 'wins': player['wins'] + 1}
        if level_up:
            updates['hp_max'] = player['hp_max'] + 10; updates['atk'] = player['atk'] + 2; updates['defense'] = player['defense'] + 1
        db.update_player(user_id, **updates)
        drop_text = ""
        if monster['drop'] and random.random() < 0.3:
            drop_item = random.choice(monster['drop'])
            db.add_item(user_id, drop_item)
            drop_text = f"\n🎁 *Добыча:* {ITEMS[drop_item]['name']}"
        result = battle_log + f"\n🏆 *ПОБЕДА!*\n\n⭐ {exp_gain} опыта\n🪙 {gold_gain} золота{drop_text}"
        if level_up: result += f"\n\n🎉 *НОВЫЙ УРОВЕНЬ {new_level}!*"
        await query.edit_message_text(result, parse_mode='Markdown')

async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    player = db.get_player(user_id)
    categories = {'weapon': '⚔️ Оружие', 'armor': '🛡️ Броня', 'accessory': '💍 Аксессуары', 'consumable': '💊 Зелья'}
    keyboard = [[InlineKeyboardButton(name, callback_data=f'shop_{cat_id}')] for cat_id, name in categories.items()]
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='main_menu')])
    await query.edit_message_text(f"🏪 *Магазин*\n\n💰 Баланс: {player['gold']} золота\n\nКатегория:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def shop_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    player = db.get_player(user_id)
    category = query.data.replace('shop_', '')
    items_in_cat = {k: v for k, v in ITEMS.items() if v['type'] == category}
    keyboard = []
    text = f"🏪 *{category.upper()}*\n💰 {player['gold']} золота\n\n"
    for item_id, item in items_in_cat.items():
        can = "✅" if player['gold'] >= item['price'] else "❌"
        text += f"{can} {item['name']} — {item['price']}🪙\n"
        keyboard.append([InlineKeyboardButton(f"Купить {item['name']}", callback_data=f'buy_{item_id}')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='shop')])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def buy_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    item_id = query.data.replace('buy_', '')
    if item_id not in ITEMS: return
    item = ITEMS[item_id]
    player = db.get_player(user_id)
    if player['gold'] < item['price']:
        await query.answer("❌ Недостаточно золота!"); return
    db.update_player(user_id, gold=player['gold'] - item['price'])
    db.add_item(user_id, item_id)
    await query.answer(f"✅ Куплено: {item['name']}")
    await shop_category_callback(update, context)

async def daily_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    player = db.get_player(user_id)
    now = datetime.now()
    last_daily = player.get('last_daily')
    if last_daily:
        last = datetime.fromisoformat(last_daily)
        if (now - last) < timedelta(hours=24):
            remaining = timedelta(hours=24) - (now - last)
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            await query.edit_message_text(f"⏳ *Бонус уже получен!*\n\nСледующий через: {hours}ч {minutes}м", parse_mode='Markdown')
            return
    bonus_gold = 100 + (player['level'] * 10)
    bonus_exp = 50
    new_exp = player['exp'] + bonus_exp
    new_level = player['level']
    new_exp_max = player['exp_max']
    level_up = False
    while new_exp >= new_exp_max:
        new_exp -= new_exp_max; new_level += 1; new_exp_max = get_level_up_exp(new_level); level_up = True
    updates = {'gold': player['gold'] + bonus_gold, 'exp': new_exp, 'exp_max': new_exp_max, 'level': new_level, 'last_daily': now.isoformat()}
    if level_up:
        updates['hp_max'] = player['hp_max'] + 10; updates['atk'] = player['atk'] + 2; updates['defense'] = player['defense'] + 1
    db.update_player(user_id, **updates)
    text = f"🎁 *Бонус получен!*\n\n💰 +{bonus_gold} золота\n⭐ +{bonus_exp} опыта"
    if level_up: text += f"\n\n🎉 *НОВЫЙ УРОВЕНЬ {new_level}!*"
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='main_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def top_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = sqlite3.connect("game.db")
    c = conn.cursor()
    c.execute('''SELECT name, level, exp, wins FROM players ORDER BY level DESC, exp DESC LIMIT 10''')
    top = c.fetchall()
    conn.close()
    text = "🏆 *ТОП ИГРОКОВ*\n\n"
    medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    for i, (name, level, exp, wins) in enumerate(top):
        text += f"{medals[i]} *{name}* — Ур. {level} | {exp} XP | {wins} побед\n"
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='main_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🎮 ИГРАТЬ", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📊 Профиль", callback_data='profile'), InlineKeyboardButton("🎒 Инвентарь", callback_data='inventory')],
        [InlineKeyboardButton("⚔️ Бой", callback_data='battle_menu'), InlineKeyboardButton("🗺️ Локации", callback_data='locations')],
        [InlineKeyboardButton("🏪 Магазин", callback_data='shop'), InlineKeyboardButton("🏆 Рейтинг", callback_data='top')],
        [InlineKeyboardButton("💰 Бонус", callback_data='daily')]
    ]
    await query.edit_message_text("⚔️ *LEGACY WARS*\n\nВыбери действие:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        action = data.get('action')
        if action == 'get_profile':
            user_id = update.effective_user.id
            player = db.get_player(user_id)
            if player:
                stats = get_stats_with_equipment(player)
                response = {'success': True, 'profile': {'name': player['name'], 'class': player['class'], 'level': player['level'],
                    'exp': player['exp'], 'exp_max': player['exp_max'], 'hp': player['hp'], 'hp_max': stats['hp_max'],
                    'atk': stats['atk'], 'def': stats['defense'], 'crit': stats['crit'], 'gold': player['gold'],
                    'endurance': stats['endurance'], 'impact': stats['impact'], 'rage': stats['rage'], 'max_rage': stats['max_rage'],
                    'mana': stats['mana'], 'max_mana': stats['max_mana'], 'spell_intensity': stats['spell_intensity'],
                    'agility': stats['agility'], 'evasion': stats['evasion'], 'stealth': stats['stealth'],
                    'faith': stats['faith'], 'aura_strength': stats['aura_strength'], 'self_heal': stats['self_heal'],
                    'magic_resist': stats['magic_resist'], 'holy_power': stats['holy_power'], 'max_holy_power': stats['max_holy_power']}}
            else: response = {'success': False, 'error': 'Player not found'}
            await update.effective_message.reply_text(json.dumps(response))
        else: await update.effective_message.reply_text(json.dumps({'ok': True}))
    except Exception as e:
        logger.error(f"WebApp data error: {e}")
        await update.effective_message.reply_text(json.dumps({'error': str(e)}))

def main():
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    create_conv = ConversationHandler(entry_points=[CallbackQueryHandler(create_char_callback, pattern='^create_char$')],
        states={ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)]}, fallbacks=[])
    app.add_handler(CommandHandler("start", start))
    app.add_handler(create_conv)
    app.add_handler(CallbackQueryHandler(profile_callback, pattern='^profile$'))
    app.add_handler(CallbackQueryHandler(inventory_callback, pattern='^inventory$'))
    app.add_handler(CallbackQueryHandler(equipment_callback, pattern='^equipment$'))
    app.add_handler(CallbackQueryHandler(equip_item_callback, pattern='^equip_'))
    app.add_handler(CallbackQueryHandler(use_item_callback, pattern='^use_item$'))
    app.add_handler(CallbackQueryHandler(use_consumable_callback, pattern='^use_'))
    app.add_handler(CallbackQueryHandler(battle_menu_callback, pattern='^battle_menu$'))
    app.add_handler(CallbackQueryHandler(goto_location_callback, pattern='^goto_'))
    app.add_handler(CallbackQueryHandler(fight_monster_callback, pattern='^fight_'))
    app.add_handler(CallbackQueryHandler(shop_callback, pattern='^shop$'))
    app.add_handler(CallbackQueryHandler(shop_category_callback, pattern='^shop_'))
    app.add_handler(CallbackQueryHandler(buy_item_callback, pattern='^buy_'))
    app.add_handler(CallbackQueryHandler(daily_callback, pattern='^daily$'))
    app.add_handler(CallbackQueryHandler(top_callback, pattern='^top$'))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern='^main_menu$'))
    app.add_handler(CallbackQueryHandler(select_class_callback, pattern='^class_'))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))
    print("✅ LEGACY WARS BOT ЗАПУЩЕН")
    print("⚔️ Воин: Выносливость, Сила удара, Гнев")
    print("🔮 Маг: Мана, Интенсивность магии, CDR")
    print("🗡️ Разбойник: Ловкость, Уклонение, Скрытность")
    print("🛡️ Паладин: Вера, Аура, Самоисцеление, Сопротивление магии")
    app.run_polling()

if __name__ == "__main__":
    main()