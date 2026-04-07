CREATE DATABASE IF NOT EXISTS seckill_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
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

USE order_db_0;

CREATE TABLE IF NOT EXISTS t_order_0 (
    order_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_user_id (user_id),
    KEY idx_product_id (product_id)
);

CREATE TABLE IF NOT EXISTS t_order_1 LIKE t_order_0;

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
CREATE TABLE IF NOT EXISTS t_user_purchase_record LIKE order_db_0.t_user_purchase_record;
