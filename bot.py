from flask import Flask, request, jsonify
from datetime import datetime
import requests

app = Flask(__name__)

# Configuration
STARTING_BALANCE = 100.0
LEVERAGE = 4
TP_POINTS = 150
SL_POINTS = 75
EMA_PERIOD = 200

# Trading State
balance = STARTING_BALANCE
trades = []
current_position = None
price_history = []
ema_ready = False

def fetch_historical_candles():
    """Fetch 200 historical 15min candles from Kraken on startup"""
    try:
        print("📥 Fetching 200 historical candles from Kraken...")
        response = requests.get(
            'https://api.kraken.com/0/public/OHLC',
            params={
                'pair': 'XBTUSD',
                'interval': 15
            }
        )
        data = response.json()
        candles = data['result']['XXBTZUSD']
        closes = [float(c[4]) for c in candles[-200:]]
        print(f"✅ Loaded {len(closes)} historical candles!")
        return closes
    except Exception as e:
        print(f"❌ Error fetching historical data: {e}")
        return []

def calculate_ema(prices, period=200):
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_pnl(entry, exit_price, direction):
    if direction == 'buy':
        return (exit_price - entry) / entry * (LEVERAGE * STARTING_BALANCE)
    else:
        return (entry - exit_price) / entry * (LEVERAGE * STARTING_BALANCE)

def print_stats():
    wins = len([t for t in trades if t['pnl'] > 0])
    losses = len([t for t in trades if t['pnl'] <= 0])
    total_pnl = sum(t['pnl'] for t in trades)
    win_rate = (wins / len(trades) * 100) if trades else 0
    print(f"\n📊 STATS | Balance: ${balance:.2f} | PnL: ${total_pnl:.2f} | Trades: {len(trades)} ({wins}W/{losses}L) | Win Rate: {win_rate:.1f}%")

# Load historical data on startup
price_history = fetch_historical_candles()
ema_ready = len(price_history) >= EMA_PERIOD

if ema_ready:
    current_ema = calculate_ema(price_history)
    print(f"✅ EMA Ready! Current EMA: ${current_ema:,.1f}")
else:
    print(f"⚠️ Only {len(price_history)} candles loaded — need {EMA_PERIOD}")

@app.route('/webhook', methods=['POST'])
def webhook():
    global balance, current_position, price_history, ema_ready

    data = request.json
    signal = data.get('signal', '').lower()
    price = float(data.get('price', 0))

    print(f"\n🔔 Signal received: {signal.upper()} at ${price:,.1f}")

    # Add price to history
    price_history.append(price)
    if len(price_history) > 300:
        price_history = price_history[-300:]

    # Calculate EMA
    ema = calculate_ema(price_history)

    if not ema:
        print(f"⏳ Building EMA... {len(price_history)}/{EMA_PERIOD} prices")
        return jsonify({'status': 'building EMA'})

    ema_ready = True
    trend = "📈 UPTREND" if price > ema else "📉 DOWNTREND"
    print(f"💹 Price: ${price:,.1f} | EMA: ${ema:,.1f} | {trend}")

    # Check existing position
    if current_position:
        entry = current_position['entry']
        direction = current_position['direction']
        tp = current_position['tp']
        sl = current_position['sl']

        # Check TP
        if direction == 'buy' and price >= tp:
            pnl = calculate_pnl(entry, tp, direction)
            balance += pnl
            trades.append({
                'number': len(trades) + 1,
                'direction': direction.upper(),
                'entry': entry,
                'exit': tp,
                'result': 'TP',
                'pnl': round(pnl, 2),
                'balance': round(balance, 2),
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            print(f"\n✅ WIN - BUY TP HIT!")
            print(f"Entry: ${entry:,.1f} → Exit: ${tp:,.1f}")
            print(f"PnL: +${pnl:.2f} | Balance: ${balance:.2f}")
            print_stats()
            current_position = None

        elif direction == 'sell' and price <= tp:
            pnl = calculate_pnl(entry, tp, direction)
            balance += pnl
            trades.append({
                'number': len(trades) + 1,
                'direction': direction.upper(),
                'entry': entry,
                'exit': tp,
                'result': 'TP',
                'pnl': round(pnl, 2),
                'balance': round(balance, 2),
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            print(f"\n✅ WIN - SELL TP HIT!")
            print(f"Entry: ${entry:,.1f} → Exit: ${tp:,.1f}")
            print(f"PnL: +${pnl:.2f} | Balance: ${balance:.2f}")
            print_stats()
            current_position = None

        elif direction == 'buy' and price <= sl:
            pnl = calculate_pnl(entry, sl, direction)
            balance += pnl
            trades.append({
                'number': len(trades) + 1,
                'direction': direction.upper(),
                'entry': entry,
                'exit': sl,
                'result': 'SL',
                'pnl': round(pnl, 2),
                'balance': round(balance, 2),
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            print(f"\n❌ LOSS - BUY SL HIT!")
            print(f"Entry: ${entry:,.1f} → Exit: ${sl:,.1f}")
            print(f"PnL: ${pnl:.2f} | Balance: ${balance:.2f}")
            print_stats()
            current_position = None

        elif direction == 'sell' and price >= sl:
            pnl = calculate_pnl(entry, sl, direction)
            balance += pnl
            trades.append({
                'number': len(trades) + 1,
                'direction': direction.upper(),
                'entry': entry,
                'exit': sl,
                'result': 'SL',
                'pnl': round(pnl, 2),
                'balance': round(balance, 2),
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            print(f"\n❌ LOSS - SELL SL HIT!")
            print(f"Entry: ${entry:,.1f} → Exit: ${sl:,.1f}")
            print(f"PnL: ${pnl:.2f} | Balance: ${balance:.2f}")
            print_stats()
            current_position = None

        elif signal != current_position['direction']:
            pnl = calculate_pnl(entry, price, direction)
            balance += pnl
            result = 'WIN' if pnl > 0 else 'LOSS'
            trades.append({
                'number': len(trades) + 1,
                'direction': direction.upper(),
                'entry': entry,
                'exit': price,
                'result': f'Closed by opposite signal ({result})',
                'pnl': round(pnl, 2),
                'balance': round(balance, 2),
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            print(f"\n{'✅' if pnl > 0 else '❌'} Closed by opposite signal")
            print(f"Entry: ${entry:,.1f} → Exit: ${price:,.1f}")
            print(f"PnL: ${pnl:.2f} | Balance: ${balance:.2f}")
            print_stats()
            current_position = None

    # Open new position
    if not current_position:
        if signal == 'buy' and price < ema:
            print(f"⚠️ Skip BUY — price below EMA")
            return jsonify({'status': 'skipped - below EMA'})
        if signal == 'sell' and price > ema:
            print(f"⚠️ Skip SELL — price above EMA")
            return jsonify({'status': 'skipped - above EMA'})

        tp = price + TP_POINTS if signal == 'buy' else price - TP_POINTS
        sl = price - SL_POINTS if signal == 'buy' else price + SL_POINTS

        current_position = {
            'direction': signal,
            'entry': price,
            'tp': tp,
            'sl': sl,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        print(f"\n🚀 NEW {signal.upper()} POSITION")
        print(f"Entry: ${price:,.1f}")
        print(f"TP: ${tp:,.1f} (+{TP_POINTS} pts)")
        print(f"SL: ${sl:,.1f} (-{SL_POINTS} pts)")
        print(f"EMA 200: ${ema:,.1f}")
        print(f"Balance: ${balance:.2f}")

    return jsonify({
        'status': 'success',
        'position': current_position,
        'balance': round(balance, 2)
    })

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

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'Bot is running!', 'ema_ready': ema_ready, 'balance': round(balance, 2)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)