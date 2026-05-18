import requests
import time
from datetime import datetime

# Configuration
STARTING_BALANCE = 100.0
LEVERAGE = 4
TP_POINTS = 150
SL_POINTS = 75
CHECK_INTERVAL = 60  # Check every 60 seconds

# Trading State
balance = STARTING_BALANCE
trades = []
current_position = None
price_history = []

def get_btc_price():
    try:
        response = requests.get('https://api.kraken.com/0/public/Ticker?pair=XBTUSD')
        data = response.json()
        price = float(data['result']['XXBTZUSD']['c'][0])
        return price
    except:
        print("Error fetching price")
        return None

def calculate_ema(prices, period=200):
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema

def detect_ut_bot_signal(prices, key_value=1, atr_period=10):
    if len(prices) < atr_period + 2:
        return None
    
    # Calculate ATR
    atr = sum([abs(prices[i] - prices[i-1]) 
               for i in range(-atr_period, 0)]) / atr_period
    
    trailing_stop = prices[-2] - (key_value * atr)
    
    prev_price = prices[-2]
    curr_price = prices[-1]
    
    # Buy signal
    if curr_price > trailing_stop and prev_price <= trailing_stop:
        return 'buy'
    # Sell signal
    elif curr_price < trailing_stop and prev_price >= trailing_stop:
        return 'sell'
    
    return None

def calculate_pnl(entry, exit_price, direction):
    if direction == 'buy':
        return (exit_price - entry) / entry * (LEVERAGE * balance)
    else:
        return (entry - exit_price) / entry * (LEVERAGE * balance)

def check_position(current_price):
    global balance, current_position
    
    if not current_position:
        return
    
    entry = current_position['entry']
    direction = current_position['direction']
    tp = current_position['tp']
    sl = current_position['sl']
    result = None
    exit_price = None
    
    # Check TP
    if direction == 'buy' and current_price >= tp:
        result = 'TP'
        exit_price = tp
    elif direction == 'sell' and current_price <= tp:
        result = 'TP'
        exit_price = tp
    
    # Check SL
    elif direction == 'buy' and current_price <= sl:
        result = 'SL'
        exit_price = sl
    elif direction == 'sell' and current_price >= sl:
        result = 'SL'
        exit_price = sl
    
    if result:
        pnl = calculate_pnl(entry, exit_price, direction)
        balance += pnl
        
        trades.append({
            'number': len(trades) + 1,
            'direction': direction.upper(),
            'entry': entry,
            'exit': exit_price,
            'result': result,
            'pnl': round(pnl, 2),
            'balance': round(balance, 2),
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        print(f"\n{'='*40}")
        print(f"{'✅ WIN' if result == 'TP' else '❌ LOSS'} - {direction.upper()}")
        print(f"Entry: ${entry:,.1f} → Exit: ${exit_price:,.1f}")
        print(f"PnL: ${pnl:.2f}")
        print(f"Balance: ${balance:.2f}")
        print(f"Total Trades: {len(trades)}")
        wins = len([t for t in trades if t['pnl'] > 0])
        print(f"Win Rate: {wins/len(trades)*100:.1f}%")
        print(f"{'='*40}")
        
        current_position = None

def open_position(signal, price, ema):
    global current_position
    
    # EMA Filter
    if signal == 'buy' and price < ema:
        print(f"⚠️ Skipping BUY - price below 200 EMA")
        return
    if signal == 'sell' and price > ema:
        print(f"⚠️ Skipping SELL - price above 200 EMA")
        return
    
    tp = price + TP_POINTS if signal == 'buy' else price - TP_POINTS
    sl = price - SL_POINTS if signal == 'buy' else price + SL_POINTS
    
    current_position = {
        'direction': signal,
        'entry': price,
        'tp': tp,
        'sl': sl,
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    print(f"\n{'='*40}")
    print(f"🚀 NEW {signal.upper()} POSITION")
    print(f"Entry: ${price:,.1f}")
    print(f"TP: ${tp:,.1f} (+{TP_POINTS} pts)")
    print(f"SL: ${sl:,.1f} (-{SL_POINTS} pts)")
    print(f"EMA: ${ema:,.1f}")
    print(f"Balance: ${balance:.2f}")
    print(f"{'='*40}")

def print_stats():
    wins = len([t for t in trades if t['pnl'] > 0])
    losses = len([t for t in trades if t['pnl'] <= 0])
    total_pnl = sum(t['pnl'] for t in trades)
    win_rate = (wins / len(trades) * 100) if trades else 0
    
    print(f"\n📊 STATS")
    print(f"Balance: ${balance:.2f}")
    print(f"Total PnL: ${total_pnl:.2f}")
    print(f"Trades: {len(trades)} ({wins}W/{losses}L)")
    print(f"Win Rate: {win_rate:.1f}%")

def run_bot():
    global price_history
    
    print("🤖 Trading Bot Started!")
    print(f"💰 Balance: ${STARTING_BALANCE}")
    print(f"📈 TP: {TP_POINTS} pts | SL: {SL_POINTS} pts")
    print(f"⏱️ Checking every {CHECK_INTERVAL} seconds")
    print("="*40)
    
    last_signal = None
    check_count = 0
    
    while True:
        try:
            price = get_btc_price()
            if not price:
                time.sleep(CHECK_INTERVAL)
                continue
            
            price_history.append(price)
            
            # Keep last 300 prices
            if len(price_history) > 300:
                price_history = price_history[-300:]
            
            ema = calculate_ema(price_history)
            check_count += 1
            
            # Print status every 10 checks
            if check_count % 10 == 0:
                print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')} | Price: ${price:,.1f} | EMA: ${ema:,.1f if ema else 'Building...'}")
                if current_position:
                    print(f"📍 Open {current_position['direction'].upper()} from ${current_position['entry']:,.1f}")
                print_stats()
            
            # Check existing position
            check_position(price)
            
            # Look for new signal only if no position open
            if not current_position and ema:
                signal = detect_ut_bot_signal(price_history)
                
                if signal and signal != last_signal:
                    open_position(signal, price, ema)
                    last_signal = signal
            
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    run_bot()