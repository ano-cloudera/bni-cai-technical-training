# Resource Sizing

| Workload | Count | Total CPU | Total memory | GPU |
|---|---:|---:|---:|---:|
| Group Workbench sessions | 10 | 20 vCPU | 80 GB | 0 |
| Concurrent group Streamlit Applications | 3 | 3 vCPU | 6 GB | 0 |
| Shared vLLM Application | 1 | 16 vCPU | 64 GB | 1 H200 |
| Shared Qdrant Application | 1 | 4 vCPU | 16 GB | 0 |
| Shared Phoenix Application | 1 | 4 vCPU | 16 GB | 0 |
| Shared LiteLLM Application | 1 | 2 vCPU | 4 GB | 0 |
| Day 1 group UI peak: sessions + vLLM + Qdrant + 3 Streamlit | | 43 vCPU | 166 GB | 1 GPU |
| Conservative planning capacity | | 60 vCPU | 220 GB | 1 GPU |

This excludes Cloudera AI platform services, Agent Studio installation, and the Model/Application workloads created by publishing the selected Agent Studio workflow.

Phoenix and LiteLLM are provisioned but scheduled in separate modules so the workshop remains within the five-active-Application limit. The L40S sandbox and H200 BNI runtime profiles must each pass their own GPU compatibility test.

