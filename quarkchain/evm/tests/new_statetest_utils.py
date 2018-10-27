from quarkchain.evm.state import State
from quarkchain.evm.common import FakeHeader
from quarkchain.evm.utils import decode_hex, parse_int_or_hex, sha3, to_string, \
    remove_0x_head, encode_hex, big_endian_to_int
from quarkchain.evm.config import default_config, Env
from quarkchain.config import get_default_evm_config
from quarkchain.evm.exceptions import InvalidTransaction
import quarkchain.evm.transactions as transactions
from quarkchain.evm.messages import apply_transaction
import copy
import os
from quarkchain.db import InMemoryDb

config_string = ':info,eth.vm.log:trace,eth.vm.op:trace,eth.vm.stack:trace,eth.vm.exit:trace,eth.pb.msg:trace,eth.pb.tx:debug'

konfig = copy.copy(default_config)

# configure_logging(config_string=config_string)

fixture_path = os.path.join(os.path.dirname(__file__), '../..', 'fixtures')

fake_headers = {}


def mk_fake_header(blknum):
    if blknum not in fake_headers:
        fake_headers[blknum] = FakeHeader(sha3(to_string(blknum)))
    return fake_headers[blknum]


basic_env = {
    "currentCoinbase": "0x2adc25665018aa1fe0e6bc666dac8fc2697ff9ba",
    "currentDifficulty": "0x020000",
    "currentGasLimit": "0x7fffffffffffffff",
    "currentNumber": "0x01",
    "currentTimestamp": "0x03e8",
    "previousHash": "0x5e20a0453cecd065ea59c37ac63e079ee08998b6045136a8ce6635c7912ec0b6"
}


configs = {
    # "Frontier": config_frontier,
    # "Homestead": config_homestead,
    # "EIP150": config_tangerine,
    # "EIP158": config_spurious,
    "Byzantium": get_default_evm_config()
}

# Makes a diff between a prev and post state


def mk_state_diff(prev, post):
    o = {}
    for k in prev.keys():
        if k not in post:
            o[k] = ["-", prev[k]]
    for k in post.keys():
        if k not in prev:
            o[k] = ["+", post[k]]
        elif prev[k] != post[k]:
            ok = {}
            for key in ('nonce', 'balance', 'code'):
                if prev[k][key] != post[k][key]:
                    ok[key] = [prev[k][key], "->", post[k][key]]
            if prev[k]["storage"] != post[k]["storage"]:
                ok["storage"] = {}
                for sk in prev[k]["storage"].keys():
                    if sk not in post[k]["storage"]:
                        ok["storage"][sk] = ["-", prev[k]["storage"][sk]]
                for sk in post[k]["storage"].keys():
                    if sk not in prev[k]["storage"]:
                        ok["storage"][sk] = ["+", post[k]["storage"][sk]]
                    else:
                        ok["storage"][sk] = [
                            prev[k]["storage"][sk], "->", post[k]["storage"][sk]]
            o[k] = ok
    return o

# Compute a single unit of a state test


def compute_state_test_unit(state, txdata, indices, konfig):
    state.env.config = konfig
    s = state.snapshot()
    try:
        # Create the transaction
        tx = transactions.Transaction(
            nonce=parse_int_or_hex(txdata['nonce'] or b"0"),
            gasprice=parse_int_or_hex(txdata['gasPrice'] or b"0"),
            startgas=parse_int_or_hex(
                txdata['gasLimit'][indices["gas"]] or b"0"),
            gas_token_id=1,
            to=decode_hex(remove_0x_head(txdata['to'])),
            value=parse_int_or_hex(txdata['value'][indices["value"]] or b"0"),
            transfer_token_id=1,
            data=decode_hex(remove_0x_head(txdata['data'][indices["data"]])))
        if 'secretKey' in txdata:
            tx.sign(decode_hex(remove_0x_head(txdata['secretKey'])))
        else:
            tx._in_mutable_context = True
            tx.v = parse_int_or_hex(txdata['v'])
            tx._in_mutable_context = False
        # Run it
        prev = state.to_dict()
        success, output = apply_transaction(state, tx)
        print("Applied tx")
    except InvalidTransaction as e:
        print("Exception: %r" % e)
        success, output = False, b''
    # state.set_code('0x3e180b1862f9d158abb5e519a6d8605540c23682', b'')
    state.commit()
    post = state.to_dict()
    # print('pozt', post)
    output_decl = {
        "hash": '0x' + encode_hex(state.trie.root_hash),
        "indexes": indices,
        "diff": mk_state_diff(prev, post)
    }
    state.revert(s)
    return output_decl


# Initialize the state for state tests
def init_state(env, pre):
    # Setup env
    db = InMemoryDb()
    stateEnv = Env(config=konfig)
    stateEnv.db = db
    state = State(
        env=stateEnv,
        block_prevhash=decode_hex(remove_0x_head(env['previousHash'])),
        prev_headers=[mk_fake_header(i) for i in range(parse_int_or_hex(env['currentNumber']) - 1,
                                                       max(-1, parse_int_or_hex(env['currentNumber']) - 257), -1)],
        block_number=parse_int_or_hex(env['currentNumber']),
        block_coinbase=decode_hex(remove_0x_head(env['currentCoinbase'])),
        block_difficulty=parse_int_or_hex(env['currentDifficulty']),
        gas_limit=parse_int_or_hex(env['currentGasLimit']),
        timestamp=parse_int_or_hex(env['currentTimestamp']))

    # Fill up pre
    for address, h in list(pre.items()):
        assert len(address) in (40, 42)
        address = decode_hex(remove_0x_head(address))
        assert set(h.keys()) == set(['code', 'nonce', 'balance', 'storage'])
        state.set_nonce(address, parse_int_or_hex(h['nonce']))
        state.set_balance(address, parse_int_or_hex(h['balance']), 0)  #TODO get token_id from pre items
        state.set_code(address, decode_hex(remove_0x_head(h['code'])))
        for k, v in h['storage'].items():
            state.set_storage_data(address,
                                   big_endian_to_int(decode_hex(k[2:])),
                                   big_endian_to_int(decode_hex(v[2:])))

    state.commit(allow_empties=True)
    # state.commit()
    return state


class EnvNotFoundException(Exception):
    pass

# Verify a state test


def verify_state_test(test):
    print("Verifying state test")
    if "env" not in test:
        raise EnvNotFoundException("Env not found")
    _state = init_state(test["env"], test["pre"])
    for config_name, results in test["post"].items():
        # Old protocol versions may not be supported
        if config_name not in configs:
            continue
        print("Testing for %s" % config_name)
        for result in results:
            data = test["transaction"]['data'][result["indexes"]["data"]]
            if len(data) > 2000:
                data = "data<%d>" % (len(data) // 2 - 1)
            print("Checking for values: g %d v %d d %s (indexes g %d v %d d %d)" % (
                  parse_int_or_hex(test["transaction"]
                                   ['gasLimit'][result["indexes"]["gas"]]),
                  parse_int_or_hex(test["transaction"]
                                   ['value'][result["indexes"]["value"]]),
                  data,
                  result["indexes"]["gas"],
                  result["indexes"]["value"],
                  result["indexes"]["data"]))
            computed = compute_state_test_unit(
                _state, test["transaction"], result["indexes"], configs[config_name])
            if computed["hash"][-64:] != result["hash"][-64:]:
                for k in computed["diff"]:
                    print(k, computed["diff"][k])
                raise Exception(
                    "Hash mismatch, computed: %s, supplied: %s" %
                    (computed["hash"], result["hash"]))
            else:
                for k in computed["diff"]:
                    print(k, computed["diff"][k])
                print("Hash matched!: %s" % computed["hash"])
    return True
