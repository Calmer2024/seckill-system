CREATE DATABASE IF NOT EXISTS seckill_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS inventory_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS order_db_0 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS order_db_1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE seckill_db;

CREATE TABLE IF NOT EXISTS seckill_product (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    stock INT NOT NULL DEFAULT 0
);

INSERT INTO seckill_product (id, name, price, stock)
VALUES
    (1, 'Adudu Cleaner Pro', 19.90, 30),
    (2, 'Noise Cancel Earbuds', 299.00, 20),
    (3, '4K Streaming Stick', 129.00, 15)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    price = VALUES(price),
    stock = VALUES(stock);

USE inventory_db;

CREATE TABLE IF NOT EXISTS inventory_item (
    product_id INT PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    available_stock INT NOT NULL DEFAULT 0,
    reserved_stock INT NOT NULL DEFAULT 0,
    sold_stock INT NOT NULL DEFAULT 0,
    version INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory_reservation (
    order_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    status VARCHAR(32) NOT NULL,
    failure_reason VARCHAR(128) DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_user_product_status (user_id, product_id, status)
);

CREATE TABLE IF NOT EXISTS inventory_outbox_event (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    aggregate_id BIGINT NOT NULL,
    topic VARCHAR(128) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    payload JSON NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'NEW',
    retry_count INT NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMP NULL DEFAULT NULL,
    published_at TIMESTAMP NULL DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_outbox_status_retry (status, next_retry_at),
    KEY idx_outbox_aggregate_id (aggregate_id)
);

INSERT INTO inventory_item (product_id, product_name, unit_price, available_stock, reserved_stock, sold_stock)
VALUES
    (1, 'Adudu Cleaner Pro', 19.90, 30, 0, 0),
    (2, 'Noise Cancel Earbuds', 299.00, 20, 0, 0),
    (3, '4K Streaming Stick', 129.00, 15, 0, 0)
ON DUPLICATE KEY UPDATE
    product_name = VALUES(product_name),
    unit_price = VALUES(unit_price),
    available_stock = VALUES(available_stock),
    reserved_stock = VALUES(reserved_stock),
    sold_stock = VALUES(sold_stock);

USE order_db_0;

CREATE TABLE IF NOT EXISTS t_order_0 (
    order_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    failure_reason VARCHAR(128) DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_user_id (user_id),
    KEY idx_product_id (product_id)
);

CREATE TABLE IF NOT EXISTS t_order_1 LIKE t_order_0;

CREATE TABLE IF NOT EXISTS t_payment_0 (
    order_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_user_id (user_id)
);

CREATE TABLE IF NOT EXISTS t_payment_1 LIKE t_payment_0;

CREATE TABLE IF NOT EXISTS t_order_outbox_event_0 (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    aggregate_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    topic VARCHAR(128) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    payload JSON NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'NEW',
    retry_count INT NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMP NULL DEFAULT NULL,
    published_at TIMESTAMP NULL DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_status_retry (status, next_retry_at),
    KEY idx_user_id (user_id),
    KEY idx_aggregate_id (aggregate_id)
);

CREATE TABLE IF NOT EXISTS t_order_outbox_event_1 LIKE t_order_outbox_event_0;

CREATE TABLE IF NOT EXISTS t_user_purchase_record (
    user_id BIGINT NOT NULL,
    product_id INT NOT NULL,
    order_id BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, product_id),
    UNIQUE KEY uk_order_id (order_id)
);

USE order_db_1;

CREATE TABLE IF NOT EXISTS t_order_0 LIKE order_db_0.t_order_0;
CREATE TABLE IF NOT EXISTS t_order_1 LIKE order_db_0.t_order_1;
CREATE TABLE IF NOT EXISTS t_payment_0 LIKE order_db_0.t_payment_0;
CREATE TABLE IF NOT EXISTS t_payment_1 LIKE order_db_0.t_payment_1;
CREATE TABLE IF NOT EXISTS t_order_outbox_event_0 LIKE order_db_0.t_order_outbox_event_0;
CREATE TABLE IF NOT EXISTS t_order_outbox_event_1 LIKE order_db_0.t_order_outbox_event_1;
CREATE TABLE IF NOT EXISTS t_user_purchase_record LIKE order_db_0.t_user_purchase_record;
