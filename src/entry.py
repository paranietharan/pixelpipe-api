from workers import WorkerEntrypoint
from router import router


class Default(WorkerEntrypoint):
    """PixelPipe Cloudflare Workers Python Entrypoint."""

    async def fetch(self, request):
        return await router.dispatch(request, self.env)
