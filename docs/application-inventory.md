# Application Inventory

| Owner | Project | Application | Concurrent policy |
|---|---|---|---|
| Trainer | `bni-ai-training-shared` | `bni-vllm-qwen35-9b` | One shared |
| Trainer | `bni-ai-training-shared` | `bni-qdrant` | One shared |
| Trainer | `bni-ai-training-shared` | `bni-phoenix` | One shared |
| Trainer | `bni-ai-training-shared` | `bni-litellm` | One shared |
| Group NN | `bni-ai-training-gNN` | `bni-credit-insight-gNN` | Five active at a time |

The trainer keeps exact CAI IDs in an untracked local inventory. Only one selected Agent Studio workflow is published.

