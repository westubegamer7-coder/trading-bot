from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# Configuration
STARTING_BALANCE = 100.0
LEVERAGE = 4
TP_POINTS = 150
SL_POINTS = 75
EMA_200 = 78348  # Update this daily

# Trading State
balance = STARTING_BALANCE
trades = []
current_position = None

def calculate_pnl(entry, exit_price, direction):
    if direction == "buy":
        return (exit_price - entry) * (LEVERAGE * balance / entry)
    else:
        return (entry - exit_price) * (LEVERAGE * balance / entry)

@app.route('/webhook', methods=['POST'])
def webhook():
    global balance, current_position
    
    data = request.json
    signal = data.get('signal', '').lower()
    price = float(data.get('price', 0))
    
    # 200 EMA Filter
    if signal == 'buy' and price < EMA_200:
        return jsonify({
            'status': 'skipped',
            'reason': 'Price below 200 EMA - no buys allowed'
        })
    
    if signal == 'sell' and price > EMA_200:
        return jsonify({
            'status': 'skipped', 
            'reason': 'Price above 200 EMA - no sells allowed'
        })
    
    # Close existing position if opposite signal
    if current_position:
        entry = current_position['entry']
        direction = current_position['direction']
        
        if direction != signal:
            pnl = calculate_pnl(entry, price, direction)
            balance += pnl
            
            trades.append({
                'number': len(trades) + 1,
                'direction': direction.upper(),
                'entry': entry,
                'exit': price,
                'result': 'Closed by opposite signal',
                'pnl': round(pnl, 2),
                'balance': round(balance, 2),
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            current_position = None
    
    # Open new position
    if not current_position:
        tp_price = price + TP_POINTS if signal == 'buy' else price - TP_POINTS
        sl_price = price - SL_POINTS if signal == 'buy' else price + SL_POINTS
        
        current_position = {
            'direction': signal,
            'entry': price,
            'tp': tp_price,
            'sl': sl_price,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print(f"\n{'='*40}")
        print(f"NEW {signal.upper()} POSITION")
        print(f"Entry: ${price:,.1f}")
        print(f"TP: ${tp_price:,.1f}")
        print(f"SL: ${sl_price:,.1f}")
        print(f"Balance: ${balance:.2f}")
        print(f"{'='*40}")
    
    return jsonify({'status': 'success', 'position': current_position})

@app.route('/price', methods=['POST'])
def price_update():
    global balance, current_position
    
    if not current_position:
        return jsonify({'status': 'no position'})
    
    data = request.json
    current_price = float(data.get('price', 0))
    direction = current_position['direction']
    entry = current_position['entry']
    tp = current_position['tp']
    sl = current_position['sl']
    
    result = None
    
    # Check TP
    if direction == 'buy' and current_price >= tp:
        result = 'TP'
        pnl = calculate_pnl(entry, tp, direction)
    elif direction == 'sell' and current_price <= tp:
        result = 'TP'
        pnl = calculate_pnl(entry, tp, direction)
    
    # Check SL
    elif direction == 'buy' and current_price <= sl:
        result = 'SL'
        pnl = calculate_pnl(entry, sl, direction)
    elif direction == 'sell' and current_price >= sl:
        result = 'SL'
        pnl = calculate_pnl(entry, sl, direction)
    
    if result:
        balance += pnl
        trades.append({
            'number': len(trades) + 1,
            'direction': direction.upper(),
            'entry': entry,
            'exit': tp if result == 'TP' else sl,
            'result': result,
            'pnl': round(pnl, 2),
            'balance': round(balance, 2),
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        print(f"\n{'='*40}")
        print(f"{result} HIT - {direction.upper()}")
        print(f"Entry: ${entry:,.1f} → Exit: ${tp if result == 'TP' else sl:,.1f}")
        print(f"PnL: ${pnl:.2f}")
        print(f"Balance: ${balance:.2f}")
        print(f"{'='*40}")
        
        current_position = None
    
    return jsonify({'status': result or 'open', 'balance': round(balance, 2)})

@app.route('/stats', methods=['GET'])
def stats():
    wins = len([t for t in trades if t['pnl'] > 0])
    losses = len([t for t in trades if t['pnl'] <= 0])
    total_pnl = sum(t['pnl'] for t in trades)
    win_rate = (wins / len(trades) * 100) if trades else 0
    
    return jsonify({
        'starting_balance': STARTING_BALANCE,
        'current_balance': round(balance, 2),
        'total_profit': round(total_pnl, 2),
        'total_trades': len(trades),
        'wins': wins,
        'losses': losses,
        'win_rate': f"{win_rate:.1f}%",
        'trades': trades
    })

if __name__ == '__main__':
    app.run(port=5000)