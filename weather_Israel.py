from mcp.server.fastmcp import FastMCP
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright


mcp = FastMCP("weather-Israel")

FORECAST_URL = "https://www.weather2day.co.il/forecast"


browser = None
page = None
playwright = None

@mcp.tool()
async def open_weather_forecast_israel() -> str:
    """Open the Israel weather forecast website."""

    global browser, page, playwright

    if page is None:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        page = await browser.new_page()

    if not page.url.startswith(FORECAST_URL):
        await page.goto(FORECAST_URL, wait_until="domcontentloaded")

    await page.wait_for_selector("#city_search_forecast")

    return "Weather forecast website opened."



@mcp.tool()
async def enter_weather_forecast_city_israel(city: str) -> str:
    """Enter city name and wait for suggestions."""

    global page

    search = page.locator("#city_search_forecast")

    await search.fill("")
    await search.fill(city)

    suggestions = page.locator("#city_search_forecastautocomplete-list div")

    await suggestions.first.wait_for(
        state="visible",
        timeout=3000
    )


    return f"{city} entered successfully."

@mcp.tool()
async def select_weather_forecast_city_israel(city: str) -> str:
    """Select the requested city from the suggestions."""

    global page

    city_option = page.locator(
        "#city_search_forecastautocomplete-list"
    ).get_by_text(city, exact=False)

    await city_option.first.wait_for(
        state="visible",
        timeout=3000
    )

    await city_option.first.click()

    return f"{city} selected successfully."


@mcp.tool()
async def extract_weather_page() -> str:
    """
    Extract the current weather information from the weather page.
    This tool returns clean text that the LLM can use to answer the user.
    """

    global page

    if page is None:
        raise RuntimeError("Browser page is not initialized.")

    await page.wait_for_selector(".current-weather", timeout=10000)

    weather_text = await page.locator(".current-weather").inner_text()

    lines = []
    for line in weather_text.splitlines():
        line = line.strip()
        if line:
            lines.append(line)

    cleaned_text = "\n".join(lines)

    return f"""
Current weather information extracted from the website:

{cleaned_text}

Use ONLY this information when answering the user.
Do not add information that does not appear here.
"""
def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
