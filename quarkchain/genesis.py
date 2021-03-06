from typing import Optional

from quarkchain.config import QuarkChainConfig
from quarkchain.core import (
    Address,
    MinorBlockMeta,
    MinorBlockHeader,
    MinorBlock,
    Branch,
    ShardInfo,
    RootBlockHeader,
    RootBlock,
)
from quarkchain.evm.state import State as EvmState
from quarkchain.utils import sha3_256, check


class GenesisManager:
    """ Manage the creation of genesis blocks based on the genesis configs from env"""

    def __init__(self, qkc_config: QuarkChainConfig):
        self._qkc_config = qkc_config

    def create_root_block(self) -> RootBlock:
        """ Create the genesis root block """
        genesis = self._qkc_config.ROOT.GENESIS
        header = RootBlockHeader(
            version=genesis.VERSION,
            height=genesis.HEIGHT,
            shard_info=ShardInfo.create(genesis.SHARD_SIZE),
            hash_prev_block=bytes.fromhex(genesis.HASH_PREV_BLOCK),
            hash_merkle_root=bytes.fromhex(genesis.HASH_MERKLE_ROOT),
            create_time=genesis.TIMESTAMP,
            difficulty=genesis.DIFFICULTY,
        )
        return RootBlock(header=header, minor_block_header_list=[])

    def create_minor_block(
        self, root_block: RootBlock, shard_id: int, evm_state: EvmState
    ) -> MinorBlock:
        """ Create genesis block for shard.
        Genesis block's hash_prev_root_block is set to the genesis root block.
        Genesis state will be committed to the given evm_state.
        """
        branch = Branch.create(self._qkc_config.SHARD_SIZE, shard_id)
        genesis = self._qkc_config.SHARD_LIST[shard_id].GENESIS
        coinbase_address = Address.create_from(bytes.fromhex(genesis.COINBASE_ADDRESS))
        check(coinbase_address.get_shard_id(self._qkc_config.SHARD_SIZE) == shard_id)

        for address_hex, amount_in_wei in genesis.ALLOC.items():
            address = Address.create_from(bytes.fromhex(address_hex))
            check(address.get_shard_id(self._qkc_config.SHARD_SIZE) == shard_id)
            evm_state.full_shard_id = address.full_shard_id
            evm_state.delta_balance(address.recipient, amount_in_wei, 0)

        evm_state.commit()

        meta = MinorBlockMeta(
            hash_merkle_root=bytes.fromhex(genesis.HASH_MERKLE_ROOT),
            hash_evm_state_root=evm_state.trie.root_hash,
            coinbase_address=coinbase_address,
        )
        header = MinorBlockHeader(
            version=genesis.VERSION,
            height=genesis.HEIGHT,
            branch=branch,
            hash_prev_minor_block=bytes.fromhex(genesis.HASH_PREV_MINOR_BLOCK),
            hash_prev_root_block=root_block.header.get_hash(),
            evm_gas_limit=genesis.GAS_LIMIT,
            hash_meta=sha3_256(meta.serialize()),
            coinbase_amount=genesis.COINBASE_AMOUNT,
            create_time=genesis.TIMESTAMP,
            difficulty=genesis.DIFFICULTY,
            extra_data=bytes.fromhex(genesis.EXTRA_DATA),
        )
        return MinorBlock(header=header, meta=meta, tx_list=[])
