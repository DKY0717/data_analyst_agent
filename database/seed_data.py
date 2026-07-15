# 模拟数据生成脚本
# 生成电商业务所需的测试数据（扩大版）

import random
import sys
from contextlib import nullcontext
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.db.connection import db_connection

random.seed(42)

REGIONS_DATA = [
    (1, "East", "Zhejiang", "Hangzhou"), (2, "East", "Shanghai", "Shanghai"),
    (3, "East", "Jiangsu", "Nanjing"), (4, "East", "Shandong", "Qingdao"),
    (5, "East", "Fujian", "Xiamen"), (6, "East", "Anhui", "Hefei"),
    (7, "South", "Guangdong", "Guangzhou"), (8, "South", "Guangdong", "Shenzhen"),
    (9, "South", "Guangdong", "Dongguan"), (10, "South", "Guangxi", "Nanning"),
    (11, "South", "Hainan", "Haikou"), (12, "North", "Beijing", "Beijing"),
    (13, "North", "Hebei", "Shijiazhuang"), (14, "North", "Tianjin", "Tianjin"),
    (15, "North", "Shanxi", "Taiyuan"), (16, "North", "Inner Mongolia", "Hohhot"),
    (17, "West", "Sichuan", "Chengdu"), (18, "West", "Chongqing", "Chongqing"),
    (19, "West", "Yunnan", "Kunming"), (20, "West", "Guizhou", "Guiyang"),
    (21, "West", "Shaanxi", "Xian"), (22, "West", "Gansu", "Lanzhou"),
    (23, "Central", "Hubei", "Wuhan"), (24, "Central", "Hunan", "Changsha"),
    (25, "Central", "Henan", "Zhengzhou"), (26, "Central", "Jiangxi", "Nanchang"),
    (27, "Northeast", "Liaoning", "Shenyang"), (28, "Northeast", "Jilin", "Changchun"),
    (29, "Northeast", "Heilongjiang", "Harbin"), (30, "Northeast", "Dalian", "Dalian"),
]

CATEGORIES_DATA = [
    (1, "Electronics"), (2, "Clothing"), (3, "Food"), (4, "Home"),
    (5, "Books"), (6, "Sports"), (7, "Beauty"), (8, "Toys"),
]

PRODUCT_TEMPLATES = {
    1: [
        ("Laptop", 4999, 3500), ("Smartphone", 2999, 2100), ("Tablet", 1999, 1400),
        ("Headphones", 299, 150), ("Smartwatch", 599, 350), ("Monitor", 1299, 800),
        ("Keyboard", 199, 80), ("Mouse", 99, 40), ("USB Hub", 79, 30),
        ("Webcam", 249, 100), ("Speaker", 399, 180), ("Charger", 69, 25),
        ("Power Bank", 129, 50), ("SSD 1TB", 499, 280), ("RAM 16GB", 299, 150),
        ("Graphics Card", 2999, 2200), ("CPU", 1899, 1400), ("Motherboard", 799, 500),
        ("Case", 299, 120), ("PSU", 399, 200), ("Router", 249, 100),
        ("Earbuds", 199, 80), ("Camera", 3499, 2500), ("Drone", 2499, 1800),
        ("Printer", 699, 400),
    ],
    2: [
        ("T-Shirt", 89, 35), ("Jeans", 199, 80), ("Jacket", 399, 180),
        ("Sneakers", 499, 250), ("Dress", 299, 120), ("Hoodie", 249, 100),
        ("Shorts", 129, 50), ("Skirt", 169, 70), ("Coat", 599, 280),
        ("Sweater", 279, 110), ("Polo", 159, 60), ("Vest", 199, 80),
        ("Scarf", 89, 35), ("Hat", 69, 25), ("Belt", 129, 50),
        ("Socks 3-Pack", 39, 12), ("Underwear", 59, 20), ("Pajamas", 149, 55),
        ("Suit", 899, 400), ("Tie", 99, 35), ("Gloves", 79, 30),
        ("Swimwear", 139, 50), ("Sportswear", 199, 80), ("Boots", 449, 200),
        ("Sandals", 179, 70),
    ],
    3: [
        ("Coffee Beans", 68, 30), ("Chocolate", 39, 15), ("Tea Set", 128, 60),
        ("Snack Box", 59, 25), ("Honey", 88, 40), ("Nuts", 49, 20),
        ("Dried Fruit", 39, 15), ("Chips", 19, 8), ("Cookies", 29, 12),
        ("Juice", 15, 6), ("Milk", 12, 5), ("Bread", 8, 3),
        ("Rice 5kg", 39, 20), ("Oil 5L", 59, 30), ("Sauce", 19, 8),
        ("Spices", 25, 10), ("Candy", 15, 5), ("Gum", 8, 3),
        ("Energy Bar", 12, 5), ("Protein Powder", 199, 80), ("Vitamins", 89, 35),
        ("Cereal", 29, 12), ("Yogurt", 9, 4), ("Ice Cream", 19, 8),
        ("Seafood", 89, 45),
    ],
    4: [
        ("Pillow", 99, 40), ("Blanket", 199, 80), ("Lamp", 149, 70),
        ("Vase", 79, 35), ("Rug", 299, 120), ("Curtain", 249, 100),
        ("Cushion", 69, 28), ("Towel", 49, 18), ("Sheet Set", 189, 75),
        ("Duvet", 349, 140), ("Clock", 89, 35), ("Mirror", 199, 80),
        ("Shelf", 249, 100), ("Basket", 59, 22), ("Hanger 10-Pack", 39, 15),
        ("Cleaning Set", 79, 30), ("Trash Can", 49, 18), ("Doormat", 59, 22),
        ("Candle", 39, 15), ("Photo Frame", 49, 18), ("Plant Pot", 39, 15),
        ("Storage Box", 69, 28), ("Iron", 199, 80), ("Vacuum", 599, 280),
        ("Air Purifier", 899, 450),
    ],
    5: [
        ("Python Book", 59, 20), ("Data Science Book", 69, 25), ("Novel", 39, 12),
        ("Cookbook", 49, 18), ("History Book", 55, 20), ("Science Book", 65, 25),
        ("Art Book", 89, 35), ("Travel Guide", 45, 18), ("Dictionary", 79, 30),
        ("Magazine", 15, 5), ("Comic", 25, 10), ("Poetry", 29, 10),
        ("Business Book", 59, 22), ("Philosophy", 45, 18), ("Psychology", 55, 22),
        ("Children Book", 35, 12), ("Textbook", 89, 35), ("Language Book", 49, 18),
        ("Music Book", 59, 22), ("Photography", 79, 30), ("Gardening", 39, 15),
        ("Fitness", 45, 18), ("Self-Help", 39, 15), ("Biography", 49, 18),
        ("Fantasy Novel", 35, 12),
    ],
    6: [
        ("Yoga Mat", 89, 35), ("Dumbbells", 149, 60), ("Running Shoes", 399, 180),
        ("Water Bottle", 39, 12), ("Sports Bag", 129, 50), ("Resistance Bands", 49, 18),
        ("Jump Rope", 29, 10), ("Foam Roller", 69, 28), ("Gloves", 59, 22),
        ("Wristband", 19, 7), ("Knee Pad", 39, 15), ("Bike Helmet", 199, 80),
        ("Tennis Racket", 299, 120), ("Basketball", 99, 40), ("Football", 89, 35),
        ("Badminton Set", 129, 50), ("Swimming Goggles", 69, 28), ("Ski Goggles", 199, 80),
        ("Hiking Boots", 499, 220), ("Tent", 599, 280), ("Sleeping Bag", 299, 120),
        ("Backpack", 249, 100), ("Compass", 39, 15), ("Binoculars", 399, 180),
        ("Fitness Tracker", 299, 130),
    ],
    7: [
        ("Face Cream", 199, 80), ("Lipstick", 129, 45), ("Perfume", 399, 150),
        ("Shampoo", 69, 25), ("Sunscreen", 89, 35), ("Moisturizer", 149, 55),
        ("Serum", 249, 90), ("Mask", 79, 28), ("Toner", 99, 38),
        ("Cleanser", 89, 32), ("Eye Cream", 179, 65), ("Hand Cream", 59, 20),
        ("Body Lotion", 79, 28), ("Hair Oil", 99, 38), ("Nail Polish", 39, 12),
        ("Makeup Brush Set", 149, 55), ("Foundation", 179, 65), ("Mascara", 99, 35),
        ("Eyeliner", 59, 20), ("Blush", 89, 32), ("Primer", 129, 48),
        ("Setting Spray", 79, 28), ("Hair Dryer", 299, 120), ("Straightener", 249, 100),
        ("Bath Bomb", 29, 10),
    ],
    8: [
        ("LEGO Set", 299, 120), ("Board Game", 99, 40), ("Puzzle", 59, 20),
        ("Stuffed Animal", 79, 30), ("Remote Car", 149, 60), ("Doll", 89, 35),
        ("Building Blocks", 69, 25), ("Art Kit", 79, 30), ("Science Kit", 129, 50),
        ("Card Game", 39, 15), ("Action Figure", 99, 40), ("Train Set", 199, 80),
        ("Play Dough", 29, 10), ("Kite", 39, 15), ("Slime Kit", 25, 8),
        ("Robot Kit", 249, 100), ("Drone Toy", 199, 80), ("Puzzle 3D", 89, 35),
        ("Musical Instrument", 149, 60), ("Outdoor Toy", 79, 30),
        ("Edu Toy", 119, 45), ("Water Gun", 49, 18), ("Bubble Machine", 39, 15),
        ("Toy Car", 59, 22), ("Jigsaw 1000pc", 69, 25),
    ],
}

SURNAMES = ["Zhang", "Li", "Wang", "Liu", "Chen", "Yang", "Huang", "Zhao", "Wu", "Zhou",
            "Xu", "Sun", "Ma", "Zhu", "Hu", "Guo", "He", "Lin", "Luo", "Zheng"]
GENDERS = ["Male", "Female"]
PAYMENT_METHODS = ["Alipay", "WeChat Pay", "Credit Card", "Debit Card"]
PAYMENT_STATUSES_WEIGHTED = ["Paid"] * 7 + ["Failed", "Pending"]
ORDER_STATUSES_WEIGHTED = ["Completed"] * 6 + ["Cancelled", "Refunded"]
REFUND_REASONS = ["Quality Issue", "Not as Described", "Wrong Item", "Changed Mind", "Late Delivery", "Damaged in Transit"]
TABLE_DELETE_ORDER = [
    "refunds",
    "payments",
    "order_items",
    "orders",
    "customers",
    "products",
    "categories",
    "regions",
]


def generate_regions():
    return REGIONS_DATA


def generate_categories():
    return CATEGORIES_DATA


def generate_products():
    products = []
    product_id = 1
    for category_id, templates in PRODUCT_TEMPLATES.items():
        for name, price, cost in templates:
            created_at = datetime(2022, 1, 1) + timedelta(days=random.randint(0, 365))
            products.append((product_id, name, category_id, price, cost, created_at.strftime("%Y-%m-%d")))
            product_id += 1
    return products


def generate_customers(num_customers=1000):
    customers = []
    for i in range(1, num_customers + 1):
        name = f"{random.choice(SURNAMES)}_{i}"
        gender = random.choice(GENDERS)
        age = random.randint(18, 65)
        region_id = random.randint(1, len(REGIONS_DATA))
        register_date = datetime(2022, 1, 1) + timedelta(days=random.randint(0, 730))
        customers.append((i, name, gender, age, region_id, register_date.strftime("%Y-%m-%d")))
    return customers


def generate_orders_and_items(products, customers):
    orders = []
    order_items = []
    order_id = 1
    item_id = 1

    for customer_id in range(1, len(customers) + 1):
        num_orders = random.randint(3, 8)
        for _ in range(num_orders):
            order_date = datetime(2022, 1, 1) + timedelta(days=random.randint(0, 1095))
            status = random.choice(ORDER_STATUSES_WEIGHTED)
            num_items = random.randint(1, 4)
            selected_products = random.sample(products, num_items)

            total_amount = 0
            for product in selected_products:
                product_id = product[0]
                unit_price = product[3]
                quantity = random.randint(1, 3)
                total_amount += unit_price * quantity
                order_items.append((item_id, order_id, product_id, quantity, unit_price))
                item_id += 1

            orders.append((order_id, customer_id, order_date.strftime("%Y-%m-%d"), status, round(total_amount, 2)))
            order_id += 1

    return orders, order_items


def generate_payments(orders):
    payments = []
    for i, order in enumerate(orders, 1):
        order_id = order[0]
        order_date = datetime.strptime(order[2], "%Y-%m-%d")
        status = order[3]
        total_amount = order[4]
        payment_method = random.choice(PAYMENT_METHODS)

        if status == "Cancelled":
            payment_status = "Failed"
        elif status == "Refunded":
            payment_status = "Paid"
        else:
            payment_status = random.choice(PAYMENT_STATUSES_WEIGHTED)

        paid_amount = total_amount if payment_status == "Paid" else 0
        paid_at = order_date + timedelta(hours=random.randint(0, 24))
        payments.append((i, order_id, payment_method, payment_status, paid_amount, paid_at.strftime("%Y-%m-%d %H:%M:%S")))

    return payments


def generate_refunds(orders):
    refunds = []
    refund_id = 1
    for order in orders:
        if order[3] == "Refunded":
            order_date = datetime.strptime(order[2], "%Y-%m-%d")
            refund_date = order_date + timedelta(days=random.randint(1, 30))
            refunds.append((refund_id, order[0], order[4], random.choice(REFUND_REASONS), refund_date.strftime("%Y-%m-%d")))
            refund_id += 1
    return refunds


def seed_database(connection=None, verbose=True):
    """填充数据库；支持 DuckDB 和 PostgreSQL 双后端。"""
    random.seed(42)
    if verbose:
        print("开始生成模拟数据...")

    regions = generate_regions()
    categories = generate_categories()
    products = generate_products()
    customers = generate_customers()
    orders, order_items = generate_orders_and_items(products, customers)
    payments = generate_payments(orders)
    refunds = generate_refunds(orders)

    if verbose:
        print("生成数据统计:")
        print(f"  - 地区: {len(regions)} 条")
        print(f"  - 类别: {len(categories)} 条")
        print(f"  - 商品: {len(products)} 条")
        print(f"  - 客户: {len(customers)} 条")
        print(f"  - 订单: {len(orders)} 条")
        print(f"  - 订单明细: {len(order_items)} 条")
        print(f"  - 支付: {len(payments)} 条")
        print(f"  - 退款: {len(refunds)} 条")

    session = nullcontext(connection) if connection is not None else db_connection.get_session()
    with session as conn:
        is_pg = connection is not None and hasattr(conn, 'cursor') and not hasattr(conn, 'execute')
        if connection is None:
            is_pg = db_connection.backend == "postgresql"
        ph = "%s" if is_pg else "?"

        def execute_statement(sql):
            if is_pg:
                cur = conn.cursor()
                cur.execute(sql)
            else:
                conn.execute(sql)

        def execute_many(sql, rows):
            if is_pg:
                cur = conn.cursor()
                cur.executemany(sql, rows)
            else:
                conn.executemany(sql, rows)

        # DuckDB 的外键索引不支持在同一事务内先删子表再删父表，因此清空阶段保持依赖顺序提交。
        for table in TABLE_DELETE_ORDER:
            execute_statement(f"DELETE FROM {table}")

        # 真正耗时的是批量插入；用单事务提交，既加速空库自举，也避免失败时留下半批新数据。
        if not is_pg:
            execute_statement("BEGIN TRANSACTION")

        try:
            execute_many(f"INSERT INTO regions VALUES ({ph}, {ph}, {ph}, {ph})", regions)
            execute_many(f"INSERT INTO categories VALUES ({ph}, {ph})", categories)
            execute_many(
                f"INSERT INTO products VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                products,
            )
            execute_many(
                f"INSERT INTO customers VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                customers,
            )
            execute_many(f"INSERT INTO orders VALUES ({ph}, {ph}, {ph}, {ph}, {ph})", orders)
            execute_many(
                f"INSERT INTO order_items VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
                order_items,
            )
            execute_many(
                f"INSERT INTO payments VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                payments,
            )
            execute_many(
                f"INSERT INTO refunds VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
                refunds,
            )

            if is_pg:
                conn.commit()
            else:
                execute_statement("COMMIT")
        except Exception:
            if is_pg:
                conn.rollback()
            else:
                execute_statement("ROLLBACK")
            raise

    if verbose:
        print("数据插入完成！")

    verification_session = (
        nullcontext(connection) if connection is not None else db_connection.get_session()
    )
    with verification_session as conn:
        tables = ['regions', 'customers', 'categories', 'products', 'orders', 'order_items', 'payments', 'refunds']
        if verbose:
            print("\n数据验证:")
        for table in tables:
            if is_pg:
                cur = conn.cursor()
                cur.execute(f'SELECT COUNT(*) FROM {table}')
                count = cur.fetchone()[0]
            else:
                count = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            if verbose:
                print(f"  - {table}: {count} 条记录")

if __name__ == "__main__":
    seed_database()
