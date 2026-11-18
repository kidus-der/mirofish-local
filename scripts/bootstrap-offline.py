"""One-time, explicit model download: the ONLY sanctioned network step of this fork.

Run: cd backend && uv run python ../scripts/bootstrap-offline.py
Fills backend/.models (HF_HOME, TIKTOKEN_CACHE_DIR) so the app then runs with the network blocked.
"""

import os
import sys

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND))
if os.environ.get("NETGUARD") != "off":
    # sitecustomize already armed the guard in this process; restart with it off (it prints a loud warning).
    os.environ.update(NETGUARD="off", HF_HUB_OFFLINE="0", TRANSFORMERS_OFFLINE="0")
    os.execv(sys.executable, [sys.executable, *sys.argv])
os.makedirs(os.environ["TIKTOKEN_CACHE_DIR"], exist_ok=True)

# 1. tiktoken: CAMEL's OpenAI-compatible token counter hard-codes "gpt-4o-mini" for any model
#    name it does not know (such as mirofish-qwen), which resolves to o200k_base.
from camel.types.unified_model_type import UnifiedModelType  # noqa: E402
from camel.utils.token_counting import OpenAITokenCounter  # noqa: E402

counter = OpenAITokenCounter(UnifiedModelType("mirofish-qwen"))
print("tiktoken encoding:", counter.encoding.name)

# 2. OASIS TWHIN recommender (Twitter platform): tokenizer + model.
from transformers import AutoModel, AutoTokenizer  # noqa: E402

AutoTokenizer.from_pretrained("Twitter/twhin-bert-base")
AutoModel.from_pretrained("Twitter/twhin-bert-base")
print("twhin-bert-base ok")

# 3. Reranker, used via sentence-transformers CrossEncoder.
from sentence_transformers import CrossEncoder  # noqa: E402

CrossEncoder("BAAI/bge-reranker-v2-m3")
print("bge-reranker-v2-m3 ok")
# paraphrase-MiniLM-L6-v2 is not fetched: MiroFish only uses recsys "twhin-bert" (Twitter) and
# "reddit" (no model); the MiniLM path (recsys_type "twitter") is never selected.
