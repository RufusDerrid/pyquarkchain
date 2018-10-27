# MultiToken QuarkChain

Multi-token version P2P Transactional System QuarkChain https://quarkchain.io/

Changes:
* Account model with multi-token balance
* Transaction model with gas_token_id and transfer_token_id
* apply_transaction metod changed
* Message, ShardState, CrossShardTransactionDeposit models and other minor changes
* Some changes in JSON RPC, inscluding createTransactions method
* Tests updated for multi-token

# Installation

Run docker in directory with Dockerfile:
docker build .

# Using

Created docker image after running starts QuarkChain cluster with minning.
For testing transaction with multi-token send request createTransactions:

curl -X POST --data '{"jsonrpc":"2.0","method":"createTransactions","params":{"numTxPerShard":10000, 
   "xShardPercent":10},"id":0}' container_address:38491
