;; Local, one-shot OmegaClaw agent proof. The provider and channel are loaded
;; through OmegaClaw Core's Python plugin mechanism; the core runtime remains
;; unmodified and continues to provide the MeTTa NAL/PLN substrate.

!(import! &self (library lib_import))
!(git-import! "https://github.com/asi-alliance/OmegaClaw-Core.git" "" "./repos" "9890bcb8041598fc6a4f1d8e658b8306a204cc87")
!(import! &self (library OmegaClaw-Core lib_omegaclaw))
!(omegaclaw)
