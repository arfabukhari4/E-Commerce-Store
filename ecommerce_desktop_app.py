"""
PROFESSIONAL E-COMMERCE STORE - UNIFIED DESKTOP APPLICATION
=============================================================
Built with Python + Tkinter. Consolidates 9 window-per-module scripts into
a single, state-sharing, single-root desktop application, following the
same architectural discipline demonstrated in elearning_desktop_app.py:
OOP service layer, custom exceptions, a call-logging decorator, JSON
persistence, centralized theming, and sidebar navigation.

Color theme: Baby Pink & Light Purple (see ThemeManager.THEME).

WHERE EACH ORIGINAL FILE LIVES
--------------------------------
    main.py                -> WelcomePanel               (show_welcome)
    login.py                -> LoginPanel                 (show_login)
    register_window.py      -> RegisterPanel              (show_register)
    customer_dashboard.py   -> DashboardPanel             (show_dashboard)
    products.py              -> ProductsPanel              (show_products)
    cart.py                  -> CartPanel                  (show_cart)
    wishlist.py               -> WishlistPanel              (show_wishlist)
    orders.py                 -> OrdersPanel                (show_orders)
    profile.py                -> ProfilePanel               (show_profile)

Service / logic layer (pure Python, zero tkinter imports):
    UserStore, ProductCatalog, CartService, WishlistService, OrderService

Run:
    python ecommerce_desktop_app.py

Requirements:
    Python 3.9+ with the standard 'tkinter' module.
    On Linux, if you see "ModuleNotFoundError: No module named 'tkinter'",
    install it with:  sudo apt install python3-tk
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from functools import wraps
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

DATA_FILE = Path("ecommerce_data.json")


# =============================================================================
# CUSTOM EXCEPTION HIERARCHY
# =============================================================================
class StoreError(Exception):
    """Base exception for every application-specific error."""


class AuthenticationError(StoreError):
    """Raised when login credentials are invalid."""


class DuplicateUsernameError(StoreError):
    """Raised when registering a username that already exists."""


class ValidationError(StoreError):
    """Raised when form input fails validation rules."""


class EmptyCartError(StoreError):
    """Raised when attempting to checkout an empty cart."""


class ProductNotFoundError(StoreError):
    """Raised when a referenced product does not exist."""


class InsufficientStockError(StoreError):
    """Raised when attempting to add an out-of-stock product to the cart."""


# =============================================================================
# DECORATOR - lightweight call logger (mirrors the reference project)
# =============================================================================
def log_call(func):
    """Logs the name and execution time of the wrapped method to the console."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"[LOG] {func.__name__}() took {elapsed_ms:.3f} ms")
        return result

    return wrapper


# =============================================================================
# VALIDATION HELPERS
# =============================================================================
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def require(value, field_name: str) -> str:
    if value is None or str(value).strip() == "":
        raise ValidationError(f"{field_name} is required.")
    return str(value).strip()


def validate_email(value) -> str:
    value = require(value, "Email")
    if not EMAIL_RE.match(value):
        raise ValidationError("Please enter a valid email address.")
    return value


def validate_phone(value) -> str:
    value = require(value, "Phone number")
    if not (value.isdigit() and 10 <= len(value) <= 15):
        raise ValidationError(
            "Phone number must contain only digits and be between 10 and 15 digits."
        )
    return value


# =============================================================================
# SERVICE / LOGIC LAYER - zero tkinter imports, fully unit-testable
# =============================================================================
class UserStore:
    """Registers, authenticates, and updates user accounts (register_window.py
    + login.py). Wraps a single combined JSON persistence layer instead of a
    standalone users.json, and keeps the password private -- it is never
    included in the public dict returned to the GUI layer."""

    def __init__(self):
        self._users: dict[str, dict] = {}  # key: lowercase username

    def _exists(self, username: str) -> bool:
        return username.strip().lower() in self._users

    @log_call
    def register(
        self,
        full_name: str,
        username: str,
        email: str,
        phone: str,
        address: str,
        password: str,
        confirm_password: str,
    ) -> dict:
        full_name = require(full_name, "Full Name")
        username = require(username, "Username")
        email = validate_email(email)
        phone = validate_phone(phone)
        address = require(address, "Address")
        password = require(password, "Password")
        confirm_password = require(confirm_password, "Confirm Password")

        if len(password) < 6:
            raise ValidationError("Password must be at least 6 characters.")

        if password != confirm_password:
            raise ValidationError("Passwords do not match.")

        if self._exists(username):
            raise DuplicateUsernameError(f"Username '{username}' already exists.")

        record = {
            "full_name": full_name,
            "username": username,
            "email": email,
            "phone": phone,
            "address": address,
            "_password": password,
        }

        self._users[username.lower()] = record

        return self.get_public(username)

    @log_call
    def login(self, username: str, password: str) -> dict:
        username = require(username, "Username")
        password = require(password, "Password")

        record = self._users.get(username.strip().lower())

        if record is None or record["_password"] != password:
            raise AuthenticationError("Invalid username or password.")

        return self.get_public(username)

    def get_public(self, username: str) -> dict:
        record = self._users.get(username.strip().lower())

        if record is None:
            raise AuthenticationError("User not found.")

        return {key: value for key, value in record.items() if key != "_password"}

    def update_profile(self, username: str, **fields) -> dict:
        record = self._users.get(username.strip().lower())

        if record is None:
            raise AuthenticationError("User not found.")

        if fields.get("email"):
            fields["email"] = validate_email(fields["email"])

        if fields.get("phone"):
            fields["phone"] = validate_phone(fields["phone"])

        for key in ("full_name", "email", "phone", "address"):
            if fields.get(key):
                record[key] = fields[key]

        return self.get_public(username)

    def change_password(
        self, username: str, old_password: str, new_password: str, confirm_password: str
    ) -> None:
        record = self._users.get(username.strip().lower())

        if record is None or record["_password"] != old_password:
            raise AuthenticationError("Current password is incorrect.")

        new_password = require(new_password, "New Password")
        confirm_password = require(confirm_password, "Confirm Password")

        if len(new_password) < 6:
            raise ValidationError("Password must be at least 6 characters.")

        if new_password != confirm_password:
            raise ValidationError("Passwords do not match.")

        record["_password"] = new_password

    def to_json(self) -> list[dict]:
        return list(self._users.values())

    def load_json(self, rows: list[dict]) -> None:
        for row in rows:
            try:
                username = row["username"]
                self._users[username.lower()] = dict(row)
            except (KeyError, TypeError):
                continue


class ProductCatalog:
    """Search/filter over the product list (products.py)."""

    def __init__(self):
        self.products: list[dict] = [
            {
                "name": "Laptop", "category": "Electronics", "price": 850.0,
                "stock": "In Stock", "stock_qty": 25, "rating": "\u2605\u2605\u2605\u2605\u2606",
                "description": "Powerful laptop for work and study.", "icon": "\U0001F4BB",
            },
            {
                "name": "Smart Phone", "category": "Electronics", "price": 550.0,
                "stock": "In Stock", "stock_qty": 40, "rating": "\u2605\u2605\u2605\u2605\u2605",
                "description": "Latest Android smartphone.", "icon": "\U0001F4F1",
            },
            {
                "name": "Headphones", "category": "Accessories", "price": 90.0,
                "stock": "Limited Stock", "stock_qty": 3, "rating": "\u2605\u2605\u2605\u2605\u2606",
                "description": "Noise cancelling headphones.", "icon": "\U0001F3A7",
            },
            {
                "name": "Smart Watch", "category": "Accessories", "price": 180.0,
                "stock": "Out of Stock", "stock_qty": 0, "rating": "\u2605\u2605\u2605\u2605\u2606",
                "description": "Fitness tracking smartwatch.", "icon": "\u231A",
            },
            {
                "name": "Gaming Mouse", "category": "Computer", "price": 45.0,
                "stock": "In Stock", "stock_qty": 60, "rating": "\u2605\u2605\u2605\u2605\u2605",
                "description": "RGB gaming mouse.", "icon": "\U0001F5B1",
            },
            {
                "name": "Keyboard", "category": "Computer", "price": 65.0,
                "stock": "In Stock", "stock_qty": 30, "rating": "\u2605\u2605\u2605\u2605\u2606",
                "description": "Mechanical keyboard.", "icon": "\u2328",
            },
        ]

    def all(self) -> list[dict]:
        return list(self.products)

    def categories(self) -> list[str]:
        return ["All"] + sorted({p["category"] for p in self.products})

    def search(self, keyword: str = "", category: str = "All") -> list[dict]:
        keyword = (keyword or "").strip().lower()
        results = []

        for product in self.products:
            match_keyword = (
                keyword in product["name"].lower()
                or keyword in product["description"].lower()
            )
            match_category = category == "All" or product["category"] == category

            if match_keyword and match_category:
                results.append(product)

        return results

    def find(self, name: str) -> dict:
        for product in self.products:
            if product["name"] == name:
                return product

        raise ProductNotFoundError(f"Product '{name}' not found.")


class CartService:
    """Add/remove/increase/decrease/clear/total (cart.py)."""

    def __init__(self):
        self.items: list[dict] = []

    def _find(self, name: str) -> dict | None:
        for item in self.items:
            if item["name"] == name:
                return item
        return None

    @log_call
    def add(self, product: dict, quantity: int = 1) -> None:
        if product.get("stock") == "Out of Stock":
            raise InsufficientStockError(f"'{product['name']}' is out of stock.")

        existing = self._find(product["name"])

        if existing:
            existing["quantity"] += quantity
        else:
            self.items.append({
                "name": product["name"],
                "price": float(product["price"]),
                "quantity": quantity,
            })

    def remove(self, name: str) -> None:
        item = self._find(name)

        if item:
            self.items.remove(item)

    def increase(self, name: str) -> None:
        item = self._find(name)

        if item:
            item["quantity"] += 1

    def decrease(self, name: str) -> None:
        item = self._find(name)

        if item is None:
            return

        if item["quantity"] <= 1:
            raise ValidationError("Quantity cannot be less than 1.")

        item["quantity"] -= 1

    def clear(self) -> None:
        self.items.clear()

    def total_items(self) -> int:
        return sum(item["quantity"] for item in self.items)

    def total_price(self) -> float:
        return sum(item["price"] * item["quantity"] for item in self.items)

    def to_json(self) -> list[dict]:
        return list(self.items)

    def load_json(self, rows: list[dict]) -> None:
        self.items = list(rows) if rows else []


class WishlistService:
    """Add/remove/move-to-cart (wishlist.py)."""

    def __init__(self, cart: CartService):
        self._cart = cart
        self.items: list[dict] = []

    def _find(self, name: str) -> dict | None:
        for item in self.items:
            if item["name"] == name:
                return item
        return None

    def add(self, product: dict) -> None:
        if self._find(product["name"]):
            raise ValidationError(f"'{product['name']}' is already in your wishlist.")

        self.items.append(dict(product))

    def remove(self, name: str) -> None:
        item = self._find(name)

        if item:
            self.items.remove(item)

    @log_call
    def move_to_cart(self, name: str) -> None:
        item = self._find(name)

        if item is None:
            raise ProductNotFoundError(f"'{name}' not found in wishlist.")

        self._cart.add(item)
        self.remove(name)

    def to_json(self) -> list[dict]:
        return list(self.items)

    def load_json(self, rows: list[dict]) -> None:
        self.items = list(rows) if rows else []


class OrderService:
    """Place order from cart, search, sort (orders.py)."""

    def __init__(self):
        self.orders: list[dict] = [
            {
                "id": "ORD1001", "customer": "Ali Khan", "date": "01-Aug-2026",
                "products": "Laptop, Mouse", "amount": 900.0, "payment": "Paid",
                "delivery": "Delivered",
            },
            {
                "id": "ORD1002", "customer": "Sara Ahmed", "date": "02-Aug-2026",
                "products": "Smart Phone", "amount": 550.0, "payment": "Paid",
                "delivery": "Shipped",
            },
            {
                "id": "ORD1003", "customer": "Ahmed Raza", "date": "03-Aug-2026",
                "products": "Keyboard, Headphones", "amount": 180.0, "payment": "Pending",
                "delivery": "Processing",
            },
        ]
        self._counter = 1004

    @log_call
    def place_order(self, cart: CartService, customer_name: str) -> dict:
        if not cart.items:
            raise EmptyCartError("Your cart is empty. Add products before checkout.")

        order = {
            "id": f"ORD{self._counter}",
            "customer": customer_name,
            "date": datetime.now().strftime("%d-%b-%Y"),
            "products": ", ".join(item["name"] for item in cart.items),
            "amount": cart.total_price(),
            "payment": "Paid",
            "delivery": "Processing",
        }

        self._counter += 1
        self.orders.append(order)
        cart.clear()

        return order

    def search(self, keyword: str) -> list[dict]:
        keyword = keyword.strip().lower()
        return [
            order for order in self.orders
            if keyword in order["id"].lower() or keyword in order["customer"].lower()
        ]

    def sort(self, field: str) -> None:
        if field == "Order ID":
            self.orders.sort(key=lambda o: o["id"])
        elif field == "Customer":
            self.orders.sort(key=lambda o: o["customer"])
        elif field == "Date":
            self.orders.sort(key=lambda o: o["date"])
        elif field == "Amount":
            self.orders.sort(key=lambda o: o["amount"])

    def to_json(self) -> list[dict]:
        return list(self.orders)

    def load_json(self, rows: list[dict]) -> None:
        if not rows:
            return

        self.orders = list(rows)
        numbers = [
            int(order["id"].replace("ORD", ""))
            for order in self.orders
            if order["id"].startswith("ORD") and order["id"][3:].isdigit()
        ]

        if numbers:
            self._counter = max(numbers) + 1


class PersistenceManager:
    """Single combined JSON persistence layer for users, cart, wishlist, orders."""

    def __init__(self, path: Path = DATA_FILE):
        self.path = path

    def load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except json.JSONDecodeError:
                return {}
        return {}

    @log_call
    def save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2))


# =============================================================================
# THEME MANAGER - Baby Pink & Light Purple palette
# =============================================================================
class ThemeManager:
    THEME = {
        "bg": "#FFF0F5",
        "sidebar_bg": "#B497D6",
        "sidebar_fg": "#FFFFFF",
        "sidebar_active": "#9B7EBD",
        "card_bg": "#FFFFFF",
        "card_border": "#F4C2C2",
        "text_primary": "#4A3B5C",
        "text_muted": "#8A7C99",
        "accent": "#F7B7D1",
        "accent_purple": "#C9A8E9",
        "success": "#4CAF50",
        "warning": "#E5989B",
        "error": "#D14D72",
    }

    @property
    def colors(self) -> dict:
        return self.THEME


# =============================================================================
# MAIN APPLICATION - single tk.Tk() root, sidebar + swappable content frame
# =============================================================================
class StoreApp:
    WIDTH = 1300
    HEIGHT = 780

    def __init__(self, root: tk.Tk):
        self.root = root
        self.theme = ThemeManager()
        self.c = self.theme.colors

        # ---------------- Service layer ---------------- #
        self.persistence = PersistenceManager()
        self.users = UserStore()
        self.catalog = ProductCatalog()
        self.cart = CartService()
        self.wishlist = WishlistService(self.cart)
        self.orders = OrderService()

        self._load_saved_data()

        # ---------------- Session state ---------------- #
        self.session_user: dict | None = None
        self.sidebar_frame: tk.Frame | None = None
        self.nav_buttons: dict[str, tk.Button] = {}
        self.cart_nav_btn: tk.Button | None = None
        self.wishlist_nav_btn: tk.Button | None = None
        self._toast_job = None

        self._configure_window()
        self._build_content_only()
        self.show_welcome()

    # ------------------------------------------------------------ Startup
    def _load_saved_data(self) -> None:
        data = self.persistence.load()

        if data.get("users"):
            self.users.load_json(data["users"])
        if data.get("cart"):
            self.cart.load_json(data["cart"])
        if data.get("wishlist"):
            self.wishlist.load_json(data["wishlist"])
        if data.get("orders"):
            self.orders.load_json(data["orders"])

    # ------------------------------------------------------------ Window
    def _configure_window(self) -> None:
        self.root.title("Professional E-Commerce Store")
        self.root.configure(bg=self.c["bg"])
        self.root.minsize(self.WIDTH, self.HEIGHT)
        self._center_window()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _center_window(self) -> None:
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (self.WIDTH // 2)
        y = (self.root.winfo_screenheight() // 2) - (self.HEIGHT // 2)
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

    def _build_content_only(self) -> None:
        """Pre-auth layout: content frame fills the whole window, no sidebar."""
        self.content = tk.Frame(self.root, bg=self.c["bg"])
        self.content.pack(side="left", fill="both", expand=True)

    # -------------------------------------------------------------- Hover
    def _bind_hover(self, widget, normal_bg: str, hover_bg: str | None = None) -> None:
        hover_bg = hover_bg or self.c["accent_purple"]
        widget.bind("<Enter>", lambda e: widget.configure(bg=hover_bg, cursor="hand2"))
        widget.bind("<Leave>", lambda e: widget.configure(bg=normal_bg))

    # ------------------------------------------------------- Panel helpers
    def _clear_content(self) -> None:
        for widget in self.content.winfo_children():
            widget.destroy()

    def _panel_header(self, parent, text: str, subtitle: str = "") -> None:
        tk.Label(
            parent, text=text, font=("Segoe UI", 20, "bold"),
            bg=self.c["bg"], fg=self.c["text_primary"],
        ).pack(anchor="w", padx=24, pady=(18, 2))

        if subtitle:
            tk.Label(
                parent, text=subtitle, font=("Segoe UI", 10),
                bg=self.c["bg"], fg=self.c["text_muted"],
            ).pack(anchor="w", padx=24, pady=(0, 10))

    def _button(self, parent, text: str, command, bg: str, fg: str = "white", width: int = 16) -> tk.Button:
        btn = tk.Button(
            parent, text=text, command=command, width=width,
            bg=bg, fg=fg, font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
        )
        self._bind_hover(btn, bg)
        return btn

    def _toast(self, parent, message: str, kind: str = "success") -> None:
        """Toast-style inline confirmation, auto-fades after 2.2 seconds."""
        colors = {
            "success": self.c["success"], "warning": self.c["warning"],
            "error": self.c["error"], "info": self.c["accent_purple"],
        }
        toast = tk.Label(
            parent, text=message, bg=colors.get(kind, self.c["success"]), fg="white",
            font=("Segoe UI", 10, "bold"), padx=14, pady=8, anchor="w",
        )
        toast.pack(fill="x", padx=24, pady=(0, 8))
        parent.after(2200, lambda: toast.destroy() if toast.winfo_exists() else None)

    def _empty_state(self, parent, icon: str, text: str) -> None:
        frame = tk.Frame(parent, bg=self.c["bg"])
        frame.pack(fill="both", expand=True, pady=60)
        tk.Label(
            frame, text=icon, bg=self.c["bg"], font=("Segoe UI Emoji", 48),
        ).pack()
        tk.Label(
            frame, text=text, bg=self.c["bg"], fg=self.c["text_muted"],
            font=("Segoe UI", 12),
        ).pack(pady=8)

    def _make_scrollable(self, parent) -> tk.Frame:
        container = tk.Frame(parent, bg=self.c["bg"])
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=self.c["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True, padx=(24, 0))

        inner = tk.Frame(canvas, bg=self.c["bg"])
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        inner.container = container  # outermost frame; destroy this to tear the whole thing down
        return inner

    def _styled_treeview(self, parent, columns: list[str], height: int = 12) -> ttk.Treeview:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Store.Treeview", background=self.c["card_bg"], fieldbackground=self.c["card_bg"],
            foreground=self.c["text_primary"], rowheight=30, font=("Segoe UI", 10),
        )
        style.configure(
            "Store.Treeview.Heading", background=self.c["sidebar_bg"], foreground="white",
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Store.Treeview", background=[("selected", self.c["accent_purple"])])

        tree = ttk.Treeview(parent, columns=columns, show="headings", style="Store.Treeview", height=height)

        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, anchor="center", width=150)

        return tree

    # ======================================================================
    # SESSION / SIDEBAR
    # ======================================================================
    def _enter_app(self, user: dict) -> None:
        """Called after a successful login/registration. Builds the sidebar
        and swaps into the connected, state-shared part of the application."""
        self.session_user = user
        self.content.pack_forget()
        self._build_sidebar()
        self.content = tk.Frame(self.root, bg=self.c["bg"])
        self.content.pack(side="left", fill="both", expand=True)
        self.show_products()

    def _exit_app_session(self) -> None:
        """Logout: tear down the sidebar and return to the pre-auth Welcome screen."""
        self.session_user = None

        if self.sidebar_frame is not None:
            self.sidebar_frame.destroy()
            self.sidebar_frame = None

        self.content.pack_forget()
        self.content = tk.Frame(self.root, bg=self.c["bg"])
        self.content.pack(side="left", fill="both", expand=True)
        self.show_welcome()

    def _build_sidebar(self) -> None:
        c = self.c
        sidebar = tk.Frame(self.root, bg=c["sidebar_bg"], width=250)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self.sidebar_frame = sidebar

        # ---------------- Session-aware header: avatar + name ---------------- #
        initial = self.session_user["full_name"][0].upper() if self.session_user else "?"

        avatar = tk.Label(
            sidebar, text=initial, bg=c["sidebar_active"], fg="white",
            font=("Segoe UI", 20, "bold"), width=3, height=1,
        )
        avatar.pack(pady=(22, 6))

        tk.Label(
            sidebar, text=self.session_user["full_name"], bg=c["sidebar_bg"], fg="white",
            font=("Segoe UI", 12, "bold"), wraplength=210, justify="center",
        ).pack()

        tk.Label(
            sidebar, text="\U0001F6CD Baby Pink & Light Purple", bg=c["sidebar_bg"],
            fg=c["accent"], font=("Segoe UI", 8, "italic"),
        ).pack(pady=(2, 14))

        # ---------------- Global search bar ---------------- #
        search_frame = tk.Frame(sidebar, bg=c["sidebar_bg"])
        search_frame.pack(fill="x", padx=14, pady=(0, 14))

        self.global_search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=self.global_search_var, font=("Segoe UI", 10))
        search_entry.pack(fill="x", ipady=4)
        search_entry.bind("<Return>", lambda e: self._global_search())

        search_btn = tk.Button(
            search_frame, text="\U0001F50D Search Products", command=self._global_search,
            bg=c["accent"], fg=c["text_primary"], font=("Segoe UI", 9, "bold"),
            relief="flat", cursor="hand2",
        )
        search_btn.pack(fill="x", pady=(6, 0), ipady=4)
        self._bind_hover(search_btn, c["accent"])

        # ---------------- Navigation ---------------- #
        self.nav_buttons = {}

        nav_items = [
            ("\U0001F4CA Dashboard", self.show_dashboard),
            ("\U0001F6CD Products", self.show_products),
            ("cart", self.show_cart),
            ("wishlist", self.show_wishlist),
            ("\U0001F4E6 Orders", self.show_orders),
            ("\U0001F464 Profile", self.show_profile),
        ]

        for label, command in nav_items:
            if label == "cart":
                self.cart_nav_btn = self._add_nav_button(sidebar, "\U0001F6D2 Cart (0)", command, key="Cart")
            elif label == "wishlist":
                self.wishlist_nav_btn = self._add_nav_button(sidebar, "\u2764 Wishlist (0)", command, key="Wishlist")
            else:
                self._add_nav_button(sidebar, label, command, key=label)

        tk.Frame(sidebar, bg=c["sidebar_bg"]).pack(fill="y", expand=True)

        logout_btn = tk.Button(
            sidebar, text="\U0001F513 Logout", font=("Segoe UI", 11, "bold"), bd=0, relief="flat",
            bg=c["error"], fg="white", command=self.logout,
        )
        logout_btn.pack(fill="x", side="bottom", padx=14, pady=(4, 8), ipady=8)
        self._bind_hover(logout_btn, c["error"])

        exit_btn = tk.Button(
            sidebar, text="\u274C Exit Application", font=("Segoe UI", 10, "bold"), bd=0, relief="flat",
            bg=c["sidebar_active"], fg="white", command=self._on_close,
        )
        exit_btn.pack(fill="x", side="bottom", padx=14, pady=(0, 4), ipady=6)
        self._bind_hover(exit_btn, c["sidebar_active"])

        self._refresh_badges()

    def _add_nav_button(self, parent, label: str, command, key: str) -> tk.Button:
        c = self.c
        btn = tk.Button(
            parent, text=label, font=("Segoe UI", 11), bd=0, relief="flat", anchor="w", padx=18,
            bg=c["sidebar_bg"], fg=c["sidebar_fg"], activebackground=c["sidebar_active"],
            activeforeground="white", command=lambda: self._navigate(key, command),
        )
        btn.pack(fill="x", padx=10, pady=3, ipady=8)
        self._bind_hover(btn, c["sidebar_bg"], hover_bg=c["sidebar_active"])
        self.nav_buttons[key] = btn
        return btn

    def _navigate(self, key: str, command) -> None:
        for name, btn in self.nav_buttons.items():
            btn.configure(bg=self.c["sidebar_active"] if name == key else self.c["sidebar_bg"])
        command()

    def _refresh_badges(self) -> None:
        """Live badge counters -- the concrete proof that state is unified."""
        if self.cart_nav_btn is not None:
            self.cart_nav_btn.configure(text=f"\U0001F6D2 Cart ({self.cart.total_items()})")
        if self.wishlist_nav_btn is not None:
            self.wishlist_nav_btn.configure(text=f"\u2764 Wishlist ({len(self.wishlist.items)})")

    def _global_search(self) -> None:
        keyword = self.global_search_var.get().strip()
        self.show_products(prefill_keyword=keyword)

    # ======================================================================
    # WELCOME PANEL  (main.py)
    # ======================================================================
    def show_welcome(self) -> None:
        self._clear_content()
        c = self.c

        tk.Label(
            self.content, text="\U0001F6D2", bg=c["bg"], fg=c["accent_purple"],
            font=("Segoe UI Emoji", 80),
        ).pack(pady=(60, 10))

        tk.Label(
            self.content, text="Professional E-Commerce Store", bg=c["bg"], fg=c["text_primary"],
            font=("Segoe UI", 26, "bold"),
        ).pack(pady=(0, 6))

        tk.Label(
            self.content, text="Welcome to the Professional\nE-Commerce Desktop Application",
            bg=c["bg"], fg=c["text_muted"], justify="center", font=("Segoe UI", 13),
        ).pack(pady=10)

        button_frame = tk.Frame(self.content, bg=c["bg"])
        button_frame.pack(pady=30)

        login_btn = self._button(button_frame, "Login", self.show_login, c["accent_purple"], width=22)
        login_btn.pack(pady=8, ipady=6)

        register_btn = self._button(button_frame, "Register", self.show_register, c["accent"], fg=c["text_primary"], width=22)
        register_btn.pack(pady=8, ipady=6)

        exit_btn = self._button(button_frame, "Exit", self._on_close, c["error"], width=22)
        exit_btn.pack(pady=8, ipady=6)

        tk.Label(
            self.content, text="\u00A9 2026 Professional E-Commerce Store", bg=c["bg"],
            fg=c["text_muted"], font=("Segoe UI", 9),
        ).pack(side="bottom", pady=15)

    # ======================================================================
    # LOGIN PANEL  (login.py)
    # ======================================================================
    def show_login(self) -> None:
        self._clear_content()
        c = self.c
        self._panel_header(self.content, "\U0001F6D2 Customer Login")

        form = tk.Frame(self.content, bg=c["card_bg"], highlightbackground=c["card_border"], highlightthickness=1)
        form.pack(padx=140, pady=10, fill="x")

        tk.Label(form, text="Username", bg=c["card_bg"], fg=c["text_primary"], font=("Segoe UI", 11)).pack(
            anchor="w", padx=24, pady=(24, 5)
        )
        username_var = tk.StringVar()
        tk.Entry(form, textvariable=username_var, font=("Segoe UI", 12), width=34).pack(padx=24)

        tk.Label(form, text="Password", bg=c["card_bg"], fg=c["text_primary"], font=("Segoe UI", 11)).pack(
            anchor="w", padx=24, pady=(18, 5)
        )
        password_var = tk.StringVar()
        password_entry = tk.Entry(form, textvariable=password_var, font=("Segoe UI", 12), show="*", width=34)
        password_entry.pack(padx=24)

        show_password = tk.BooleanVar(value=False)

        def toggle_password():
            password_entry.config(show="" if show_password.get() else "*")

        tk.Checkbutton(
            form, text="Show Password", variable=show_password, command=toggle_password,
            bg=c["card_bg"], font=("Segoe UI", 10),
        ).pack(anchor="w", padx=22, pady=8)

        banner_holder = tk.Frame(form, bg=c["card_bg"])
        banner_holder.pack(fill="x", padx=24)

        def do_login(event=None):
            try:
                user = self.users.login(username_var.get(), password_var.get())
                self._enter_app(user)
            except AuthenticationError as exc:
                self._toast(banner_holder, str(exc), kind="error")
            except ValidationError as exc:
                self._toast(banner_holder, str(exc), kind="error")

        password_entry.bind("<Return>", do_login)

        button_frame = tk.Frame(form, bg=c["card_bg"])
        button_frame.pack(pady=20)

        self._button(button_frame, "Login", do_login, c["accent_purple"]).grid(row=0, column=0, padx=6, pady=6)
        self._button(button_frame, "Clear", lambda: (username_var.set(""), password_var.set("")), c["text_muted"]).grid(
            row=0, column=1, padx=6, pady=6
        )
        self._button(button_frame, "Register", self.show_register, c["accent"], fg=c["text_primary"]).grid(
            row=1, column=0, padx=6, pady=6
        )
        self._button(button_frame, "Back", self.show_welcome, c["sidebar_bg"]).grid(row=1, column=1, padx=6, pady=6)

    # ======================================================================
    # REGISTER PANEL  (register_window.py)
    # ======================================================================
    def show_register(self) -> None:
        self._clear_content()
        c = self.c
        self._panel_header(self.content, "\U0001F6D2 Customer Registration")

        outer = self._make_scrollable(self.content)

        form = tk.Frame(outer, bg=c["card_bg"], highlightbackground=c["card_border"], highlightthickness=1)
        form.pack(padx=(0, 24), pady=10, fill="x")

        full_name_var = tk.StringVar()
        username_var = tk.StringVar()
        email_var = tk.StringVar()
        phone_var = tk.StringVar()
        password_var = tk.StringVar()
        confirm_password_var = tk.StringVar()

        def labeled_entry(label_text, var, show=None):
            tk.Label(form, text=label_text, bg=c["card_bg"], fg=c["text_primary"], font=("Segoe UI", 11)).pack(
                anchor="w", padx=24, pady=(14, 4)
            )
            entry = tk.Entry(form, textvariable=var, font=("Segoe UI", 11), width=44, show=show or "")
            entry.pack(padx=24)
            return entry

        labeled_entry("Full Name", full_name_var)
        labeled_entry("Username", username_var)
        labeled_entry("Email", email_var)
        labeled_entry("Phone Number", phone_var)

        tk.Label(form, text="Address", bg=c["card_bg"], fg=c["text_primary"], font=("Segoe UI", 11)).pack(
            anchor="w", padx=24, pady=(14, 4)
        )
        address_box = tk.Text(form, width=44, height=3, font=("Segoe UI", 11))
        address_box.pack(padx=24)

        labeled_entry("Password", password_var, show="*")
        confirm_entry = labeled_entry("Confirm Password", confirm_password_var, show="*")

        banner_holder = tk.Frame(form, bg=c["card_bg"])
        banner_holder.pack(fill="x", padx=24)

        def do_register(event=None):
            try:
                user = self.users.register(
                    full_name_var.get(), username_var.get(), email_var.get(),
                    phone_var.get(), address_box.get("1.0", tk.END).strip(),
                    password_var.get(), confirm_password_var.get(),
                )
            except (ValidationError, DuplicateUsernameError) as exc:
                self._toast(banner_holder, str(exc), kind="error")
                return

            answer = messagebox.askyesno(
                "Registration Successful",
                f"Welcome, {user['full_name']}! Do you want to log in now?",
            )

            if answer:
                logged_in = self.users.login(user["username"], password_var.get())
                self._enter_app(logged_in)
            else:
                self.show_login()

        confirm_entry.bind("<Return>", do_register)

        button_frame = tk.Frame(form, bg=c["card_bg"])
        button_frame.pack(pady=20)

        self._button(button_frame, "Register", do_register, c["accent_purple"]).grid(row=0, column=0, padx=6, pady=6)
        self._button(
            button_frame, "Clear",
            lambda: [v.set("") for v in (full_name_var, username_var, email_var, phone_var, password_var, confirm_password_var)]
            or address_box.delete("1.0", tk.END),
            c["text_muted"],
        ).grid(row=0, column=1, padx=6, pady=6)
        self._button(button_frame, "Login", self.show_login, c["accent"], fg=c["text_primary"]).grid(
            row=1, column=0, padx=6, pady=6
        )
        self._button(button_frame, "Back", self.show_welcome, c["sidebar_bg"]).grid(row=1, column=1, padx=6, pady=6)

    # ======================================================================
    # DASHBOARD PANEL  (customer_dashboard.py)
    # ======================================================================
    def show_dashboard(self) -> None:
        self._clear_content()
        c = self.c
        self._panel_header(self.content, f"Welcome, {self.session_user['full_name']}", "Dashboard")

        # ---------------- Real stat cards ---------------- #
        stats_frame = tk.Frame(self.content, bg=c["bg"])
        stats_frame.pack(fill="x", padx=24, pady=(0, 16))

        my_orders = [o for o in self.orders.orders if o["customer"] == self.session_user["full_name"]]
        reward_points = int(sum(o["amount"] for o in my_orders) // 10) + 50

        statistics = [
            ("\U0001F6CD Orders", str(len(my_orders))),
            ("\U0001F6D2 Cart Items", str(self.cart.total_items())),
            ("\u2764 Wishlist", str(len(self.wishlist.items))),
            ("\u2B50 Reward Points", str(reward_points)),
        ]

        for title, value in statistics:
            card = tk.Frame(
                stats_frame, bg=c["card_bg"], width=220, height=110,
                highlightbackground=c["card_border"], highlightthickness=1,
            )
            card.pack(side="left", padx=12)
            card.pack_propagate(False)

            tk.Label(card, text=title, bg=c["card_bg"], fg=c["text_primary"], font=("Segoe UI", 12, "bold")).pack(
                pady=(18, 5)
            )
            tk.Label(card, text=value, bg=c["card_bg"], fg=c["accent_purple"], font=("Segoe UI", 22, "bold")).pack()

        tk.Label(
            self.content, text="Featured Products", bg=c["bg"], fg=c["text_primary"], font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", padx=24, pady=(6, 8))

        dashboard_toast_holder = tk.Frame(self.content, bg=c["bg"])
        dashboard_toast_holder.pack(fill="x", padx=24)

        products_frame = tk.Frame(self.content, bg=c["bg"])
        products_frame.pack(fill="x", padx=24)

        for product in self.catalog.all()[:4]:
            card = tk.Frame(
                products_frame, bg=c["card_bg"], width=220, height=230,
                highlightbackground=c["card_border"], highlightthickness=1,
            )
            card.pack(side="left", padx=10)
            card.pack_propagate(False)

            tk.Label(card, text=product["icon"], bg=c["card_bg"], font=("Segoe UI Emoji", 36)).pack(pady=(12, 5))
            tk.Label(card, text=product["name"], bg=c["card_bg"], fg=c["text_primary"], font=("Segoe UI", 12, "bold")).pack()
            tk.Label(card, text=f"${product['price']:.0f}", bg=c["card_bg"], fg=c["success"], font=("Segoe UI", 11)).pack(pady=4)

            self._button(
                card, "Add to Cart", lambda p=product: self._add_to_cart(p, dashboard_toast_holder),
                c["accent_purple"], width=14,
            ).pack(pady=10)

    # ======================================================================
    # PRODUCTS PANEL  (products.py)
    # ======================================================================
    def show_products(self, prefill_keyword: str = "", prefill_category: str = "All") -> None:
        self._clear_content()
        c = self.c

        top = tk.Frame(self.content, bg=c["sidebar_bg"], height=70)
        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Label(top, text="\U0001F6CD Product Catalog", bg=c["sidebar_bg"], fg="white", font=("Segoe UI", 18, "bold")).pack(
            side="left", padx=20
        )

        search_var = tk.StringVar(value=prefill_keyword)
        tk.Entry(top, textvariable=search_var, font=("Segoe UI", 11), width=26).pack(side="left", padx=15)

        category_var = tk.StringVar(value=prefill_category)
        category_combo = ttk.Combobox(
            top, textvariable=category_var, values=self.catalog.categories(), width=16, state="readonly",
        )
        category_combo.pack(side="left", padx=10)

        toast_holder = tk.Frame(self.content, bg=c["bg"])
        toast_holder.pack(fill="x")

        body_holder = {"frame": None}

        def render(keyword="", category="All"):
            if body_holder["frame"] is not None:
                body_holder["frame"].destroy()

            products = self.catalog.search(keyword, category)

            if not products:
                empty_frame = tk.Frame(self.content, bg=c["bg"])
                empty_frame.pack(fill="both", expand=True)
                body_holder["frame"] = empty_frame
                self._empty_state(empty_frame, "\U0001F50D", "No products match your search.")
                return

            inner = self._make_scrollable(self.content)
            body_holder["frame"] = inner.container
            self._render_product_grid(inner, products, toast_holder)

        def do_search():
            render(search_var.get(), category_var.get())

        def do_refresh():
            search_var.set("")
            category_var.set("All")
            render()

        self._button(top, "Search", do_search, "white", fg=c["text_primary"], width=10).pack(side="left", padx=5)
        self._button(top, "Refresh", do_refresh, "white", fg=c["text_primary"], width=10).pack(side="left", padx=5)

        render(prefill_keyword, prefill_category)

    def _render_product_grid(self, parent, products: list[dict], toast_target: tk.Frame) -> None:
        c = self.c
        columns = 3

        for index, product in enumerate(products):
            row, column = divmod(index, columns)

            card = tk.Frame(
                parent, bg=c["card_bg"], width=340, height=300,
                highlightbackground=c["card_border"], highlightthickness=1,
            )
            card.grid(row=row, column=column, padx=15, pady=15)
            card.grid_propagate(False)

            tk.Label(card, text=product["icon"], bg=c["card_bg"], font=("Segoe UI Emoji", 40)).pack(pady=(12, 5))
            tk.Label(card, text=product["name"], bg=c["card_bg"], fg=c["text_primary"], font=("Segoe UI", 13, "bold")).pack()
            tk.Label(
                card, text=f"Category : {product['category']}", bg=c["card_bg"], fg=c["text_muted"], font=("Segoe UI", 10),
            ).pack()
            tk.Label(
                card, text=f"Price : ${product['price']:.0f}", bg=c["card_bg"], fg=c["success"],
                font=("Segoe UI", 11, "bold"),
            ).pack()

            stock_color = c["success"] if product["stock"] == "In Stock" else (
                c["warning"] if product["stock"] == "Limited Stock" else c["error"]
            )
            tk.Label(card, text=f"Stock : {product['stock']}", bg=c["card_bg"], fg=stock_color, font=("Segoe UI", 10)).pack()
            tk.Label(card, text=f"Rating : {product['rating']}", bg=c["card_bg"], fg=c["accent_purple"], font=("Segoe UI", 10)).pack()
            tk.Label(
                card, text=product["description"], bg=c["card_bg"], fg=c["text_muted"], wraplength=290,
                justify="center", font=("Segoe UI", 9),
            ).pack(pady=5)

            button_frame = tk.Frame(card, bg=c["card_bg"])
            button_frame.pack(pady=8)

            self._button(
                button_frame, "View Details", lambda p=product: self._view_product_details(p),
                c["sidebar_bg"], width=11,
            ).grid(row=0, column=0, padx=3)
            self._button(
                button_frame, "Add to Cart", lambda p=product: self._add_to_cart(p, toast_target),
                c["success"], width=11,
            ).grid(row=0, column=1, padx=3)
            self._button(
                button_frame, "Wishlist", lambda p=product: self._add_to_wishlist(p, toast_target),
                c["accent"], fg=c["text_primary"], width=24,
            ).grid(row=1, column=0, columnspan=2, pady=6)

    def _view_product_details(self, product: dict) -> None:
        messagebox.showinfo(
            "Product Details",
            f"Product : {product['name']}\n\n"
            f"Category : {product['category']}\n"
            f"Price : ${product['price']:.2f}\n"
            f"Stock : {product['stock']}\n"
            f"Rating : {product['rating']}\n\n"
            f"{product['description']}",
        )

    def _add_to_cart(self, product: dict, toast_target: tk.Frame) -> None:
        """toast_target must be a pack-only container (never a grid-managed
        product card), otherwise Tkinter raises a geometry-manager conflict."""
        try:
            self.cart.add(product)
            self._refresh_badges()
            self._toast(toast_target, f"{product['name']} added to cart.", kind="success")
        except InsufficientStockError as exc:
            self._toast(toast_target, str(exc), kind="error")

    def _add_to_wishlist(self, product: dict, toast_target: tk.Frame) -> None:
        try:
            self.wishlist.add(product)
            self._refresh_badges()
            self._toast(toast_target, f"{product['name']} added to wishlist.", kind="info")
        except ValidationError as exc:
            self._toast(toast_target, str(exc), kind="warning")

    # ======================================================================
    # CART PANEL  (cart.py)
    # ======================================================================
    def show_cart(self) -> None:
        self._clear_content()
        c = self.c
        self._panel_header(self.content, "\U0001F6D2 Shopping Cart")

        toast_holder = tk.Frame(self.content, bg=c["bg"])
        toast_holder.pack(fill="x", padx=24)

        if not self.cart.items:
            self._empty_state(self.content, "\U0001F6D2", "Your cart is empty. Browse products to add items.")
            nav = tk.Frame(self.content, bg=c["bg"])
            nav.pack(pady=10)
            self._button(nav, "Continue Shopping", self.show_products, c["accent_purple"]).pack()
            return

        tree = self._styled_treeview(self.content, ["Product", "Price", "Quantity", "Subtotal"], height=12)
        tree.pack(padx=24, pady=10, fill="x")

        summary = tk.Frame(self.content, bg=c["card_bg"], highlightbackground=c["card_border"], highlightthickness=1)
        summary.pack(fill="x", padx=24, pady=10)

        total_items_label = tk.Label(
            summary, text="", bg=c["card_bg"], fg=c["text_primary"], font=("Segoe UI", 12, "bold"),
        )
        total_items_label.grid(row=0, column=0, padx=20, pady=10)

        total_price_label = tk.Label(
            summary, text="", bg=c["card_bg"], fg=c["success"], font=("Segoe UI", 12, "bold"),
        )
        total_price_label.grid(row=0, column=1, padx=20, pady=10)

        def reload():
            tree.delete(*tree.get_children())
            for item in self.cart.items:
                subtotal = item["price"] * item["quantity"]
                tree.insert("", tk.END, values=(item["name"], f"${item['price']:.2f}", item["quantity"], f"${subtotal:.2f}"))
            total_items_label.configure(text=f"Total Items : {self.cart.total_items()}")
            total_price_label.configure(text=f"Total Price : ${self.cart.total_price():.2f}")
            self._refresh_badges()

            if not self.cart.items:
                self.show_cart()

        def get_selected_name():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Selection Required", "Please select a product.")
                return None
            return tree.item(selected[0], "values")[0]

        def add_demo_product():
            self.cart.add({"name": "Wireless Mouse", "price": 40.0, "stock": "In Stock"})
            reload()
            self._toast(toast_holder, "Wireless Mouse added successfully.", kind="success")

        def remove_product():
            name = get_selected_name()
            if name is None:
                return
            self.cart.remove(name)
            reload()

        def increase_quantity():
            name = get_selected_name()
            if name is None:
                return
            self.cart.increase(name)
            reload()

        def decrease_quantity():
            name = get_selected_name()
            if name is None:
                return
            try:
                self.cart.decrease(name)
            except ValidationError as exc:
                messagebox.showwarning("Invalid Quantity", str(exc))
            reload()

        def clear_cart():
            if messagebox.askyesno("Clear Cart", "Do you want to remove all products?"):
                self.cart.clear()
                reload()

        def checkout():
            try:
                order = self.orders.place_order(self.cart, self.session_user["full_name"])
                self._refresh_badges()
                messagebox.showinfo(
                    "Checkout", f"Order {order['id']} placed successfully!\n\nTotal Amount: ${order['amount']:.2f}",
                )
                self.show_orders()
            except EmptyCartError as exc:
                messagebox.showwarning("Empty Cart", str(exc))

        button_frame = tk.Frame(self.content, bg=c["bg"])
        button_frame.pack(pady=10)

        self._button(button_frame, "Add Demo Product", add_demo_product, c["success"], width=17).grid(row=0, column=0, padx=4, pady=4)
        self._button(button_frame, "Remove Product", remove_product, c["error"], width=17).grid(row=0, column=1, padx=4, pady=4)
        self._button(button_frame, "Increase Qty", increase_quantity, c["accent_purple"], width=17).grid(row=0, column=2, padx=4, pady=4)
        self._button(button_frame, "Decrease Qty", decrease_quantity, c["warning"], width=17).grid(row=0, column=3, padx=4, pady=4)
        self._button(button_frame, "Clear Cart", clear_cart, c["sidebar_bg"], width=17).grid(row=0, column=4, padx=4, pady=4)

        nav_frame = tk.Frame(self.content, bg=c["bg"])
        nav_frame.pack(pady=(0, 10))

        self._button(nav_frame, "Continue Shopping", self.show_products, c["accent"], fg=c["text_primary"], width=20).grid(
            row=0, column=0, padx=6
        )
        self._button(nav_frame, "Checkout", checkout, c["success"], width=20).grid(row=0, column=1, padx=6)

        reload()

    # ======================================================================
    # WISHLIST PANEL  (wishlist.py)
    # ======================================================================
    def show_wishlist(self) -> None:
        self._clear_content()
        c = self.c

        header = tk.Frame(self.content, bg=c["sidebar_bg"], height=80)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="\u2764 Wishlist", bg=c["sidebar_bg"], fg="white", font=("Segoe UI", 20, "bold")).pack(
            side="left", padx=20
        )
        total_label = tk.Label(
            header, text=f"Saved Items : {len(self.wishlist.items)}", bg=c["sidebar_bg"], fg="white",
            font=("Segoe UI", 12, "bold"),
        )
        total_label.pack(side="right", padx=20)

        toast_holder = tk.Frame(self.content, bg=c["bg"])
        toast_holder.pack(fill="x")

        if not self.wishlist.items:
            self._empty_state(self.content, "\u2764", "Your wishlist is empty. Save products you love!")
            nav = tk.Frame(self.content, bg=c["bg"])
            nav.pack(pady=10)
            self._button(nav, "Continue Shopping", self.show_products, c["accent_purple"]).pack()
            return

        inner = self._make_scrollable(self.content)
        columns = 3

        for index, product in enumerate(self.wishlist.items):
            row, column = divmod(index, columns)

            card = tk.Frame(
                inner, bg=c["card_bg"], width=320, height=260,
                highlightbackground=c["card_border"], highlightthickness=1,
            )
            card.grid(row=row, column=column, padx=15, pady=15)
            card.grid_propagate(False)

            tk.Label(card, text=product.get("icon", "\U0001F5BC"), bg=c["card_bg"], font=("Segoe UI Emoji", 38)).pack(pady=(12, 5))
            tk.Label(card, text=product["name"], bg=c["card_bg"], fg=c["text_primary"], font=("Segoe UI", 13, "bold")).pack()
            tk.Label(
                card, text=f"Category : {product.get('category', '-')}", bg=c["card_bg"], fg=c["text_muted"],
                font=("Segoe UI", 10),
            ).pack()
            tk.Label(
                card, text=f"Price : ${product['price']:.0f}", bg=c["card_bg"], fg=c["success"], font=("Segoe UI", 11, "bold"),
            ).pack(pady=5)

            def move_to_cart(name=product["name"]):
                try:
                    self.wishlist.move_to_cart(name)
                    self._refresh_badges()
                    self._toast(toast_holder, f"{name} moved to Shopping Cart.", kind="success")
                    self.root.after(600, self.show_wishlist)
                except ProductNotFoundError as exc:
                    self._toast(toast_holder, str(exc), kind="error")
                except InsufficientStockError as exc:
                    self._toast(toast_holder, str(exc), kind="error")

            def remove(name=product["name"]):
                self.wishlist.remove(name)
                self._refresh_badges()
                self.show_wishlist()

            def view(p=product):
                messagebox.showinfo(
                    "Product Details", f"Product : {p['name']}\n\nCategory : {p.get('category', '-')}\nPrice : ${p['price']:.2f}",
                )

            button_frame = tk.Frame(card, bg=c["card_bg"])
            button_frame.pack(pady=10)

            self._button(button_frame, "Move to Cart", move_to_cart, c["success"], width=14).grid(row=0, column=0, padx=3)
            self._button(button_frame, "Remove", remove, c["error"], width=14).grid(row=0, column=1, padx=3)
            self._button(button_frame, "View Details", view, c["sidebar_bg"], width=30).grid(row=1, column=0, columnspan=2, pady=8)

    # ======================================================================
    # ORDERS PANEL  (orders.py)
    # ======================================================================
    def show_orders(self) -> None:
        self._clear_content()
        c = self.c
        self._panel_header(self.content, "\U0001F4E6 Order History")

        if not self.orders.orders:
            self._empty_state(self.content, "\U0001F4E6", "You have no orders yet.")
            return

        toolbar = tk.Frame(self.content, bg=c["bg"])
        toolbar.pack(fill="x", padx=24, pady=10)

        tk.Label(toolbar, text="Search:", bg=c["bg"], fg=c["text_primary"], font=("Segoe UI", 10, "bold")).pack(side="left")
        search_var = tk.StringVar()
        tk.Entry(toolbar, textvariable=search_var, width=26).pack(side="left", padx=5)

        tk.Label(toolbar, text="Sort By:", bg=c["bg"], fg=c["text_primary"], font=("Segoe UI", 10, "bold")).pack(
            side="left", padx=(20, 5)
        )
        sort_option = ttk.Combobox(
            toolbar, width=16, state="readonly", values=["Order ID", "Customer", "Date", "Amount"],
        )
        sort_option.current(0)
        sort_option.pack(side="left")

        tree_holder = tk.Frame(self.content, bg=c["bg"])
        tree_holder.pack(fill="both", expand=True, padx=24, pady=10)

        tree = self._styled_treeview(
            tree_holder, ["Order ID", "Customer", "Date", "Products", "Amount", "Payment", "Delivery"], height=14,
        )
        tree.pack(fill="both", expand=True)

        status_colors = {
            "Delivered": c["success"], "Shipped": c["accent_purple"],
            "Processing": c["accent_purple"], "Pending": c["warning"], "Cancelled": c["error"],
        }
        for status, color in status_colors.items():
            tree.tag_configure(status, foreground=color)

        def reload(orders=None):
            tree.delete(*tree.get_children())
            for order in (orders if orders is not None else self.orders.orders):
                tree.insert(
                    "", tk.END,
                    values=(order["id"], order["customer"], order["date"], order["products"],
                            f"${order['amount']:.2f}", order["payment"], order["delivery"]),
                    tags=(order["delivery"],),
                )

        def do_search():
            keyword = search_var.get().strip()
            reload(self.orders.search(keyword) if keyword else None)

        def do_sort():
            self.orders.sort(sort_option.get())
            reload()

        self._button(toolbar, "Search", do_search, c["accent_purple"], width=10).pack(side="left", padx=5)
        self._button(toolbar, "Sort", do_sort, c["success"], width=10).pack(side="left", padx=5)

        def get_selected_order():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Selection Required", "Please select an order.")
                return None
            order_id = tree.item(selected[0], "values")[0]
            for order in self.orders.orders:
                if order["id"] == order_id:
                    return order
            return None

        def view_details():
            order = get_selected_order()
            if order is None:
                return
            messagebox.showinfo(
                "Order Details",
                f"Order ID : {order['id']}\n\nCustomer : {order['customer']}\nDate : {order['date']}\n"
                f"Products : {order['products']}\nAmount : ${order['amount']:.2f}\n"
                f"Payment : {order['payment']}\nDelivery : {order['delivery']}",
            )

        def view_invoice():
            order = get_selected_order()
            if order is None:
                return
            messagebox.showinfo(
                "Invoice",
                f"Invoice for {order['id']}\n\nCustomer : {order['customer']}\nAmount : ${order['amount']:.2f}\n\n"
                "Thank you for shopping with us!",
            )

        def repeat_order():
            order = get_selected_order()
            if order is None:
                return

            added, skipped = [], []
            for raw_name in order["products"].split(","):
                name = raw_name.strip()
                try:
                    product = self.catalog.find(name)
                    self.cart.add(product)
                    added.append(name)
                except (ProductNotFoundError, InsufficientStockError) as exc:
                    skipped.append(f"{name} ({exc})")

            self._refresh_badges()

            summary = f"Added to cart: {', '.join(added) if added else 'none'}."
            if skipped:
                summary += f"\nSkipped: {', '.join(skipped)}."
            messagebox.showinfo("Repeat Order", summary)

        button_frame = tk.Frame(self.content, bg=c["bg"])
        button_frame.pack(pady=10)

        self._button(button_frame, "View Details", view_details, c["accent_purple"], width=18).grid(row=0, column=0, padx=5, pady=5)
        self._button(button_frame, "View Invoice", view_invoice, c["success"], width=18).grid(row=0, column=1, padx=5, pady=5)
        self._button(button_frame, "Repeat Order", repeat_order, c["warning"], width=18).grid(row=0, column=2, padx=5, pady=5)

        reload()

    # ======================================================================
    # PROFILE PANEL  (profile.py)
    # ======================================================================
    def show_profile(self) -> None:
        self._clear_content()
        c = self.c
        self._panel_header(self.content, "\U0001F464 Customer Profile", "Your registered account details")

        user = self.users.get_public(self.session_user["username"])

        form = tk.Frame(self.content, bg=c["card_bg"], highlightbackground=c["card_border"], highlightthickness=1)
        form.pack(padx=24, pady=10, fill="x")

        tk.Label(
            form, text=f"Username : {user['username']} (cannot be changed)", bg=c["card_bg"],
            fg=c["text_muted"], font=("Segoe UI", 10, "italic"),
        ).pack(anchor="w", padx=24, pady=(20, 10))

        full_name_var = tk.StringVar(value=user["full_name"])
        email_var = tk.StringVar(value=user["email"])
        phone_var = tk.StringVar(value=user["phone"])
        address_var = tk.StringVar(value=user["address"])

        entries: list[tk.Entry] = []

        def labeled_field(label_text, var):
            tk.Label(form, text=label_text, bg=c["card_bg"], fg=c["text_primary"], font=("Segoe UI", 11)).pack(
                anchor="w", padx=24, pady=(10, 4)
            )
            entry = tk.Entry(form, textvariable=var, font=("Segoe UI", 11), width=44, state="disabled")
            entry.pack(padx=24)
            entries.append(entry)
            return entry

        labeled_field("Full Name", full_name_var)
        labeled_field("Email", email_var)
        labeled_field("Phone", phone_var)
        labeled_field("Address", address_var)

        banner_holder = tk.Frame(form, bg=c["card_bg"])
        banner_holder.pack(fill="x", padx=24)

        def toggle_edit():
            new_state = "normal" if entries[0]["state"] == "disabled" else "disabled"
            for entry in entries:
                entry.configure(state=new_state)

        def save_profile():
            try:
                updated = self.users.update_profile(
                    self.session_user["username"], full_name=full_name_var.get(),
                    email=email_var.get(), phone=phone_var.get(), address=address_var.get(),
                )
                self.session_user = updated
                for entry in entries:
                    entry.configure(state="disabled")
                self._toast(banner_holder, "Profile updated successfully.", kind="success")
                if self.sidebar_frame is not None:
                    self._navigate("\U0001F464 Profile", self.show_profile)
            except ValidationError as exc:
                self._toast(banner_holder, str(exc), kind="error")

        button_frame = tk.Frame(form, bg=c["card_bg"])
        button_frame.pack(pady=16)

        self._button(button_frame, "Edit", toggle_edit, c["accent"], fg=c["text_primary"]).grid(row=0, column=0, padx=6)
        self._button(button_frame, "Save", save_profile, c["success"]).grid(row=0, column=1, padx=6)

        # ---------------- Change Password ---------------- #
        pw_card = tk.Frame(self.content, bg=c["card_bg"], highlightbackground=c["card_border"], highlightthickness=1)
        pw_card.pack(padx=24, pady=10, fill="x")

        tk.Label(
            pw_card, text="Change Password", bg=c["card_bg"], fg=c["text_primary"], font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", padx=24, pady=(16, 10))

        old_pw = tk.StringVar()
        new_pw = tk.StringVar()
        confirm_pw = tk.StringVar()

        def pw_field(label_text, var):
            tk.Label(pw_card, text=label_text, bg=c["card_bg"], fg=c["text_primary"], font=("Segoe UI", 10)).pack(
                anchor="w", padx=24, pady=(6, 2)
            )
            tk.Entry(pw_card, textvariable=var, font=("Segoe UI", 11), width=34, show="*").pack(padx=24)

        pw_field("Current Password", old_pw)
        pw_field("New Password", new_pw)
        pw_field("Confirm New Password", confirm_pw)

        pw_banner_holder = tk.Frame(pw_card, bg=c["card_bg"])
        pw_banner_holder.pack(fill="x", padx=24)

        def change_password():
            try:
                self.users.change_password(
                    self.session_user["username"], old_pw.get(), new_pw.get(), confirm_pw.get(),
                )
                old_pw.set("")
                new_pw.set("")
                confirm_pw.set("")
                self._toast(pw_banner_holder, "Password changed successfully.", kind="success")
            except (AuthenticationError, ValidationError) as exc:
                self._toast(pw_banner_holder, str(exc), kind="error")

        self._button(pw_card, "Change Password", change_password, c["error"]).pack(pady=16)

    # ======================================================================
    # LOGOUT / EXIT
    # ======================================================================
    def logout(self) -> None:
        if messagebox.askyesno("Logout", "Do you want to logout?"):
            self._exit_app_session()

    # ------------------------------------------------------------ Exit
    def _on_close(self) -> None:
        answer = messagebox.askyesno("Exit", "Do you really want to exit?")
        if not answer:
            return

        self.persistence.save({
            "users": self.users.to_json(),
            "cart": self.cart.to_json(),
            "wishlist": self.wishlist.to_json(),
            "orders": self.orders.to_json(),
        })
        self.root.destroy()


# =============================================================================
# ENTRY POINT
# =============================================================================
def main() -> None:
    root = tk.Tk()
    StoreApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
