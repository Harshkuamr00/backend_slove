from flask import Flask, request, jsonify
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, func
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta

# Import models
from models import (
    db, Company, Warehouse, Product, Inventory, 
    InventoryHistory, Supplier, SupplierProduct
)

app = Flask(__name__)

# --- Configuration ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db' # Using SQLite for simplicity
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize DB with App
db.init_app(app)

# Create tables before first request
with app.app_context():
    db.create_all()

# --- API Constants ---
STOCK_THRESHOLDS = {
    'standard': 20,
    'bundle': 10,
    'default': 15
}

# --- Routes ---

@app.route('/api/products', methods=['POST'])
def create_product():
    try:
        data = request.json

        # 1. Input validation
        required_fields = ['name', 'sku', 'price', 'warehouse_id']
        for field in required_fields:
            if field not in data or data[field] is None:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # 2. Validate and parse price
        try:
            price = Decimal(str(data['price']))
            if price < 0:
                return jsonify({'error': 'Price cannot be negative'}), 400
        except InvalidOperation:
            return jsonify({'error': 'Price must be a valid decimal number'}), 400

        # 3. Validate warehouse_id
        try:
            warehouse_id = int(data['warehouse_id'])
        except (ValueError, TypeError):
            return jsonify({'error': 'warehouse_id must be an integer'}), 400

        # 4. Optional field validation
        initial_quantity = data.get('initial_quantity', 0)
        try:
            initial_quantity = int(initial_quantity)
            if initial_quantity < 0:
                return jsonify({'error': 'Quantity cannot be negative'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'initial_quantity must be an integer'}), 400

        # 5. Check warehouse existence
        warehouse = Warehouse.query.get(warehouse_id)
        if not warehouse:
            return jsonify({'error': f'Warehouse {warehouse_id} does not exist'}), 404

        # 6. Create Product
        product = Product(
            name=data['name'],
            sku=data['sku'],
            base_price=price,
            product_type=data.get('product_type', 'standard')
        )
        
        db.session.add(product)
        
        try:
            db.session.flush() # Check SKU uniqueness here
        except IntegrityError as e:
            db.session.rollback()
            if 'unique' in str(e.orig).lower():
                return jsonify({'error': 'SKU already exists'}), 409
            return jsonify({'error': 'Database constraint violation'}), 400

        # 7. Create Inventory Record
        inventory = Inventory(
            product_id=product.product_id,
            warehouse_id=warehouse_id,
            quantity=initial_quantity
        )
        db.session.add(inventory)

        # 8. Commit Transaction
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify({'error': 'Failed to create inventory record'}), 500

        return jsonify({
            'message': 'Product created successfully',
            'product_id': product.product_id,
            'sku': product.sku,
            'warehouse_id': warehouse_id
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@app.route('/api/companies/<int:company_id>/alerts/low-stock', methods=['GET'])
def get_low_stock_alerts(company_id):
    try:
        # 1. Validate Company
        company = Company.query.get(company_id)
        if not company:
            return jsonify({'error': f'Company {company_id} not found'}), 404

        # 2. Parse Query Parameters
        threshold_percentage = request.args.get('threshold_override', default=100, type=int)
        include_no_sales = request.args.get('include_no_sales', default='false').lower() == 'true'
        days_back = request.args.get('days', default=30, type=int)

        if not (0 <= threshold_percentage <= 100):
            return jsonify({'error': 'threshold_override must be between 0 and 100'}), 400

        # 3. Get Warehouses
        warehouses = Warehouse.query.filter_by(company_id=company_id).all()
        if not warehouses:
            return jsonify({'alerts': [], 'total_alerts': 0, 'timestamp': datetime.utcnow().isoformat()}), 200
        
        warehouse_ids = [w.warehouse_id for w in warehouses]
        date_threshold = datetime.utcnow() - timedelta(days=days_back)

        # 4. Query Low Stock Products (Aggregation)
        low_stock_query = db.session.query(
            Product.product_id,
            Product.name,
            Product.sku,
            Product.product_type,
            func.sum(Inventory.quantity).label('total_quantity')
        ).join(
            Inventory, Product.product_id == Inventory.product_id
        ).filter(
            Inventory.warehouse_id.in_(warehouse_ids)
        ).group_by(
            Product.product_id, Product.name, Product.sku, Product.product_type
        )

        alerts = []

        for product in low_stock_query.all():
            p_id, name, sku, p_type, total_qty = product
            total_qty = total_qty or 0

            # Determine Threshold
            base_threshold = STOCK_THRESHOLDS.get(p_type, STOCK_THRESHOLDS['default'])
            adjusted_threshold = (base_threshold * threshold_percentage) // 100

            if total_qty >= adjusted_threshold:
                continue

            # Check Sales Activity (if filtering enabled)
            if not include_no_sales:
                has_sales = db.session.query(InventoryHistory).join(Inventory).filter(
                    Inventory.product_id == p_id,
                    InventoryHistory.changed_at >= date_threshold,
                    InventoryHistory.change_reason == 'sale'
                ).first()
                
                if not has_sales:
                    continue

            # Calculate Severity
            if total_qty <= (adjusted_threshold * 0.5):
                severity = 'critical'
            elif total_qty <= (adjusted_threshold * 0.75):
                severity = 'high'
            else:
                severity = 'medium'

            # Fetch Detailed Context (Warehouses & Suppliers)
            warehouse_details = db.session.query(
                Warehouse.warehouse_id, Warehouse.location, Inventory.quantity
            ).join(Inventory).filter(
                Inventory.product_id == p_id,
                Warehouse.company_id == company_id
            ).all()

            supplier_details = db.session.query(
                Supplier.supplier_id, Supplier.name, Supplier.contact_email,
                SupplierProduct.lead_time_days, SupplierProduct.minimum_order_quantity,
                SupplierProduct.unit_cost
            ).join(SupplierProduct).filter(
                SupplierProduct.product_id == p_id
            ).all()

            # Build Alert Object
            alert = {
                'product_id': p_id,
                'product_name': name,
                'sku': sku,
                'total_quantity': total_qty,
                'low_stock_threshold': adjusted_threshold,
                'severity': severity,
                'warehouses': [
                    {'id': w.warehouse_id, 'loc': w.location, 'qty': w.quantity} 
                    for w in warehouse_details
                ],
                'suppliers': [
                    {
                        'name': s.name, 
                        'email': s.contact_email,
                        'lead_time': s.lead_time_days,
                        'cost': float(s.unit_cost) if s.unit_cost else None
                    } for s in supplier_details
                ]
            }
            alerts.append(alert)

        # Sort: Critical first
        severity_order = {'critical': 0, 'high': 1, 'medium': 2}
        alerts.sort(key=lambda x: severity_order.get(x['severity'], 3))

        return jsonify({
            'alerts': alerts,
            'total_alerts': len(alerts),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 200

    except Exception as e:
        app.logger.error(f"Alerts Error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
