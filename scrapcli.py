import asyncio
from scrap import get_todays_data

TARGETS = [
    "/us/oh/kent",
    "/us/ga/athens"
]

async def grab_weather():
    output = []
    for target in TARGETS:
        print(f"Getting Weather Information for -> {target}")
        data = await get_todays_data(target)
        data['target'] = target
        output.append(data)
    print("")

    for entry in output:
        print("=== Weather Data ===")
        for k, v in entry.items():
            print(f"{k} => {v}")
        print("====================")

def main():
    asyncio.run(grab_weather())

if __name__ == "__main__":
    main()
