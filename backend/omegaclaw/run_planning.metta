;; One-shot OmegaClaw planning run. The request is supplied through the
;; HelixMind planning channel; no literature or external channel is enabled.
!(import! &self (library lib_import))
!(git-import! "https://github.com/asi-alliance/OmegaClaw-Core.git" "" "./repos" "9890bcb8041598fc6a4f1d8e658b8306a204cc87")
!(import! &self (library OmegaClaw-Core lib_omegaclaw))
!(omegaclaw)
