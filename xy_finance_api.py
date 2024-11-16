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
            w3: W3Client,
            session: ClientSession,
            aggregator_base_url,
            open_api_base_url,
    ):
        self.__w3 = w3
        self.__session = session
        self.__aggregator_base_url = aggregator_base_url
        self.__open_api_base_url = open_api_base_url

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
            raise RuntimeError("Can`t get native token")

        tokens: list = content.get("recommendedTokens")

        for token in tokens:
            if XY_FINANCE_NATIVE_KEY in token.get("types"):
                return {
                    "address": token.get("address"),
                    "symbol": token.get("symbol"),
                    "name": token.get("name"),
                    "decimals": token.get("decimals"),
                    "chainId": token.get("chainId")
                }

        raise NativeTokenNotFound(chain_id)

    async def __get_quite(self, *, amount: float, slippage: float, token_src: dict, token_target: dict) -> dict:
        path = "/quote"

        payload = {
            "srcChainId": token_src.get("chainId"),
            "dstChainId": token_target.get("chainId"),
            "srcQuoteTokenAddress": token_src.get("address"),
            "srcQuoteTokenAmount": self.__w3.to_wei(amount=amount, decimals=token_src.get("decimals")),
            "dstQuoteTokenAddress": token_target.get("address"),
            "slippage": slippage,
        }

        content = await self.__send_request(
            method="GET",
            url=f"{self.__aggregator_base_url}{path}",
            data=payload
        )

        if not content.get("success"):
            raise GetQuoteError(f"Can`t get quote. {content.get('errorMsg')}")

        return content.get("routes")[0]

    async def __build_tx(self, quite: dict):
        path = "/buildTx"

        payload = {
            "srcChainId":  quite.get("srcChainId"),
            "dstChainId":  quite.get("dstChainId"),
            "srcQuoteTokenAddress": quite.get("srcQuoteTokenAddress"),
            "dstQuoteTokenAddress": quite.get("dstQuoteTokenAddress"),
            "srcBridgeTokenAddress": quite.get("bridgeDescription").get("srcBridgeTokenAddress"),
            "dstBridgeTokenAddress": quite.get("bridgeDescription").get("dstBridgeTokenAddress"),
            "srcQuoteTokenAmount": quite.get("srcQuoteTokenAmount"),
            "receiver": self.__w3.get_account_address(),
            "slippage": quite.get("slippage"),
            "bridgeProvider": quite.get("bridgeDescription").get("provider")
        }

        if quite.get("srcSwapDescription") and quite.get("srcSwapDescription") is not None:
            payload = payload | {
                "srcSwapProvider": quite.get("srcSwapDescription").get("provider"),
                "dstSwapProvider": quite.get("srcSwapDescription").get("provider"),
            }

        content = await self.__send_request(
            method="GET",
            url=f"{self.__aggregator_base_url}{path}",
            data=payload
        )

        if not content.get("success"):
            raise BuildTxError(content.get("errorMsg"))

        return content

    async def get_balance(self):
        return await self.__w3.get_native_token_balance()

    async def swap(
        self,
        *,
        amount: float,
        slippage: float,
        token_src: dict,
        token_target: dict
    ):
        quite = await self.__get_quite(
            amount=amount,
            slippage=slippage,
            token_src=token_src,
            token_target=token_target
        )

        gas_price = await self.__w3.get_ges_price()

        decimals = token_src.get('decimals')
        balance = await self.__w3.get_native_token_balance()
        will_be_spend = self.__w3.to_wei(amount, decimals) + gas_price

        if balance < will_be_spend:
            raise InsufficientError(
                f"Balance: {(balance / (10 ** decimals)):.7f},"
                f" amount with gas: {(will_be_spend / (10 ** decimals)):.7f}")

        tx_info = await self.__build_tx(quite)

        estimate_gas = await self.__w3.get_estimate_gas(tx_info["tx"])

        tx = tx_info.get("tx") | await self.__w3.prepare_tx() | {
            "gas": estimate_gas,
        }

        tx_signed = await self.__w3.sign(tx)

        tx_hash = await self.__w3.send_raw_transaction(tx_signed.raw_transaction)

        logger.info(f"Swap: {amount} {token_src.get('name').upper()} to {token_target.get('name').upper()}")
        logger.info(f"Transaction sent: {tx_hash.hex()}")

        await self.__w3.wait_tx(hex_bytes=tx_hash)