import json
from web3 import AsyncWeb3, AsyncHTTPProvider
from web3.types import HexBytes, HexStr, TxParams, Wei
from typing import cast
from loguru import logger

class W3Client:
    def __init__(self, *, proxy, private, chain):
        self._chain = chain
        self._private = private

        request_kwargs = {
            "proxy": f"http://{proxy}"
        } if proxy else {}

        self.__w3 = AsyncWeb3(
            AsyncHTTPProvider(
                self._chain.get("rpc_url"),
                request_kwargs=request_kwargs
            )
        )
        self._account_address = self.__w3.to_checksum_address(
            self.__w3.eth.account.from_key(private).address
        )

    async def _send_raw_transaction(self, trx):
        return await self.__w3.eth.send_raw_transaction(trx)

    def _to_checksum(self, address):
        return self.__w3.to_checksum_address(address)

    async def _get_cain_id(self) -> int:
        return await self.__w3.eth.chain_id

    def _to_wei(self, *, amount: float, decimals: int) -> int:
        unit_name = {
            6: "mwei",
            9: "gwei",
            18: "ether",
        }.get(decimals)

        if not unit_name:
            raise RuntimeError(f"Can`t find unit for decimals: {decimals}")

        return self.__w3.to_wei(amount, unit_name)

    async def _send_transaction(self, transaction):
        signed_tx = self.__w3.eth.account.sign_transaction(transaction, self._private)
        tx_hash = await self.__w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        return tx_hash

    def _get_contract(self, token_address: str, abi):
        return self.__w3.eth.contract(
            address=self.__w3.to_checksum_address(token_address),
            abi=abi
        )

    async def _prepare_tx(self) -> TxParams:
        base_fee = await self.__w3.eth.gas_price
        max_priority_fee_per_gas = await self.__w3.eth.max_priority_fee
        max_fee_per_gas = int(base_fee + max_priority_fee_per_gas)

        trx: TxParams = {
            "from": self._account_address,
            "chainId": await self.__w3.eth.chain_id,
            "nonce": await self.__w3.eth.get_transaction_count(self._account_address),
            "maxPriorityFeePerGas": max_priority_fee_per_gas,
            "maxFeePerGas": cast(Wei, max_fee_per_gas),
            "type": HexStr("0x2")
        }

        return trx

    async def _approve(self, *, token_address: str, router_address: str, abi: dict, amount_in_wai: int):
        transaction = await self._get_contract(
            token_address=token_address,
            abi=abi
        ).functions.approve(
            self._to_checksum(router_address),
            amount_in_wai
        ).build_transaction(await self._prepare_tx())

        return await self._send_transaction(transaction)

    async def _sign(self, transaction: dict) -> HexBytes:
        signed_transaction = self.__w3.eth.account.sign_transaction(transaction, self._private)
        return signed_transaction.raw_transaction

    async def _wait_tx_2(self, hex_bytes: HexBytes):
        await self.__w3.eth.wait_for_transaction_receipt(hex_bytes, timeout=80)
        logger.success(f"Transaction was successful: {self._chain.get('explorer_url')}tx/0x{hex_bytes.hex()}")