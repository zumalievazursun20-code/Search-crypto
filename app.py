from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from mnemonic import Mnemonic
from eth_account import Account
from web3 import Web3
import threading
import time
import json
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app)

# Настройки
BIP39_WORDS = 12
RPC_URLS = [
    'https://bsc-dataseed.binance.org/',
    'https://bsc-dataseed1.defibit.io/',
    'https://bsc-dataseed1.ninicoin.io/'
]
THREADS = 5
found_wallets = []
is_running = False
total_checked = 0
executor = None
future_tasks = []

Account.enable_unaudited_hdwallet_features()

def generate_mnemonic():
    mnemo = Mnemonic('english')
    return mnemo.generate(strength=128 if BIP39_WORDS == 12 else 256)

def mnemonic_to_address(mnemonic):
    account = Account.from_mnemonic(mnemonic)
    return account.address, account.key.hex()

def get_balance(address):
    w3 = Web3(Web3.HTTPProvider(RPC_URLS[0], request_kwargs={'timeout': 3}))
    try:
        balance_wei = w3.eth.get_balance(address)
        return float(w3.from_wei(balance_wei, 'ether'))
    except:
        return -1

def check_wallet():
    global total_checked, found_wallets
    while is_running:
        try:
            mnemonic = generate_mnemonic()
            address, private_key = mnemonic_to_address(mnemonic)
            total_checked += 1
            
            # Проверяем баланс
            balance = get_balance(address)
            
            if balance > 0:
                wallet_data = {
                    'mnemonic': mnemonic,
                    'address': address,
                    'private_key': private_key,
                    'balance': round(balance, 6)
                }
                found_wallets.append(wallet_data)
                print(f"[+] Найден кошелёк! {address} - {balance} BNB")
                
                # Сохраняем в файл
                with open('found_wallets.json', 'a') as f:
                    f.write(json.dumps(wallet_data) + '\n')
            
            # Статистика каждые 10 проверок
            if total_checked % 10 == 0:
                print(f"[*] Проверено: {total_checked} | Найдено: {len(found_wallets)}")
                
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(0.1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_scan():
    global is_running, executor, future_tasks
    if is_running:
        return jsonify({'status': 'already_running'})
    
    is_running = True
    executor = ThreadPoolExecutor(max_workers=THREADS)
    future_tasks = []
    
    for _ in range(THREADS):
        future = executor.submit(check_wallet)
        future_tasks.append(future)
    
    return jsonify({'status': 'started'})

@app.route('/stop', methods=['POST'])
def stop_scan():
    global is_running
    is_running = False
    if executor:
        executor.shutdown(wait=False)
    return jsonify({'status': 'stopped'})

@app.route('/status')
def status():
    return jsonify({
        'is_running': is_running,
        'total_checked': total_checked,
        'found_wallets': found_wallets[-10:],  # последние 10
        'total_found': len(found_wallets)
    })

@app.route('/wallets')
def get_wallets():
    return jsonify(found_wallets)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
