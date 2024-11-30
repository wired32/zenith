import openmeteo_requests
from openmeteo_sdk.Variable import Variable

import requests_cache
from retry_requests import retry

import json
import os, requests
import logging

class Zenith:
    def __init__(self, configPath: str = None, defInterval: int = 120, level = logging.INFO):
        self.URL = "https://api.open-meteo.com/v1/forecast"
        self.logger = logging.getLogger('zenith')

        self.logger.setLevel(level)

        file_handler = logging.FileHandler(os.path.join(configPath or os.path.expanduser("~/.config/zenith/"), 'zenith.log'))
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        self.logger.addHandler(file_handler)
        self.logger.addHandler(stream_handler)

        if configPath is None:
            configPath = os.path.expanduser("~/.config/zenith/")
            self.logger.debug(f"Using default config path: {configPath}")

        self._handleConfiguration(configPath, defInterval)
        self._fetchIP()

    def _handleConfiguration(self, configPath: str, defInterval: int):
        if os.path.exists(os.path.join(configPath, 'config.json')):
            with open(os.path.join(configPath, 'config.json'), 'r') as f:
                self.logger.debug("Configuration file found, loading data")
                self.config = json.load(f)
                self.logger.debug(f"Configuration data: {self.config}")
        else:
            self.logger.info("Couldn't find configuration file, setting default configurations.")
            os.makedirs(configPath, exist_ok=True)
            self.config = {'interval': defInterval}
            self.logger.debug("Set configuration variable.")
            with open(os.path.join(configPath, 'config.json'), 'w') as f:
                json.dump(self.config, f)
                self.logger.debug("Dumped configuration data.")

    def fetchCoordinates(self):
        url = f"https://ipinfo.io/{self.ip}/json"
        response = requests.get(url)
        data = response.json()
        return [float(d) for d in data['loc'].split(',')]

    def _fetchIP(self):
        ip = requests.get('https://api.ipify.org')
        try:
            ip.raise_for_status()
            self.ip = ip.text
        except Exception as e:
            self.logger.error(f"Failed to fetch IP address: {e}")

    def fetchData(self):
        self.logger.debug("Initializing Open Meteo SDK...")
        cache_session = requests_cache.CachedSession('.cache', expire_after=3600)   # Setting cache
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)         # Setting retries
        openmeteo = openmeteo_requests.Client(session=retry_session)                # Initializing Open Meteo SDK
        self.logger.debug("Open Meteo SDK initialized.")

        self.logger.info("Fetching weather data...")

        coordinates = self.fetchCoordinates()

        params = {
            "latitude": coordinates[0],
            "longitude": coordinates[1],
            "hourly": ["temperature_2m", "precipitation", "wind_speed_10m"],
            "current": ["temperature_2m", "relative_humidity_2m", "weather_code"]
        }
        responses = openmeteo.weather_api(self.URL, params=params)
        self.logger.info("Weather data fetched.")

        response = responses[0]
        current = response.Current()
        current_variables = list(map(lambda i: current.Variables(i), range(0, current.VariablesLength())))
        temperature = next(filter(lambda x: x.Variable() == Variable.temperature and x.Altitude() == 2, current_variables))
        humidity = next(filter(lambda x: x.Variable() == Variable.relative_humidity and x.Altitude() == 2, current_variables))
        wmo = next(filter(lambda x: x.Variable() == Variable.weather_code, current_variables))

        self.logger.info(f"Current time {current.Time()}")
        self.logger.info(f"Current temperature {temperature.Value()}")
        self.logger.info(f"Current humidity {humidity.Value()}")
        self.logger.info(f"Current weather code: {wmo.Value()}")

if __name__ == "__main__":
    zenith = Zenith()
    zenith.fetchData()
