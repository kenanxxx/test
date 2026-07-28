import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import asyncio
import threading
import base64
import httpx
import webbrowser
from datetime import datetime
from dotenv import load_dotenv
import os
import struct
from config import fetch_sol_price
from blockchain import SolanaClient
from pumpfun import PumpFunAnalyzer

load_dotenv()

PUMP_FUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMP_FUN_V2 = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"

KNOWN_PUMP_ACCOUNTS = {
    PUMP_FUN_PROGRAM, PUMP_FUN_V2,
    "4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf",
    "Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7Hx6SgqR",
    "pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ",
    "CebN5WGQ4jvEPvsVU4EoHEpgzq1VV2fskvCwf8gCDbZ",
}

NON_PUMP_PROGRAMS = {
    "11111111111111111111111111111111",
    "ComputeBudget111111111111111111111111111111",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    "SysvarRent111111111111111111111111111111111",
    "SysvarC1ock11111111111111111111111111111111",
    "jitodontfront111111111111111111111111111112",
}


class PumpFunBoostGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PUMP.FUN BOOST TRACKER")
        self.root.geometry("1200x800")
        self.root.configure(bg="#1a1a2e")
        self.root.minsize(1000, 700)
        self.running = False
        self.bot_thread = None
        self.seen_sigs = set()
        self.seen_tokens = set()
        self.signal_count = 0
        self.token_curve_cache = {}

        self.colors = {
            "bg": "#1a1a2e", "bg2": "#16213e", "bg3": "#0f3460",
            "accent": "#e94560", "green": "#00d4aa", "yellow": "#f5a623",
            "red": "#ff4757", "blue": "#3498db", "text": "#ffffff",
            "text2": "#a0a0a0", "input_bg": "#2d2d44",
        }

        self.rpc_url = tk.StringVar(value=os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"))
        self.tg_token = tk.StringVar(value=os.getenv("TELEGRAM_BOT_TOKEN", ""))
        self.tg_chat = tk.StringVar(value=os.getenv("TELEGRAM_CHAT_ID", ""))
        self.scan_interval = tk.StringVar(value="2")
        self.min_completion = tk.StringVar(value="70")
        self.max_fresh = tk.StringVar(value="100")
        self.max_bundle = tk.StringVar(value="100")

        self.solana_client = SolanaClient()
        self.pumpfun_analyzer = PumpFunAnalyzer(self.solana_client)
        self.setup_styles()
        self.create_widgets()
        self.tokens_tree._sort_dir = {}
        self.signals_tree._sort_dir = {}

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=self.colors["bg"])
        style.configure("TNotebook.Tab", background=self.colors["bg2"], foreground=self.colors["text"], padding=[15, 8], font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", self.colors["bg3"])], foreground=[("selected", self.colors["accent"])])
        style.configure("TFrame", background=self.colors["bg"])
        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("TButton", background=self.colors["accent"], foreground=self.colors["text"], font=("Segoe UI", 10, "bold"), padding=[10, 5])
        style.map("TButton", background=[("active", "#c0392b")])
        style.configure("Green.TButton", background=self.colors["green"], foreground="#000000")
        style.configure("Red.TButton", background=self.colors["red"], foreground="#ffffff")
        style.configure("TEntry", fieldbackground=self.colors["input_bg"], foreground=self.colors["text"], font=("Consolas", 10))
        style.configure("TLabelframe", background=self.colors["bg"], foreground=self.colors["accent"])
        style.configure("TLabelframe.Label", background=self.colors["bg"], foreground=self.colors["accent"], font=("Segoe UI", 11, "bold"))

    def create_widgets(self):
        header = tk.Frame(self.root, bg=self.colors["bg3"], height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="PUMP.FUN BOOST TRACKER", bg=self.colors["bg3"], fg=self.colors["accent"], font=("Segoe UI", 18, "bold")).pack(side="left", padx=20, pady=10)
        self.status_label = tk.Label(header, text="STOPPED", bg=self.colors["bg3"], fg=self.colors["red"], font=("Segoe UI", 12, "bold"))
        self.status_label.pack(side="right", padx=10)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        self.create_dashboard_tab()
        self.create_settings_tab()
        self.create_tokens_tab()
        self.create_signals_tab()
        self.create_logs_tab()

    def create_dashboard_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="  Dashboard  ")
        stats = ttk.LabelFrame(frame, text="  Statistics  ")
        stats.pack(fill="x", padx=10, pady=5)
        grid = tk.Frame(stats, bg=self.colors["bg"])
        grid.pack(fill="x", padx=10, pady=10)
        self.stat_labels = {}
        items = [("Scans", "0", self.colors["blue"]), ("Tokens Found", "0", self.colors["green"]),
                 ("Signals", "0", self.colors["accent"]), ("Errors", "0", self.colors["red"])]
        for i, (name, val, color) in enumerate(items):
            card = tk.Frame(grid, bg=self.colors["bg2"])
            card.grid(row=0, column=i, padx=5, pady=5, sticky="nsew")
            grid.columnconfigure(i, weight=1)
            tk.Label(card, text=name, bg=self.colors["bg2"], fg=self.colors["text2"], font=("Segoe UI", 9)).pack(pady=(8, 0))
            lbl = tk.Label(card, text=val, bg=self.colors["bg2"], fg=color, font=("Segoe UI", 22, "bold"))
            lbl.pack(pady=(0, 8))
            self.stat_labels[name] = lbl

        ctrl = ttk.LabelFrame(frame, text="  Controls  ")
        ctrl.pack(fill="x", padx=10, pady=5)
        btns = tk.Frame(ctrl, bg=self.colors["bg"])
        btns.pack(fill="x", padx=10, pady=10)
        ttk.Button(btns, text="START", style="Green.TButton", command=self.start_bot).pack(side="left", padx=5)
        ttk.Button(btns, text="STOP", style="Red.TButton", command=self.stop_bot).pack(side="left", padx=5)
        ttk.Button(btns, text="SINGLE SCAN", command=self.single_scan).pack(side="left", padx=5)

        log_frame = ttk.LabelFrame(frame, text="  Live Log  ")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.live_log = scrolledtext.ScrolledText(log_frame, bg=self.colors["input_bg"], fg=self.colors["green"], font=("Consolas", 9), wrap="word", state="disabled", height=15)
        self.live_log.pack(fill="both", expand=True, padx=5, pady=5)

    def create_settings_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="  Settings  ")
        rpc = ttk.LabelFrame(frame, text="  RPC Settings  ")
        rpc.pack(fill="x", padx=10, pady=5, ipady=5)
        tk.Label(rpc, text="RPC URL:", bg=self.colors["bg"], fg=self.colors["text"], width=12, anchor="e").grid(row=0, column=0, padx=5, pady=5)
        ttk.Entry(rpc, textvariable=self.rpc_url, width=60).grid(row=0, column=1, padx=5, pady=5)
        tg = ttk.LabelFrame(frame, text="  Telegram  ")
        tg.pack(fill="x", padx=10, pady=5, ipady=5)
        tk.Label(tg, text="Bot Token:", bg=self.colors["bg"], fg=self.colors["text"], width=12, anchor="e").grid(row=0, column=0, padx=5, pady=5)
        ttk.Entry(tg, textvariable=self.tg_token, width=60).grid(row=0, column=1, padx=5, pady=5)
        tk.Label(tg, text="Chat ID:", bg=self.colors["bg"], fg=self.colors["text"], width=12, anchor="e").grid(row=1, column=0, padx=5, pady=5)
        ttk.Entry(tg, textvariable=self.tg_chat, width=60).grid(row=1, column=1, padx=5, pady=5)
        boost = ttk.LabelFrame(frame, text="  Boost Settings  ")
        boost.pack(fill="x", padx=10, pady=5, ipady=5)
        tk.Label(boost, text="Scan Interval (s):", bg=self.colors["bg"], fg=self.colors["text"], width=15, anchor="e").grid(row=0, column=0, padx=5, pady=5)
        ttk.Entry(boost, textvariable=self.scan_interval, width=10).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        tk.Label(boost, text="Min Completion %:", bg=self.colors["bg"], fg=self.colors["text"], width=15, anchor="e").grid(row=1, column=0, padx=5, pady=5)
        ttk.Entry(boost, textvariable=self.min_completion, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        btn_frame = tk.Frame(frame, bg=self.colors["bg"])
        btn_frame.pack(fill="x", padx=10, pady=10)
        ttk.Button(btn_frame, text="SAVE SETTINGS", command=self.save_settings).pack(side="left", padx=5)

    def create_tokens_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="  Tokens  ")

        filter_frame = tk.Frame(frame, bg=self.colors["bg2"])
        filter_frame.pack(fill="x", padx=10, pady=(10, 2))
        tk.Label(filter_frame, text="Min Completion %:", bg=self.colors["bg2"], fg=self.colors["text"], font=("Segoe UI", 9)).pack(side="left", padx=(5, 2))
        ttk.Entry(filter_frame, textvariable=self.min_completion, width=6).pack(side="left", padx=(0, 10))
        tk.Label(filter_frame, text="Max Fresh %:", bg=self.colors["bg2"], fg=self.colors["text"], font=("Segoe UI", 9)).pack(side="left", padx=(5, 2))
        ttk.Entry(filter_frame, textvariable=self.max_fresh, width=6).pack(side="left", padx=(0, 10))
        tk.Label(filter_frame, text="Max Bundle %:", bg=self.colors["bg2"], fg=self.colors["text"], font=("Segoe UI", 9)).pack(side="left", padx=(5, 2))
        ttk.Entry(filter_frame, textvariable=self.max_bundle, width=6).pack(side="left")

        cols = ("Symbol", "Mint", "Completion", "Market Cap", "SOL", "Fresh %", "Bundle %", "Stage", "Time")
        self.tokens_tree = ttk.Treeview(frame, columns=cols, show="headings", height=15)
        for c in cols:
            self.tokens_tree.heading(c, text=c, command=lambda col=c: self._sort_treeview(self.tokens_tree, col))
            self.tokens_tree.column(c, width=110, anchor="center")
        self.tokens_tree.column("Mint", width=160)
        self.tokens_tree.column("Time", width=80)
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tokens_tree.yview)
        self.tokens_tree.configure(yscrollcommand=sb.set)
        self.tokens_tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=5)
        self.tokens_tree.bind("<Double-1>", self._on_token_click)
        sb.pack(side="right", fill="y", padx=(0, 10), pady=5)

        hint2 = tk.Label(frame, text="Double-click a token to open on Padre Trade", bg=self.colors["bg"], fg=self.colors["text2"], font=("Segoe UI", 9))
        hint2.pack(pady=(0, 5))

    def create_signals_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="  Signals  ")
        cols = ("Time", "Action", "Symbol", "Mint", "Confidence", "Reason", "Amount")
        self.signals_tree = ttk.Treeview(frame, columns=cols, show="headings", height=15)
        for c in cols:
            self.signals_tree.heading(c, text=c, command=lambda col=c: self._sort_treeview(self.signals_tree, col))
            self.signals_tree.column(c, width=110, anchor="center")
        self.signals_tree.column("Mint", width=160)
        self.signals_tree.column("Reason", width=200)
        self.signals_tree.pack(fill="both", expand=True, padx=10, pady=5)
        self.signals_tree.bind("<Double-1>", self._on_signal_click)

        hint = tk.Label(frame, text="Double-click a signal to open on Padre Trade", bg=self.colors["bg"], fg=self.colors["text2"], font=("Segoe UI", 9))
        hint.pack(pady=(0, 5))

    def create_logs_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="  Logs  ")
        btn_frame = tk.Frame(frame, bg=self.colors["bg"])
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text="CLEAR", command=self.clear_logs).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="SAVE", command=self.save_logs).pack(side="left", padx=5)
        self.log_text = scrolledtext.ScrolledText(frame, bg=self.colors["input_bg"], fg=self.colors["green"], font=("Consolas", 9), wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

    def log(self, msg, level="INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{level}] {msg}\n"
        for w in [self.log_text, self.live_log]:
            w.configure(state="normal")
            w.insert("end", line)
            w.see("end")
            w.configure(state="disabled")

    def update_stat(self, name, val):
        if name in self.stat_labels:
            self.stat_labels[name].configure(text=str(val))

    def start_bot(self):
        if self.running:
            return
        self.running = True
        self.status_label.configure(text="RUNNING", fg=self.colors["green"])
        self.log("Bot started")
        self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()

    def stop_bot(self):
        self.running = False
        self.status_label.configure(text="STOPPED", fg=self.colors["red"])
        self.log("Bot stopped")

    def single_scan(self):
        threading.Thread(target=self.run_single_scan, daemon=True).start()

    def run_bot(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.scan_loop())

    def run_single_scan(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._do_scan())

    def _get_pump_accounts_from_tx(self, tx):
        accs = tx.get("transaction", {}).get("message", {}).get("accountKeys", [])
        pump_accs = []
        for a in accs:
            addr = a if isinstance(a, str) else a.get("pubkey", "")
            if addr not in NON_PUMP_PROGRAMS and len(addr) >= 32:
                pump_accs.append(addr)
        return pump_accs

    def _extract_mints_and_curve_from_tx(self, tx):
        meta = tx.get("meta", {})
        msg = tx.get("transaction", {}).get("message", {})
        accs = msg.get("accountKeys", [])

        token_mints = []
        candidate_curves = []

        for a in accs:
            addr = a if isinstance(a, str) else a.get("pubkey", "")
            if addr.endswith("pump") and len(addr) >= 32:
                token_mints.append(addr)

        post = meta.get("postTokenBalances", [])
        pre = meta.get("preTokenBalances", [])
        pre_mints = {pb.get("mint") for pb in pre}

        for pb in post:
            mint = pb.get("mint", "")
            if mint and mint not in pre_mints and mint not in token_mints:
                token_mints.append(mint)

        pump_accs = self._get_pump_accounts_from_tx(tx)
        known_set = set(NON_PUMP_PROGRAMS) | set(KNOWN_PUMP_ACCOUNTS)
        for a in pump_accs:
            if a not in known_set and not a.endswith("pump"):
                candidate_curves.append(a)

        return token_mints, candidate_curves

    async def scan_loop(self):
        self.log("Scan loop started")
        scan_count = 0
        token_count = 0
        error_count = 0

        async with httpx.AsyncClient(timeout=30) as client:
            while self.running:
                scan_count += 1
                self.root.after(0, self.update_stat, "Scans", scan_count)
                try:
                    result = await self._do_scan_with_client(client, scan_count)
                    if result:
                        token_count += result
                        self.root.after(0, self.update_stat, "Tokens Found", token_count)
                except Exception as e:
                    error_count += 1
                    self.root.after(0, self.update_stat, "Errors", error_count)
                    self.log(f"Scan error: {e}", "ERROR")
                await asyncio.sleep(int(self.scan_interval.get()))

    async def _do_scan(self):
        async with httpx.AsyncClient(timeout=30) as client:
            await self._do_scan_with_client(client, 0)

    async def _do_scan_with_client(self, client, scan_num):
        self.log(f"--- Scan #{scan_num} ---")
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "getSignaturesForAddress",
            "params": [PUMP_FUN_PROGRAM, {"limit": 20}]
        }
        resp = await client.post(self.rpc_url.get(), json=payload)
        data = resp.json()

        if "result" not in data:
            self.log(f"RPC error: {data.get('error')}", "ERROR")
            return 0

        sigs = data["result"]
        self.log(f"Fetched {len(sigs)} signatures")
        found = 0

        for sig_info in sigs:
            if not self.running:
                break
            sig = sig_info.get("signature")
            if not sig or sig in self.seen_sigs:
                continue
            self.seen_sigs.add(sig)

            tx_payload = {
                "jsonrpc": "2.0", "id": 1,
                "method": "getTransaction",
                "params": [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
            }

            try:
                tx_resp = await client.post(self.rpc_url.get(), json=tx_payload)
                tx_data = tx_resp.json()
                if "result" not in tx_data or not tx_data["result"]:
                    continue

                tx = tx_data["result"]
                meta = tx.get("meta", {})
                if not meta or meta.get("err"):
                    continue

                token_mints, candidate_curves = self._extract_mints_and_curve_from_tx(tx)

                for mint in token_mints:
                    if mint and mint not in self.seen_tokens:
                        self.seen_tokens.add(mint)
                        found += 1
                        self.log(f"PUMP TOKEN: {mint[:20]}...", "SIGNAL")
                        await self.fetch_token_details(client, mint, candidate_curves)

            except Exception as e:
                self.log(f"TX error: {e}", "ERROR")
                continue

        self.log(f"Scan #{scan_num} done: {found} new tokens")
        return found

    async def fetch_token_details(self, client, mint, candidate_curves=None):
        try:
            sol_price = await fetch_sol_price(client)

            if mint in self.token_curve_cache:
                curve = self.token_curve_cache[mint]
                fresh_pct, bundle_pct = await self.pumpfun_analyzer.analyze_holders(mint)
                self._display_token(mint, curve, sol_price, fresh_pct, bundle_pct)
                return

            curve = None

            if candidate_curves:
                self.log(f"  [{mint[:8]}] Checking {len(candidate_curves)} candidate curve accounts...")
                try:
                    batch = candidate_curves[:10]
                    payload = {
                        "jsonrpc": "2.0", "id": 1,
                        "method": "getMultipleAccounts",
                        "params": [batch]
                    }
                    resp = await client.post(self.rpc_url.get(), json=payload)
                    data = resp.json()

                    if "result" in data and data["result"].get("value"):
                        for idx, acct in enumerate(data["result"]["value"]):
                            if not acct:
                                continue
                            owner = acct.get("owner", "")
                            acct_data = acct.get("data", [])
                            data_type = acct.get("data", {})

                            if owner == PUMP_FUN_PROGRAM:
                                self.log(f"  [{mint[:8]}] MATCH owner=PUMP idx={idx} addr={batch[idx][:16]}...")

                                if isinstance(acct_data, list) and len(acct_data) >= 2:
                                    encoding = acct_data[1]
                                    raw_bytes = base64.b64decode(acct_data[0])
                                    self.log(f"  [{mint[:8]}] encoding={encoding} dataLen={len(raw_bytes)}")

                                    if len(raw_bytes) >= 40:
                                        hex_preview = raw_bytes[:48].hex()
                                        disc = raw_bytes[:8].hex()
                                        self.log(f"  [{mint[:8]}] disc={disc} dataLen={len(raw_bytes)} hex={hex_preview}")

                                        if len(raw_bytes) == 151 and disc == "17b7f83760d8ac60":
                                            vtok = struct.unpack_from("<Q", raw_bytes, 8)[0] / 1e6
                                            vsol = struct.unpack_from("<Q", raw_bytes, 16)[0] / 1e9
                                            rtok = struct.unpack_from("<Q", raw_bytes, 24)[0] / 1e6
                                            rsol = struct.unpack_from("<Q", raw_bytes, 32)[0] / 1e9
                                            supply = struct.unpack_from("<Q", raw_bytes, 40)[0] / 1e6
                                            self.log(f"  [{mint[:8]}] BONDING CURVE: vTok={vtok:.0f} vSol={vsol:.2f} rTok={rtok:.0f} rSol={rsol:.4f} supply={supply:.0f}")

                                            if vsol > 0 or rsol > 0:
                                                curve = {
                                                    "virtualSolReserves": int(vsol * 1e9),
                                                    "virtualTokenReserves": int(vtok * 1e6),
                                                    "realSolReserves": int(rsol * 1e9),
                                                    "realTokenReserves": int(rtok * 1e6),
                                                    "tokenTotalSupply": int(supply * 1e6),
                                                }
                                                self.token_curve_cache[mint] = curve
                                                self.log(f"  [{mint[:8]}] Curve data extracted!")
                                                break
                                        else:
                                            self.log(f"  [{mint[:8]}] SKIPPED (not bonding curve)")

                                elif isinstance(acct_data, dict):
                                    parsed = acct_data.get("parsed", {})
                                    info = parsed.get("info", {}) if isinstance(parsed, dict) else {}
                                    self.log(f"  [{mint[:8]}] parsed keys: {list(info.keys())[:10] if isinstance(info, dict) else 'N/A'}")
                                    if info:
                                        curve = info
                                        self.token_curve_cache[mint] = curve
                                        self.log(f"  [{mint[:8]}] Curve from parsed data!")
                                        break
                            else:
                                if idx < 3:
                                    self.log(f"  [{mint[:8]}] idx={idx} owner={owner[:20]}...")
                except Exception as e:
                    self.log(f"  [{mint[:8]}] Batch scan error: {e}", "ERROR")

            if not curve:
                self.log(f"  [{mint[:8]}] No curve data found")
                return

            fresh_pct, bundle_pct = await self.pumpfun_analyzer.analyze_holders(mint)
            self._display_token(mint, curve, sol_price, fresh_pct, bundle_pct)

        except Exception as e:
            self.log(f"  Detail error: {e}", "ERROR")

    def _display_token(self, mint, curve, sol_price, fresh_pct="?", bundle_pct="?"):
        virtual_sol = float(curve.get("virtualSolReserves", 0)) / 1e9
        real_sol = float(curve.get("realSolReserves", 0)) / 1e9
        real_tokens = float(curve.get("realTokenReserves", 0)) / 1e6
        total_supply = float(curve.get("tokenTotalSupply", 1_000_000_000_000_000)) / 1e6
        virtual_tokens = float(curve.get("virtualTokenReserves", 0)) / 1e6

        if total_supply == 0:
            total_supply = 1_000_000_000

        if virtual_sol == 0 and real_sol == 0:
            return

        tokens_sold = total_supply - real_tokens
        price_per_token = virtual_sol / virtual_tokens if virtual_tokens > 0 else 0
        market_cap = price_per_token * total_supply * sol_price
        completion = min((real_sol / 85) * 100, 100)

        if completion >= 100:
            stage = "PumpSwap"
        elif completion >= 90:
            stage = "THRESHOLD"
        elif completion >= 70:
            stage = "LATE"
        elif completion >= 40:
            stage = "MID"
        else:
            stage = "EARLY"

        now = datetime.now().strftime("%H:%M:%S")
        symbol = mint[:8]
        fresh_str = f"{fresh_pct:.1f}%" if isinstance(fresh_pct, float) else str(fresh_pct)
        bundle_str = f"{bundle_pct:.1f}%" if isinstance(bundle_pct, float) else str(bundle_pct)
        self.root.after(0, self._add_token_row, symbol, mint, f"{completion:.1f}%", f"${market_cap:,.0f}", f"{real_sol:.2f}", fresh_str, bundle_str, stage, now)
        self.log(f"  TOKEN: {mint[:12]}... | {completion:.1f}% | ${market_cap:,.0f} | {stage}")

        min_comp = float(self.min_completion.get())
        max_fresh = float(self.max_fresh.get())
        max_bundle = float(self.max_bundle.get())
        fresh_ok = not isinstance(fresh_pct, float) or fresh_pct <= max_fresh
        bundle_ok = not isinstance(bundle_pct, float) or bundle_pct <= max_bundle

        if completion >= min_comp and fresh_ok and bundle_ok:
            confidence = min(completion * 0.9, 95)
            if stage == "THRESHOLD":
                reason = f"Near graduation ({completion:.1f}%) - SOL:{real_sol:.1f} MCap:${market_cap:,.0f}"
                confidence = min(confidence + 10, 95)
            elif stage == "PumpSwap":
                reason = f"BOOST candidate - SOL:{real_sol:.1f} MCap:${market_cap:,.0f} BOOST:17.6 SOL"
                confidence = min(confidence + 15, 98)
            elif stage == "LATE":
                reason = f"Late curve ({completion:.1f}%) - SOL:{real_sol:.1f} MCap:${market_cap:,.0f}"
            elif stage == "MID":
                reason = f"Mid curve ({completion:.1f}%) - SOL:{real_sol:.1f} MCap:${market_cap:,.0f}"
            else:
                reason = f"Early ({completion:.1f}%) - SOL:{real_sol:.1f} MCap:${market_cap:,.0f}"

            action = "BUY" if completion >= 90 or stage == "PumpSwap" else "WATCH"
            self.signal_count += 1
            self.root.after(0, self.update_stat, "Signals", self.signal_count)
            self.root.after(0, self._add_signal_row, action, symbol, mint, f"{confidence:.0f}%", reason, f"{real_sol:.2f}")
            self.log(f"  >>> SIGNAL: {action} {symbol} | {confidence:.0f}% | {reason}", "SIGNAL")

    def _add_token_row(self, symbol, mint, completion, mcap, sol, fresh, bundle, stage, time):
        self.tokens_tree.insert("", "0", values=(symbol, mint, completion, mcap, sol, fresh, bundle, stage, time))

    def _add_signal_row(self, action, symbol, mint, confidence, reason, amount):
        now = datetime.now().strftime("%H:%M:%S")
        self.signals_tree.insert("", "0", values=(now, action, symbol, mint, confidence, reason, amount))

    def _sort_treeview(self, tree, col):
        numeric_cols = {"Completion", "Market Cap", "SOL", "Fresh %", "Bundle %", "Confidence", "Amount"}
        items = [(tree.set(k, col), k) for k in tree.get_children("")]
        try:
            if col in numeric_cols:
                items.sort(key=lambda x: float(x[0].replace("$", "").replace("%", "").replace(",", "")),
                           reverse=(tree._sort_dir.get(col, False)))
            else:
                items.sort(reverse=tree._sort_dir.get(col, False))
        except:
            items.sort(reverse=tree._sort_dir.get(col, False))
        for idx, (_, k) in enumerate(items):
            tree.move(k, "", idx)
        tree._sort_dir[col] = not tree._sort_dir.get(col, False)

    def _on_signal_click(self, event):
        sel = self.signals_tree.selection()
        if not sel:
            return
        item = self.signals_tree.item(sel[0])
        mint = item["values"][3]
        url = f"https://trade.padre.gg/trade/solana/{mint}"
        self.log(f"Opening: {url}")
        webbrowser.open(url)

    def _on_token_click(self, event):
        sel = self.tokens_tree.selection()
        if not sel:
            return
        item = self.tokens_tree.item(sel[0])
        mint = item["values"][1]
        url = f"https://trade.padre.gg/trade/solana/{mint}"
        self.log(f"Opening: {url}")
        webbrowser.open(url)

    def clear_logs(self):
        for w in [self.log_text, self.live_log]:
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.configure(state="disabled")

    def save_logs(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f"logs_{ts}.txt", "w", encoding="utf-8") as f:
            f.write(self.log_text.get("1.0", "end"))
        self.log("Logs saved")

    def save_settings(self):
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        with open(env_path, "w") as f:
            f.write(f"SOLANA_RPC_URL={self.rpc_url.get()}\n")
            f.write(f"TELEGRAM_BOT_TOKEN={self.tg_token.get()}\n")
            f.write(f"TELEGRAM_CHAT_ID={self.tg_chat.get()}\n")
            f.write(f"SCAN_INTERVAL={self.scan_interval.get()}\n")
            f.write(f"MIN_COMPLETION={self.min_completion.get()}\n")
        self.log("Settings saved")
        messagebox.showinfo("OK", "Settings saved")

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.log("PUMP.FUN BOOST TRACKER initialized")
        self.log(f"RPC: {self.rpc_url.get()[:50]}...")
        self.log("Click START to begin")
        self.root.mainloop()

    def on_close(self):
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    app = PumpFunBoostGUI()
    app.run()
