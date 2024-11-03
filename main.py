import asyncio
from aiohttp_socks import ProxyConnector
from aiohttp import ClientSession, TCPConnector
from exceptions import *
from odos_api import XYFinanceClient
from web3.exceptions import Web3RPCError
from helpers import *

async def main(chain: dict, amount: float, slippage: float, token_from: str, token_to: str):
    proxy, private, base_url = get_start_up_settings()

    session = ClientSession(
        connector=ProxyConnector.from_url(f"http://{proxy}") if proxy else TCPConnector(),
    )

    try:
        api = XYFinanceClient(
            session=session,
            base_url=base_url,
            proxy=proxy,
            private=private,
            chain=chain
        )

        await api.swap(
            amount=float(amount),
            slippage=float(slippage),
            token_name_from=token_from,
            token_name_to=token_to
        )

    except TokenNotFound as e:
        logger.error(e)
    except GetQuoteError as e:
        logger.error(f"Quote: {e}")
    except AssembleError as e:
        logger.error(f"Assemble: {e}")
    except Web3RPCError as e:
        logger.error(f"RPC error: {e}")
    except Exception as e:
        logger.error(f"Something went wrong: {e}")
    finally:
        await session.close()

chain, amount, slippage, token_from, token_to = get_user_input_params()
asyncio.run(main(chain, amount, slippage, token_from, token_to))