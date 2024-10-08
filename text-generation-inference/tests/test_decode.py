
from dataclasses import dataclass

import pytest
from helpers import create_request, prepare_model
from text_generation_server.auto_generator import AutoGenerator
from text_generation_server.pb.generate_pb2 import Batch
from tqdm import tqdm

from optimum.tpu.jetstream_pt_support import jetstream_pt_available


@dataclass
class DecodeTestParams:
    model_id: str
    sequence_length: int
    expected_text: str
    do_sample: bool = False


@pytest.mark.parametrize("params",
    [
        DecodeTestParams(
            model_id="google/gemma-2b",
            sequence_length=1024,
            expected_text="\n\nThe first thing I noticed was the smell of the rain. It was a smell I had never",
        ),
        DecodeTestParams(
            model_id="Maykeye/TinyLLama-v0",
            sequence_length=1024,
            expected_text=" It was a very special day, and it was a very special day.\nThe mommy said",
        ),
    ],
    ids=["gemma-2b", "TinyLLama-v0"],
)
def test_decode_single(params):
    _test_decode_single(params)

@pytest.mark.slow
@pytest.mark.parametrize("params",
    [
        DecodeTestParams(
            model_id="meta-llama/Meta-Llama-3-8B",
            sequence_length=256,
            expected_text=" Winston Smith, his chin nuzzled into his breast in an effort to escape the vile wind,",
        ),
        DecodeTestParams(
            model_id="google/gemma-7b",
            sequence_length=128,
            expected_text="\n\nThe first line of George Orwell’s <em>1984</em> is a perfect example",
        ),
        DecodeTestParams(
            model_id="mistralai/Mistral-7B-v0.3",
            sequence_length=128,
            expected_text=" Winston Smith, his chin nuzzled into his breast in an effort to escape the v",
        ),
    ],
    ids=["Meta-Llama-3-8B", "gemma-7b", "Mistral-7B-v0.3"],
)
def test_decode_single_slow(params):
    _test_decode_single(params)


def _test_decode_single(params):
    model_path = prepare_model(params.model_id, params.sequence_length)
    input_text = "It was a bright cold day in April, and the clocks were striking thirteen."
    max_new_tokens = 20

    generator = AutoGenerator.from_pretrained(
        model_path, revision="", max_batch_size=1, max_sequence_length=params.sequence_length
    )
    request = create_request(id=0, inputs=input_text, max_new_tokens=max_new_tokens, do_sample=params.do_sample)
    batch = Batch(id=0, requests=[request], size=1, max_tokens=params.sequence_length)
    generations, next_batch = generator.prefill(batch)
    # We already generated one token: call decode max_new_tokens - 1 times
    for _ in tqdm(range(max_new_tokens - 1)):
        assert next_batch.size == 1
        assert next_batch.max_tokens == params.sequence_length
        assert len(generations) == 1
        assert len(generations[0].tokens.ids) == 1
        generations, next_batch = generator.decode([next_batch])
    # Destroy generator: this will properly stop threads and prevent them from getting stuck if one of the following
    # assertions fails.
    del generator
    assert next_batch is None
    assert len(generations) == 1
    output = generations[0].generated_text
    assert output.generated_tokens == max_new_tokens
    assert output.finish_reason == 0
    if params.do_sample:
        assert output.text != params.expected_text
    else:
        assert output.text == params.expected_text


@pytest.mark.slow
@pytest.mark.parametrize("do_sample", [False, True], ids=["greedy", "sample"])
@pytest.mark.parametrize("params",
    [
        DecodeTestParams(
            model_id="meta-llama/Llama-2-7b-hf",
            sequence_length=256,
            expected_text="\nThe clocks were striking thirteen\nThe clocks were striking thirteen\nThe",
        ),
        DecodeTestParams(
            model_id="meta-llama/Meta-Llama-3-8B",
            sequence_length=256,
            expected_text=" Winston Smith, his chin on his hands, and the clock in the Ministry of Truth, Minit",
        ),
    ],
    ids=["Llama-2-7b-hf", "Meta-Llama-3-8B"],
)
def test_decode_single_jetstream_pytorch_slow(params, do_sample):
    if not jetstream_pt_available():
        pytest.skip("Jetstream PyTorch is not available")
    params.do_sample = do_sample
    _test_decode_single(params)


@pytest.mark.parametrize("do_sample", [False, True], ids=["greedy", "sample"])
@pytest.mark.parametrize("params",
    [
        DecodeTestParams(
            model_id="Maykeye/TinyLLama-v0",
            sequence_length=256,
            expected_text=" She had a big and it had a big, blue, and a big, red and a big",
        ),
    ],
    ids=["TinyLLama-v0"],
)
def test_decode_single_jetstream_pytorch(params, do_sample):
    if not jetstream_pt_available():
        pytest.skip("Jetstream PyTorch is not available")
    params.do_sample = do_sample
    _test_decode_single(params)
