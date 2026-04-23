"""
paraphraser.py  (FIXED)
-----------------------
Fixes applied
─────────────
1. BUG: num_return_sequences > 1  with  do_sample=True  and  num_beams=1
   crashes PyTorch ("do_sample=True requires num_return_sequences==1 or num_beams>1").
   FIX: generate one sequence at a time inside a loop → collect N independent
        samples without triggering the constraint.

2. BUG: nltk.data.find('tokenizers/punkt') fails on NLTK ≥ 3.9 because the
   new tokenizer is stored under 'tokenizers/punkt_tab', not 'punkt'.
   FIX: try both keys; download both 'punkt' and 'punkt_tab' when missing.

3. BUG: process_text() skips sentences with ≤ 8 words, but NLTK may split
   compound sentences at abbreviations, leaving fragments un-paraphrased.
   FIX: lower threshold to 5 words so short-but-complete sentences are caught.

4. IMPROVEMENT: Added graceful fallback — if the model is unavailable the
   class still works using rule-based rewriting (useful for testing / CI).
"""

import random
import re


# ---------------------------------------------------------------------------
# Rule-based fallback (no ML dependency required for basic operation)
# ---------------------------------------------------------------------------
_RULE_REWRITES = [
    (r"\bFurthermore,?\s*",         "Also, "),
    (r"\bMoreover,?\s*",            "On top of that, "),
    (r"\bHowever,?\s*",             "But "),
    (r"\bAdditionally,?\s*",        "Also, "),
    (r"\bIn conclusion,?\s*",       "To wrap up, "),
    (r"\bIn summary,?\s*",          "In short, "),
    (r"\bIt is crucial to\b",       "You need to"),
    (r"\bIt is essential to\b",     "You should"),
    (r"\bIt is worth noting that\b","Note that"),
    (r"\bThis demonstrates\b",      "This shows"),
    (r"\bplays a vital role\b",     "matters a lot"),
    (r"\bdelve into\b",             "look at"),
    (r"\butilize[sd]?\b",           "use"),
    (r"\bleverages?\b",             "uses"),
    (r"\bfacilitates?\b",           "helps"),
    (r"\bimplements?\b",            "builds"),
    (r"\bdemonstrates?\b",          "shows"),
    (r"\brobust\b",                 "solid"),
    (r"\bseamless(ly)?\b",          r"smooth\1"),
    (r"\befficient(ly)?\b",         "well"),
    (r"\bsignificant\b",            "major"),
    (r"\bnumerous\b",               "many"),
    (r"\bapproximately\b",          "about"),
    (r"\bsubsequently\b",           "later"),
    (r"\bIn order to\b",            "To"),
    (r"\bdue to the fact that\b",   "because"),
    (r"\bat this point in time\b",  "now"),
    (r"\ba large number of\b",      "many"),
    (r"\bAs a result,?\s*",         "So, "),
    (r"\bthus\b",                   "so"),
    (r"\bhence\b",                  "so"),
    (r"\bindeed\b",                 "actually"),
    (r"\bcrucial\b",                "important"),
    (r"\bessential\b",              "needed"),
]


def _rule_paraphrase(sentence: str) -> str:
    """Lightweight rule-based rewrite — used as fallback when model unavailable."""
    result = sentence
    for pattern, replacement in _RULE_REWRITES:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


# ---------------------------------------------------------------------------
# NLTK sentence tokenizer (with safe download)
# ---------------------------------------------------------------------------
def _safe_sent_tokenize(text: str) -> list[str]:
    """Tokenize text into sentences; downloads NLTK data if missing."""
    import nltk

    # FIX 2: check for both old ('punkt') and new ('punkt_tab') resource names
    for resource in ("tokenizers/punkt_tab", "tokenizers/punkt"):
        try:
            nltk.data.find(resource)
            break
        except LookupError:
            pass
    else:
        # Neither found — download both to cover all NLTK versions
        for pkg in ("punkt", "punkt_tab"):
            try:
                nltk.download(pkg, quiet=True)
            except Exception:
                pass

    try:
        from nltk.tokenize import sent_tokenize
        return sent_tokenize(text)
    except Exception:
        # Last resort: naive split
        return re.split(r'(?<=[.!?])\s+', text.strip())


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------
class MLParaphraser:
    """
    T5-based paraphraser with rule-based fallback.

    Parameters
    ----------
    model_name : str
        HuggingFace model hub ID.
    use_ml : bool
        Set False to skip model loading entirely (uses rule-based only).
    """

    def __init__(
        self,
        model_name: str = "Vamsi/T5_Paraphrase_Paws",
        use_ml: bool = True,
    ):
        self.model     = None
        self.tokenizer = None
        self.device    = "cpu"
        self._ml_ready = False

        if use_ml:
            self._load_model(model_name)

        if not self._ml_ready:
            print("  [MLParaphraser] Running in rule-based fallback mode.")

    # ------------------------------------------------------------------
    def _load_model(self, model_name: str):
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

            print(f"  [MLParaphraser] Loading model ({model_name})...")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False)
            self.model     = AutoModelForSeq2SeqLM.from_pretrained(model_name)

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            self._ml_ready = True
            print(f"  [MLParaphraser] Model loaded on: {self.device}")

        except Exception as exc:
            print(f"  [MLParaphraser] Could not load ML model ({exc}).")
            self._ml_ready = False

    # ------------------------------------------------------------------
    def paraphrase_sentence(
        self,
        sentence: str,
        num_return_sequences: int = 3,
        temperature: float = 0.9,
        top_k: int = 50,
        top_p: float = 0.95,
    ) -> str:
        """
        Paraphrase a single sentence.

        FIX 1: generate sequences one at a time to avoid the PyTorch error
        "num_return_sequences > 1 requires num_beams > 1 when do_sample=True".
        """
        if not self._ml_ready:
            return _rule_paraphrase(sentence)

        import torch

        text = "paraphrase: " + sentence.strip() + " </s>"

        encoding = self.tokenizer(
            text,
            padding="max_length",
            truncation=True,
            max_length=256,
            return_tensors="pt",
        )
        input_ids      = encoding["input_ids"].to(self.device)
        attention_mask = encoding["attention_mask"].to(self.device)

        results = []

        # FIX 1: loop → one sequence per call
        for _ in range(num_return_sequences):
            with torch.no_grad():
                output = self.model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    max_length=256,
                    do_sample=True,
                    temperature=temperature,
                    top_k=top_k,
                    top_p=top_p,
                    num_beams=1,           # sampling mode
                    num_return_sequences=1,# one at a time  ← FIX
                    repetition_penalty=1.2,
                    no_repeat_ngram_size=3,
                )

            decoded = self.tokenizer.decode(
                output[0],
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True,
            )

            if decoded.lower() != sentence.lower():
                results.append(decoded)

        # Deduplicate & pick best (longest tends to be most complete)
        results = list(set(results))
        if not results:
            return _rule_paraphrase(sentence)  # fallback

        results.sort(key=len, reverse=True)
        return results[0]

    # ------------------------------------------------------------------
    def process_text(
        self,
        text: str,
        min_words: int = 5,           # FIX 3: was 8 — catches more sentences
        num_return_sequences: int = 3,
    ) -> str:
        """
        Paraphrase every sentence in *text* that has at least *min_words* words.
        """
        sentences = _safe_sent_tokenize(text)
        paraphrased = []

        for sent in sentences:
            word_count = len(sent.split())
            if word_count >= min_words:
                new_sent = self.paraphrase_sentence(
                    sent, num_return_sequences=num_return_sequences
                )
                paraphrased.append(new_sent)
            else:
                paraphrased.append(sent)

        return " ".join(paraphrased)


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # use_ml=False → instant test without downloading the model
    para = MLParaphraser(use_ml=False)

    ai_text = (
        "Furthermore, it is crucial to delve into the data. "
        "The system processes the data efficiently, and it stores the results in the cloud. "
        "This demonstrates that robust and scalable solutions are essential."
    )

    print("Original:")
    print(ai_text)
    print("\nParaphrased:")
    print(para.process_text(ai_text))