from sqlalchemy import text
from sqlalchemy.engine import Engine


INVENTORY_CATALOG: list[dict[str, object]] = [
    {"product_id": 1, "product_name": "CleanSweep S6 扫拖机器人", "unit_price": 1999.00, "available_stock": 36},
    {"product_id": 2, "product_name": "Noise Cancel Earbuds Pro", "unit_price": 299.00, "available_stock": 48},
    {"product_id": 3, "product_name": "4K Streaming Stick", "unit_price": 129.00, "available_stock": 54},
    {"product_id": 4, "product_name": "FocusBeam 显示器挂灯", "unit_price": 239.00, "available_stock": 42},
    {"product_id": 5, "product_name": "FlexDock 铝合金电脑支架", "unit_price": 159.00, "available_stock": 67},
    {"product_id": 6, "product_name": "PulseMini 蓝牙音箱", "unit_price": 219.00, "available_stock": 58},
    {"product_id": 7, "product_name": "AirNest 香薰加湿灯", "unit_price": 179.00, "available_stock": 51},
    {"product_id": 8, "product_name": "GlowCup 智能暖杯垫", "unit_price": 99.00, "available_stock": 62},
    {"product_id": 9, "product_name": "SnapGo 磁吸充电宝", "unit_price": 189.00, "available_stock": 73},
    {"product_id": 10, "product_name": "SilkWave 负离子吹风机", "unit_price": 399.00, "available_stock": 28},
    {"product_id": 11, "product_name": "AeroFlow 循环风扇", "unit_price": 329.00, "available_stock": 31},
    {"product_id": 12, "product_name": "PocketBrew 便携咖啡机", "unit_price": 469.00, "available_stock": 19},
    {"product_id": 13, "product_name": "CalmSleep 白噪音音箱", "unit_price": 149.00, "available_stock": 45},
    {"product_id": 14, "product_name": "FrameCam 智能家居摄像头", "unit_price": 259.00, "available_stock": 37},
    {"product_id": 15, "product_name": "FlexNote 墨水屏记事本", "unit_price": 599.00, "available_stock": 22},
    {"product_id": 16, "product_name": "MoveBeat 运动挂耳耳机", "unit_price": 269.00, "available_stock": 57},
    {"product_id": 17, "product_name": "FreshBox 真空封口机", "unit_price": 219.00, "available_stock": 33},
    {"product_id": 18, "product_name": "ReliefPulse 颈部按摩仪", "unit_price": 359.00, "available_stock": 26},
    {"product_id": 19, "product_name": "DockHub 7 合 1 扩展坞", "unit_price": 279.00, "available_stock": 41},
    {"product_id": 20, "product_name": "LumiClock 日出唤醒灯", "unit_price": 199.00, "available_stock": 39},
]


def ensure_inventory_catalog(engine: Engine) -> None:
    statement = text(
        """
        INSERT INTO inventory_item (
            product_id, product_name, unit_price, available_stock, reserved_stock, sold_stock, version
        ) VALUES (
            :product_id, :product_name, :unit_price, :available_stock, 0, 0, 0
        )
        ON DUPLICATE KEY UPDATE
            product_name = VALUES(product_name),
            unit_price = VALUES(unit_price)
        """
    )

    with engine.begin() as connection:
        for item in INVENTORY_CATALOG:
            connection.execute(statement, item)
