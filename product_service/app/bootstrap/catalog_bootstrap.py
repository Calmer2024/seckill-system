import json

from redis import Redis
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.core.config import settings


PRODUCT_CATALOG: list[dict[str, object]] = [
    {
        "id": 1,
        "name": "CleanSweep S6 扫拖机器人",
        "price": 1999.00,
        "stock": 36,
        "category": "home",
        "rating": 4.9,
        "review_count": 1842,
        "tags": ["激光避障", "自动回充", "静音清洁"],
        "summary": "适合大户型与多房间清洁的扫拖一体机器人，支持日常灰尘、毛发与地面轻污渍处理。",
        "highlight": "全屋清洁",
        "visual_icon": "lucide:disc-3",
    },
    {
        "id": 2,
        "name": "Noise Cancel Earbuds Pro",
        "price": 299.00,
        "stock": 48,
        "category": "music",
        "rating": 4.8,
        "review_count": 2630,
        "tags": ["主动降噪", "通勤佩戴", "蓝牙 5.4"],
        "summary": "轻巧贴耳的降噪耳机，适合通勤、学习和轻运动场景，兼顾低延迟与续航表现。",
        "highlight": "沉浸音频",
        "visual_icon": "lucide:headphones",
    },
    {
        "id": 3,
        "name": "4K Streaming Stick",
        "price": 129.00,
        "stock": 54,
        "category": "home",
        "rating": 4.7,
        "review_count": 1218,
        "tags": ["4K HDR", "语音遥控", "客厅影音"],
        "summary": "即插即用的高清影音棒，让老电视快速接入流媒体平台，适合卧室与客厅场景升级。",
        "highlight": "影音升级",
        "visual_icon": "lucide:tv",
    },
    {
        "id": 4,
        "name": "FocusBeam 显示器挂灯",
        "price": 239.00,
        "stock": 42,
        "category": "desk",
        "rating": 4.8,
        "review_count": 913,
        "tags": ["非对称照明", "桌面护眼", "亮度记忆"],
        "summary": "针对桌面阅读与夜间办公设计的挂灯，减少屏幕反光，让桌面环境更柔和稳定。",
        "highlight": "办公护眼",
        "visual_icon": "lucide:lamp",
    },
    {
        "id": 5,
        "name": "FlexDock 铝合金电脑支架",
        "price": 159.00,
        "stock": 67,
        "category": "desk",
        "rating": 4.9,
        "review_count": 1536,
        "tags": ["多角度调节", "稳固承重", "散热友好"],
        "summary": "为笔记本和轻薄本打造的折叠支架，适合长时间编码、写作和在线会议使用。",
        "highlight": "桌面效率",
        "visual_icon": "lucide:laptop",
    },
    {
        "id": 6,
        "name": "PulseMini 蓝牙音箱",
        "price": 219.00,
        "stock": 58,
        "category": "music",
        "rating": 4.7,
        "review_count": 842,
        "tags": ["低音增强", "露营便携", "IPX 防泼溅"],
        "summary": "体积紧凑但声音饱满的蓝牙音箱，适合宿舍、小客厅和户外休闲播放使用。",
        "highlight": "随身音乐",
        "visual_icon": "lucide:speaker",
    },
    {
        "id": 7,
        "name": "AirNest 香薰加湿灯",
        "price": 179.00,
        "stock": 51,
        "category": "home",
        "rating": 4.8,
        "review_count": 734,
        "tags": ["氛围夜灯", "细腻水雾", "卧室放松"],
        "summary": "将轻雾加湿、柔光夜灯与香薰体验融合在一起，适合作为卧室和书房的放松装置。",
        "highlight": "松弛氛围",
        "visual_icon": "lucide:droplets",
    },
    {
        "id": 8,
        "name": "GlowCup 智能暖杯垫",
        "price": 99.00,
        "stock": 62,
        "category": "kitchen",
        "rating": 4.6,
        "review_count": 667,
        "tags": ["恒温保温", "办公桌角", "自动待机"],
        "summary": "适合咖啡、热茶与牛奶保温的暖杯垫，让工作与阅读时段都能喝到合适温度的饮品。",
        "highlight": "热饮常伴",
        "visual_icon": "lucide:cup-soda",
    },
    {
        "id": 9,
        "name": "SnapGo 磁吸充电宝",
        "price": 189.00,
        "stock": 73,
        "category": "desk",
        "rating": 4.8,
        "review_count": 1406,
        "tags": ["磁吸对齐", "轻薄便携", "出门续航"],
        "summary": "兼顾轻便和握持舒适度的磁吸充电宝，适合通勤、差旅和移动办公补能。",
        "highlight": "出行续航",
        "visual_icon": "lucide:battery-charging",
    },
    {
        "id": 10,
        "name": "SilkWave 负离子吹风机",
        "price": 399.00,
        "stock": 28,
        "category": "wellness",
        "rating": 4.9,
        "review_count": 1121,
        "tags": ["快速干发", "温控护发", "旅行收纳"],
        "summary": "强调风量与温控平衡的高速吹风机，适合晨间快速造型和夜间精细护发。",
        "highlight": "轻养护发",
        "visual_icon": "lucide:wind",
    },
    {
        "id": 11,
        "name": "AeroFlow 循环风扇",
        "price": 329.00,
        "stock": 31,
        "category": "home",
        "rating": 4.7,
        "review_count": 578,
        "tags": ["广角送风", "夏季通风", "低噪运行"],
        "summary": "用于客厅、卧室和工作区空气循环的静音风扇，帮助室内风感更均匀清爽。",
        "highlight": "清爽循环",
        "visual_icon": "lucide:fan",
    },
    {
        "id": 12,
        "name": "PocketBrew 便携咖啡机",
        "price": 469.00,
        "stock": 19,
        "category": "kitchen",
        "rating": 4.8,
        "review_count": 492,
        "tags": ["出差随行", "胶囊兼容", "小巧机身"],
        "summary": "为差旅与桌面咖啡需求准备的便携咖啡机，轻松在办公室和酒店喝到稳定口感。",
        "highlight": "随行咖啡",
        "visual_icon": "lucide:coffee",
    },
    {
        "id": 13,
        "name": "CalmSleep 白噪音音箱",
        "price": 149.00,
        "stock": 45,
        "category": "wellness",
        "rating": 4.7,
        "review_count": 861,
        "tags": ["助眠模式", "自然音效", "床头陪伴"],
        "summary": "内置多种自然环境声与睡眠模式的白噪音音箱，适合睡前放松和专注工作。",
        "highlight": "舒缓助眠",
        "visual_icon": "lucide:moon-star",
    },
    {
        "id": 14,
        "name": "FrameCam 智能家居摄像头",
        "price": 259.00,
        "stock": 37,
        "category": "home",
        "rating": 4.8,
        "review_count": 1324,
        "tags": ["移动侦测", "双向通话", "居家守护"],
        "summary": "适合玄关、客厅和儿童房的家用摄像头，帮助你更方便查看家中动态与安全状态。",
        "highlight": "居家守护",
        "visual_icon": "lucide:camera",
    },
    {
        "id": 15,
        "name": "FlexNote 墨水屏记事本",
        "price": 599.00,
        "stock": 22,
        "category": "desk",
        "rating": 4.9,
        "review_count": 1005,
        "tags": ["轻办公", "手写同步", "无纸整理"],
        "summary": "面向会议记录、课程笔记和灵感整理的墨水屏设备，兼顾阅读舒适和轻量记录体验。",
        "highlight": "轻量创作",
        "visual_icon": "lucide:notebook-pen",
    },
    {
        "id": 16,
        "name": "MoveBeat 运动挂耳耳机",
        "price": 269.00,
        "stock": 57,
        "category": "music",
        "rating": 4.7,
        "review_count": 944,
        "tags": ["稳固佩戴", "跑步通勤", "长续航"],
        "summary": "专为跑步、力量训练和城市骑行准备的挂耳耳机，兼顾稳固性和通透听感。",
        "highlight": "运动陪练",
        "visual_icon": "lucide:headphones",
    },
    {
        "id": 17,
        "name": "FreshBox 真空封口机",
        "price": 219.00,
        "stock": 33,
        "category": "kitchen",
        "rating": 4.6,
        "review_count": 506,
        "tags": ["食材保鲜", "一键封口", "厨房整理"],
        "summary": "帮助肉类、蔬果和坚果延长保鲜周期的真空封口机，适合日常备餐和冰箱收纳。",
        "highlight": "保鲜整理",
        "visual_icon": "lucide:package-check",
    },
    {
        "id": 18,
        "name": "ReliefPulse 颈部按摩仪",
        "price": 359.00,
        "stock": 26,
        "category": "wellness",
        "rating": 4.8,
        "review_count": 783,
        "tags": ["热敷放松", "轻柔脉冲", "久坐舒缓"],
        "summary": "面向久坐办公和肩颈疲劳场景的按摩仪，支持热敷与多档力度调节。",
        "highlight": "肩颈舒缓",
        "visual_icon": "lucide:heart-pulse",
    },
    {
        "id": 19,
        "name": "DockHub 7 合 1 扩展坞",
        "price": 279.00,
        "stock": 41,
        "category": "desk",
        "rating": 4.8,
        "review_count": 1179,
        "tags": ["多口扩展", "桌搭整洁", "高速传输"],
        "summary": "为轻薄本用户准备的桌面扩展坞，适合连接显示器、U 盘和常用外设。",
        "highlight": "接口扩展",
        "visual_icon": "lucide:usb",
    },
    {
        "id": 20,
        "name": "LumiClock 日出唤醒灯",
        "price": 199.00,
        "stock": 39,
        "category": "wellness",
        "rating": 4.7,
        "review_count": 694,
        "tags": ["日出模拟", "晨间唤醒", "床头氛围"],
        "summary": "通过渐亮光线与舒缓铃声模拟自然醒来节奏，帮助建立更平和的晨起体验。",
        "highlight": "晨间唤醒",
        "visual_icon": "lucide:sun",
    },
]


def ensure_product_schema_and_seed(engine: Engine) -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("seckill_product")}

    column_definitions = {
        "category": "ALTER TABLE seckill_product ADD COLUMN category VARCHAR(32) NOT NULL DEFAULT 'home'",
        "rating": "ALTER TABLE seckill_product ADD COLUMN rating DOUBLE NOT NULL DEFAULT 4.8",
        "review_count": "ALTER TABLE seckill_product ADD COLUMN review_count INT NOT NULL DEFAULT 0",
        "tags": "ALTER TABLE seckill_product ADD COLUMN tags TEXT NOT NULL",
        "summary": "ALTER TABLE seckill_product ADD COLUMN summary TEXT NOT NULL",
        "highlight": "ALTER TABLE seckill_product ADD COLUMN highlight VARCHAR(80) NOT NULL DEFAULT ''",
        "visual_icon": "ALTER TABLE seckill_product ADD COLUMN visual_icon VARCHAR(80) NOT NULL DEFAULT 'lucide:package-open'",
    }

    with engine.begin() as connection:
        for name, statement in column_definitions.items():
            if name not in columns:
                try:
                    connection.execute(text(statement))
                except OperationalError as exc:
                    if "Duplicate column name" not in str(exc):
                        raise

        upsert_statement = text(
            """
            INSERT INTO seckill_product (
                id, name, price, stock, category, rating, review_count, tags, summary, highlight, visual_icon
            ) VALUES (
                :id, :name, :price, :stock, :category, :rating, :review_count, :tags, :summary, :highlight, :visual_icon
            )
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
                visual_icon = VALUES(visual_icon)
            """
        )
        for item in PRODUCT_CATALOG:
            connection.execute(
                upsert_statement,
                {
                    **item,
                    "tags": json.dumps(item["tags"], ensure_ascii=False),
                },
            )


def clear_product_cache(redis_client: Redis) -> None:
    pattern = f"{settings.CACHE_KEY_PREFIX}:*"
    cursor = 0
    while True:
        cursor, keys = redis_client.scan(cursor=cursor, match=pattern, count=200)
        if keys:
            redis_client.delete(*keys)
        if cursor == 0:
            break


def seed_product_catalog(session: Session) -> None:
    ensure_product_schema_and_seed(session.get_bind())
