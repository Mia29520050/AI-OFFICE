# Synthetic Reasoning Chain-of-Thought (CoT) Dataset

## 1. Overview
The **Synthetic Reasoning CoT Dataset** module is designed to eliminate classic cognitive traps and tokenization biases in Large Language Models (LLMs) through rigorous, structured step-by-step reasoning inside `<think> ... </think>` tags.

- **Generator Script**: [scripts/generate_reasoning_data.py](file:///f:/AI-Office/scripts/generate_reasoning_data.py)
- **Output Dataset**: [data/training/reasoning_cot_train.jsonl](file:///f:/AI-Office/data/training/reasoning_cot_train.jsonl)
- **Format**: ChatML / Qwen (`messages` with role/content + pre-formatted `text` with `<|im_start|>` tokens)
- **Unit Tests**: [tests/test_reasoning_data.py](file:///f:/AI-Office/tests/test_reasoning_data.py)

---

## 2. Problem Categories & Cognitive Traps Addressed

### 2.1. Exponential Lily Pad Growth (`exponential_growth_lilypad`)
- **Linear Fallacy**: Most humans and uncalibrated models assume doubling is linear (e.g., "if 1 cluster takes 30 days to fill the lake, 4 clusters take 30/4 = 7.5 days", or "half the lake takes 30/2 = 15 days").
- **CoT Formulation**:
  $$S(t) = K \cdot S_0 \cdot r^t = S_0 \cdot r^{m + t} = S_0 \cdot r^D \implies t = D - m$$
  where $K = r^m$ is the initial cluster count.
- **Variations Generated**:
  - Initial clusters: $1, 2, 4, 8, 16, 32$ clusters ($2^m$ saving $m$ days).
  - Growth multipliers: $\times 2$ (doubling), $\times 3$ (tripling), $\times 4$ (quadrupling).
  - Fractions: $1/2, 1/4, 1/8, 1/16$ lake capacity.
  - Contexts: Lakes, ponds, petri dish bacteria division with real clock times (e.g., 8:00 AM to 12:00 PM).

### 2.2. Character-Level Decomposition Counting (`character_decomposition_counting`)
- **Tokenization Fallacy**: Subword tokenizers (Byte-Pair Encoding) merge letter sequences into single tokens (e.g. "strawberry" -> `["str", "aw", "berry"]`), preventing direct attention to individual letters and causing hallucinations.
- **CoT Formulation**:
  The assistant explicitly breaks down the phrase letter-by-letter with 1-based indexing, evaluates each position against the target character, logs matching indices, and summarizes the count.
- **Variations Generated**:
  - English words: `"strawberry"`, `"occurrence"`, `"mississippi"`, `"millennium"`, `"accommodation"`, `"embarrassment"`, `"supercalifragilisticexpialidocious"`, etc.
  - Vietnamese phrases: `"nghiêng ngả"`, `"thanh long ruột đỏ"`, `"trường đại học bách khoa"`, `"hoa bèo nở rộ"`, `"suy luận logic"`, etc.
  - Zero-occurrence negative controls (e.g., count `'z'` in `"strawberry"` = 0) to avoid false positives.

### 2.3. Knights and Knaves Truth/Liar Logic (`logic_truth_liar`)
- **Logic Failure**: LLMs often get trapped in cyclical or superficial reasoning when analyzing self-referential or accusatory statements.
- **CoT Formulation**:
  Systematic proof by contradiction:
  1. Hypothesize Person A is a Knight (truth-teller). Follow implications to check consistency.
  2. If contradiction arises, reject hypothesis and conclude Person A is a Knave (liar).
  3. Determine remaining identities and confirm all statements match.
- **Variations Generated**:
  - 2-person puzzles: "Both of us are liars", "At least one is a liar", "A claims B is liar; B claims same type", "Both are truth-tellers; B claims A is liar".
  - 3-person puzzles: Cyclic accusations and mutual type declarations.

### 2.4. Cognitive Reflection & Math Traps (`cognitive_traps_math`)
- **Bat and Ball**: Total $T$, difference $D$. Refutes $T - D$ intuitive trap by solving $2x + D = T \implies x = (T - D)/2$.
- **Machine Work Rate**: $N$ machines take $T$ minutes to make $P$ widgets. Proves why $M$ machines take $T$ minutes to make $M$ widgets.
- **Snail Climbing Well**: Deep well $H$, day climb $U$, night slip $D$. Accounts for daytime exit: $\lceil (H - U)/(U - D) \rceil + 1$.
- **Harmonic Mean Speed**: Round trip average speed $v_{\text{avg}} = \frac{2 v_1 v_2}{v_1 + v_2}$, refuting arithmetic mean $(v_1+v_2)/2$.
- **Palindrome Verification**: Systematic symmetric index pairing $S[i] \leftrightarrow S[N - 1 - i]$.

---

## 3. Dataset Distribution & Statistics

Summary of the generated `data/training/reasoning_cot_train.jsonl`:
- **Total Samples**: 1,500
- **File Size**: 6.36 MB
- **Category Breakdown**:
  - `exponential_growth_lilypad`: 450 (30.0%)
  - `logic_truth_liar`: 388 (25.9%)
  - `character_decomposition_counting`: 365 (24.3%)
  - `cognitive_traps_math`: 297 (19.8%)
- **Average Assistant Length**: 1,154.9 characters
- **Average Thinking Length**: 972.3 characters
- **CoT Think Tag Coverage**: 100% (1,500 / 1,500)

---

## 4. Usage Instructions

### Generate New or Custom Dataset
```bash
# Generate default 1500 samples
python scripts/generate_reasoning_data.py --num-samples 1500

# Custom size and seed
python scripts/generate_reasoning_data.py --num-samples 3000 --seed 123 --output-path data/training/custom_cot.jsonl

# Specific category generation
python scripts/generate_reasoning_data.py --num-samples 500 --categories exponential_growth_lilypad
```

### Run Verification Test Suite
```bash
pytest tests/test_reasoning_data.py -v
```
