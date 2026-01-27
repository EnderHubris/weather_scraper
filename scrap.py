from requests_html import HTMLSession
from bs4 import BeautifulSoup
from datetime import date, time
import requests

TARGETS = [
    "/us/oh/kent",
    "/us/ga/athens"
]

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

    return inner_rows[0].decode_contents()

def get_temp_range(url):
    min_temp = max_temp = "Unknown"

    session = HTMLSession()

    attempts = 0

    while attempts < 50 and min_temp == "Unknown" and max_temp == "Unknown":
        attempts += 1

        print("[*] Rendering Tables. . .")
        r = session.get(url)
        r.html.render(timeout=20)

        almanac_soup = BeautifulSoup(r.html.html, "html.parser")
        data_table = almanac_soup.find("div", class_="summary-table")

        if data_table:
            table = data_table.find("table")

            if not table:
                continue

            rows = table.find_all("tr")
            if rows and len(rows) > 2:
                attempts = 0
                min_temp = extract_from_row(rows[2])
                max_temp = extract_from_row(rows[1])
    
    print("[+] Captured Temperatures")
    return min_temp, max_temp

def get_todays_data(location:str):
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

    weather_url = f"https://www.wunderground.com/weather/{location}"

    r = requests.get(weather_url);

    if r.status_code == 200:
        # fetch data from website
        fetch_base_data(r.text, data)
    else:
        err = "[-] Could not connect to weather-site!"
        print(err)
        return

    print(f"[*] Spidering to almanac url")
    almanac_url = find_almanac_url(r.text)

    if "http" in almanac_url:
        data["min_temp"], data["max_temp"] = get_temp_range(almanac_url)
    else:
        print("[-] Could not find Almanac url")

    print(f"Low  Temp -> {data['min_temp']}")
    print(f"High Temp -> {data['max_temp']}")

    return data

def main():
    for target in TARGETS:
        print(f"Getting Weather Information for -> {target}")
        data = get_todays_data(target)
        print("")

if __name__ == "__main__":
    main()
