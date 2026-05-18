import requests
import time
from datetime import datetime

# Configuration
STARTING_BALANCE = 100.0
LEVERAGE = 4
TP_POINTS = 150
SL_POINTS = 75

# Trading State
balance = STARTING_BALANCE
trades = []
current_position = None

def get_15min_candles():
    try:
        response = requests.get(
            'https://api.kraken.com/0/public/OHLC',
            params={
                'pair': 'XBTUSD',
                'interval': 15
            }
        )
        data = response.json()
        candles = data['result']['XXBTZUSD']
        closes = [float(c[4]) for c in candles]
        return closes
    except Exception as e:
        print(f"Error fetching candles: {e}")
        return None

def calculate_ema(prices, period=200):
    if len(prices) < period:
        print(f"⏳ Building EMA... {len(prices)}/{period} candles")
        return None
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema

def detect_signal(closes, key_value=1, atr_period=10):
    if len(closes) < atr_period + 2:
        return None
    
    # Calculate ATR
    atr = sum([abs(closes[i] - closes[i-1]) 
               for i in range(-atr_period, 0)]) / atr_period
    
    nLoss = key_value * atr
    
    prev_close = closes[-2]
    curr_close = closes[-1]
    prev_stop = closes[-3] - nLoss
    
    # Buy signal
    if curr_close > prev_stop and prev_close <= prev_stop:
        return 'buy'
    # Sell signal  
    elif curr_close < prev_stop and prev_close >= prev_stop:
        return 'sell'
    
    return None

def calculate_pnl(entry, exit_price, direction):
    if direction == 'buy':
        return (exit_price - entry) / entry * (LEVERAGE * STARTING_BALANCE)
    else:
        return (entry - exit_price) / entry * (LEVERAGE * STARTING_BALANCE)

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
    
    if direction == 'buy' and current_price >= tp:
        result = 'TP'
        exit_price = tp
    elif direction == 'sell' and current_price <= tp:
        result = 'TP'
        exit_price = tp
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
        
        wins = len([t for t in trades if t['pnl'] > 0])
        
        print(f"\n{'='*40}")
        print(f"{'✅ WIN' if result == 'TP' else '❌ LOSS'} - {direction.upper()}")
        print(f"Entry: ${entry:,.1f} → Exit: ${exit_price:,.1f}")
        print(f"PnL: ${pnl:.2f}")
        print(f"Balance: ${balance:.2f}")
        print(f"Trades: {len(trades)} | Wins: {wins} | Win Rate: {wins/len(trades)*100:.1f}%")
        print(f"{'='*40}")
        
        current_position = None

def open_position(signal, price, ema):
    global current_position
    
    if signal == 'buy' and price < ema:
        print(f"⚠️ Skip BUY — price ${price:,.1f} below EMA ${ema:,.1f}")
        return
    if signal == 'sell' and price > ema:
        print(f"⚠️ Skip SELL — price ${price:,.1f} above EMA ${ema:,.1f}")
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
    print(f"EMA 200: ${ema:,.1f}")
    print(f"Balance: ${balance:.2f}")
    print(f"{'='*40}")

def print_stats():
    wins = len([t for t in trades if t['pnl'] > 0])
    losses = len([t for t in trades if t['pnl'] <= 0])
    total_pnl = sum(t['pnl'] for t in trades)
    win_rate = (wins / len(trades) * 100) if trades else 0
    
    print(f"\n📊 STATS | Balance: ${balance:.2f} | PnL: ${total_pnl:.2f} | Trades: {len(trades)} ({wins}W/{losses}L) | Win Rate: {win_rate:.1f}%")

def run_bot():
    print("🤖 Bot Started!")
    print(f"💰 Balance: ${STARTING_BALANCE} | Leverage: {LEVERAGE}x")
    print(f"🎯 TP: {TP_POINTS} pts | SL: {SL_POINTS} pts")
    print(f"📊 Timeframe: 15 min candles")
    print("="*40)
    
    last_signal = None
    last_candle_time = None
    
    while True:
        try:
            closes = get_15min_candles()
            if not closes:
                time.sleep(60)
                continue
            
            current_price = closes[-1]
            ema = calculate_ema(closes)
            
            now = datetime.now().strftime('%H:%M:%S')
            
            if ema:
                trend = "📈 UPTREND" if current_price > ema else "📉 DOWNTREND"
                print(f"\n⏰ {now} | Price: ${current_price:,.1f} | EMA: ${ema:,.1f} | {trend}")
                
                # Check existing position
                check_position(current_price)
                
                # Look for new signal
                if not current_position:
                    signal = detect_signal(closes)
                    
                    if signal and signal != last_signal:
                        print(f"🔔 Signal detected: {signal.upper()}")
                        open_position(signal, current_price, ema)
                        last_signal = signal
                    else:
                        print(f"👀 Watching... No new signal")
                else:
                    print(f"📍 Position open: {current_position['direction'].upper()} from ${current_position['entry']:,.1f} | TP: ${current_position['tp']:,.1f} | SL: ${current_position['sl']:,.1f}")
                
                print_stats()
            
            # Wait for next 15 min candle
            time.sleep(900)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    run_bot()