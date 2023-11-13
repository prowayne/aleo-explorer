from dataclasses import dataclass

from aleo_types import Block


@dataclass
class BlockModel:
    height: int
    block_hash: str
    previous_hash: str
    cumulative_proof_target: int
    coinbase_target: int

    @classmethod
    def from_block(cls, block: Block):
        return cls(
            height=int(block.height),
            block_hash=str(block.block_hash),
            previous_hash=str(block.previous_hash),
            cumulative_proof_target=int(block.cumulative_proof_target),
            coinbase_target=int(block.header.metadata.coinbase_target)
        )


