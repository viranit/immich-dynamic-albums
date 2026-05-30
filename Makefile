# Immich Dynamic Albums — translation & development helpers
.PHONY: i18n-extract i18n-update i18n-compile i18n-add-lang help

BABEL   := pybabel
CFG     := babel.cfg
POT     := translations/messages.pot
TRANS   := translations

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*##"}{printf "  %-22s %s\n",$$1,$$2}'

i18n-extract:  ## Extract translatable strings into the .pot template
	$(BABEL) extract -F $(CFG) -k lazy_gettext -o $(POT) .

i18n-update:  ## Update all existing .po files from the .pot template
	$(BABEL) update -i $(POT) -d $(TRANS)

i18n-compile:  ## Compile all .po files into binary .mo files
	$(BABEL) compile -d $(TRANS) --statistics

i18n-add-lang:  ## Add a new language, e.g.: make i18n-add-lang LANG=de
	$(BABEL) init -i $(POT) -d $(TRANS) -l $(LANG)

run-dev:  ## Start development server
	flask run --debug

test:  ## Run the test suite
	pytest
