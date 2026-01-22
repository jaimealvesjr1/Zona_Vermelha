import json
import os
import uuid
import random
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(BASE_DIR, 'players.json')
GAME_FILE = os.path.join(BASE_DIR, 'gamestate.json')

# --- CONFIGURAÇÃO ---
SPECIALIZATIONS = {
    'socorrista': {'name': 'Socorrista', 'bonus': {'int': 2, 'vig': -1}},
    'mecanico': {'name': 'Mecânico', 'bonus': {'int': 2, 'pre': -1}},
    'cacador': {'name': 'Caçador', 'bonus': {'per': 2, 'pre': -1}},
    'lutador': {'name': 'Lutador', 'bonus': {'vig': 2, 'int': -1}},
    'atleta': {'name': 'Atleta', 'bonus': {'agi': 2, 'per': -1}},
    'dancarino': {'name': 'Dançarino', 'bonus': {'agi': 2, 'vig': -1}},
    'pastor': {'name': 'Pastor', 'bonus': {'pre': 2, 'agi': -1}},
    'nativo': {'name': 'Nativo', 'bonus': {'per': 2, 'int': -1}},
    'guarda': {'name': 'Guarda', 'bonus': {'pre': 2, 'per': -1}},
    'vendedor': {'name': 'Vendedor', 'bonus': {'pre': 2, 'per': -1}},
    'farmaceutico': {'name': 'Farmacêutico', 'bonus': {'int': 2, 'agi': -1}}
}

# --- PERSISTÊNCIA JOGADORES ---
def load_data():
    if not os.path.exists(DATA_FILE): return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)

def get_player(pid, players):
    return next((p for p in players if p['id'] == pid), None)

# --- PERSISTÊNCIA GAME STATE (NOVO) ---
def load_gamestate():
    default_state = {
        'location': 'DESCONHECIDO',
        'time': '00:00',
        'notes': '',
        'doom_clock': 0,
        'doom_max': 12,
        'dm_last_roll': None,     # <--- NOVO
        'dm_last_die': None       # <--- NOVO
    }
    if not os.path.exists(GAME_FILE):
        return default_state
    with open(GAME_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return {**default_state, **data}

def save_gamestate(data):
    with open(GAME_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)

# --- CÁLCULOS ---
def calculate_stats(attributes, specs_ids):
    final = attributes.copy()
    for spec_id in specs_ids:
        if spec_id in SPECIALIZATIONS:
            bonuses = SPECIALIZATIONS[spec_id]['bonus']
            for attr, val in bonuses.items():
                final[attr] = final.get(attr, 0) + val
    return {
        'pv_max': 10 + final['vig'], 'ps_max': 10 + final['pre'],
        'pa_max': 5, 'final_attrs': final
    }

# --- ROTAS PRINCIPAIS ---
@app.route('/')
def index():
    players = load_data()
    gamestate = load_gamestate() # <--- Carrega estado do jogo
    
    for p in players:
        # Patchs de compatibilidade
        if 'inventory' not in p: p['inventory'] = []
        if 'dice' not in p: p['dice'] = {'d4': None, 'd6': None, 'd12': None, 'd20': None}
        if 'level' not in p: p['level'] = 1
        
        p['stats'] = calculate_stats(p['attributes'], p['specs'])
        if 'current_pv' not in p: p['current_pv'] = p['stats']['pv_max']
        if 'current_ps' not in p: p['current_ps'] = p['stats']['ps_max']
        if 'current_pa' not in p: p['current_pa'] = 5
        
    return render_template('dashboard.html', players=players, specs=SPECIALIZATIONS, gamestate=gamestate)

# --- ROTAS DE GAME STATE (NOVAS) ---
@app.route('/gamestate/update', methods=['POST'])
def update_gamestate():
    state = load_gamestate()
    if 'location' in request.form: state['location'] = request.form['location'].upper()
    if 'time' in request.form: state['time'] = request.form['time']
    if 'notes' in request.form: state['notes'] = request.form['notes']
    save_gamestate(state)
    return "" # Retorna nada, pois o input já atualizou visualmente (ou usamos hx-swap="none")

@app.route('/gamestate/doom/<action>', methods=['POST'])
def update_doom(action):
    state = load_gamestate()
    if action == 'inc': state['doom_clock'] = min(state['doom_clock'] + 1, state['doom_max'])
    elif action == 'dec': state['doom_clock'] = max(state['doom_clock'] - 1, 0)
    elif action == 'reset': state['doom_clock'] = 0
    save_gamestate(state)
    return render_template('partials/doom_clock.html', gamestate=state)

# --- ROTAS DE JOGADOR (MANTIDAS IGUAIS) ---
@app.route('/add', methods=['POST'])
def add_player():
    data = request.form
    specs = request.form.getlist('specs')
    raw_attrs = {
        'vig': int(data.get('vig')), 'agi': int(data.get('agi')),
        'int': int(data.get('int')), 'per': int(data.get('per')),
        'pre': int(data.get('pre'))
    }
    if sum(raw_attrs.values()) > 10: return "Soma > 10", 400
    if len(specs) != 3: return "Specs != 3", 400
    stats = calculate_stats(raw_attrs, specs)
    new_player = {
        'id': str(uuid.uuid4()), 'name': data.get('name').upper(), 'age': data.get('age'),
        'attributes': raw_attrs, 'specs': specs, 'inventory': [],
        'dice': {'d4': None, 'd6': None, 'd12': None, 'd20': None}, 'level': 1,
        'current_pv': stats['pv_max'], 'current_ps': stats['ps_max'], 'current_pa': 5
    }
    players = load_data()
    players.append(new_player)
    save_data(players)
    return redirect(url_for('index'))

@app.route('/delete/<pid>', methods=['DELETE'])
def delete_player(pid):
    players = load_data()
    save_data([p for p in players if p['id'] != pid])
    return ""

@app.route('/update_stat/<pid>/<stat>/<action>', methods=['POST'])
def update_stat(pid, stat, action):
    players = load_data()
    player = get_player(pid, players)
    if not player: return "", 404
    stats = calculate_stats(player['attributes'], player['specs'])
    max_val = stats['pv_max'] if stat == 'current_pv' else (stats['ps_max'] if stat == 'current_ps' else 5)
    if action == 'inc': player[stat] = min(player.get(stat, max_val) + 1, max_val)
    elif action == 'dec': player[stat] = max(player.get(stat, 0) - 1, 0)
    save_data(players)
    player['stats'] = stats
    return render_template('partials/player_card.html', player=player, specs=SPECIALIZATIONS)

@app.route('/level/<pid>/<action>', methods=['POST'])
def update_level(pid, action):
    players = load_data()
    player = get_player(pid, players)
    current = player.get('level', 1)
    if action == 'inc': player['level'] = min(current + 1, 20)
    elif action == 'dec': player['level'] = max(current - 1, 1)
    save_data(players)
    player['stats'] = calculate_stats(player['attributes'], player['specs'])
    return render_template('partials/player_card.html', player=player, specs=SPECIALIZATIONS)

@app.route('/inventory/add/<pid>', methods=['POST'])
def add_item(pid):
    item_name = request.form.get('item_name')
    if not item_name: return "", 400
    players = load_data()
    player = get_player(pid, players)
    player['inventory'].append({'id': str(uuid.uuid4()), 'name': item_name.upper(), 'qty': 1})
    save_data(players)
    player['stats'] = calculate_stats(player['attributes'], player['specs'])
    return render_template('partials/player_card.html', player=player, specs=SPECIALIZATIONS)

@app.route('/inventory/update/<pid>/<item_id>/<action>', methods=['POST'])
def update_item(pid, item_id, action):
    players = load_data()
    player = get_player(pid, players)
    for item in player['inventory']:
        if item['id'] == item_id:
            if action == 'inc': item['qty'] += 1
            elif action == 'dec': item['qty'] = max(0, item['qty'] - 1)
            break
    save_data(players)
    player['stats'] = calculate_stats(player['attributes'], player['specs'])
    return render_template('partials/player_card.html', player=player, specs=SPECIALIZATIONS)

@app.route('/inventory/delete/<pid>/<item_id>', methods=['DELETE'])
def delete_item(pid, item_id):
    players = load_data()
    player = get_player(pid, players)
    player['inventory'] = [i for i in player['inventory'] if i['id'] != item_id]
    save_data(players)
    player['stats'] = calculate_stats(player['attributes'], player['specs'])
    return render_template('partials/player_card.html', player=player, specs=SPECIALIZATIONS)

@app.route('/inventory/reorder/<pid>/<item_id>/<direction>', methods=['POST'])
def reorder_item(pid, item_id, direction):
    players = load_data()
    player = get_player(pid, players)
    inv = player['inventory']
    index = next((i for i, item in enumerate(inv) if item['id'] == item_id), None)
    if index is not None:
        if direction == 'up' and index > 0: inv[index], inv[index-1] = inv[index-1], inv[index]
        elif direction == 'down' and index < len(inv) - 1: inv[index], inv[index+1] = inv[index+1], inv[index]
    save_data(players)
    player['stats'] = calculate_stats(player['attributes'], player['specs'])
    return render_template('partials/player_card.html', player=player, specs=SPECIALIZATIONS)

@app.route('/roll/<pid>/<die>', methods=['POST'])
def roll_die(pid, die):
    if die not in ['d4', 'd6', 'd12', 'd20']: return "", 400
    players = load_data()
    player = get_player(pid, players)
    faces = int(die[1:])
    result = random.randint(1, faces)
    if 'dice' not in player: player['dice'] = {}
    player['dice'][die] = result
    save_data(players)
    player['stats'] = calculate_stats(player['attributes'], player['specs'])
    return render_template('partials/player_card.html', player=player, specs=SPECIALIZATIONS)

@app.route('/gamestate/roll_dm/<die>', methods=['POST'])
def roll_dm_die(die):
    if die not in ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100']: return "", 400
    
    state = load_gamestate()
    faces = int(die[1:])
    result = random.randint(1, faces)
    
    state['dm_last_roll'] = result
    state['dm_last_die'] = die.upper()
    
    save_gamestate(state)
    return render_template('partials/dm_dice.html', gamestate=state)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
