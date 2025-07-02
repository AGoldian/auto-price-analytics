import json
import logging
import requests
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("llm_price")

API_URL = "http://localhost:1234/v1/chat/completions"


def estimate_price(
    raw_lines: str,
    make: str,
    model: str,
    *,
    model_name: str = "mediocredev/open-llama-3b-v2-instruct",
    temperature: float = 0.0,
    max_tokens: int = 32,
    max_chars: int = 1000
) -> str:
    """
    Возвращает цену строкой. Никаких JSON/пояснений.
    """
    truncated = raw_lines[:max_chars]

    sys_prompt = f"""
    Ты — автономная модель-оценщик автомобилей, эксперт по вторичному рынку Владивостока
    (июль 2025 года).  

    Тебе передают:
    • MAKE_MODEL  — марку и модель, извлечённые из URL;  
    • CHARACTERISTICS — единственный блок характеристик нужного автомобиля
        (год выпуска, пробег, объём двигателя, тип топлива, КПП, цвет и т. д.).

    Жёсткие требования вывода  
    1. **Верни строго одну строку**: цену автомобиля в рублях,  
    формат «1 234 567 ₽» (цифры, пробелы-разделители тысяч, символ ₽).  
    2. Никаких слов, кавычек, JSON, переносов строк, пояснений или знаков «Ответ:».  
    3. Игнорируй всё, что не относится к указанному автомобилю
    (другие лоты, запчасти, реклама и т. п.).  

    ### Примеры — следуй формату строго

    Пример 1  
    MAKE_MODEL: toyota crown  
    CHARACTERISTICS:  
    Год: 2015  
    Пробег: 6 000 км  

    <Вывод>  
    2 764 060 ₽

    Пример 2  
    MAKE_MODEL: lada 2109  
    CHARACTERISTICS:  
    Год: 1992  
    Пробег: 81 000 км  

    <Вывод>  
    140 000 ₽

    Пример 3  
    MAKE_MODEL: mercedes s-klasse  
    CHARACTERISTICS:  
    Год: 2018  
    Пробег: 45 000 км  
    Объём: 3000 cc  

    <Вывод>  
    5 200 000 ₽
""".strip()

    user_prompt = f"MAKE_MODEL: {make} {model}\nCHARACTERISTICS:\n{truncated}"

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": user_prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    logger.info("►►► Payload to LLM:")
    for line in json.dumps(payload, ensure_ascii=False, indent=2).splitlines():
        logger.info("    %s", line)

    resp = requests.post(API_URL, json=payload, timeout=45)
    resp.raise_for_status()

    answer = resp.json()["choices"][0]["message"]["content"].strip()
    logger.info("LLM raw answer: %r", answer)
    return answer
