# Copyright 2023-2024 SGLang Team
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

from typing import Iterable, Optional, Tuple

import torch
from torch import nn
from transformers import Qwen2Config  # Qwen3 uses Qwen2Config

from sglang.srt.layers.pooler import EmbeddingPoolerOutput, Pooler, PoolingType
from sglang.srt.layers.quantization.base_config import QuantizationConfig
from sglang.srt.model_executor.forward_batch_info import ForwardBatch
from sglang.srt.models.qwen3 import Qwen3ForCausalLM, Qwen3Model
from sglang.srt.utils import add_prefix


class Qwen3ForSequenceClassification(nn.Module):
    def __init__(
        self,
        config: Qwen2Config,
        quant_config: Optional[QuantizationConfig] = None,
        prefix: str = "",
    ) -> None:
        super().__init__()
        self.config = config
        self.quant_config = quant_config
        self.model = Qwen3Model(
            config, quant_config=quant_config, prefix=add_prefix("model", prefix)
        )
        self.score = nn.Linear(config.hidden_size, config.num_labels)
        # Use normalize=True for qwen3 embedding based on official implementation
        # Reference: https://github.com/QwenLM/Qwen3-Embedding/blob/main/examples/qwen3_embedding_transformers.py#L55
        # Official code: output = F.normalize(output, p=2, dim=1)
        self.pooler = Pooler(pooling_type=PoolingType.LAST, normalize=True)

        self.eos_token_id = config.eos_token_id

    @torch.no_grad()
    def forward(
        self,
        input_ids: torch.Tensor,
        positions: torch.Tensor,
        forward_batch: ForwardBatch,
        input_embeds: Optional[torch.Tensor] = None,
        get_embedding: bool = True,
    ) -> EmbeddingPoolerOutput:
        assert (
            get_embedding
        ), "Qwen3ForSequenceClassification is only used for embedding"

        hidden_states = self.model(input_ids, positions, forward_batch, input_embeds)
        logits = self.score(hidden_states)
        pooled_logits = self.pooler(logits, forward_batch).embeddings

        return EmbeddingPoolerOutput(pooled_logits)

    def load_weights(self, weights: Iterable[Tuple[str, torch.Tensor]]):
        # Filter out lm_head weights of Qwen3ForCausalLM
        filtered_weights = [
            (name, w) for name, w in weights if not name.startswith("lm_head")
        ]
        return Qwen3ForCausalLM.load_weights(self, filtered_weights)


EntryClass = [
    Qwen3ForSequenceClassification,
] 