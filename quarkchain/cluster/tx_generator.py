import asyncio
import random
import time
from typing import Optional

from quarkchain.core import Address, Code, Transaction
from quarkchain.evm.transactions import Transaction as EvmTransaction
from quarkchain.utils import Logger
from quarkchain.config import QuarkChainConfig


def random_full_shard_id(shard_size, shard_id):
    full_shard_id = random.randint(0, (2 ** 32) - 1)
    shard_mask = shard_size - 1
    return full_shard_id & (~shard_mask) | shard_id


class Account:
    def __init__(self, address: Address, key: bytes):
        self.address = address
        self.key = key


class TransactionGenerator:
    def __init__(self, qkc_config: QuarkChainConfig, shard: int):
        self.qkc_config = qkc_config
        self.shard_id = shard.shard_id
        self.shard = shard
        self.running = False

        self.accounts = []
        for item in qkc_config.loadtest_accounts:
            account = Account(
                Address.create_from(item["address"]), bytes.fromhex(item["key"])
            )
            self.accounts.append(account)

    def generate(self, num_tx, x_shard_percent, tx: Transaction):
        """Generate a bunch of transactions in the network """
        if self.running or not self.shard.state.initialized:
            return False

        self.running = True
        asyncio.ensure_future(self.__gen(num_tx, x_shard_percent, tx))
        return True

    async def __gen(self, num_tx, x_shard_percent, sample_tx: Transaction):
        Logger.info(
            "[{}] start generating {} transactions with {}% cross-shard".format(
                self.shard_id, num_tx, x_shard_percent
            )
        )
        if num_tx <= 0:
            return
        start_time = time.time()
        tx_list = []
        total = 0
        sample_evm_tx = sample_tx.code.get_evm_transaction()
        for account in self.accounts:
            nonce = self.shard.state.get_transaction_count(account.address.recipient)
            tx = self.create_transaction(account, nonce, x_shard_percent, sample_evm_tx)
            if not tx:
                continue
            tx_list.append(tx)
            total += 1
            if len(tx_list) >= 600 or total >= num_tx:
                self.shard.add_tx_list(tx_list)
                tx_list = []
                await asyncio.sleep(
                    random.uniform(8, 12)
                )  # yield CPU so that other stuff won't be held for too long

            if total >= num_tx:
                break

        end_time = time.time()
        Logger.info(
            "[{}] generated {} transactions in {:.2f} seconds".format(
                self.shard_id, total, end_time - start_time
            )
        )
        self.running = False

    def create_transaction(
        self, account, nonce, x_shard_percent, sample_evm_tx
    ) -> Optional[Transaction]:
        shard_size = self.qkc_config.SHARD_SIZE
        shard_mask = shard_size - 1
        from_shard = self.shard_id

        # skip if from shard is specified and not matching current branch
        # FIXME: it's possible that clients want to specify '0x0' as the full shard ID, however it will not be supported
        if (
            sample_evm_tx.from_full_shard_id
            and (sample_evm_tx.from_full_shard_id & shard_mask) != from_shard
        ):
            return None

        if sample_evm_tx.from_full_shard_id:
            from_full_shard_id = sample_evm_tx.from_full_shard_id
        else:
            from_full_shard_id = (
                account.address.full_shard_id & (~shard_mask) | from_shard
            )

        if not sample_evm_tx.to:
            to_address = random.choice(self.accounts).address
            recipient = to_address.recipient
            to_full_shard_id = to_address.full_shard_id & (~shard_mask) | from_shard
        else:
            recipient = sample_evm_tx.to
            to_full_shard_id = from_full_shard_id

        if random.randint(1, 100) <= x_shard_percent:
            # x-shard tx
            to_shard = random.randint(0, self.qkc_config.SHARD_SIZE - 1)
            if to_shard == self.shard_id:
                to_shard = (to_shard + 1) % self.qkc_config.SHARD_SIZE
            to_full_shard_id = to_full_shard_id & (~shard_mask) | to_shard

        value = sample_evm_tx.value
        if not sample_evm_tx.data:
            value = random.randint(1, 100) * (10 ** 15)

        gas_token_id = 1
        transfer_token_id = 1

        evm_tx = EvmTransaction(
            nonce=nonce,
            gasprice=sample_evm_tx.gasprice,
            startgas=sample_evm_tx.startgas,
            gas_token_id=gas_token_id,
            to=recipient,
            value=value,
            transfer_token_id=transfer_token_id,
            data=sample_evm_tx.data,
            from_full_shard_id=from_full_shard_id,
            to_full_shard_id=to_full_shard_id,
            network_id=self.qkc_config.NETWORK_ID,
        )
        evm_tx.sign(account.key)
        return Transaction(code=Code.create_evm_code(evm_tx))
