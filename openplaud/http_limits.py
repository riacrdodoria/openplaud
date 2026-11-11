"""Bound JSON/calendar requests before FastAPI's body parsing, including chunked bodies."""
class JSONBodyLimit:
    def __init__(self,app,limit=2*1024**2):self.app=app;self.limit=limit
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method'] not in ('POST','PUT','PATCH') or scope['path']=='/api/recordings':
            return await self.app(scope,receive,send)
        messages=[];size=0
        while True:
            message=await receive()
            if message['type']=='http.disconnect':return
            size+=len(message.get('body',b''))
            if size>self.limit:
                body=b'{"detail":"Body too large"}'
                await send({'type':'http.response.start','status':413,'headers':[(b'content-type',b'application/json'),(b'cache-control',b'no-store')]})
                await send({'type':'http.response.body','body':body});return
            messages.append(message)
            if not message.get('more_body',False):break
        index=0
        async def replay():
            nonlocal index
            if index<len(messages):
                message=messages[index];index+=1;return message
            return await receive()
        await self.app(scope,replay,send)
