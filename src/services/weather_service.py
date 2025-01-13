import aiohttp
import logging
from typing import Dict, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class WeatherService:
    def __init__(self):
        self.weather_base_url = "https://api.open-meteo.com/v1/forecast"
        self.geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
        
        self.lat = 52.2978
        self.lon = 104.2964
        
        self.weather_enabled_groups = [
           -1002321513211
        ]

    async def get_weather_and_traffic(self) -> str:
        """Получает информацию о погоде в Иркутске"""
        try:
            weather_info = await self._get_weather()
            recommendations = self._generate_recommendations(weather_info)
            
            weather_message = (
                f"🌤 Погода в Иркутске:\n"
                f"Температура: {weather_info['temp']}°C\n"
                f"Ощущается как: {weather_info['feels_like']}°C\n"
                f"Влажность: {weather_info['humidity']}%\n"
                f"Скорость ветра: {weather_info['wind_speed']} км/ч\n"
                f"Вероятность осадков: {weather_info['precipitation']}%\n\n"
                f"👔 Рекомендации:\n{recommendations}\n\n"
                f"🚗 Ситуация на дорогах:\n"
                f"В будние дни с 8:00 до 10:00 и с 17:00 до 19:00 возможны затруднения "
                f"на основных магистралях города (ул. Ленина, ул. Карла Маркса, "
                f"Академический мост)"
            )
            
            return weather_message
            
        except Exception as e:
            logger.error(f"Ошибка при получении данных о погоде: {e}")
            return "Извините, не удалось получить информацию о погоде 😔"

    async def _get_weather(self) -> Dict:
        """Получает данные о погоде через OpenMeteo API"""
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "current": ["temperature_2m", "relative_humidity_2m", "apparent_temperature", "wind_speed_10m", "precipitation_probability"],
            "timezone": "Asia/Irkutsk"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.weather_base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    current = data["current"]
                    return {
                        "temp": round(current["temperature_2m"]),
                        "feels_like": round(current["apparent_temperature"]),
                        "humidity": current["relative_humidity_2m"],
                        "wind_speed": round(current["wind_speed_10m"]),
                        "precipitation": current["precipitation_probability"]
                    }
                else:
                    raise Exception(f"Weather API returned status code {response.status}")

    def _generate_recommendations(self, weather_data: Dict) -> str:
        """Генерирует рекомендации на основе погодных данных"""
        recommendations = []
        temp = weather_data["temp"]
        wind_speed = weather_data["wind_speed"]
        precipitation = weather_data["precipitation"]
        
        if temp < -25:
            recommendations.append("Вообще не выходите!")
        elif temp < -15:
            recommendations.append("🧥 Оденьтесь очень тепло, на улице сильный мороз!")
        elif temp < 0:
            recommendations.append("🧥 Не забудьте теплую куртку и шапку")
        elif temp < 10:
            recommendations.append("🧥 Прохладно, возьмите куртку")
        elif temp < 20:
            recommendations.append("👕 Комфортная погода для легкой одежды")
        else:
            recommendations.append("👕 Жарко! Наденьте что-нибудь легкое")

        if wind_speed > 20:
            recommendations.append("💨 Очень сильный ветер, будьте осторожны!")
        elif wind_speed > 10:
            recommendations.append("🌬 Ветрено, возьмите ветровку")

        if precipitation > 70:
            recommendations.append("☔️ Высокая вероятность осадков, возьмите зонт!")
        elif precipitation > 30:
            recommendations.append("🌂 Возможны осадки, зонт не помешает")

        return "\n".join(recommendations)

    def is_weather_enabled(self, chat_id: int) -> bool:
        """Проверяет, включена ли функция погоды для данного чата"""
        return chat_id in self.weather_enabled_groups
