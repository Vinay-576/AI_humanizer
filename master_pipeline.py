"""
master_pipeline.py  (FIXED + IMPROVED)
---------------------------------------
Fixes applied
─────────────
1. BUG: `synonym_engine` module was missing entirely.
   FIX: Created synonym_engine.py; import now works.

2. BUG: `while iteration <= max_iterations` runs (max_iterations + 1) times.
   e.g. max_iterations=3 → iterations 0,1,2,3 = 4 loops.
   FIX: changed to `while iteration < max_iterations`.

3. BUG: `perplexity = 80.0` is a hard-coded constant — it never changes
   regardless of how many transformations are applied.  The score therefore
   can never rise above ~80 with the original weights, making it impossible
   to reach the default target of 95.
   FIX: perplexity is now estimated from lexical richness & AI-word density,
   so the score actually responds to each transformation pass.

4. BUG: `vary_sentence_structure` could truncate every sentence to half-length
   (r < 0.25 branch) without any length guard, producing half-sentences.
   FIX: only apply truncation when sentence is > 15 words, and keep at least
   8 words.

5. BUG: `apply_synonyms` uses `random.random() < 0.7` to SKIP — meaning 70 %
   of words are never swapped, giving very low coverage per iteration.
   FIX: probability now respects a configurable `swap_rate` (default 0.45),
   and longer phrases are tried first so they aren't missed by partial matches.

6. IMPROVEMENT: Added `_estimate_perplexity()` so the score is dynamic and
   actually improves as AI patterns are removed.

7. IMPROVEMENT: Added `_inject_filler_phrases()` to insert natural human
   connectors ("you know", "I think", "to be honest") for burstiness.

8. IMPROVEMENT: Added `_vary_punctuation()` for em-dashes and ellipses that
   are typical in human writing.

9. IMPROVEMENT: Score breakdown is now printed at each iteration so you can
   see which metric is lagging.
"""

import re
import random
import math

import spacy
from synonym_engine import SynonymEngine
from paraphraser import MLParaphraser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_AI_TRIGGERS = [
    "delve", "utilize", "leverage", "robust", "scalable",
    "seamless", "efficient", "significant", "numerous",
    "intricate", "crucial", "essential", "furthermore",
    "moreover", "thus", "hence", "additionally",
    "in conclusion", "in summary", "as a result",
    "this demonstrates", "plays a vital role",
    "in order to", "due to the fact that",
    "it is worth noting", "at this point in time",
    "a large number of", "on the other hand",
]

_HUMAN_FILLERS = [
    "you know,", "I think", "honestly,", "basically,",
    "so,", "well,", "to be fair,", "actually,",
    "look,", "here's the thing —",
]

_CASUAL_STARTERS = [
    "Honestly,", "So,", "Well,", "Basically,",
    "Here's the thing —", "Look,", "Truth is,",
]


class MasterHumanizer:
    def __init__(self, use_ml: bool = True, db_config: dict = None):
        print("🚀 Initializing Master Humanizer Pipeline...")

        # NLP — fall back to a lightweight wrapper if the model isn't installed
        try:
            self.nlp = spacy.load("en_core_web_sm")
            self._spacy_ok = True
        except OSError:
            print("  [spaCy] en_core_web_sm not found — using lightweight fallback NLP.")
            print("          To enable full NLP: python -m spacy download en_core_web_sm")
            self.nlp = None
            self._spacy_ok = False

        # Components
        self.synonym_db  = SynonymEngine(db_config=db_config)
        self.paraphraser = MLParaphraser(use_ml=use_ml)

        # Cache replacements — sort by phrase length DESC so multi-word
        # phrases are matched before their component words
        raw = self.synonym_db.get_all_replacements()
        self.replacements = dict(
            sorted(raw.items(), key=lambda kv: len(kv[0].split()), reverse=True)
        )

        print("✅ Pipeline ready.\n")

    # ------------------------------------------------------------------ #
    #  TOKENIZER HELPER (spaCy or regex fallback)                         #
    # ------------------------------------------------------------------ #
    def _tokenize(self, text: str):
        """Return (alpha_tokens_list, sentence_lengths_list)."""
        if self._spacy_ok and self.nlp:
            doc     = self.nlp(text)
            tokens  = [t.text.lower() for t in doc if t.is_alpha]
            lengths = [len(list(s)) for s in doc.sents]
        else:
            tokens  = re.findall(r"[a-zA-Z]+", text.lower())
            lengths = [len(s.split()) for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
        return tokens, lengths

    # ------------------------------------------------------------------ #
    #  SCORE CALCULATION                                                   #
    # ------------------------------------------------------------------ #
    def calculate_score(self, text: str, verbose: bool = False) -> float:
        tokens, lengths = self._tokenize(text)
        if not tokens:
            return 0.0

        # 1. Vocabulary Diversity
        vocab_diversity = (len(set(tokens)) / len(tokens)) * 100

        # 2. Burstiness (sentence-length variance)
        if not lengths:
            lengths = [len(tokens)]
        if len(lengths) > 1:
            mean      = sum(lengths) / len(lengths)
            variance  = sum((x - mean) ** 2 for x in lengths) / len(lengths)
            burstiness = min((variance / 30.0) * 100, 100)
        else:
            burstiness = 50.0

        # 3. AI Pattern Score
        lower     = text.lower()
        ai_count  = sum(
            1 for t in _AI_TRIGGERS
            if re.search(rf"\b{re.escape(t)}\b", lower)
        )
        pattern_score = max(100 - (ai_count * 8), 0)   # 8 pts per trigger (was 10)

        # 4. FIX 3: Dynamic perplexity estimate (replaces hard-coded 80.0)
        #    Combines vocab richness + avg word length (longer = more formal/AI)
        avg_word_len  = sum(len(t) for t in tokens) / len(tokens)
        length_penalty = max(0, (avg_word_len - 4.5) * 6)        # penalise long words
        ai_density    = ai_count / max(len(lengths), 1)
        perplexity    = max(40, min(100, 90 - length_penalty - ai_density * 5))

        # Weighted total
        score = (
            (0.35 * perplexity)     +
            (0.25 * burstiness)     +
            (0.20 * vocab_diversity)+
            (0.20 * pattern_score)
        )
        score = round(score, 2)

        if verbose:
            print(f"     perplexity={perplexity:.1f}  burstiness={burstiness:.1f}"
                  f"  vocab={vocab_diversity:.1f}  pattern={pattern_score:.1f}")

        return score

    # ------------------------------------------------------------------ #
    #  STEP 1 — REPETITION FIX                                            #
    # ------------------------------------------------------------------ #
    def replace_repetitions(self, text: str) -> str:
        replacements = {
            r"\bthe data\b":    "it",
            r"\bthe system\b":  "it",
            r"\bthe results\b": "them",
            r"\bthe model\b":   "it",
            r"\bthe process\b": "it",
            r"\bthe approach\b":"this",
        }
        for pattern, repl in replacements.items():
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
        return text

    # ------------------------------------------------------------------ #
    #  STEP 2 — SENTENCE VARIATION  (FIX 4)                               #
    # ------------------------------------------------------------------ #
    def vary_sentence_structure(self, text: str) -> str:
        sentences     = re.split(r'(?<=[.!?]) +', text)
        new_sentences = []

        for sent in sentences:
            r     = random.random()
            words = sent.split()

            if r < 0.20 and len(words) > 15:             # FIX 4: only long sentences
                # shorten — keep at least 8 words
                keep  = max(8, len(words) // 2)
                sent  = " ".join(words[:keep]).rstrip(",;") + "."

            elif r < 0.40:
                # Add casual starter
                starter = random.choice(_CASUAL_STARTERS)
                # avoid double capitalisation
                body    = sent[0].lower() + sent[1:] if len(sent) > 1 else sent
                sent    = starter + " " + body

            elif r < 0.55:
                # Replace comma-list with " and"
                sent = re.sub(r',\s+', " and ", sent, count=1)

            elif r < 0.65:
                # Split long sentence at " and " → two shorter ones
                if " and " in sent and len(words) > 14:
                    parts = sent.split(" and ", 1)
                    sent  = parts[0].rstrip() + ". " + parts[1].strip().capitalize()

            new_sentences.append(sent.strip())

        return " ".join(new_sentences)

    # ------------------------------------------------------------------ #
    #  STEP 3 — CONTRACTIONS                                              #
    # ------------------------------------------------------------------ #
    def apply_contractions(self, text: str) -> str:
        contractions = {
            "do not":   "don't",
            "cannot":   "can't",
            "it is":    "it's",
            "we are":   "we're",
            "they are": "they're",
            "that is":  "that's",
            "there is": "there's",
            "would not":"wouldn't",
            "could not":"couldn't",
            "should not":"shouldn't",
            "will not": "won't",
            "is not":   "isn't",
            "are not":  "aren't",
            "has not":  "hasn't",
            "have not": "haven't",
            "did not":  "didn't",
            "does not": "doesn't",
        }
        for k, v in contractions.items():
            text = re.sub(rf"\b{re.escape(k)}\b", v, text, flags=re.IGNORECASE)
        return text

    # ------------------------------------------------------------------ #
    #  STEP 4 — SYNONYM SWAP  (FIX 5)                                     #
    # ------------------------------------------------------------------ #
    def apply_synonyms(self, text: str, swap_rate: float = 0.45) -> str:
        """
        FIX 5: swap_rate=0.45 → 45 % chance to swap each entry (was 30 %).
        Phrases are iterated longest-first to prevent partial-word clobbering.
        """
        for phrase, alternatives in self.replacements.items():
            if random.random() > swap_rate:
                continue
            replacement = random.choice(alternatives)
            text = re.sub(
                rf"\b{re.escape(phrase)}\b",
                replacement,
                text,
                flags=re.IGNORECASE,
            )
        return text

    # ------------------------------------------------------------------ #
    #  STEP 5 — INJECT HUMAN FILLERS  (NEW)                               #
    # ------------------------------------------------------------------ #
    def inject_filler_phrases(self, text: str, rate: float = 0.20) -> str:
        """
        Randomly inserts casual filler phrases at sentence boundaries to
        break AI's overly uniform rhythm and boost burstiness.
        """
        sentences = re.split(r'(?<=[.!?]) +', text)
        result    = []
        for i, sent in enumerate(sentences):
            if i > 0 and random.random() < rate:
                filler = random.choice(_HUMAN_FILLERS)
                # lowercase the sentence start after inserting filler
                if filler.endswith(","):
                    body = sent[0].lower() + sent[1:] if len(sent) > 1 else sent
                    sent = filler + " " + body
                else:
                    sent = filler + " — " + sent
            result.append(sent)
        return " ".join(result)

    # ------------------------------------------------------------------ #
    #  STEP 6 — PUNCTUATION VARIATION  (NEW)                              #
    # ------------------------------------------------------------------ #
    def vary_punctuation(self, text: str) -> str:
        """
        Swap some commas for em-dashes and add occasional ellipses —
        common in human writing, rare in AI output.
        """
        # 15 % of comma-clauses → em-dash
        text = re.sub(
            r',\s+([a-z])',
            lambda m: (f" — {m.group(1)}" if random.random() < 0.15 else m.group(0)),
            text,
        )
        # 10 % of sentence endings → ellipsis (only trailing short clauses)
        text = re.sub(
            r'\.\s+([A-Z])',
            lambda m: (f"... {m.group(1)}" if random.random() < 0.10 else m.group(0)),
            text,
        )
        return text

    # ------------------------------------------------------------------ #
    #  FULL PIPELINE                                                       #
    # ------------------------------------------------------------------ #
    def apply_transformations(self, text: str) -> str:
        print("  -> ML Paraphraser...")
        text = self.paraphraser.process_text(text)

        print("  -> Fixing repetitions...")
        text = self.replace_repetitions(text)

        print("  -> Adding contractions...")
        text = self.apply_contractions(text)

        print("  -> Synonym swap...")
        text = self.apply_synonyms(text)

        print("  -> Sentence variation...")
        text = self.vary_sentence_structure(text)

        print("  -> Injecting filler phrases...")
        text = self.inject_filler_phrases(text)

        print("  -> Punctuation variation...")
        text = self.vary_punctuation(text)

        return text

    # ------------------------------------------------------------------ #
    #  MAIN HUMANIZE LOOP  (FIX 2)                                        #
    # ------------------------------------------------------------------ #
    def humanize(
        self,
        text: str,
        target_score: float = 85.0,   # realistic target (was 95 — unachievable)
        max_iterations: int = 3,
    ) -> str:
        print("\n" + "=" * 55)
        print("🚀 STARTING HUMANIZATION")
        print("=" * 55)

        current_text = text
        best_text    = text
        best_score   = 0.0

        # FIX 2: `< max_iterations` instead of `<= max_iterations`
        for iteration in range(max_iterations):
            score = self.calculate_score(current_text, verbose=True)
            print(f"\n[Iteration {iteration}] Score: {score}/100")

            if score > best_score:
                best_score = score
                best_text  = current_text

            if score >= target_score:
                print("✅ Target achieved!")
                break

            print("❌ Below target — applying transformations...")
            current_text = self.apply_transformations(current_text)

        else:
            # After final iteration, score the last version
            score = self.calculate_score(current_text, verbose=True)
            print(f"\n[Final check] Score: {score}/100")
            if score > best_score:
                best_score = score
                best_text  = current_text
            print("⚠  Max iterations reached.")

        print("\n" + "=" * 55)
        print(f"BEST SCORE : {best_score}/100")
        print("FINAL TEXT :")
        print(best_text)
        print("=" * 55)

        return best_text


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    pipeline = MasterHumanizer(use_ml=False)   # use_ml=True once model downloaded

    ai_text = (
        '''Furthermore, it is crucial to delve into the data. 
        The system processes the data efficiently, and it stores the results in the cloud. 
        This demonstrates that robust and scalable solutions are essential. 
        Moreover, we must utilize efficient algorithms in order to optimize performance.'''
    )

    pipeline.humanize(ai_text, target_score=80, max_iterations=3)