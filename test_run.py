import asyncio
from app.db.engine import async_session_factory
from app.services.chat_service import ChatService

async def test():
    async with async_session_factory() as db:
        svc = ChatService(db)
        session = await svc.create_session(
            agent_id='da19d4ed-126e-404f-a202-855e042d8174',
            title='test',
            session_type='NORMAL'
        )
        await db.commit()
        print(f'Session: {session.id}')
        msg = await svc.create_message(
            session_id=str(session.id),
            role='user',
            content='你好'
        )
        await db.commit()
        print(f'Message: {msg.id}')

asyncio.run(test())
