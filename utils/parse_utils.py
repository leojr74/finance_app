
import re

def parse_money(value_str):
    if not value_str:
        return None

    value_str = value_str.strip()

    negative = False

    if value_str.endswith("-"):
        negative = True
        value_str = value_str[:-1]

    value_str = value_str.replace("R$", "")
    value_str = value_str.replace("−", "-")

    value_str = value_str.replace(".", "")
    value_str = value_str.replace(",", ".")

    try:
        value = float(value_str)
    except:
        return None

    if negative:
        value = -value

    return value


def parse_date(date_str):
    if not date_str:
        return None

    parts = date_str.split("/")

    if len(parts) == 3:
        dia = parts[0]
        mes = parts[1]
    elif len(parts) == 2:
        dia, mes = parts
    else:
        return None

    return f"{int(dia):02d}/{int(mes):02d}"
