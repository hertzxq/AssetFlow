import aiosqlite
from datetime import datetime

async def init_db():
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 0.0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT,
                section TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                category_id INTEGER,
                name TEXT,
                description TEXT,
                price REAL,
                photo TEXT,
                asset_url TEXT,
                is_free INTEGER DEFAULT 0
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
                payment_method TEXT,
                total_price REAL,
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
        # Migrate existing orders table if it contains unused columns
        try:
            async with db.execute('PRAGMA table_info(orders)') as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
            if 'delivery_method' in columns or 'name' in columns or 'phone' in columns or 'city' in columns:
                await db.execute('ALTER TABLE orders RENAME TO orders_old')
                await db.execute('''
                    CREATE TABLE orders (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER,
                        status TEXT,
                        payment_method TEXT,
                        total_price REAL,
                        created_at TEXT
                    )
                ''')
                await db.execute('''
                    INSERT INTO orders (id, user_id, status, payment_method, total_price, created_at)
                    SELECT id, user_id, status, payment_method, total_price, created_at
                    FROM orders_old
                ''')
                await db.execute('DROP TABLE orders_old')
        except aiosqlite.Error:
            pass  # Ignore if migration fails (e.g., table doesn't exist yet)
        await db.commit()

async def get_user_balance(user_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT balance FROM users WHERE user_id=?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            else:
                await db.execute('INSERT INTO users (user_id, balance) VALUES (?, 0.0)', (user_id,))
                await db.commit()
                return 0.0

async def update_user_balance(user_id, amount):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT balance FROM users WHERE user_id=?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                new_balance = row[0] + amount
                if new_balance < 0:
                    return False
                await db.execute('UPDATE users SET balance=? WHERE user_id=?', (new_balance, user_id))
            else:
                if amount < 0:
                    return False
                await db.execute('INSERT INTO users (user_id, balance) VALUES (?, ?)', (user_id, amount))
            await db.commit()
            return True

async def get_categories(section=None):
    async with aiosqlite.connect('bot.db') as db:
        if section:
            async with db.execute('SELECT id, name FROM categories WHERE section=?', (section,)) as cursor:
                return await cursor.fetchall()
        else:
            async with db.execute('SELECT id, name FROM categories') as cursor:
                return await cursor.fetchall()

async def add_category(name, section):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('INSERT INTO categories (name, section) VALUES (?, ?)', (name, section))
        await db.commit()

async def get_products_by_category(category_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute(
            'SELECT id, category_id, name, description, price, photo, asset_url FROM products WHERE category_id=?',
            (category_id,)
        ) as cursor:
            return await cursor.fetchall()

async def add_product(category_id, name, description, price, photo, asset_url, is_free):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute(
            '''INSERT INTO products (category_id, name, description, price, photo, asset_url, is_free)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (category_id, name, description, price, photo, asset_url, is_free)
        )
        await db.commit()

async def get_product(product_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute(
            'SELECT id, category_id, name, description, price, photo, asset_url, is_free FROM products WHERE id=?',
            (product_id,)
        ) as cursor:
            return await cursor.fetchone()

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

    balance = await get_user_balance(user_id)
    if balance < total_price:
        return None, "Недостаточно средств на балансе. 💸 Пожалуйста, пополните баланс."

    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE users SET balance=balance-? WHERE user_id=?', (total_price, user_id))

        async with db.execute('''
            INSERT INTO orders (user_id, status, payment_method, total_price, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            user_id, 'pending', data.get('payment_method', 'Unknown'), total_price, datetime.now().isoformat()
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
    return order_id, None

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