# 模拟数据生成脚本
# 生成电商业务所需的测试数据

import random
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加backend目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.db.connection import db_connection

# 固定随机种子，保证数据可复现
random.seed(42)

def generate_regions():
    """生成地区数据"""
    regions = [
        (1, "East", "Zhejiang", "Hangzhou"),
        (2, "East", "Shanghai", "Shanghai"),
        (3, "South", "Guangdong", "Guangzhou"),
        (4, "South", "Guangdong", "Shenzhen"),
        (5, "North", "Beijing", "Beijing"),
        (6, "North", "Hebei", "Shijiazhuang"),
        (7, "West", "Sichuan", "Chengdu"),
        (8, "West", "Chongqing", "Chongqing"),
        (9, "Central", "Hubei", "Wuhan"),
        (10, "Central", "Hunan", "Changsha"),
    ]
    return regions

def generate_categories():
    """生成商品类别数据"""
    categories = [
        (1, "Electronics"),
        (2, "Clothing"),
        (3, "Food"),
        (4, "Home"),
        (5, "Books"),
        (6, "Sports"),
        (7, "Beauty"),
        (8, "Toys"),
    ]
    return categories

def generate_products():
    """生成商品数据"""
    products = []
    product_id = 1

    # Electronics
    electronics = [
        ("Laptop", 1, 4999.00, 3500.00),
        ("Smartphone", 1, 2999.00, 2100.00),
        ("Tablet", 1, 1999.00, 1400.00),
        ("Headphones", 1, 299.00, 150.00),
        ("Smartwatch", 1, 599.00, 350.00),
    ]

    # Clothing
    clothing = [
        ("T-Shirt", 2, 89.00, 35.00),
        ("Jeans", 2, 199.00, 80.00),
        ("Jacket", 2, 399.00, 180.00),
        ("Sneakers", 2, 499.00, 250.00),
        ("Dress", 2, 299.00, 120.00),
    ]

    # Food
    food = [
        ("Coffee Beans", 3, 68.00, 30.00),
        ("Chocolate", 3, 39.00, 15.00),
        ("Tea Set", 3, 128.00, 60.00),
        ("Snack Box", 3, 59.00, 25.00),
        ("Honey", 3, 88.00, 40.00),
    ]

    # Home
    home = [
        ("Pillow", 4, 99.00, 40.00),
        ("Blanket", 4, 199.00, 80.00),
        ("Lamp", 4, 149.00, 70.00),
        ("Vase", 4, 79.00, 35.00),
        ("Rug", 4, 299.00, 120.00),
    ]

    # Books
    books = [
        ("Python Book", 5, 59.00, 20.00),
        ("Data Science Book", 5, 69.00, 25.00),
        ("Novel", 5, 39.00, 12.00),
        ("Cookbook", 5, 49.00, 18.00),
        ("History Book", 5, 55.00, 20.00),
    ]

    # Sports
    sports = [
        ("Yoga Mat", 6, 89.00, 35.00),
        ("Dumbbells", 6, 149.00, 60.00),
        ("Running Shoes", 6, 399.00, 180.00),
        ("Water Bottle", 6, 39.00, 12.00),
        ("Sports Bag", 6, 129.00, 50.00),
    ]

    # Beauty
    beauty = [
        ("Face Cream", 7, 199.00, 80.00),
        ("Lipstick", 7, 129.00, 45.00),
        ("Perfume", 7, 399.00, 150.00),
        ("Shampoo", 7, 69.00, 25.00),
        ("Sunscreen", 7, 89.00, 35.00),
    ]

    # Toys
    toys = [
        ("LEGO Set", 8, 299.00, 120.00),
        ("Board Game", 8, 99.00, 40.00),
        ("Puzzle", 8, 59.00, 20.00),
        ("Stuffed Animal", 8, 79.00, 30.00),
        ("Remote Car", 8, 149.00, 60.00),
    ]

    all_products = electronics + clothing + food + home + books + sports + beauty + toys

    for name, category_id, price, cost in all_products:
        created_at = datetime(2022, 1, 1) + timedelta(days=random.randint(0, 365))
        products.append((product_id, name, category_id, price, cost, created_at.strftime("%Y-%m-%d")))
        product_id += 1

    return products

def generate_customers():
    """生成客户数据"""
    customers = []
    customer_id = 1

    surnames = ["Zhang", "Li", "Wang", "Liu", "Chen", "Yang", "Huang", "Zhao", "Wu", "Zhou"]
    genders = ["Male", "Female"]

    for i in range(100):
        name = f"{random.choice(surnames)}_{customer_id}"
        gender = random.choice(genders)
        age = random.randint(18, 65)
        region_id = random.randint(1, 10)
        register_date = datetime(2022, 1, 1) + timedelta(days=random.randint(0, 730))

        customers.append((customer_id, name, gender, age, region_id, register_date.strftime("%Y-%m-%d")))
        customer_id += 1

    return customers

def generate_orders_and_items(products, customers):
    """生成订单和订单明细数据"""
    orders = []
    order_items = []
    order_id = 1
    item_id = 1

    statuses = ["Completed", "Completed", "Completed", "Completed", "Cancelled", "Refunded"]

    for customer_id, customer in enumerate(customers, 1):
        # 每个客户有1-5个订单
        num_orders = random.randint(1, 5)

        for _ in range(num_orders):
            order_date = datetime(2022, 1, 1) + timedelta(days=random.randint(0, 1095))
            status = random.choice(statuses)

            # 每个订单有1-4个商品
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
    """生成支付数据"""
    payments = []
    payment_id = 1

    payment_methods = ["Alipay", "WeChat Pay", "Credit Card", "Debit Card"]
    payment_statuses = ["Paid", "Paid", "Paid", "Paid", "Failed", "Pending"]

    for order in orders:
        order_id = order[0]
        order_date = datetime.strptime(order[2], "%Y-%m-%d")
        status = order[3]
        total_amount = order[4]

        payment_method = random.choice(payment_methods)

        if status == "Cancelled":
            payment_status = "Failed"
        elif status == "Refunded":
            payment_status = "Paid"
        else:
            payment_status = random.choice(payment_statuses)

        paid_amount = total_amount if payment_status == "Paid" else 0
        paid_at = order_date + timedelta(hours=random.randint(0, 24))

        payments.append((payment_id, order_id, payment_method, payment_status, paid_amount, paid_at.strftime("%Y-%m-%d %H:%M:%S")))
        payment_id += 1

    return payments

def generate_refunds(orders):
    """生成退款数据"""
    refunds = []
    refund_id = 1

    refund_reasons = [
        "Quality Issue",
        "Not as Described",
        "Wrong Item",
        "Changed Mind",
        "Late Delivery",
        "Damaged in Transit"
    ]

    for order in orders:
        order_id = order[0]
        status = order[3]
        total_amount = order[4]

        # 只有Refunded状态的订单才有退款记录
        if status == "Refunded":
            refund_amount = total_amount
            refund_reason = random.choice(refund_reasons)
            order_date = datetime.strptime(order[2], "%Y-%m-%d")
            refund_date = order_date + timedelta(days=random.randint(1, 30))

            refunds.append((refund_id, order_id, refund_amount, refund_reason, refund_date.strftime("%Y-%m-%d")))
            refund_id += 1

    return refunds

def seed_database():
    """填充数据库"""
    print("开始生成模拟数据...")

    # 生成数据
    regions = generate_regions()
    categories = generate_categories()
    products = generate_products()
    customers = generate_customers()
    orders, order_items = generate_orders_and_items(products, customers)
    payments = generate_payments(orders)
    refunds = generate_refunds(orders)

    print(f"生成数据统计:")
    print(f"  - 地区: {len(regions)} 条")
    print(f"  - 类别: {len(categories)} 条")
    print(f"  - 商品: {len(products)} 条")
    print(f"  - 客户: {len(customers)} 条")
    print(f"  - 订单: {len(orders)} 条")
    print(f"  - 订单明细: {len(order_items)} 条")
    print(f"  - 支付: {len(payments)} 条")
    print(f"  - 退款: {len(refunds)} 条")

    # 插入数据
    with db_connection.get_session() as conn:
        # 插入地区数据
        for region in regions:
            conn.execute("INSERT INTO regions VALUES (?, ?, ?, ?)", region)

        # 插入类别数据
        for category in categories:
            conn.execute("INSERT INTO categories VALUES (?, ?)", category)

        # 插入商品数据
        for product in products:
            conn.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)", product)

        # 插入客户数据
        for customer in customers:
            conn.execute("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)", customer)

        # 插入订单数据
        for order in orders:
            conn.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", order)

        # 插入订单明细数据
        for item in order_items:
            conn.execute("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", item)

        # 插入支付数据
        for payment in payments:
            conn.execute("INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?)", payment)

        # 插入退款数据
        for refund in refunds:
            conn.execute("INSERT INTO refunds VALUES (?, ?, ?, ?, ?)", refund)

    print("数据插入完成！")

    # 验证数据
    with db_connection.get_session() as conn:
        tables = ['regions', 'customers', 'categories', 'products', 'orders', 'order_items', 'payments', 'refunds']
        print("\n数据验证:")
        for table in tables:
            result = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()
            print(f"  - {table}: {result[0]} 条记录")

if __name__ == "__main__":
    seed_database()