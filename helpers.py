import os
import json
import questionary
from loguru import logger
from dotenv import load_dotenv

CHAINS_FILE_NAME = "chains.json"
README_URL = "https://github.com/nir007/swap-xy-finance/blob/main/Readme.md"

def is_number(val: str) -> bool:
    return val.replace(".", "").isdigit()

def get_start_up_settings():
    load_dotenv()

    try:
        proxy = os.getenv("PROXY")
        private = os.getenv("PRIVATE")
        base_url = os.getenv("BASE_URL")

        if not private:
            raise RuntimeError(f"Setup your private key in .env file please. \nSee {README_URL}")

        if not base_url:
            raise RuntimeError(f"Setup XY Finance api base url in .env file please. \nSee {README_URL}")

        return proxy, private, base_url

    except Exception as e:
        logger.error(f"Invalid startup data: {e}")

def get_user_input_params():
    with open(CHAINS_FILE_NAME, "r") as file:
        chains: dict = json.load(file)

    happy = questionary.confirm("Are you happy?").ask()

    logger.info("Great! Lets go" if happy else "Now we will make you happy")

    chain_name = questionary.select("Select chain: ", choices=list(chains.keys())).ask()

    chain_tokens = list(chains.get(chain_name).get("tokens"))

    token_from = questionary.select("Select token from: ", choices=chain_tokens).ask()

    chain_tokens.remove(token_from)
    token_to = questionary.select("Select token to: ", choices=chain_tokens).ask()

    amount = 0
    while not amount:
        amount = questionary.text(f"Enter {token_from.upper()} amount: ").ask()

        if not is_number(amount) and amount != "0":
            logger.warning("Enter number please!")
            amount = 0

    slippage = 0
    while not slippage:
        slippage = questionary.text(f"Enter swap slippage in percents: ").ask()

        if not is_number(slippage):
            logger.warning("Enter number please!")
            slippage = 0

    return chains.get(chain_name), amount, slippage, token_from, token_to