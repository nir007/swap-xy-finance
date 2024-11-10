import asyncio
from lib2to3.btm_utils import tokens

import nest_asyncio
from aiohttp_socks import ProxyConnector
from aiohttp import ClientSession, TCPConnector
from exceptions import *
from xy_finance_api import XYFinanceClient
from w3_client import W3Client
from web3.exceptions import Web3RPCError
from helpers import *

async def main():
    print_hello()

    proxy, private, agg_base_url, open_api_base_url = get_start_up_settings()

    session = ClientSession(
        connector=ProxyConnector.from_url(f"http://{proxy}") if proxy else TCPConnector(),
    )

    try:
        api = XYFinanceClient(
            session=session,
            aggregator_base_url=agg_base_url,
            open_api_base_url=open_api_base_url
        )

        chains = await api.get_supported_chains()

        api.set_w3(W3Client(proxy=proxy, private=private, chain_src={}))

        chain_name_src = questionary.select(
            "Select source chain: ",
            choices=list(chains.keys())
        ).ask()

        chain_name_target = questionary.select(
            "Select target chain: ",
            choices=list(chains.keys())
        ).ask()

        native_token_src = await api.get_native_token_info(chains.get(chain_name_src))
        native_token_target = await api.get_native_token_info(chains.get(chain_name_target))

        amount = 0
        while not amount:
            amount = questionary.text(f"Enter {native_token_src.get('name').upper()} amount: ").ask()

            if not is_number(amount) and amount != "0":
                logger.warning("Enter number please!")
                amount = 0

        slippage = 0
        while not slippage:
            slippage = questionary.text(f"Enter swap slippage in percents: ").ask()

            if not is_number(slippage):
                logger.warning("Enter number please!")
                slippage = 0

        agree_to_continue = questionary.confirm(
            f"Do you want to swap "
            f"{amount} {native_token_src.get('name').upper()}"
            f" from {chain_name_src.upper()} to "
            f"{native_token_target.get('name').upper()} {chain_name_target.upper()} chain?"
        ).ask()

        if not agree_to_continue:
            logger.success("See you soon!")
            sys.exit()

        await api.swap(
            chain_src=chains.get(chain_name_src),
            chain_target=chains.get(chain_name_target),
            token_src=native_token_src,
            token_target=native_token_target,
            amount=float(amount),
            slippage=float(slippage)
        )

    except NativeTokenNotFound as e:
        logger.error(e)
    except GetQuoteError as e:
        logger.error(f"Quote: {e}")
    except BuildTxError as e:
        logger.error(f"BuildTx: {e}")
    except Web3RPCError as e:
        logger.error(f"RPC error: {e}")
    except Exception as e:
        logger.error(f"Something went wrong: {e}")
    finally:
        await session.close()

nest_asyncio.apply()
asyncio.run(main())