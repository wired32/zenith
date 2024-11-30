import openmeteo_requests
from openmeteo_sdk.Variable import Variable

import requests_cache
from retry_requests import retry

import json
import os, requests, pathlib
import logging
from typing import Optional
import subprocess

class Zenith:
    def __init__(self, configPath: Optional[str] = None, defInterval: int = 120, level: int = logging.INFO) -> None:
        self.URL = "https://api.open-meteo.com/v1/forecast"
        self.logger = logging.getLogger('zenith')
        self.defaultPath = 'default'
        
        if not os.path.exists(self.defaultPath):
            os.makedirs(self.defaultPath, exist_ok=True)

        self.logger.setLevel(level)

        log_file = configPath or os.path.expanduser("~/.config/zenith/")
        if not os.path.exists(log_file):
            os.makedirs(log_file, exist_ok=True)
        file_handler = logging.FileHandler(os.path.join(log_file, 'zenith.log'))
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        self.logger.addHandler(file_handler)
        self.logger.addHandler(stream_handler)

        if configPath is None:
            configPath = os.path.expanduser("~/.config/zenith/")
            self.logger.debug(f"Using default config path: {configPath}")

        self.configPath = configPath
        self._handleConfiguration(configPath, defInterval)
        self._fetchIP()

    def _handleConfiguration(self, configPath: str, defInterval: int) -> None:
        if os.path.exists(os.path.join(configPath, 'config.json')):
            with open(os.path.join(configPath, 'config.json'), 'r') as f:
                self.logger.debug("Configuration file found, loading data")
                self.config = json.load(f)
                self.logger.debug(f"Configuration data: {self.config}")
        else:
            self.logger.info("Couldn't find configuration file, setting default configurations.")
            self._setConfiguration(configPath, defInterval)

    def downloadDefaults(self) -> None:
        os.makedirs(os.path.join(self.defaultPath, 'images'), exist_ok=True)

        if 'backgrounds' not in self.config:
            self._setConfiguration(self.configPath, 120)

        for background in self.config['backgrounds'].values():
            if not os.path.exists(background[0]):
                self.logger.info(f"Downloading background: {background[0]}...")
                response = requests.get(background[1])

                with open(background[0], 'wb') as f:
                    f.write(response.content)
                    self.logger.info(f"Downloaded background: {background[0]} successfully.")

    def fetchCoordinates(self) -> list[float, float]:
        url = f"https://ipinfo.io/{self.ip}/json"
        response = requests.get(url)
        data = response.json()
        return [float(d) for d in data['loc'].split(',')]

    def _fetchIP(self) -> None:
        ip = requests.get('https://api.ipify.org')
        try:
            ip.raise_for_status()
            self.ip = ip.text
        except Exception as e:
            self.logger.error(f"Failed to fetch IP address: {e}")

    def _setConfiguration(self, configPath: str, defInterval: int) -> None:
        os.makedirs(self.defaultPath, exist_ok=True)
        self.config = {
            'interval': defInterval,
            'backgrounds': {
                'rain': (os.path.join(self.defaultPath, 'images', 'rain.jpg'), "https://github.com/wired32/zenith/raw/refs/heads/main/default/images/rain.jpg"),
                'clear': (os.path.join(self.defaultPath, 'images', 'clear.jpg'), "https://raw.githubusercontent.com/wired32/zenith/main/default/images/clear.jpg"),
                'cloudy': (os.path.join(self.defaultPath, 'images', 'cloudy.jpg'), "https://raw.githubusercontent.com/wired32/zenith/main/default/images/cloudy.jpg"),
                'snow': (os.path.join(self.defaultPath, 'images', 'snow.jpg'), "https://raw.githubusercontent.com/wired32/zenith/main/default/images/snow.jpg"),
            }
        }
        self.logger.debug("Set configuration variable.")
        with open(os.path.join(configPath, 'config.json'), 'w') as f:
            json.dump(self.config, f)
            self.logger.debug("Dumped configuration data.")

    def fetchData(self) -> tuple[float, float, float]:
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

        return (temperature.Value(), humidity.Value(), wmo.Value())
    
    def processWMO(self, wmo_code: int) -> str:
        weather_map = {
            0: "clear",        # Clear sky
            1: "cloudy",       # Partly cloudy
            2: "cloudy",       # Cloudy
            3: "cloudy",       # Overcast
            4: "rain",         # Light rain
            5: "rain",         # Moderate rain
            6: "rain",         # Heavy rain
            7: "rain",         # Very heavy rain
            8: "snow",         # Snow
            9: "snow",         # Heavy snow
            10: "snow",        # Blizzard
            11: "rain",        # Thunderstorm
            12: "rain"         # Thunderstorm with rain
        }

        return weather_map.get(wmo_code, "unknown")
    
    def changeBackground(self, weather: str) -> None:
        absolutePath = os.path.abspath(self.config['backgrounds'][weather][0])
        command = f'gsettings set org.gnome.desktop.background picture-uri "file://{absolutePath}"'
        self.logger.debug(f"Running command: {command}")
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.stdout: self.logger.debug(f"Subprocess output: {result.stdout}")
        if result.stderr: self.logger.error(f"Subprocess error: {result.stderr}")
        self.logger.info(f"Background set to {absolutePath}")
    
    def run(self) -> None:
        temperature, humidity, wmo = self.fetchData()

        self.downloadDefaults()

        weather: str = self.processWMO(wmo)

        if weather == "unknown":
            self.logger.warning(f"Unknown weather condition: {weather}")
        else:
            self.changeBackground('clear')

if __name__ == "__main__":
    zenith = Zenith(level=logging.DEBUG)
    zenith.run()
