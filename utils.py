import asyncio


# This function runs an async function within a sync function, while checking the event loop status.
def run_async(async_func, *args, **kwargs):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if not loop.is_running():
        return loop.run_until_complete(async_func(*args, **kwargs))
    else:
        future = asyncio.ensure_future(async_func(*args, **kwargs))
        loop.run_until_complete(future)
        return future.result()
    

    #by t.me/yehuda100