"""
GLOW — Natural Beauty
FastAPI backend: auth, products, wishlist, cart, orders.

Local run:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Deployed on Render:
    Start command -> uvicorn main:app --host 0.0.0.0 --port $PORT
    See README.md for the full step-by-step deployment guide.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week

# Comma-separated list of allowed frontend origins, e.g.
# "https://your-app.vercel.app,http://localhost:5500"
FRONTEND_ORIGINS = os.environ.get("FRONTEND_ORIGIN", "https://glow-store-dusky.vercel.app")
ALLOWED_ORIGINS = (
    [o.strip() for o in FRONTEND_ORIGINS.split(",")]
    if FRONTEND_ORIGINS != "*"
    else ["*"]
)

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./store.db")
# Render's Postgres add-on gives a "postgres://" URL; SQLAlchemy 1.4+/2.0 wants "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    image = Column(String, nullable=False)  # e.g. "images/vitamin-c-serum.jpg"


class WishlistItem(Base):
    __tablename__ = "wishlist_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)

    product = relationship("Product")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total = Column(Float, nullable=False)
    status = Column(String, default="Placed")
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    name = Column(String, nullable=False)   # snapshot at time of purchase
    price = Column(Float, nullable=False)   # snapshot at time of purchase
    quantity = Column(Integer, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")


Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# Seed catalog — same products as the Glow reference design
# ---------------------------------------------------------------------------

SEED_PRODUCTS = [
    {"name": "Vitamin C Glow Serum",       "category": "Serum",       "price": 350, "image": "images/vitamin.jpg"},
    {"name": "Niacinamide 10% Serum",      "category": "Serum",       "price": 250, "image": "images/serum.jpg"},
    {"name": "Hyaluronic Acid Moisturizer","category": "Moisturizer", "price": 550, "image": "images/hydro.jpg"},
    {"name": "Aloevera Cream",             "category": "Moisturizer", "price": 450, "image": "images/aleo.jpg"},
    {"name": "Night Cream",                "category": "Moisturizer", "price": 299, "image": "images/night.jpg"},
    {"name": "Foaming Face Cleanser",      "category": "Cleanser",    "price": 449, "image": "images/wash.jpg"},
    {"name": "SPF 50 Sunscreen Gel",       "category": "Sunscreen",   "price": 399, "image": "images/sun.jpg"},
    {"name": "Rose Water Face Mist",       "category": "Toner",       "price": 249, "image": "images/water.jpg"},
    {"name": "Lip treatment Balm",         "category": "Lip Care",    "price": 150, "image": "images/lip.jpg"},
    {"name": "Lip Mask",                   "category": "Lip Care",    "price": 250, "image": "images/mask.jpg"},
]


def seed_if_empty():
    db = SessionLocal()
    try:
        if db.query(Product).count() == 0:
            for p in SEED_PRODUCTS:
                db.add(Product(**p))
            db.commit()
    finally:
        db.close()


seed_if_empty()

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ProductOut(BaseModel):
    id: int
    name: str
    category: str
    price: float
    image: str

    class Config:
        from_attributes = True


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=4, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class MeOut(BaseModel):
    id: int
    username: str


class WishlistItemOut(BaseModel):
    id: int
    product: ProductOut

    class Config:
        from_attributes = True


class WishlistCreate(BaseModel):
    product_id: int


class CartItemOut(BaseModel):
    id: int
    quantity: int
    product: ProductOut

    class Config:
        from_attributes = True


class CartCreate(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


class CartUpdate(BaseModel):
    quantity: int = Field(ge=1)


class OrderItemOut(BaseModel):
    id: int
    name: str
    price: float
    quantity: int

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: int
    total: float
    status: str
    created_at: datetime
    items: List[OrderItemOut]

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# App + auth helpers
# ---------------------------------------------------------------------------

app = FastAPI(title="Glow Store API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    authorization: str = Header(default=None), db: Session = Depends(get_db)
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not authorization or not authorization.startswith("Bearer "):
        raise credentials_error
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_error
    except jwt.PyJWTError:
        raise credentials_error

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_error
    return user


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------


@app.post("/auth/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    user = User(username=payload.username, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.username)
    return TokenOut(access_token=token, username=user.username)


@app.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(user.username)
    return TokenOut(access_token=token, username=user.username)


@app.get("/auth/me", response_model=MeOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ---------------------------------------------------------------------------
# Product routes (public)
# ---------------------------------------------------------------------------


@app.get("/products", response_model=List[ProductOut])
def list_products(category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Product)
    if category and category.lower() != "all":
        query = query.filter(Product.category.ilike(category))
    return query.all()


# ---------------------------------------------------------------------------
# Wishlist routes (auth required)
# ---------------------------------------------------------------------------


@app.get("/wishlist", response_model=List[WishlistItemOut])
def get_wishlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(WishlistItem).filter(WishlistItem.user_id == user.id).all()


@app.post("/wishlist", response_model=WishlistItemOut, status_code=201)
def add_to_wishlist(
    payload: WishlistCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = (
        db.query(WishlistItem)
        .filter(WishlistItem.user_id == user.id, WishlistItem.product_id == payload.product_id)
        .first()
    )
    if existing:
        return existing

    item = WishlistItem(user_id=user.id, product_id=payload.product_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/wishlist/{product_id}", status_code=204)
def remove_from_wishlist(
    product_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(WishlistItem)
        .filter(WishlistItem.user_id == user.id, WishlistItem.product_id == product_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not in wishlist")
    db.delete(item)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Cart routes (auth required)
# ---------------------------------------------------------------------------


@app.get("/cart", response_model=List[CartItemOut])
def get_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(CartItem).filter(CartItem.user_id == user.id).all()


@app.post("/cart", response_model=CartItemOut, status_code=201)
def add_to_cart(
    payload: CartCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = (
        db.query(CartItem)
        .filter(CartItem.user_id == user.id, CartItem.product_id == payload.product_id)
        .first()
    )
    if existing:
        existing.quantity += payload.quantity
        db.commit()
        db.refresh(existing)
        return existing

    item = CartItem(user_id=user.id, product_id=payload.product_id, quantity=payload.quantity)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.patch("/cart/{item_id}", response_model=CartItemOut)
def update_cart_item(
    item_id: int,
    payload: CartUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    item.quantity = payload.quantity
    db.commit()
    db.refresh(item)
    return item


@app.delete("/cart/{item_id}", status_code=204)
def remove_cart_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    db.delete(item)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Order routes (auth required)
# ---------------------------------------------------------------------------


@app.get("/orders", response_model=List[OrderOut])
def list_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Order)
        .filter(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .all()
    )


@app.post("/orders/checkout", response_model=OrderOut, status_code=201)
def checkout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart_items = db.query(CartItem).filter(CartItem.user_id == user.id).all()
    if not cart_items:
        raise HTTPException(status_code=400, detail="Your cart is empty")

    total = sum(ci.product.price * ci.quantity for ci in cart_items)
    order = Order(user_id=user.id, total=total, status="Placed")
    db.add(order)
    db.flush()  # get order.id before commit

    for ci in cart_items:
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=ci.product_id,
                name=ci.product.name,
                price=ci.product.price,
                quantity=ci.quantity,
            )
        )
        db.delete(ci)

    db.commit()
    db.refresh(order)
    return order


@app.get("/")
def root():
    return {"status": "ok", "service": "Glow Store API"}


@app.get("/health")
def health():
    return {"status": "healthy"}