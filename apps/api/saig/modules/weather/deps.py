from saig.modules.weather.provider import OpenMeteoProvider, WeatherProvider

# Default provider. Tests override this via app.dependency_overrides so the
# suite never touches the network (testing-strategy.md).
_default_provider: WeatherProvider = OpenMeteoProvider()


def get_weather_provider() -> WeatherProvider:
    return _default_provider
