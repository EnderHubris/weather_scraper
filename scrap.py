from bs4 import BeautifulSoup
from datetime import date, time
from time import sleep
import requests, asyncio

try:
    # you can attach this to a discord bot to send pings if desired!
    import discord
except ImportError:
    discord = None

# Uses playwright to request a page that
# uses JS to populate table data
from playwright.async_api import async_playwright

def get_current_temp(soup):
    span = soup.find("span", class_="wu-value wu-value-to")
    temp = span.decode_contents()
    print(f"Current Temperature -> {temp}")
    return temp

def get_sky_condition(soup):
    div = soup.find("div", class_="condition-icon small-6 medium-12 columns")
    p = div.find("p")

    sky_condition = "Unknown"

    if p:
        sky_condition = p.text

    print(f"Sky Condition -> {sky_condition}")
    return sky_condition

def get_wind(soup):
    direction = "Unknown"
    speed = "Unknown"

    wind_div = soup.find("div", class_="wind-compass-wrap")

    if "NE" in wind_div.decode_contents():
        direction = "North East"
    elif "NW" in wind_div.decode_contents():
        direction = "North West"
    elif "SE" in wind_div.decode_contents():
        direction = "South East"
    elif "SW" in wind_div.decode_contents():
        direction = "South West"
    elif "N" in wind_div.decode_contents():
        direction = "North"
    elif "S" in wind_div.decode_contents():
        direction = "South"
    elif "W" in wind_div.decode_contents():
        direction = "West"
    elif "E" in wind_div.decode_contents():
        direction = "East"

    wind_speed_div = wind_div.find("strong")
    if wind_speed_div:
        speed = wind_speed_div.decode_contents()

    wind_data = f"{speed} mph {direction}"
    print(f"Wind Speed & Direction -> {wind_data}")
    return wind_data

def get_precipitation(soup):
    precip = "Unknown"

    precip_tile = soup.find("lib-precip-tile")

    if precip_tile:
        precip_anchor = precip_tile.find("a")
        if precip_anchor:
            print("[*] Spidering to precip url. . .")
            precip_url = "https://www.wunderground.com" + precip_anchor["href"]
            r = requests.get(precip_url)
            if r.status_code == 200:
                precip_soup = BeautifulSoup(r.text, "html.parser")
                precip_table = precip_soup.find("div", class_="table-view")
                precip_span = precip_table.find("span", class_="wu-value wu-value-to")
                if precip_span:
                    precip = precip_span.decode_contents()

    print(f"Precipitation -> {precip}")
    return precip

def get_additionals(soup):
    additionals = soup.find("div", class_="data-module additional-conditions")
    data_spans = additionals.find_all("span", class_="wu-value wu-value-to")

    pressure = data_spans[0].decode_contents()
    humidity = data_spans[3].decode_contents()

    print(f"Humidity -> {humidity}")
    print(f"Pressure -> {pressure}")

    return humidity, pressure

def fetch_base_data(html, data):
    base_soup = BeautifulSoup(html, "html.parser")
    div = base_soup.find("div", class_="region-content-main")
    data_soup = BeautifulSoup(div.decode_contents(), "html.parser")

    if div:
        # nicely formatted HTML
        # print(div.prettify())

        data["current_temp"] = get_current_temp(data_soup)
        data["precipitation"] = get_precipitation(data_soup)
        data["humidity"], data["pressure"] = get_additionals(data_soup)
        data["wind"] = get_wind(data_soup)
        data["sky"] = get_sky_condition(data_soup)
    else:
        print("Contents not found!")

def find_almanac_url(html):
    base_soup = BeautifulSoup(html, "html.parser")
    almanac_div = base_soup.find("div", class_="station-name")
    almanac_url = "Unknown"

    if almanac_div:
        almanac_a = almanac_div.find("a")
        if almanac_a:
            almanac_url = almanac_a["href"]

    return "https://www.wunderground.com" + almanac_url

def extract_from_row(row):
    if not row:
        return "Unknown"

    inner_rows = row.find_all("td")

    if not inner_rows:
        return "Unknown"

    if len(inner_rows) < 1:
        return "Unknown"

    content = inner_rows[0].decode_contents()

    if len(content) > 0:
        return content
    else:
        return "Unknown"

def is_int(value):
    try:
        int(value)
        return True
    except (ValueError, TypeError):
        return False

async def extract_temps_from_page(page, url: str):
    min_temp = max_temp = "Unknown"

    try:
        await page.goto(url, timeout=120000)
        await page.wait_for_load_state("networkidle")

        body_text = await page.inner_text("body")
        if "No data recorded" in body_text:
            return min_temp, max_temp

        await page.wait_for_selector("text=High Temp", timeout=30000)

        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        data_table = soup.find("div", class_="summary-table")
        if data_table:
            table = data_table.find("table")
            if table:
                rows = table.find_all("tr")
                if rows and len(rows) > 2:
                    min_temp = extract_from_row(rows[2])
                    max_temp = extract_from_row(rows[1])

        return min_temp, max_temp
    except asyncio.CancelledError:
        raise
    except Exception:
        return min_temp, max_temp


async def get_temp_range(url: str, channel=None):
    print("[*] Attempting to fetch min/max temperatures...")

    # discord is not needed to run these methods
    if discord is None:
        channel = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # create n number of tabs in attempt to find the data we need
        MAX_TABS = 10
        pages = [await browser.new_page() for _ in range(MAX_TABS)]

        tasks = [
            asyncio.create_task(extract_temps_from_page(page, url))
            for page in pages
        ]

        try:
            for task in asyncio.as_completed(tasks):
                min_temp, max_temp = await task

                if is_int(min_temp) and is_int(max_temp):
                    print("[+] Captured Temperatures")
                    print(f" |--- min_temp ({min_temp}) | max_temp ({max_temp})")

                    # Cancel remaining tasks
                    for t in tasks:
                        if not t.done():
                            t.cancel()

                    return min_temp, max_temp

            print(f"[-] Could not find temperatures at: {url}")
            if channel:
                await channel.send("Could not locate min/max temperatures. . .")
            return "Unknown", "Unknown"
        except Exception as e:
            if channel:
                await channel.send("Something went horribly wrong!")
        finally:
            # Ensure pages are closed
            for page in pages:
                await page.close()

            await browser.close()

# main exported function that is used
async def get_todays_data(location:str, channel=None):
    # discord is not needed to run these methods
    if discord is None:
        channel = None

    data = {
        "current_temp":"",
        "precipitation":"",
        "humidity":"",
        "pressure":"",
        "wind":"",
        "min_temp":"",
        "max_temp":"",
        "sky":""
    }

    try:
        weather_url = f"https://www.wunderground.com/weather/{location}"

        r = requests.get(weather_url)

        if r.status_code == 200:
            # fetch data from website
            fetch_base_data(r.text, data)
        else:
            err = "[-] Could not connect to weather-site!"
            if channel:
                await channel.send(f"Error connecting to --> {weather_url}")
            print(err)
            return data

        # some feedback
        if channel:
            await channel.send("Searching for Almanac URL. . .")

        print(f"[*] Spidering to almanac url")
        almanac_url = find_almanac_url(r.text)
        
        if channel:
            await channel.send(f"Found Almanac URL -> {almanac_url}")

        if "http" in almanac_url:
            # ensure we always get the temperature
            attempts = 0
            while attempts < 10:
                data["min_temp"], data["max_temp"] = await get_temp_range(almanac_url, channel)
                if is_int(data["min_temp"]) and is_int(data["max_temp"]):
                    break
                attempts += 1
        else:
            print("[-] Could not find Almanac url")

        # some times the current temperature is higher than the max temperature found in the almanac
        if int(data['max_temp']) < int(data['current_temp']):
            data['max_temp'] = data['current_temp']

        print(f"Low  Temp -> {data['min_temp']}")
        print(f"High Temp -> {data['max_temp']}")
        
        print("I finished capturing today's weather data!")
    except Exception as e:
        # something went horribly wrong
        if channel:
            await channel.send(f"(EXCEPTION)[get todays data] --> ```\n{e}\n```")
        print(f"(EXCEPTION): {e}")

    return data
