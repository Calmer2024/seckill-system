CREATE DATABASE IF NOT EXISTS seckill_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS inventory_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS order_db_0 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS order_db_1 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE seckill_db;

CREATE TABLE IF NOT EXISTS seckill_product (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    stock INT NOT NULL DEFAULT 0,
    category VARCHAR(32) NOT NULL DEFAULT 'home',
    rating DOUBLE NOT NULL DEFAULT 4.8,
    review_count INT NOT NULL DEFAULT 0,
    tags TEXT NOT NULL,
    summary TEXT NOT NULL,
    highlight VARCHAR(80) NOT NULL DEFAULT '',
    visual_icon VARCHAR(80) NOT NULL DEFAULT 'lucide:package-open'
);

INSERT INTO seckill_product (
    id, name, price, stock, category, rating, review_count, tags, summary, highlight, visual_icon
)
VALUES
    (1, 'CleanSweep S6 扫拖机器人', 1999.00, 36, 'home', 4.9, 1842, '["激光避障","自动回充","静音清洁"]', '适合大户型与多房间清洁的扫拖一体机器人，支持日常灰尘、毛发与地面轻污渍处理。', '全屋清洁', 'lucide:disc-3'),
    (2, 'Noise Cancel Earbuds Pro', 299.00, 48, 'music', 4.8, 2630, '["主动降噪","通勤佩戴","蓝牙 5.4"]', '轻巧贴耳的降噪耳机，适合通勤、学习和轻运动场景，兼顾低延迟与续航表现。', '沉浸音频', 'lucide:headphones'),
    (3, '4K Streaming Stick', 129.00, 54, 'home', 4.7, 1218, '["4K HDR","语音遥控","客厅影音"]', '即插即用的高清影音棒，让老电视快速接入流媒体平台，适合卧室与客厅场景升级。', '影音升级', 'lucide:tv'),
    (4, 'FocusBeam 显示器挂灯', 239.00, 42, 'desk', 4.8, 913, '["非对称照明","桌面护眼","亮度记忆"]', '针对桌面阅读与夜间办公设计的挂灯，减少屏幕反光，让桌面环境更柔和稳定。', '办公护眼', 'lucide:lamp'),
    (5, 'FlexDock 铝合金电脑支架', 159.00, 67, 'desk', 4.9, 1536, '["多角度调节","稳固承重","散热友好"]', '为笔记本和轻薄本打造的折叠支架，适合长时间编码、写作和在线会议使用。', '桌面效率', 'lucide:laptop'),
    (6, 'PulseMini 蓝牙音箱', 219.00, 58, 'music', 4.7, 842, '["低音增强","露营便携","IPX 防泼溅"]', '体积紧凑但声音饱满的蓝牙音箱，适合宿舍、小客厅和户外休闲播放使用。', '随身音乐', 'lucide:speaker'),
    (7, 'AirNest 香薰加湿灯', 179.00, 51, 'home', 4.8, 734, '["氛围夜灯","细腻水雾","卧室放松"]', '将轻雾加湿、柔光夜灯与香薰体验融合在一起，适合作为卧室和书房的放松装置。', '松弛氛围', 'lucide:droplets'),
    (8, 'GlowCup 智能暖杯垫', 99.00, 62, 'kitchen', 4.6, 667, '["恒温保温","办公桌角","自动待机"]', '适合咖啡、热茶与牛奶保温的暖杯垫，让工作与阅读时段都能喝到合适温度的饮品。', '热饮常伴', 'lucide:cup-soda'),
    (9, 'SnapGo 磁吸充电宝', 189.00, 73, 'desk', 4.8, 1406, '["磁吸对齐","轻薄便携","出门续航"]', '兼顾轻便和握持舒适度的磁吸充电宝，适合通勤、差旅和移动办公补能。', '出行续航', 'lucide:battery-charging'),
    (10, 'SilkWave 负离子吹风机', 399.00, 28, 'wellness', 4.9, 1121, '["快速干发","温控护发","旅行收纳"]', '强调风量与温控平衡的高速吹风机，适合晨间快速造型和夜间精细护发。', '轻养护发', 'lucide:wind'),
    (11, 'AeroFlow 循环风扇', 329.00, 31, 'home', 4.7, 578, '["广角送风","夏季通风","低噪运行"]', '用于客厅、卧室和工作区空气循环的静音风扇，帮助室内风感更均匀清爽。', '清爽循环', 'lucide:fan'),
    (12, 'PocketBrew 便携咖啡机', 469.00, 19, 'kitchen', 4.8, 492, '["出差随行","胶囊兼容","小巧机身"]', '为差旅与桌面咖啡需求准备的便携咖啡机，轻松在办公室和酒店喝到稳定口感。', '随行咖啡', 'lucide:coffee'),
    (13, 'CalmSleep 白噪音音箱', 149.00, 45, 'wellness', 4.7, 861, '["助眠模式","自然音效","床头陪伴"]', '内置多种自然环境声与睡眠模式的白噪音音箱，适合睡前放松和专注工作。', '舒缓助眠', 'lucide:moon-star'),
    (14, 'FrameCam 智能家居摄像头', 259.00, 37, 'home', 4.8, 1324, '["移动侦测","双向通话","居家守护"]', '适合玄关、客厅和儿童房的家用摄像头，帮助你更方便查看家中动态与安全状态。', '居家守护', 'lucide:camera'),
    (15, 'FlexNote 墨水屏记事本', 599.00, 22, 'desk', 4.9, 1005, '["轻办公","手写同步","无纸整理"]', '面向会议记录、课程笔记和灵感整理的墨水屏设备，兼顾阅读舒适和轻量记录体验。', '轻量创作', 'lucide:notebook-pen'),
    (16, 'MoveBeat 运动挂耳耳机', 269.00, 57, 'music', 4.7, 944, '["稳固佩戴","跑步通勤","长续航"]', '专为跑步、力量训练和城市骑行准备的挂耳耳机，兼顾稳固性和通透听感。', '运动陪练', 'lucide:headphones'),
    (17, 'FreshBox 真空封口机', 219.00, 33, 'kitchen', 4.6, 506, '["食材保鲜","一键封口","厨房整理"]', '帮助肉类、蔬果和坚果延长保鲜周期的真空封口机，适合日常备餐和冰箱收纳。', '保鲜整理', 'lucide:package-check'),
    (18, 'ReliefPulse 颈部按摩仪', 359.00, 26, 'wellness', 4.8, 783, '["热敷放松","轻柔脉冲","久坐舒缓"]', '面向久坐办公和肩颈疲劳场景的按摩仪，支持热敷与多档力度调节。', '肩颈舒缓', 'lucide:heart-pulse'),
    (19, 'DockHub 7 合 1 扩展坞', 279.00, 41, 'desk', 4.8, 1179, '["多口扩展","桌搭整洁","高速传输"]', '为轻薄本用户准备的桌面扩展坞，适合连接显示器、U 盘和常用外设。', '接口扩展', 'lucide:usb'),
    (20, 'LumiClock 日出唤醒灯', 199.00, 39, 'wellness', 4.7, 694, '["日出模拟","晨间唤醒","床头氛围"]', '通过渐亮光线与舒缓铃声模拟自然醒来节奏，帮助建立更平和的晨起体验。', '晨间唤醒', 'lucide:sun')
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    price = VALUES(price),
    stock = VALUES(stock),
    category = VALUES(category),
    rating = VALUES(rating),
    review_count = VALUES(review_count),
    tags = VALUES(tags),
    summary = VALUES(summary),
    highlight = VALUES(highlight),
    visual_icon = VALUES(visual_icon);

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
    (1, 'CleanSweep S6 扫拖机器人', 1999.00, 36, 0, 0),
    (2, 'Noise Cancel Earbuds Pro', 299.00, 48, 0, 0),
    (3, '4K Streaming Stick', 129.00, 54, 0, 0),
    (4, 'FocusBeam 显示器挂灯', 239.00, 42, 0, 0),
    (5, 'FlexDock 铝合金电脑支架', 159.00, 67, 0, 0),
    (6, 'PulseMini 蓝牙音箱', 219.00, 58, 0, 0),
    (7, 'AirNest 香薰加湿灯', 179.00, 51, 0, 0),
    (8, 'GlowCup 智能暖杯垫', 99.00, 62, 0, 0),
    (9, 'SnapGo 磁吸充电宝', 189.00, 73, 0, 0),
    (10, 'SilkWave 负离子吹风机', 399.00, 28, 0, 0),
    (11, 'AeroFlow 循环风扇', 329.00, 31, 0, 0),
    (12, 'PocketBrew 便携咖啡机', 469.00, 19, 0, 0),
    (13, 'CalmSleep 白噪音音箱', 149.00, 45, 0, 0),
    (14, 'FrameCam 智能家居摄像头', 259.00, 37, 0, 0),
    (15, 'FlexNote 墨水屏记事本', 599.00, 22, 0, 0),
    (16, 'MoveBeat 运动挂耳耳机', 269.00, 57, 0, 0),
    (17, 'FreshBox 真空封口机', 219.00, 33, 0, 0),
    (18, 'ReliefPulse 颈部按摩仪', 359.00, 26, 0, 0),
    (19, 'DockHub 7 合 1 扩展坞', 279.00, 41, 0, 0),
    (20, 'LumiClock 日出唤醒灯', 199.00, 39, 0, 0)
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
