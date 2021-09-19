import asyncio
import os
import importlib
import requests
import time
from arq import cron, Worker
from arq.connections import RedisSettings

from currencies_store.AllowedCurrencies import AllowedCurrencies
from custom_currencies.abstract.CustomCurrencyAbstract import CustomCurrencyAbstract
from utils.redis.RedisUtils import RedisUtils


def update_redis_currencies(actual_currency: dict) -> None:
    RedisUtils.salva_objeto("currency:base", os.getenv("base_currency", "USD"))
    RedisUtils.salva_objeto("currency:timestamp", f"{time.time()}")

    rates_supported_currencies = dict(
        (k, actual_currency[k]) for k in AllowedCurrencies.get_allowed_currencies() if
        k in actual_currency)

    for k, v in rates_supported_currencies.items():
        for k2, v2 in rates_supported_currencies.items():
            RedisUtils.salva_objeto(f"currency:{k}:{k2}", v / v2)


def update_eth_currency(actual_currency) -> dict:
    eth = requests.get("https://min-api.cryptocompare.com/data/price?fsym=ETH&tsyms=USD").json()['USD']
    dict_eth = {"ETH": float(eth)}
    return dict_eth


def update_default_currencies() -> dict:
    currencies = requests.get(
        f"https://openexchangerates.org/api/latest.json?app_id={os.getenv('currencies_api_id')}").json()
    return currencies['rates']


def update_custom_currencies() -> dict:
    dict_custom_currencies = {}
    if RedisUtils.verifica_existencia_chave("currency:custom_currencies"):
        list_custom_currencies = RedisUtils.recupera_objeto("currency:custom_currencies")
        for custom_currency in list_custom_currencies:
            try:
                module = importlib.import_module(f"custom_currencies.currencies.{custom_currency}")
                custom_currency_clazz = getattr(module, f"{custom_currency}")
                if issubclass(custom_currency_clazz, CustomCurrencyAbstract):
                    dict_rate = custom_currency_clazz().obtem_rate_default()
                    dict_custom_currencies.update(dict_rate)
            except:
                pass
    return dict_custom_currencies


def salva_moedas_default(actual_currency):
    default_keys = list(actual_currency.keys())
    RedisUtils.salva_objeto("currency:default_currencies", default_keys)


async def update_currencies(ctx):
    actual_currency = {}
    actual_currency.update(update_default_currencies())
    actual_currency.update(update_eth_currency(actual_currency))
    actual_currency.update(update_custom_currencies())
    salva_moedas_default(actual_currency)
    update_redis_currencies(actual_currency)
    print("corrotina rodada!!")


class WorkerSettings:
    cron_jobs = [
        cron(update_currencies, second=0, minute=0)
    ]
    on_startup = update_currencies
    redis_settings = RedisSettings(password=os.getenv("redis_access"))


def inicia_rotinas():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    Worker(redis_settings=WorkerSettings.redis_settings, cron_jobs=WorkerSettings.cron_jobs,
           on_startup=WorkerSettings.on_startup).run()


if __name__ == "__main__":
    inicia_rotinas()