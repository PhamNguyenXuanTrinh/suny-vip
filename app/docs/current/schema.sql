-- Generated from a fresh, migrated database. Quantity columns use exact integer millionths.

CREATE TABLE ai_conversations (
      id VARCHAR(36) PRIMARY KEY NOT NULL, organization_id VARCHAR(36) NOT NULL,
      user_id VARCHAR(36) NOT NULL,title VARCHAR(200) NOT NULL,created_at VARCHAR(32) NOT NULL,
      CONSTRAINT uq_ai_conversations_organization_id UNIQUE(organization_id,id), FOREIGN KEY(organization_id,user_id) REFERENCES app_users(organization_id,id));

CREATE TABLE ai_messages (
      id VARCHAR(36) PRIMARY KEY NOT NULL, organization_id VARCHAR(36) NOT NULL,
      conversation_id VARCHAR(36) NOT NULL,role VARCHAR(20) NOT NULL CHECK(role IN ('user','assistant')),
      content TEXT NOT NULL,sources_json TEXT,usage_json TEXT,status VARCHAR(20) NOT NULL,
      created_at VARCHAR(32) NOT NULL, FOREIGN KEY(organization_id,conversation_id) REFERENCES ai_conversations(organization_id,id));

CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

CREATE TABLE app_users (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	employee_id VARCHAR(36) NOT NULL, 
	username VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	is_active BOOLEAN DEFAULT 1 NOT NULL, 
	must_change_password BOOLEAN DEFAULT 1 NOT NULL, 
	failed_login_count BIGINT DEFAULT 0 NOT NULL, 
	locked_until VARCHAR(32), 
	last_login_at VARCHAR(32), 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_app_users PRIMARY KEY (id), 
	CHECK (is_active IN (0, 1)), 
	CHECK (must_change_password IN (0, 1)), 
	CONSTRAINT ck_app_users_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_app_users_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_app_users_organization_id_employees FOREIGN KEY(organization_id, employee_id) REFERENCES employees (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_username_normalized CHECK (username = lower(trim(username))), 
	CONSTRAINT ck_app_users_failed_login_count_integer CHECK (typeof(failed_login_count) = 'integer'), 
	CONSTRAINT ck_app_users_failed_login_count_nonnegative CHECK (failed_login_count >= 0), 
	CONSTRAINT uq_app_users_0 UNIQUE (employee_id), 
	CONSTRAINT uq_app_users_1 UNIQUE (username), 
	CONSTRAINT uq_app_users_2 UNIQUE (organization_id, id)
);

CREATE TABLE audit_log (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	actor_user_id VARCHAR(36), 
	action VARCHAR(80) NOT NULL, 
	entity_type VARCHAR(100) NOT NULL, 
	entity_id VARCHAR(36), 
	old_json TEXT, 
	new_json TEXT, 
	occurred_at VARCHAR(32) NOT NULL, 
	request_id VARCHAR(100), 
	ip_address VARCHAR(45), 
	CONSTRAINT pk_audit_log PRIMARY KEY (id), 
	CONSTRAINT ck_audit_log_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_audit_log_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_audit_log_organization_id_app_users FOREIGN KEY(organization_id, actor_user_id) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_audit_log_0 UNIQUE (organization_id, id)
);

CREATE TABLE auth_sessions (
        id VARCHAR(36) PRIMARY KEY NOT NULL, organization_id VARCHAR(36) NOT NULL,
        user_id VARCHAR(36) NOT NULL, family_id VARCHAR(36) NOT NULL,
        refresh_hash VARCHAR(64) NOT NULL, created_at VARCHAR(32) NOT NULL,
        expires_at VARCHAR(32) NOT NULL, revoked_at VARCHAR(32),
        CONSTRAINT uq_auth_sessions_refresh_hash UNIQUE(refresh_hash),
        FOREIGN KEY (organization_id,user_id) REFERENCES app_users(organization_id,id));

CREATE TABLE bills_of_materials (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	bom_code VARCHAR(60) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	version_no BIGINT DEFAULT 1 NOT NULL, 
	output_quantity BIGINT DEFAULT '0' NOT NULL, 
	effective_from DATE, 
	effective_to DATE, 
	status VARCHAR(30) DEFAULT 'draft' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_bills_of_materials PRIMARY KEY (id), 
	CONSTRAINT ck_bills_of_materials_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_bills_of_materials_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_bills_of_materials_organization_id_products FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_bills_of_materials_version_no_integer CHECK (typeof(version_no) = 'integer'), 
	CONSTRAINT ck_bills_of_materials_version_no_nonnegative CHECK (version_no >= 0), 
	CONSTRAINT ck_bills_of_materials_output_quantity_nonnegative CHECK (output_quantity >= 0), 
	CONSTRAINT ck_bills_of_materials_output_quantity_precision CHECK ((typeof(output_quantity) = 'integer' AND abs(output_quantity) < 1000000000000000000) OR output_quantity IS NULL), 
	CONSTRAINT ck_bills_of_materials_status_enum CHECK (status IN ('draft','active','obsolete')), 
	CONSTRAINT uq_bills_of_materials_0 UNIQUE (organization_id, bom_code, version_no), 
	CONSTRAINT uq_bills_of_materials_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_bills_of_materials_rule_0 CHECK (output_quantity > 0), 
	CONSTRAINT ck_bills_of_materials_rule_1 CHECK (version_no > 0), 
	CONSTRAINT ck_bills_of_materials_rule_2 CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from), 
	CONSTRAINT uq_bills_of_materials_paired_production_orders_0 UNIQUE (organization_id, id, product_id)
);

CREATE TABLE bom_lines (
	id VARCHAR(36) NOT NULL, 
	bom_id VARCHAR(36) NOT NULL, 
	line_no BIGINT NOT NULL, 
	component_product_id VARCHAR(36) NOT NULL, 
	quantity BIGINT DEFAULT '0' NOT NULL, 
	uom VARCHAR(20) NOT NULL, 
	scrap_rate BIGINT DEFAULT 0 NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	CONSTRAINT pk_bom_lines PRIMARY KEY (id), 
	CONSTRAINT ck_bom_lines_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_bom_lines_organization_id_bills_of_materials FOREIGN KEY(organization_id, bom_id) REFERENCES bills_of_materials (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_bom_lines_line_no_integer CHECK (typeof(line_no) = 'integer'), 
	CONSTRAINT ck_bom_lines_line_no_nonnegative CHECK (line_no >= 0), 
	CONSTRAINT ck_bom_lines_line_no_positive CHECK (line_no > 0), 
	CONSTRAINT fk_bom_lines_organization_id_products FOREIGN KEY(organization_id, component_product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_bom_lines_quantity_nonnegative CHECK (quantity >= 0), 
	CONSTRAINT ck_bom_lines_quantity_precision CHECK ((typeof(quantity) = 'integer' AND abs(quantity) < 1000000000000000000) OR quantity IS NULL), 
	CONSTRAINT ck_bom_lines_scrap_rate_integer CHECK (typeof(scrap_rate) = 'integer'), 
	CONSTRAINT ck_bom_lines_scrap_rate_nonnegative CHECK (scrap_rate >= 0), 
	CONSTRAINT fk_bom_lines_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_bom_lines_0 UNIQUE (bom_id, line_no), 
	CONSTRAINT uq_bom_lines_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_bom_lines_rule_0 CHECK (quantity > 0), 
	CONSTRAINT ck_bom_lines_rule_1 CHECK (scrap_rate BETWEEN 0 AND 10000)
);

CREATE TABLE customer_contacts (
	id VARCHAR(36) NOT NULL, 
	customer_id VARCHAR(36) NOT NULL, 
	full_name VARCHAR(200) NOT NULL, 
	title VARCHAR(120), 
	phone VARCHAR(30), 
	email VARCHAR(255), 
	is_primary BOOLEAN DEFAULT 0 NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	CONSTRAINT pk_customer_contacts PRIMARY KEY (id), 
	CHECK (is_primary IN (0, 1)), 
	CONSTRAINT ck_customer_contacts_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_customer_contacts_organization_id_customers FOREIGN KEY(organization_id, customer_id) REFERENCES customers (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_customer_contacts_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_customer_contacts_0 UNIQUE (organization_id, id)
);

CREATE TABLE customer_invoice_lines (
	id VARCHAR(36) NOT NULL, 
	invoice_id VARCHAR(36) NOT NULL, 
	line_no BIGINT NOT NULL, 
	sales_order_line_id VARCHAR(36), 
	description TEXT, 
	quantity BIGINT DEFAULT '0' NOT NULL, 
	uom VARCHAR(20) NOT NULL, 
	unit_price BIGINT DEFAULT 0 NOT NULL, 
	tax_amount BIGINT DEFAULT 0 NOT NULL, 
	line_total BIGINT DEFAULT 0 NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	CONSTRAINT pk_customer_invoice_lines PRIMARY KEY (id), 
	CONSTRAINT ck_customer_invoice_lines_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_customer_invoice_lines_organization_id_customer_invoices FOREIGN KEY(organization_id, invoice_id) REFERENCES customer_invoices (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_customer_invoice_lines_line_no_integer CHECK (typeof(line_no) = 'integer'), 
	CONSTRAINT ck_customer_invoice_lines_line_no_nonnegative CHECK (line_no >= 0), 
	CONSTRAINT ck_customer_invoice_lines_line_no_positive CHECK (line_no > 0), 
	CONSTRAINT fk_customer_invoice_lines_organization_id_sales_order_lines FOREIGN KEY(organization_id, sales_order_line_id) REFERENCES sales_order_lines (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_customer_invoice_lines_quantity_nonnegative CHECK (quantity >= 0), 
	CONSTRAINT ck_customer_invoice_lines_quantity_precision CHECK ((typeof(quantity) = 'integer' AND abs(quantity) < 1000000000000000000) OR quantity IS NULL), 
	CONSTRAINT ck_customer_invoice_lines_unit_price_integer CHECK (typeof(unit_price) = 'integer'), 
	CONSTRAINT ck_customer_invoice_lines_unit_price_nonnegative CHECK (unit_price >= 0), 
	CONSTRAINT ck_customer_invoice_lines_tax_amount_integer CHECK (typeof(tax_amount) = 'integer'), 
	CONSTRAINT ck_customer_invoice_lines_tax_amount_nonnegative CHECK (tax_amount >= 0), 
	CONSTRAINT ck_customer_invoice_lines_line_total_integer CHECK (typeof(line_total) = 'integer'), 
	CONSTRAINT ck_customer_invoice_lines_line_total_nonnegative CHECK (line_total >= 0), 
	CONSTRAINT fk_customer_invoice_lines_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_customer_invoice_lines_0 UNIQUE (invoice_id, line_no), 
	CONSTRAINT uq_customer_invoice_lines_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_customer_invoice_lines_rule_0 CHECK (quantity > 0)
);

CREATE TABLE customer_invoices (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	invoice_no VARCHAR(100) NOT NULL, 
	customer_id VARCHAR(36) NOT NULL, 
	sales_order_id VARCHAR(36), 
	invoice_date DATE NOT NULL, 
	due_date DATE, 
	currency VARCHAR(3) DEFAULT 'VND' NOT NULL, 
	subtotal_amount BIGINT DEFAULT 0 NOT NULL, 
	tax_amount BIGINT DEFAULT 0 NOT NULL, 
	total_amount BIGINT DEFAULT 0 NOT NULL, 
	status VARCHAR(30) DEFAULT 'draft' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_customer_invoices PRIMARY KEY (id), 
	CONSTRAINT ck_customer_invoices_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_customer_invoices_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_customer_invoices_organization_id_customers FOREIGN KEY(organization_id, customer_id) REFERENCES customers (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_customer_invoices_organization_id_sales_orders FOREIGN KEY(organization_id, sales_order_id) REFERENCES sales_orders (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_customer_invoices_currency_enum CHECK (currency IN ('VND')), 
	CONSTRAINT ck_customer_invoices_subtotal_amount_integer CHECK (typeof(subtotal_amount) = 'integer'), 
	CONSTRAINT ck_customer_invoices_subtotal_amount_nonnegative CHECK (subtotal_amount >= 0), 
	CONSTRAINT ck_customer_invoices_tax_amount_integer CHECK (typeof(tax_amount) = 'integer'), 
	CONSTRAINT ck_customer_invoices_tax_amount_nonnegative CHECK (tax_amount >= 0), 
	CONSTRAINT ck_customer_invoices_total_amount_integer CHECK (typeof(total_amount) = 'integer'), 
	CONSTRAINT ck_customer_invoices_total_amount_nonnegative CHECK (total_amount >= 0), 
	CONSTRAINT ck_customer_invoices_status_enum CHECK (status IN ('draft','issued','partially_paid','paid','overdue','voided')), 
	CONSTRAINT uq_customer_invoices_0 UNIQUE (organization_id, invoice_no), 
	CONSTRAINT uq_customer_invoices_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_customer_invoices_rule_0 CHECK (total_amount = subtotal_amount + tax_amount), 
	CONSTRAINT ck_customer_invoices_rule_1 CHECK (due_date IS NULL OR due_date >= invoice_date), 
	CONSTRAINT fk_customer_invoices_paired_0 FOREIGN KEY(organization_id, sales_order_id, customer_id) REFERENCES sales_orders (organization_id, id, customer_id)
);

CREATE TABLE customer_payment_allocations (
	id VARCHAR(36) NOT NULL, 
	receipt_id VARCHAR(36) NOT NULL, 
	invoice_id VARCHAR(36) NOT NULL, 
	amount BIGINT DEFAULT 0 NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	created_by VARCHAR(36), 
	organization_id VARCHAR(36) NOT NULL, 
	CONSTRAINT pk_customer_payment_allocations PRIMARY KEY (id), 
	CONSTRAINT ck_customer_payment_allocations_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_customer_payment_allocations_organization_id_customer_receipts FOREIGN KEY(organization_id, receipt_id) REFERENCES customer_receipts (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_customer_payment_allocations_organization_id_customer_invoices FOREIGN KEY(organization_id, invoice_id) REFERENCES customer_invoices (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_customer_payment_allocations_amount_integer CHECK (typeof(amount) = 'integer'), 
	CONSTRAINT ck_customer_payment_allocations_amount_nonnegative CHECK (amount >= 0), 
	CONSTRAINT fk_customer_payment_allocations_organization_id_app_users FOREIGN KEY(organization_id, created_by) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_customer_payment_allocations_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_customer_payment_allocations_0 UNIQUE (receipt_id, invoice_id), 
	CONSTRAINT uq_customer_payment_allocations_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_customer_payment_allocations_rule_0 CHECK (amount > 0)
);

CREATE TABLE customer_receipts (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	receipt_code VARCHAR(70) NOT NULL, 
	customer_id VARCHAR(36) NOT NULL, 
	received_at VARCHAR(32), 
	amount BIGINT DEFAULT 0 NOT NULL, 
	currency VARCHAR(3) DEFAULT 'VND' NOT NULL, 
	payment_method VARCHAR(30) NOT NULL, 
	external_reference VARCHAR(160), 
	status VARCHAR(30) DEFAULT 'draft' NOT NULL, 
	verified_by VARCHAR(36), 
	created_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_customer_receipts PRIMARY KEY (id), 
	CONSTRAINT ck_customer_receipts_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_customer_receipts_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_customer_receipts_organization_id_customers FOREIGN KEY(organization_id, customer_id) REFERENCES customers (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_customer_receipts_amount_integer CHECK (typeof(amount) = 'integer'), 
	CONSTRAINT ck_customer_receipts_amount_nonnegative CHECK (amount >= 0), 
	CONSTRAINT ck_customer_receipts_currency_enum CHECK (currency IN ('VND')), 
	CONSTRAINT ck_customer_receipts_status_enum CHECK (status IN ('draft','verified','voided')), 
	CONSTRAINT fk_customer_receipts_organization_id_app_users FOREIGN KEY(organization_id, verified_by) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_customer_receipts_0 UNIQUE (organization_id, receipt_code), 
	CONSTRAINT uq_customer_receipts_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_customer_receipts_rule_0 CHECK (amount > 0)
);

CREATE TABLE customers (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	customer_code VARCHAR(50) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	tax_code VARCHAR(50), 
	phone VARCHAR(30), 
	email VARCHAR(255), 
	billing_address TEXT, 
	shipping_address TEXT, 
	status VARCHAR(30) DEFAULT 'active' NOT NULL, 
	owner_employee_id VARCHAR(36), 
	current_debt_amount BIGINT DEFAULT 0 NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_customers PRIMARY KEY (id), 
	CONSTRAINT ck_customers_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_customers_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_customers_status_enum CHECK (status IN ('active','inactive','blocked')), 
	CONSTRAINT fk_customers_organization_id_employees FOREIGN KEY(organization_id, owner_employee_id) REFERENCES employees (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_customers_current_debt_amount_integer CHECK (typeof(current_debt_amount) = 'integer'), 
	CONSTRAINT ck_customers_current_debt_amount_nonnegative CHECK (current_debt_amount >= 0), 
	CONSTRAINT uq_customers_0 UNIQUE (organization_id, customer_code), 
	CONSTRAINT uq_customers_1 UNIQUE (organization_id, id)
);

CREATE TABLE departments (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	parent_department_id VARCHAR(36), 
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	manager_employee_id VARCHAR(36), 
	is_active BOOLEAN DEFAULT 1 NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_departments PRIMARY KEY (id), 
	CHECK (is_active IN (0, 1)), 
	CONSTRAINT ck_departments_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_departments_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_departments_organization_id_departments FOREIGN KEY(organization_id, parent_department_id) REFERENCES departments (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_departments_organization_id_employees FOREIGN KEY(organization_id, manager_employee_id) REFERENCES employees (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_departments_0 UNIQUE (organization_id, code), 
	CONSTRAINT uq_departments_1 UNIQUE (organization_id, id)
);

CREATE TABLE documents (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	original_name VARCHAR(255) NOT NULL, 
	media_type VARCHAR(120) NOT NULL, 
	byte_size BIGINT DEFAULT 0 NOT NULL, 
	storage_key VARCHAR(500) NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	uploaded_by VARCHAR(36) NOT NULL, 
	received_at VARCHAR(32) NOT NULL, 
	source_kind VARCHAR(50) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_documents PRIMARY KEY (id), 
	CONSTRAINT ck_documents_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_documents_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_documents_byte_size_integer CHECK (typeof(byte_size) = 'integer'), 
	CONSTRAINT ck_documents_byte_size_nonnegative CHECK (byte_size >= 0), 
	CONSTRAINT fk_documents_organization_id_app_users FOREIGN KEY(organization_id, uploaded_by) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_documents_0 UNIQUE (storage_key), 
	CONSTRAINT uq_documents_1 UNIQUE (organization_id, id)
);

CREATE TABLE employees (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	site_id VARCHAR(36), 
	department_id VARCHAR(36), 
	employee_code VARCHAR(50) NOT NULL, 
	full_name VARCHAR(200) NOT NULL, 
	phone VARCHAR(30), 
	email VARCHAR(255), 
	job_title VARCHAR(120), 
	status VARCHAR(30) DEFAULT 'active' NOT NULL, 
	hired_on DATE, 
	terminated_on DATE, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_employees PRIMARY KEY (id), 
	CONSTRAINT ck_employees_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_employees_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_employees_organization_id_sites FOREIGN KEY(organization_id, site_id) REFERENCES sites (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_employees_organization_id_departments FOREIGN KEY(organization_id, department_id) REFERENCES departments (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_employees_status_enum CHECK (status IN ('active','inactive','on_leave','terminated')), 
	CONSTRAINT uq_employees_0 UNIQUE (organization_id, employee_code), 
	CONSTRAINT uq_employees_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_employees_rule_0 CHECK (terminated_on IS NULL OR hired_on IS NULL OR terminated_on >= hired_on)
);

CREATE TABLE inventory_lots (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	lot_code VARCHAR(100) NOT NULL, 
	supplier_id VARCHAR(36), 
	manufactured_at DATE, 
	expires_at DATE, 
	received_at VARCHAR(32) NOT NULL, 
	source_document_id VARCHAR(36), 
	created_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_inventory_lots PRIMARY KEY (id), 
	CONSTRAINT ck_inventory_lots_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_inventory_lots_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_lots_organization_id_products FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_lots_organization_id_suppliers FOREIGN KEY(organization_id, supplier_id) REFERENCES suppliers (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_lots_organization_id_documents FOREIGN KEY(organization_id, source_document_id) REFERENCES documents (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_inventory_lots_0 UNIQUE (organization_id, product_id, lot_code), 
	CONSTRAINT uq_inventory_lots_1 UNIQUE (organization_id, id), 
	CONSTRAINT uq_inventory_lots_paired_inventory_units_1 UNIQUE (organization_id, id, product_id)
);

CREATE TABLE inventory_movements (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	movement_code VARCHAR(70) NOT NULL, 
	movement_type VARCHAR(30) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	inventory_unit_id VARCHAR(36), 
	lot_id VARCHAR(36), 
	warehouse_id VARCHAR(36) NOT NULL, 
	location_id VARCHAR(36), 
	quantity_delta BIGINT DEFAULT '0' NOT NULL, 
	unit_cost BIGINT DEFAULT 0 NOT NULL, 
	total_value BIGINT DEFAULT 0 NOT NULL, 
	occurred_at VARCHAR(32) NOT NULL, 
	reference_type VARCHAR(50) NOT NULL, 
	reference_id VARCHAR(36), 
	idempotency_key VARCHAR(120) NOT NULL, 
	actor_user_id VARCHAR(36) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_inventory_movements PRIMARY KEY (id), 
	CONSTRAINT ck_inventory_movements_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_inventory_movements_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_inventory_movements_movement_type_enum CHECK (movement_type IN ('receipt','issue','transfer_out','transfer_in','production_consume','production_output','adjustment','reversal')), 
	CONSTRAINT fk_inventory_movements_organization_id_products FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_movements_organization_id_inventory_units FOREIGN KEY(organization_id, inventory_unit_id) REFERENCES inventory_units (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_movements_organization_id_inventory_lots FOREIGN KEY(organization_id, lot_id) REFERENCES inventory_lots (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_movements_organization_id_warehouses FOREIGN KEY(organization_id, warehouse_id) REFERENCES warehouses (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_movements_organization_id_warehouse_locations FOREIGN KEY(organization_id, location_id) REFERENCES warehouse_locations (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_inventory_movements_quantity_delta_precision CHECK ((typeof(quantity_delta) = 'integer' AND abs(quantity_delta) < 1000000000000000000) OR quantity_delta IS NULL), 
	CONSTRAINT ck_inventory_movements_unit_cost_integer CHECK (typeof(unit_cost) = 'integer'), 
	CONSTRAINT ck_inventory_movements_unit_cost_nonnegative CHECK (unit_cost >= 0), 
	CONSTRAINT ck_inventory_movements_total_value_integer CHECK (typeof(total_value) = 'integer'), 
	CONSTRAINT ck_inventory_movements_total_value_nonnegative CHECK (total_value >= 0), 
	CONSTRAINT fk_inventory_movements_organization_id_app_users FOREIGN KEY(organization_id, actor_user_id) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_inventory_movements_0 UNIQUE (organization_id, movement_code), 
	CONSTRAINT uq_inventory_movements_1 UNIQUE (organization_id, idempotency_key), 
	CONSTRAINT uq_inventory_movements_2 UNIQUE (organization_id, id), 
	CONSTRAINT ck_inventory_movements_rule_0 CHECK (quantity_delta != 0), 
	CONSTRAINT fk_inventory_movements_paired_0 FOREIGN KEY(organization_id, inventory_unit_id, product_id) REFERENCES inventory_units (organization_id, id, product_id), 
	CONSTRAINT fk_inventory_movements_paired_1 FOREIGN KEY(organization_id, lot_id, product_id) REFERENCES inventory_lots (organization_id, id, product_id), 
	CONSTRAINT fk_inventory_movements_paired_2 FOREIGN KEY(organization_id, location_id, warehouse_id) REFERENCES warehouse_locations (organization_id, id, warehouse_id)
);

CREATE TABLE inventory_units (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	lot_id VARCHAR(36), 
	roll_code VARCHAR(100) NOT NULL, 
	warehouse_id VARCHAR(36) NOT NULL, 
	location_id VARCHAR(36), 
	initial_quantity BIGINT DEFAULT '0' NOT NULL, 
	remaining_quantity BIGINT DEFAULT '0' NOT NULL, 
	uom VARCHAR(20) NOT NULL, 
	unit_cost BIGINT DEFAULT 0 NOT NULL, 
	status VARCHAR(30) DEFAULT 'available' NOT NULL, 
	received_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_inventory_units PRIMARY KEY (id), 
	CONSTRAINT ck_inventory_units_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_inventory_units_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_units_organization_id_products FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_units_organization_id_inventory_lots FOREIGN KEY(organization_id, lot_id) REFERENCES inventory_lots (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_units_organization_id_warehouses FOREIGN KEY(organization_id, warehouse_id) REFERENCES warehouses (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_inventory_units_organization_id_warehouse_locations FOREIGN KEY(organization_id, location_id) REFERENCES warehouse_locations (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_inventory_units_initial_quantity_nonnegative CHECK (initial_quantity >= 0), 
	CONSTRAINT ck_inventory_units_initial_quantity_precision CHECK ((typeof(initial_quantity) = 'integer' AND abs(initial_quantity) < 1000000000000000000) OR initial_quantity IS NULL), 
	CONSTRAINT ck_inventory_units_remaining_quantity_nonnegative CHECK (remaining_quantity >= 0), 
	CONSTRAINT ck_inventory_units_remaining_quantity_precision CHECK ((typeof(remaining_quantity) = 'integer' AND abs(remaining_quantity) < 1000000000000000000) OR remaining_quantity IS NULL), 
	CONSTRAINT ck_inventory_units_unit_cost_integer CHECK (typeof(unit_cost) = 'integer'), 
	CONSTRAINT ck_inventory_units_unit_cost_nonnegative CHECK (unit_cost >= 0), 
	CONSTRAINT ck_inventory_units_status_enum CHECK (status IN ('available','reserved','consumed','quarantined','scrapped','in_transit')), 
	CONSTRAINT uq_inventory_units_0 UNIQUE (organization_id, roll_code), 
	CONSTRAINT uq_inventory_units_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_inventory_units_rule_0 CHECK (remaining_quantity >= 0), 
	CONSTRAINT ck_inventory_units_rule_1 CHECK (initial_quantity >= 0), 
	CONSTRAINT fk_inventory_units_paired_0 FOREIGN KEY(organization_id, location_id, warehouse_id) REFERENCES warehouse_locations (organization_id, id, warehouse_id), 
	CONSTRAINT fk_inventory_units_paired_1 FOREIGN KEY(organization_id, lot_id, product_id) REFERENCES inventory_lots (organization_id, id, product_id), 
	CONSTRAINT uq_inventory_units_paired_inventory_movements_0 UNIQUE (organization_id, id, product_id)
);

CREATE TABLE kpi_targets (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	employee_id VARCHAR(36) NOT NULL, 
	assigned_by VARCHAR(36) NOT NULL, 
	kpi_type VARCHAR(60) NOT NULL, 
	target_amount BIGINT, 
	target_value BIGINT, 
	period_start DATE NOT NULL, 
	period_end DATE NOT NULL, 
	status VARCHAR(30) DEFAULT 'draft' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_kpi_targets PRIMARY KEY (id), 
	CONSTRAINT ck_kpi_targets_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_kpi_targets_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_kpi_targets_organization_id_employees FOREIGN KEY(organization_id, employee_id) REFERENCES employees (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_kpi_targets_organization_id_app_users FOREIGN KEY(organization_id, assigned_by) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_kpi_targets_kpi_type_enum CHECK (kpi_type IN ('sales_revenue','scrap_rate','output_quantity','task_completion')), 
	CONSTRAINT ck_kpi_targets_target_amount_integer CHECK (typeof(target_amount) = 'integer' OR target_amount IS NULL), 
	CONSTRAINT ck_kpi_targets_target_amount_nonnegative CHECK (target_amount >= 0), 
	CONSTRAINT ck_kpi_targets_target_value_nonnegative CHECK (target_value >= 0), 
	CONSTRAINT ck_kpi_targets_target_value_precision CHECK ((typeof(target_value) = 'integer' AND abs(target_value) < 1000000000000000000) OR target_value IS NULL), 
	CONSTRAINT ck_kpi_targets_status_enum CHECK (status IN ('draft','active','completed','cancelled')), 
	CONSTRAINT uq_kpi_targets_0 UNIQUE (organization_id, id), 
	CONSTRAINT ck_kpi_targets_rule_0 CHECK (period_end >= period_start), 
	CONSTRAINT ck_kpi_targets_rule_1 CHECK ((kpi_type = 'sales_revenue' AND target_amount IS NOT NULL AND target_value IS NULL) OR (kpi_type != 'sales_revenue' AND target_amount IS NULL AND target_value IS NOT NULL))
);

CREATE TABLE machines (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	work_center_id VARCHAR(36) NOT NULL, 
	machine_code VARCHAR(60) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	serial_no VARCHAR(100), 
	status VARCHAR(30) DEFAULT 'active' NOT NULL, 
	commissioned_on DATE, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_machines PRIMARY KEY (id), 
	CONSTRAINT ck_machines_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_machines_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_machines_organization_id_work_centers FOREIGN KEY(organization_id, work_center_id) REFERENCES work_centers (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_machines_status_enum CHECK (status IN ('active','maintenance','idle','retired')), 
	CONSTRAINT uq_machines_0 UNIQUE (organization_id, machine_code), 
	CONSTRAINT uq_machines_1 UNIQUE (organization_id, id), 
	CONSTRAINT uq_machines_paired_production_order_operations_0 UNIQUE (organization_id, id, work_center_id)
);

CREATE TABLE notifications (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36), 
	title VARCHAR(250) NOT NULL, 
	content TEXT NOT NULL, 
	type VARCHAR(20) DEFAULT 'info' NOT NULL, 
	is_read BOOLEAN DEFAULT 0 NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	read_at VARCHAR(32), 
	CONSTRAINT pk_notifications PRIMARY KEY (id), 
	CHECK (is_read IN (0, 1)), 
	CONSTRAINT ck_notifications_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_notifications_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_notifications_organization_id_app_users FOREIGN KEY(organization_id, user_id) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_notifications_type_enum CHECK (type IN ('info','warning','danger')), 
	CONSTRAINT uq_notifications_0 UNIQUE (organization_id, id)
);

CREATE TABLE operation_keys (
      id VARCHAR(36) PRIMARY KEY NOT NULL,organization_id VARCHAR(36) NOT NULL,
      actor_user_id VARCHAR(36) NOT NULL,key VARCHAR(120) NOT NULL,
      route VARCHAR(250) NOT NULL,payload_hash VARCHAR(64) NOT NULL,result_json TEXT NOT NULL,
      created_at VARCHAR(32) NOT NULL, CONSTRAINT uq_operation_keys_organization_id UNIQUE(organization_id,key),
      FOREIGN KEY(organization_id,actor_user_id) REFERENCES app_users(organization_id,id));

CREATE TABLE organizations (
	id VARCHAR(36) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	tax_code VARCHAR(50), 
	address TEXT, 
	phone VARCHAR(30), 
	email VARCHAR(255), 
	base_currency VARCHAR(3) DEFAULT 'VND' NOT NULL, 
	is_active BOOLEAN DEFAULT 1 NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_organizations PRIMARY KEY (id), 
	CHECK (is_active IN (0, 1)), 
	CONSTRAINT ck_organizations_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT ck_organizations_base_currency_enum CHECK (base_currency IN ('VND')), 
	CONSTRAINT uq_organizations_0 UNIQUE (code)
);

CREATE TABLE payment_allocation_events (
      id VARCHAR(36) PRIMARY KEY NOT NULL, organization_id VARCHAR(36) NOT NULL,
      customer_allocation_id VARCHAR(36),supplier_allocation_id VARCHAR(36),
      amount BIGINT NOT NULL CHECK(typeof(amount)='integer' AND amount>0),
      occurred_at VARCHAR(32) NOT NULL,actor_user_id VARCHAR(36) NOT NULL,
      CHECK((customer_allocation_id IS NOT NULL) != (supplier_allocation_id IS NOT NULL)),
      FOREIGN KEY(organization_id,customer_allocation_id) REFERENCES customer_payment_allocations(organization_id,id),
      FOREIGN KEY(organization_id,supplier_allocation_id) REFERENCES supplier_payment_allocations(organization_id,id),
      FOREIGN KEY(organization_id,actor_user_id) REFERENCES app_users(organization_id,id));

CREATE TABLE production_order_operations (
	id VARCHAR(36) NOT NULL, 
	production_order_id VARCHAR(36) NOT NULL, 
	sequence_no BIGINT NOT NULL, 
	work_center_id VARCHAR(36) NOT NULL, 
	machine_id VARCHAR(36), 
	planned_start_at VARCHAR(32), 
	planned_end_at VARCHAR(32), 
	actual_start_at VARCHAR(32), 
	actual_end_at VARCHAR(32), 
	status VARCHAR(30) DEFAULT 'pending' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	CONSTRAINT pk_production_order_operations PRIMARY KEY (id), 
	CONSTRAINT ck_production_order_operations_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_production_order_operations_organization_id_production_orders FOREIGN KEY(organization_id, production_order_id) REFERENCES production_orders (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_production_order_operations_sequence_no_integer CHECK (typeof(sequence_no) = 'integer'), 
	CONSTRAINT ck_production_order_operations_sequence_no_nonnegative CHECK (sequence_no >= 0), 
	CONSTRAINT ck_production_order_operations_sequence_no_positive CHECK (sequence_no > 0), 
	CONSTRAINT fk_production_order_operations_organization_id_work_centers FOREIGN KEY(organization_id, work_center_id) REFERENCES work_centers (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_production_order_operations_organization_id_machines FOREIGN KEY(organization_id, machine_id) REFERENCES machines (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_production_order_operations_status_enum CHECK (status IN ('pending','ready','in_progress','completed','blocked')), 
	CONSTRAINT fk_production_order_operations_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_production_order_operations_0 UNIQUE (production_order_id, sequence_no), 
	CONSTRAINT uq_production_order_operations_1 UNIQUE (organization_id, id), 
	CONSTRAINT fk_production_order_operations_paired_0 FOREIGN KEY(organization_id, machine_id, work_center_id) REFERENCES machines (organization_id, id, work_center_id)
);

CREATE TABLE production_orders (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	production_order_code VARCHAR(70) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	bom_id VARCHAR(36) NOT NULL, 
	sales_order_line_id VARCHAR(36), 
	planned_quantity BIGINT DEFAULT '0' NOT NULL, 
	released_quantity BIGINT DEFAULT '0' NOT NULL, 
	good_quantity BIGINT DEFAULT '0' NOT NULL, 
	scrap_quantity BIGINT DEFAULT '0' NOT NULL, 
	planned_start_at VARCHAR(32), 
	planned_end_at VARCHAR(32), 
	actual_start_at VARCHAR(32), 
	actual_end_at VARCHAR(32), 
	status VARCHAR(30) DEFAULT 'draft' NOT NULL, 
	created_by VARCHAR(36) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_production_orders PRIMARY KEY (id), 
	CONSTRAINT ck_production_orders_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_production_orders_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_production_orders_organization_id_products FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_production_orders_organization_id_bills_of_materials FOREIGN KEY(organization_id, bom_id) REFERENCES bills_of_materials (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_production_orders_organization_id_sales_order_lines FOREIGN KEY(organization_id, sales_order_line_id) REFERENCES sales_order_lines (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_production_orders_planned_quantity_nonnegative CHECK (planned_quantity >= 0), 
	CONSTRAINT ck_production_orders_planned_quantity_precision CHECK ((typeof(planned_quantity) = 'integer' AND abs(planned_quantity) < 1000000000000000000) OR planned_quantity IS NULL), 
	CONSTRAINT ck_production_orders_released_quantity_nonnegative CHECK (released_quantity >= 0), 
	CONSTRAINT ck_production_orders_released_quantity_precision CHECK ((typeof(released_quantity) = 'integer' AND abs(released_quantity) < 1000000000000000000) OR released_quantity IS NULL), 
	CONSTRAINT ck_production_orders_good_quantity_nonnegative CHECK (good_quantity >= 0), 
	CONSTRAINT ck_production_orders_good_quantity_precision CHECK ((typeof(good_quantity) = 'integer' AND abs(good_quantity) < 1000000000000000000) OR good_quantity IS NULL), 
	CONSTRAINT ck_production_orders_scrap_quantity_nonnegative CHECK (scrap_quantity >= 0), 
	CONSTRAINT ck_production_orders_scrap_quantity_precision CHECK ((typeof(scrap_quantity) = 'integer' AND abs(scrap_quantity) < 1000000000000000000) OR scrap_quantity IS NULL), 
	CONSTRAINT ck_production_orders_status_enum CHECK (status IN ('draft','released','in_progress','completed','cancelled')), 
	CONSTRAINT fk_production_orders_organization_id_app_users FOREIGN KEY(organization_id, created_by) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_production_orders_0 UNIQUE (organization_id, production_order_code), 
	CONSTRAINT uq_production_orders_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_production_orders_rule_0 CHECK (planned_quantity > 0), 
	CONSTRAINT ck_production_orders_rule_1 CHECK (released_quantity <= planned_quantity), 
	CONSTRAINT ck_production_orders_rule_2 CHECK (good_quantity + scrap_quantity <= released_quantity), 
	CONSTRAINT ck_production_orders_rule_3 CHECK (planned_end_at IS NULL OR planned_start_at IS NULL OR planned_end_at >= planned_start_at), 
	CONSTRAINT fk_production_orders_paired_0 FOREIGN KEY(organization_id, bom_id, product_id) REFERENCES bills_of_materials (organization_id, id, product_id)
);

CREATE TABLE production_report_corrections (
      id VARCHAR(36) PRIMARY KEY NOT NULL,organization_id VARCHAR(36) NOT NULL,
      report_id VARCHAR(36) NOT NULL,good_delta BIGINT NOT NULL,scrap_delta BIGINT NOT NULL,
      reason TEXT NOT NULL,actor_user_id VARCHAR(36) NOT NULL,created_at VARCHAR(32) NOT NULL,
      CHECK(typeof(good_delta)='integer' AND typeof(scrap_delta)='integer'),
      CHECK(good_delta!=0 OR scrap_delta!=0),
      FOREIGN KEY(organization_id,report_id) REFERENCES production_reports(organization_id,id),
      FOREIGN KEY(organization_id,actor_user_id) REFERENCES app_users(organization_id,id));

CREATE TABLE production_reports (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	production_order_id VARCHAR(36) NOT NULL, 
	operation_id VARCHAR(36), 
	reported_by VARCHAR(36) NOT NULL, 
	reported_at VARCHAR(32) NOT NULL, 
	good_quantity BIGINT DEFAULT '0' NOT NULL, 
	scrap_quantity BIGINT DEFAULT '0' NOT NULL, 
	scrap_value BIGINT DEFAULT 0 NOT NULL, 
	downtime_minutes BIGINT DEFAULT 0 NOT NULL, 
	downtime_reason VARCHAR(120), 
	notes TEXT, 
	created_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_production_reports PRIMARY KEY (id), 
	CONSTRAINT ck_production_reports_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_production_reports_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_production_reports_organization_id_production_orders FOREIGN KEY(organization_id, production_order_id) REFERENCES production_orders (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_production_reports_organization_id_production_order_operations FOREIGN KEY(organization_id, operation_id) REFERENCES production_order_operations (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_production_reports_organization_id_app_users FOREIGN KEY(organization_id, reported_by) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_production_reports_good_quantity_nonnegative CHECK (good_quantity >= 0), 
	CONSTRAINT ck_production_reports_good_quantity_precision CHECK ((typeof(good_quantity) = 'integer' AND abs(good_quantity) < 1000000000000000000) OR good_quantity IS NULL), 
	CONSTRAINT ck_production_reports_scrap_quantity_nonnegative CHECK (scrap_quantity >= 0), 
	CONSTRAINT ck_production_reports_scrap_quantity_precision CHECK ((typeof(scrap_quantity) = 'integer' AND abs(scrap_quantity) < 1000000000000000000) OR scrap_quantity IS NULL), 
	CONSTRAINT ck_production_reports_scrap_value_integer CHECK (typeof(scrap_value) = 'integer'), 
	CONSTRAINT ck_production_reports_scrap_value_nonnegative CHECK (scrap_value >= 0), 
	CONSTRAINT ck_production_reports_downtime_minutes_integer CHECK (typeof(downtime_minutes) = 'integer'), 
	CONSTRAINT ck_production_reports_downtime_minutes_nonnegative CHECK (downtime_minutes >= 0), 
	CONSTRAINT uq_production_reports_0 UNIQUE (organization_id, id), 
	CONSTRAINT ck_production_reports_rule_0 CHECK (good_quantity + scrap_quantity > 0 OR downtime_minutes > 0)
);

CREATE TABLE products (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	sku VARCHAR(80) NOT NULL, 
	name VARCHAR(250) NOT NULL, 
	description TEXT, 
	product_type VARCHAR(40) DEFAULT 'raw_material' NOT NULL, 
	base_uom VARCHAR(20) NOT NULL, 
	tracking_method VARCHAR(30) DEFAULT 'none' NOT NULL, 
	standard_cost BIGINT DEFAULT 0 NOT NULL, 
	is_purchasable BOOLEAN DEFAULT 1 NOT NULL, 
	is_sellable BOOLEAN DEFAULT 1 NOT NULL, 
	is_manufactured BOOLEAN DEFAULT 0 NOT NULL, 
	is_active BOOLEAN DEFAULT 1 NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_products PRIMARY KEY (id), 
	CHECK (is_purchasable IN (0, 1)), 
	CHECK (is_sellable IN (0, 1)), 
	CHECK (is_manufactured IN (0, 1)), 
	CHECK (is_active IN (0, 1)), 
	CONSTRAINT ck_products_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_products_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_products_product_type_enum CHECK (product_type IN ('raw_material','finished_good','semi_finished','service')), 
	CONSTRAINT ck_products_tracking_method_enum CHECK (tracking_method IN ('none','lot','serial','roll')), 
	CONSTRAINT ck_products_standard_cost_integer CHECK (typeof(standard_cost) = 'integer'), 
	CONSTRAINT ck_products_standard_cost_nonnegative CHECK (standard_cost >= 0), 
	CONSTRAINT uq_products_0 UNIQUE (organization_id, sku), 
	CONSTRAINT uq_products_1 UNIQUE (sku), 
	CONSTRAINT uq_products_2 UNIQUE (organization_id, id)
);

CREATE TABLE purchase_order_lines (
	id VARCHAR(36) NOT NULL, 
	purchase_order_id VARCHAR(36) NOT NULL, 
	line_no BIGINT NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	description TEXT, 
	quantity BIGINT DEFAULT '0' NOT NULL, 
	received_quantity BIGINT DEFAULT '0' NOT NULL, 
	uom VARCHAR(20) NOT NULL, 
	unit_price BIGINT DEFAULT 0 NOT NULL, 
	tax_amount BIGINT DEFAULT 0 NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	CONSTRAINT pk_purchase_order_lines PRIMARY KEY (id), 
	CONSTRAINT ck_purchase_order_lines_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_purchase_order_lines_organization_id_purchase_orders FOREIGN KEY(organization_id, purchase_order_id) REFERENCES purchase_orders (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_purchase_order_lines_line_no_integer CHECK (typeof(line_no) = 'integer'), 
	CONSTRAINT ck_purchase_order_lines_line_no_nonnegative CHECK (line_no >= 0), 
	CONSTRAINT ck_purchase_order_lines_line_no_positive CHECK (line_no > 0), 
	CONSTRAINT fk_purchase_order_lines_organization_id_products FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_purchase_order_lines_quantity_nonnegative CHECK (quantity >= 0), 
	CONSTRAINT ck_purchase_order_lines_quantity_precision CHECK ((typeof(quantity) = 'integer' AND abs(quantity) < 1000000000000000000) OR quantity IS NULL), 
	CONSTRAINT ck_purchase_order_lines_received_quantity_nonnegative CHECK (received_quantity >= 0), 
	CONSTRAINT ck_purchase_order_lines_received_quantity_precision CHECK ((typeof(received_quantity) = 'integer' AND abs(received_quantity) < 1000000000000000000) OR received_quantity IS NULL), 
	CONSTRAINT ck_purchase_order_lines_unit_price_integer CHECK (typeof(unit_price) = 'integer'), 
	CONSTRAINT ck_purchase_order_lines_unit_price_nonnegative CHECK (unit_price >= 0), 
	CONSTRAINT ck_purchase_order_lines_tax_amount_integer CHECK (typeof(tax_amount) = 'integer'), 
	CONSTRAINT ck_purchase_order_lines_tax_amount_nonnegative CHECK (tax_amount >= 0), 
	CONSTRAINT fk_purchase_order_lines_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_purchase_order_lines_0 UNIQUE (purchase_order_id, line_no), 
	CONSTRAINT uq_purchase_order_lines_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_purchase_order_lines_rule_0 CHECK (quantity > 0), 
	CONSTRAINT ck_purchase_order_lines_rule_1 CHECK (received_quantity <= quantity)
);

CREATE TABLE purchase_orders (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	po_code VARCHAR(60) NOT NULL, 
	supplier_id VARCHAR(36) NOT NULL, 
	ordered_at VARCHAR(32) NOT NULL, 
	expected_date DATE, 
	status VARCHAR(30) DEFAULT 'draft' NOT NULL, 
	currency VARCHAR(3) DEFAULT 'VND' NOT NULL, 
	subtotal_amount BIGINT DEFAULT 0 NOT NULL, 
	tax_amount BIGINT DEFAULT 0 NOT NULL, 
	total_amount BIGINT DEFAULT 0 NOT NULL, 
	created_by VARCHAR(36) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_purchase_orders PRIMARY KEY (id), 
	CONSTRAINT ck_purchase_orders_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_purchase_orders_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_purchase_orders_organization_id_suppliers FOREIGN KEY(organization_id, supplier_id) REFERENCES suppliers (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_purchase_orders_status_enum CHECK (status IN ('draft','approved','partially_received','received','cancelled')), 
	CONSTRAINT ck_purchase_orders_currency_enum CHECK (currency IN ('VND')), 
	CONSTRAINT ck_purchase_orders_subtotal_amount_integer CHECK (typeof(subtotal_amount) = 'integer'), 
	CONSTRAINT ck_purchase_orders_subtotal_amount_nonnegative CHECK (subtotal_amount >= 0), 
	CONSTRAINT ck_purchase_orders_tax_amount_integer CHECK (typeof(tax_amount) = 'integer'), 
	CONSTRAINT ck_purchase_orders_tax_amount_nonnegative CHECK (tax_amount >= 0), 
	CONSTRAINT ck_purchase_orders_total_amount_integer CHECK (typeof(total_amount) = 'integer'), 
	CONSTRAINT ck_purchase_orders_total_amount_nonnegative CHECK (total_amount >= 0), 
	CONSTRAINT fk_purchase_orders_organization_id_app_users FOREIGN KEY(organization_id, created_by) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_purchase_orders_0 UNIQUE (organization_id, po_code), 
	CONSTRAINT uq_purchase_orders_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_purchase_orders_rule_0 CHECK (total_amount = subtotal_amount + tax_amount), 
	CONSTRAINT uq_purchase_orders_paired_supplier_bills_0 UNIQUE (organization_id, id, supplier_id)
);

CREATE TABLE roles (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	description TEXT, 
	is_system BOOLEAN DEFAULT 0 NOT NULL, 
	is_active BOOLEAN DEFAULT 1 NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_roles PRIMARY KEY (id), 
	CHECK (is_system IN (0, 1)), 
	CHECK (is_active IN (0, 1)), 
	CONSTRAINT ck_roles_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_roles_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_roles_0 UNIQUE (organization_id, code), 
	CONSTRAINT uq_roles_1 UNIQUE (organization_id, id)
);

CREATE TABLE "sales_order_lines" (
	id VARCHAR(36) NOT NULL, 
	order_id VARCHAR(36) NOT NULL, 
	line_no BIGINT NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	description TEXT, 
	quantity BIGINT DEFAULT '0' NOT NULL, 
	uom VARCHAR(20) NOT NULL, 
	unit_price BIGINT DEFAULT 0 NOT NULL, 
	discount_amount BIGINT DEFAULT 0 NOT NULL, 
	tax_rate BIGINT DEFAULT 0 NOT NULL, 
	line_total BIGINT DEFAULT 0 NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	CONSTRAINT pk_sales_order_lines PRIMARY KEY (id), 
	CONSTRAINT ck_sales_order_lines_discount_amount_integer CHECK (typeof(discount_amount) = 'integer'), 
	CONSTRAINT ck_sales_order_lines_tax_rate_integer CHECK (typeof(tax_rate) = 'integer'), 
	CONSTRAINT ck_sales_order_lines_discount_amount_nonnegative CHECK (discount_amount >= 0), 
	CONSTRAINT ck_sales_order_lines_tax_rate_nonnegative CHECK (tax_rate >= 0), 
	CONSTRAINT ck_sales_order_lines_line_no_integer CHECK (typeof(line_no) = 'integer'), 
	CONSTRAINT ck_sales_order_lines_unit_price_integer CHECK (typeof(unit_price) = 'integer'), 
	CONSTRAINT ck_sales_order_lines_line_no_nonnegative CHECK (line_no >= 0), 
	CONSTRAINT ck_sales_order_lines_unit_price_nonnegative CHECK (unit_price >= 0), 
	CONSTRAINT ck_sales_order_lines_line_no_positive CHECK (line_no > 0), 
	CONSTRAINT ck_sales_order_lines_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT uq_sales_order_lines_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_sales_order_lines_line_total_integer CHECK (typeof(line_total) = 'integer'), 
	CONSTRAINT uq_sales_order_lines_0 UNIQUE (order_id, line_no), 
	CONSTRAINT fk_sales_order_lines_organization_id_products FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_sales_order_lines_line_total_nonnegative CHECK (line_total >= 0), 
	CONSTRAINT fk_sales_order_lines_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_sales_order_lines_quantity_nonnegative CHECK (quantity >= 0), 
	CONSTRAINT ck_sales_order_lines_quantity_precision CHECK ((typeof(quantity) = 'integer' AND abs(quantity) < 1000000000000000000) OR quantity IS NULL), 
	CONSTRAINT ck_sales_order_lines_rule_0 CHECK (quantity > 0), 
	CONSTRAINT fk_sales_order_lines_organization_id_sales_orders FOREIGN KEY(organization_id, order_id) REFERENCES sales_orders (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_sales_order_lines_rule_1 CHECK (typeof(((quantity / 1000000) * unit_price + (quantity % 1000000) * (unit_price / 1000000) + ((quantity % 1000000) * (unit_price % 1000000) + 500000) / 1000000)) = 'integer' AND discount_amount <= ((quantity / 1000000) * unit_price + (quantity % 1000000) * (unit_price / 1000000) + ((quantity % 1000000) * (unit_price % 1000000) + 500000) / 1000000))
);

CREATE TABLE sales_orders (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	order_code VARCHAR(60) NOT NULL, 
	customer_id VARCHAR(36) NOT NULL, 
	ordered_at VARCHAR(32), 
	required_delivery_at VARCHAR(32), 
	status VARCHAR(30) DEFAULT 'draft' NOT NULL, 
	subtotal_amount BIGINT DEFAULT 0 NOT NULL, 
	discount_amount BIGINT DEFAULT 0 NOT NULL, 
	tax_amount BIGINT DEFAULT 0 NOT NULL, 
	total_amount BIGINT DEFAULT 0 NOT NULL, 
	currency VARCHAR(3) DEFAULT 'VND' NOT NULL, 
	notes TEXT, 
	created_by VARCHAR(36) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_sales_orders PRIMARY KEY (id), 
	CONSTRAINT ck_sales_orders_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_sales_orders_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_sales_orders_organization_id_customers FOREIGN KEY(organization_id, customer_id) REFERENCES customers (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_sales_orders_status_enum CHECK (status IN ('draft','confirmed','in_progress','completed','cancelled')), 
	CONSTRAINT ck_sales_orders_subtotal_amount_integer CHECK (typeof(subtotal_amount) = 'integer'), 
	CONSTRAINT ck_sales_orders_subtotal_amount_nonnegative CHECK (subtotal_amount >= 0), 
	CONSTRAINT ck_sales_orders_discount_amount_integer CHECK (typeof(discount_amount) = 'integer'), 
	CONSTRAINT ck_sales_orders_discount_amount_nonnegative CHECK (discount_amount >= 0), 
	CONSTRAINT ck_sales_orders_tax_amount_integer CHECK (typeof(tax_amount) = 'integer'), 
	CONSTRAINT ck_sales_orders_tax_amount_nonnegative CHECK (tax_amount >= 0), 
	CONSTRAINT ck_sales_orders_total_amount_integer CHECK (typeof(total_amount) = 'integer'), 
	CONSTRAINT ck_sales_orders_total_amount_nonnegative CHECK (total_amount >= 0), 
	CONSTRAINT ck_sales_orders_currency_enum CHECK (currency IN ('VND')), 
	CONSTRAINT fk_sales_orders_organization_id_app_users FOREIGN KEY(organization_id, created_by) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_sales_orders_0 UNIQUE (organization_id, order_code), 
	CONSTRAINT uq_sales_orders_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_sales_orders_rule_0 CHECK (total_amount = subtotal_amount - discount_amount + tax_amount), 
	CONSTRAINT ck_sales_orders_rule_1 CHECK (discount_amount <= subtotal_amount), 
	CONSTRAINT uq_sales_orders_paired_shipments_0 UNIQUE (organization_id, id, customer_id)
);

CREATE TABLE shipment_lines (
	id VARCHAR(36) NOT NULL, 
	shipment_id VARCHAR(36) NOT NULL, 
	sales_order_line_id VARCHAR(36), 
	product_id VARCHAR(36) NOT NULL, 
	quantity BIGINT DEFAULT '0' NOT NULL, 
	uom VARCHAR(20) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	CONSTRAINT pk_shipment_lines PRIMARY KEY (id), 
	CONSTRAINT ck_shipment_lines_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_shipment_lines_organization_id_shipments FOREIGN KEY(organization_id, shipment_id) REFERENCES shipments (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_shipment_lines_organization_id_sales_order_lines FOREIGN KEY(organization_id, sales_order_line_id) REFERENCES sales_order_lines (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_shipment_lines_organization_id_products FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_shipment_lines_quantity_nonnegative CHECK (quantity >= 0), 
	CONSTRAINT ck_shipment_lines_quantity_precision CHECK ((typeof(quantity) = 'integer' AND abs(quantity) < 1000000000000000000) OR quantity IS NULL), 
	CONSTRAINT fk_shipment_lines_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_shipment_lines_0 UNIQUE (organization_id, id)
);

CREATE TABLE shipments (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	shipment_code VARCHAR(60) NOT NULL, 
	customer_id VARCHAR(36) NOT NULL, 
	sales_order_id VARCHAR(36), 
	shipped_at VARCHAR(32), 
	delivered_at VARCHAR(32), 
	carrier VARCHAR(120), 
	tracking_no VARCHAR(120), 
	status VARCHAR(30) DEFAULT 'draft' NOT NULL, 
	created_by VARCHAR(36) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_shipments PRIMARY KEY (id), 
	CONSTRAINT ck_shipments_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_shipments_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_shipments_organization_id_customers FOREIGN KEY(organization_id, customer_id) REFERENCES customers (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_shipments_organization_id_sales_orders FOREIGN KEY(organization_id, sales_order_id) REFERENCES sales_orders (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_shipments_status_enum CHECK (status IN ('draft','ready','shipped','delivered','cancelled')), 
	CONSTRAINT fk_shipments_organization_id_app_users FOREIGN KEY(organization_id, created_by) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_shipments_0 UNIQUE (organization_id, shipment_code), 
	CONSTRAINT uq_shipments_1 UNIQUE (organization_id, id), 
	CONSTRAINT fk_shipments_paired_0 FOREIGN KEY(organization_id, sales_order_id, customer_id) REFERENCES sales_orders (organization_id, id, customer_id)
);

CREATE TABLE sites (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	address TEXT, 
	is_active BOOLEAN DEFAULT 1 NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_sites PRIMARY KEY (id), 
	CHECK (is_active IN (0, 1)), 
	CONSTRAINT ck_sites_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_sites_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_sites_0 UNIQUE (organization_id, code), 
	CONSTRAINT uq_sites_1 UNIQUE (organization_id, id)
);

CREATE TABLE stock_transfer_lines (
	id VARCHAR(36) NOT NULL, 
	transfer_id VARCHAR(36) NOT NULL, 
	product_id VARCHAR(36) NOT NULL, 
	inventory_unit_id VARCHAR(36), 
	lot_id VARCHAR(36), 
	quantity BIGINT DEFAULT '0' NOT NULL, 
	uom VARCHAR(20) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	CONSTRAINT pk_stock_transfer_lines PRIMARY KEY (id), 
	CONSTRAINT ck_stock_transfer_lines_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_stock_transfer_lines_organization_id_stock_transfers FOREIGN KEY(organization_id, transfer_id) REFERENCES stock_transfers (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_stock_transfer_lines_organization_id_products FOREIGN KEY(organization_id, product_id) REFERENCES products (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_stock_transfer_lines_organization_id_inventory_units FOREIGN KEY(organization_id, inventory_unit_id) REFERENCES inventory_units (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_stock_transfer_lines_organization_id_inventory_lots FOREIGN KEY(organization_id, lot_id) REFERENCES inventory_lots (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_stock_transfer_lines_quantity_nonnegative CHECK (quantity >= 0), 
	CONSTRAINT ck_stock_transfer_lines_quantity_precision CHECK ((typeof(quantity) = 'integer' AND abs(quantity) < 1000000000000000000) OR quantity IS NULL), 
	CONSTRAINT fk_stock_transfer_lines_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_stock_transfer_lines_0 UNIQUE (organization_id, id), 
	CONSTRAINT ck_stock_transfer_lines_rule_0 CHECK (quantity > 0)
);

CREATE TABLE stock_transfers (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	transfer_code VARCHAR(70) NOT NULL, 
	from_warehouse_id VARCHAR(36) NOT NULL, 
	to_warehouse_id VARCHAR(36) NOT NULL, 
	requested_at VARCHAR(32) NOT NULL, 
	shipped_at VARCHAR(32), 
	received_at VARCHAR(32), 
	status VARCHAR(30) DEFAULT 'draft' NOT NULL, 
	created_by VARCHAR(36) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_stock_transfers PRIMARY KEY (id), 
	CONSTRAINT ck_stock_transfers_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_stock_transfers_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_stock_transfers_organization_id_warehouses FOREIGN KEY(organization_id, from_warehouse_id) REFERENCES warehouses (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_stock_transfers_organization_id_warehouses FOREIGN KEY(organization_id, to_warehouse_id) REFERENCES warehouses (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_stock_transfers_status_enum CHECK (status IN ('draft','requested','shipped','received','cancelled')), 
	CONSTRAINT fk_stock_transfers_organization_id_app_users FOREIGN KEY(organization_id, created_by) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_stock_transfers_0 UNIQUE (organization_id, transfer_code), 
	CONSTRAINT uq_stock_transfers_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_stock_transfers_rule_0 CHECK (from_warehouse_id != to_warehouse_id)
);

CREATE TABLE supplier_bills (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	supplier_id VARCHAR(36) NOT NULL, 
	purchase_order_id VARCHAR(36), 
	bill_no VARCHAR(100) NOT NULL, 
	bill_date DATE NOT NULL, 
	due_date DATE, 
	subtotal_amount BIGINT DEFAULT 0 NOT NULL, 
	tax_amount BIGINT DEFAULT 0 NOT NULL, 
	total_amount BIGINT DEFAULT 0 NOT NULL, 
	currency VARCHAR(3) DEFAULT 'VND' NOT NULL, 
	status VARCHAR(30) DEFAULT 'draft' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_supplier_bills PRIMARY KEY (id), 
	CONSTRAINT ck_supplier_bills_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_supplier_bills_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_supplier_bills_organization_id_suppliers FOREIGN KEY(organization_id, supplier_id) REFERENCES suppliers (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_supplier_bills_organization_id_purchase_orders FOREIGN KEY(organization_id, purchase_order_id) REFERENCES purchase_orders (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_supplier_bills_subtotal_amount_integer CHECK (typeof(subtotal_amount) = 'integer'), 
	CONSTRAINT ck_supplier_bills_subtotal_amount_nonnegative CHECK (subtotal_amount >= 0), 
	CONSTRAINT ck_supplier_bills_tax_amount_integer CHECK (typeof(tax_amount) = 'integer'), 
	CONSTRAINT ck_supplier_bills_tax_amount_nonnegative CHECK (tax_amount >= 0), 
	CONSTRAINT ck_supplier_bills_total_amount_integer CHECK (typeof(total_amount) = 'integer'), 
	CONSTRAINT ck_supplier_bills_total_amount_nonnegative CHECK (total_amount >= 0), 
	CONSTRAINT ck_supplier_bills_currency_enum CHECK (currency IN ('VND')), 
	CONSTRAINT ck_supplier_bills_status_enum CHECK (status IN ('draft','posted','partially_paid','paid','cancelled')), 
	CONSTRAINT uq_supplier_bills_0 UNIQUE (organization_id, supplier_id, bill_no), 
	CONSTRAINT uq_supplier_bills_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_supplier_bills_rule_0 CHECK (total_amount = subtotal_amount + tax_amount), 
	CONSTRAINT ck_supplier_bills_rule_1 CHECK (due_date IS NULL OR due_date >= bill_date), 
	CONSTRAINT fk_supplier_bills_paired_0 FOREIGN KEY(organization_id, purchase_order_id, supplier_id) REFERENCES purchase_orders (organization_id, id, supplier_id)
);

CREATE TABLE supplier_payment_allocations (
      id VARCHAR(36) PRIMARY KEY NOT NULL, organization_id VARCHAR(36) NOT NULL,
      payment_id VARCHAR(36) NOT NULL,bill_id VARCHAR(36) NOT NULL,
      amount BIGINT NOT NULL CHECK(typeof(amount)='integer' AND amount>0),
      created_at VARCHAR(32) NOT NULL,created_by VARCHAR(36) NOT NULL,
      CONSTRAINT uq_supplier_payment_allocations_payment_id UNIQUE(payment_id,bill_id),
      CONSTRAINT uq_supplier_payment_allocations_organization_id UNIQUE(organization_id,id),
      FOREIGN KEY(organization_id,payment_id) REFERENCES supplier_payments(organization_id,id),
      FOREIGN KEY(organization_id,bill_id) REFERENCES supplier_bills(organization_id,id),
      FOREIGN KEY(organization_id,created_by) REFERENCES app_users(organization_id,id));

CREATE TABLE supplier_payments (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	supplier_id VARCHAR(36) NOT NULL, 
	payment_code VARCHAR(60) NOT NULL, 
	paid_at VARCHAR(32), 
	amount BIGINT DEFAULT 0 NOT NULL, 
	currency VARCHAR(3) DEFAULT 'VND' NOT NULL, 
	payment_method VARCHAR(30) NOT NULL, 
	external_reference VARCHAR(160), 
	status VARCHAR(30) DEFAULT 'draft' NOT NULL, 
	created_by VARCHAR(36) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_supplier_payments PRIMARY KEY (id), 
	CONSTRAINT ck_supplier_payments_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_supplier_payments_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_supplier_payments_organization_id_suppliers FOREIGN KEY(organization_id, supplier_id) REFERENCES suppliers (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_supplier_payments_amount_integer CHECK (typeof(amount) = 'integer'), 
	CONSTRAINT ck_supplier_payments_amount_nonnegative CHECK (amount >= 0), 
	CONSTRAINT ck_supplier_payments_currency_enum CHECK (currency IN ('VND')), 
	CONSTRAINT ck_supplier_payments_status_enum CHECK (status IN ('draft','verified','voided')), 
	CONSTRAINT fk_supplier_payments_organization_id_app_users FOREIGN KEY(organization_id, created_by) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_supplier_payments_0 UNIQUE (organization_id, payment_code), 
	CONSTRAINT uq_supplier_payments_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_supplier_payments_rule_0 CHECK (amount > 0)
);

CREATE TABLE suppliers (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	supplier_code VARCHAR(50) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	tax_code VARCHAR(50), 
	phone VARCHAR(30), 
	email VARCHAR(255), 
	address TEXT, 
	status VARCHAR(30) DEFAULT 'active' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_suppliers PRIMARY KEY (id), 
	CONSTRAINT ck_suppliers_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_suppliers_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_suppliers_status_enum CHECK (status IN ('active','inactive','blocked')), 
	CONSTRAINT uq_suppliers_0 UNIQUE (organization_id, supplier_code), 
	CONSTRAINT uq_suppliers_1 UNIQUE (organization_id, id)
);

CREATE TABLE task_assignees (
	id VARCHAR(36) NOT NULL, 
	task_id VARCHAR(36) NOT NULL, 
	employee_id VARCHAR(36) NOT NULL, 
	assigned_by VARCHAR(36) NOT NULL, 
	assigned_at VARCHAR(32) NOT NULL, 
	status VARCHAR(30) DEFAULT 'assigned' NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	CONSTRAINT pk_task_assignees PRIMARY KEY (id), 
	CONSTRAINT ck_task_assignees_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_task_assignees_organization_id_tasks FOREIGN KEY(organization_id, task_id) REFERENCES tasks (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_task_assignees_organization_id_employees FOREIGN KEY(organization_id, employee_id) REFERENCES employees (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_task_assignees_organization_id_app_users FOREIGN KEY(organization_id, assigned_by) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_task_assignees_status_enum CHECK (status IN ('assigned','accepted','completed','removed')), 
	CONSTRAINT fk_task_assignees_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_task_assignees_0 UNIQUE (task_id, employee_id), 
	CONSTRAINT uq_task_assignees_1 UNIQUE (organization_id, id)
);

CREATE TABLE task_updates (
	id VARCHAR(36) NOT NULL, 
	task_id VARCHAR(36) NOT NULL, 
	employee_id VARCHAR(36) NOT NULL, 
	update_type VARCHAR(30) NOT NULL, 
	content TEXT, 
	progress_percent BIGINT, 
	created_at VARCHAR(32) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	CONSTRAINT pk_task_updates PRIMARY KEY (id), 
	CONSTRAINT ck_task_updates_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_task_updates_organization_id_tasks FOREIGN KEY(organization_id, task_id) REFERENCES tasks (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_task_updates_organization_id_employees FOREIGN KEY(organization_id, employee_id) REFERENCES employees (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_task_updates_update_type_enum CHECK (update_type IN ('comment','progress','status_change','attachment')), 
	CONSTRAINT ck_task_updates_progress_percent_integer CHECK (typeof(progress_percent) = 'integer' OR progress_percent IS NULL), 
	CONSTRAINT ck_task_updates_progress_percent_nonnegative CHECK (progress_percent >= 0), 
	CONSTRAINT fk_task_updates_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_task_updates_0 UNIQUE (organization_id, id), 
	CONSTRAINT ck_task_updates_rule_0 CHECK (progress_percent IS NULL OR progress_percent BETWEEN 0 AND 100)
);

CREATE TABLE tasks (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	task_code VARCHAR(60) NOT NULL, 
	title VARCHAR(250) NOT NULL, 
	description TEXT, 
	task_type VARCHAR(40) DEFAULT 'general' NOT NULL, 
	priority VARCHAR(20) DEFAULT 'normal' NOT NULL, 
	status VARCHAR(30) DEFAULT 'open' NOT NULL, 
	created_by VARCHAR(36) NOT NULL, 
	production_order_id VARCHAR(36), 
	start_at VARCHAR(32), 
	due_at VARCHAR(32), 
	completed_at VARCHAR(32), 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_tasks PRIMARY KEY (id), 
	CONSTRAINT ck_tasks_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_tasks_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT ck_tasks_task_type_enum CHECK (task_type IN ('production','maintenance','approval','general')), 
	CONSTRAINT ck_tasks_priority_enum CHECK (priority IN ('low','normal','high','urgent')), 
	CONSTRAINT ck_tasks_status_enum CHECK (status IN ('open','in_progress','blocked','completed','cancelled')), 
	CONSTRAINT fk_tasks_organization_id_app_users FOREIGN KEY(organization_id, created_by) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_tasks_organization_id_production_orders FOREIGN KEY(organization_id, production_order_id) REFERENCES production_orders (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_tasks_0 UNIQUE (organization_id, task_code), 
	CONSTRAINT uq_tasks_1 UNIQUE (organization_id, id), 
	CONSTRAINT ck_tasks_rule_0 CHECK (due_at IS NULL OR start_at IS NULL OR due_at >= start_at)
);

CREATE TABLE user_roles (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	role_id VARCHAR(36) NOT NULL, 
	site_id VARCHAR(36), 
	assigned_by VARCHAR(36), 
	assigned_at VARCHAR(32) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	CONSTRAINT pk_user_roles PRIMARY KEY (id), 
	CONSTRAINT ck_user_roles_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_user_roles_organization_id_app_users FOREIGN KEY(organization_id, user_id) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_user_roles_organization_id_roles FOREIGN KEY(organization_id, role_id) REFERENCES roles (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_user_roles_organization_id_sites FOREIGN KEY(organization_id, site_id) REFERENCES sites (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_user_roles_organization_id_app_users FOREIGN KEY(organization_id, assigned_by) REFERENCES app_users (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_user_roles_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_user_roles_0 UNIQUE (user_id, role_id, site_id), 
	CONSTRAINT uq_user_roles_1 UNIQUE (organization_id, id)
);

CREATE TABLE warehouse_locations (
	id VARCHAR(36) NOT NULL, 
	warehouse_id VARCHAR(36) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	location_type VARCHAR(30) DEFAULT 'bin' NOT NULL, 
	is_active BOOLEAN DEFAULT 1 NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	CONSTRAINT pk_warehouse_locations PRIMARY KEY (id), 
	CHECK (is_active IN (0, 1)), 
	CONSTRAINT ck_warehouse_locations_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_warehouse_locations_organization_id_warehouses FOREIGN KEY(organization_id, warehouse_id) REFERENCES warehouses (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_warehouse_locations_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_warehouse_locations_0 UNIQUE (warehouse_id, code), 
	CONSTRAINT uq_warehouse_locations_1 UNIQUE (organization_id, id), 
	CONSTRAINT uq_warehouse_locations_paired_inventory_units_0 UNIQUE (organization_id, id, warehouse_id)
);

CREATE TABLE warehouses (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	site_id VARCHAR(36) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	location TEXT, 
	is_active BOOLEAN DEFAULT 1 NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_warehouses PRIMARY KEY (id), 
	CHECK (is_active IN (0, 1)), 
	CONSTRAINT ck_warehouses_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_warehouses_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_warehouses_organization_id_sites FOREIGN KEY(organization_id, site_id) REFERENCES sites (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT uq_warehouses_0 UNIQUE (organization_id, code), 
	CONSTRAINT uq_warehouses_1 UNIQUE (organization_id, id)
);

CREATE TABLE work_centers (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	site_id VARCHAR(36) NOT NULL, 
	code VARCHAR(60) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	capacity_minutes_per_day BIGINT DEFAULT 0 NOT NULL, 
	is_active BOOLEAN DEFAULT 1 NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	CONSTRAINT pk_work_centers PRIMARY KEY (id), 
	CHECK (is_active IN (0, 1)), 
	CONSTRAINT ck_work_centers_uuid CHECK (length(id) = 36 AND lower(id) = id AND substr(id,9,1) = '-' AND substr(id,14,1) = '-' AND substr(id,19,1) = '-' AND substr(id,24,1) = '-' AND length(replace(id,'-','')) = 32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'), 
	CONSTRAINT fk_work_centers_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_work_centers_organization_id_sites FOREIGN KEY(organization_id, site_id) REFERENCES sites (organization_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_work_centers_capacity_minutes_per_day_integer CHECK (typeof(capacity_minutes_per_day) = 'integer'), 
	CONSTRAINT ck_work_centers_capacity_minutes_per_day_nonnegative CHECK (capacity_minutes_per_day >= 0), 
	CONSTRAINT uq_work_centers_0 UNIQUE (organization_id, code), 
	CONSTRAINT uq_work_centers_1 UNIQUE (organization_id, id)
);

CREATE INDEX ix_ai_messages_conversation ON ai_messages(conversation_id,created_at);

CREATE INDEX ix_app_users_employee_id ON app_users (organization_id, employee_id);

CREATE INDEX ix_app_users_tenant ON app_users (organization_id);

CREATE INDEX ix_audit_log_actor_user_id ON audit_log (organization_id, actor_user_id);

CREATE INDEX ix_audit_log_entity_id ON audit_log (organization_id, entity_id);

CREATE INDEX ix_audit_log_request_id ON audit_log (organization_id, request_id);

CREATE INDEX ix_audit_log_tenant ON audit_log (organization_id);

CREATE INDEX ix_auth_sessions_family_id ON auth_sessions(family_id);

CREATE INDEX ix_bills_of_materials_product_id ON bills_of_materials (organization_id, product_id);

CREATE INDEX ix_bills_of_materials_tenant ON bills_of_materials (organization_id);

CREATE INDEX ix_bom_lines_bom_id ON bom_lines (organization_id, bom_id);

CREATE INDEX ix_bom_lines_component_product_id ON bom_lines (organization_id, component_product_id);

CREATE INDEX ix_bom_lines_tenant ON bom_lines (organization_id);

CREATE INDEX ix_customer_contacts_customer_id ON customer_contacts (organization_id, customer_id);

CREATE INDEX ix_customer_contacts_tenant ON customer_contacts (organization_id);

CREATE INDEX ix_customer_invoice_lines_invoice_id ON customer_invoice_lines (organization_id, invoice_id);

CREATE INDEX ix_customer_invoice_lines_sales_order_line_id ON customer_invoice_lines (organization_id, sales_order_line_id);

CREATE INDEX ix_customer_invoice_lines_tenant ON customer_invoice_lines (organization_id);

CREATE INDEX ix_customer_invoices_customer_id ON customer_invoices (organization_id, customer_id);

CREATE INDEX ix_customer_invoices_sales_order_id ON customer_invoices (organization_id, sales_order_id);

CREATE INDEX ix_customer_invoices_tenant ON customer_invoices (organization_id);

CREATE INDEX ix_customer_payment_allocations_invoice_id ON customer_payment_allocations (organization_id, invoice_id);

CREATE INDEX ix_customer_payment_allocations_receipt_id ON customer_payment_allocations (organization_id, receipt_id);

CREATE INDEX ix_customer_payment_allocations_tenant ON customer_payment_allocations (organization_id);

CREATE INDEX ix_customer_receipts_customer_id ON customer_receipts (organization_id, customer_id);

CREATE INDEX ix_customer_receipts_tenant ON customer_receipts (organization_id);

CREATE INDEX ix_customers_owner_employee_id ON customers (organization_id, owner_employee_id);

CREATE INDEX ix_customers_tenant ON customers (organization_id);

CREATE INDEX ix_departments_manager_employee_id ON departments (organization_id, manager_employee_id);

CREATE INDEX ix_departments_parent_department_id ON departments (organization_id, parent_department_id);

CREATE INDEX ix_departments_tenant ON departments (organization_id);

CREATE INDEX ix_documents_tenant ON documents (organization_id);

CREATE INDEX ix_employees_department_id ON employees (organization_id, department_id);

CREATE INDEX ix_employees_site_id ON employees (organization_id, site_id);

CREATE INDEX ix_employees_tenant ON employees (organization_id);

CREATE INDEX ix_inventory_lots_product_id ON inventory_lots (organization_id, product_id);

CREATE INDEX ix_inventory_lots_source_document_id ON inventory_lots (organization_id, source_document_id);

CREATE INDEX ix_inventory_lots_supplier_id ON inventory_lots (organization_id, supplier_id);

CREATE INDEX ix_inventory_lots_tenant ON inventory_lots (organization_id);

CREATE INDEX ix_inventory_movements_actor_user_id ON inventory_movements (organization_id, actor_user_id);

CREATE INDEX ix_inventory_movements_inventory_unit_id ON inventory_movements (organization_id, inventory_unit_id);

CREATE INDEX ix_inventory_movements_location_id ON inventory_movements (organization_id, location_id);

CREATE INDEX ix_inventory_movements_lot_id ON inventory_movements (organization_id, lot_id);

CREATE INDEX ix_inventory_movements_product_id ON inventory_movements (organization_id, product_id);

CREATE INDEX ix_inventory_movements_reference_id ON inventory_movements (organization_id, reference_id);

CREATE INDEX ix_inventory_movements_tenant ON inventory_movements (organization_id);

CREATE INDEX ix_inventory_movements_warehouse_id ON inventory_movements (organization_id, warehouse_id);

CREATE INDEX ix_inventory_units_location_id ON inventory_units (organization_id, location_id);

CREATE INDEX ix_inventory_units_lot_id ON inventory_units (organization_id, lot_id);

CREATE INDEX ix_inventory_units_product_id ON inventory_units (organization_id, product_id);

CREATE INDEX ix_inventory_units_tenant ON inventory_units (organization_id);

CREATE INDEX ix_inventory_units_warehouse_id ON inventory_units (organization_id, warehouse_id);

CREATE INDEX ix_kpi_targets_employee_id ON kpi_targets (organization_id, employee_id);

CREATE INDEX ix_kpi_targets_tenant ON kpi_targets (organization_id);

CREATE INDEX ix_machines_tenant ON machines (organization_id);

CREATE INDEX ix_machines_work_center_id ON machines (organization_id, work_center_id);

CREATE INDEX ix_notifications_tenant ON notifications (organization_id);

CREATE INDEX ix_notifications_user_id ON notifications (organization_id, user_id);

CREATE INDEX ix_payment_events_tenant_time ON payment_allocation_events(organization_id,occurred_at);

CREATE INDEX ix_production_corrections_report ON production_report_corrections(report_id);

CREATE INDEX ix_production_order_operations_machine_id ON production_order_operations (organization_id, machine_id);

CREATE INDEX ix_production_order_operations_production_order_id ON production_order_operations (organization_id, production_order_id);

CREATE INDEX ix_production_order_operations_tenant ON production_order_operations (organization_id);

CREATE INDEX ix_production_order_operations_work_center_id ON production_order_operations (organization_id, work_center_id);

CREATE INDEX ix_production_orders_bom_id ON production_orders (organization_id, bom_id);

CREATE INDEX ix_production_orders_product_id ON production_orders (organization_id, product_id);

CREATE INDEX ix_production_orders_sales_order_line_id ON production_orders (organization_id, sales_order_line_id);

CREATE INDEX ix_production_orders_tenant ON production_orders (organization_id);

CREATE INDEX ix_production_reports_operation_id ON production_reports (organization_id, operation_id);

CREATE INDEX ix_production_reports_production_order_id ON production_reports (organization_id, production_order_id);

CREATE INDEX ix_production_reports_tenant ON production_reports (organization_id);

CREATE INDEX ix_products_tenant ON products (organization_id);

CREATE INDEX ix_purchase_order_lines_product_id ON purchase_order_lines (organization_id, product_id);

CREATE INDEX ix_purchase_order_lines_purchase_order_id ON purchase_order_lines (organization_id, purchase_order_id);

CREATE INDEX ix_purchase_order_lines_tenant ON purchase_order_lines (organization_id);

CREATE INDEX ix_purchase_orders_supplier_id ON purchase_orders (organization_id, supplier_id);

CREATE INDEX ix_purchase_orders_tenant ON purchase_orders (organization_id);

CREATE INDEX ix_roles_tenant ON roles (organization_id);

CREATE INDEX ix_sales_order_lines_order_id ON sales_order_lines (organization_id, order_id);

CREATE INDEX ix_sales_order_lines_product_id ON sales_order_lines (organization_id, product_id);

CREATE INDEX ix_sales_order_lines_tenant ON sales_order_lines (organization_id);

CREATE INDEX ix_sales_orders_customer_id ON sales_orders (organization_id, customer_id);

CREATE INDEX ix_sales_orders_tenant ON sales_orders (organization_id);

CREATE INDEX ix_shipment_lines_product_id ON shipment_lines (organization_id, product_id);

CREATE INDEX ix_shipment_lines_sales_order_line_id ON shipment_lines (organization_id, sales_order_line_id);

CREATE INDEX ix_shipment_lines_shipment_id ON shipment_lines (organization_id, shipment_id);

CREATE INDEX ix_shipment_lines_tenant ON shipment_lines (organization_id);

CREATE INDEX ix_shipments_customer_id ON shipments (organization_id, customer_id);

CREATE INDEX ix_shipments_sales_order_id ON shipments (organization_id, sales_order_id);

CREATE INDEX ix_shipments_tenant ON shipments (organization_id);

CREATE INDEX ix_sites_tenant ON sites (organization_id);

CREATE INDEX ix_stock_transfer_lines_inventory_unit_id ON stock_transfer_lines (organization_id, inventory_unit_id);

CREATE INDEX ix_stock_transfer_lines_lot_id ON stock_transfer_lines (organization_id, lot_id);

CREATE INDEX ix_stock_transfer_lines_product_id ON stock_transfer_lines (organization_id, product_id);

CREATE INDEX ix_stock_transfer_lines_tenant ON stock_transfer_lines (organization_id);

CREATE INDEX ix_stock_transfer_lines_transfer_id ON stock_transfer_lines (organization_id, transfer_id);

CREATE INDEX ix_stock_transfers_from_warehouse_id ON stock_transfers (organization_id, from_warehouse_id);

CREATE INDEX ix_stock_transfers_tenant ON stock_transfers (organization_id);

CREATE INDEX ix_stock_transfers_to_warehouse_id ON stock_transfers (organization_id, to_warehouse_id);

CREATE INDEX ix_supplier_bills_purchase_order_id ON supplier_bills (organization_id, purchase_order_id);

CREATE INDEX ix_supplier_bills_supplier_id ON supplier_bills (organization_id, supplier_id);

CREATE INDEX ix_supplier_bills_tenant ON supplier_bills (organization_id);

CREATE INDEX ix_supplier_payments_supplier_id ON supplier_payments (organization_id, supplier_id);

CREATE INDEX ix_supplier_payments_tenant ON supplier_payments (organization_id);

CREATE INDEX ix_suppliers_tenant ON suppliers (organization_id);

CREATE INDEX ix_task_assignees_employee_id ON task_assignees (organization_id, employee_id);

CREATE INDEX ix_task_assignees_task_id ON task_assignees (organization_id, task_id);

CREATE INDEX ix_task_assignees_tenant ON task_assignees (organization_id);

CREATE INDEX ix_task_updates_employee_id ON task_updates (organization_id, employee_id);

CREATE INDEX ix_task_updates_task_id ON task_updates (organization_id, task_id);

CREATE INDEX ix_task_updates_tenant ON task_updates (organization_id);

CREATE INDEX ix_tasks_production_order_id ON tasks (organization_id, production_order_id);

CREATE INDEX ix_tasks_tenant ON tasks (organization_id);

CREATE INDEX ix_user_roles_role_id ON user_roles (organization_id, role_id);

CREATE INDEX ix_user_roles_site_id ON user_roles (organization_id, site_id);

CREATE INDEX ix_user_roles_tenant ON user_roles (organization_id);

CREATE INDEX ix_user_roles_user_id ON user_roles (organization_id, user_id);

CREATE INDEX ix_warehouse_locations_tenant ON warehouse_locations (organization_id);

CREATE INDEX ix_warehouse_locations_warehouse_id ON warehouse_locations (organization_id, warehouse_id);

CREATE INDEX ix_warehouses_site_id ON warehouses (organization_id, site_id);

CREATE INDEX ix_warehouses_tenant ON warehouses (organization_id);

CREATE INDEX ix_work_centers_site_id ON work_centers (organization_id, site_id);

CREATE INDEX ix_work_centers_tenant ON work_centers (organization_id);

CREATE UNIQUE INDEX uq_customer_contacts_partial ON customer_contacts (customer_id) WHERE is_primary = 1;

CREATE UNIQUE INDEX uq_user_roles_partial ON user_roles (user_id, role_id) WHERE site_id IS NULL;

CREATE TRIGGER department_cycle_insert BEFORE INSERT ON departments WHEN NEW.parent_department_id IS NOT NULL BEGIN
      SELECT RAISE(ABORT,'department cycle') WHERE NEW.parent_department_id = NEW.id;
    END;

CREATE TRIGGER department_cycle_update BEFORE UPDATE OF parent_department_id ON departments WHEN NEW.parent_department_id IS NOT NULL BEGIN
      SELECT RAISE(ABORT,'department cycle') WHERE NEW.id IN (
        WITH RECURSIVE ancestors(id) AS (SELECT NEW.parent_department_id UNION SELECT d.parent_department_id FROM departments d JOIN ancestors a ON d.id=a.id WHERE d.parent_department_id IS NOT NULL) SELECT id FROM ancestors);
    END;

CREATE TRIGGER immutable_audit_log_delete BEFORE DELETE ON audit_log BEGIN SELECT RAISE(ABORT,'append-only ledger'); END;

CREATE TRIGGER immutable_audit_log_update BEFORE UPDATE ON audit_log BEGIN SELECT RAISE(ABORT,'append-only ledger'); END;

CREATE TRIGGER immutable_customer_payment_allocations_delete BEFORE DELETE ON customer_payment_allocations BEGIN SELECT RAISE(ABORT,'append-only ledger'); END;

CREATE TRIGGER immutable_inventory_movements_delete BEFORE DELETE ON inventory_movements BEGIN SELECT RAISE(ABORT,'append-only ledger'); END;

CREATE TRIGGER immutable_inventory_movements_update BEFORE UPDATE ON inventory_movements BEGIN SELECT RAISE(ABORT,'append-only ledger'); END;

CREATE TRIGGER immutable_payment_events_delete BEFORE DELETE ON payment_allocation_events BEGIN SELECT RAISE(ABORT,'append-only allocation history'); END;

CREATE TRIGGER immutable_payment_events_update BEFORE UPDATE ON payment_allocation_events BEGIN SELECT RAISE(ABORT,'append-only allocation history'); END;

CREATE TRIGGER immutable_production_corrections_delete BEFORE DELETE ON production_report_corrections BEGIN SELECT RAISE(ABORT,'append-only production corrections'); END;

CREATE TRIGGER immutable_production_corrections_update BEFORE UPDATE ON production_report_corrections BEGIN SELECT RAISE(ABORT,'append-only production corrections'); END;

CREATE TRIGGER immutable_production_reports_delete BEFORE DELETE ON production_reports BEGIN SELECT RAISE(ABORT,'append-only ledger'); END;

CREATE TRIGGER immutable_production_reports_update BEFORE UPDATE ON production_reports BEGIN SELECT RAISE(ABORT,'append-only ledger'); END;

CREATE TRIGGER immutable_task_updates_delete BEFORE DELETE ON task_updates BEGIN SELECT RAISE(ABORT,'append-only ledger'); END;

CREATE TRIGGER immutable_task_updates_update BEFORE UPDATE ON task_updates BEGIN SELECT RAISE(ABORT,'append-only ledger'); END;
