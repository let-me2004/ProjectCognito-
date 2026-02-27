# web_dashboard.py - Trading Dashboard Web Server
# =================================================
# Run: python web_dashboard.py
# Open: http://localhost:5050

import json
import os
import csv
import datetime
import time as time_module
import threading
from flask import Flask, render_template_string, jsonify, request
import fyers_client
import config

app = Flask(__name__)

POSITION_FILES = {
    "Options Agent": "paper_positions_options.json",
    "Scalper Agent": "paper_positions_scalper.json",
    "Equity Agent": "paper_positions_equity.json",
}

TRADE_LOG = "trade_log.csv"


def load_positions(filename):
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_positions(filename, positions):
    with open(filename, "w") as f:
        json.dump(positions, f, indent=4)


def load_trade_log():
    if not os.path.exists(TRADE_LOG):
        return []
    try:
        with open(TRADE_LOG, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            return rows[-50:]  # Last 50 trades
    except Exception:
        return []


def _save_trade_log(trade_data):
    """Append a closed trade to trade_log.csv."""
    file_exists = os.path.exists(TRADE_LOG) and os.path.getsize(TRADE_LOG) > 0
    try:
        with open(TRADE_LOG, mode='a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "trade_id", "symbol", "status", "direction", "qty",
                    "entry_price", "exit_price", "entry_time", "exit_time",
                    "stop_loss", "take_profit", "pnl"
                ])
            writer.writerow([
                trade_data.get('id'), trade_data.get('symbol'), trade_data.get('status'),
                trade_data.get('direction'), trade_data.get('qty'), trade_data.get('entry_price'),
                trade_data.get('exit_price'), trade_data.get('entry_time'),
                trade_data.get('exit_time'), trade_data.get('stop_loss'),
                trade_data.get('take_profit'), trade_data.get('pnl')
            ])
    except Exception as e:
        print(f"[TRADE LOG] Failed to write: {e}")


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProjectCognito — Trading Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0e17;
            --bg-secondary: #111827;
            --bg-card: #1a2332;
            --bg-card-hover: #1f2b3d;
            --border: #2d3748;
            --text-primary: #f0f4f8;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-yellow: #f59e0b;
            --accent-purple: #8b5cf6;
            --glow-green: rgba(16, 185, 129, 0.15);
            --glow-red: rgba(239, 68, 68, 0.15);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }

        .header {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            border-bottom: 1px solid var(--border);
            padding: 16px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .header h1 {
            font-size: 22px;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }

        .header-info {
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .live-dot {
            width: 8px; height: 8px;
            background: var(--accent-green);
            border-radius: 50%;
            animation: pulse 2s infinite;
            display: inline-block;
            margin-right: 6px;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            50% { opacity: 0.7; box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
        }

        .container { max-width: 1400px; margin: 0 auto; padding: 24px 32px; }

        /* Summary Cards */
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 28px;
        }

        .summary-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            transition: all 0.2s;
        }

        .summary-card:hover {
            border-color: var(--accent-blue);
            transform: translateY(-2px);
        }

        .summary-card .label {
            font-size: 12px;
            font-weight: 500;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        .summary-card .value {
            font-size: 28px;
            font-weight: 700;
        }

        .summary-card .sub {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        .positive { color: var(--accent-green); }
        .negative { color: var(--accent-red); }

        /* Agent Sections */
        .agent-section {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            margin-bottom: 20px;
            overflow: hidden;
        }

        .agent-header {
            padding: 16px 20px;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .agent-header h2 {
            font-size: 16px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .agent-badge {
            font-size: 11px;
            padding: 3px 10px;
            border-radius: 20px;
            font-weight: 600;
        }

        .badge-options { background: rgba(59, 130, 246, 0.15); color: var(--accent-blue); }
        .badge-scalper { background: rgba(139, 92, 246, 0.15); color: var(--accent-purple); }
        .badge-equity { background: rgba(245, 158, 11, 0.15); color: var(--accent-yellow); }

        .position-count {
            font-size: 13px;
            color: var(--text-secondary);
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th {
            text-align: left;
            padding: 12px 20px;
            font-size: 11px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border);
        }

        td {
            padding: 14px 20px;
            font-size: 13px;
            border-bottom: 1px solid rgba(45, 55, 72, 0.5);
            font-variant-numeric: tabular-nums;
        }

        tr:hover td { background: var(--bg-card-hover); }

        .empty-state {
            padding: 40px;
            text-align: center;
            color: var(--text-muted);
            font-size: 14px;
        }

        /* Action Buttons */
        .actions-bar {
            display: flex;
            gap: 12px;
            margin-bottom: 28px;
        }

        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-family: 'Inter', sans-serif;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .btn-buy {
            background: linear-gradient(135deg, #059669, #10b981);
            color: white;
        }
        .btn-buy:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3); }

        .btn-sell {
            background: linear-gradient(135deg, #dc2626, #ef4444);
            color: white;
        }
        .btn-sell:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3); }

        .btn-refresh {
            background: var(--bg-card);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }
        .btn-refresh:hover { border-color: var(--accent-blue); }

        .btn-clear {
            background: transparent;
            color: var(--text-muted);
            border: 1px solid var(--border);
            margin-left: auto;
        }
        .btn-clear:hover { border-color: var(--accent-red); color: var(--accent-red); }

        .sell-btn-small {
            padding: 5px 14px;
            font-size: 11px;
            background: rgba(239, 68, 68, 0.15);
            color: var(--accent-red);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            font-family: 'Inter', sans-serif;
            transition: all 0.2s;
        }
        .sell-btn-small:hover { background: var(--accent-red); color: white; }

        /* Modal */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.7);
            backdrop-filter: blur(4px);
            z-index: 100;
            justify-content: center;
            align-items: center;
        }

        .modal-overlay.active { display: flex; }

        .modal {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 28px;
            width: 440px;
            max-width: 90vw;
        }

        .modal h3 {
            font-size: 18px;
            margin-bottom: 20px;
        }

        .form-group {
            margin-bottom: 14px;
        }

        .form-group label {
            display: block;
            font-size: 12px;
            font-weight: 500;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }

        .form-group input, .form-group select {
            width: 100%;
            padding: 10px 14px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text-primary);
            font-family: 'Inter', sans-serif;
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }

        .form-group input:focus, .form-group select:focus {
            border-color: var(--accent-blue);
        }

        .modal-actions {
            display: flex;
            gap: 10px;
            margin-top: 20px;
            justify-content: flex-end;
        }

        .btn-cancel {
            padding: 10px 20px;
            background: var(--bg-secondary);
            color: var(--text-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            cursor: pointer;
            font-family: 'Inter', sans-serif;
            font-weight: 500;
        }

        /* Trade Log */
        .trade-log-section { margin-top: 8px; }

        .trade-log-section h2 {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 16px;
            color: var(--text-primary);
        }

        .pnl-positive { color: var(--accent-green); font-weight: 600; }
        .pnl-negative { color: var(--accent-red); font-weight: 600; }

        /* Responsive */
        @media (max-width: 900px) {
            .summary-grid { grid-template-columns: repeat(2, 1fr); }
            .container { padding: 16px; }
        }

        @media (max-width: 600px) {
            .summary-grid { grid-template-columns: 1fr; }
        }

        /* Toast */
        .toast {
            position: fixed;
            bottom: 30px;
            right: 30px;
            padding: 14px 24px;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 500;
            z-index: 200;
            animation: slideIn 0.3s ease;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .toast-success { background: var(--accent-green); color: white; }
        .toast-error { background: var(--accent-red); color: white; }

        @keyframes slideIn {
            from { transform: translateX(100px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        /* Symbol autocomplete dropdown */
        .symbol-dropdown {
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            max-height: 220px;
            overflow-y: auto;
            background: var(--bg-secondary);
            border: 1px solid var(--accent-blue);
            border-top: none;
            border-radius: 0 0 8px 8px;
            z-index: 10;
        }
        .symbol-dropdown.active { display: block; }
        .symbol-option {
            padding: 10px 14px;
            font-size: 13px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid rgba(45,55,72,0.3);
        }
        .symbol-option:hover { background: var(--bg-card-hover); }
        .symbol-option .sym-name { font-weight: 600; color: var(--text-primary); }
        .symbol-option .sym-type-ce { color: var(--accent-green); font-size: 11px; font-weight: 600; }
        .symbol-option .sym-type-pe { color: var(--accent-red); font-size: 11px; font-weight: 600; }
    </style>
</head>
<body>
    <div class="header">
        <h1>⚡ ProjectCognito Dashboard</h1>
        <div class="header-info">
            <span style="color: var(--text-secondary); font-size: 13px;">
                <span class="live-dot"></span> Live
            </span>
            <span id="clock" style="color: var(--text-muted); font-size: 13px; font-variant-numeric: tabular-nums;"></span>
        </div>
    </div>

    <div class="container">
        <!-- Summary Cards -->
        <div class="summary-grid">
            <div class="summary-card">
                <div class="label">Open Positions</div>
                <div class="value" id="total-positions">0</div>
                <div class="sub">Across all agents</div>
            </div>
            <div class="summary-card">
                <div class="label">Active Agents</div>
                <div class="value" id="active-agents">0</div>
                <div class="sub">With open positions</div>
            </div>
            <div class="summary-card">
                <div class="label">Total Invested</div>
                <div class="value" id="total-invested">₹0</div>
                <div class="sub">Current exposure</div>
            </div>
            <div class="summary-card">
                <div class="label">Closed Trades Today</div>
                <div class="value" id="closed-today">0</div>
                <div class="sub">From trade log</div>
            </div>
        </div>

        <!-- Action Buttons -->
        <div class="actions-bar">
            <button class="btn btn-buy" onclick="openBuyModal()">＋ Manual Buy</button>
            <button class="btn btn-refresh" onclick="refreshData()">↻ Refresh</button>
            <button class="btn btn-clear" onclick="clearAll()">Clear All Positions</button>
        </div>

        <!-- Agent Positions -->
        <div id="positions-container"></div>

        <!-- Trade Log -->
        <div class="trade-log-section">
            <div class="agent-section">
                <div class="agent-header">
                    <h2>📋 Recent Trade Log</h2>
                </div>
                <div id="trade-log-body"></div>
            </div>
        </div>
    </div>

    <!-- Buy Modal -->
    <div class="modal-overlay" id="buyModal">
        <div class="modal">
            <h3 style="color: var(--accent-green);">＋ Manual Buy Order</h3>
            <div class="form-group">
                <label>Agent</label>
                <select id="buy-agent">
                    <option value="paper_positions_options.json">Options Agent</option>
                    <option value="paper_positions_scalper.json">Scalper Agent</option>
                    <option value="paper_positions_equity.json">Equity Agent</option>
                </select>
            </div>
            <div class="form-group" style="position:relative;">
                <label>Symbol</label>
                <input type="text" id="buy-symbol" placeholder="Type NIFTY or BANKNIFTY..." autocomplete="off" oninput="onSymbolInput(this.value)" onfocus="onSymbolInput(this.value)">
                <div id="symbol-dropdown" class="symbol-dropdown"></div>
            </div>
            <div class="form-group">
                <label>Quantity</label>
                <input type="number" id="buy-qty" placeholder="75" value="75">
            </div>

            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
                <div>
                    <div style="font-size:11px; font-weight:600; color:var(--accent-purple); text-transform:uppercase; letter-spacing:0.5px; margin-bottom:10px; padding-bottom:6px; border-bottom:1px solid var(--border);">Premium (Option)</div>
                    <div class="form-group">
                        <label>Entry Price</label>
                        <input type="number" step="0.05" id="buy-entry" placeholder="150.00">
                    </div>
                    <div class="form-group">
                        <label>Stop Loss</label>
                        <input type="number" step="0.05" id="buy-sl" placeholder="135.00">
                    </div>
                    <div class="form-group">
                        <label>Take Profit</label>
                        <input type="number" step="0.05" id="buy-tp" placeholder="180.00">
                    </div>
                </div>
                <div>
                    <div style="font-size:11px; font-weight:600; color:var(--accent-blue); text-transform:uppercase; letter-spacing:0.5px; margin-bottom:10px; padding-bottom:6px; border-bottom:1px solid var(--border);">Index (Underlying)</div>
                    <div class="form-group">
                        <label>Index Entry</label>
                        <input type="number" step="0.05" id="buy-idx-entry" placeholder="25800.00">
                    </div>
                    <div class="form-group">
                        <label>Index SL</label>
                        <input type="number" step="0.05" id="buy-idx-sl" placeholder="25770.00">
                    </div>
                    <div class="form-group">
                        <label>Index TP</label>
                        <input type="number" step="0.05" id="buy-idx-tp" placeholder="25830.00">
                    </div>
                </div>
            </div>

            <div class="modal-actions">
                <button class="btn-cancel" onclick="closeBuyModal()">Cancel</button>
                <button class="btn btn-buy" onclick="executeBuy()">Place Buy Order</button>
            </div>
        </div>
    </div>

    <!-- Sell Modal -->
    <div class="modal-overlay" id="sellModal">
        <div class="modal">
            <h3 style="color: var(--accent-red);">✕ Close Position</h3>
            <p style="color: var(--text-secondary); margin-bottom: 16px; font-size: 14px;" id="sell-info"></p>
            <div class="form-group">
                <label>Exit Price (leave blank for entry price)</label>
                <input type="number" step="0.05" id="sell-price" placeholder="Market price">
            </div>
            <input type="hidden" id="sell-file">
            <input type="hidden" id="sell-symbol">
            <div class="modal-actions">
                <button class="btn-cancel" onclick="closeSellModal()">Cancel</button>
                <button class="btn btn-sell" onclick="executeSell()">Confirm Sell</button>
            </div>
        </div>
    </div>

    <script>
        // Clock
        function updateClock() {
            document.getElementById('clock').textContent = new Date().toLocaleString('en-IN', {
                timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
            }) + ' IST';
        }
        setInterval(updateClock, 1000);
        updateClock();

        // Toast notification
        function showToast(msg, type='success') {
            const t = document.createElement('div');
            t.className = `toast toast-${type}`;
            t.textContent = msg;
            document.body.appendChild(t);
            setTimeout(() => t.remove(), 3000);
        }

        // Fetch & render
        // Store live prices globally
        let livePrices = {};

        async function refreshData() {
            const resp = await fetch('/api/positions');
            const data = await resp.json();

            // Collect all symbols for live price fetch (including spread sell legs)
            const allSymbols = [];
            for (const [agent, info] of Object.entries(data)) {
                for (const [sym, pos] of Object.entries(info.positions)) {
                    allSymbols.push(sym);
                    // Also fetch sell leg LTP for spread positions
                    if (pos.is_spread && pos.sell_symbol) {
                        allSymbols.push(pos.sell_symbol);
                    }
                }
            }

            // Fetch live prices for all open positions
            if (allSymbols.length > 0) {
                try {
                    const priceResp = await fetch('/api/live_prices', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({symbols: allSymbols})
                    });
                    livePrices = await priceResp.json();
                } catch(e) {
                    console.error('Live prices fetch failed', e);
                }
            }

            renderPositions(data);

            const logResp = await fetch('/api/trades');
            const logData = await logResp.json();
            renderTradeLog(logData);
        }

        const BADGES = {
            'Options Agent': 'badge-options',
            'Scalper Agent': 'badge-scalper',
            'Equity Agent': 'badge-equity',
        };

        function renderPositions(data) {
            const container = document.getElementById('positions-container');
            let html = '';
            let totalPos = 0, activeAgents = 0, totalInvested = 0;

            for (const [agent, info] of Object.entries(data)) {
                const positions = Object.entries(info.positions);
                const count = positions.length;
                totalPos += count;
                if (count > 0) activeAgents++;

                html += `<div class="agent-section">
                    <div class="agent-header">
                        <h2><span class="agent-badge ${BADGES[agent] || ''}">${agent}</span>
                            <span class="position-count">${info.file}</span></h2>
                        <span class="position-count">${count} position${count !== 1 ? 's' : ''}</span>
                    </div>`;

                if (count === 0) {
                    html += `<div class="empty-state">No open positions</div>`;
                } else {
                    html += `<table><thead><tr>
                        <th>Symbol</th><th>Dir</th><th>Qty</th>
                        <th>Entry</th><th>SL</th><th>TP</th>
                        <th>Live LTP</th><th>Live Index</th>
                        <th>P&L</th><th>P&L %</th>
                        <th></th>
                    </tr></thead><tbody>`;

                    for (const [sym, pos] of positions) {
                        const qty = pos.qty || 0;
                        const isSpread = pos.is_spread || false;
                        // If it's strictly SHORT, it's red. If it has LONG in it (like LONG SPREAD), it's green.
                        const isDirectionShort = pos.direction && pos.direction.includes('SHORT') && !pos.direction.includes('LONG');
                        const dirColor = isDirectionShort ? 'var(--accent-red)' : 'var(--accent-green)';

                        // Entry price: for spreads show buy premium, for singles show sim_entry
                        const entry = isSpread ? (pos.buy_premium || 0) : (pos.sim_entry_price || 0);
                        const netDebit = pos.net_debit || 0;
                        const invested = isSpread ? (netDebit * qty) : (entry * qty);
                        totalInvested += invested;

                        // Get live prices
                        const liveData = livePrices[sym] || {};
                        const premLtp = liveData.premium_ltp || 0;
                        const idxLtp = liveData.index_ltp || 0;

                        // For spreads, also get sell leg LTP
                        let sellLtp = 0;
                        if (isSpread && pos.sell_symbol) {
                            const sellData = livePrices[pos.sell_symbol] || {};
                            sellLtp = sellData.premium_ltp || 0;
                        }

                        // Calculate P&L
                        let pnl = 0;
                        let pnlPct = 0;
                        if (isSpread) {
                            // Spread P&L = (current spread value - net debit) × qty
                            // current spread value = buy_ltp - sell_ltp
                            if (premLtp > 0 && sellLtp > 0 && netDebit > 0) {
                                const currentSpreadValue = premLtp - sellLtp;
                                pnl = (currentSpreadValue - netDebit) * qty;
                                pnlPct = (currentSpreadValue - netDebit) / netDebit * 100;
                            }
                        } else {
                            // Single leg: P&L = (LTP - Entry) * Qty
                            if (premLtp > 0 && entry > 0) {
                                pnl = (premLtp - entry) * qty;
                                pnlPct = (premLtp - entry) / entry * 100;
                            }
                        }

                        const pnlColor = pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
                        const pnlStr = pnl >= 0 ? `+₹${pnl.toFixed(0)}` : `-₹${Math.abs(pnl).toFixed(0)}`;
                        const pnlPctStr = pnlPct >= 0 ? `+${pnlPct.toFixed(1)}%` : `${pnlPct.toFixed(1)}%`;
                        const hasLive = isSpread ? (premLtp > 0 && sellLtp > 0) : (premLtp > 0);

                        const spreadLabel = isSpread ? `<span style="background:var(--accent-purple);color:#fff;padding:1px 6px;border-radius:4px;font-size:10px;margin-left:6px;">SPREAD</span>` : '';
                        const sellSymShort = (pos.sell_symbol || '').replace('NSE:', '');
                        const buySymShort = sym.replace('NSE:', '');
                        const spreadTooltip = isSpread ? `Net Debit: ₹${netDebit.toFixed(2)} | Max Profit: ₹${(pos.max_profit || 0).toFixed(2)}` : `Since: ${since}`;
                        const symbolDisplay = isSpread 
                            ? `<span style="color:var(--accent-green);font-size:12px;">BUY</span> ${buySymShort}${spreadLabel}<br><span style="color:var(--accent-red);font-size:12px;">SELL</span> <span style="opacity:0.7;">${sellSymShort}</span>`
                            : `${sym}`;

                        // Live LTP display: for spreads show "buy / sell"
                        const ltpDisplay = isSpread 
                            ? (hasLive ? `₹${premLtp.toFixed(2)} / ₹${sellLtp.toFixed(2)}` : '...')
                            : (premLtp > 0 ? '₹' + premLtp.toFixed(2) : '...');

                        // Entry display: for spreads show "buy prem (net: X)"
                        const entryDisplay = isSpread
                            ? `₹${entry.toFixed(2)} <small style="opacity:0.6;">(net: ₹${netDebit.toFixed(2)})</small>`
                            : `₹${entry.toFixed(2)}`;

                        // SL and TP logic
                        const slPrice = isSpread ? pos.index_stop_loss_price || 0 : pos.sim_stop_loss_price || 0;
                        const tpPrice = pos.sim_take_profit_price || 0;
                        const slSuffix = isSpread ? `<sub style="opacity:0.6;">(idx)</sub>` : '';
                        const tpSuffix = isSpread ? `<sub style="opacity:0.6;">(prem)</sub>` : '';

                        html += `<tr>
                            <td style="font-weight:600;" title="${spreadTooltip}">${symbolDisplay}</td>
                            <td><span style="color: ${dirColor}; font-weight:600;">${pos.direction || 'LONG'}</span></td>
                            <td>${qty}</td>
                            <td>${entryDisplay}</td>
                            <td style="color:var(--accent-red);" title="Stop Loss">₹${slPrice.toFixed(2)}${slSuffix}</td>
                            <td style="color:var(--accent-green);" title="Take Profit">₹${tpPrice.toFixed(2)}${tpSuffix}</td>
                            <td style="font-weight:700; color:var(--accent-purple);">${ltpDisplay}</td>
                            <td style="font-weight:600; color:var(--accent-blue);">${idxLtp > 0 ? idxLtp.toFixed(2) : '...'}</td>
                            <td style="font-weight:700; color:${pnlColor};">${hasLive ? pnlStr : '...'}</td>
                            <td style="font-weight:600; color:${pnlColor};">${hasLive ? pnlPctStr : '...'}</td>
                            <td><button class="sell-btn-small" onclick="openSellModal('${info.file}','${sym}',${qty},${entry})">SELL</button></td>
                        </tr>`;
                    }
                    html += '</tbody></table>';
                }
                html += '</div>';
            }

            container.innerHTML = html;
            document.getElementById('total-positions').textContent = totalPos;
            document.getElementById('active-agents').textContent = activeAgents;
            document.getElementById('total-invested').textContent = '₹' + totalInvested.toLocaleString('en-IN', {maximumFractionDigits: 0});
        }

        function renderTradeLog(trades) {
            const el = document.getElementById('trade-log-body');
            const today = new Date().toISOString().slice(0, 10);
            let todayCount = 0;

            if (!trades.length) {
                el.innerHTML = '<div class="empty-state">No recent trades</div>';
                document.getElementById('closed-today').textContent = '0';
                return;
            }

            let html = `<table><thead><tr>
                <th>Time</th><th>Symbol</th><th>Direction</th><th>Entry</th><th>Exit</th><th>Exit Reason</th><th>P&L</th>
            </tr></thead><tbody>`;

            for (const t of trades.reverse()) {
                const pnl = parseFloat(t.pnl || t.pnl_rupees || 0);
                const cls = pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
                const sign = pnl >= 0 ? '+' : '';
                const exitTime = t.exit_time || t.close_time || '';
                if (exitTime.includes(today)) todayCount++;

                html += `<tr>
                    <td style="font-size:12px; color:var(--text-muted);">${exitTime.substring(0,16)}</td>
                    <td style="font-weight:500;">${t.symbol || ''}</td>
                    <td>${t.direction || ''}</td>
                    <td>₹${parseFloat(t.entry_price || t.sim_entry_price || 0).toFixed(2)}</td>
                    <td>₹${parseFloat(t.exit_price || 0).toFixed(2)}</td>
                    <td>${t.exit_reason || ''}</td>
                    <td class="${cls}">${sign}₹${pnl.toFixed(2)}</td>
                </tr>`;
            }
            html += '</tbody></table>';
            el.innerHTML = html;
            document.getElementById('closed-today').textContent = todayCount;
        }

        // Modals
        function openBuyModal() { document.getElementById('buyModal').classList.add('active'); }
        function closeBuyModal() { document.getElementById('buyModal').classList.remove('active'); }

        function openSellModal(file, sym, qty, entry) {
            document.getElementById('sell-file').value = file;
            document.getElementById('sell-symbol').value = sym;
            document.getElementById('sell-info').textContent = `${sym} — ${qty} units @ ₹${entry.toFixed(2)}`;
            document.getElementById('sell-price').value = '';
            document.getElementById('sellModal').classList.add('active');
        }
        function closeSellModal() { document.getElementById('sellModal').classList.remove('active'); }

        async function executeBuy() {
            const symbol = document.getElementById('buy-symbol').value.trim();
            const qty = parseInt(document.getElementById('buy-qty').value);
            const entry = parseFloat(document.getElementById('buy-entry').value);
            const sl = parseFloat(document.getElementById('buy-sl').value);
            const tp = parseFloat(document.getElementById('buy-tp').value);
            const idxEntry = parseFloat(document.getElementById('buy-idx-entry').value);
            const idxSl = parseFloat(document.getElementById('buy-idx-sl').value);
            const idxTp = parseFloat(document.getElementById('buy-idx-tp').value);

            // Frontend validation
            if (!symbol) { showToast('Symbol is required', 'error'); return; }
            if (!symbol.includes(':')) { showToast('Symbol must be in NSE:SYMBOL format', 'error'); return; }
            if (isNaN(qty) || qty <= 0) { showToast('Quantity must be a positive number', 'error'); return; }
            if (isNaN(entry) || entry <= 0) { showToast('Premium Entry price must be > 0', 'error'); return; }
            if (isNaN(sl) || sl <= 0) { showToast('Premium SL must be > 0', 'error'); return; }
            if (isNaN(tp) || tp <= 0) { showToast('Premium TP must be > 0', 'error'); return; }
            if (isNaN(idxEntry) || idxEntry <= 0) { showToast('Index Entry must be > 0', 'error'); return; }
            if (isNaN(idxSl) || idxSl <= 0) { showToast('Index SL must be > 0', 'error'); return; }
            if (isNaN(idxTp) || idxTp <= 0) { showToast('Index TP must be > 0', 'error'); return; }

            const body = {
                file: document.getElementById('buy-agent').value,
                symbol, qty, entry, sl, tp,
                idx_entry: idxEntry, idx_sl: idxSl, idx_tp: idxTp
            };
            const resp = await fetch('/api/buy', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
            const result = await resp.json();
            if (result.ok) { showToast('Buy order placed!'); closeBuyModal(); refreshData(); }
            else showToast(result.error || 'Failed', 'error');
        }

        async function executeSell() {
            const body = {
                file: document.getElementById('sell-file').value,
                symbol: document.getElementById('sell-symbol').value,
                exit_price: parseFloat(document.getElementById('sell-price').value) || null,
            };
            const resp = await fetch('/api/sell', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
            const result = await resp.json();
            if (result.ok) { showToast(`Sold! P&L: ₹${result.pnl?.toFixed(2)}`); closeSellModal(); refreshData(); }
            else showToast(result.error || 'Failed', 'error');
        }

        async function clearAll() {
            if (!confirm('Clear ALL positions across all agents?')) return;
            const resp = await fetch('/api/clear', { method: 'POST' });
            const result = await resp.json();
            if (result.ok) { showToast('All positions cleared'); refreshData(); }
        }

        // Click outside modal to close
        document.querySelectorAll('.modal-overlay').forEach(m => {
            m.addEventListener('click', e => { if (e.target === m) m.classList.remove('active'); });
        });

        // --- Symbol Autocomplete ---
        let symbolCache = [];
        let symbolFetchTimeout = null;

        async function onSymbolInput(val) {
            const dropdown = document.getElementById('symbol-dropdown');
            val = val.trim().toUpperCase();

            if (val.length < 2) {
                dropdown.classList.remove('active');
                return;
            }

            // Debounce
            clearTimeout(symbolFetchTimeout);
            symbolFetchTimeout = setTimeout(async () => {
                try {
                    const resp = await fetch(`/api/symbols?q=${encodeURIComponent(val)}`);
                    const symbols = await resp.json();
                    symbolCache = symbols;

                    if (symbols.length === 0) {
                        dropdown.classList.remove('active');
                        return;
                    }

                    let html = '';
                    for (const s of symbols) {
                        const typeClass = s.includes('CE') ? 'sym-type-ce' : 'sym-type-pe';
                        const typeLabel = s.includes('CE') ? 'CE' : 'PE';
                        html += `<div class="symbol-option" onclick="selectSymbol('${s}')">
                            <span class="sym-name">${s}</span>
                            <span class="${typeClass}">${typeLabel}</span>
                        </div>`;
                    }
                    dropdown.innerHTML = html;
                    dropdown.classList.add('active');
                } catch(e) {
                    dropdown.classList.remove('active');
                }
            }, 150);
        }

        async function selectSymbol(sym) {
            document.getElementById('buy-symbol').value = sym;
            document.getElementById('symbol-dropdown').classList.remove('active');

            // Fetch live prices for BOTH option premium AND underlying index
            try {
                // 1. Fetch option premium price
                const resp = await fetch(`/api/quote?symbol=${encodeURIComponent(sym)}`);
                const data = await resp.json();
                if (data.lp && data.lp > 0) {
                    const lp = data.lp;
                    document.getElementById('buy-entry').value = lp.toFixed(2);
                    document.getElementById('buy-sl').value = (lp * 0.90).toFixed(2);
                    document.getElementById('buy-tp').value = (lp * 1.15).toFixed(2);
                }

                // 2. Fetch underlying index spot price
                const isBank = sym.includes('BANK');
                const idxSym = isBank ? 'NSE:NIFTYBANK-INDEX' : 'NSE:NIFTY50-INDEX';
                const idxResp = await fetch(`/api/quote?symbol=${encodeURIComponent(idxSym)}`);
                const idxData = await idxResp.json();
                if (idxData.lp && idxData.lp > 0) {
                    const idxLp = idxData.lp;
                    const isPut = sym.toUpperCase().endsWith('PE');
                    // For CE: SL below, TP above. For PE: SL above, TP below (but stored as index values)
                    const slOffset = isBank ? 30 : 15;
                    const tpOffset = isBank ? 30 : 15;
                    document.getElementById('buy-idx-entry').value = idxLp.toFixed(2);
                    if (isPut) {
                        document.getElementById('buy-idx-sl').value = (idxLp + slOffset).toFixed(2);
                        document.getElementById('buy-idx-tp').value = (idxLp - tpOffset).toFixed(2);
                    } else {
                        document.getElementById('buy-idx-sl').value = (idxLp - slOffset).toFixed(2);
                        document.getElementById('buy-idx-tp').value = (idxLp + tpOffset).toFixed(2);
                    }
                }

                if (data.lp > 0 || idxData.lp > 0) {
                    showToast(`Premium: ₹${data.lp?.toFixed(2)} | Index: ${idxData.lp?.toFixed(2)}`, 'success');
                } else {
                    showToast('Could not fetch prices', 'error');
                }
            } catch(e) {
                console.error('Quote fetch failed', e);
            }
        }

        // Close dropdown on click outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.form-group')) {
                document.getElementById('symbol-dropdown').classList.remove('active');
            }
        });

        // Auto-refresh every 2 seconds (WebSocket feeds backend, so this is cheap)
        refreshData();
        setInterval(refreshData, 2000);
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/positions')
def api_positions():
    result = {}
    for agent, fname in POSITION_FILES.items():
        result[agent] = {
            "file": fname,
            "positions": load_positions(fname)
        }
    return jsonify(result)


def _get_next_expiry():
    today = datetime.date.today()
    days_ahead = (3 - today.weekday() + 7) % 7
    if days_ahead == 0 and datetime.datetime.now().time() > datetime.time(15, 30):
        days_ahead = 7
    return today + datetime.timedelta(days=days_ahead)


def _generate_option_symbols(index_name, spot_approx, num_strikes=10):
    """Generate real NSE option symbol names around ATM."""
    expiry = _get_next_expiry()
    month_map = {10: 'O', 11: 'N', 12: 'D'}
    month_part = str(expiry.month) if expiry.month < 10 else month_map[expiry.month]
    date_str = f"{expiry.strftime('%y')}{month_part}{expiry.strftime('%d')}"
    date_str_alt = expiry.strftime('%y%b').upper()

    if index_name == 'NIFTY':
        rounding = 50
        base = 'NIFTY'
    else:
        rounding = 100
        base = 'BANKNIFTY'

    atm = round(spot_approx / rounding) * rounding
    symbols = []

    for offset in range(-num_strikes, num_strikes + 1):
        strike = atm + (offset * rounding)
        for opt_type in ['CE', 'PE']:
            sym1 = f"NSE:{base}{date_str}{strike}{opt_type}"
            sym2 = f"NSE:{base}{date_str_alt}{strike}{opt_type}"
            symbols.append(sym1)
            symbols.append(sym2)

    return symbols


# Cache live spot prices (refresh every 60s)
_spot_cache = {'nifty': 0, 'banknifty': 0, 'last_fetch': 0}
_fyers_model = None

def _get_fyers():
    global _fyers_model
    if _fyers_model is None:
        _fyers_model = fyers_client.get_fyers_model()
    return _fyers_model

def _get_live_spot(index_name):
    """Fetch live spot price from Fyers, cached for 60s."""
    global _spot_cache
    now = time_module.time()

    if now - _spot_cache['last_fetch'] < 60 and _spot_cache['nifty'] > 0:
        return _spot_cache.get(index_name.lower(), 0)

    fyers = _get_fyers()
    if not fyers:
        return _spot_cache.get(index_name.lower(), 25800 if index_name == 'NIFTY' else 61500)

    try:
        quote = fyers.quotes({"symbols": "NSE:NIFTY50-INDEX,NSE:NIFTYBANK-INDEX"})
        if quote.get('s') == 'ok' and quote.get('d'):
            for item in quote['d']:
                sym = item.get('n', '')
                lp = item.get('v', {}).get('lp', 0)
                if 'NIFTY50' in sym:
                    _spot_cache['nifty'] = lp
                elif 'NIFTYBANK' in sym:
                    _spot_cache['banknifty'] = lp
            _spot_cache['last_fetch'] = now
    except Exception as e:
        print(f"Spot fetch error: {e}")

    return _spot_cache.get(index_name.lower(), 25800 if index_name == 'NIFTY' else 61500)


@app.route('/api/symbols')
def api_symbols():
    q = request.args.get('q', '').strip().upper()
    if len(q) < 2:
        return jsonify([])

    results = []

    # Fetch LIVE spot prices
    if 'NIFTY' in q and 'BANK' not in q:
        spot = _get_live_spot('NIFTY')
        results = _generate_option_symbols('NIFTY', spot)
    elif 'BANK' in q:
        spot = _get_live_spot('BANKNIFTY')
        results = _generate_option_symbols('BANKNIFTY', spot)
    else:
        nifty_spot = _get_live_spot('NIFTY')
        bank_spot = _get_live_spot('BANKNIFTY')
        results = _generate_option_symbols('NIFTY', nifty_spot) + _generate_option_symbols('BANKNIFTY', bank_spot)

    # Filter by query
    if q:
        results = [s for s in results if q in s]

    # Deduplicate and limit
    seen = set()
    unique = []
    for s in results:
        if s not in seen:
            seen.add(s)
            unique.append(s)

    return jsonify(unique[:30])


@app.route('/api/quote')
def api_quote():
    """Fetch live price for a single option symbol."""
    symbol = request.args.get('symbol', '').strip()
    if not symbol:
        return jsonify({"lp": 0, "error": "No symbol"})

    fyers = _get_fyers()
    if not fyers:
        return jsonify({"lp": 0, "error": "Fyers not connected"})

    try:
        quote = fyers.quotes({"symbols": symbol})
        if quote.get('s') == 'ok' and quote.get('d'):
            v = quote['d'][0].get('v', {})
            return jsonify({
                "lp": v.get('lp', 0),
                "open": v.get('open_price', 0),
                "high": v.get('high_price', 0),
                "low": v.get('low_price', 0),
                "volume": v.get('volume', 0),
            })
        return jsonify({"lp": 0, "error": "Symbol not found"})
    except Exception as e:
        return jsonify({"lp": 0, "error": str(e)})

# ========== WEBSOCKET LIVE TICK STORE ==========
_live_ticks = {}  # Thread-safe dict: {symbol: ltp}
_ws_socket = None
_ws_subscribed_symbols = set()
_ws_lock = threading.Lock()


def _on_ws_tick(tick_data):
    """Called by Fyers WebSocket on each tick. Stores LTP in memory."""
    global _live_ticks
    try:
        print(f"[WS DEBUG] Tick: {tick_data}") 
        ticks = tick_data if isinstance(tick_data, list) else [tick_data]
        for tick in ticks:
            if isinstance(tick, dict):
                sym = tick.get('symbol', '')
                ltp = tick.get('ltp', 0)
                if sym and ltp > 0:
                    _live_ticks[sym] = ltp
                    # print(f"[WS UPDATE] {sym}: {ltp}")
    except Exception:
        pass


def _start_ws_streaming():
    """Start Fyers WebSocket in background thread, subscribe to open position symbols + indices."""
    global _ws_socket, _ws_subscribed_symbols

    fyers = _get_fyers()
    if not fyers:
        print("[WS] Fyers not connected, skipping WebSocket")
        return

    # Collect all symbols from open positions
    symbols_to_watch = set()
    symbols_to_watch.add('NSE:NIFTY50-INDEX')
    symbols_to_watch.add('NSE:NIFTYBANK-INDEX')

    for fname in POSITION_FILES.values():
        positions = load_positions(fname)
        for sym, pos in positions.items():
            symbols_to_watch.add(sym)
            # Also subscribe to sell leg of spreads
            if isinstance(pos, dict) and pos.get('is_spread') and pos.get('sell_symbol'):
                symbols_to_watch.add(pos['sell_symbol'])

    # Note: caller should hold _ws_lock to prevent race conditions
    if symbols_to_watch == _ws_subscribed_symbols and _ws_socket is not None:
        return  # Already subscribed to same symbols

    if _ws_socket is not None:
        try:
            _ws_socket.close_connection()
        except Exception:
            pass

    symbols_list = list(symbols_to_watch)
    print(f"[WS] Starting WebSocket for {len(symbols_list)} symbols: {symbols_list}")

    try:
        _ws_socket = fyers_client.start_level2_websocket(
            access_token=fyers.token,
            on_tick=_on_ws_tick,
            symbols=symbols_list
        )
        if _ws_socket:
            ws_thread = threading.Thread(target=_ws_socket.keep_running, daemon=True)
            ws_thread.start()
            _ws_subscribed_symbols = symbols_to_watch
            print(f"[WS] WebSocket streaming started! Subscribed to {len(symbols_list)} symbols")
        else:
            print("[WS] Failed to start WebSocket")
    except Exception as e:
        print(f"[WS] WebSocket start error: {e}")


def _refresh_ws_subscriptions():
    """Check if we need to subscribe to new symbols (positions changed)."""
    with _ws_lock:
        current_symbols = set()
        current_symbols.add('NSE:NIFTY50-INDEX')
        current_symbols.add('NSE:NIFTYBANK-INDEX')

        for fname in POSITION_FILES.values():
            positions = load_positions(fname)
            for sym, pos in positions.items():
                current_symbols.add(sym)
                # Also subscribe to sell leg of spreads
                if pos.get('is_spread') and pos.get('sell_symbol'):
                    current_symbols.add(pos['sell_symbol'])

        if current_symbols != _ws_subscribed_symbols:
            _start_ws_streaming()


@app.route('/api/live_prices', methods=['POST'])
def api_live_prices():
    """Read live prices from WebSocket tick store (instant, no API call)."""
    data = request.json or {}
    symbols = data.get('symbols', [])
    if not symbols:
        return jsonify({})

    # Refresh subscriptions if positions changed
    _refresh_ws_subscriptions()

    # Read from in-memory tick store
    nifty_ltp = _live_ticks.get('NSE:NIFTY50-INDEX', 0)
    bank_ltp = _live_ticks.get('NSE:NIFTYBANK-INDEX', 0)

    result = {}
    missing_symbols = []
    
    for sym in symbols:
        prem_ltp = _live_ticks.get(sym, 0)
        if prem_ltp <= 0:
            missing_symbols.append(sym)
            
        idx_ltp = bank_ltp if 'BANK' in sym else nifty_ltp
        result[sym] = {
            "premium_ltp": prem_ltp,
            "index_ltp": idx_ltp
        }

    # --- REST API Fallback if WebSocket tick data is missing ---
    if missing_symbols:
        try:
            fyers = _get_fyers()
            if fyers:
                # Need to also fetch index if missing
                if nifty_ltp <= 0 and 'NSE:NIFTY50-INDEX' not in missing_symbols: missing_symbols.append('NSE:NIFTY50-INDEX')
                if bank_ltp <= 0 and 'NSE:NIFTYBANK-INDEX' not in missing_symbols: missing_symbols.append('NSE:NIFTYBANK-INDEX')
                
                # Fyers limits quotes to 50 symbols. Join and fetch.
                sym_string = ",".join(missing_symbols[:50])
                quotes = fyers.quotes(data={"symbols": sym_string})
                if quotes.get('s') == 'ok' and quotes.get('d'):
                    for item in quotes['d']:
                        sym_name = item.get('n', '')
                        lp = item.get('v', {}).get('lp', 0)
                        if lp > 0:
                            _live_ticks[sym_name] = lp # populate the cache
                            if sym_name == 'NSE:NIFTY50-INDEX':
                                nifty_ltp = lp
                            elif sym_name == 'NSE:NIFTYBANK-INDEX':
                                bank_ltp = lp
                            else:
                                if sym_name in result:
                                    result[sym_name]["premium_ltp"] = lp
                                    
                    # Re-map index prices for missing symbols now that we might have them
                    for sym in result:
                        if result[sym]["index_ltp"] <= 0:
                            result[sym]["index_ltp"] = bank_ltp if 'BANK' in sym else nifty_ltp
                            
        except Exception as e:
            print(f"[Fallback] Quote fetch error: {e}")

    return jsonify(result)


@app.route('/api/trades')
def api_trades():
    return jsonify(load_trade_log())


@app.route('/api/buy', methods=['POST'])
def api_buy():
    data = request.json
    fname = data.get('file', '')
    symbol = (data.get('symbol') or '').strip()

    # Validate file
    if fname not in POSITION_FILES.values():
        return jsonify({"ok": False, "error": f"Invalid agent file: {fname}"})

    # Validate symbol
    if not symbol or ':' not in symbol:
        return jsonify({"ok": False, "error": "Symbol must be in NSE:SYMBOL format"})

    # Validate numbers
    try:
        qty = int(data.get('qty', 0))
        entry = float(data.get('entry', 0))
        sl = float(data.get('sl', 0))
        tp = float(data.get('tp', 0))
        idx_entry = float(data.get('idx_entry', 0))
        idx_sl = float(data.get('idx_sl', 0))
        idx_tp = float(data.get('idx_tp', 0))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Invalid numeric values"})

    if qty <= 0:
        return jsonify({"ok": False, "error": "Quantity must be > 0"})
    if entry <= 0:
        return jsonify({"ok": False, "error": "Premium Entry price must be > 0"})
    if sl <= 0 or tp <= 0:
        return jsonify({"ok": False, "error": "Premium SL and TP must be > 0"})
    if idx_entry <= 0 or idx_sl <= 0 or idx_tp <= 0:
        return jsonify({"ok": False, "error": "All Index prices must be > 0"})

    # Check for duplicate
    positions = load_positions(fname)
    if symbol in positions:
        return jsonify({"ok": False, "error": f"Already holding {symbol}. Sell first."})

    # Auto-detect direction: CE = LONG (bullish), PE = SHORT (bearish)
    direction = "SHORT" if symbol.upper().endswith("PE") else "LONG"

    positions[symbol] = {
        "id": int(datetime.datetime.now().timestamp()),
        "qty": qty,
        "direction": direction,
        "entry_time": datetime.datetime.now().isoformat(),
        "sim_entry_price": entry,
        "sim_stop_loss_price": sl,
        "sim_take_profit_price": tp,
        "index_entry_price": idx_entry,
        "index_stop_loss_price": idx_sl,
        "index_take_profit_price": idx_tp,
    }
    save_positions(fname, positions)
    return jsonify({"ok": True})


@app.route('/api/sell', methods=['POST'])
def api_sell():
    data = request.json
    fname = data.get('file')
    symbol = data.get('symbol')
    if not fname or not symbol:
        return jsonify({"ok": False, "error": "Missing fields"})

    positions = load_positions(fname)
    if symbol not in positions:
        return jsonify({"ok": False, "error": "Position not found"})

    pos = positions[symbol]
    entry = pos.get('sim_entry_price', 0)
    qty = pos.get('qty', 0)
    direction = pos.get('direction', 'LONG')
    is_spread = pos.get('is_spread', False)

    # Calculate live exit price
    exit_price = 0
    if is_spread:
        # Spread exit price is the net spread premium: Buy LTP - Sell LTP
        buy_ltp = _live_ticks.get(symbol, 0)
        sell_ltp = _live_ticks.get(pos.get('sell_symbol', ''), 0)
        
        if buy_ltp > 0 and sell_ltp > 0:
            exit_price = buy_ltp - sell_ltp
        else:
            exit_price = data.get('exit_price') or entry # Fallback to net debit (0 P&L)
    else:
        # Single option exit price is just the live tick
        exit_price = _live_ticks.get(symbol, 0)
        if exit_price <= 0:
            exit_price = data.get('exit_price') or entry

    # P&L Calculation: P&L = (Exit - Entry) * Qty
    pnl = (exit_price - entry) * qty

    # Log the trade to trade_log.csv
    _save_trade_log({
        'id': pos.get('id', ''),
        'symbol': symbol,
        'status': 'CLOSED',
        'direction': direction,
        'qty': qty,
        'entry_price': entry,
        'exit_price': round(exit_price, 2),
        'entry_time': pos.get('entry_time', ''),
        'exit_time': datetime.datetime.now().isoformat(),
        'stop_loss': pos.get('sim_stop_loss_price', 0),
        'take_profit': pos.get('sim_take_profit_price', 0),
        'pnl': round(pnl, 2)
    })

    del positions[symbol]
    save_positions(fname, positions)
    return jsonify({"ok": True, "pnl": round(pnl, 2)})


@app.route('/api/clear', methods=['POST'])
def api_clear():
    for fname in POSITION_FILES.values():
        if os.path.exists(fname):
            save_positions(fname, {})
    return jsonify({"ok": True})


if __name__ == '__main__':
    print("=" * 50)
    print("  ProjectCognito Trading Dashboard")
    print("  Open: http://localhost:5050")
    print("=" * 50)

    app.run(host='0.0.0.0', port=5050, debug=False)
