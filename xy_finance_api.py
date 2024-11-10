import http.client
from aiohttp import ClientSession
from exceptions import *
from w3_client import W3Client
from loguru import logger

XY_FINANCE_NATIVE_KEY = "Native"

class XYFinanceClient:
    def __init__(
            self,
            *,
            w3: W3Client = None,
            session: ClientSession,
            aggregator_base_url,
            open_api_base_url,
    ):
        self.__w3 = w3
        self.__chain_tokens: list | None = None
        self.__session = session
        self.__aggregator_base_url = aggregator_base_url
        self.__open_api_base_url = open_api_base_url

    def set_w3(self, w3: W3Client):
        self.__w3 = w3

    async def __send_request(self, *, url: str, method: str = "GET", data: dict = None):
        logger.info(f"Sent request to {method}: {url}")

        async with self.__session.request(
            method=method,
            url=url,
            json=data if method != "GET" else None,
            params=data if method == "GET" else None,
            timeout=15,
            allow_redirects=False,
            headers={
                "Content-Type": "application/json"
            }
        ) as res:
            content = await res.json(content_type=res.headers["Content-Type"])

            if res.status not in (http.client.OK, http.client.CREATED, http.client.NO_CONTENT):
                raise RuntimeError(f"Bad response code from {url}: {res.status} {content}")

            return content

    async def get_native_token_info(self, chain_id) -> dict:
        path = f"/recommendedTokens?chainId={chain_id}"

        content = await self.__send_request(method="GET", url=f"{self.__open_api_base_url}{path}")

        if not content.get("isSuccess"):
            raise RuntimeError("Can`t get supported tokens")

        tokens: list = content.get("recommendedTokens")

        for token in tokens:
            if XY_FINANCE_NATIVE_KEY in token.get("types"):
                return token

        raise NativeTokenNotFound(chain_id)

    async def get_supported_chains(self) -> dict:
        path = "/supportedChains"
        content = await self.__send_request(method="GET", url=f"{self.__aggregator_base_url}{path}")

        if not content.get("success"):
            raise RuntimeError("Can`t get supported chains")

        chains: dict = {}
        supported_chains: list = content.get("supportedChains")
        for el in supported_chains:
            chains[el.get("name")] = el.get("chainId")

        return chains

    async def __get_contract_info(self) -> (str, dict):
        chain_id = await self._get_cain_id()

        path = f"/info/contract-info/v2/{chain_id}"

        content = await self.__send_request(
            method="GET",
            url=f"{self.__aggregator_base_url}{path}"
        )

        return content.get("routerAddress"), content.get("erc20Abi").get("abi")

    async def __get_quite(self, *, amount: float, chain_src_id: int, chain_target: int) -> dict:
        path = "/quote"

        token_address_from, token_decimals_from, _ = await self.__get_native_token_info(chain_src_id)
        token_address_to, _, _ = await self.__get_native_token_info(chain_target)

        payload = {
            "srcChainId":  await self._get_cain_id(),
            "destChainId":  await self._get_cain_id(),
            "fromTokenAddress": token_address_from,
            "toTokenAddress": token_address_to,
            "amount": self._to_wei(amount=amount, decimals=token_decimals_from),
        }

        content = await self.__send_request(
            method="GET",
            url=f"{self.__agg_base_url}{path}",
            data=payload
        )

        if not content.get("success"):
            raise GetQuoteError("Can`t get quote")

        return content

    async def __get_swap(self, quite: dict) -> dict:
        path = "/swap"

        routes: list = quite.get("routes")
        if len(routes) == 0:
            raise GetQuoteError("No one routes found")

        route = routes[0]

        payload = {
            "srcChainId":  route.get("srcChainId"),
            "destChainId":  route.get("srcChainId"),
            "fromTokenAddress": route.get("srcQuoteTokenAddress"),
            "toTokenAddress": route.get("dstQuoteTokenAddress"),
            "amount": route.get("srcQuoteTokenAmount"),
            "slippage": route.get("slippage"),
            "receiveAddress": self._get_account_address()
        }

        content = await self.__send_request(
            method="GET",
            url=f"{self.__aggregator_base_url}{path}",
            data=payload
        )

        if not content.get("isSuccess"):
            raise GetQuoteError(content.get("msg"))

        return content

    async def __build_tx(self, quite: dict):
        path = "/buildTx"

        routes: list = quite.get("routes")
        if len(routes) == 0:
            raise GetQuoteError("No one routes found")

        route = routes[0]

        payload = {
            "srcChainId":  route.get("srcChainId"),
            "dstChainId":  route.get("srcChainId"),
            "srcQuoteTokenAddress": route.get("srcQuoteTokenAddress"),
            "dstQuoteTokenAddress": route.get("dstQuoteTokenAddress"),
            "swapProviders": route.get("srcSwapDescription").get("provider"),
            "srcQuoteTokenAmount": route.get("srcQuoteTokenAmount"),
            "receiver": self._get_account_address(),
            "slippage": route.get("slippage"),
        }

        content = await self.__send_request(
            method="GET",
            url=f"{self.__agg_base_url}{path}",
            data=payload
        )

        if not content.get("success"):
            raise BuildTxError(content.get("errorMsg"))

        return content

    async def swap(
        self,
        *,
        amount: float,
        slippage: float,
        chain_src: dict,
        chain_target: dict
    ):
        quite = await self.__get_quite(
            amount=amount,
            slippage=slippage,
        )

        token_address, token_decimals, native = await self.__get_native_token_info(token_name_from)

        if not native:
            router_address, abi = await self.__get_contract_info()

            tx_hash = await self._approve(
                abi=abi,
                token_address=token_address,
                router_address=router_address,
                amount_in_wai=self._to_wei(amount=amount, decimals=token_decimals)
            )

            logger.info(f"Approving swap {amount} {token_name_from.upper()}")
            logger.info(f"Approve transaction sent: {tx_hash.hex()}")

            await self._wait_tx(hex_bytes=tx_hash)

        tx_info_swap = await self.__get_swap(quite)

        trx = tx_info_swap.get("tx") | await self._prepare_tx() | {
            "gas": tx_info_swap.get("estimatedGas")
        }

        tx_hash = await self._send_raw_transaction(await self._sign(trx))

        logger.info(f"Swap: {amount:.7f} {token_name_from.upper()} to {token_name_to.upper()}")
        logger.info(f"Transaction sent: {tx_hash.hex()}")

        await self._wait_tx(hex_bytes=tx_hash)