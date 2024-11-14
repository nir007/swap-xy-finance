from web3 import AsyncWeb3, AsyncHTTPProvider
from web3.types import HexBytes, HexStr, TxParams, Wei
from typing import cast
from loguru import logger

class W3Client:
    def __init__(self, *, proxy, private, chain_src):
        self._chain_src = chain_src
        self._private = private

        print(f"rpc_url {self._chain_src.get('rpc_url')}")

        request_kwargs = {
            "proxy": f"http://{proxy}"
        } if proxy else {}

        self.__w3 = AsyncWeb3(
            AsyncHTTPProvider(
                self._chain_src.get('rpc_url'),
                request_kwargs=request_kwargs
            )
        )

        self._account_address = self.__w3.to_checksum_address(
            self.__w3.eth.account.from_key(private).address
        )

    async def send_raw_transaction(self, trx):
        return await self.__w3.eth.send_raw_transaction(trx)

    def to_checksum(self, address):
        return self.__w3.to_checksum_address(address)

    def get_account_address(self):
        return self._account_address

    async def get_cain_id(self) -> int:
        return await self.__w3.eth.chain_id

    def to_wei(self, amount: float, decimals: int) -> int:
        unit_name = {
            6: "mwei",
            9: "gwei",
            18: "ether",
        }.get(decimals)

        if not unit_name:
            raise RuntimeError(f"Can`t find unit for decimals: {decimals}")

        return self.__w3.to_wei(amount, unit_name)

    def from_wei(self, *, amount: int, decimals: int) -> float:
        unit_name = {
            6: "mwei",
            9: "gwei",
            18: "ether",
        }.get(decimals)

        if not unit_name:
            raise RuntimeError(f"Can`t find unit for decimals: {decimals}")

        return self.__w3.from_wei(amount, unit_name)

    async def send_transaction(self, transaction):
        signed_tx = self.__w3.eth.account.sign_transaction(transaction, self._private)
        tx_hash = await self.__w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        return tx_hash

    def get_contract(self, token_address: str, abi):
        return self.__w3.eth.contract(
            address=self.__w3.to_checksum_address(token_address),
            abi=abi
        )

    async def get_nonce(self):
        return await self.__w3.eth.get_transaction_count(self._account_address)

    async def get_ges_price(self):
        return await self.__w3.eth.gas_price

    async def get_estimate_gas(self, tx: dict):
        return await self.__w3.eth.estimate_gas(tx)

    async def _get_gas_price(self) -> (int, int):
        base_fee = await self.get_ges_price()
        max_priority_fee_per_gas = await self.__w3.eth.max_priority_fee
        max_fee_per_gas = int(base_fee + max_priority_fee_per_gas)

        return max_priority_fee_per_gas, max_fee_per_gas

    async def prepare_tx(self) -> TxParams:
        max_priority_fee_per_gas, max_fee_per_gas = await self._get_gas_price()

        trx: TxParams = {
            "from": self._account_address,
            "chainId": await self.__w3.eth.chain_id,
            "nonce": await self.get_nonce(),
            "maxPriorityFeePerGas": max_priority_fee_per_gas,
            "maxFeePerGas": cast(Wei, max_fee_per_gas),
            "type": HexStr("0x2")
        }

        return trx

    async def get_native_token_balance(self):
        return await self.__w3.eth.get_balance(self._account_address)

    async def sign(self, transaction: dict) -> HexBytes:
        signed_transaction = self.__w3.eth.account.sign_transaction(transaction, self._private)
        return signed_transaction.raw_transaction

    async def wait_tx(self, hex_bytes: HexBytes):
        await self.__w3.eth.wait_for_transaction_receipt(hex_bytes, timeout=80)
        logger.success(f"Transaction was successful: {self._chain_src.get('explorer_url')}tx/0x{hex_bytes.hex()}")