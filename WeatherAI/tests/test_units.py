import unittest

from weather_ai.utils.units import c_to_f, make_trend_df, format_quick_weather_text


class TestUnitsConversion(unittest.TestCase):
    def test_c_to_f(self):
        self.assertAlmostEqual(c_to_f(0.0), 32.0, places=3)
        self.assertAlmostEqual(c_to_f(100.0), 212.0, places=3)
        self.assertAlmostEqual(c_to_f(-40.0), -40.0, places=3)
        self.assertAlmostEqual(c_to_f(37.0), 98.6, places=1)

    def test_quick_weather_text_c(self):
        payload = {"city": "Phoenix", "date": "2025-10-01", "t_max_c": 30.0, "t_min_c": 20.0}
        out = format_quick_weather_text(payload, "°C")
        self.assertIn("High 30.0 °C", out)
        self.assertIn("Low 20.0 °C", out)

    def test_quick_weather_text_f(self):
        payload = {"city": "Phoenix", "date": "2025-10-01", "t_max_c": 30.0, "t_min_c": 20.0}
        out = format_quick_weather_text(payload, "°F")
        self.assertIn("High 86.0 °F", out)
        self.assertIn("Low 68.0 °F", out)

    def test_trend_df_c(self):
        items = [
            {"month": "2025-01", "t_max_c": 10.0, "t_min_c": 0.0},
            {"month": "2025-02", "t_max_c": 12.0, "t_min_c": 2.0},
        ]
        df = make_trend_df(items, "°C")
        self.assertListEqual(list(df.columns), ["Month", "High (°C)", "Low (°C)"])
        self.assertAlmostEqual(df.iloc[0]["High (°C)"], 10.0)
        self.assertAlmostEqual(df.iloc[0]["Low (°C)"], 0.0)

    def test_trend_df_f(self):
        items = [
            {"month": "2025-01", "t_max_c": 10.0, "t_min_c": 0.0},
            {"month": "2025-02", "t_max_c": 12.0, "t_min_c": 2.0},
        ]
        df = make_trend_df(items, "°F")
        self.assertListEqual(list(df.columns), ["Month", "High (°F)", "Low (°F)"])
        self.assertAlmostEqual(df.iloc[0]["High (°F)"], c_to_f(10.0))
        self.assertAlmostEqual(df.iloc[0]["Low (°F)"], c_to_f(0.0))


if __name__ == "__main__":
    unittest.main()
