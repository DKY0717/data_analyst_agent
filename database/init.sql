-- 数据库初始化脚本
-- 创建电商业务所需的表结构

-- 地区表
CREATE TABLE IF NOT EXISTS regions (
    region_id INTEGER PRIMARY KEY,
    region_name VARCHAR,
    province VARCHAR,
    city VARCHAR
);

-- 客户表
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    customer_name VARCHAR,
    gender VARCHAR,
    age INTEGER,
    region_id INTEGER,
    register_date DATE,
    FOREIGN KEY (region_id) REFERENCES regions(region_id)
);

-- 商品类别表
CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY,
    category_name VARCHAR
);

-- 商品表
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    product_name VARCHAR,
    category_id INTEGER,
    price DECIMAL(10,2),
    cost DECIMAL(10,2),
    created_at DATE,
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

-- 订单表
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    order_date DATE,
    status VARCHAR,
    total_amount DECIMAL(10,2),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- 订单明细表
CREATE TABLE IF NOT EXISTS order_items (
    item_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    unit_price DECIMAL(10,2),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 支付表
CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    payment_method VARCHAR,
    payment_status VARCHAR,
    paid_amount DECIMAL(10,2),
    paid_at TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- 退款表
CREATE TABLE IF NOT EXISTS refunds (
    refund_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    refund_amount DECIMAL(10,2),
    refund_reason VARCHAR,
    refund_date DATE,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);