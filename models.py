from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize SQLAlchemy
db = SQLAlchemy()

# --- Database Schema ---

class Company(db.Model):
    __tablename__ = 'company'
    company_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Warehouse(db.Model):
    __tablename__ = 'warehouse'
    warehouse_id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.company_id'), nullable=False, index=True)
    location = db.Column(db.String(255))
    capacity = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    __tablename__ = 'product'
    product_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    sku = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    base_price = db.Column(db.Numeric(10, 2), nullable=False)
    product_type = db.Column(db.Enum('standard', 'bundle', name='product_type_enum'), default='standard')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Indexes (Using __table_args__ for composite indexes if needed)
    __table_args__ = (db.Index('idx_product_type', 'product_type'),)

class Inventory(db.Model):
    __tablename__ = 'inventory'
    inventory_id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.product_id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.warehouse_id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    low_stock_threshold = db.Column(db.Integer)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('product_id', 'warehouse_id', name='uq_product_warehouse'),
        db.Index('idx_product_quantity', 'product_id', 'quantity'),
    )

class InventoryHistory(db.Model):
    __tablename__ = 'inventory_history'
    history_id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.inventory_id'), nullable=False, index=True)
    previous_quantity = db.Column(db.Integer)
    new_quantity = db.Column(db.Integer)
    change_reason = db.Column(db.String(255))
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    changed_by = db.Column(db.String(255))

class Supplier(db.Model):
    __tablename__ = 'supplier'
    supplier_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    contact_email = db.Column(db.String(255))
    contact_phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SupplierProduct(db.Model):
    __tablename__ = 'supplier_product'
    supplier_product_id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.supplier_id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.product_id'), nullable=False, index=True)
    lead_time_days = db.Column(db.Integer)
    minimum_order_quantity = db.Column(db.Integer)
    unit_cost = db.Column(db.Numeric(10, 2))

    __table_args__ = (
        db.UniqueConstraint('supplier_id', 'product_id', name='uq_supplier_product'),
    )
