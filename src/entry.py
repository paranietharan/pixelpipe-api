from workers import WorkerEntrypoint
from router import router
from db import reconcile_images


class Default(WorkerEntrypoint):
    """PixelPipe Cloudflare Workers Python Entrypoint."""

    async def fetch(self, request):
        return await router.dispatch(request, self.env)


    async def scheduled(self, controller):
        await reconcile_images(self.env)
