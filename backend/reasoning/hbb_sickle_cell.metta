;; HelixMind's minimal OmegaClaw/MeTTa scientific knowledge proof.
;; Premises are source facts, not clinical guidance. STV values represent
;; system evidence assessment and are not validated medical probabilities.

!(import! &self (library lib_import))
!(git-import! "https://github.com/asi-alliance/OmegaClaw-Core.git" "" "./repos" "9890bcb8041598fc6a4f1d8e658b8306a204cc87")
!(import! &self (library OmegaClaw-Core lib_nal))

;; Source provenance is retained as an explicit AtomSpace fact.
(source HBB_HbS_Study PubMed PMID_10000001)

;; A two-hop NAL deduction over source-grounded scientific statements.
!(|- ((--> HBB HbSVariant) (stv 1.0 0.95))
     ((--> HbSVariant SickleCellDisease) (stv 1.0 0.90)))
