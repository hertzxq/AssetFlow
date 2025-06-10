import aiosqlite


async def init_db():
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT,
                section TEXT  -- Убедитесь, что этот столбец есть
            )
        ''')
        await db.commit()