from datetime import datetime, timedelta
def string_to_timedelta(input_string):
    def get_data(final_settings, number, unit):
        units = {
            # "Y": "years",
            # "M": "months",
            "W": "weeks",
            "D": "days",
            "h": "hours",
            "m": "minutes",
            "s": "seconds",
            "ms": "milliseconds"
        }
        if unit in units:
            final_settings[units[unit]] = number

    if len(input_string) < 2:
        # doesn't have enough length to have a number and unit
        return None
    final_settings = {}
    number = 0
    unit = ""
    finishing = False
    for char in input_string:
        try:
            digit = int(char)
            if finishing:
                get_data(final_settings, number, unit)
                number = digit
                unit = ""
                finishing = False
            else:
                number *= 10
                number += digit
        except Exception as e:
            unit += char
            finishing = True
    if finishing:
        get_data(final_settings, number, unit)
    return timedelta(**final_settings)
