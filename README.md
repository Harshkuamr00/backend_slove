# SOLUTIONS

## Part 1: Code Review & Debugging - Issues & Fixes

### Issues Identified

1.  **No error handling for missing or invalid data**
    *   **Impact:** If required fields are missing from the JSON payload, the code will throw a `KeyError`. No validation of data types (e.g., ensuring price is a number, `warehouse_id` is valid).

2.  **No SKU uniqueness validation**
    *   **Impact:** Duplicate SKUs can be created, violating the business requirement that SKUs must be unique across the platform. This causes data integrity issues and confusion in inventory tracking.

3.  **No transaction rollback on partial failure**
    *   **Impact:** If an error occurs after adding product but before adding inventory, the product is created but inventory record doesn't exist. This creates orphaned data and inconsistent state.

4.  **No validation that warehouse exists**
    *   **Impact:** Foreign key constraint might fail at commit time, but there's no explicit check. Invalid `warehouse_id` could be inserted, or validation error only appears during commit.

5.  **Assumes `initial_quantity` field exists**
    *   **Impact:** If `initial_quantity` is not provided in the request, `KeyError` will be thrown. No default value or optional handling.

6.  **No response validation or HTTP status codes**
    *   **Impact:** Always returns 200 even if data is invalid. No distinction between successful creation and error cases for client.

7.  **Database session not closed on errors**
    *   **Impact:** In case of exception, session might remain open or in failed state, causing resource leaks.

### Key Improvements

1.  Input validation for all required fields before database operations.
2.  Type checking and conversion for numeric fields.
3.  Explicit warehouse existence check before operations.
4.  Use of `db.session.flush()` to detect constraint violations early.
5.  Proper exception handling with `IntegrityError` catching for SKU uniqueness.
6.  Transaction rollback on any error to maintain consistency.
7.  HTTP status codes (201 for creation, 400 for validation, 409 for conflict, 404 for not found).
8.  Defensive programming: optional fields with defaults.
9.  Detailed error messages for debugging.
10. Resource cleanup with rollback on exceptions.

---

## Part 2: Missing Requirements Questions & Design

### Missing Requirements Questions to Ask Product Team

1.  **Sales/Order Tracking:** Do you need to track customer orders? Should inventory decrement based on orders?
2.  **Multi-warehouse transfers:** Can products be transferred between warehouses? Do we need transfer history?
3.  **Batch/Expiry tracking:** Do products have expiry dates or batch numbers for perishable goods?
4.  **Product variants:** Do products have sizes/colors/variants that need separate SKUs and inventory?
5.  **Supplier contracts:** Are there contract terms, pricing tiers, or volume discounts?
6.  **Inventory reservations:** Should we support reserving inventory for pending orders?
7.  **Reorder points:** What triggers automatic reorder suggestions?
8.  **Return management:** How are returned products handled in inventory?
9.  **Audit requirements:** How long should we keep historical data? Compliance requirements?
10. **User roles/permissions:** Different access levels for warehouse staff, managers, suppliers?
11. **Multi-currency:** Do suppliers operate in different currencies?
12. **Real-time sync:** Do supplier systems sync in real-time or batch?

### Design Justification

1.  **Separate Company and Warehouse tables:** Allows proper multi-tenancy and company-specific configurations.
2.  **Product table without `warehouse_id`:** Products are company-level entities that can exist in multiple warehouses.
3.  **Inventory table with UNIQUE constraint on (`product_id`, `warehouse_id`):** Ensures single inventory record per product-warehouse combination.
4.  **`InventoryHistory` for audit trail:** Tracks all quantity changes for compliance and debugging.
5.  **`ProductBundle` table with recursive structure:** Supports "bundle" product type for composite products.
6.  **Indexes on frequently queried columns:** `warehouse_id` for warehouse lookups, `product_id` + `quantity` for low-stock queries.
7.  **`SupplierProduct` as junction table:** Handles many-to-many relationship between suppliers and products.
8.  **`lead_time_days` and `minimum_order_quantity`:** Critical for reorder logic.
9.  **`LOW_STOCK_THRESHOLD` in Inventory:** Product-warehouse specific threshold (varies by location/demand).
10. **`change_reason` field:** Important for understanding inventory changes (sales vs adjustments vs restocks).

---

## Part 3: API Implementation - Low Stock Alerts Endpoint

### Assumptions Made

1.  Low stock threshold varies by product type (defined in `Product.product_type`).
2.  "Recent sales activity" means products with sales in the last 30 days.
3.  Multiple warehouses per company need to be aggregated.
4.  Response should include supplier info for quick reordering.
5.  Alert severity based on how close to threshold (urgent if < 50% of threshold).
6.  Stock level = quantity in `Inventory` table.

### Edge Cases Handled

1.  **Company doesn't exist:** Returns 404.
2.  **No warehouses for company:** Returns empty alerts list.
3.  **No suppliers for product:** Returns alert with empty suppliers array.
4.  **No sales history:** Respects `include_no_sales` flag.
5.  **Invalid query parameters:** Returns 400 with error message.
6.  **Null inventory quantities:** Treats as 0.
7.  **Multiple warehouse aggregation:** Sums quantities across all warehouses.
8.  **Floating point precision:** Uses `Decimal` for costs.
9.  **Timezone handling:** Uses UTC for consistency.
10. **Large datasets:** Uses indexed queries for performance.

### Optimizations

1.  Indexes on (`product_id`, `warehouse_id`) in Inventory for fast lookups.
2.  Index on `change_reason` and `changed_at` in InventoryHistory for filtering sales.
3.  `Company_id` index in Warehouse for multi-tenant queries.
4.  Sorted results by severity for immediate actionability.
5.  Parameterized thresholds allow override for different business rules.
6.  Query caching could be added for frequently accessed data.
