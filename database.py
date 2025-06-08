import aiosqlite
from datetime import datetime

async def init_db():
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT,
                gender TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                category_id INTEGER,
                name TEXT,
                description TEXT,
                price REAL,
                photo TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS cart_items (
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                PRIMARY KEY (user_id, product_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                status TEXT,
                delivery_method TEXT,
                payment_method TEXT,
                total_price REAL,
                name TEXT,
                phone TEXT,
                city TEXT,
                created_at TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                order_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                price_at_purchase REAL
            )
        ''')
        await db.commit()

async def get_categories(gender=None):
    async with aiosqlite.connect('bot.db') as db:
        if gender:
            query = 'SELECT id, name FROM categories WHERE gender=?'
            args = (gender,)
        else:
            query = 'SELECT id, name FROM categories'
            args = ()
        async with db.execute(query, args) as cursor:
            return await cursor.fetchall()

async def add_category(name, gender):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('INSERT INTO categories (name, gender) VALUES (?, ?)', (name, gender))
        await db.commit()

async def get_products_by_category(category_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute(
            'SELECT id, category_id, name, description, price, photo FROM products WHERE category_id=?',
            (category_id,)
        ) as cursor:
            return await cursor.fetchall()

async def get_product(product_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute(
            'SELECT id, category_id, name, description, price, photo FROM products WHERE id=?',
            (product_id,)
        ) as cursor:
            return await cursor.fetchone()

async def add_product(category_id, name, description, price, photo):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute(
            'INSERT INTO products (category_id, name, description, price, photo) VALUES (?, ?, ?, ?, ?)',
            (category_id, name, description, price, photo)
        )
        await db.commit()

async def delete_category(category_id):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('DELETE FROM products WHERE category_id=?', (category_id,))
        await db.execute('DELETE FROM categories WHERE id=?', (category_id,))
        await db.commit()

async def delete_product(product_id):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('DELETE FROM products WHERE id=?', (product_id,))
        await db.commit()

async def add_to_cart(user_id, product_id, quantity=1):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT quantity FROM cart_items WHERE user_id=? AND product_id=?',
                              (user_id, product_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                await db.execute(
                    'UPDATE cart_items SET quantity=? WHERE user_id=? AND product_id=?',
                    (row[0] + quantity, user_id, product_id)
                )
            else:
                await db.execute(
                    'INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)',
                    (user_id, product_id, quantity)
                )
        await db.commit()

async def get_cart_items(user_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT product_id, quantity FROM cart_items WHERE user_id=?', (user_id,)) as cursor:
            return [{'product_id': row[0], 'quantity': row[1]} for row in await cursor.fetchall()]

async def clear_cart(user_id):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('DELETE FROM cart_items WHERE user_id=?', (user_id,))
        await db.commit()

async def create_order(user_id, data):
    cart_items = await get_cart_items(user_id)
    total_price = 0
    for item in cart_items:
        product = await get_product(item['product_id'])
        total_price += product[4] * item['quantity']

    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('''
            INSERT INTO orders (user_id, status, delivery_method, payment_method, total_price, name, phone, city, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, 'pending', data['delivery_method'], data['payment_method'],
            total_price, data['name'], data['phone'], data['city'], datetime.now().isoformat()
        )) as cursor:
            order_id = cursor.lastrowid

        for item in cart_items:
            product = await get_product(item['product_id'])
            await db.execute('''
                INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase)
                VALUES (?, ?, ?, ?)
            ''', (order_id, item['product_id'], item['quantity'], product[4]))

        await db.commit()

    await clear_cart(user_id)
    return order_id

async def get_pending_orders():
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute(
            'SELECT id, user_id, status, delivery_method, payment_method, total_price, name, phone, city FROM orders WHERE status="pending"'
        ) as cursor:
            return [
                {
                    'id': row[0], 'user_id': row[1], 'status': row[2],
                    'delivery_method': row[3], 'payment_method': row[4],
                    'total_price': row[5], 'name': row[6], 'phone': row[7], 'city': row[8]
                } for row in await cursor.fetchall()
            ]

async def get_order_items(order_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute(
            'SELECT product_id, quantity, price_at_purchase FROM order_items WHERE order_id=?',
            (order_id,)
        ) as cursor:
            return [
                {'product_id': row[0], 'quantity': row[1], 'price_at_purchase': row[2]}
                for row in await cursor.fetchall()
            ]
