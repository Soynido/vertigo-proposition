"""The same explicit browser selection for doctor, collection and PDF export."""
import os


def launch_browser(playwright, **options):
    explicit = os.environ.get('PROPOSITION_BROWSER_CHANNEL')
    channels = [explicit] if explicit else ['chrome', 'chromium']
    for index, channel in enumerate(channels):
        try:
            browser = playwright.chromium.launch(headless=True, **options,
                **({'channel': channel} if channel != 'chromium' else {}))
            return browser, channel
        except Exception:
            if index == len(channels)-1:
                raise


async def alaunch_browser(playwright, **options):
    """Async counterpart with the identical explicit-channel/fallback policy."""
    explicit=os.environ.get('PROPOSITION_BROWSER_CHANNEL')
    channels=[explicit] if explicit else ['chrome','chromium']
    for index,channel in enumerate(channels):
        try:
            browser=await playwright.chromium.launch(headless=True,**options,**({} if channel=='chromium' else {'channel':channel}))
            return browser,channel
        except Exception:
            if index==len(channels)-1: raise
